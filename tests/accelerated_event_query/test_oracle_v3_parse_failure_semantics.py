from garc_eval.accelerated_event_query import unit_label_from_parse
from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response


def test_malformed_output_is_parse_failure_not_unknown_or_negative():
    parsed = parse_oracle_v3_response("not json")
    row = unit_label_from_parse(
        unit_id="u0", query_id="q", video_id="v", start_time=0, end_time=10, result=parsed
    )
    assert row.outcome == "parse_failure"
    assert row.is_indeterminate
    assert not row.is_negative
    assert row.confidence is None and row.evidence is None
