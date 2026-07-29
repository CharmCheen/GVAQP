"""Frozen minimal output contract for the model-relative AEQ oracle V3."""

from __future__ import annotations

from typing import Final


SCHEMA_VERSION: Final = "AEQ_MODEL_RELATIVE_ORACLE_V3_SCHEMA_1"
RESPONSE_KEYS: Final = frozenset({"label", "confidence", "evidence"})
LABELS: Final = frozenset({"relevant", "not_relevant", "unknown"})
CONFIDENCES: Final = frozenset({"high", "medium", "low"})
FORBIDDEN_AUTHORITATIVE_TIME_KEYS: Final = frozenset({
    "event_start_sec",
    "event_end_sec",
    "start_time",
    "end_time",
    "onset",
    "offset",
})


# This value is also materialized as a hash-bound JSON artifact before execution.
# It is intentionally small: only ``label`` is authoritative; confidence and
# evidence are required diagnostics. Because they are required by this frozen
# schema, malformed diagnostics invalidate the object rather than changing a
# successfully parsed label.
JSON_SCHEMA: Final = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:gvaqp:aeq:model-relative-oracle-v3:output",
    "title": "AEQ Model-Relative Oracle V3 Output",
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "confidence", "evidence"],
    "properties": {
        "label": {"type": "string", "enum": sorted(LABELS)},
        "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
        "evidence": {"type": "string", "minLength": 1, "pattern": "\\S"},
    },
}


def authoritative_fields() -> tuple[str, ...]:
    return ("label",)


def diagnostic_fields() -> tuple[str, ...]:
    return ("confidence", "evidence")
