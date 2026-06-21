#!/usr/bin/env python3
from __future__ import annotations

import math

import pandas as pd

from repair_common import EPSILON, REPAIR_DIR, append_progress, ensure_dirs, normal_quantile


def pre_fix_formula(y_vals: list[float], m_vals: list[float], population_n: int, delta: float) -> dict:
    n = len(y_vals)
    z = normal_quantile(delta)
    ys = pd.Series(y_vals, dtype=float)
    ms = pd.Series(m_vals, dtype=float)
    fpc = math.sqrt(max(0.0, 1.0 - n / max(population_n, 1))) if population_n > 1 else 0.0
    y_hat = population_n * float(ys.mean())
    m_hat = population_n * float(ms.mean())
    y_se_total = population_n * (float(ys.std(ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    m_se_total = population_n * (float(ms.std(ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    lcb_y = max(0.0, y_hat - z * y_se_total)
    ucb_m = min(lcb_y if lcb_y > 0 else float("inf"), m_hat + z * m_se_total)
    return {"Y_hat_O": y_hat, "M_hat_O": m_hat, "LCB_Y_O": lcb_y, "UCB_M_O": ucb_m}


def fixed_formula(y_vals: list[float], m_vals: list[float], population_n: int, delta: float) -> dict:
    n = len(y_vals)
    z = normal_quantile(delta)
    ys = pd.Series(y_vals, dtype=float)
    ms = pd.Series(m_vals, dtype=float)
    fpc = math.sqrt(max(0.0, 1.0 - n / max(population_n, 1))) if population_n > 1 else 0.0
    y_hat = population_n * float(ys.mean())
    m_hat = population_n * float(ms.mean())
    y_se_total = population_n * (float(ys.std(ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    m_se_total = population_n * (float(ms.std(ddof=1)) / math.sqrt(n) * fpc if n > 1 else 0.0)
    lcb_y = max(0.0, y_hat - z * y_se_total)
    ucb_m = max(m_hat, m_hat + z * m_se_total)
    return {"Y_hat_O": y_hat, "M_hat_O": m_hat, "LCB_Y_O": lcb_y, "UCB_M_O": ucb_m}


def main() -> None:
    ensure_dirs()
    # Synthetic sample: many missed events and high variance in total events make
    # the old LCB(Y) cap push UCB(M) below M_hat.
    y_vals = [0, 50, 50, 50]
    m_vals = [0, 45, 45, 45]
    population_n = 100
    delta = 0.05
    old = pre_fix_formula(y_vals, m_vals, population_n, delta)
    new = fixed_formula(y_vals, m_vals, population_n, delta)
    old_fails = old["UCB_M_O"] < old["M_hat_O"] - EPSILON
    new_passes = (new["UCB_M_O"] >= new["M_hat_O"] - EPSILON) and (new["LCB_Y_O"] <= new["Y_hat_O"] + EPSILON)
    rows = pd.DataFrame(
        [
            {"formula": "pre_fix", **old, "invariant_passes": not old_fails},
            {"formula": "fixed", **new, "invariant_passes": new_passes},
        ]
    )
    rows.to_csv(REPAIR_DIR / "tables/bound_formula_unit_test.csv", index=False)
    if not old_fails or not new_passes:
        raise SystemExit("bound formula unit test did not catch the old defect and pass the fix")
    (REPAIR_DIR / "reports/BOUND_FORMULA_UNIT_TEST.md").write_text(
        "\n".join(
            [
                "# Bound Formula Unit Test",
                "",
                f"- epsilon: `{EPSILON}`",
                "- pre-fix formula fails invariant `UCB_M_O >= M_hat_O - epsilon`: `true`",
                "- fixed formula passes `UCB_M_O >= M_hat_O - epsilon` and `LCB_Y_O <= Y_hat_O + epsilon`: `true`",
                "",
                "Results are in `tables/bound_formula_unit_test.csv`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    append_progress(
        "R1 bound formula test",
        "python scripts/r10_fix_bound_formula.py",
        "pre-fix formula failed as expected; fixed formula passed",
        next_action="run corrected no-repair block audit",
    )


if __name__ == "__main__":
    main()
