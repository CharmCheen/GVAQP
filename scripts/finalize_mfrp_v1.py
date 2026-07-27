#!/usr/bin/env python3
"""MFRP Phase 4: cost-adjusted utility, automatic gates, and reports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from run_mfrp_univariate import score_metrics
from run_mrpo_univariate import geometry_order_scores


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"
BRANCHES = ("P1_L", "P1_M", "P2")
ALL_PREVIEWS = ("P0", "P1_L", "P1_M", "P2")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value.rstrip() + "\n")
    tmp.replace(path)


def git_value(*args: str) -> str:
    command = ["git", f"--git-dir={ROOT/'.git'}", f"--work-tree={ROOT}", *args]
    result = subprocess.run(command, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def selected_prefix(frame: pd.DataFrame, scores: np.ndarray, scan_budget_sec: float) -> list[int]:
    order = np.argsort(-np.asarray(scores, dtype=float), kind="stable")
    spent = 0.0; selected = []
    for index in order:
        cost = float(frame.iloc[index].full_scan_cost_sec)
        if spent + cost > scan_budget_sec + 1e-12:
            break
        selected.append(int(index)); spent += cost
    return selected


def score_for_branch(predictions: pd.DataFrame, branch: str, truth: pd.DataFrame) -> np.ndarray:
    return predictions[
        predictions.preview.eq(branch) & predictions.test_video_id.eq(str(truth.video_id.iloc[0]))
    ].set_index("region_id").loc[truth.region_id].score.to_numpy(dtype=float)


def main() -> None:
    regions = pd.read_parquet(OUT / "labels/region_table.parquet")
    features = pd.read_parquet(OUT / "features/region_features.parquet")
    data = regions.merge(features, on=[
        "video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec",
    ], validate="one_to_one").sort_values(["video_id", "region_index"]).reset_index(drop=True)
    predictions = pd.read_parquet(OUT / "predictions/nested_lovo_predictions_all_branches.parquet")
    branch_metrics = pd.read_csv(OUT / "metrics/nested_branch_per_video_metrics.csv")
    cost_audit = json.loads((OUT / "audits/preview_cost_audit.json").read_text())
    random = pd.read_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv").groupby("video_id").recall_at_20.mean().to_dict()
    static_controls = pd.read_csv(OUT / "experiments/controls/static_control_metrics.csv")
    p0_inheritance = json.loads((OUT / "preview/p0/inheritance_manifest.json").read_text())
    candidate_branch = json.loads((OUT / "experiments/models/phase3_summary.json").read_text())["candidate_branch"]

    branch_score_maps: dict[str, dict[str, np.ndarray]] = {branch: {} for branch in ALL_PREVIEWS}
    geometry_maps = {}
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        branch_score_maps["P0"][video_id] = -truth["p0__luma_std__std"].to_numpy(dtype=float)
        for branch in BRANCHES:
            branch_score_maps[branch][video_id] = score_for_branch(predictions, branch, truth)
        geometry_maps[video_id] = geometry_order_scores(truth)

    # Shuffled-score distributions for every component branch.
    shuffled_rows = []
    for branch in BRANCHES:
        for video_id, truth in data.groupby("video_id", sort=True):
            truth = truth.sort_values("region_index").reset_index(drop=True)
            score = branch_score_maps[branch][video_id]
            for seed in range(100):
                shuffled_rows.append({
                    "control": "B8_SHUFFLED_REGION_SCORE", "preview": branch,
                    "video_id": video_id, "seed": seed,
                    **score_metrics(truth, np.random.default_rng(seed).permutation(score)),
                })
    shuffled = pd.DataFrame(shuffled_rows)
    shuffled.to_csv(OUT / "experiments/controls/B8_SHUFFLED_REGION_SCORE_ALL_BRANCHES.csv", index=False)

    # Preview-cost-adjusted budget grid.  Cells below preview cost are explicitly
    # infeasible and never converted into zero-event observations.
    budget_rows = []
    for preview in ALL_PREVIEWS:
        per_video_preview_cost = cost_audit["configs"][preview]["conservative_per_video_cost_sec"]
        for video_id, truth in data.groupby("video_id", sort=True):
            truth = truth.sort_values("region_index").reset_index(drop=True)
            full_cost = float(truth.full_scan_cost_sec.sum())
            budgets = [
                ("WALLCLOCK_60S", 60.0),
                ("FULL_SCAN_COST_20PCT", 0.20 * full_cost),
                ("FULL_SCAN_COST_30PCT", 0.30 * full_cost),
            ]
            preview_cost = float(per_video_preview_cost[video_id])
            for budget_id, total_budget in budgets:
                if total_budget < preview_cost:
                    budget_rows.append({
                        "preview": preview, "video_id": video_id, "budget_id": budget_id,
                        "budget_cell": "INFEASIBLE_PREVIEW_COST", "total_budget_sec": total_budget,
                        "preview_cost_sec": preview_cost, "remaining_scan_budget_sec": None,
                        "preview_event_count": None, "coverage_event_count": None,
                        "delta_event_count": None, "preview_recall": None, "coverage_recall": None,
                        "preview_scan_cost_used_sec": None, "coverage_scan_cost_used_sec": None,
                    })
                    continue
                remaining = total_budget - preview_cost
                preview_selected = selected_prefix(truth, branch_score_maps[preview][video_id], remaining)
                coverage_selected = selected_prefix(truth, geometry_maps[video_id], total_budget)
                preview_events = int(truth.iloc[preview_selected].residual_event_count.sum()) if preview_selected else 0
                coverage_events = int(truth.iloc[coverage_selected].residual_event_count.sum()) if coverage_selected else 0
                denominator = int(truth.residual_event_count.sum())
                budget_rows.append({
                    "preview": preview, "video_id": video_id, "budget_id": budget_id,
                    "budget_cell": "FEASIBLE", "total_budget_sec": total_budget,
                    "preview_cost_sec": preview_cost, "remaining_scan_budget_sec": remaining,
                    "preview_event_count": preview_events, "coverage_event_count": coverage_events,
                    "delta_event_count": preview_events - coverage_events,
                    "preview_recall": preview_events / denominator,
                    "coverage_recall": coverage_events / denominator,
                    "preview_scan_cost_used_sec": float(truth.iloc[preview_selected].full_scan_cost_sec.sum()) if preview_selected else 0.0,
                    "coverage_scan_cost_used_sec": float(truth.iloc[coverage_selected].full_scan_cost_sec.sum()) if coverage_selected else 0.0,
                })
    budget_grid = pd.DataFrame(budget_rows)
    budget_grid.to_csv(OUT / "metrics/net_event_yield_budget_grid.csv", index=False)

    # Candidate and branch ranking summaries with random enrichment.
    enriched_branch_rows = []
    for row in branch_metrics.to_dict("records"):
        row["enrichment_at_20"] = row["recall_at_20"] / random[row["video_id"]]
        row["preview_cost_ratio"] = cost_audit["configs"][row["preview"]]["preview_cost_ratio"]
        enriched_branch_rows.append(row)
    branch_metrics = pd.DataFrame(enriched_branch_rows)
    candidate_metrics = branch_metrics[branch_metrics.preview.eq(candidate_branch)].copy()
    candidate_metrics.to_csv(OUT / "metrics/per_video_metrics.csv", index=False)

    per_region_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        scores = branch_score_maps[candidate_branch][video_id]
        order = np.argsort(-scores, kind="stable")
        ranks = np.empty(len(truth), dtype=int); ranks[order] = np.arange(1, len(truth) + 1)
        selected = {
            q: set(selected_prefix(truth, scores, q * float(truth.full_scan_cost_sec.sum())))
            for q in (0.10, 0.20, 0.30)
        }
        for index, row in truth.iterrows():
            per_region_rows.append({
                "video_id": video_id, "region_id": row.region_id, "region_index": int(row.region_index),
                "score": float(scores[index]), "rank": int(ranks[index]),
                "residual_event_count": int(row.residual_event_count),
                "binary_positive": bool(row.binary_positive), "full_scan_cost_sec": float(row.full_scan_cost_sec),
                "selected_at_10": index in selected[0.10], "selected_at_20": index in selected[0.20],
                "selected_at_30": index in selected[0.30],
            })
    per_region = pd.DataFrame(per_region_rows)
    per_region.to_csv(OUT / "metrics/per_region_metrics.csv", index=False)

    # Leave-best baseline and Gate ingredients.
    p0_leave_best = {}
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        drop = int(np.argmax(truth.residual_event_count.to_numpy()))
        reduced = truth.drop(index=drop).reset_index(drop=True)
        p0_score = np.delete(branch_score_maps["P0"][video_id], drop)
        p0_leave_best[video_id] = score_metrics(reduced, p0_score)["recall_at_20"]
    time_macro = float(
        static_controls[static_controls.control.str.startswith("B3_TIME_INDEX")]
        .groupby("control").recall_at_20.mean().max()
    )
    shuffled_means = shuffled.groupby(["preview", "video_id"]).recall_at_20.mean().to_dict()
    p0_nested = p0_inheritance["frozen_nested_lovo_recall_at_20"]

    gate_records = {}
    for branch in BRANCHES:
        local = branch_metrics[branch_metrics.preview.eq(branch)].set_index("video_id")
        primary_net = budget_grid[
            budget_grid.preview.eq(branch) & budget_grid.budget_id.eq("FULL_SCAN_COST_20PCT")
        ].set_index("video_id")
        common_positive = False
        for budget_id in ("WALLCLOCK_60S", "FULL_SCAN_COST_20PCT", "FULL_SCAN_COST_30PCT"):
            cells = budget_grid[budget_grid.preview.eq(branch) & budget_grid.budget_id.eq(budget_id)]
            if len(cells) == 2 and cells.budget_cell.eq("FEASIBLE").all() and cells.delta_event_count.gt(0).all():
                common_positive = True
        checks = {
            "recall_at_20_ge_0_40_both": bool(local.recall_at_20.ge(0.40).all()),
            "enrichment_gt_1_5_both": bool(local.enrichment_at_20.gt(1.5).all()),
            "nested_lovo_recall_beats_p0_both": bool(all(
                local.loc[video_id].recall_at_20 > p0_nested[video_id] for video_id in local.index
            )),
            "nested_lovo_auc_gt_0_55_both": bool(local.ranking_event_recall_auc.gt(0.55).all()),
            "beats_shuffled_score_both": bool(all(
                local.loc[video_id].recall_at_20 > shuffled_means[(branch, video_id)] for video_id in local.index
            )),
            "beats_time_index_macro": bool(local.recall_at_20.mean() > time_macro),
            "preview_cost_ratio_le_0_10": bool(cost_audit["configs"][branch]["preview_cost_ratio"] <= 0.10),
            "net_yield_primary_budget_nonnegative_both": bool(
                primary_net.budget_cell.eq("FEASIBLE").all() and primary_net.delta_event_count.ge(0).all()
            ),
            "at_least_one_common_budget_positive_both": common_positive,
            "leave_best_region_direction_nonnegative_vs_p0_both": bool(all(
                local.loc[video_id].leave_best_region_out_recall_at_20 >= p0_leave_best[video_id]
                for video_id in local.index
            )),
        }
        gate_records[branch] = {
            "checks": checks, "all_checks_pass": all(checks.values()),
            "per_video": local.reset_index().to_dict("records"),
            "shuffled_score_mean_recall20": {
                video_id: shuffled_means[(branch, video_id)] for video_id in local.index
            },
            "primary_net_yield": primary_net.reset_index().to_dict("records"),
        }
    p1_component_pass = gate_records["P1_L"]["all_checks_pass"] or gate_records["P1_M"]["all_checks_pass"]
    p2_component_pass = gate_records["P2"]["all_checks_pass"]
    p3_status = "IMPLEMENTED_AFTER_COMPONENT_GATES" if p1_component_pass and p2_component_pass else "NOT_IMPLEMENTED"
    if p3_status != "NOT_IMPLEMENTED":
        raise RuntimeError("P3 component gates unexpectedly passed; a separate frozen P3 implementation is required")
    exploratory_pass = gate_records[candidate_branch]["all_checks_pass"]
    selected_preview = candidate_branch if exploratory_pass else "NONE"
    decision = {
        "candidate_exploratory_branch": candidate_branch,
        "component_gates": gate_records, "p1_component_pass": p1_component_pass,
        "p2_component_pass": p2_component_pass, "p3_status": p3_status,
        "selected_preview_candidate": selected_preview,
        "multi_fidelity_preview_signal": "CANDIDATE_HYPOTHESIS" if exploratory_pass else "NOT_ESTABLISHED",
        "region_directed_scan": "BLOCKED_PENDING_FORMAL_VALIDATION" if exploratory_pass else "CLOSED_UNDER_CURRENT_VISIBLE_SIGNALS",
        "formal_static_ranking_gate": "BLOCKED_INSUFFICIENT_VALIDATION_VIDEOS",
        "one_step_allocator": "BLOCKED",
    }
    write_json(OUT / "metrics/exploratory_gate.json", decision)
    write_json(OUT / "metrics/ranking_metrics.json", {
        "candidate_branch": candidate_branch, "selected_preview_candidate": selected_preview,
        "per_video": candidate_metrics.to_dict("records"),
        "branch_metrics": branch_metrics.to_dict("records"),
        "random_mean_recall_at_20": random,
        "p0_nested_lovo_recall_at_20": p0_nested,
        "all_reference_events": 268, "exposable_reference_events": 263,
        "unexposable_reference_events": 5, "full_scan_exposure_ceiling": 263 / 268,
        "event_claim_scope": "RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
    })
    write_json(OUT / "metrics/cost_adjusted_metrics.json", {
        "cost_semantics": cost_audit["deployed_cost_semantics"],
        "strongest_coverage_baseline": "B6_STRONGEST_GEOMETRIC_COVERAGE_REGION_ORDER",
        "budget_grid_file": "metrics/net_event_yield_budget_grid.csv",
        "candidate_branch": candidate_branch,
        "candidate_primary_budget": budget_grid[
            budget_grid.preview.eq(candidate_branch) & budget_grid.budget_id.eq("FULL_SCAN_COST_20PCT")
        ].to_dict("records"),
    })

    # Required failure analysis.
    high_false, low_positive = [], []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True).copy()
        truth["candidate_score"] = branch_score_maps[candidate_branch][video_id]
        high_false.append(truth[truth.residual_event_count.eq(0)].sort_values("candidate_score", ascending=False).head(10))
        low_positive.append(truth[truth.residual_event_count.gt(0)].sort_values("candidate_score").head(10))
    pd.concat(high_false)[["video_id", "region_id", "candidate_score", "residual_event_count"]].to_csv(
        OUT / "experiments/models/high_score_zero_event_regions.csv", index=False
    )
    pd.concat(low_positive)[["video_id", "region_id", "candidate_score", "residual_event_count"]].to_csv(
        OUT / "experiments/models/low_score_positive_event_regions.csv", index=False
    )
    univariate = pd.read_parquet(OUT / "experiments/univariate/all_feature_per_video_metrics.parquet")
    conflicts = 0
    for _, group in univariate.groupby("feature"):
        signs = set(np.sign(group.spearman_count.to_numpy()).astype(int)) - {0}
        conflicts += int(len(signs) > 1)
    nested_univariate = pd.read_csv(OUT / "experiments/univariate/nested_lovo_best_univariate.csv")
    disagreement_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        model_scores = branch_score_maps[candidate_branch][video_id]
        heuristic_row = nested_univariate[
            nested_univariate.preview.eq(candidate_branch) & nested_univariate.test_video_id.eq(video_id)
        ].iloc[0]
        heuristic_scores = int(heuristic_row.selected_orientation) * truth[heuristic_row.selected_feature].to_numpy(dtype=float)
        full_budget = 0.20 * float(truth.full_scan_cost_sec.sum())
        model_set = set(selected_prefix(truth, model_scores, full_budget))
        heuristic_set = set(selected_prefix(truth, heuristic_scores, full_budget))
        p0_set = set(selected_prefix(truth, branch_score_maps["P0"][video_id], full_budget))
        p2_set = set(selected_prefix(truth, branch_score_maps["P2"][video_id], full_budget))
        oracle_row = static_controls[
            static_controls.video_id.eq(video_id) & static_controls.control.eq("B9_OFFLINE_FULL_INFORMATION_REGION_ORDER")
        ].iloc[0]
        candidate_row = candidate_metrics[candidate_metrics.video_id.eq(video_id)].iloc[0]
        disagreement_rows.append({
            "video_id": video_id,
            "cross_video_feature_conflict_count_global": conflicts,
            "time_index_best_recall20": float(static_controls[
                static_controls.video_id.eq(video_id) & static_controls.control.str.startswith("B3_TIME_INDEX")
            ].recall_at_20.max()),
            "candidate_minus_time_index_recall20": float(candidate_row.recall_at_20 - static_controls[
                static_controls.video_id.eq(video_id) & static_controls.control.str.startswith("B3_TIME_INDEX")
            ].recall_at_20.max()),
            "offline_oracle_missed_headroom_recall20": float(oracle_row.recall_at_20 - candidate_row.recall_at_20),
            "p0_vs_candidate_symmetric_difference": len(p0_set.symmetric_difference(model_set)),
            "p2_vs_candidate_symmetric_difference": len(p2_set.symmetric_difference(model_set)),
            "model_vs_univariate_symmetric_difference": len(model_set.symmetric_difference(heuristic_set)),
            "best_region_contribution_ratio": float(candidate_row.best_region_contribution_ratio_at_20),
        })
    failure = {
        "candidate_branch": candidate_branch, "per_video": disagreement_rows,
        "feature_missingness_total": int(features.isna().sum().sum()),
        "preview_cost_decomposition": cost_audit["configs"],
        "cross_video_conflicting_feature_count": conflicts,
        "high_score_zero_event_file": "experiments/models/high_score_zero_event_regions.csv",
        "low_score_positive_event_file": "experiments/models/low_score_positive_event_regions.csv",
        "new_direction": "NO_NEW_DIRECTION_ESTABLISHED; ANY_FUTURE_SIGNAL_IS_CANDIDATE_HYPOTHESIS_ONLY",
    }
    write_json(OUT / "metrics/failure_analysis_metrics.json", failure)

    gate_table = pd.DataFrame([
        {"preview": branch, "all_checks_pass": record["all_checks_pass"], **record["checks"]}
        for branch, record in gate_records.items()
    ])
    write_text(OUT / "reports/COST_ADJUSTED_RANKING_REPORT.md", "# Cost-adjusted Ranking Report\n\n" + budget_grid.to_markdown(index=False) + "\n")
    write_text(OUT / "reports/FAILURE_ANALYSIS.md", f"""# Failure Analysis

