from garc_eval.psvr_factorization.policy_service import decide
from garc_eval.psvr_pilot.policy_service import decide as stage2_decide


UNITS = [{"unit_id": i} for i in range(347)]


def payload(method, proxy=(), queried=(), scans=0):
    return {"method": method, "public_units": UNITS,
            "proxy_rows": [{"unit_id": i, "proxy_score": s} for i, s in proxy],
            "queried_ids": list(queried), "batch_size": 4,
            "parameters": {"lambda": 0.5, "beta": 0.25, "revision": 0, "scan_actions": scans}}


def test_c0_matches_stage2_coverage_interleave_actions():
    factor = decide(payload("C0"))
    old = stage2_decide({**payload("C0"), "method": "coverage_interleave"})
    assert (factor["action"], factor["scan_unit_ids"], factor["candidate_unit_id"]) == \
           (old["action"], old["scan_unit_ids"], old["candidate_unit_id"])
    proxy = [(i, float(i % 7)) for i in range(1, 347, 3)]
    factor = decide(payload("C0", proxy=proxy, scans=29))
    old = stage2_decide({**payload("C0", proxy=proxy, scans=29), "method": "coverage_interleave"})
    assert factor["action"] == old["action"] == "query"
    assert factor["candidate_unit_id"] == old["candidate_unit_id"]


def test_c3_matches_stage2_coverage_debt_on_realized_style_state():
    proxy = [(173, 2), (86, 5), (260, 11), (42, 3)]
    factor = decide(payload("C3", proxy=proxy, scans=1))
    old = stage2_decide({**payload("C3", proxy=proxy, scans=1), "method": "coverage_debt_psvr"})
    for key in ("action", "scan_unit_ids", "candidate_unit_id", "scan_priorities"):
        assert factor[key] == old[key]


def test_factor_crosses_are_distinct_and_candidate_rule_is_shared():
    assert decide(payload("C1"))["scan_unit_ids"] == [173, 86, 260, 42]
    assert decide(payload("C2"))["scan_unit_ids"] == [1, 4, 7, 10]
    proxy = [(1, 5), (4, 5), (7, 2), (10, 1)]
    for method in ("C0", "C1", "C2", "C3"):
        row = decide(payload(method, proxy=proxy, scans=29 if method in ("C0", "C1") else 1))
        assert row["candidate_unit_id"] == 1
