from garc_eval.accelerated_event_query import EventRecord, match_events, summarize_matches


def event(event_id: str, start: float, end: float) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        query_id="Q_DRIVER_RESPONSE_V1",
        video_id="V0",
        start_time=start,
        end_time=end,
        event_score=1.0,
        evidence_status="VERIFIED_EVENT",
        source_candidate_ids=(event_id,),
        verification_history=(),
        k3_group=event_id,
        commit_time=1.0,
    )


def test_one_reference_matches_at_most_one_duplicate_prediction():
    predicted = [event("p0", 0.0, 10.0), event("p1", 2.0, 8.0)]
    reference = [event("r0", 1.0, 9.0)]
    matches = match_events(predicted, reference)
    assert len(matches) == 1
    metrics = summarize_matches(predicted, reference, matches)
    assert metrics["matched_events"] == 1
    assert metrics["32b_operational_oracle_relative_event_precision"] == 0.5
    assert metrics["32b_operational_oracle_relative_event_recall"] == 1.0


def test_nonoverlapping_events_do_not_match():
    assert match_events([event("p0", 0.0, 10.0)], [event("r0", 10.0, 20.0)]) == ()