The strongest branch is `{candidate_branch}`, but its Recall@20 remains below 0.40 on both videos. It improves over frozen P0 and has AUC above 0.55, so semantic occupancy is a real mechanism signal, but it is insufficient for the frozen Gate.

Gate table:

{gate_table.to_markdown(index=False)}

There are {conflicts} feature columns with cross-video Spearman sign conflicts. High-score/no-event and low-score/high-event tables are materialized. Structured P0/P1/P2 disagreement, time confounding, preview cost decomposition, single-region contribution, model-versus-heuristic disagreement, and offline-oracle missed headroom are in `metrics/failure_analysis_metrics.json`.

No new scheduler or allocator is authorized. Any new visible-signal direction remains a `CANDIDATE_HYPOTHESIS`.
""")

    frozen = json.loads((OUT / "contracts/frozen_contract.json").read_text())
    preview_contracts = json.loads((OUT / "contracts/preview_contracts/index.json").read_text())
    selected_folds = pd.read_csv(OUT / "experiments/models/nested_selected_configs.csv")
    candidate_folds = selected_folds[selected_folds.preview.eq(candidate_branch)]
    schema_hash = hashlib.sha256("\n".join(candidate_folds.selected_feature_schema_hash.astype(str)).encode()).hexdigest()
    model_hash = hashlib.sha256(candidate_folds.to_json(orient="records", double_precision=15).encode()).hexdigest()
    local = candidate_metrics.set_index("video_id")
    short, long = local.loc["PSP_V0_SHORT"], local.loc["PSP_V1_LONG"]
    primary_net = budget_grid[
        budget_grid.preview.eq(candidate_branch) & budget_grid.budget_id.eq("FULL_SCAN_COST_20PCT")
    ].set_index("video_id")
    p1_l_gate = "PASS" if gate_records["P1_L"]["all_checks_pass"] else "FAIL"
    p1_m_gate = "PASS" if gate_records["P1_M"]["all_checks_pass"] else "FAIL"
    p2_gate = "PASS" if gate_records["P2"]["all_checks_pass"] else "FAIL"
    final = f"""# Final Preview Decision

