#!/usr/bin/env python3
"""The gate before hand-off: is this folder safe to send, and does it hold only plain text?

    python3 -I check_bundle.py DIR                         check a run bundle: DIR is the run folder or its send/
    python3 -I check_bundle.py --package DIR --terms FILE  scan our own package for names listed in FILE

Bundle rules: the run folder holds only send/ and .local/; send/ is a flat folder; only .md .json .jsonl .txt; valid UTF-8, no NUL bytes; no <script,
<html, <iframe, javascript: or shebang; no base64 run over 1 KB; total under 10 MB; no secret
pattern; no term from the alias table; JSON/JSONL must parse; elements must match the schema;
report.md must not contain recommendation language.
Exit 0 when clean, 1 with a list of problems (file and rule, never the matched name).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402
import validate  # noqa: E402

ALLOWED = {".md", ".json", ".jsonl", ".txt"}
MAX_BYTES = 10 * 1024 * 1024
ACTIVE = re.compile(r"<\s*(script|html|iframe|object|embed)\b|javascript:|^#!", re.I | re.M)
BASE64 = re.compile(r"[A-Za-z0-9+/=]{1024,}")
# Diagnostic run: the report shows observations, never advice (decision 3, plan discovery-run-v1).
ADVICE = re.compile(r"\b(we recommend|i recommend|recommendations?|you should|you could|consider (?:adding|using|switching|creating)"
                    r"|next steps?|quick wins?|opportunit(?:y|ies)|action items?|to improve this|try (?:adding|using))\b", re.I)


# Details the participant may not want to forward; they belong in sensitive elements, not report prose.
SENSITIVE = re.compile(r"\b(weekends?|saturdays?|sundays?|late[- ]night|at night|evenings?|after (?:8|9|10|20|21|22)(?::00)?\s*(?:pm)?|1password|keychain|bitwarden|lastpass"
                       r"|password manager|permission mode|bypass permissions|dangerously)\b", re.I)


def check_bundle(path: Path) -> list[str]:
    """path: the run folder or its send/ folder; the bundle checked is always send/."""
    path = Path(path)
    # the run is identified by its marker, and a send/ folder's parent run wins, so neither a nested
    # send/ nor a marker planted inside send/ can redirect the check
    if path.name == "send" and (path.parent / ".local" / "run.json").is_file():
        run = path.parent
    elif (path / ".local" / "run.json").is_file():
        run = path
    else:
        return ["not a run folder (no .local/run.json here or above send/)"]
    root = run / "send"
    problems: list[str] = []
    if root.is_symlink() or not root.is_dir():
        return ["send: missing or a link (run assemble first)"]
    for p in sorted(run.iterdir()):
        if p.name not in ("send", ".local"):
            problems.append(f"{p.name}: outside the send folder (move it into send/ or delete it)")
    aliases = evidence.AliasTable.load(run / ".local" / "aliases.json") if (run / ".local" / "aliases.json").exists() else None
    total = 0
    schema = validate.load_schema("evidence-element")
    for p in sorted(root.iterdir()):
        if p.is_dir():
            problems.append(f"{p.name}: sub-folder not allowed (bundle must be flat)")
            continue
        if p.is_symlink():
            problems.append(f"{p.name}: symlink not allowed")
            continue
        if p.suffix.lower() not in ALLOWED:
            problems.append(f"{p.name}: file type {p.suffix or '(none)'} not allowed")
            continue
        raw = p.read_bytes()
        total += len(raw)
        if b"\x00" in raw:
            problems.append(f"{p.name}: contains NUL bytes")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{p.name}: not valid UTF-8")
            continue
        if ACTIVE.search(text):
            problems.append(f"{p.name}: contains active content (script/html/shebang)")
        if BASE64.search(text):
            problems.append(f"{p.name}: contains an encoded blob over 1 KB")
        decoded = text
        if p.suffix in (".json", ".jsonl"):
            # also look at decoded strings: "M\\u00fcller" must count as Müller
            vals = []
            for chunk in (text.splitlines() if p.suffix == ".jsonl" else [text]):
                try:
                    vals.append(json.dumps(json.loads(chunk), ensure_ascii=False))
                except ValueError:
                    pass
            decoded = text + "\n" + "\n".join(vals)
        if evidence.has_secret(decoded):
            problems.append(f"{p.name}: contains a secret-like string")
        if aliases:
            n = len(aliases.leaks(decoded))
            if n:
                problems.append(f"{p.name}: {n} hidden name(s) still present")
        if p.suffix == ".json":
            try:
                json.loads(text)
            except ValueError:
                problems.append(f"{p.name}: invalid JSON")
        if p.suffix == ".jsonl":
            for i, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    problems.append(f"{p.name}:{i}: invalid JSON line")
                    continue
                if p.name == "elements.jsonl":
                    errs = validate.validate(obj, schema)
                    if errs:
                        problems.append(f"{p.name}:{i}: {errs[0]}")
        if p.name == "report.md":
            m = ADVICE.findall(text)
            if m:
                problems.append(f"report.md: recommendation language ({len(m)}x, e.g. '{m[0]}')")
            sens = SENSITIVE.findall(text)
            if sens:
                problems.append(f"report.md: sharing-sensitive detail ({len(sens)}x, e.g. '{sens[0]}'); keep it in a sensitive element instead")
    if total > MAX_BYTES:
        problems.append(f"bundle is {total // 1024} KB, over the 10 MB limit")
    for required in ("README.txt", "report.md", "manifest.json", "elements.jsonl"):
        if not (root / required).exists():
            problems.append(f"{required}: missing")
    return problems


def check_package(root: Path, terms_file: Path) -> list[str]:
    """Our own package must stay general-purpose: no client, participant or machine-specific names."""
    terms = [t.strip() for t in terms_file.read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    problems = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or ".git" in p.relative_to(root).parts:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for t in terms:
            if re.search(r"(?<![\w])" + re.escape(t) + r"(?![\w])", text, re.I):
                problems.append(f"{p.relative_to(root)}: contains a listed term (#{terms.index(t) + 1})")
        if evidence.has_secret(text):
            problems.append(f"{p.relative_to(root)}: contains a secret-like string")
    return problems


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--package" in argv:
        root = Path(argv[argv.index("--package") + 1]).expanduser()
        problems = check_package(root, Path(argv[argv.index("--terms") + 1]).expanduser())
    elif argv and not argv[0].startswith("-"):
        problems = check_bundle(Path(argv[0]).expanduser())
    else:
        print(__doc__)
        return 2
    print(json.dumps({"clean": not problems, "problems": problems}, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
