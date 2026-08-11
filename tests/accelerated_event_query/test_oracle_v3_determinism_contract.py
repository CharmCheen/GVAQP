from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response


def test_diagnostic_wording_does_not_change_equal_authoritative_labels():
    left = parse_oracle_v3_response(
        '{"label":"relevant","confidence":"high","evidence":"pedestrian"}'
    )
    right = parse_oracle_v3_response(
        '{"label":"relevant","confidence":"low","evidence":"different explanation"}'
    )
    assert left.authoritative_label == right.authoritative_label == "relevant"
    assert left.parsed != right.parsed
