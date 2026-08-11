from garc_eval.accelerated_event_query import K3UnitEventAdapter

from .v3_helpers import unit


def test_post_deadline_k3_update_cannot_enter_durable_relation():
    adapter = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1")
    before = adapter.apply("VERIFY", [unit(0, "relevant")], elapsed_sec=1.0, deadline_sec=2.0)
    after = adapter.apply("VERIFY", [unit(1, "relevant")], elapsed_sec=2.001, deadline_sec=2.0)
    assert before.accepted
    assert not after.accepted
    assert after.attempted_after_deadline
    assert not after.post_deadline_commit
    assert after.relation == before.relation == adapter.relation
