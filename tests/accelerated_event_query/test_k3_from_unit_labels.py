from garc_eval.accelerated_event_query import K3UnitEventAdapter
from garc_eval.accelerated_event_query.model_relative_labels import ModelRelativeUnitLabel

from .v3_helpers import unit


def test_same_unit_sequence_always_has_same_event_relation():
    rows = [unit(2, "not_relevant"), unit(1, "relevant"), unit(0, "relevant")]
    left = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize(rows)
    right = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize(reversed(rows))
    assert left == right
    assert left.relation_sha256 == right.relation_sha256
    assert len(left.events) == 1
    assert (left.events[0].start_time, left.events[0].end_time) == (0.0, 20.0)


def test_duration_cap_deterministically_splits_observationally_adjacent_events():
    rows = [unit(index, "relevant") for index in range(5)]
    relation = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize(rows)
    assert [(event.start_time, event.end_time) for event in relation.events] == [
        (0.0, 40.0), (40.0, 50.0)
    ]


def test_overlapping_windows_merge_and_exact_duplicate_is_suppressed():
    left = unit(0, "relevant")
    overlap = ModelRelativeUnitLabel(
        unit_id="V0_overlap",
        query_id="Q_DRIVER_RESPONSE_V1",
        video_id="V0",
        start_time=5.0,
        end_time=15.0,
        outcome="relevant",
    )
    relation = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize([
        left, left, overlap
    ])
    assert len(relation.events) == 1
    assert relation.events[0].source_candidate_ids == ("V0_overlap", "V0_u0000")
    assert (relation.events[0].start_time, relation.events[0].end_time) == (0.0, 15.0)


def test_video_boundary_always_separates_events():
    relation = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1").materialize([
        unit(0, "relevant", video_id="A"), unit(0, "relevant", video_id="B")
    ])
    assert len(relation.events) == 2
    assert {event.video_id for event in relation.events} == {"A", "B"}
