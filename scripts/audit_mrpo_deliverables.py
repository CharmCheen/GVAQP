#!/usr/bin/env python3
"""Independent read-only consistency checks for MRPO-V1 deliverables."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_mrpo_phase0_audit import region_index


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/macro_region_proxy_optimization_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    required = [
        "contracts/frozen_contract.json", "audits/asset_audit.json", "audits/label_audit.json",
        "audits/feature_legality_audit.json", "audits/preview_cost_audit.json", "audits/leakage_audit.json",
        "labels/region_binary_labels.parquet", "labels/region_count_labels.parquet", "labels/event_region_map.parquet",
        "predictions/region_scores.parquet", "predictions/out_of_video_predictions.parquet",
        "metrics/ranking_metrics.json", "metrics/cost_adjusted_metrics.json", "metrics/per_video_metrics.csv",
        "metrics/per_region_metrics.csv", "metrics/random_baseline_distribution.json",
        "metrics/leave_one_video_out_direction.json", "metrics/net_event_yield_budget_grid.csv",
        "metrics/failure_analysis_metrics.json", "predictions/candidate_lovo_calibration_predictions.parquet",
        "reports/FINAL_PROXY_DECISION.md", "repair_log.json", "environment_lock.json", "code_version.json",
        "reports/CONTRACT_COMPLETION_MATRIX.csv", "reports/CONTRACT_COMPLETION_MATRIX.md",
    ]
    checks = {}
    checks["required_files_exist"] = all((OUT / path).exists() for path in required)
    binary = pd.read_parquet(OUT / "labels/region_binary_labels.parquet")
    count = pd.read_parquet(OUT / "labels/region_count_labels.parquet")
    event_map = pd.read_parquet(OUT / "labels/event_region_map.parquet")
    checks["region_row_count_229"] = len(binary) == len(count) == 229
    checks["offset0_exposable_count_263"] = int(count.residual_event_count.sum()) == 263
    checks["all_reference_event_map_count_268"] = event_map.reference_event_id.nunique() == 268 and len(event_map) == 268
    checks["event_mapped_once"] = event_map.reference_event_id.value_counts().eq(1).all()
    checks["exact_boundary_uses_smaller_region_index"] = (
        region_index(0.0, 40, 100) == 0
        and region_index(40.0, 40, 100) == 0
        and region_index(40.0 + 1e-9, 40, 100) == 1
    )
    phase0_labels = json.loads((OUT / "audits/label_audit.json").read_text())
    checks["all_macro_candidates_and_tail_regions_retained"] = (
        phase0_labels["candidate_lengths"] == [40, 60, 90, 120]
        and bool(phase0_labels["tail_regions_retained"])
        and phase0_labels["event_mapping_row_count_per_length"] == 268
    )
    random = pd.read_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv")
    checks["random_100_seeds_per_video"] = random.groupby("video_id").seed.nunique().eq(100).all()
    model = pd.read_csv(OUT / "experiments/models/config_ranking.csv")
    checks["search_config_count_45_le_50"] = model.config_id.nunique() == 45
    checks["model_family_count_le_5"] = model.family.nunique() <= 5
    preview = json.loads((OUT / "audits/preview_cost_audit.json").read_text())
    checks["preview_cost_ratio_le_0_10"] = preview["preview_to_full_scan_cost_ratio"] <= 0.10
    checks["preview_deterministic"] = bool(preview["determinism_repeat_hash_match"])
    preview_manifest = json.loads((OUT / "preview/operator_manifests/P0_SELECTION.json").read_text())
    checks["preview_config_count_le_4"] = len(preview_manifest["candidate_operators"]) <= 4
    checks["every_preview_config_deterministic"] = (
        len(preview_manifest["per_operator_determinism"]) == len(preview_manifest["candidate_operators"])
        and all(row["hash_match"] for row in preview_manifest["per_operator_determinism"].values())
    )
    checks["every_preview_config_complete_no_missing"] = all(
        row["zero_sample_region_count"] == 0 and row["missing_feature_cell_count"] == 0
        for row in preview_manifest["per_operator_observability"].values()
    )
    checks["every_preview_config_has_cost_decomposition"] = (
        len(preview["per_operator_cost_decomposition"]) == len(preview_manifest["candidate_operators"])
        and all(
            all(key in row for key in (
                "run1_decode_and_pipe_wait_sec", "run1_model_inference_sec",
                "run1_feature_compute_sec", "run1_total_wallclock_sec",
                "run1_seconds_per_video_hour", "run1_peak_memory_kib_process_lifetime",
            )) for row in preview["per_operator_cost_decomposition"].values()
        )
    )
    leakage = json.loads((OUT / "audits/leakage_audit.json").read_text())
    checks["no_forbidden_main_input"] = leakage["forbidden_input_intersection"] == []
    gate = json.loads((OUT / "metrics/exploratory_gate.json").read_text())
    checks["failed_gate_is_terminal"] = (
        gate["exploratory_proxy_signal"] == "NOT_ESTABLISHED"
        and gate["one_step_allocator"] == "NOT_ALLOWED"
    )
    checks["no_stage_b_allocator_artifact"] = not any("allocator" in p.name.lower() for p in OUT.rglob("*") if p.is_file())
    per_video = pd.read_csv(OUT / "metrics/per_video_metrics.csv")
    checks["reported_recall_matches_gate"] = all(
        abs(float(row["recall_at_20"]) - float(per_video.set_index("video_id").loc[row["video_id"], "recall_at_20"])) < 1e-12
        for row in gate["per_video"]
    )
    per_region = pd.read_csv(OUT / "metrics/per_region_metrics.csv")
    recomputed_primary_ok = True
    for video_id, group in per_region.groupby("video_id"):
        reported = float(per_video.set_index("video_id").loc[video_id, "recall_at_20"])
        recomputed = float(group.loc[group.selected_at_20, "residual_event_count"].sum() / group.residual_event_count.sum())
        spent = float(group.loc[group.selected_at_20, "full_scan_cost_sec"].sum())
        if abs(reported - recomputed) > 1e-12 or spent > 0.20 * float(group.full_scan_cost_sec.sum()) + 1e-12:
            recomputed_primary_ok = False
    checks["primary_recall_recomputes_and_never_exceeds_cost_budget"] = recomputed_primary_ok
    oov = pd.read_parquet(OUT / "predictions/out_of_video_predictions.parquet")
    region = pd.read_parquet(OUT / "predictions/region_scores.parquet")
    checks["oov_is_combination_model_not_design_selected_b4"] = (
        "binary_probability" in oov.columns and "binary_probability" not in region.columns
    )
    required_secondary = {
        "recall_at_10", "recall_at_20", "recall_at_30", "ranking_event_recall_auc",
        "binary_auprc", "binary_brier_score_lovo_calibrated", "count_mae_lovo_calibrated",
        "spearman_count", "leave_best_region_out_recall_at_20",
        "best_region_contribution_ratio_at_20", "enrichment_at_20",
    }
    checks["all_candidate_secondary_metrics_reported"] = required_secondary.issubset(per_video.columns) and not per_video[list(required_secondary)].isna().any().any()
    lovo = json.loads((OUT / "metrics/leave_one_video_out_direction.json").read_text())
    checks["nested_lovo_has_both_complete_video_directions"] = (
        len(lovo["results"]) == 2
        and {row["test_video_id"] for row in lovo["results"]} == set(per_video.video_id)
        and all(row["train_video_id"] != row["test_video_id"] for row in lovo["results"])
    )
    net_grid = pd.read_csv(OUT / "metrics/net_event_yield_budget_grid.csv")
    checks["net_yield_includes_60_and_q10_q20_q30"] = (
        set(net_grid.budget_id) == {"WALLCLOCK_60S", "FULL_SCAN_COST_10PCT", "FULL_SCAN_COST_20PCT", "FULL_SCAN_COST_30PCT"}
        and net_grid.groupby("video_id").budget_id.nunique().eq(4).all()
    )
    checks["preview_paid_inside_every_net_budget"] = (
        (net_grid.preview_cost_sec > 0).all()
        and np.allclose(
            net_grid.proxy_scan_budget_sec,
            np.maximum(0.0, net_grid.total_wallclock_budget_sec - net_grid.preview_cost_sec),
        )
    )
    static = pd.read_csv(OUT / "experiments/controls/static_control_metrics.csv")
    present_controls = set(static.control.str.extract(r"^(B\d)", expand=False).dropna())
    for file_name, control_id in [
        ("B0_RANDOM_COST_MATCHED_100_SEEDS.csv", "B0"),
        ("B4_best_univariate.csv", "B4"),
        ("B6_shuffled_label.csv", "B6"),
        ("B7_shuffled_score_100_seeds.csv", "B7"),
    ]:
        if (OUT / "experiments/controls" / file_name).exists():
            present_controls.add(control_id)
    checks["mandatory_controls_B0_through_B8_present"] = present_controls == {f"B{i}" for i in range(9)}
    failure = json.loads((OUT / "metrics/failure_analysis_metrics.json").read_text())
    checks["failure_analysis_structured_evidence_complete"] = (
        "proxy_feature_missingness" in failure
        and "preview_cost_decomposition" in failure
        and "nested_lovo" in failure
        and len(failure["per_video"]) == 2
        and (OUT / "experiments/models/high_score_zero_event_regions.csv").exists()
        and (OUT / "experiments/models/low_score_positive_event_regions.csv").exists()
    )
    repairs = json.loads((OUT / "repair_log.json").read_text())
    checks["repair_cycles_le_1_and_fully_recorded"] = len(repairs) <= 1 and all(
        all(key in row for key in ("issue", "root_cause", "affected_artifacts", "before_hash", "after_hash", "experiments_rerun", "claim_impact"))
        for row in repairs
    )
    completion = pd.read_csv(OUT / "reports/CONTRACT_COMPLETION_MATRIX.csv")
    checks["completion_matrix_has_no_unresolved_applicable_requirement"] = not completion.status.isin(["MISSING", "FAIL", "INCOMPLETE"]).any()
    final_text = (OUT / "reports/FINAL_PROXY_DECISION.md").read_text()
    terminal_fields = [
        "CONTRACT_HASH", "CODE_COMMIT", "VIDEO_COUNT", "DESIGN_VIDEO_COUNT",
        "VALIDATION_VIDEO_COUNT", "TEST_VIDEO_COUNT", "REFERENCE_TYPE",
        "REFERENCE_COMPLETENESS_STATUS", "EVENT_CLAIM_SCOPE", "PREVIEW_OPERATOR",
        "PREVIEW_OPERATOR_HASH", "PREVIEW_COST_RATIO", "PREVIEW_LEGALITY",
        "MACRO_REGION_LENGTH", "FEATURE_SCHEMA_HASH", "MODEL_FAMILY", "MODEL_CONFIG_HASH",
        "PRIMARY_RECALL_AT_20", "PRIMARY_ENRICHMENT_AT_20", "RANKING_AUC",
        "NET_EVENT_YIELD", "CROSS_VIDEO_DIRECTION", "LEAVE_BEST_VIDEO_OUT",
        "BEST_REGION_CONTRIBUTION", "EXPLORATORY_GATE", "FORMAL_STATIC_RANKING_GATE",
        "REGION_VALUE_PROXY_SIGNAL", "SELECTED_PROXY_STATUS", "ONE_STEP_ALLOCATOR_STATUS",
        "GUARDED_MARGINAL_STATUS", "FORMAL_METHOD_RANKING", "NEXT_ALLOWED_STAGE",
    ]
    checks["all_final_terminal_fields_present"] = all(f"{field} =" in final_text for field in terminal_fields)
    checks["final_decision_respects_failed_gate"] = (
        "SELECTED_PROXY_STATUS = NOT_ESTABLISHED" in final_text
        and "ONE_STEP_ALLOCATOR_STATUS = BLOCKED" in final_text
        and "GUARDED_MARGINAL_STATUS = STOPPED" in final_text
    )
    manifest = json.loads((OUT / "artifact_hash_manifest.json").read_text())
    manifest_valid = True
    for relative, metadata in manifest["artifacts"].items():
        path = OUT / relative
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"] or path.stat().st_size != metadata["bytes"]:
            manifest_valid = False
            break
    checks["artifact_manifest_hashes_validate"] = manifest_valid
    checks = {key: bool(value) for key, value in checks.items()}
    status = "PASS" if all(checks.values()) else "FAIL"
    result = {"status": status, "check_count": len(checks), "checks": checks}
    if args.write:
        path = OUT / "reports/INDEPENDENT_RESULT_AUDIT.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
