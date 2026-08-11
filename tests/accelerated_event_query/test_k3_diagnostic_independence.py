from garc_eval.accelerated_event_query import K3UnitEventAdapter

from .v3_helpers import unit


def test_diagnostic_evidence_and_natural_language_times_do_not_change_relation():
    left = [unit(0, "relevant", confidence="high", evidence="event at 17 to 20 seconds")]
    right = [unit(0, "relevant", confidence="low", evidence="no temporal claim")]
    adapter = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1")
    a, b = adapter.materialize(left), adapter.materialize(right)
    assert a == b
    assert a.events[0].start_time == 0.0
    assert a.events[0].end_time == 10.0
