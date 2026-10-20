#!/usr/bin/env python3
"""Privacy pass, deterministic layer. Rewrites model-written run files in place: masks secrets
and every name in the run's alias table. The model-based privacy check runs after this.

    python3 -I sanitize.py --run DIR

Covers the bundle's text files (send/, plus any stray ones at the run root) and .local/sections and .local/elements. Prints replacement
counts by label, never the names themselves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402

TEXT = (".md", ".json", ".jsonl", ".txt")


def targets(run: Path) -> list[Path]:
    files = [p for d in (run, run / "send") if d.is_dir() for p in d.iterdir() if p.is_file() and p.suffix in TEXT]
    # model-written files only; .local/map holds working state (queue paths must stay real) and
    # records are already masked at submit
    for sub in ("sections", "elements"):
        d = run / ".local" / sub
        if d.is_dir():
            files += [p for p in d.rglob("*") if p.is_file() and p.suffix in TEXT]
    root = run.resolve()
    # never follow a link out of the run folder (the gate rejects links too, but only afterwards)
    return sorted(f for f in files if not f.is_symlink() and (f.resolve() == root or root in f.resolve().parents))


def sanitize(run: Path) -> dict:
    if not (run / ".local" / "run.json").is_file():
        raise SystemExit(f"{run} is not a discovery run folder (no .local/run.json); nothing changed")
    aliases = evidence.AliasTable.load(run / ".local" / "aliases.json") if (run / ".local" / "aliases.json").exists() else evidence.AliasTable()
    terms = aliases.masked_terms()
    counts: dict[str, int] = {}
    secrets = 0
    changed = 0
    for p in targets(run):
        before = p.read_text(encoding="utf-8", errors="replace")
        for term, label in terms.items():
            n = len(evidence.re.findall(r"(?<![\w])" + evidence.re.escape(term) + r"(?![\w])", before, evidence.re.I))
            if n:
                counts[label] = counts.get(label, 0) + n
        if p.suffix in (".json", ".jsonl"):
            # parse first, so masking never breaks the JSON
            after = aliases.mask_json_text(before, jsonl=p.suffix == ".jsonl")
        else:
            after = aliases.mask(evidence.mask_secrets(before))
        secrets += max(0, after.count("[secret]") - before.count("[secret]"))
        if after != before:
            p.write_text(after, encoding="utf-8")
            changed += 1
    return {"files_checked": len(targets(run)), "files_changed": changed, "secrets_masked": secrets, "replacements_by_label": counts}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--run" not in argv:
        print(__doc__)
        return 2
    print(json.dumps(sanitize(Path(argv[argv.index("--run") + 1]).expanduser()), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
