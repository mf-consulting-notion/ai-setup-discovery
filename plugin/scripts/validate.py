"""Minimal JSON-schema subset validator (standard library only).

Supports: type (string | integer | number | boolean | array | object | null, or a list of these),
required, properties, additionalProperties (false only), enum, items, maxLength, minimum, maximum,
maxItems, maxWords (custom: whitespace-separated words in a string).

    validate(obj, schema) -> list[str]     empty list means valid
    load_schema(name) -> dict              from plugin/schemas/<name>.json
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"
_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict, "null": type(None)}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.json").read_text(encoding="utf-8"))


def _type_ok(v, t) -> bool:
    if isinstance(t, list):
        return any(_type_ok(v, x) for x in t)
    if t in ("integer", "number") and isinstance(v, bool):
        return False
    return isinstance(v, _TYPES[t])


def validate(obj, schema: dict, path: str = "$") -> list[str]:
    errs: list[str] = []
    t = schema.get("type")
    if t and not _type_ok(obj, t):
        return [f"{path}: expected {t}, got {type(obj).__name__}"]
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in {schema['enum']}")
    if isinstance(obj, str):
        if "maxLength" in schema and len(obj) > schema["maxLength"]:
            errs.append(f"{path}: longer than {schema['maxLength']} chars")
        if "maxWords" in schema and len(obj.split()) > schema["maxWords"]:
            errs.append(f"{path}: more than {schema['maxWords']} words")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append(f"{path}: below {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append(f"{path}: above {schema['maximum']}")
    if isinstance(obj, list):
        if "maxItems" in schema and len(obj) > schema["maxItems"]:
            errs.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, x in enumerate(obj):
                errs += validate(x, schema["items"], f"{path}[{i}]")
    if isinstance(obj, dict):
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"{path}: missing {k}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in obj:
                if k not in props:
                    errs.append(f"{path}: unexpected field {k}")
        for k, sub in props.items():
            if k in obj:
                errs += validate(obj[k], sub, f"{path}.{k}")
    return errs
