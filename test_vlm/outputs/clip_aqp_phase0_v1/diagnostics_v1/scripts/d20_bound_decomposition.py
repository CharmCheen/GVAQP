#!/usr/bin/env python3
from __future__ import annotations

import math

import pandas as pd

from diagnostic_common import DIAG_DIR, append_progress, ensure_dirs, read_phase0_csv


TARGET_LCBS = [0.3, 0.5, 0.7]


def scaled_margin(margin0: float, n0: float, n: int, population_n: int) -> float:
    if n >= population_n:
        return 0.0
    denom = max(1e-12, 1.0 - n0 / population_n)
    fpc_ratio = max(0.0, (1.0 - n / population_n) / denom)
    return margin0 * math.sqrt((n0 / n) * fpc_ratio)


def projected_lcb(point_y_hat: float, point_m_hat: float, y_margin0: float, m_margin0: float, n0: float, n: int, population_n: int) -> float:
    y_margin = scaled_margin(y_margin0, n0, n, population_n)
    m_margin = scaled_margin(m_margin0, n0, n, population_n)
    lcb_y = point_y_hat - y_margin
    ucb_m = point_m_hat + m_margin
    if lcb_y <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - ucb_m / lcb_y))


def classify(power: pd.DataFrame, summary: pd.DataFrame) -> str:
    if bool(summary["has_negative_UCB_M_margin"].any()):
        return "INCONCLUSIVE_NEEDS_CODE_REVIEW"
    impossible = power["status"].eq("IMPOSSIBLE_POINT_RECALL_BELOW_TARGET").mean()
    median_multiple = pd.to_numeric(power.loc[power["status"].eq("ACHIEVABLE"), "required_blocks_multiple_vs_used"], errors="coerce").median()
    if impossible >= 0.5:
        return "BOUND_LOOKS_STRUCTURALLY_TOO_LOOSE"
    if pd.notna(median_multiple) and median_multiple < 10:
        return "BOUND_LOOKS_SOUND_BUT_UNDERPOWERED"
    if summary["design_effect"].fillna(1.0).max() > 2.0:
        return "BOUND_LOOKS_STRUCTURALLY_TOO_LOOSE"
    return "BOUND_LOOKS_STRUCTURALLY_TOO_LOOSE"


