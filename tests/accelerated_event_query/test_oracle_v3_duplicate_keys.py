from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response


def test_duplicate_key_is_parse_failure():
    raw = '{"label":"relevant","label":"unknown","confidence":"low","evidence":"x"}'
    result = parse_oracle_v3_response(raw)
    assert result.parse_status == "parse_error"
    assert result.effective_label == "parse_failure"
