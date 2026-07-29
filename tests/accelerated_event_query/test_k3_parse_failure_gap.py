from garc_eval.accelerated_event_query import K3UnitEventAdapter

from .v3_helpers import unit


def test_parse_failure_is_indeterminate_barrier_not_negative():
    relation = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize([
        unit(0, "relevant"), unit(1, "parse_failure"), unit(2, "relevant")
    ])
    assert len(relation.events) == 2
    assert relation.parse_failure_unit_ids == ("V0_u0001",)
    assert relation.negative_unit_ids == ()
