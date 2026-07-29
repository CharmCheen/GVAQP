from dataclasses import replace

from garc_eval.accelerated_event_query import (
    CandidateObservation,
    IncrementalK3,
    VerificationRecord,
)


def candidate(candidate_id: str, start: float, end: float, probability: float = 0.9):
    return CandidateObservation(
        candidate_id=candidate_id,
        query_id="Q_DRIVER_RESPONSE_V1",
        video_id="V0",
        start_time=start,
        end_time=end,
        proxy_score=probability,
        calibrated_probability=probability,
    )


def test_scan_materializes_probable_event_and_required_fields():
    k3 = IncrementalK3()
    update = k3.apply("SCAN", [candidate("c0", 0.0, 10.0)], elapsed_sec=1.0, deadline_sec=10.0)
    assert update.accepted
    event = update.events[0]
    assert event.evidence_status == "PROBABLE_EVENT"
    assert event.commit_time == 1.0
    assert set(event.to_dict()) == {
        "event_id", "query_id", "video_id", "start_time", "end_time",
        "event_score", "evidence_status", "source_candidate_ids",
        "verification_history", "k3_group", "commit_time",
    }


def test_verify_promotes_probable_to_verified_event():
    k3 = IncrementalK3()
    raw = candidate("c0", 0.0, 10.0)
    first = k3.apply("SCAN", [raw], elapsed_sec=1.0, deadline_sec=10.0)
    record = VerificationRecord(2.0, "positive", "abc", 0.5)
    verified = replace(raw, evidence_status="VERIFIED_POSITIVE", verification_history=(record,))
    second = k3.apply("VERIFY", [verified], elapsed_sec=2.0, deadline_sec=10.0)
    assert second.events[0].evidence_status == "VERIFIED_EVENT"
    assert second.events[0].commit_time == first.events[0].commit_time
    assert second.promoted_event_ids == (second.events[0].event_id,)


def test_verified_negative_barrier_splits_neighbor_groups():
    k3 = IncrementalK3()
    left = candidate("c0", 0.0, 10.0)
    bridge = replace(candidate("c1", 10.0, 20.0), evidence_status="VERIFIED_NEGATIVE")
    right = candidate("c2", 20.0, 30.0)
    update = k3.apply("VERIFY", [left, bridge, right], elapsed_sec=3.0, deadline_sec=10.0)
    assert len(update.events) == 2
    assert all("c1" not in event.source_candidate_ids for event in update.events)


def test_post_deadline_action_has_no_state_effect_or_commit():
    k3 = IncrementalK3()
    before = k3.apply("SCAN", [candidate("c0", 0.0, 10.0)], elapsed_sec=1.0, deadline_sec=2.0)
    after = k3.apply("SCAN", [candidate("c1", 10.0, 20.0)], elapsed_sec=2.001, deadline_sec=2.0)
    assert not after.accepted
    assert after.attempted_after_deadline
    assert not after.post_deadline_commit
    assert after.events == before.events
    assert "c1" not in dict(after.candidate_to_event)


def test_materialization_is_deterministic_under_input_order():
    rows = [candidate("c1", 10.0, 20.0), candidate("c0", 0.0, 10.0)]
    left, right = IncrementalK3(), IncrementalK3()
    a = left.apply("SCAN", rows, elapsed_sec=1.0, deadline_sec=2.0)
    b = right.apply("SCAN", list(reversed(rows)), elapsed_sec=1.0, deadline_sec=2.0)
    assert a.events == b.events
    assert a.candidate_to_event == b.candidate_to_event
