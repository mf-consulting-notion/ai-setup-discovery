"""Evidence sources for a discovery run: every piece of transcript knowledge lives here.

Reads Claude Code (~/.claude/projects), Cowork on the desktop app (local-agent-mode-sessions,
which stores Claude Code-format transcripts) and Codex (~/.codex/sessions). Standard library
only, read-only, never raises on malformed input.

Interface:
    sessions(home, window_days=30, now=None) -> list[Session]
    skeleton(session, max_chars=60000, aliases=None) -> str        first line: "# session <id> ..."
    tool_calls(session) -> Iterator[ToolCall]
    import_chat_export(export, out_dir) -> int                     claude.ai export -> per-chat transcripts
    AliasTable.build(home, extra_names=()) / .load(path) / .save(path) / .label(project_key) / .mask(text)
    mask_secrets(text) -> str
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

# ---------------------------------------------------------------- secrets

SECRET_PATTERNS = [
    re.compile(p) for p in (
        r"sk-(?:ant-)?[A-Za-z0-9_-]{16,}",          # Anthropic / OpenAI style keys
        r"gh[pousr]_[A-Za-z0-9]{20,}",              # GitHub tokens
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"xox[abprs]-[A-Za-z0-9-]{10,}",             # Slack
        r"(?:ntn|secret)_[A-Za-z0-9]{20,}",          # Notion integration tokens
        r"AKIA[0-9A-Z]{16}",                         # AWS access key id
        r"AIza[0-9A-Za-z_-]{30,}",                   # Google API key
        r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{10,})?",  # JWT
        r"(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)",
        r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}",
        r"://[^/\s:@]+:[^@\s]+@",                     # credentials inside a URL
        r"(?i)['\"]?(?:password|passwd|pwd|api[_-]?key|apikey|secret|client[_-]?secret|token|access[_-]?token|auth[_-]?token)['\"]?\s*[:=]\s*['\"]?[^\s'\",}]{8,}",
    )
]


CREDENTIAL_KEY = re.compile(r"(?i)^(?:password|passwd|pwd|api[_-]?key|apikey|secret|client[_-]?secret|token|access[_-]?token|auth[_-]?token|private[_-]?key)$")


def mask_secrets(text: str) -> str:
    for p in SECRET_PATTERNS:
        text = p.sub("[secret]", text)
    return text


def has_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


# ---------------------------------------------------------------- low-level readers

def _ts(s) -> _dt.datetime | None:
    if not s:
        return None
    try:
        t = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def _records(path: Path, skipped: list | None = None) -> Iterator[dict]:
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except (ValueError, RecursionError):
                if skipped is not None:
                    skipped.append(1)
                continue
            if isinstance(d, dict):
                yield d


def _text_of(content) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text")
                 and isinstance(b.get("text"), str)]
        return "\n".join(parts) if parts else None
    return None


INJECTED = ("<system-reminder", "<local-command", "<command-message", "Caveat:", "<bash-", "<task-notification",
            "<user_instructions", "<environment_context", "# AGENTS.md instructions", "<turn_aborted")
CMD = re.compile(r"<command-name>/?([^<\s]+)</command-name>")
ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)


def _is_human(text: str | None) -> bool:
    return bool(text and text.strip() and not text.lstrip().startswith(INJECTED))


# ---------------------------------------------------------------- sessions

@dataclass
class Session:
    id: str                      # short stable id (8 chars) used in records and skeleton headers
    surface: str                 # claude_code | cowork | codex
    path: Path
    project_key: str             # cwd relative to home ("~/work/acme-site"), or "?" if unknown
    started: _dt.datetime | None = None
    ended: _dt.datetime | None = None
    active_ms: int = 0
    active_source: str = "none"  # turn_duration | task_complete | gap_estimate | none
    prompts: int = 0
    slash_commands: list = field(default_factory=list)
    model: str | None = None
    title: str | None = None
    skipped_lines: int = 0
    active_buckets: set = field(default_factory=set, repr=False)   # 5-minute slots with any activity


    @property
    def wall_min(self) -> int | None:
        if self.started and self.ended:
            return round((self.ended - self.started).total_seconds() / 60)
        return None


GAP_CAP_MS = 5 * 60 * 1000   # gaps longer than this count as the participant being away


def _gap_estimate(times: list) -> int:
    times = sorted(t for t in times if t)
    return int(sum(min((b - a).total_seconds() * 1000, GAP_CAP_MS) for a, b in zip(times, times[1:])))


def _buckets(times: list) -> set:
    return {int(t.timestamp() // 300) for t in times if t}


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _msg(d: dict) -> dict:
    m = d.get("message")
    return m if isinstance(m, dict) else {}


def _rel(home: Path, p: str | None) -> str:
    if not p:
        return "?"
    p = str(p).replace("\\", "/")
    h = str(home).replace("\\", "/").rstrip("/")
    return "~" + p[len(h):] if p.lower().startswith(h.lower()) else p


def _claude_session(path: Path, home: Path, surface: str) -> Session:
    skipped: list = []
    s = Session(id=path.stem[:8], surface=surface, path=path, project_key="?")
    times, turn_ms, cwd = [], 0, None
    for d in _records(path, skipped):
        t = _ts(d.get("timestamp"))
        if t:
            times.append(t)
        cwd = cwd or d.get("cwd")
        typ = d.get("type")
        if typ == "ai-title":
            s.title = d.get("aiTitle") or d.get("title") or s.title
        elif typ == "system" and d.get("subtype") == "turn_duration":
            turn_ms += _int(d.get("durationMs"))
        elif typ == "assistant" and not s.model:
            s.model = _msg(d).get("model")
        elif typ == "user" and not d.get("isSidechain") and not d.get("isMeta"):
            h = _text_of(_msg(d).get("content"))
            if h and CMD.search(h):
                s.prompts += 1
                s.slash_commands.append(CMD.search(h).group(1))
            elif _is_human(h) and "[Request interrupted" not in h:
                s.prompts += 1
    s.skipped_lines = len(skipped)
    s.project_key = _rel(home, cwd)
    s.active_buckets = _buckets(times)
    if times:
        s.started, s.ended = min(times), max(times)
    if turn_ms:
        s.active_ms, s.active_source = turn_ms, "turn_duration"
    elif len(times) > 1:
        s.active_ms, s.active_source = _gap_estimate(times), "gap_estimate"
    return s


def _codex_session(path: Path, home: Path) -> Session | None:
    skipped: list = []
    s = Session(id=path.stem[-8:], surface="codex", path=path, project_key="?")
    times, task_ms, cwd, meta = [], 0, None, {}
    for d in _records(path, skipped):
        t = _ts(d.get("timestamp"))
        if t:
            times.append(t)
        p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        typ = d.get("type")
        if typ == "session_meta":
            meta = p
            cwd = cwd or p.get("cwd")
        elif typ == "turn_context":
            cwd = cwd or p.get("cwd")
            s.model = s.model or p.get("model")
        elif typ == "event_msg" and p.get("type") == "task_complete":
            task_ms += _int(p.get("duration_ms"))
        elif typ == "response_item" and p.get("type") == "message" and p.get("role") == "user":
            if _is_human(_text_of(p.get("content"))):
                s.prompts += 1
    if meta.get("forked_from_id") or meta.get("parent_thread_id"):
        return None   # child threads are part of their root's work
    s.skipped_lines = len(skipped)
    s.project_key = _rel(home, cwd)
    s.active_buckets = _buckets(times)
    if times:
        s.started, s.ended = min(times), max(times)
    if task_ms:
        s.active_ms, s.active_source = task_ms, "task_complete"
    elif len(times) > 1:
        s.active_ms, s.active_source = _gap_estimate(times), "gap_estimate"
    return s


# ---------------------------------------------------------------- claude.ai export

def _export_conversations(export: Path) -> list:
    """conversations.json from a claude.ai data export, given the file itself or the export .zip (read in memory)."""
    import zipfile
    export = Path(export)
    if zipfile.is_zipfile(export):
        with zipfile.ZipFile(export) as z:
            name = next((n for n in z.namelist() if n.split("/")[-1] == "conversations.json"), None)
            if not name:
                return []
            data = json.loads(z.read(name).decode("utf-8", errors="replace"))
    else:
        data = json.loads(export.read_text(encoding="utf-8", errors="replace"))
    return data if isinstance(data, list) else []


def import_chat_export(export: Path, out_dir: Path) -> int:
    """Turn each claude.ai conversation into a Claude Code-shaped transcript in out_dir/<uuid>.jsonl, so
    sessions(), skeleton() and tool_calls() work on chat history unchanged (surface "chat")."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for conv in _export_conversations(export):
        if not isinstance(conv, dict) or not re.fullmatch(r"[0-9A-Fa-f-]{8,64}", str(conv.get("uuid") or "")):
            continue   # also blocks path tricks: the id becomes a file name
        rows = [{"type": "ai-title", "aiTitle": conv.get("name") or ""}]
        for m in conv.get("chat_messages") or []:
            if not isinstance(m, dict):
                continue
            t = m.get("created_at")
            blocks, results = [], []
            for b in m.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text"):
                    blocks.append({"type": "text", "text": b["text"]})
                elif b.get("type") == "tool_use":
                    blocks.append({"type": "tool_use", "id": b.get("id") or f"t{len(blocks)}", "name": b.get("name") or "?",
                                   "input": b.get("input") if isinstance(b.get("input"), dict) else {}})
                elif b.get("type") == "tool_result":
                    results.append({"type": "tool_result", "tool_use_id": b.get("tool_use_id") or "", "is_error": bool(b.get("is_error")),
                                    "content": ""})
            if not blocks and m.get("text"):
                blocks = [{"type": "text", "text": m["text"]}]
            attach = len(m.get("attachments") or []) + len(m.get("files") or [])
            if m.get("sender") == "human":
                text = "\n".join(b["text"] for b in blocks if b.get("type") == "text")
                if attach:
                    text += f"\n[{attach} attachment(s)]"
                rows.append({"type": "user", "timestamp": t, "cwd": "chat", "message": {"role": "user", "content": text}})
            else:
                rows.append({"type": "assistant", "timestamp": t, "message": {"role": "assistant", "content": blocks}})
                if results:
                    rows.append({"type": "user", "timestamp": t, "message": {"role": "user", "content": results}})
        with open(out_dir / f"{conv['uuid']}.jsonl", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        n += 1
    return n


def cowork_roots(home: Path) -> list[Path]:
    """Where the Claude desktop app keeps Cowork sessions on macOS and Windows."""
    cands = [home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"]
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands.append(Path(appdata) / "Claude" / "local-agent-mode-sessions")
    cands.append(home / "AppData" / "Roaming" / "Claude" / "local-agent-mode-sessions")
    out, seen = [], set()
    for c in cands:
        if c.is_dir() and c.resolve() not in seen:
            seen.add(c.resolve())
            out.append(c)
    return out


def transcript_files(home: Path, chat_dir: Path | None = None) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {"claude_code": [], "cowork": [], "codex": [], "chat": []}
    if chat_dir and Path(chat_dir).is_dir():
        out["chat"] = sorted(Path(chat_dir).glob("*.jsonl"))
    proj = home / ".claude" / "projects"
    if proj.is_dir():
        out["claude_code"] = sorted(p for p in proj.glob("*/*.jsonl")
                                    if ".orphaned-" not in p.name and ".superseded-" not in p.name)
    for root in cowork_roots(home):
        out["cowork"] += sorted(root.glob("**/local_*/.claude/projects/*/*.jsonl"))
    cx = home / ".codex" / "sessions"
    if cx.is_dir():
        out["codex"] = sorted(cx.glob("**/*.jsonl"))
    return out


def sessions(home: Path, window_days: int = 30, now: _dt.datetime | None = None,
             min_prompts: int = 1, chat_dir: Path | None = None) -> list[Session]:
    """All root sessions with activity inside the window and at least `min_prompts` prompts.
    chat_dir: transcripts made by import_chat_export (their file times are import times, so not used to skip)."""
    home = Path(home)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    cut = now - _dt.timedelta(days=window_days)
    found: list[Session] = []
    files = transcript_files(home, chat_dir)
    def stale(f: Path) -> bool:
        try:
            return f.stat().st_mtime < cut.timestamp() - 86400
        except OSError:
            return True   # dangling symlink or unreadable: skip

    for surface in ("claude_code", "cowork", "chat"):
        for f in files[surface]:
            if (surface != "chat" and stale(f)) or not f.is_file():
                continue
            found.append(_claude_session(f, home, surface))
    for f in files["codex"]:
        if stale(f):
            continue
        s = _codex_session(f, home)
        if s:
            found.append(s)
    keep = [s for s in found if s.ended and cut <= s.ended <= now + _dt.timedelta(days=1) and s.prompts >= min_prompts]
    return sorted(keep, key=lambda s: s.started)


# ---------------------------------------------------------------- tool calls

@dataclass
class ToolCall:
    session: str
    name: str
    server: str | None        # MCP server name for mcp__<server>__<op>, else None
    op: str
    kind: str                 # read | write | other
    duration_ms: int | None
    error_class: str | None   # None when the call succeeded
    target_hash: str | None


READ_VERBS = set("search fetch get list read query find show download describe explore status navigate screenshot view check "
                 "lookup count retrieve export inspect".split())
WRITE_VERBS = set("create update delete send post move write upload apply add set reply forward trash label duplicate restore "
                  "archive connect trigger publish deploy schedule cancel respond share edit insert remove replace rename "
                  "comment invite submit run execute".split())
ID_KEYS = ("page_id", "database_id", "data_source_id", "id", "url", "parent", "data_source_url", "channel_id",
           "thread_id", "file_id", "file_path", "path")


def op_kind(op: str) -> str:
    """First verb in the operation name decides: notion-create-pages -> write, list_connected_browsers -> read."""
    for seg in re.split(r"[-_.\s]+|(?<=[a-z])(?=[A-Z])", op):
        seg = seg.lower()
        if seg in READ_VERBS:
            return "read"
        if seg in WRITE_VERBS:
            return "write"
    return "other"


def err_class(text: str) -> str:
    t = (text or "").lower()
    for k, pat in (("not_found", r"404|not found|could not find|does not exist|no such file"),
                   ("auth", r"401|403|unauthor|forbidden|permission|not shared|access denied"),
                   ("timeout", r"timeout|timed out"), ("rate_limit", r"429|rate limit|quota"),
                   ("validation", r"invalid|validation|required|schema"),
                   ("rejected", r"user (?:rejected|denied|doesn't want)|was rejected")):
        if re.search(pat, t):
            return k
    return "other"


def _h(v) -> str:
    return hashlib.sha1(str(v).encode()).hexdigest()[:8]


def _split_name(name: str) -> tuple[str | None, str]:
    if name.startswith("mcp__"):
        parts = name.split("__")
        return (parts[1] if len(parts) > 1 else "?"), (parts[2] if len(parts) > 2 else "?")
    return None, name


def tool_calls(session: Session) -> Iterator[ToolCall]:
    pending: dict[str, tuple] = {}
    if session.surface == "codex":
        for d in _records(session.path):
            p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            t = _ts(d.get("timestamp"))
            if p.get("type") in ("function_call", "custom_tool_call"):
                pending[p.get("call_id")] = (p.get("name") or "?", t, None)
            elif p.get("type") in ("function_call_output", "custom_tool_call_output") and p.get("call_id") in pending:
                name, t0, _ = pending.pop(p["call_id"])
                out = str(p.get("output") or "")
                failed = bool(re.search(r'"exit_code":\s*[1-9]|Process exited with code [1-9]|^error', out[:400], re.I))
                server, op = _split_name(name)
                yield ToolCall(session.id, name, server, op, op_kind(op),
                               int((t - t0).total_seconds() * 1000) if t and t0 else None,
                               err_class(out[:400]) if failed else None, None)
        return
    for d in _records(session.path):
        if d.get("isSidechain"):
            continue
        t = _ts(d.get("timestamp"))
        content = _msg(d).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                target = next((inp[k] for k in ID_KEYS if inp.get(k)), None)
                pending[b.get("id")] = (b.get("name") or "?", t, _h(target) if target else None)
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                name, t0, target = pending.pop(b["tool_use_id"])
                c = b.get("content")
                txt = c if isinstance(c, str) else " ".join(x["text"] for x in c if isinstance(x, dict) and isinstance(x.get("text"), str)) if isinstance(c, list) else ""
                server, op = _split_name(name)
                yield ToolCall(session.id, name, server, op, op_kind(op),
                               int((t - t0).total_seconds() * 1000) if t and t0 else None,
                               err_class(txt[:400]) if b.get("is_error") else None, target)


# ---------------------------------------------------------------- aliases

# Folder names that are ordinary words, never worth masking (2026-10-14 · folder-names-make-a-bad-masking-list).
COMMON = set("""
projects project code src dev work workspace repos repo github gitlab git claude codex agents agent skills plugins
clients client leads personal private misc sandbox playground experiments experiment scripts tools tool config
dotfiles blog site web website app apps api docs doc notes test tests tmp temp scratch archive desktop documents
downloads home library main master prototype prototypes demo demos data backup backups old new internal admin
chat cowork local sessions session present reason unknown memory report reports content marketing research
""".split())
# The toolkit's own vocabulary (surfaces, schema values, JSON field words) must never be masked.
COMMON |= {"claude_code", "true", "false", "null", "none", "full", "light", "observed_trace", "config_inspection"}


def _variants(name: str) -> set[str]:
    base = name.strip()
    return {v for v in {base, base.replace("-", " "), base.replace("_", " "), base.replace("-", ""), base.replace("_", "")}
            if len(v) >= 4 and v.lower() not in COMMON}


class AliasTable:
    """Run-local mapping from real names to stable labels. Never leaves the participant's machine.

    projects: project_key -> "project A"; names: real name -> replacement ("a client", "a colleague").
    """

    def __init__(self, projects: dict | None = None, names: dict | None = None, keep: list | None = None):
        self.projects = dict(projects or {})
        self.names = dict(names or {})
        self.keep = set(keep or [])   # folder names the participant said are fine to show (ordinary words)
        self._pat = None

    # construction -----------------------------------------------------
    @classmethod
    def build(cls, project_keys: Iterable[str], extra_names: dict | Iterable[str] = ()) -> "AliasTable":
        t = cls()
        for k in sorted(set(project_keys)):
            t.label(k)
        if isinstance(extra_names, dict):
            for n, r in extra_names.items():
                t.add_name(n, r)
        else:
            for n in extra_names:
                t.add_name(n)
        return t

    @classmethod
    def load(cls, path: Path) -> "AliasTable":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d.get("projects"), d.get("names"), d.get("keep"))

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"projects": self.projects, "names": self.names, "keep": sorted(self.keep)}, indent=1, ensure_ascii=False),
                              encoding="utf-8")

    # use ---------------------------------------------------------------
    def label(self, project_key: str) -> str:
        if project_key in ("?", "~", "", None, "chat"):
            return {"~": "home", "chat": "chat"}.get(project_key, "unknown")
        if project_key not in self.projects:
            n = len(self.projects)
            self.projects[project_key] = "project " + (chr(65 + n) if n < 26 else f"{chr(65 + n // 26 - 1)}{chr(65 + n % 26)}")
            self._pat = None
        return self.projects[project_key]

    def keep_folder(self, name: str) -> None:
        self.keep.add(name.strip())
        self._pat = None

    def add_name(self, name: str, replacement: str = "a third party") -> None:
        if name and name.strip():
            self.names[name.strip()] = replacement
            self._pat = None

    def masked_terms(self) -> dict[str, str]:
        """Every string that must not survive into the bundle, mapped to its replacement. Folder-derived
        variants need 4+ characters and skip ordinary words; names the participant gave are always kept."""
        terms: dict[str, str] = {}
        nfc = lambda x: unicodedata.normalize("NFC", x)  # noqa: E731
        for key, label in self.projects.items():
            key = nfc(key)
            base = key.replace("\\", "/").rstrip("/").split("/")[-1]
            if base.lower() in {k.lower() for k in self.keep}:
                continue
            for v in _variants(base):
                terms.setdefault(v, label)
        for name, rep in ((nfc(n), r) for n, r in self.names.items()):
            for v in _variants(name) | {name}:
                if v.strip():
                    terms[v] = rep
        return terms

    def _patterns(self):
        """Short terms (under 4 chars) match case-sensitively, so "Li" doesn't hit "li" inside ordinary text."""
        if self._pat is None:
            terms = self.masked_terms()
            long_t = sorted((t for t in terms if len(t) >= 4), key=len, reverse=True)
            short_t = sorted((t for t in terms if len(t) < 4), key=len, reverse=True)
            mk = lambda ts, fl: re.compile(r"(?<![\w])(" + "|".join(map(re.escape, ts)) + r")(?![\w])", fl) if ts else None  # noqa: E731
            self._pat = (mk(long_t, re.I), mk(short_t, 0), {k.lower(): v for k, v in terms.items()}, terms)
        return self._pat

    def mask(self, text: str) -> str:
        text = unicodedata.normalize("NFC", text)
        long_p, short_p, low, terms = self._patterns()
        if long_p:
            text = long_p.sub(lambda m: low.get(m.group(1).lower(), "a third party"), text)
        if short_p:
            text = short_p.sub(lambda m: terms.get(m.group(1), "a third party"), text)
        return text

    def mask_json_text(self, text: str, jsonl: bool = False) -> str:
        """Mask JSON / JSONL on decoded values, so \\u-escaped names can't slip past and the result stays
        valid JSON. Values under credential-like keys become "[secret]"."""
        def walk(o, key=None):
            if key is not None and isinstance(key, str) and CREDENTIAL_KEY.search(key) and isinstance(o, (str, int, float)) and str(o):
                return "[secret]"
            if isinstance(o, str):
                return self.mask(mask_secrets(o))
            if isinstance(o, list):
                return [walk(x) for x in o]
            if isinstance(o, dict):
                return {walk(k): walk(v, k) for k, v in o.items()}
            return o
        if jsonl:
            out = []
            for line in text.splitlines():
                try:
                    out.append(json.dumps(walk(json.loads(line)), ensure_ascii=False) if line.strip() else line)
                except (ValueError, RecursionError):
                    out.append(self.mask(mask_secrets(line)))
            return "\n".join(out) + ("\n" if text.endswith("\n") else "")
        try:
            return json.dumps(walk(json.loads(text)), indent=1, ensure_ascii=False)
        except (ValueError, RecursionError):
            return self.mask(mask_secrets(text))

    def leaks(self, text: str) -> list[str]:
        """Masked terms still present in text (whole word; case-insensitive from 4 characters)."""
        text = unicodedata.normalize("NFC", text)
        long_p, short_p, low, terms = self._patterns()
        hits = set()
        for p in (long_p, short_p):
            if p:
                hits |= {m.group(1).lower() if p is long_p else m.group(1) for m in p.finditer(text)}
        return sorted(hits)


