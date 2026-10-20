#!/usr/bin/env python3
"""Discovery run collectors and run-folder plumbing. Standard library only, read-only on the
participant's files; writes only inside the run folder.

    python3 -I discover.py init      (--out DIR | --parent DIR) [--home H] [--window 30]
    python3 -I discover.py import-chat --run DIR --export FILE   claude.ai data export (.zip or conversations.json)
    python3 -I discover.py probe     --run DIR
    python3 -I discover.py aliases   --run DIR [--add "Name=replacement" ...] [--keep FOLDER ...] [--show]
    python3 -I discover.py collect   --run DIR [--only config,memory,activity,tools,environment]
    python3 -I discover.py self-assess --run DIR [--model opus]   fresh headless session from the home folder
    python3 -I discover.py show      --run DIR --collector NAME [--keys a,b.c] [--max 20000]   read part of a collector
    python3 -I discover.py elements  --run DIR            validate .local/elements/*.jsonl against the schema
    python3 -I discover.py assemble  --run DIR            write the bundle files (README, collectors, sections, elements, manifest)

Every collector writes DIR/.local/collectors/<name>.json and prints a one-line summary. A
missing source yields {"present": false, "reason": ...}: absence is data. All collector output
passes through the alias table and the secret mask before it is written.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402

def _plugin_version() -> str | None:
    try:
        return json.loads((Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return None


SKILL_VERSION = _plugin_version()   # plugin.json is the one place the version lives
MIN_CLAUDE = (2, 1, 275)   # older CLIs fail the headless self-assessment (pilot, 2.1.55)
CODEBOOK_VERSION = "0.4.0"
AREAS = ("environment", "session_behaviour", "context_memory", "skills", "connectors", "automation", "self_assessment")
AREAS_ELEMENTS = AREAS + ("intake",)   # intake has elements but no section
C = collections.Counter


# ---------------------------------------------------------------- run folder

class Run:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.local = self.root / ".local"
        self.send = self.root / "send"   # the run bundle: the only thing the participant sends
        cfg = json.loads((self.local / "run.json").read_text(encoding="utf-8"))
        self.home = Path(cfg["home"])
        self.window = int(cfg["window_days"])
        self.id = cfg["run_id"]
        self.now = dt.datetime.fromisoformat(cfg["now"]) if cfg.get("now") else dt.datetime.now(dt.timezone.utc)

    def sessions(self, min_prompts: int = 1):
        """Frozen at probe time (.local/session-index.json), so every step sees the same set and the
        run's own, growing session never becomes data."""
        if not hasattr(self, "_sessions"):
            found = evidence.sessions(self.home, self.window, self.now, min_prompts=0, chat_dir=self.local / "chat")
            idx = self.local / "session-index.json"
            if idx.exists():
                keep = set(json.loads(idx.read_text(encoding="utf-8")))
                found = [s for s in found if str(s.path) in keep]
            self._sessions = found
        return [s for s in self._sessions if s.total_prompts >= min_prompts]

    def freeze(self, exclude_newer_than_minutes: int = 0) -> int:
        ss = [s for s in self.sessions(0)
              if not (exclude_newer_than_minutes and s.started and s.started > self.now - dt.timedelta(minutes=exclude_newer_than_minutes))]
        (self.local / "session-index.json").write_text(json.dumps(sorted(str(s.path) for s in ss)), encoding="utf-8")
        self._sessions = ss
        return len(ss)


    def aliases(self) -> evidence.AliasTable:
        p = self.local / "aliases.json"
        return evidence.AliasTable.load(p) if p.exists() else evidence.AliasTable.build(s.project_key for s in self.sessions(0))

    def write_collector(self, name: str, data: dict) -> dict:
        aliases = self.aliases()
        text = aliases.mask_json_text(json.dumps(data, ensure_ascii=False, default=str))
        out = self.local / "collectors" / f"{name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return json.loads(text)


