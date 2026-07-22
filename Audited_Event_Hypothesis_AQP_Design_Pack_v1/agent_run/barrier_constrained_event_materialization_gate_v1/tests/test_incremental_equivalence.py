import pandas as pd

from garc_eval.bcem_gate_v1.core import (
    BCEMConfig, IncrementalLegalState, legal_group_edges, parse_observations,
)
from garc_eval.bcem_gate_v1.public import IncrementalBCEM, batch_materialize


def units(n=20):
    return pd.DataFrame({"unit_id": range(n), "start_time": [10.0*i for i in range(n)],
                         "end_time": [10.0*(i+1) for i in range(n)]})


def canonical(edges):
    return {i: tuple((g.anchors, g.start_time, g.end_time, g.unknown_internal_units) for g in groups)
            for i, groups in edges.items()}


def test_incremental_observation_transitions_equal_batch_fallback():
    sequence = [(2, "positive"), (5, "positive"), (3, "negative"),
                (8, "negative"), (7, "positive"), (6, "positive")]
    engine = IncrementalLegalState.empty(units(), BCEMConfig())
    rows = []
    for uid, label in sequence:
        rows.append({"unit_id": uid, "oracle_label_after_query": label})
        engine.apply(uid, label)
        batch_state = parse_observations(pd.DataFrame(rows))
        batch = legal_group_edges(units(), batch_state, BCEMConfig()) if batch_state.positives else {}
        assert engine.state == batch_state
        assert canonical(engine.edges) == canonical(batch)
    assert engine.transition_count == len(sequence)
    assert engine.full_recompute_fallbacks == len(sequence)


def test_public_incremental_relation_equals_batch_after_positive_and_negative_updates():
    sequence = [(2, "positive"), (5, "positive"), (3, "negative"),
                (7, "positive"), (6, "positive"), (8, "negative")]
    cfg = BCEMConfig(objective_id="CAP_NORMALIZED_DESCRIPTION_LENGTH_V1")
    engine = IncrementalBCEM(units(), cfg)
    rows = []
    for uid, label in sequence:
        rows.append({"unit_id": uid, "oracle_label_after_query": label})
        incremental, diag = engine.apply(uid, label)
        batch, partition, _ = batch_materialize(units(), pd.DataFrame(rows), cfg)
        cols = ["event_id", "start_time", "end_time", "anchor_unit_ids", "relation_hash"]
        assert incremental[cols].reset_index(drop=True).equals(batch[cols].reset_index(drop=True))
        assert engine.partition.anchor_tuples == partition.anchor_tuples
        assert diag["full_video_units_scanned_after_initialization"] == 0
        assert diag["maximum_lookback_seconds"] == 40.0
