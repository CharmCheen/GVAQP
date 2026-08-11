import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_accelerated_event_query_oracle_preflight_v1.py"
SPEC = importlib.util.spec_from_file_location("aeq_preflight_runner", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def raw(**overrides) -> str:
    value = {
        "label": "relevant",
        "event_start_sec": 1.0,
        "event_end_sec": 2.0,
        "required_response": ["brake"],
        "cause": "lead vehicle stops",
        "confidence": "high",
        "evidence": "visible closing distance",
        "unknown_reason": None,
    }
    value.update(overrides)
    return json.dumps(value)


def test_valid_operational_oracle_response_parses():
    parsed, status = MODULE.parse_response(raw())
    assert status == "ok"
    assert parsed["label"] == "relevant"


def test_unknown_is_retained_as_unknown():
    parsed, status = MODULE.parse_response(raw(
        label="unknown", event_start_sec=None, event_end_sec=None,
        required_response=[], unknown_reason="boundary",
    ))
    assert status == "ok"
    assert parsed["label"] == "unknown"


def test_malformed_or_out_of_range_response_is_not_negative():
    _, status = MODULE.parse_response(raw(event_end_sec=11.0))
    assert status == "invalid_relevant_boundary"
    _, status = MODULE.parse_response("not json")
    assert status == "no_json_object"
