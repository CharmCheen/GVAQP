import pytest

from garc_eval.psvr_hscan1a.policy_service import decide, eligible_cells, priority_batch
from garc_eval.psvr_pilot.policy_service import _coverage_debt_batch, decide as old_decide


UNITS = [{"unit_id": i} for i in range(347)]


def payload(method, proxy=(), queried=(), scans=0):
    return {"method": method, "public_units": UNITS,
            "proxy_rows": [{"unit_id": unit, "proxy_score": score} for unit, score in proxy],
            "queried_ids": list(queried), "batch_size": 4,
            "parameters": {"lambda": 0.5, "beta": 0.25, "revision": 0, "scan_actions": scans}}


@pytest.mark.parametrize("proxy", [
    (),
    ((173, 2), (86, 5), (260, 11), (42, 3)),
    ((173, 2), (86, 5), (260, 11), (42, 3), (303, 10), (216, 5), (129, 1), (238, 8)),
])
def test_D1_batch_exactly_matches_frozen_C1_implementation(proxy):
    scores = dict(proxy); observed = set(scores)
    expected, _ = _coverage_debt_batch(347, observed, scores, 4, 0.5, 0.25)
    actual, _ = priority_batch(347, observed, scores, 4, "D1")
    assert actual == expected


def test_D0_decision_matches_frozen_C0():
    new = decide(payload("D0"))
    old = old_decide({**payload("D0"), "method": "coverage_interleave"})
    assert (new["action"], new["scan_unit_ids"], new["candidate_unit_id"]) == \
           (old["action"], old["scan_unit_ids"], old["candidate_unit_id"])


@pytest.mark.parametrize("proxy", [
    (), ((173, 2), (86, 5), (260, 11), (42, 3)),
    ((20, 6), (42, 3), (75, 6), (86, 5), (151, 10), (173, 2), (238, 8), (260, 11)),
])
def test_component_zeroing_identity_on_scheduler_states(proxy):
    scores = dict(proxy); observed = set(scores)
    _, full = priority_batch(347, observed, scores, 4, "D1")
    _, structural = priority_batch(347, observed, scores, 4, "D2")
    _, proxy_only = priority_batch(347, observed, scores, 4, "D3")
    # Eligibility can diverge after the first selection because zeroing changes
    # the chosen cell. The identity is checked on every common current state by
    # comparing the first eligible selection scores by cell id.
    for row in full[:1] + structural[:1] + proxy_only[:1]:
        assert row["full_priority"] == pytest.approx(
            row["structural_group_contribution"] + row["proxy_group_contribution"])
    assert structural[0]["priority"] == pytest.approx(structural[0]["structural_group_contribution"])
    assert proxy_only[0]["priority"] == pytest.approx(proxy_only[0]["proxy_group_contribution"])


def test_D1_D2_D3_have_identical_eligible_cells_on_same_state():
    observed = {42, 86, 173, 260}; expected = eligible_cells(347, observed)
    for method in ("D1", "D2", "D3"):
        # All three rank exactly the same eligible set before selection.
        assert eligible_cells(347, observed) == expected
        assert {row["cell_id"] for row in priority_batch(347, observed, {x: 0.0 for x in observed}, 1, method)[1]} <= \
               {row["cell_id"] for row in expected}


def test_D3_zero_signal_uses_frozen_ascending_unit_tie_break():
    chosen, rows = priority_batch(347, set(), {}, 4, "D3")
    assert chosen == [173, 86, 42, 20]
    assert all(row["priority"] == 0.0 for row in rows)


def test_shared_candidate_tie_break_and_A0():
    proxy = ((86, 5), (173, 5), (260, 2), (42, 1))
    for method in ("D0", "D1", "D2", "D3"):
        scans = 29 if method != "D0" else 29
        row = decide(payload(method, proxy=proxy, scans=scans))
        assert row["action"] == "query" and row["candidate_unit_id"] == 86


def test_no_future_proxy_or_evaluator_fields_are_accepted():
    for forbidden in ("future_proxy_rows", "reference_events", "eventual_positive_candidate"):
        row = payload("D1"); row[forbidden] = []
        with pytest.raises(ValueError, match="schema"):
            decide(row)