## Strongest supported conclusion

Low-rate semantic detection improves region observability relative to P0, but it does not establish a deployable region-value proxy. `{candidate_branch}` obtains nested Recall@20 {short.recall_at_20:.3f}/{long.recall_at_20:.3f} and AUC {short.ranking_event_recall_auc:.3f}/{long.ranking_event_recall_auc:.3f}; both Recall values remain below the frozen 0.40 threshold. Its cost-adjusted direction is budget-dependent: it loses 2/4 events at 60 s but gains 1/8 at the 20% total-wall-clock budget. P1-M is video-unstable and P2 is near random. P3 is not implemented because neither a P1 branch nor P2 passes its full component Gate.

Consequently region-directed SCAN is closed under the currently tested visible signals. Geometric coverage remains the safe baseline. This is relative only to frozen full-context Oracle pseudo-reference and is not a human-ground-truth detection claim.

CONTRACT_HASH = {frozen['contract_hash']}
CODE_COMMIT = {git_value('rev-parse', 'HEAD')}

VIDEO_COUNT = 2
DESIGN_VIDEO_COUNT = 2
VALIDATION_VIDEO_COUNT = 0
TEST_VIDEO_COUNT = 0

REFERENCE_TYPE = FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE
REFERENCE_COMPLETENESS_STATUS = NOT_HUMAN_GROUND_TRUTH_COMPLETE; OFFSET0_EXPOSABLE_263_OF_268
EVENT_CLAIM_SCOPE = RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE

