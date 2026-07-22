from garc_eval.psvr_pilot.policy_service import coverage_state, decide


def payload(method, observed=None, queried=None, **parameters):
    observed = observed or {}
    return {
        "method": method,
        "public_units": [{"unit_id": i} for i in range(16)],
        "proxy_rows": [{"unit_id": i, "proxy_score": score} for i, score in observed.items()],
        "queried_ids": queried or [],
        "batch_size": 4,
        "parameters": parameters,
    }


def test_uniform_temporal_first_batch_is_deterministic_and_spread():
    result = decide(payload("uniform_temporal_interleave"))
    assert result["action"] == "scan"
    assert result["scan_unit_ids"] == [7, 11, 3, 13]
    assert len(set(result["scan_unit_ids"])) == 4


def test_coverage_debt_uses_only_observed_signal_and_changes_priority():
    base = decide(payload("coverage_debt_psvr", {7: 0.0}, scan_actions=1))
    signaled = decide(payload("coverage_debt_psvr", {7: 10.0}, scan_actions=1))
    assert base["action"] == signaled["action"] == "query"
    # After the visible candidate is queried, the next scan is allowed to use
    # its already-observed proxy signal but no future score.
    base = decide(payload("coverage_debt_psvr", {7: 0.0}, queried=[7], scan_actions=1))
    signaled = decide(payload("coverage_debt_psvr", {7: 10.0}, queried=[7], scan_actions=1))
    assert base["action"] == signaled["action"] == "scan"
    assert all("observed_local_proxy_signal" in row for row in signaled["scan_priorities"])
    assert base["scan_priorities"] != signaled["scan_priorities"]


def test_scan_then_verify_does_not_query_before_full_scan():
    result = decide(payload("scan_then_verify", {i: 1.0 for i in range(15)}))
    assert result["action"] == "scan"
    result = decide(payload("scan_then_verify", {i: 1.0 for i in range(16)}))
    assert result["action"] == "query"


def test_coverage_state_reports_largest_contiguous_debt():
    state = coverage_state(10, {2, 7})
    assert state["max_unobserved_units"] == 4
    assert state["temporal_coverage"] == 0.2
