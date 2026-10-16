#!/usr/bin/env python3
"""PreToolUse hook: pre-approve only the discovery run's own, read-only work, so the participant
isn't asked hundreds of times (the briefing's acceptance is the approval).

Allows exactly:
  - Bash: `<python> -I <this plugin>/scripts/<discover|map_loop|sanitize|check_bundle>.py <args>` with no
    shell operators, plus map_loop's `submit ... <<'JSON'` quoted heredoc (its body is never expanded)
  - Read / Glob / Grep under ~/.claude, ~/.codex, the Cowork folder, this plugin, and run folders
  - Write / Edit only inside a run folder (~/ai-work-discovery-*)
Everything else gets no opinion (normal permission handling applies). Never denies.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
HOME = Path.home().resolve()
SCRIPTS = ("discover", "map_loop", "sanitize", "check_bundle")
PY = r"(?:python3|python|py -3|/usr/bin/python3)"   # bare names resolve via PATH; no arbitrary executables
AGENT = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
OPS = re.compile(r"[;&|`$<>(){}\n\r]")


def _real(p: str) -> Path | None:
    try:
        return Path(os.path.expanduser(p.strip("\"'"))).resolve()
    except (OSError, ValueError):
        return None


def _under(p: Path | None, roots) -> bool:
    return bool(p) and any(p == r or r in p.parents for r in roots)


def run_folder(p: Path | None) -> bool:
    if not p:
        return False
    try:
        rel = p.relative_to(HOME)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0].startswith("ai-work-discovery-")


def read_roots():
    roots = [HOME / ".claude", HOME / ".codex", PLUGIN, HOME / "Library" / "Application Support" / "Claude"]
    if os.environ.get("APPDATA"):
        roots.append(Path(os.environ["APPDATA"]) / "Claude")
    return [r.resolve() for r in roots if r.exists()] + [HOME / ".claude.json"]


def _args_ok(script: str, argv: list) -> bool:
    """Every path the script will write to must be a run folder; agent names are single components."""
    i = 0
    while i < len(argv):
        tok = argv[i]
        val = argv[i + 1] if i + 1 < len(argv) else None
        if tok in ("--run", "--out"):
            if val is None or not run_folder(_real(val)):
                return False
            i += 2
            continue
        if tok == "--parent":
            if val is None or _real(val) != HOME:
                return False
            i += 2
            continue
        if tok == "--agent":
            if val is None or not AGENT.match(val):
                return False
            i += 2
            continue
        if tok in ("--package", "--terms"):
            return False   # developer-only modes
        if script == "check_bundle" and not tok.startswith("-"):
            if not run_folder(_real(tok)):
                return False
        i += 1
    return True


def bash_ok(cmd: str) -> bool:
    cmd = cmd.strip()
    if re.fullmatch(r"(?:python3|python|py -3) --version", cmd):
        return True
    first, sep, rest = cmd.partition("\n")
    hd = re.search(r"\s<<\s*'JSON'\s*$", first)
    if hd:
        # map_loop submit with a quoted heredoc: the body is passed verbatim, never expanded
        lines = rest.split("\n")
        if lines[-1].strip() != "JSON" or any(x.strip() == "JSON" for x in lines[:-1]):
            return False
        first = first[:hd.start()]
        heredoc = True
    elif sep:
        return False
    else:
        heredoc = False
    # no expansion, globbing or operators anywhere on the command line, script path included
    # (`~` alone is allowed: it only ever expands to the home folder)
    if re.search(r"[$`\\;&|<>(){}*?!#\r]", first):
        return False
    try:
        tokens = shlex.split(first)
    except ValueError:
        return False
    m = re.match(rf"^{PY}$", " ".join(tokens[:2]) if tokens[:2] == ["py", "-3"] else tokens[0] if tokens else "")
    if not m:
        return False
    rest_tokens = tokens[2:] if tokens[:2] == ["py", "-3"] else tokens[1:]
    if len(rest_tokens) < 1 or rest_tokens[0] != "-I" or len(rest_tokens) < 2:
        return False
    script = _real(rest_tokens[1])
    if not script or script.parent != HERE or script.stem not in SCRIPTS or script.suffix != ".py":
        return False
    argv = rest_tokens[2:]
    if heredoc and not (script.stem == "map_loop" and argv[:1] == ["submit"]):
        return False
    return _args_ok(script.stem, argv)


def decide(event: dict) -> bool:
    tool, inp = event.get("tool_name"), event.get("tool_input") or {}
    if tool == "Bash":
        return bash_ok(str(inp.get("command", "")))
    if tool in ("Read", "Glob", "Grep"):
        raw = str(inp.get("file_path") or inp.get("path") or "")
        if not raw:
            return False
        real = _real(raw)   # resolved: a link that points outside the allowed roots is not approved
        return _under(real, read_roots()) or run_folder(real)
    if tool in ("Write", "Edit"):
        return run_folder(_real(str(inp.get("file_path", ""))))
    return False


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if decide(event):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                 "permissionDecisionReason": "discovery run: own read-only script or run folder"}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
