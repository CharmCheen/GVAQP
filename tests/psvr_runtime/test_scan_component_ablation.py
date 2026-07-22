import pytest

from garc_eval.psvr_pilot.policy_service import _coverage_debt_batch
from garc_eval.psvr_scan_ablation.policy_service import component_batch, decide


UNITS = [{"unit_id": i} for i in range(347)]


def payload(method, proxy=(), queried=(), scans=0):
    return {"method": method, "public_units": UNITS,
            "proxy_rows": [{"unit_id": unit, "proxy_score": score} for unit, score in proxy],
            "queried_ids": list(queried), "batch_size": 4,
            "parameters": {"scan_actions": scans}}


def test_all_components_reproduce_frozen_S1_batch_exactly():
    observed = {173, 86, 260, 42}; scores = {173: 2.0, 86: 5.0, 260: 11.0, 42: 3.0}
    expected, _ = _coverage_debt_batch(347, observed, scores, 4, 0.5, 0.25)
    # Reconstruct S1 by summing all three traced terms.
    from garc_eval.psvr_scan_ablation import policy_service as module
    old = module.INCLUDED.get("S1")
    module.INCLUDED["S1"] = frozenset({"duration", "debt", "proxy"})
    module.METHODS = frozenset(set(module.METHODS) | {"S1"})
    try:
        actual, _ = component_batch(347, observed, scores, 4, "S1")
    finally:
        module.METHODS = frozenset({"S2", "S3", "S4"})
        if old is None:
            del module.INCLUDED["S1"]
        else:
            module.INCLUDED["S1"] = old
    assert actual == expected


@pytest.mark.parametrize("method,components", [
    ("S2", {"duration", "proxy"}), ("S3", {"duration", "debt"}), ("S4", {"debt", "proxy"})])
def test_trace_has_preregistered_components_and_no_reference(method, components):
    row = decide(payload(method))["scan_priorities"][0]
    assert set(row["included_components"]) == components
    assert row["cell_id"] == "0:346" and row["parent_cell_id"] is None and row["scan_level"] == 0
    assert row["selected_rank"] == 1 and row["next_best_cell"] is None
    forbidden = {"event", "reference", "positive", "overlap", "f1"}
    assert not any(token in key.lower() for key in row for token in forbidden)


def test_fixed_A0_and_shared_candidate_tie_break():
    proxy = [(173, 5), (86, 5), (260, 2), (42, 1)]
    for method in ("S2", "S3", "S4"):
        assert decide(payload(method, proxy=proxy, scans=28))["action"] == "scan"
        row = decide(payload(method, proxy=proxy, scans=29))
        assert row["action"] == "query" and row["candidate_unit_id"] == 86


def test_schema_rejects_hidden_field():
    row = payload("S2"); row["reference_rows"] = []
    with pytest.raises(ValueError, match="schema"):
        decide(row)
