import json

from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response
from garc_eval.accelerated_event_query.oracle_v3_schema import JSON_SCHEMA


def test_minimal_required_schema_and_authoritative_label():
    raw = json.dumps({"label": "relevant", "confidence": "high", "evidence": "visible rider"})
    result = parse_oracle_v3_response(raw)
    assert result.parse_status == "ok"
    assert result.authoritative_label == "relevant"
    assert JSON_SCHEMA["required"] == ["label", "confidence", "evidence"]
    assert JSON_SCHEMA["additionalProperties"] is False


def test_required_diagnostic_structure_is_strict():
    result = parse_oracle_v3_response('{"label":"relevant","confidence":"high"}')
    assert result.parse_status == "schema_mismatch"
    assert result.effective_label == "parse_failure"


def test_whitespace_only_evidence_and_markdown_fence_fail_strict_parse():
    whitespace = parse_oracle_v3_response(
        '{"label":"relevant","confidence":"high","evidence":"   "}'
    )
    fenced = parse_oracle_v3_response(
        '```json\n{"label":"relevant","confidence":"high","evidence":"x"}\n```'
    )
    assert whitespace.parse_status == "invalid_evidence"
    assert fenced.parse_status == "parse_error"
