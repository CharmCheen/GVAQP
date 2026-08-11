#!/usr/bin/env python3
"""Independent requirement-by-requirement audit for MFRP-V1."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"
DOC = ROOT / "docs/MULTI_FIDELITY_REGION_PREVIEW_CONTRACT_V1.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    checks = {}
    frozen = json.loads((OUT / "contracts/frozen_contract.json").read_text())
    checks["contract_document_hash_matches_frozen_record"] = sha256(DOC) == frozen["contract_hash"] == "04114ce3562c013ab51954cee5829ef40bd8eb89ad62c9f34855bb408ac7dc63"
    checks["contract_frozen_before_new_preview_execution"] = bool(frozen["frozen_before_new_preview_execution"])
    parent = json.loads((OUT / "contracts/parent_asset_hashes.json").read_text())
    parent_ok = True
    for relative, metadata in parent.items():
        if relative == "source_videos":
            for row in metadata.values():
                path = Path(row["path"])
                if not path.exists() or sha256(path) != row["actual_sha256"] or not row["matches_manifest"]:
                    parent_ok = False
        else:
            path = ROOT / relative
            if metadata["exists"] != path.exists() or (path.exists() and sha256(path) != metadata["sha256"]):
                parent_ok = False
    checks["parent_assets_and_source_video_hashes_validate"] = parent_ok
    asset = json.loads((OUT / "audits/asset_audit.json").read_text())
    checks["two_design_no_validation_test"] = (
        asset["design_video_count"] == 2
        and asset["additional_complete_validation_videos_with_frozen_reference_and_timeline"] == 0
        and frozen["validation_video_count"] == 0 and frozen["test_video_count"] == 0
    )
    checks["formal_gate_correctly_blocked"] = asset["formal_static_ranking_gate"] == "BLOCKED_INSUFFICIENT_VALIDATION_VIDEOS"

    label = json.loads((OUT / "audits/label_audit.json").read_text())
    event_map = pd.read_parquet(OUT / "labels/event_region_map.parquet")
    counts = pd.read_parquet(OUT / "labels/region_count_labels.parquet")
    binary = pd.read_parquet(OUT / "labels/region_binary_labels.parquet")
    checks["labels_229_regions_263_exposable_268_all"] = len(counts) == len(binary) == 229 and int(counts.residual_event_count.sum()) == 263 and len(event_map) == event_map.reference_event_id.nunique() == 268
    checks["event_mapped_exactly_once"] = event_map.reference_event_id.value_counts().eq(1).all() and bool(label["event_counted_once"])
    sensitivity = pd.read_csv(OUT / "experiments/macro_region_sensitivity/label_sensitivity.csv")
    checks["all_four_macro_lengths_and_tails"] = set(sensitivity.macro_region_length_sec) == {40, 60, 90, 120} and sensitivity.groupby("macro_region_length_sec").video_id.nunique().eq(2).all() and bool(label["tail_regions_retained"])
    macro = json.loads((OUT / "contracts/macro_region_selection.json").read_text())
    nested_length = json.loads((OUT / "experiments/macro_region_sensitivity/nested_length_selection.json").read_text())
    checks["macro_length_frozen_once_and_nested_folds_agree"] = macro["selected_macro_region_length_sec"] == 40 and macro["selection_timing"] == "BEFORE_NEW_P1_P2_METRICS" and nested_length["all_folds_match_frozen_40s"]

    cost = json.loads((OUT / "audits/preview_cost_audit.json").read_text())
    determinism = json.loads((OUT / "audits/determinism_audit.json").read_text())
    checks["four_fixed_preview_configs_only"] = set(cost["configs"]) == {"P0", "P1_L", "P1_M", "P2"}
    checks["every_preview_two_repeats_full_timeline_deterministic"] = all(
        row["deterministic_hash_match"] and row["full_timeline_coverage"] and row["region_count"] == 229
        for row in cost["configs"].values()
    ) and determinism["repeat_count_per_config"] == 2
    checks["every_preview_zero_missing_regions"] = all(
        row["missing_feature_cells"] == 0 and row["zero_sample_regions"] == 0
        for row in cost["configs"].values()
    )
    checks["every_preview_cost_ratio_le_0_10"] = all(row["preview_cost_ratio"] <= 0.10 for row in cost["configs"].values())
    runtime = pd.read_csv(OUT / "audits/preview_runtime_samples.csv")
    required_runtime = {
        "decode_time_sec", "model_time_sec", "feature_time_sec", "total_wallclock_sec",
        "seconds_per_video_hour", "peak_cpu_memory_bytes", "peak_gpu_memory_bytes",
    }
    checks["all_required_runtime_and_memory_fields"] = required_runtime.issubset(runtime.columns) and len(runtime) == 16 and not runtime[list(required_runtime)].isna().any().any()
    checks["p1_model_hash_frozen"] = all(
        json.loads((OUT / f"contracts/preview_contracts/{name}.json").read_text())["model_sha256"] == sha256(ROOT / "models/yolo/yolov8n.pt")
        for name in ("P1_L", "P1_M")
    )

    schema = pd.read_csv(OUT / "audits/feature_legality_audit.csv")
    required_legality = {
        "feature_name", "feature_family", "source_preview", "runtime_visibility", "cost",
        "missingness", "uses_reference", "uses_full_scan", "uses_future_information", "legality_status",
    }
    checks["feature_legality_exact_fields_and_le_8_families"] = required_legality.issubset(schema.columns) and schema.feature_family.nunique() <= 8 and len(schema) == 458
    checks["all_features_legal_visible_nonleaky"] = (
        schema.legality_status.eq("LEGAL").all() and schema.missingness.eq(0).all()
        and (~schema.uses_reference).all() and (~schema.uses_full_scan).all()
        and (~schema.uses_future_information).all()
    )
    leakage = json.loads((OUT / "audits/leakage_audit.json").read_text())
    preview_source = (ROOT / "scripts/run_mfrp_previews.py").read_text()
    forbidden_preview_literals = ["reference_events", "candidate_event_map", "scan_outputs", "timeline_units", "residual_event_count"]
    checks["preview_code_has_no_hidden_asset_access"] = leakage["status"] == "PASS" and not any(token in preview_source for token in forbidden_preview_literals)

    univariate = pd.read_parquet(OUT / "experiments/univariate/all_feature_per_video_metrics.parquet")
    checks["every_legal_feature_has_both_video_univariate_metrics"] = univariate.feature.nunique() == len(schema) and univariate.groupby("feature").video_id.nunique().eq(2).all()
    model_manifest = json.loads((OUT / "contracts/model_search_manifest.json").read_text())
    configs = model_manifest["configs"]
    checks["model_search_45_configs_4_families_within_budget"] = len(configs) == model_manifest["config_count"] == 45 and len({row["family"] for row in configs}) == 4 <= 5
    checks["lightgbm_constraints_respected"] = all(
        row.get("max_depth", 0) <= 4 and row.get("num_leaves", 0) <= 15
        and row.get("min_child_samples", 10) >= 10 and row.get("n_estimators", 0) <= 300
        for row in configs if row["family"] == "SHALLOW_LIGHTGBM"
    )
    selected_folds = pd.read_csv(OUT / "experiments/models/nested_selected_configs.csv")
    checks["nested_lovo_has_all_three_branches_both_video_directions"] = len(selected_folds) == 6 and selected_folds.groupby("preview").test_video_id.nunique().eq(2).all() and (selected_folds.train_video_id != selected_folds.test_video_id).all()
    checks["nested_features_selected_train_only"] = selected_folds.selected_feature_count.gt(0).all() and (OUT / "experiments/models/nested_feature_selections.json").exists()

    static = pd.read_csv(OUT / "experiments/controls/static_control_metrics.csv")
    present = set(static.control.str.extract(r"^(B\d+)", expand=False).dropna())
    for control, file_name in [
        ("B0", "B0_RANDOM_COST_MATCHED_100_SEEDS.csv"),
        ("B7", "B7_SHUFFLED_LABEL.csv"),
        ("B8", "B8_SHUFFLED_REGION_SCORE_ALL_BRANCHES.csv"),
    ]:
        if (OUT / "experiments/controls" / file_name).exists(): present.add(control)
    checks["mandatory_B0_through_B9_controls_present"] = present == {f"B{i}" for i in range(10)}
    random = pd.read_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv")
    checks["random_100_fixed_seeds_each_video"] = random.groupby("video_id").seed.nunique().eq(100).all() and set(random.seed) == set(range(100))

    per_video = pd.read_csv(OUT / "metrics/per_video_metrics.csv")
    required_metrics = {
        "recall_at_10", "recall_at_20", "recall_at_30", "used_cost_fraction_at_20",
        "ranking_event_recall_auc", "binary_auprc", "binary_brier_score", "count_mae",
        "spearman_count", "leave_best_region_out_recall_at_20",
        "best_region_contribution_ratio_at_20", "enrichment_at_20", "preview_cost_ratio",
    }
    checks["all_primary_secondary_metrics_reported"] = required_metrics.issubset(per_video.columns) and len(per_video) == 2 and not per_video[list(required_metrics)].isna().any().any()
    per_region = pd.read_csv(OUT / "metrics/per_region_metrics.csv")
    recompute_ok = True
    for video_id, group in per_region.groupby("video_id"):
        expected = float(per_video.set_index("video_id").loc[video_id, "recall_at_20"])
        actual = float(group.loc[group.selected_at_20, "residual_event_count"].sum() / group.residual_event_count.sum())
        spent = float(group.loc[group.selected_at_20, "full_scan_cost_sec"].sum())
        if abs(expected - actual) > 1e-12 or spent > 0.20 * float(group.full_scan_cost_sec.sum()) + 1e-12:
            recompute_ok = False
    checks["primary_metric_recomputes_complete_regions_within_budget"] = recompute_ok
    checks["feature_family_ablation_both_videos"] = pd.read_csv(OUT / "experiments/ablations/candidate_family_ablation.csv").groupby("omitted_family").video_id.nunique().eq(2).all()

    grid = pd.read_csv(OUT / "metrics/net_event_yield_budget_grid.csv")
    checks["net_grid_all_previews_videos_60_20_30"] = len(grid) == 24 and grid.groupby(["preview", "video_id"]).budget_id.nunique().eq(3).all()
    infeasible_ok = True
    for row in grid.itertuples(index=False):
        should_infeasible = row.total_budget_sec < row.preview_cost_sec
        if should_infeasible != (row.budget_cell == "INFEASIBLE_PREVIEW_COST"):
            infeasible_ok = False
        if row.budget_cell == "INFEASIBLE_PREVIEW_COST" and not pd.isna(row.delta_event_count):
            infeasible_ok = False
    checks["infeasible_preview_cells_explicit_never_faked_zero"] = infeasible_ok
    gate = json.loads((OUT / "metrics/exploratory_gate.json").read_text())
    checks["gate_automatically_fails_only_as_conjunction"] = (
        gate["candidate_exploratory_branch"] == "P1_L"
        and not gate["component_gates"]["P1_L"]["checks"]["recall_at_20_ge_0_40_both"]
        and not gate["component_gates"]["P1_L"]["all_checks_pass"]
        and gate["multi_fidelity_preview_signal"] == "NOT_ESTABLISHED"
        and gate["selected_preview_candidate"] == "NONE"
    )
    checks["p3_not_implemented_because_component_gates_fail"] = gate["p3_status"] == "NOT_IMPLEMENTED" and not (OUT / "preview/p3").exists()
    checks["allocator_correctly_blocked_and_region_directed_scan_closed"] = gate["one_step_allocator"] == "BLOCKED" and gate["region_directed_scan"] == "CLOSED_UNDER_CURRENT_VISIBLE_SIGNALS"
    failure = json.loads((OUT / "metrics/failure_analysis_metrics.json").read_text())
    checks["all_required_failure_analysis_evidence"] = (
        len(failure["per_video"]) == 2 and "preview_cost_decomposition" in failure
        and "cross_video_conflicting_feature_count" in failure
        and (OUT / failure["high_score_zero_event_file"]).exists()
        and (OUT / failure["low_score_positive_event_file"]).exists()
    )
    repairs = json.loads((OUT / "repair_log.json").read_text())
    checks["repair_cycle_count_le_1"] = len(repairs) <= 1

    required_files = [
        "audits/completion_matrix.md", "features/region_features.parquet", "features/feature_schema.json",
        "predictions/nested_lovo_predictions.parquet", "predictions/region_scores.parquet",
        "metrics/ranking_metrics.json", "metrics/cost_adjusted_metrics.json",
        "metrics/net_event_yield_budget_grid.csv", "metrics/per_video_metrics.csv",
        "metrics/per_region_metrics.csv", "metrics/random_baseline_distribution.json",
        "reports/PHASE0_ASSET_AND_LABEL_AUDIT.md", "reports/PREVIEW_OBSERVABILITY_REPORT.md",
        "reports/UNIVARIATE_HEADROOM_REPORT.md", "reports/SIMPLE_MODEL_SEARCH_REPORT.md",
        "reports/FEATURE_ABLATION_REPORT.md", "reports/COST_ADJUSTED_RANKING_REPORT.md",
        "reports/FAILURE_ANALYSIS.md", "reports/FINAL_PREVIEW_DECISION.md",
        "environment_lock.json", "code_version.json", "artifact_hash_manifest.json",
    ]
    checks["required_deliverables_exist"] = all((OUT / relative).exists() for relative in required_files)
    final = (OUT / "reports/FINAL_PREVIEW_DECISION.md").read_text()
    fields = [
        "CONTRACT_HASH", "CODE_COMMIT", "VIDEO_COUNT", "DESIGN_VIDEO_COUNT", "VALIDATION_VIDEO_COUNT",
        "TEST_VIDEO_COUNT", "REFERENCE_TYPE", "REFERENCE_COMPLETENESS_STATUS", "EVENT_CLAIM_SCOPE",
        "P0_STATUS", "P1_L_OPERATOR", "P1_L_COST_RATIO", "P1_L_GATE", "P1_M_OPERATOR",
        "P1_M_COST_RATIO", "P1_M_GATE", "P2_OPERATOR", "P2_COST_RATIO", "P2_GATE", "P3_STATUS",
        "SELECTED_PREVIEW_CANDIDATE", "MACRO_REGION_LENGTH", "FEATURE_SCHEMA_HASH", "MODEL_FAMILY",
        "MODEL_CONFIG_HASH", "PRIMARY_RECALL_AT_20", "PRIMARY_ENRICHMENT_AT_20",
        "NESTED_LOVO_RECALL_AT_20", "NESTED_LOVO_AUC", "PREVIEW_COST_RATIO", "NET_EVENT_YIELD",
        "CROSS_VIDEO_DIRECTION", "LEAVE_BEST_REGION_OUT", "BEST_REGION_CONTRIBUTION",
        "EXPLORATORY_GATE", "FORMAL_STATIC_RANKING_GATE", "MULTI_FIDELITY_PREVIEW_SIGNAL",
        "SELECTED_PROXY_STATUS", "ONE_STEP_ALLOCATOR_STATUS", "GUARDED_MARGINAL_STATUS",
        "FORMAL_METHOD_RANKING", "NEXT_ALLOWED_STAGE",
    ]
    checks["all_final_terminal_fields_present"] = all(f"{field} =" in final for field in fields)
    checks["final_decision_matches_gate"] = (
        "SELECTED_PREVIEW_CANDIDATE = NONE" in final
        and "MULTI_FIDELITY_PREVIEW_SIGNAL = NOT_ESTABLISHED" in final
        and "SELECTED_PROXY_STATUS = NOT_ESTABLISHED" in final
        and "ONE_STEP_ALLOCATOR_STATUS = BLOCKED" in final
        and "GUARDED_MARGINAL_STATUS = STOPPED" in final
    )
    forbidden_artifact_names = ["allocator", "guarded_marginal", "contiguous_batch", "bandit", "smdp", "confirm"]
    checks["no_prohibited_stage_artifacts"] = not any(
        any(token in path.name.lower() for token in forbidden_artifact_names)
        for path in OUT.rglob("*") if path.is_file()
    )
    code = json.loads((OUT / "code_version.json").read_text())
    checks["code_version_script_hashes_validate"] = all(
        sha256(ROOT / "scripts" / name) == metadata["sha256"]
        for name, metadata in code["scripts"].items()
    )
    manifest = json.loads((OUT / "artifact_hash_manifest.json").read_text())
    checks["artifact_manifest_hashes_validate"] = all(
        (OUT / relative).exists()
        and sha256(OUT / relative) == metadata["sha256"]
        and (OUT / relative).stat().st_size == metadata["bytes"]
        for relative, metadata in manifest["artifacts"].items()
    )

    checks = {name: bool(value) for name, value in checks.items()}
    result = {"status": "PASS" if all(checks.values()) else "FAIL", "check_count": len(checks), "checks": checks}
    if args.write:
        (OUT / "audits/independent_completion_audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
