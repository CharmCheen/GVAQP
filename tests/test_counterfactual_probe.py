import json
from pathlib import Path

from rc_sem.counterfactual_probe import alternatives, build_plan, public_actions, reconstruct_b_snapshots
from rc_sem.exploratory_h0 import RuntimeAction


def scan(target, elapsed, units):
    return {"timestamp_seconds": elapsed, "physical_cost_seconds": 1.0, "action_type": "SCAN", "target": target, "outcome": {"exposed": [{"unit_id": u, "score": float(u)} for u in units]}}


def verify(target, elapsed, label="negative"):
    return {"timestamp_seconds": elapsed, "physical_cost_seconds": 1.0, "action_type": "VERIFY", "target": target, "outcome": {"label": label}}


def synthetic_trace():
    return [scan(21, 0.0, range(210, 220)), verify(213, 10.0), scan(10, 20.0, range(100, 110)), verify(109, 30.0)]


def test_restore_has_same_public_actions_and_no_unexposed_verify() -> None:
    snapshots = reconstruct_b_snapshots(synthetic_trace())
    restored = snapshots[1].runtime_state()
    assert RuntimeAction("VERIFY", 213) in public_actions(snapshots[1])
    assert RuntimeAction("VERIFY", 999) not in public_actions(snapshots[1])
    assert restored == snapshots[1].runtime_state()


def test_plan_is_label_blind_and_bounded() -> None:
    root = Path(__file__).resolve().parents[1]
    trace = json.loads((root / "outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s/B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.trace.json").read_text())
    changed = json.loads(json.dumps(trace))
    for row in changed:
        if row["action_type"] == "VERIFY":
            row["outcome"]["label"] = "positive" if row["outcome"]["label"] != "positive" else "negative"
    original = build_plan(trace, parent_trace_sha256="x" * 64)
    mutated = build_plan(changed, parent_trace_sha256="x" * 64)
    assert [item["state_id"] for item in original["states"]] == [item["state_id"] for item in mutated["states"]]
    assert [item["alternatives"] for item in original["states"]] == [item["alternatives"] for item in mutated["states"]]
    assert len(original["states"]) <= 12
    assert all(len(item["alternatives"]) <= 2 for item in original["states"])


def test_alternative_verify_is_exposed_and_not_parent_action() -> None:
    snapshots = reconstruct_b_snapshots(synthetic_trace())
    choices = alternatives(snapshots[1])
    assert choices == (RuntimeAction("SCAN", 10), RuntimeAction("VERIFY", 219))
    assert all(choice in public_actions(snapshots[1]) for choice in choices)


def test_snapshot_is_immutable_for_branch_isolation() -> None:
    snapshot = reconstruct_b_snapshots(synthetic_trace())[1]
    before = snapshot.sha256()
    _ = alternatives(snapshot)
    assert snapshot.sha256() == before
