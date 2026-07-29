import pytest

from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response


@pytest.mark.parametrize("label", ["positive", "negative", "Relevant", "", 1, None])
def test_nonfrozen_label_is_never_coerced(label):
    raw = f'{{"label":{_json(label)},"confidence":"low","evidence":"x"}}'
    result = parse_oracle_v3_response(raw)
    assert result.parse_status == "invalid_label"
    assert result.effective_label == "parse_failure"


def _json(value):
    import json
    return json.dumps(value)
