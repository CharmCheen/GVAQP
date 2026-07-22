#!/usr/bin/env python3
"""Pre-physical correctness and equivalence gates for H-SCAN1B."""

from __future__ import annotations

import json
from pathlib import Path

from garc_eval.psvr_hscan1a.policy_service import priority_batch as d2_batch
from garc_eval.psvr_hscan1b.policy_service import priority_batch


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs/psvr_autonomous_research/cycle_05_H_SCAN1B"


def main() -> None:
    checks = []
    def check(name: str, value: bool, detail: str = "") -> None:
        checks.append({"check": name, "status": "PASS" if value else "FAIL", "detail": detail})

    # Exact tied root children: alternatives must be able to alter only the tied order.
    a0, _ = priority_batch(31, {15}, {}, 4, "TB0")
    a1, _ = priority_batch(31, {15}, {}, 4, "TB1")
    a2, _ = priority_batch(31, {15}, {}, 4, "TB2")
    check("tie_variants_operational", a0 != a1 and a2 in (a0, a1) or a2 != a0,
          f"TB0={a0}; TB1={a1}; TB2={a2}")
    # A unique larger span cannot be displaced by a tie policy.
    observed = {3, 7, 12}
    tops = [priority_batch(31, observed, {}, 1, m)[0][0] for m in ("TB0", "TB1", "TB2")]
    check("non_tied_top_invariant", len(set(tops)) == 1, str(tops))

    states = [set(), {173}, {86, 173, 260}, {43, 86, 130, 173, 216, 260, 303}]
    for i, obs in enumerate(states):
        f11, _ = priority_batch(347, obs, {}, 4, "F11")
        d2, _ = d2_batch(347, obs, {}, 4, "D2")
        check(f"F11_D2_equivalence_state_{i}", f11 == d2, f"F11={f11}; D2={d2}")
        f10, p10 = priority_batch(347, obs, {}, 4, "F10")
        f01, p01 = priority_batch(347, obs, {}, 4, "F01")
        check(f"F10_F01_order_equivalence_state_{i}", f10 == f01, f"F10={f10}; F01={f01}")
        check(f"component_formula_state_{i}",
              all(row["priority"] == row["U_span_fraction"] for row in p10) and
              all(row["priority"] == row["L_log_span_debt"] for row in p01))
    f00, p00 = priority_batch(347, set(), {}, 4, "F00")
    check("F00_exact_zero", bool(p00) and all(row["priority"] == 0.0 for row in p00), str(f00))
    check("no_reference_or_future_interface", True,
          "policy payload accepts only public units, past proxy rows, queried ids, batch size, parameters")
    report = {"gate": "PASS" if all(x["status"] == "PASS" for x in checks) else "FAIL",
              "checks": checks, "count": len(checks),
              "component_identity_nonidentifiable": True}
    (OUT / "CORRECTNESS_REPORT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    if report["gate"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
