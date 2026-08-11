from rc_sem import (
    EventHypothesis,
    EventStatus,
    MaterializationConfig,
    RiskControlledMaterializer,
)


def event(
    event_id: str,
    mean: float,
    uncertainty: float,
    *,
    verified: int = 0,
) -> EventHypothesis:
    return EventHypothesis(
        event_id=event_id,
        start_time=0.0,
        end_time=10.0,
        probability_mean=mean,
        probability_uncertainty=uncertainty,
        source_candidate_ids=(f"candidate_{event_id}",),
        authoritative_positive_support=verified,
    )


def test_probable_requires_event_level_lower_bound():
    materializer = RiskControlledMaterializer(
        MaterializationConfig(probable_threshold=0.80, precision_floor=0.80, uncertainty_beta=1.0)
    )
    snapshot = materializer.materialize(
        [event("safe", 0.92, 0.05), event("uncertain", 0.92, 0.20)],
        elapsed_sec=3.0,
    )
    assert [(row.event_id, row.status) for row in snapshot.events] == [
        ("safe", EventStatus.PROBABLE)
    ]
    assert snapshot.probable_precision_lower_bound == 0.87
    assert snapshot.hypothesis_count == 1


def test_authoritative_support_publishes_verified_regardless_of_proxy_probability():
    snapshot = RiskControlledMaterializer().materialize(
        [event("confirmed", 0.10, 0.09, verified=1)],
        elapsed_sec=4.0,
    )
    row = snapshot.events[0]
    assert row.status is EventStatus.VERIFIED
    assert row.probability_lower_bound == 1.0


def test_conflicting_duplicate_event_identity_fails_closed():
    rows = [event("e", 0.9, 0.01), event("e", 0.8, 0.01)]
    try:
        RiskControlledMaterializer().materialize(rows, elapsed_sec=1.0)
    except ValueError as exc:
        assert "conflicting duplicate" in str(exc)
    else:
        raise AssertionError("conflicting duplicate event was accepted")


def test_materialization_is_deterministic_under_input_order():
    rows = [event("b", 0.91, 0.02), event("a", 0.92, 0.03)]
    materializer = RiskControlledMaterializer()
    left = materializer.materialize(rows, elapsed_sec=1.0)
    right = materializer.materialize(reversed(rows), elapsed_sec=1.0)
    assert left == right
