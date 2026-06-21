#!/usr/bin/env python3
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from repair_common import (
    BLOCK_SIZES,
    CERT_SAMPLE_FRAC,
    DELTAS,
    GAMMAS,
    NUM_TRIALS,
    RANDOM_SEED,
    REPAIR_DIR,
    RETURNED_CLIP_BUDGET_FRAC,
    THETAS,
    add_certification_provenance,
    append_progress,
    certificate_from_sample,
    ensure_dirs,
    event_recall,
    fixed_returned_clips,
    load_events,
    load_units,
    partition_blocks,
    sample_blocks,
)


def summarize_trial(sample: pd.DataFrame, blocks: pd.DataFrame, true_recall: float, gamma: float, delta: float, theta: float, block_size: float, trial: int) -> dict:
    cert = certificate_from_sample(
        sample,
        len(blocks),
        delta,
        context={"trial": trial, "gamma": gamma, "delta": delta, "theta": theta, "block_size_seconds": block_size},
    )
    lcb = float(cert["LCB_recall_O"])
    return {
        "mode": "no_repair_v2",
        "trial": trial,
        "gamma": gamma,
        "delta": delta,
        "theta": theta,
        "block_size_seconds": block_size,
        "population_blocks": len(blocks),
        "sampled_blocks": len(sample),
        "sample_split": "certification",
        "used_for_design": False,
        "used_for_repair": False,
        "used_for_certificate": True,
        "padding_width_used": float(sample["padding_width_used"].max()) if len(sample) else math.nan,
        "score_source": ";".join(sorted(sample["score_source"].dropna().astype(str).unique())) if len(sample) else "proxy_score",
        "Y_sample_sum_O": int(sample["Y_i_O"].sum()) if len(sample) else 0,
        "M_sample_sum_O": int(sample["M_i_O"].sum()) if len(sample) else 0,
        "Y_hat_O": cert["Y_hat_O"],
        "M_hat_O": cert["M_hat_O"],
        "UCB_M_O": cert["UCB_M_O"],
        "LCB_Y_O": cert["LCB_Y_O"],
        "LCB_recall_O": lcb,
        "total_events_O": int(blocks["Y_i_O"].sum()),
        "total_missed_O": int(blocks["M_i_O"].sum()),
        "true_oracle_recall": true_recall,
        "coverage": lcb <= true_recall,
        "GVR": lcb > true_recall,
        "tightness": true_recall - lcb,
        "certificate_success": lcb >= gamma,
        "certificate_status": cert["certificate_status"] if lcb >= gamma else "NO_CERTIFICATE",
        "cost_to_certificate": len(sample),
        "certification_cost": len(sample),
        "total_cost": len(sample),
        "event_boundary_type": "pseudo_from_adjacent_oracle_positive_units",
        "oracle_relative": True,
        "epsilon": cert["epsilon"],
        "bound_invariant_UCB_M_ge_M_hat": cert["UCB_M_O"] >= cert["M_hat_O"] - cert["epsilon"],
        "bound_invariant_LCB_Y_le_Y_hat": cert["LCB_Y_O"] <= cert["Y_hat_O"] + cert["epsilon"],
    }


def recompute_check(rows: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    grouped = rows.groupby(["trial", "gamma", "delta", "theta", "block_size_seconds"], as_index=False).agg(
        sampled_blocks=("block_id", "count"),
        Y_sample_sum_O=("Y_i_O", "sum"),
        M_sample_sum_O=("M_i_O", "sum"),
        population_blocks=("population_blocks", "first"),
    )
    merged = grouped.merge(
        results[
            [
                "trial",
                "gamma",
                "delta",
                "theta",
                "block_size_seconds",
                "sampled_blocks",
                "Y_sample_sum_O",
                "M_sample_sum_O",
                "population_blocks",
            ]
        ],
        on=["trial", "gamma", "delta", "theta", "block_size_seconds"],
        suffixes=("_rows", "_results"),
        how="outer",
    )
    merged["sampled_blocks_match"] = merged["sampled_blocks_rows"] == merged["sampled_blocks_results"]
    merged["Y_sample_sum_match"] = merged["Y_sample_sum_O_rows"] == merged["Y_sample_sum_O_results"]
    merged["M_sample_sum_match"] = merged["M_sample_sum_O_rows"] == merged["M_sample_sum_O_results"]
    merged["population_blocks_match"] = merged["population_blocks_rows"] == merged["population_blocks_results"]
    merged["all_match"] = merged[["sampled_blocks_match", "Y_sample_sum_match", "M_sample_sum_match", "population_blocks_match"]].all(axis=1)
    return merged


def main() -> None:
    ensure_dirs()
    units = load_units()
    events = load_events()
    rng = np.random.default_rng(RANDOM_SEED + 20)
    returned = fixed_returned_clips(units, RETURNED_CLIP_BUDGET_FRAC)
    result_rows = []
    block_rows = []
    for theta in THETAS:
        true_recall, _, _ = event_recall(events, returned, theta)
        for block_size in BLOCK_SIZES:
            blocks = partition_blocks(units, events, returned, block_size, theta)
            for gamma in GAMMAS:
                for delta in DELTAS:
                    for trial in range(NUM_TRIALS):
                        sample = sample_blocks(blocks, rng, CERT_SAMPLE_FRAC)
                        sample = add_certification_provenance(sample, trial, gamma, delta, theta, block_size, len(blocks))
                        block_rows.append(sample)
                        result_rows.append(summarize_trial(sample, blocks, true_recall, gamma, delta, theta, block_size, trial))
    rows = pd.concat(block_rows, ignore_index=True)
    results = pd.DataFrame(result_rows)
    rows = rows[
        [
            "trial",
            "gamma",
            "delta",
            "theta",
            "block_size_seconds",
            "block_id",
            "video_id",
            "start_time",
            "end_time",
            "Y_i_O",
            "M_i_O",
            "inclusion_probability",
            "sample_split",
            "used_for_design",
            "used_for_repair",
            "used_for_certificate",
            "padding_width_used",
            "score_source",
            "population_blocks",
        ]
    ]
    rows.to_csv(REPAIR_DIR / "tables/block_audit_rows_v2.csv", index=False)
    results.to_csv(REPAIR_DIR / "tables/block_audit_no_repair_results_v2.csv", index=False)
    checks = recompute_check(rows, results)
    checks.to_csv(REPAIR_DIR / "tables/block_audit_recompute_check_v2.csv", index=False)
    ok = bool(checks["all_match"].all())
    (REPAIR_DIR / "reports/BLOCK_AUDIT_RECOMPUTE_CHECK.md").write_text(
        "\n".join(
            [
                "# Block Audit Recompute Check v2",
                "",
                f"- per-block rows: `{len(rows)}`",
                f"- trial rows: `{len(results)}`",
                f"- all sampled block aggregate checks match: `{ok}`",
                "",
                "Checked from `tables/block_audit_rows_v2.csv` against `tables/block_audit_no_repair_results_v2.csv`: sampled block count, `Y_sample_sum_O`, `M_sample_sum_O`, and population block count.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if not ok:
        raise SystemExit("per-block recomputation check failed")
    append_progress(
        "R2/R5 corrected no-repair block audit",
        "python scripts/r20_block_audit_no_repair_v2.py",
        f"wrote {len(results)} trial rows and {len(rows)} block rows; recompute_check={ok}",
        next_action="identify certification oracle",
    )


if __name__ == "__main__":
    main()