def cmd_init(a) -> dict:
    if not (a.get("--out") or a.get("--parent")):
        raise SystemExit("init needs --out DIR or --parent DIR")
    home = Path(os.path.expanduser(a.get("--home") or "~"))
    now = a.get("--now")
    run_id = (dt.datetime.fromisoformat(now) if now else dt.datetime.now()).strftime("%Y%m%d-%H%M")
    out = Path(os.path.expanduser(a.get("--out"))) if a.get("--out") else Path(os.path.expanduser(a.get("--parent"))) / f"ai-work-discovery-{run_id}"
    for d in ("collectors", "map", "tmp", "sections", "elements"):
        (out / ".local" / d).mkdir(parents=True, exist_ok=True)
    cfg = {"run_id": run_id, "home": str(home), "window_days": int(a.get("--window") or 30), "now": now,
           "created": dt.datetime.now(dt.timezone.utc).isoformat(), "skill_version": SKILL_VERSION}
    (out / ".local" / "run.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    return {"run": str(out), "run_id": run_id}


# ---------------------------------------------------------------- probe

def _which_version(cmd: str) -> str | None:
    exe = shutil.which(cmd)
    if not exe:
        return None
    try:
        return subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()[:80] or "present"
    except Exception:
        return "present"


def cmd_import_chat(run: Run, a) -> dict:
    export = Path(os.path.expanduser(a.get("--export") or ""))
    if not export.is_file():
        return {"imported": 0, "reason": "export file not found"}
    n = evidence.import_chat_export(export, run.local / "chat")
    return {"imported": n}


def cmd_probe(run: Run) -> dict:
    files = evidence.transcript_files(run.home, run.local / "chat")
    # sessions started in the last 10 minutes are this run's own (or another live one): not data
    if not (run.local / "session-index.json").exists():
        run.freeze(exclude_newer_than_minutes=10)
    ss = run.sessions(0)
    by = C(s.surface for s in ss if s.total_prompts)
    data = {
        "os": platform.system(), "os_release": platform.release(), "python": platform.python_version(),
        "claude_cli": _which_version("claude"), "codex_cli": _which_version("codex"),
        "window_days": run.window,
        "sources": {
            "claude_code_transcripts": len(files["claude_code"]), "cowork_transcripts": len(files["cowork"]),
            "codex_transcripts": len(files["codex"]), "chat_export_conversations": len(files["chat"]),
            "claude_dir": (run.home / ".claude").is_dir(), "codex_dir": (run.home / ".codex").is_dir(),
            "prompt_history": (run.home / ".claude" / "history.jsonl").exists(),
        },
        "sessions_in_window": dict(by), "sessions_in_window_total": sum(by.values()),
        "oldest_in_window": min((s.started for s in ss if s.total_prompts and s.started), default=None),
        "projects_in_window": len({s.project_key for s in ss if s.total_prompts}),
    }
    oldest = evidence.oldest_record(f for fs in files.values() for f in fs)
    span = round((run.now - oldest).total_seconds() / 86400, 1) if oldest else 0
    data["transcript_span_days"] = span
    data["window_coverage_days"] = min(run.window, span)
    data["suggested_path"] = "local" if data["sessions_in_window_total"] >= 5 else "chat"
    return run.write_collector("probe", data)


# ---------------------------------------------------------------- aliases

def cmd_aliases(run: Run, a) -> dict:
    t = run.aliases()
    for s in run.sessions(0):
        t.label(s.project_key)
    for k in a.getall("--keep"):
        t.keep_folder(k)
    for add in a.getall("--add"):
        name, _, rep = add.partition("=")
        t.add_name(name, rep.strip() or "a third party")
    t.save(run.local / "aliases.json")
    shown = {"projects": len(t.projects), "names": len(t.names)}
    if a.get("--show") is not None:
        # The orchestrator shows these to the participant at intake; this is the only place real names are printed.
        shown["hidden_project_folders"] = _hidden_folders(t)
        shown["hidden_names"] = sorted(t.names)
    return shown


def _hidden_folders(t: evidence.AliasTable) -> list:
    bases = {k.replace("\\", "/").rstrip("/").split("/")[-1] for k in t.projects}
    # only names that are actually masked (ordinary words like "projects" or "tmp" never are)
    return sorted(b for b in bases if evidence.folder_variants(b) and b.lower() not in {k.lower() for k in t.keep})


# ---------------------------------------------------------------- collectors

def _load(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    fm, cur = {}, None
    if not m:
        return fm
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if mm:
            cur = mm.group(1)
            fm[cur] = mm.group(2).strip()
        elif cur and line.startswith((" ", "\t")):
            fm[cur] += " " + line.strip()
    return {k: v.strip().strip("'\"") if v.strip() not in (">", "|", ">-", "|-") else "" for k, v in fm.items()}


def _date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _ms_date(v):
    return dt.datetime.fromtimestamp(v / 1000).date().isoformat() if isinstance(v, (int, float)) else None


def _dist(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return {}
    return {"n": len(v), "min": v[0], "median": statistics.median(v), "p90": v[min(len(v) - 1, int(len(v) * .9))], "max": v[-1]}


def _skill_inventory(d: Path) -> list[dict]:
    out = []
    if not d.is_dir():
        return out
    for e in sorted(d.iterdir()):
        f = e / "SKILL.md"
        if e.name.startswith(".") or not e.is_dir():
            continue
        rec = {"name": e.name, "symlink": e.is_symlink(), "has_skill_md": f.exists()}
        if f.exists():
            t = f.read_text(encoding="utf-8", errors="ignore")
            fm = _frontmatter(t)
            rec.update(desc_chars=len(fm.get("description", "")), description=fm.get("description", "")[:400], lines=t.count("\n"),
                       user_only=fm.get("disable-model-invocation", "").lower() == "true",
                       modified=_date(f.stat().st_mtime))
        out.append(rec)
    return out


def col_config(run: Run) -> dict:
    c = run.home / ".claude"
    if not c.is_dir():
        return {"present": False, "reason": "no ~/.claude directory"}
    out: dict = {"present": True}
    for name in ("settings.json", "settings.local.json"):
        d = _load(c / name)
        if not isinstance(d, dict):
            continue
        p = d.get("permissions") if isinstance(d.get("permissions"), dict) else {}
        hooks = d.get("hooks") if isinstance(d.get("hooks"), dict) else {}
        env = d.get("env") if isinstance(d.get("env"), dict) else {}
        plugins = d.get("enabledPlugins") if isinstance(d.get("enabledPlugins"), dict) else {}

        def n(x):
            return len(x) if isinstance(x, list) else 0

        def hook_count(ms):
            return sum(n(m.get("hooks")) for m in ms if isinstance(m, dict)) if isinstance(ms, list) else 0

        out[name] = {
            "keys": sorted(d), "model": d.get("model"), "effort": d.get("effortLevel"),
            "permissions": {"defaultMode": p.get("defaultMode"), **{k: n(p.get(k)) for k in ("allow", "deny", "ask")}},
            "hooks": {ev: hook_count(ms) for ev, ms in hooks.items()},
            "env_var_names": sorted(env.keys()), "statusline": bool(d.get("statusLine")),
            "cleanup_period_days": d.get("cleanupPeriodDays"),
            "enabled_plugins": len(plugins),
        }
    cm = c / "CLAUDE.md"
    if cm.exists():
        t = cm.read_text(encoding="utf-8", errors="ignore")
        out["user_instructions"] = {"bytes": len(t.encode()), "lines": t.count("\n"), "headings": len(re.findall(r"^#+ ", t, re.M)),
                                    "modified": _date(cm.stat().st_mtime)}
    else:
        out["user_instructions"] = {"present": False}
    for d in ("rules", "agents", "commands", "output-styles"):
        p = c / d
        out[d] = sorted(x.stem for x in p.glob("*.md")) if p.is_dir() else []
    skills = _skill_inventory(c / "skills")
    visible = [s for s in skills if s.get("has_skill_md") and not s.get("user_only")]
    out["skills"] = {"count": len(skills), "symlinked": sum(s["symlink"] for s in skills),
                     "user_only": sum(bool(s.get("user_only")) for s in skills), "model_visible": len(visible),
                     "description_chars_visible": sum(s.get("desc_chars", 0) for s in visible),
                     "missing_skill_md": [s["name"] for s in skills if not s["has_skill_md"]],
                     "detail": skills}
    plug = _load(c / "plugins" / "installed_plugins.json") or {}
    plugs = plug.get("plugins", plug) if isinstance(plug, dict) else {}
    out["plugins"] = {"installed": sorted(plugs) if isinstance(plugs, dict) else [],
                      "marketplaces": sorted((_load(c / "plugins" / "known_marketplaces.json") or {}).keys()),
                      "plugin_skills": len(list((c / "plugins" / "cache").glob("**/SKILL.md"))) if (c / "plugins" / "cache").is_dir() else 0}
    synced = list((c / "skills" / "synced").glob("*/**/SKILL.md")) + list((c / "plugins" / "synced").glob("*/**/SKILL.md"))
    out["account_synced_skills"] = len(synced)
    # ~/.claude.json: allow-listed keys only (it also holds account identity, which is never read out)
    cj = _load(run.home / ".claude.json") or {}
    su = cj.get("skillUsage") or {}
    now_ms = run.now.timestamp() * 1000
    out["mcp_servers_user"] = {k: (v.get("type") or ("stdio" if "command" in v else "?")) for k, v in (cj.get("mcpServers") or {}).items()}
    out["mcp_servers_project"] = C(n for v in (cj.get("projects") or {}).values() for n in (v.get("mcpServers") or {})).most_common()
    out["usage_counters"] = {
        "startups": cj.get("numStartups"), "first_start": cj.get("firstStartTime"), "install_method": cj.get("installMethod"),
        "skills_ever_used": len(su), "skill_uses_total": sum(v.get("usageCount", 0) for v in su.values()),
        "skills_used_in_window": sum(1 for v in su.values() if isinstance(v.get("lastUsedAt"), (int, float))
                                     and now_ms - v["lastUsedAt"] < run.window * 86400000),
        "top_skills": sorted(((k, v.get("usageCount", 0), _ms_date(v.get("lastUsedAt"))) for k, v in su.items()), key=lambda x: -x[1])[:25],
    }
    # project-level instruction files for every project folder seen in the window
    aliases, rows = run.aliases(), []
    for key in sorted({s.project_key for s in run.sessions(1)}):
        p = Path(str(key).replace("~", str(run.home), 1))
        if not p.is_dir():
            continue
        def size(f):
            q = p / f
            return {"lines": q.read_text(encoding="utf-8", errors="ignore").count("\n"), "symlink": q.is_symlink()} if q.exists() else None
        cd = p / ".claude"
        rows.append({"project": aliases.label(key), "CLAUDE.md": size("CLAUDE.md"), "AGENTS.md": size("AGENTS.md"),
                     "glossary": bool((p / "GLOSSARY.md").exists() or (p / "CONTEXT.md").exists()),
                     "mcp_json": (p / ".mcp.json").exists(), "project_settings": (cd / "settings.json").exists(),
                     "project_skills": len(list((cd / "skills").glob("*/SKILL.md"))) if cd.is_dir() else 0,
                     "project_agents": len(list((cd / "agents").glob("*.md"))) if cd.is_dir() else 0,
                     "git": (p / ".git").exists()})
    lines = [r["CLAUDE.md"]["lines"] for r in rows if r["CLAUDE.md"]]
    out["projects"] = {"seen": len(rows), "with_CLAUDE.md": len(lines), "with_AGENTS.md": sum(1 for r in rows if r["AGENTS.md"]),
                       "CLAUDE.md_lines": _dist(lines), "detail": rows}
    return out


def col_memory(run: Run) -> dict:
    proj = run.home / ".claude" / "projects"
    if not proj.is_dir():
        return {"present": False, "reason": "no ~/.claude/projects"}
    aliases = run.aliases()
    dir_to_key = {s.path.parent.name: s.project_key for s in run.sessions(0) if s.surface == "claude_code"}
    rows, types = [], C()
    now = run.now.timestamp()
    for d in sorted(proj.glob("*/memory")):
        files = [f for f in d.rglob("*") if f.is_file()]
        if not files:
            continue
        for f in files:
            if f.suffix == ".md" and f.name != "MEMORY.md":
                m = re.search(r"^\s*type:\s*(\S+)", f.read_text(encoding="utf-8", errors="ignore")[:800], re.M)
                types[m.group(1) if m else "none"] += 1
        idx = d / "MEMORY.md"
        mt = [f.stat().st_mtime for f in files]
        key = dir_to_key.get(d.parent.name)
        rows.append({"project": aliases.label(key) if key else "project outside window",
                     "files": len(files), "index_lines": idx.read_text(encoding="utf-8", errors="ignore").count("\n") if idx.exists() else None,
                     "newest_days": round((now - max(mt)) / 86400, 1), "oldest_days": round((now - min(mt)) / 86400, 1)})
    return {"present": True, "memory_dirs": len(rows), "files_total": sum(r["files"] for r in rows),
            "files_per_dir": _dist([r["files"] for r in rows]), "index_lines": _dist([r["index_lines"] for r in rows]),
            "dirs_untouched_30d": sum(1 for r in rows if r["newest_days"] > 30), "types": dict(types),
            "detail": sorted(rows, key=lambda r: -r["files"])[:20],
            "history": _history(run)}


def _history(run: Run) -> dict:
    h = run.home / ".claude" / "history.jsonl"
    if not h.exists():
        return {"present": False}
    n, slash, weeks, lens, pasted, first, last = 0, C(), C(), [], 0, None, None
    for d in evidence._records(h):
        n += 1
        disp = d.get("display") or ""
        lens.append(len(disp))
        m = re.match(r"^/([A-Za-z0-9:_-]+)(?=\s|$)", disp)
        if m:
            slash[m.group(1)] += 1
        pasted += bool(d.get("pastedContents"))
        t = d.get("timestamp")
        if isinstance(t, (int, float)):
            day = dt.datetime.fromtimestamp(t / 1000)
            weeks[day.strftime("%G-W%V")] += 1
            first = min(first or day, day)
            last = max(last or day, day)
    return {"present": True, "prompts": n, "first": first.date().isoformat() if first else None,
            "last": last.date().isoformat() if last else None, "prompts_per_week_last12": dict(sorted(weeks.items())[-12:]),
            "slash_share": round(sum(slash.values()) / max(n, 1), 3), "slash_top": slash.most_common(25),
            "prompt_chars": _dist(lens), "with_pasted_content": pasted}


def col_activity(run: Run) -> dict:
    ss = run.sessions(1)
    if not ss:
        return {"present": False, "reason": "no sessions with prompts in the window"}
    aliases = run.aliases()
    rows = [{"session": s.id, "surface": s.surface, "project": aliases.label(s.project_key),
             "date": s.started.date().isoformat() if s.started else None, "hour": s.started.astimezone().hour if s.started else None,
             "weekday": s.started.astimezone().strftime("%a") if s.started else None,
             "active_min": round(s.active_ms / 60000, 1), "active_source": s.active_source, "wall_min": s.wall_min,
             "prompts": s.prompts, "slash_commands": s.slash_commands, "model": s.model, "origin": s.origin} for s in ss]
    by_surface = {}
    for surf in sorted({r["surface"] for r in rows}):
        x = [r for r in rows if r["surface"] == surf]
        by_surface[surf] = {"sessions": len(x), "active_hours": round(sum(r["active_min"] for r in x) / 60, 1),
                            "active_min": _dist([r["active_min"] for r in x]), "prompts": _dist([r["prompts"] for r in x]),
                            "models": C(r["model"] for r in x).most_common(5)}
    proj = C()
    for r in rows:
        proj[r["project"]] += r["active_min"] / 60
    # concurrency from 5-minute activity slots, so idle days inside a long-lived session don't count
    slots = C(b for s in ss for b in s.active_buckets)
    peak = max(slots.values(), default=0)
    multi = sum(1 for v in slots.values() if v >= 2) * 5 / 60
    # by last activity, so a long-lived session counts in the week it was last used (all such weeks lie in the window)
    weeks = C(s.ended.astimezone().strftime("%G-W%V") for s in ss if s.ended)
    return {"present": True, "window_days": run.window, "sessions": len(rows), "by_surface": by_surface,
            "active_hours_total": round(sum(r["active_min"] for r in rows) / 60, 1),
            "by_origin": {o: {"sessions": len(x), "active_hours": round(sum(r["active_min"] for r in x) / 60, 1)}
                          for o in evidence.ORIGINS for x in [[r for r in rows if r["origin"] == o]] if x},
            "active_hours_by_project": {k: round(v, 1) for k, v in proj.most_common(25)},
            "projects": len(proj), "sessions_per_week_by_last_activity": dict(sorted(weeks.items())),
            "sessions_started_before_window": sum(1 for s in ss if s.records_before_window),
            "hour_of_day": dict(sorted(C(r["hour"] for r in rows).items())), "weekday": dict(C(r["weekday"] for r in rows)),
            "concurrency": {"peak_parallel_sessions_5min": peak, "hours_with_2plus_sessions": round(multi, 1),
                            "hours_with_any_session": round(len(slots) * 5 / 60, 1)},
            "active_time_note": "turn_duration / task_complete are measured; gap_estimate caps idle gaps at 5 min",
            "per_session": rows}


def col_tools(run: Run) -> dict:
    ss = run.sessions(1)
    if not ss:
        return {"present": False, "reason": "no sessions in window"}
    mcp = collections.defaultdict(lambda: {"calls": 0, "errors": C(), "targets": set(), "sessions": set(), "dur": []})
    builtin = collections.defaultdict(lambda: {"calls": 0, "errors": C(), "sessions": set(), "dur": []})
    waits = collections.defaultdict(lambda: {"calls": 0, "minutes": 0.0, "sessions": set()})
    per_session = collections.defaultdict(lambda: {"calls": 0, "errors": 0, "wait_min_over_60s": 0.0})
    for s in ss:
        for c in evidence.tool_calls(s):
            if c.server:
                r = mcp[(c.server, c.op, c.kind)]
                if c.target_hash:
                    r["targets"].add(c.target_hash)
            else:
                r = builtin[(s.surface, c.name)]
            r["calls"] += 1
            r["sessions"].add(s.id)
            if c.error_class:
                r["errors"][c.error_class] += 1
            if c.duration_ms is not None and c.duration_ms >= 0:
                r["dur"].append(c.duration_ms)
                if c.duration_ms >= 60000:
                    w = waits[c.server or c.name]
                    w["calls"] += 1
                    w["minutes"] += c.duration_ms / 60000
                    w["sessions"].add(s.id)
                    per_session[s.id]["wait_min_over_60s"] += c.duration_ms / 60000
            per_session[s.id]["calls"] += 1
            per_session[s.id]["errors"] += bool(c.error_class)

    def row(r):
        d = sorted(r["dur"])
        return {"calls": r["calls"], "sessions": len(r["sessions"]), "errors": dict(r["errors"]),
                "error_rate": round(sum(r["errors"].values()) / r["calls"], 3) if r["calls"] else 0,
                "duration_s": {"median": round(statistics.median(d) / 1000, 1), "p90": round(d[int(len(d) * .9)] / 1000, 1),
                               "total_min": round(sum(d) / 60000, 1)} if d else None}

    connectors = sorted(({"server": k[0], "op": k[1], "kind": k[2], **row(v), "distinct_targets": len(v["targets"])}
                         for k, v in mcp.items()), key=lambda r: -r["calls"])
    servers = C()
    for r in connectors:
        servers[r["server"]] += r["calls"]
    return {"present": True, "sessions": len(ss),
            "connectors": {"servers_used": dict(servers), "write_ops_used": sorted({f"{r['server']}:{r['op']}" for r in connectors if r["kind"] == "write"}),
                           "rows": connectors},
            "builtin_tools": sorted(({"surface": k[0], "tool": k[1], **row(v)} for k, v in builtin.items()), key=lambda r: -r["calls"])[:40],
            "measured_waits_over_60s": sorted(({"tool": k, "calls": v["calls"], "minutes": round(v["minutes"], 1), "sessions": len(v["sessions"])}
                                              for k, v in waits.items()), key=lambda r: -r["minutes"]),
            "duration_note": "tool-call durations include any time the call waited for the participant to approve it",
            "per_session": {k: {**v, "wait_min_over_60s": round(v["wait_min_over_60s"], 1)} for k, v in per_session.items()}}


def _du(p: Path) -> int | None:
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
    except Exception:
        return None


def col_environment(run: Run) -> dict:
    h = run.home
    lib = h / "Library" / "Application Support"
    roam = Path(os.environ.get("APPDATA") or h / "AppData" / "Roaming")
    cands = {"codex": h / ".codex", "cursor": h / ".cursor", "gemini_cli": h / ".gemini", "continue": h / ".continue",
             "windsurf": h / ".codeium", "copilot": h / ".config" / "github-copilot", "opencode": h / ".config" / "opencode",
             "ollama": h / ".ollama", "lmstudio": h / ".lmstudio", "aider": h / ".aider.conf.yml", "shared_agent_skills": h / ".agents",
             "claude_desktop_app": lib / "Claude", "claude_desktop_app_win": roam / "Claude", "chatgpt_app": lib / "com.openai.chat",
             "cursor_app": lib / "Cursor", "codex_app": lib / "Codex"}
    tools = {k: {"present": True} for k, p in cands.items() if p.exists()}
    apps = []
    for root in (Path("/Applications"), h / "Applications", Path(os.environ.get("ProgramFiles", "C:/Program Files")),
                 Path(os.environ.get("LOCALAPPDATA", h / "AppData" / "Local")) / "Programs"):
        if root.is_dir():
            try:
                apps += [a.name for a in root.iterdir() if re.search(r"claude|chatgpt|cursor|codex|windsurf|perplexity|copilot|gemini|ollama|lm ?studio|granola|superwhisper|wispr|raycast", a.name, re.I)]
            except OSError:
                pass
    dl = h / "Downloads"
    exports = 0
    if dl.is_dir():
        try:
            exports = sum(1 for p in dl.iterdir() if re.search(r"conversations.*\.json|claude.*export|chatgpt|data-.*-batch", p.name, re.I))
        except OSError:
            pass
    cx = h / ".codex"
    codex = None
    if cx.is_dir():
        ag = cx / "AGENTS.md"
        codex = {"config_toml": (cx / "config.toml").exists(),
                 "agents_md_lines": ag.read_text(encoding="utf-8", errors="ignore").count("\n") if ag.exists() else None,
                 "agents_md_bytes": ag.stat().st_size if ag.exists() else None,
                 "skills": len(list(cx.glob("skills/*/SKILL.md"))),
                 "history_lines": sum(1 for _ in open(cx / "history.jsonl", encoding="utf-8", errors="ignore")) if (cx / "history.jsonl").exists() else None}
    cw = evidence.cowork_roots(h)
    cowork = None
    if cw:
        metas = [m for r in cw for m in r.glob("**/local_*.json")]
        cowork = {"sessions_total": len(metas),
                  "sessions_in_window": sum(1 for m in metas if m.stat().st_mtime >= run.now.timestamp() - run.window * 86400),
                  "cowork_plugins": len(list(cw[0].glob("**/cowork_plugins/*"))) if cw else 0}
    return {"present": True, "os": platform.system(), "other_ai_tools": sorted(tools), "ai_apps": sorted(set(apps)),
            "chat_export_files_in_downloads": exports, "codex": codex, "cowork": cowork,
            # configuration switches only; runtime internals and anything credential-shaped are left out
            "env_var_names": sorted(k for k in os.environ if k.startswith(("CLAUDE", "ANTHROPIC", "OPENAI", "CODEX", "MCP_", "GEMINI", "DISABLE_", "MAX_THINKING"))
                                    and not re.search(r"TOKEN|SECRET|KEY|PASS|SOCKET|SESSION|_PID|EXECPATH|ENTRYPOINT|^CLAUDECODE$|CHILD|BRIDGE|ATTENDED", k)),
            "claude_version": _which_version("claude")}


COLLECTORS = {"config": col_config, "memory": col_memory, "activity": col_activity, "tools": col_tools, "environment": col_environment}


def cmd_collect(run: Run, a) -> dict:
    only = (a.get("--only") or ",".join(COLLECTORS)).split(",")
    bad = [n for n in only if n not in COLLECTORS]
    if bad:
        raise SystemExit(f"unknown collector(s): {bad}; choose from {sorted(COLLECTORS)}")
    summary = {}
    for name in only:
        t0 = time.time()
        try:
            data = COLLECTORS[name](run)
        except Exception as e:  # a broken collector must not end the run; the gap is recorded instead
            data = {"present": False, "reason": f"collector error: {type(e).__name__}"}
        run.write_collector(name, data)
        summary[name] = {"present": data.get("present", True), "seconds": round(time.time() - t0, 1)}
    return summary


# ---------------------------------------------------------------- assemble

README = """AI Work Discovery — results to send
===================================

This "send" folder holds the results of your discovery run. Every file is plain
text (Markdown or JSON). Nothing in it is executable.

To send it: attach every file in this folder to an email to
hello@matthiasfrank-consulting.com. Zipping this folder first is fine too.

  report.md         what you saw at the end of the run
  manifest.json     what was read, over which period, and what was left out
  intake.json       your self-description, as drafted and as you corrected it
  elements.jsonl    the individual observations behind the report
  sections.md       the narrative for each area
  collectors.json   counts and structure from your setup (no conversation text)
  aggregate.json    the codes and counts from the session map (no conversation text)

The hidden .local folder next to this one stays on your machine. It holds the
list of names that were hidden and some working files. Don't send it; you can
delete it after sending.
"""


def cmd_self_assess(run: Run, a) -> dict:
    """Ask the participant's own AI, in a fresh session started from the home folder, how well it can work here.

    Starting from home (not this project) keeps the run's own context out of the answer
    (2026-10-14 · neutral-dir-self-assessment).
    """
    exe = shutil.which("claude")
    out = run.local / "sections" / "self_assessment.raw.md"
    if not exe:
        return {"ran": False, "reason": "claude CLI not on PATH"}
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", _which_version("claude") or "")
    if m and tuple(map(int, m.groups())) < MIN_CLAUDE:
        return {"ran": False, "reason": f"claude CLI {m.group(0)} is older than {'.'.join(map(str, MIN_CLAUDE))}"}
    prompt = (Path(__file__).resolve().parent.parent / "skills" / "discovery-run" / "self-assessment.md").read_text(encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_") and k != "CLAUDECODE"}
    try:
        # the prompt goes on stdin: a long argument is fragile on Windows and visible in process lists
        r = subprocess.run([exe, "-p", "--model", a.get("--model") or "opus"], input=prompt, cwd=str(run.home), env=env,
                           capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "timed out after 15 minutes"}
    if r.returncode or not r.stdout.strip():
        first = next((x.strip() for x in (r.stderr or "").splitlines() if x.strip()), "")
        first = run.aliases().mask(evidence.mask_secrets(first))[:200]
        return {"ran": False, "reason": f"exit {r.returncode}" + (f": {first}" if first else "")}
    out.write_text(run.aliases().mask(evidence.mask_secrets(r.stdout)), encoding="utf-8")
    return {"ran": True, "file": str(out), "chars": len(r.stdout)}


def cmd_show(run: Run, a) -> dict:
    """Let analysers read part of a large collector file without ad-hoc code (and without permission prompts)."""
    name = a.get("--collector") or ""
    if name not in set(COLLECTORS) | {"probe"}:
        return {"error": f"unknown collector {name!r}", "available": sorted(set(COLLECTORS) | {"probe"})}
    data = _load(run.local / "collectors" / f"{name}.json")
    if data is None:
        return {"error": f"no collector {name!r}", "available": sorted(p.stem for p in (run.local / "collectors").glob("*.json"))}
    keys = [k for k in (a.get("--keys") or "").split(",") if k]
    if not keys:
        return {"collector": name, "keys": {k: len(json.dumps(v, default=str)) for k, v in data.items()},
                "hint": "sizes in characters; pass --keys a,b.c to read parts"}
    out = {}
    for k in keys:
        v = data
        for part in k.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        out[k] = v
    text = json.dumps(out, ensure_ascii=False, default=str)
    limit = int(a.get("--max") or 20000)
    return out if len(text) <= limit else {"truncated_to": limit, "text": text[:limit]}


def cmd_elements(run: Run) -> dict:
    import validate
    schema = validate.load_schema("evidence-element")
    out, ids = {}, C()
    for p in sorted((run.local / "elements").glob("*.jsonl")):
        errs, n = [], 0
        if p.stem not in AREAS_ELEMENTS:
            out[p.stem] = {"elements": 0, "errors": [f"{p.name}: not an element area, so it would never ship ({', '.join(AREAS_ELEMENTS)})"]}
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            n += 1
            try:
                obj = json.loads(line)
            except ValueError:
                errs.append(f"line {i}: invalid JSON")
                continue
            ids[obj.get("id")] += 1
            errs += [f"line {i}: {e}" for e in validate.validate(obj, schema)]
        out[p.stem] = {"elements": n, "errors": errs[:20]}
    dup = [k for k, v in ids.items() if v > 1]
    if dup:
        out["duplicate_ids"] = dup[:20]
    out["clean"] = not dup and all(not v["errors"] for k, v in out.items() if isinstance(v, dict))
    return out


def _manifest(run: Run, cols: dict, n_elements: int) -> dict:
    notes = _load(run.local / "run-notes.json") or {}
    cfg = _load(run.local / "run.json") or {}
    mp = run.local / "map"
    q = _load(mp / "queue.json") or []
    agg = _load(mp / "aggregate.json") or {}
    plan = _load(mp / "plan.json") or {}
    # names are masked as collectors and elements are written, so the final sanitize pass rarely
    # finds any left; the alias table is the real count of what was hidden
    t = run.aliases()
    privacy = {**(notes.get("privacy_pass") or {}), "hidden_project_folders": len(_hidden_folders(t)), "hidden_names": len(t.names)}
    probe = cols.get("probe") or {}
    sources = {}
    for name, data in cols.items():
        if isinstance(data, dict):
            sources[name] = {"present": data.get("present", True), **({"reason": data["reason"]} if data.get("reason") else {})}
    if not probe:   # chat path: no collector saw the machine, so the chat skill's run-notes say what was read
        probe = {"os": notes.get("os"), "sessions_in_window": notes.get("sessions_in_window")}
        sources = notes.get("sources") or sources
    now = dt.datetime.now(dt.timezone.utc)
    created = evidence._ts(cfg.get("created"))
    return {
        "run_id": run.id, "skill_version": cfg.get("skill_version"), "codebook_version": CODEBOOK_VERSION,
        "created": cfg.get("created"), "assembled": now.isoformat(),
        "path": notes.get("path", "local"), "chat_route": notes.get("chat_route"), "capabilities": notes.get("capabilities"),
        "primary_surface": notes.get("primary_surface"),
        "other_surfaces_reported": notes.get("other_surfaces_reported"), "coordinator_model": notes.get("coordinator_model"),
        "usage_left_at_start": notes.get("usage_left_at_start"), "run_size": notes.get("run_size", "full"),
        "os": probe.get("os"), "window_days": run.window, "oldest_session_in_window": probe.get("oldest_in_window"),
        "transcript_span_days": probe.get("transcript_span_days"), "window_coverage_days": probe.get("window_coverage_days"),
        "sessions_in_window": probe.get("sessions_in_window"),
        "session_map": {"eligible": plan.get("eligible"), "mapped": agg.get("sessions_mapped"), "queued": len(q),
                        "by_surface": dict(C(x["surface"] for x in q)), "by_origin": plan.get("by_origin"),
                        "agreement": agg.get("agreement")},
        "sources": sources, "elements": n_elements,
        "self_assessment": notes.get("self_assessment"), "privacy_pass": privacy,
        "exclusions": notes.get("exclusions", []), "participant_active_minutes_estimate": notes.get("participant_active_minutes"),
        # measured, from run creation to this assembly (a model's own guess at it was off in the pilot)
        "wall_minutes": round((now - created).total_seconds() / 60) if created else None,
        "problems_during_run": notes.get("problems", []),
    }


def _put(p: Path, text: str) -> None:
    """Write a bundle file, never through a link that was left in its place."""
    if p.is_symlink():
        p.unlink()
    p.write_text(text, encoding="utf-8")


def cmd_assemble(run: Run) -> dict:
    r = run.send
    if r.is_symlink() or (r.exists() and not r.is_dir()):
        raise SystemExit(f"{r} is not a plain folder (a link or a file); nothing written")
    r.mkdir(exist_ok=True)
    cols = {p.stem: _load(p) for p in sorted((run.local / "collectors").glob("*.json"))}
    if cols:   # the chat path without scripts on the machine has none
        _put(r / "collectors.json", json.dumps(cols, indent=1, ensure_ascii=False))
    agg = run.local / "map" / "aggregate.json"
    if agg.is_file():   # codes and counts only; the records with their gists stay in .local
        _put(r / "aggregate.json", run.aliases().mask_json_text(agg.read_text(encoding="utf-8")))
    # approved section files only, in reading order; working files such as *.raw.md never ship
    secs = [run.local / "sections" / f"{a}.md" for a in AREAS if (run.local / "sections" / f"{a}.md").exists()]
    _put(r / "sections.md", "\n\n".join(p.read_text(encoding="utf-8").strip() for p in secs) + "\n")
    elements = []
    for a in AREAS_ELEMENTS:
        p = run.local / "elements" / f"{a}.jsonl"
        if p.exists():
            elements += list(evidence._records(p))
    _put(r / "elements.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in elements))
    _put(r / "README.txt", README)
    manifest = run.aliases().mask(json.dumps(_manifest(run, cols, len(elements)), indent=1, ensure_ascii=False, default=str))
    _put(r / "manifest.json", manifest)
    return {"collectors": len(cols), "sections": len(secs), "elements": len(elements), "folder": str(r)}


# ---------------------------------------------------------------- cli

class Args:
    def __init__(self, argv):
        self.argv = argv

    def get(self, k):
        if k in self.argv:
            i = self.argv.index(k)
            return self.argv[i + 1] if i + 1 < len(self.argv) and not self.argv[i + 1].startswith("--") else ""
        return None

    def getall(self, k):
        return [self.argv[i + 1] for i, x in enumerate(self.argv) if x == k and i + 1 < len(self.argv)]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, a = argv[0], Args(argv[1:])
    if cmd == "init":
        res = cmd_init(a)
    else:
        if not a.get("--run"):
            raise SystemExit(f"{cmd} needs --run DIR")
        run = Run(Path(os.path.expanduser(a.get("--run"))))
        res = {"probe": lambda: cmd_probe(run), "aliases": lambda: cmd_aliases(run, a), "collect": lambda: cmd_collect(run, a),
               "assemble": lambda: cmd_assemble(run), "elements": lambda: cmd_elements(run), "self-assess": lambda: cmd_self_assess(run, a), "show": lambda: cmd_show(run, a),
               "import-chat": lambda: cmd_import_chat(run, a)}[cmd]()
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
