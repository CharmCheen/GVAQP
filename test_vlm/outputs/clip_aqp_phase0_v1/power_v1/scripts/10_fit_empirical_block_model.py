#!/usr/bin/env python3
from __future__ import annotations

import json

import pandas as pd

from power_common import (
    POWER_DIR,
    REFERENCE_BLOCK_SIZE,
    REFERENCE_DELTA,
    REFERENCE_GAMMA,
    REFERENCE_THETA,
    append_progress,
    ensure_dirs,
    load_repair_tables,
)


def main() -> None:
    ensure_dirs()
    rows, results = load_repair_tables()
    unique_blocks = (
        rows.sort_values(["theta", "block_size_seconds", "block_id", "trial"])
        .drop_duplicates(["theta", "block_size_seconds", "block_id"])
        .reset_index(drop=True)
    )
    unique_blocks.to_csv(POWER_DIR / "tables/empirical_unique_blocks.csv", index=False)
    ref = unique_blocks[
        (unique_blocks["theta"] == REFERENCE_THETA)
        & (unique_blocks["block_size_seconds"] == REFERENCE_BLOCK_SIZE)
    ].copy()
    if ref.empty:
        raise SystemExit("reference empirical block population is empty")
    ref.to_csv(POWER_DIR / "tables/empirical_reference_blocks.csv", index=False)

    current = results[
        (results["theta"] == REFERENCE_THETA)
        & (results["block_size_seconds"] == REFERENCE_BLOCK_SIZE)
        & (results["gamma"] == REFERENCE_GAMMA)
        & (results["delta"] == REFERENCE_DELTA)
    ].copy()
    params = {
        "reference_theta": REFERENCE_THETA,
        "reference_block_size_seconds": REFERENCE_BLOCK_SIZE,
        "reference_gamma": REFERENCE_GAMMA,
        "reference_delta": REFERENCE_DELTA,
        "num_reference_blocks": int(len(ref)),
        "number_of_pseudo_events": int(ref["Y_i_O"].sum()),
        "positive_block_rate": float((ref["Y_i_O"] > 0).mean()),
        "event_prevalence_per_block": float(ref["Y_i_O"].mean()),
        "miss_rate": float(ref["M_i_O"].sum() / ref["Y_i_O"].sum()) if ref["Y_i_O"].sum() else 0.0,
        "reference_oracle_recall": float(1.0 - ref["M_i_O"].sum() / ref["Y_i_O"].sum()) if ref["Y_i_O"].sum() else 0.0,
        "current_true_oracle_recall_mean": float(current["true_oracle_recall"].mean()) if not current.empty else 0.0,
        "current_LCB_recall_mean": float(current["LCB_recall_O"].mean()) if not current.empty else 0.0,
        "current_LCB_recall_median": float(current["LCB_recall_O"].median()) if not current.empty else 0.0,
        "current_fraction_vacuous": float((current["LCB_recall_O"] <= 1e-12).mean()) if not current.empty else 1.0,
        "current_cost_to_certificate_mean": float(current["cost_to_certificate"].mean()) if not current.empty else 0.0,
        "proxy_stratification_fields_available": False,
        "stratification_used_in_power_v1": "video_id/source strata; no candidate/proxy-region field exists in block_audit_rows_v2.csv",
    }
    pd.DataFrame([params]).to_csv(POWER_DIR / "tables/empirical_params.csv", index=False)
    distributions = []
    for col in ["Y_i_O", "M_i_O"]:
        counts = ref[col].value_counts().sort_index()
        for value, count in counts.items():
            distributions.append({"distribution": col, "value": value, "count": int(count), "fraction": float(count / len(ref))})
    pd.DataFrame(distributions).to_csv(POWER_DIR / "tables/empirical_block_distributions.csv", index=False)
    (POWER_DIR / "config/power_v1_config.json").write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")
    append_progress(
        "fit empirical block model",
        "python scripts/10_fit_empirical_block_model.py",
        f"reference blocks={len(ref)} pseudo_events={params['number_of_pseudo_events']} miss_rate={params['miss_rate']:.3f}",
        next_action="run power scaling simulation",
    )


if __name__ == "__main__":
    main()
