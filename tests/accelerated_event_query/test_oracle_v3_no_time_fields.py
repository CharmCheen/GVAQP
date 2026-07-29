import json

import pytest

from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response
from garc_eval.accelerated_event_query.oracle_v3_schema import JSON_SCHEMA


@pytest.mark.parametrize("time_key", ["event_start_sec", "event_end_sec", "start_time", "onset"])
def test_any_authoritative_time_field_is_rejected_as_extra(time_key):
    value = {"label": "relevant", "confidence": "high", "evidence": "x", time_key: 17.0}
    result = parse_oracle_v3_response(json.dumps(value))
    assert result.parse_status == "schema_mismatch"
    assert result.effective_label == "parse_failure"


def test_schema_contains_no_time_property():
    assert set(JSON_SCHEMA["properties"]) == {"label", "confidence", "evidence"}
