from __future__ import annotations

from rc_sem.sequential import LabelIsolatedSequentialEnv, SequentialActionType, SequentialCostConfig


def test_forced_branch_targets_are_public_and_legal(monkeypatch):
    import controller_dynamic_headroom as headroom

    costs = SequentialCostConfig(scan_cost=0.1, verify_cost=1.0, scan_cell_units=2)
    env = LabelIsolatedSequentialEnv(
        unit_windows={i: (i * 10.0, (i + 1) * 10.0) for i in range(4)},
        proxy_scores={0: 0.1, 1: 0.9, 2: 0.8, 3: 0.2},
        oracle_labels={i: "negative" for i in range(4)},
        budget=3.0,
        costs=costs,
    )
    env.step(headroom.SequentialAction(SequentialActionType.SCAN, 0, "setup"))
    state = env.state
    verify = headroom.forced_action(state, SequentialActionType.VERIFY)
    scan = headroom.forced_action(state, SequentialActionType.SCAN)
    assert verify.target_id == 1
    assert scan.target_id in state.unscanned_cell_ids


def test_canonical_hash_is_order_invariant():
    import controller_dynamic_headroom as headroom

    assert headroom.canonical_hash({"a": 1, "b": 2}) == headroom.canonical_hash(
        {"b": 2, "a": 1}
    )
