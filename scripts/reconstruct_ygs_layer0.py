#!/usr/bin/env python3
"""Reconstruct and freeze the Layer-0 causal coverage comparators."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/scan_innovation_agentic_loop_v1"
AUDIT = ROOT / "outputs/scan_optimization_headroom_audit_v1"
M8_DIR = ROOT / "outputs/partial_scan_method_development_v1/mechanism_ablation"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temp.replace(path)


def main() -> None:
    run_path = AUDIT / "replay_run_summary.csv"
    checkpoint_path = AUDIT / "replay_budget_checkpoints.csv"
    physical_path = AUDIT / "physical_run_summary.csv"
    m8_path = M8_DIR / "ablation_summary.csv"
    runs = pd.read_csv(run_path)
    checkpoints = pd.read_csv(checkpoint_path)
    physical = pd.read_csv(physical_path)
    m8 = pd.read_csv(m8_path).query("method == 'M8'").copy()

    causal = runs.query("method_class == 'CAUSAL'").copy()
    metrics = [
        "exposure_grid_auc", "exposure_step_auc_at_60sec", "recall_at_10pct",
        "recall_at_20pct", "recall_at_40pct", "recall_at_60pct",
    ]
    summary = causal.groupby(["video_id", "policy_id"], as_index=False)[metrics].mean()
    seeds = causal.groupby(["video_id", "policy_id"], as_index=False).size().rename(columns={"size": "run_count"})
    summary = summary.merge(seeds, on=["video_id", "policy_id"], validate="one_to_one")
    summary["is_best_full_grid_auc"] = False
    summary["is_best_60sec_auc"] = False
    for _, group in summary.groupby("video_id"):
        summary.loc[group["exposure_grid_auc"].idxmax(), "is_best_full_grid_auc"] = True
        summary.loc[group["exposure_step_auc_at_60sec"].idxmax(), "is_best_60sec_auc"] = True

    # M8's historical integral has units recall*seconds. Normalize by its actual
    # controlled-warm horizon so it is comparable to the [0,1] 60-second AUC.
    m8["normalized_exposure_auc_at_60sec"] = m8["exposure_scan_time_auc"] / m8["wallclock"]
    m8_export = m8[[
        "video_id", "method", "normalized_exposure_auc_at_60sec", "exposure_end",
        "new_events", "max_gap", "wallclock",
    ]]
    physical_summary = physical.groupby(["video_id", "policy_id"], as_index=False).agg(
        physical_auc60=("physical_exposure_step_auc", "mean"),
        physical_auc60_sd=("physical_exposure_step_auc", "std"),
        physical_run_count=("run_id", "size"),
    )

    oracle = runs.query("method_class == 'EVALUATOR_ONLY_NONCAUSAL'")[[
        "video_id", "policy_id", "exposure_grid_auc", "exposure_step_auc_at_60sec",
        "recall_at_10pct", "recall_at_20pct",
    ]].copy()
    winners = []
    for video_id, group in summary.groupby("video_id"):
        full = group.loc[group["exposure_grid_auc"].idxmax()]
        short = group.loc[group["exposure_step_auc_at_60sec"].idxmax()]
        upper = oracle.query("video_id == @video_id").iloc[0]
        m8row = m8_export.query("video_id == @video_id").iloc[0]
        pgroup = physical_summary.query("video_id == @video_id")
        pbest = pgroup.loc[pgroup["physical_auc60"].idxmax()]
        winners.append({
            "video_id": video_id,
            "full_horizon_winner": full.policy_id,
            "full_horizon_auc": float(full.exposure_grid_auc),
            "auc60_winner": short.policy_id,
            "auc60": float(short.exposure_step_auc_at_60sec),
            "physical_auc60_winner_among_tested": pbest.policy_id,
            "physical_auc60": float(pbest.physical_auc60),
            "m8_auc60_normalized": float(m8row.normalized_exposure_auc_at_60sec),
            "offline_oracle_full_auc": float(upper.exposure_grid_auc),
            "remaining_full_auc_headroom": float(upper.exposure_grid_auc - full.exposure_grid_auc),
            "offline_oracle_auc60": float(upper.exposure_step_auc_at_60sec),
            "remaining_auc60_headroom": float(upper.exposure_step_auc_at_60sec - short.exposure_step_auc_at_60sec),
        })
    winners_df = pd.DataFrame(winners)

    control = OUT / "controls"
    control.mkdir(parents=True, exist_ok=True)
    summary.to_csv(control / "layer0_causal_baselines.csv", index=False)
    winners_df.to_csv(control / "layer0_per_video_winners.csv", index=False)
    m8_export.to_csv(control / "layer0_m8_60sec.csv", index=False)
    physical_summary.to_csv(control / "layer0_physical_baselines.csv", index=False)
    oracle.to_csv(control / "layer0_offline_upper_bound.csv", index=False)

    # Assert exact replay identities that were frozen in the parent audit.
    expected = {
        "PSP_V0_SHORT": ("ANYTIME_LARGEST_GAP", "SEQUENTIAL", "SEQUENTIAL"),
        "PSP_V1_LONG": ("MACRO_REGION_LARGEST_GAP", "MACRO_REGION_LARGEST_GAP", "UNIFORM_PREFIX"),
    }
    observed = {
        row.video_id: (row.full_horizon_winner, row.auc60_winner, row.physical_auc60_winner_among_tested)
        for row in winners_df.itertuples()
    }
    if observed != expected:
        raise AssertionError(f"Layer-0 winner mismatch: {observed} != {expected}")
    if len(checkpoints) != 880 or len(runs) != 110:
        raise AssertionError("Parent replay row counts changed")

    result = {
        "hypothesis_id": "YGS-H000",
        "status": "ACCEPTED",
        "decision": "FREEZE_PER_VIDEO_AND_PER_HORIZON_CAUSAL_COVERAGE_BASELINES",
        "observed_winners": winners,
        "interpretation": {
            "full_horizon": "Short: Anytime Largest-Gap; Long: Macro-region Largest-Gap.",
            "replay_sixty_second": "Short: Sequential; Long: Macro-region Largest-Gap.",
            "physical_sixty_second_among_tested": "Short: Sequential; Long: Uniform-prefix (Macro-region was not physically run).",
            "m8": "M8 is not the strongest 60-second comparator on either video.",
            "headroom": "Large evaluator-only headroom remains, but does not identify a causal signal.",
        },
        "comparison_rule": {
            "full_replay_auc": "compare against each video's best single causal full-grid-AUC policy",
            "60sec_auc": "compare against each video's best single causal 60-second-AUC policy",
            "low_budget_recall": "compare against pointwise maximum among frozen causal policies",
            "no_cross_video_single_baseline_claim": True,
        },
        "source_assets": {
            str(run_path.relative_to(ROOT)): sha256(run_path),
            str(checkpoint_path.relative_to(ROOT)): sha256(checkpoint_path),
            str(physical_path.relative_to(ROOT)): sha256(physical_path),
            str(m8_path.relative_to(ROOT)): sha256(m8_path),
        },
        "row_counts": {"runs": len(runs), "checkpoints": len(checkpoints), "physical": len(physical), "m8": len(m8)},
    }
    result["implementation_hash"] = sha256(Path(__file__))
    atomic_json(OUT / "hypotheses/YGS-H000.json", result)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