# ---------------------------------------------------------------- skeleton

def _clip(s: str, n: int, aliases: AliasTable | None) -> str:
    s = mask_secrets(" ".join(str(s).split()))
    if aliases:
        s = aliases.mask(s)
    return s if len(s) <= n else s[:n] + "…"


def _tool_target(inp, aliases) -> str:
    if not isinstance(inp, dict):
        return ""
    for k in ("skill", "subagent_type", "file_path", "path", "pattern", "url", "query", "description", "command"):
        if inp.get(k):
            v = str(inp[k])
            if k in ("file_path", "path"):
                v = v.replace("\\", "/").split("/")[-1]
            return f"{k}={_clip(v, 70, aliases)}"
    return ""


def _collapse(lines: list[str]) -> list[str]:
    out, run = [], []

    def flush():
        out.extend(run if len(run) <= 6 else run[:3] + [f"  … {len(run) - 5} more tool calls …"] + run[-2:])
        run.clear()

    for line in lines:
        if line.startswith("  tool "):
            run.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return out


def skeleton(session: Session, max_chars: int = 60000, aliases: AliasTable | None = None) -> str:
    """Readable reduction of one session for the session map. Secrets and aliased names are masked.

    Keeps human prompts (600 chars), AI text (220 chars), tool calls as name + short target and
    tool errors. Drops tool output, thinking, attachments and injected system text.
    """
    proj = aliases.label(session.project_key) if aliases else session.project_key
    head = (f"# session {session.id} · {session.surface} · project {proj} · "
            f"{session.started.date() if session.started else '?'} · {session.wall_min} min wall · "
            f"{round(session.active_ms / 60000, 1)} min active · prompts {session.prompts}")
    lines: list[str] = []
    t0 = session.started

    def at(d) -> str:
        t = _ts(d.get("timestamp"))
        return f"[+{int((t - t0).total_seconds() // 60)}m] " if t and t0 else ""

    if session.surface == "codex":
        for d in _records(session.path):
            p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            if d.get("type") != "response_item":
                continue
            t = p.get("type")
            if t == "message" and p.get("role") in ("user", "assistant"):
                txt = _text_of(p.get("content"))
                if not _is_human(txt):
                    continue
                if p["role"] == "user":
                    lines.append(at(d) + "USER " + _clip(txt, 600, aliases))
                else:
                    lines.append("  " + at(d) + "AI " + _clip(txt, 220, aliases))
            elif t in ("custom_tool_call", "function_call"):
                arg = str(p.get("input") or p.get("arguments") or "")
                m = re.search(r'(?:cmd|command)\\?"\s*:\s*\\?"([^"\\]{0,80})', arg)
                lines.append(f"  tool {p.get('name')} {_clip(m.group(1), 70, aliases) if m else ''}".rstrip())
    else:
        for d in _records(session.path):
            if d.get("isSidechain"):
                continue
            typ, msg = d.get("type"), _msg(d)
            content = msg.get("content") if isinstance(msg, dict) else None
            if typ == "user" and not d.get("isMeta"):
                h = _text_of(content)
                if h:
                    m = CMD.search(h)
                    if m:
                        a = ARGS.search(h)
                        lines.append(at(d) + f"USER /{m.group(1)} {_clip(a.group(1), 300, aliases) if a else ''}".rstrip())
                    elif "[Request interrupted" in h:
                        lines.append(at(d) + "USER [interrupted]")
                    elif _is_human(h):
                        lines.append(at(d) + "USER " + _clip(h, 600, aliases))
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                            lines.append("  tool-error")
            elif typ == "assistant" and isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and isinstance(b.get("text"), str) and b["text"].strip():
                        lines.append("  " + at(d) + "AI " + _clip(b["text"], 220, aliases))
                    elif b.get("type") == "tool_use":
                        lines.append(f"  tool {b.get('name')} {_tool_target(b.get('input'), aliases)}".rstrip())
    body = "\n".join([head] + _collapse(lines))
    return body if len(body) <= max_chars else body[:max_chars] + "\n… [truncated]"
