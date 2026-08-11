"""Whole-string AEQ oracle parser with recursive duplicate-key rejection."""

from __future__ import annotations

import json

from .oracle_protocol import parse_response_strict as _schema_parse


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def loads_unique(raw: str):
    """Load JSON while rejecting duplicate keys at every object depth."""
    return json.loads(raw, object_pairs_hook=_unique_object)


def parse_response_strict(raw: str) -> tuple[dict, str]:
    if not isinstance(raw, str):
        return {}, "response_not_string"
    try:
        loads_unique(raw.strip())
    except Exception as exc:
        return {}, f"parse_error:{type(exc).__name__}"
    return _schema_parse(raw)
