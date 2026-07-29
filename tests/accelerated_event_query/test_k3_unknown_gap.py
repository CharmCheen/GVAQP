from garc_eval.accelerated_event_query import K3UnitEventAdapter

from .v3_helpers import unit


def test_one_unknown_gap_is_bridged_but_preserved():
    relation = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize([
        unit(0, "relevant"), unit(1, "unknown"), unit(2, "relevant")
    ])
    assert len(relation.events) == 1
    assert (relation.events[0].start_time, relation.events[0].end_time) == (0.0, 30.0)
    assert relation.unknown_unit_ids == ("V0_u0001",)
    assert "V0_u0001" not in relation.events[0].source_candidate_ids


def test_two_unknown_units_do_not_bridge():
    relation = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize([
        unit(0, "relevant"), unit(1, "unknown"), unit(2, "unknown"), unit(3, "relevant")
    ])
    assert len(relation.events) == 2