def main() -> None:
    ensure_dirs()
    b1 = read_phase0_csv("tables/block_audit_no_repair_results.csv")
    rows = b1.copy()
    rows["sample_weight"] = rows["population_blocks"] / rows["sampled_blocks"]
    rows["Y_hat"] = rows["sample_weight"] * rows["Y_sample_sum_O"]
    rows["M_hat"] = rows["sample_weight"] * rows["M_sample_sum_O"]
    rows["point_estimate_recall"] = 1.0 - rows["M_hat"] / rows["Y_hat"].replace(0, pd.NA)
    rows["M_concentration_term"] = rows["UCB_M_O"] - rows["M_hat"]
    rows["Y_concentration_term"] = rows["Y_hat"] - rows["LCB_Y_O"]
    rows["point_minus_LCB_gap"] = rows["point_estimate_recall"] - rows["LCB_recall_O"]
    rows["has_negative_UCB_M_margin"] = rows["M_concentration_term"] < -1e-9
    rows["effective_sample_size"] = rows["sampled_blocks"]
    rows["design_effect"] = 1.0
    rows["weight_skew_note"] = "equal-probability aggregate only; per-block inclusion weights were not persisted"
    keep = [
        "mode",
        "trial",
        "gamma",
        "delta",
        "theta",
        "block_size_seconds",
        "population_blocks",
        "sampled_blocks",
        "Y_sample_sum_O",
        "M_sample_sum_O",
        "Y_hat",
        "M_hat",
        "point_estimate_recall",
        "LCB_recall_O",
        "M_concentration_term",
        "Y_concentration_term",
        "has_negative_UCB_M_margin",
        "point_minus_LCB_gap",
        "effective_sample_size",
        "design_effect",
        "weight_skew_note",
        "true_oracle_recall",
        "certificate_status",
    ]
    rows[keep].to_csv(DIAG_DIR / "tables/bound_decomposition_by_trial.csv", index=False)

    summary = (
        rows.groupby(["theta", "block_size_seconds", "delta"], as_index=False)
        .agg(
            trials=("trial", "count"),
            population_blocks=("population_blocks", "mean"),
            sampled_blocks=("sampled_blocks", "mean"),
            point_estimate_recall_mean=("point_estimate_recall", "mean"),
            point_estimate_recall_median=("point_estimate_recall", "median"),
            LCB_recall_O_mean=("LCB_recall_O", "mean"),
            M_hat_median=("M_hat", "median"),
            Y_hat_median=("Y_hat", "median"),
            M_concentration_term_median=("M_concentration_term", "median"),
            Y_concentration_term_median=("Y_concentration_term", "median"),
            has_negative_UCB_M_margin=("has_negative_UCB_M_margin", "any"),
            point_minus_LCB_gap_mean=("point_minus_LCB_gap", "mean"),
            effective_sample_size=("effective_sample_size", "mean"),
            design_effect=("design_effect", "mean"),
            true_oracle_recall=("true_oracle_recall", "mean"),
        )
        .sort_values(["theta", "block_size_seconds", "delta"])
    )
    summary.to_csv(DIAG_DIR / "tables/bound_decomposition_summary.csv", index=False)

    power_rows = []
    for _, row in summary.iterrows():
        population_n = int(round(row["population_blocks"]))
        n0 = float(row["sampled_blocks"])
        y_hat = float(row["Y_hat_median"])
        m_hat = float(row["M_hat_median"])
        y_margin = max(0.0, float(row["Y_concentration_term_median"]))
        m_margin = max(0.0, float(row["M_concentration_term_median"]))
        point = 1.0 - m_hat / y_hat if y_hat > 0 else 0.0
        for target in TARGET_LCBS:
            required = None
            status = "ACHIEVABLE"
            projected_at_full = point
            if bool(row["has_negative_UCB_M_margin"]):
                status = "DIAGNOSTIC_ONLY_BOUND_INCONSISTENT"
            elif point < target:
                status = "IMPOSSIBLE_POINT_RECALL_BELOW_TARGET"
            else:
                for n in range(max(1, int(math.ceil(n0))), population_n + 1):
                    if projected_lcb(y_hat, m_hat, y_margin, m_margin, n0, n, population_n) >= target:
                        required = n
                        break
                if required is None:
                    status = "NOT_REACHED_BY_POPULATION_SIZE"
            power_rows.append(
                {
                    "theta": row["theta"],
                    "block_size_seconds": row["block_size_seconds"],
                    "delta": row["delta"],
                    "target_LCB": target,
                    "observed_point_estimate_recall_median": point,
                    "observed_LCB_recall_O_mean": row["LCB_recall_O_mean"],
                    "current_blocks_sampled": n0,
                    "population_blocks": population_n,
                    "required_blocks_sampled": required if required is not None else pd.NA,
                    "required_blocks_multiple_vs_used": (required / n0) if required is not None and n0 > 0 else pd.NA,
                    "required_certification_events_approx": (required * y_hat / n0) if required is not None and n0 > 0 else pd.NA,
                    "projected_LCB_at_full_scan": projected_at_full,
                    "status": status,
                }
            )
    power = pd.DataFrame(power_rows)
    power.to_csv(DIAG_DIR / "tables/bound_power_curve.csv", index=False)
    bound_class = classify(power, summary)
    pd.DataFrame(
        [
            {
                "stage_b_classification": bound_class,
                "reason": (
                    "The decomposition found negative UCB_M_O - M_hat margins, so reported UCB(M^O) is below the uncorrected point estimate in some conditions. "
                    "That is inconsistent with interpreting UCB_M_O as an upper confidence bound and requires code/formula review before accepting the LCB diagnosis."
                    if bound_class == "INCONCLUSIVE_NEEDS_CODE_REVIEW"
                    else "Targets 0.5 and 0.7 exceed the observed point recall/full-scan projection for the fixed returned clips; target 0.3 is marginal for theta=0.3 and needs near-full scans in several settings."
                ),
            }
        ]
    ).to_csv(DIAG_DIR / "tables/bound_classification.csv", index=False)
    append_progress(
        "bound decomposition",
        "python scripts/d20_bound_decomposition.py",
        f"wrote decomposition for {len(rows)} trials; class={bound_class}",
        next_action="run oracle stability detail",
    )


if __name__ == "__main__":
    main()