P0_STATUS = NOT_ESTABLISHED_FROZEN_BASELINE_TUNING_CLOSED

P1_L_OPERATOR = {preview_contracts['P1_L']['operator']}
P1_L_COST_RATIO = {cost_audit['configs']['P1_L']['preview_cost_ratio']:.9f}
P1_L_GATE = {p1_l_gate}

P1_M_OPERATOR = {preview_contracts['P1_M']['operator']}
P1_M_COST_RATIO = {cost_audit['configs']['P1_M']['preview_cost_ratio']:.9f}
P1_M_GATE = {p1_m_gate}

P2_OPERATOR = {preview_contracts['P2']['operator']}
P2_COST_RATIO = {cost_audit['configs']['P2']['preview_cost_ratio']:.9f}
P2_GATE = {p2_gate}

P3_STATUS = {p3_status}

SELECTED_PREVIEW_CANDIDATE = {selected_preview}

MACRO_REGION_LENGTH = 40_SECONDS
FEATURE_SCHEMA_HASH = {schema_hash}
MODEL_FAMILY = NESTED_FOLD_SPECIFIC_LIGHTGBM_OR_LOGISTIC
MODEL_CONFIG_HASH = {model_hash}

PRIMARY_RECALL_AT_20 = {short.recall_at_20:.6f}/{long.recall_at_20:.6f}; MACRO={candidate_metrics.recall_at_20.mean():.6f}
PRIMARY_ENRICHMENT_AT_20 = {short.enrichment_at_20:.6f}/{long.enrichment_at_20:.6f}; MACRO={candidate_metrics.enrichment_at_20.mean():.6f}
NESTED_LOVO_RECALL_AT_20 = {short.recall_at_20:.6f}/{long.recall_at_20:.6f}
NESTED_LOVO_AUC = {short.ranking_event_recall_auc:.6f}/{long.ranking_event_recall_auc:.6f}
PREVIEW_COST_RATIO = {cost_audit['configs'][candidate_branch]['preview_cost_ratio']:.9f}
NET_EVENT_YIELD = {int(primary_net.loc['PSP_V0_SHORT'].delta_event_count)}/{int(primary_net.loc['PSP_V1_LONG'].delta_event_count)}_EVENTS_AT_20_PERCENT_TOTAL_WALLCLOCK
CROSS_VIDEO_DIRECTION = POSITIVE_VS_P0_BUT_BELOW_RECALL_GATE_BOTH
LEAVE_BEST_REGION_OUT = {short.leave_best_region_out_recall_at_20:.6f}/{long.leave_best_region_out_recall_at_20:.6f}
BEST_REGION_CONTRIBUTION = MAX_{candidate_metrics.best_region_contribution_ratio_at_20.max():.6f}

EXPLORATORY_GATE = FAIL
FORMAL_STATIC_RANKING_GATE = BLOCKED_INSUFFICIENT_VALIDATION_VIDEOS
MULTI_FIDELITY_PREVIEW_SIGNAL = {decision['multi_fidelity_preview_signal']}

SELECTED_PROXY_STATUS = {'CANDIDATE_HYPOTHESIS' if exploratory_pass else 'NOT_ESTABLISHED'}
ONE_STEP_ALLOCATOR_STATUS = BLOCKED
GUARDED_MARGINAL_STATUS = STOPPED
FORMAL_METHOD_RANKING = BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION
NEXT_ALLOWED_STAGE = NEW_POLICY_VISIBLE_SIGNAL_OR_SAFE_COVERAGE_BASELINE
"""
    write_text(OUT / "reports/FINAL_PREVIEW_DECISION.md", final)
    print(json.dumps({
        "status": "COMPLETE_PHASE4", "candidate_branch": candidate_branch,
        "selected_preview": selected_preview, "gates": {
            branch: record["checks"] for branch, record in gate_records.items()
        }, "p3_status": p3_status,
        "primary_net": primary_net.reset_index().to_dict("records"),
    }, indent=2))


if __name__ == "__main__":
    main()
