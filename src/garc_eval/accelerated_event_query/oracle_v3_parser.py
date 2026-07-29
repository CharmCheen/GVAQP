"""Whole-string, duplicate-key-safe parser for the AEQ V3 oracle schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from .oracle_v3_schema import CONFIDENCES, LABELS, RESPONSE_KEYS


ParseStatus = Literal[
    "ok",
    "response_not_string",
    "parse_error",
    "json_not_object",
    "schema_mismatch",
    "invalid_label",
    "invalid_confidence",
    "invalid_evidence",
]
EffectiveLabel = Literal["relevant", "not_relevant", "unknown", "parse_failure"]


@dataclass(frozen=True)
class OracleV3ParseResult:
    parsed: dict[str, Any]
    parse_status: ParseStatus
    effective_label: EffectiveLabel

    @property
    def authoritative_label(self) -> str | None:
        return self.parsed["label"] if self.parse_status == "ok" else None


class DuplicateKeyError(ValueError):
    """Raised when any JSON object contains the same key more than once."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def loads_unique(raw: str) -> Any:
    return json.loads(raw, object_pairs_hook=_unique_object)


def parse_oracle_v3_response(raw: str) -> OracleV3ParseResult:
    """Parse one complete object without ever coercing invalid output to a label."""
    if not isinstance(raw, str):
        return OracleV3ParseResult({}, "response_not_string", "parse_failure")
    try:
        parsed = loads_unique(raw.strip())
    except Exception:
        return OracleV3ParseResult({}, "parse_error", "parse_failure")
    if not isinstance(parsed, dict):
        return OracleV3ParseResult({}, "json_not_object", "parse_failure")
    if set(parsed) != RESPONSE_KEYS:
        return OracleV3ParseResult(parsed, "schema_mismatch", "parse_failure")
    label = parsed["label"]
    if not isinstance(label, str) or label not in LABELS:
        return OracleV3ParseResult(parsed, "invalid_label", "parse_failure")
    confidence = parsed["confidence"]
    if not isinstance(confidence, str) or confidence not in CONFIDENCES:
        return OracleV3ParseResult(parsed, "invalid_confidence", "parse_failure")
    evidence = parsed["evidence"]
    if not isinstance(evidence, str) or not evidence.strip():
        return OracleV3ParseResult(parsed, "invalid_evidence", "parse_failure")
    return OracleV3ParseResult(parsed, "ok", label)
