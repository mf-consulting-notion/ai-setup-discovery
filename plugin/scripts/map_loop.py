#!/usr/bin/env python3
"""Drives the session map so that mapper agents only fill in fields.

    python3 -I map_loop.py plan       --run DIR [--light] [--cap 150] [--second 15]
    python3 -I map_loop.py next       --run DIR --agent NAME [--pass verify]
    python3 -I map_loop.py submit     --run DIR --agent NAME [--pass verify]   < record.json
    python3 -I map_loop.py status     --run DIR
    python3 -I map_loop.py aggregate  --run DIR

`next` claims one unmapped session atomically and prints its skeleton (masked) or the line
"DONE". `submit` validates the record against schemas/session-record.json, checks that its
session id is the one this agent claimed, and appends it. On success it immediately claims and
prints the next skeleton (or DONE), so a mapper needs one call per session. Rejections print the reason and exit 1,
so the agent can fix the record and resubmit. Parallel agents never share files.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover  # noqa: E402
import evidence  # noqa: E402
import validate  # noqa: E402

FULL_CAP, LIGHT_CAP = 150, 40
AUTOMATED = ("scheduled", "scripted")   # session origins whose sessions no person started
AUTOMATED_SHARE = 0.25
COMPARED = ("work_kind", "work_category", "workflow", "pipeline_stage", "start_trigger", "interaction_mode", "outcome", "dictation_markers")


class Map:
    def __init__(self, run_dir: Path):
        self.run = discover.Run(run_dir)
        self.dir = self.run.local / "map"
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.dir / name

    def queue(self, pass_: str = "map") -> list[dict]:
        p = self.path("queue.json" if pass_ == "map" else "queue-verify.json")
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    def skipped(self, pass_: str = "map") -> set:
        p = self.path("skipped.txt" if pass_ == "map" else "skipped-verify.txt")
        return set(p.read_text().split()) if p.exists() else set()

    def skip(self, pass_: str, sid: str) -> None:
        with open(self.path("skipped.txt" if pass_ == "map" else "skipped-verify.txt"), "a") as fh:
            fh.write(sid + "\n")

    def records(self, pass_: str = "map") -> dict[str, dict]:
        p = self.path("records.jsonl" if pass_ == "map" else "records-verify.jsonl")
        return {d["session"]: d for d in evidence._records(p)} if p.exists() else {}


def _rank(sid: str) -> str:
    return hashlib.sha1(sid.encode()).hexdigest()


def sample(sessions, cap: int) -> list:
    """Deterministic. Automated sessions (scheduled, scripted) take at most a quarter of the cap and
    the rest goes to everything else, so pipelines stay visible without crowding out a person's own
    work; when there is too little of the rest, the sample stays under the cap rather than refill
    with automated sessions. This holds below the cap too. Within each group: proportional by surface,
    at least min(20, available)."""
    auto = [s for s in sessions if s.origin in AUTOMATED]
    rest = [s for s in sessions if s.origin not in AUTOMATED]
    n_auto = min(len(auto), round(AUTOMATED_SHARE * cap))
    picked = _by_surface(auto, n_auto) + _by_surface(rest, min(len(rest), cap - n_auto))
    return sorted(picked, key=lambda s: s.started)


def _by_surface(sessions, cap: int) -> list:
    if len(sessions) <= cap:
        return list(sessions)
    by = collections.defaultdict(list)
    for s in sessions:
        by[s.surface].append(s)
    quota = {k: max(min(20, len(v)), round(cap * len(v) / len(sessions))) for k, v in by.items()}
    while sum(quota.values()) > cap:
        k = max(quota, key=lambda x: quota[x])
        quota[k] -= 1
    picked = []
    for k, v in by.items():
        picked += sorted(v, key=lambda s: _rank(s.id))[:quota[k]]
    return picked


def eligible(s) -> bool:
    """Two or more prompts, or one handed-over task that ran for at least a minute (Cowork, Codex)."""
    return s.prompts >= 2 or (s.prompts == 1 and s.active_ms >= 60000)


def cmd_plan(m: Map, a) -> dict:
    ss = [s for s in m.run.sessions(1) if eligible(s)]
    cap = int(a.get("--cap") or (LIGHT_CAP if a.get("--light") is not None else FULL_CAP))
    picked = sample(ss, cap)
    q = [{"session": s.id, "surface": s.surface, "origin": s.origin, "path": str(s.path)} for s in picked]
    m.path("queue.json").write_text(json.dumps(q, indent=1), encoding="utf-8")
    n2 = int(a.get("--second") or 15)
    verify = sorted(q, key=lambda x: _rank("v" + x["session"]))[:n2]
    m.path("queue-verify.json").write_text(json.dumps(verify, indent=1), encoding="utf-8")
    for d in ("claims", "claims-verify"):
        (m.dir / d).mkdir(exist_ok=True)
    in_window = collections.Counter(s.origin for s in m.run.sessions(1))
    el, sa = collections.Counter(s.origin for s in ss), collections.Counter(x["origin"] for x in q)
    by_origin = {o: {"in_window": in_window[o], "eligible": el[o], "sampled": sa[o]} for o in evidence.ORIGINS if in_window[o]}
    info = {"eligible": len(ss), "queued": len(q), "sampled": len(q) < len(ss), "cap": cap, "by_origin": by_origin}
    m.path("plan.json").write_text(json.dumps(info), encoding="utf-8")
    return {"eligible": len(ss), "queued": len(q), "sampled": len(q) < len(ss),
            "by_surface": dict(collections.Counter(x["surface"] for x in q)), "by_origin": by_origin, "second_coder": len(verify)}


def _claim(m: Map, pass_: str, sid: str, agent: str) -> bool:
    d = m.dir / ("claims" if pass_ == "map" else "claims-verify")
    try:
        fd = os.open(str(d / f"{sid}.claim"), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as fh:
        fh.write(agent)
    return True


def _claimed_by(m: Map, pass_: str, sid: str) -> str | None:
    p = m.dir / ("claims" if pass_ == "map" else "claims-verify") / f"{sid}.claim"
    return p.read_text().strip() if p.exists() else None


def cmd_next(m: Map, agent: str, pass_: str) -> str:
    done = set(m.records(pass_)) | m.skipped(pass_)
    q = m.queue(pass_)
    by_id = {(x.id, str(x.path)): x for x in m.run.sessions(0)}
    # an agent that claimed a session but never submitted gets the same one back
    candidates = [i for i in q if i["session"] not in done and _claimed_by(m, pass_, i["session"]) == agent]
    candidates += [i for i in q if i["session"] not in done and _claimed_by(m, pass_, i["session"]) is None]
    for item in candidates:
        if _claimed_by(m, pass_, item["session"]) != agent and not _claim(m, pass_, item["session"], agent):
            continue
        s = by_id.get((item["session"], item["path"]))
        if s is None:   # transcript gone or unreadable since planning: recorded as skipped, never coded
            m.skip(pass_, item["session"])
            continue
        return _emit(m, s, agent)
    return "DONE"


def _emit(m: Map, s, agent: str) -> str:
    sk = evidence.skeleton(s, aliases=m.run.aliases())
    sk = sk.encode("utf-8", "replace").decode("utf-8")
    tmp = m.run.local / "tmp" / agent
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "current.txt").write_text(sk, encoding="utf-8")
    return sk


def cmd_submit(m: Map, agent: str, pass_: str, raw: str) -> tuple[int, dict]:
    try:
        rec = json.loads(raw)
    except ValueError as e:
        return 1, {"accepted": False, "reason": f"not valid JSON: {e}"}
    if not isinstance(rec, dict):
        return 1, {"accepted": False, "reason": "record must be a JSON object"}
    sid = rec.get("session")
    owner = _claimed_by(m, pass_, str(sid))
    if owner != agent:
        return 1, {"accepted": False, "reason": f"session {sid!r} is not the one you claimed; run next again and copy the id from the header"}
    if sid in m.records(pass_):
        return 1, {"accepted": False, "reason": f"session {sid} already recorded"}
    errs = validate.validate(rec, validate.load_schema("session-record"))
    if errs:
        return 1, {"accepted": False, "reason": "schema", "errors": errs[:10]}
    origin = next((x.get("origin") for x in m.queue(pass_) if x["session"] == sid), None)
    if origin in AUTOMATED and rec.get("start_trigger") != "automated":
        return 1, {"accepted": False, "reason": f"the skeleton header says origin {origin}: start_trigger must be \"automated\""}
    text = m.run.aliases().mask(evidence.mask_secrets(json.dumps(rec, ensure_ascii=False)))
    with open(m.path("records.jsonl" if pass_ == "map" else "records-verify.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(text + "\n")
    left = len([x for x in m.queue(pass_) if x["session"] not in m.records(pass_) and x["session"] not in m.skipped(pass_)])
    return 0, {"accepted": True, "session": sid, "remaining": left}


def cmd_status(m: Map) -> dict:
    out = {}
    for p in ("map", "verify"):
        q, r, sk = m.queue(p), m.records(p), m.skipped(p)
        out[p] = {"queued": len(q), "recorded": len(r), "skipped_unreadable": len(sk),
                  "remaining": len([x for x in q if x["session"] not in r and x["session"] not in sk])}
    return out


def agreement(a: dict, b: dict) -> dict:
    shared = sorted(set(a) & set(b))
    res = {}
    for f in COMPARED:
        if shared:
            res[f] = round(sum(a[s].get(f) == b[s].get(f) for s in shared) / len(shared), 2)
    if shared:
        def ftypes(r):
            return {x["type"] for x in r.get("friction", [])}
        def jaccard(x, y):
            return 1.0 if not x and not y else len(x & y) / len(x | y)   # both "no friction" is agreement
        res["friction_types_jaccard"] = round(sum(jaccard(ftypes(a[s]), ftypes(b[s])) for s in shared) / len(shared), 2)
        res["friction_any"] = round(sum(bool(a[s].get("friction")) == bool(b[s].get("friction")) for s in shared) / len(shared), 2)
        res["supervision_ran_unattended"] = round(sum(a[s]["supervision_markers"]["ran_unattended"] == b[s]["supervision_markers"]["ran_unattended"] for s in shared) / len(shared), 2)
    res["sessions_compared"] = len(shared)
    vals = [v for k, v in res.items() if k != "sessions_compared"]
    res["overall"] = round(sum(vals) / len(vals), 2) if vals else None
    return res


def cmd_aggregate(m: Map) -> dict:
    recs = list(m.records().values())
    n = len(recs)
    C = collections.Counter
    act0 = discover._load(m.run.local / "collectors" / "activity.json") or {}
    q = m.queue()
    # canonical bases: the report quotes these names, so every count says what it is out of
    agg = {"bases": {"sessions_in_window": act0.get("sessions"), "projects_in_window": act0.get("projects"),
                     "eligible_for_map": (discover._load(m.path("plan.json")) or {}).get("eligible"), "queued_for_map": len(q), "mapped": n,
                     "second_coded": len(m.records("verify")), "window_days": m.run.window},
           "sessions_mapped": n, "queue": cmd_status(m),
           "note": "every distribution below sums to bases.mapped; friction counts give instances and sessions separately"}
    for f in COMPARED:
        agg[f] = dict(C(r.get(f) or "unspecified" for r in recs).most_common())
    agg["by_work_kind_and_workflow"] = dict(C(f"{r['work_kind']} / {r['workflow']}" for r in recs).most_common(25))
    act = discover._load(m.run.local / "collectors" / "activity.json") or {}
    minutes = {r["session"]: r.get("active_min") or 0 for r in act.get("per_session", [])}
    tools = (discover._load(m.run.local / "collectors" / "tools.json") or {}).get("per_session", {})
    by_wf = {}
    for wf in sorted({r["workflow"] for r in recs}):
        rs = [r for r in recs if r["workflow"] == wf]
        mins = sorted(minutes.get(r["session"], 0) for r in rs)
        by_wf[wf] = {"sessions": len(rs), "active_hours": round(sum(mins) / 60, 1), "active_min_median": mins[len(mins) // 2] if mins else None,
                     "outcomes": dict(C(r["outcome"] for r in rs)), "sessions_with_friction": sum(1 for r in rs if r.get("friction")),
                     "measured_wait_min_over_60s": round(sum(tools.get(r["session"], {}).get("wait_min_over_60s", 0) for r in rs), 1)}
    agg["by_workflow_time"] = by_wf
    agg["by_work_kind_time"] = {k: {"sessions": sum(1 for r in recs if r["work_kind"] == k),
                                    "active_hours": round(sum(minutes.get(r["session"], 0) for r in recs if r["work_kind"] == k) / 60, 1)}
                                for k in sorted({r["work_kind"] for r in recs})}
    fr = [x for r in recs for x in r.get("friction", [])]
    agg["friction"] = {"sessions_with_friction": sum(1 for r in recs if r.get("friction")),
                       "instances": len(fr),
                       "by_type_instances": dict(C(x["type"] for x in fr).most_common()),
                       "by_type_sessions": dict(C(t for r in recs for t in {x["type"] for x in r.get("friction", [])}).most_common()),
                       "by_cause": dict(C(x["cause"] for x in fr).most_common()),
                       "by_caught_at": dict(C(x["caught_at"] for x in fr).most_common()),
                       "avoidable": dict(C(x["avoidable"] for x in fr).most_common()),
                       "type_x_cause": dict(C(f"{x['type']} / {x['cause']}" for x in fr).most_common(20))}
    for key in ("corrections", "restatements"):
        sess = C()
        for r in recs:
            for k in {x["key"] for x in r.get(key, [])}:
                sess[k] += 1
        agg[f"{key}_by_key_sessions"] = dict(sess.most_common(25))
    for key in ("skills_invoked", "gates_stated", "inbound_sources", "artefact_destinations", "systems_mentioned"):
        agg[key] = dict(C(v for r in recs for v in set(r.get(key, []))).most_common(25))
    agg["fluency_share"] = {k: round(sum(r["fluency"][k] for r in recs) / n, 2) for k in recs[0]["fluency"]} if n else {}
    sup = [r["supervision_markers"] for r in recs]
    agg["supervision"] = {"unattended_share": round(sum(s["ran_unattended"] for s in sup) / n, 2) if n else None,
                          "approval_requests_median": sorted(s["approval_requests"] for s in sup)[n // 2] if n else None,
                          "participant_turns_median": sorted(s["participant_turns"] for s in sup)[n // 2] if n else None}
    agg["agreement"] = agreement(m.records(), m.records("verify"))
    m.path("aggregate.json").write_text(json.dumps(agg, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"sessions_mapped": n, "agreement_overall": agg["agreement"].get("overall"), "written": str(m.path("aggregate.json"))}


def main(argv=None, stdin=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help") or "--run" not in argv:
        print(__doc__)
        return 2
    cmd, a = argv[0], discover.Args(argv[1:])
    m = Map(Path(os.path.expanduser(a.get("--run"))))
    pass_ = "verify" if a.get("--pass") == "verify" else "map"
    if cmd in ("next", "submit") and not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", a.get("--agent") or ""):
        print(f"{cmd} needs --agent NAME (letters, digits, - and _ only)")
        return 2
    if cmd == "next":
        print(cmd_next(m, a.get("--agent"), pass_))
        return 0
    if cmd == "submit":
        code, res = cmd_submit(m, a.get("--agent"), pass_, (stdin or sys.stdin).read())
        print(json.dumps(res, ensure_ascii=False))
        if code == 0:
            print("\n--- next ---\n" + cmd_next(m, a.get("--agent"), pass_))
        return code
    res = {"plan": lambda: cmd_plan(m, a), "status": lambda: cmd_status(m), "aggregate": lambda: cmd_aggregate(m)}[cmd]()
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
