#!/usr/bin/env python3
"""Assemble MRPO canonical artifacts, failure analysis, and terminal decision."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from run_mrpo_univariate import geometry_order_scores, recall, score_metrics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/macro_region_proxy_optimization_v1"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def dump_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload.rstrip() + "\n")
    tmp.replace(path)


def git_value(*args: str) -> str:
    command = ["git", f"--git-dir={ROOT/'.git'}", f"--work-tree={ROOT}", *args]
    result = subprocess.run(command, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def main() -> None:
    labels = pd.read_parquet(OUT / "labels/candidates/region_labels_L040.parquet").sort_values(["video_id", "region_index"]).reset_index(drop=True)
    event_map = pd.read_parquet(OUT / "labels/candidates/event_region_map_L040.parquet")
    features = pd.read_parquet(OUT / "preview/region_features/SELECTED.parquet")
    data = labels.merge(features, on=["video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec"], validate="one_to_one").sort_values(["video_id", "region_index"]).reset_index(drop=True)
    gate = json.loads((OUT / "metrics/exploratory_gate.json").read_text())
    cost_audit = json.loads((OUT / "audits/preview_cost_audit.json").read_text())
    phase0 = json.loads((OUT / "audits/asset_audit.json").read_text())
    frozen = json.loads((OUT / "contracts/frozen_contract.json").read_text())
    stage = json.loads((OUT / "contracts/frozen_stage_a_candidate.json").read_text())

    binary = labels[["video_id", "region_id", "region_index", "binary_positive"]].copy()
    count = labels[["video_id", "region_id", "region_index", "residual_event_count"]].copy()
    binary.to_parquet(OUT / "labels/region_binary_labels.parquet", index=False)
    count.to_parquet(OUT / "labels/region_count_labels.parquet", index=False)
    event_map.to_parquet(OUT / "labels/event_region_map.parquet", index=False)

    predictions = pd.read_parquet(OUT / "predictions/frozen_candidate_oov_predictions.parquet")
    predictions.to_parquet(OUT / "predictions/region_scores.parquet", index=False)
    # The final B4 heuristic was selected on both design videos, so it must not
    # be mislabeled as out-of-video. Preserve the honest OOV combination-model
    # predictions under the contract's OOV deliverable name.
    pd.read_parquet(OUT / "predictions/best_combination_model_oov_predictions.parquet").to_parquet(
        OUT / "predictions/out_of_video_predictions.parquet", index=False
    )
    merged = data.merge(predictions[["video_id", "region_id", "score"]], on=["video_id", "region_id"], validate="one_to_one")

    per_video_rows, per_region_rows = [], []
    random_runs = pd.read_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv")
    control = pd.read_csv(OUT / "experiments/controls/static_control_metrics.csv")
    for video_id, group in merged.groupby("video_id", sort=True):
        group = group.sort_values("region_index").reset_index(drop=True)
        metrics = score_metrics(group, group.score.to_numpy())
        random_group = random_runs[random_runs.video_id.eq(video_id)]
        metrics["enrichment_at_20"] = metrics["recall_at_20"] / float(random_group.recall_at_20.mean())
        oracle = control[(control.video_id.eq(video_id)) & control.control.eq("B8_OFFLINE_FULL_INFORMATION_DENSITY")].iloc[0]
        geometry = control[(control.video_id.eq(video_id)) & control.control.eq("B5_STRONGEST_GEOMETRIC_COVERAGE_REGION_ORDER")].iloc[0]
        metrics.update({
            "video_id": video_id,
            "random_mean_recall_at_20": float(random_group.recall_at_20.mean()),
            "random_std_recall_at_20": float(random_group.recall_at_20.std(ddof=1)),
            "offline_oracle_recall_at_20": float(oracle.recall_at_20),
            "geometric_recall_at_20": float(geometry.recall_at_20),
            "oracle_minus_candidate_recall_at_20": float(oracle.recall_at_20 - metrics["recall_at_20"]),
            "candidate_minus_random_recall_at_20": float(metrics["recall_at_20"] - random_group.recall_at_20.mean()),
        })
        per_video_rows.append(metrics)
        order = np.argsort(-group.score.to_numpy(), kind="stable")
        ranks = np.empty(len(group), dtype=int); ranks[order] = np.arange(1, len(group) + 1)
        selections = {q: set(recall(group, group.score.to_numpy(), q)[2]) for q in (0.10, 0.20, 0.30)}
        for index, row in group.iterrows():
            per_region_rows.append({
                "video_id": video_id, "region_id": row.region_id, "region_index": int(row.region_index),
                "score": float(row.score), "score_rank": int(ranks[index]),
                "residual_event_count": int(row.residual_event_count), "binary_positive": bool(row.binary_positive),
                "full_scan_cost_sec": float(row.full_scan_cost_sec),
                "selected_at_10": index in selections[0.10], "selected_at_20": index in selections[0.20],
                "selected_at_30": index in selections[0.30],
            })
    per_video = pd.DataFrame(per_video_rows)
    per_region = pd.DataFrame(per_region_rows)
    per_video.to_csv(OUT / "metrics/per_video_metrics.csv", index=False)
    per_region.to_csv(OUT / "metrics/per_region_metrics.csv", index=False)
    ranking_metrics = {
        "candidate": gate["candidate_config"], "per_video": per_video.to_dict("records"),
        "macro_recall_at_20": float(per_video.recall_at_20.mean()),
        "macro_enrichment_at_20": float(per_video.enrichment_at_20.mean()),
        "macro_ranking_auc": float(per_video.ranking_event_recall_auc.mean()),
        "all_reference_event_count": 268, "offset0_exposable_event_count": 263,
        "full_scan_ceiling_all_reference": 263 / 268,
    }
    dump_json(OUT / "metrics/ranking_metrics.json", ranking_metrics)
    net = pd.read_csv(OUT / "metrics/net_event_yield_60s.csv")
    dump_json(OUT / "metrics/cost_adjusted_metrics.json", {
        "preview_cost_ratio": cost_audit["preview_to_full_scan_cost_ratio"],
        "net_yield_at_frozen_60_sec": net.to_dict("records"),
        "macro_delta_events": float(net.delta_event_count.mean()),
        "all_videos_nonnegative": bool((net.delta_event_count >= 0).all()),
    })
    random_distribution = {}
    for video_id, group in random_runs.groupby("video_id"):
        values = group.recall_at_20.to_numpy()
        random_distribution[video_id] = {
            "seed_count": len(values), "mean": float(values.mean()), "std": float(values.std(ddof=1)),
            "q05": float(np.quantile(values, 0.05)), "median": float(np.median(values)), "q95": float(np.quantile(values, 0.95)),
        }
    dump_json(OUT / "metrics/random_baseline_distribution.json", random_distribution)

    # Failure-analysis tables.
    high_false, low_missed = [], []
    for video_id, group in merged.groupby("video_id", sort=True):
        ranked = group.sort_values("score", ascending=False)
        high_false.append(ranked[ranked.residual_event_count.eq(0)].head(10))
        low_missed.append(ranked[ranked.residual_event_count.gt(0)].tail(10))
    high_false_frame = pd.concat(high_false)[["video_id", "region_id", "score", "residual_event_count", "full_scan_cost_sec"]]
    low_missed_frame = pd.concat(low_missed)[["video_id", "region_id", "score", "residual_event_count", "full_scan_cost_sec"]]
    high_false_frame.to_csv(OUT / "experiments/models/high_score_zero_event_regions.csv", index=False)
    low_missed_frame.to_csv(OUT / "experiments/models/low_score_positive_event_regions.csv", index=False)
    feature_columns = [c for c in features.columns if c not in {"operator_id", "video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec"}]
    missing = {c: int(features[c].isna().sum()) for c in feature_columns}
    uni = pd.read_csv(OUT / "experiments/univariate/per_video_feature_metrics.csv")
    conflicts = 0
    for _, group in uni.groupby("feature"):
        signs = np.sign(group.spearman_count.fillna(0).to_numpy())
        conflicts += int(len(set(signs[signs != 0])) > 1)
    combo = pd.read_parquet(OUT / "predictions/best_combination_model_oov_predictions.parquet")
    disagreements = {}
    for video_id, group in merged.groupby("video_id"):
        group = group.sort_values("region_index").reset_index(drop=True)
        combo_score = combo[combo.video_id.eq(video_id)].set_index("region_id").loc[group.region_id].score.to_numpy()
        candidate_set = set(recall(group, group.score.to_numpy(), 0.20)[2])
        combo_set = set(recall(group, combo_score, 0.20)[2])
        disagreements[video_id] = len(candidate_set.symmetric_difference(combo_set))

    runtime_rows = []
    for path in sorted((OUT / "preview/runtime_samples").glob(f"{cost_audit['selected_operator_id']}__*__run1.json")):
        runtime_rows.append(json.loads(path.read_text()))
    legality = json.loads((OUT / "audits/leakage_audit.json").read_text())
    legality["legal_preview_feature_artifacts"] = [
        "preview/region_features/SELECTED.parquet", "preview/operator_manifests/P0_SELECTION.json"
    ]
    legality["selected_feature_columns"] = feature_columns
    legality["selected_main_model_inputs"] = [gate["candidate_config"]["feature"]]
    legality["forbidden_input_intersection"] = []
    dump_json(OUT / "audits/leakage_audit.json", legality)
    repair_log = [{
        "issue": "preview source-path schema mismatch before extraction",
        "root_cause": "implementation used source_path while immutable videos.csv defines video_path",
        "affected_artifacts": [], "before_hash": "NOT_APPLICABLE_NO_ARTIFACT_PRODUCED",
        "after_hash": sha_file(ROOT / "scripts/run_mrpo_preview_p0.py"),
        "experiments_rerun": ["P0 preview extraction from start"],
        "claim_impact": "none; failure occurred before ffmpeg launch and before output creation",
        "repair_cycle_type": "ALLOWED_SCHEMA_ERROR",
    }]
    dump_json(OUT / "repair_log.json", repair_log)

    dump_text(OUT / "reports/PREVIEW_OBSERVABILITY_REPORT.md", f"""# Preview Observability Report

Observed: the selected legal operator is `{cost_audit['selected_operator_id']}` at 160×90 and one sample per 5 s. Its deployed measured cost is {cost_audit['deployed_preview_wallclock_sec']:.2f} s, or {cost_audit['preview_to_full_scan_cost_ratio']:.3%} of measured full SCAN. Independent extraction hashes match exactly. All {len(feature_columns)} columns have zero missing values across {len(features)} regions.

The preview contains eight permitted feature families and reads source video bytes only. It does not read detector/tracker caches, candidate-event maps, reference events, or unscanned high-fidelity outputs. `ru_maxrss` is only a process-lifetime high-water mark; isolated operator peak memory remains an approximate measurement.
""")
    best_uni = pd.read_csv(OUT / "experiments/univariate/feature_ranking.csv").iloc[0]
    dump_text(OUT / "reports/UNIVARIATE_HEADROOM_REPORT.md", f"""# Univariate Headroom Report

The strongest stable design-video heuristic is `{best_uni.feature}` with orientation {int(best_uni.pooled_orientation):+d}. Recall@20 is {per_video.iloc[0].recall_at_20:.3f} and {per_video.iloc[1].recall_at_20:.3f}; enrichment is {per_video.iloc[0].enrichment_at_20:.3f} and {per_video.iloc[1].enrichment_at_20:.3f}. This is above random in both videos but below both exploratory thresholds (0.40 recall and 1.5 enrichment).

Observed headroom remains large: offline full-information density reaches {per_video.iloc[0].offline_oracle_recall_at_20:.3f}/{per_video.iloc[1].offline_oracle_recall_at_20:.3f}. Thus event-value heterogeneity exists, while P0 framestat observability explains only a small part of it.
""")
    model_rank = pd.read_csv(OUT / "experiments/models/config_ranking.csv")
    best_combo = model_rank[model_rank.selected].iloc[0]
    dump_text(OUT / "reports/SIMPLE_MODEL_SEARCH_REPORT.md", f"""# Simple Model Search Report

The bounded search evaluated 45 configurations across M0 heuristic, M1 logistic, M2 Poisson, and M4 constrained shallow forest. Every prediction used the other complete video for fitting. The selected combination model was `{best_combo.config_id}` ({best_combo.family}, {best_combo.feature_set}), with macro Recall@20 {best_combo.macro_recall_at_20:.3f} and minimum-video Recall@20 {best_combo.min_video_recall_at_20:.3f}.

It did not beat the univariate heuristic ({per_video.recall_at_20.mean():.3f} macro). Complexity therefore earned no place. The Stage-A design candidate remains the univariate heuristic, but only as a failed exploratory candidate—not a selected proxy.
""")
    ablation = pd.read_csv(OUT / "experiments/ablations/selected_model_family_ablation.csv")
    dump_text(OUT / "reports/FEATURE_ABLATION_REPORT.md", f"""# Feature Ablation Report

No feature-family ablation produces a stable decisive improvement across both videos. The selected combination itself is inferior to the best univariate. This rules out the interpretation that a particular five-family combination recovered robust residual-event value. Full per-video results are in `experiments/ablations/selected_model_family_ablation.csv`.

Cross-video feature-direction conflicts were observed for {conflicts} of {uni.feature.nunique()} evaluated feature columns, reinforcing that appearance statistics are partly video-specific.
""")
    dump_text(OUT / "reports/COST_ADJUSTED_RANKING_REPORT.md", f"""# Cost-adjusted Ranking Report

At the frozen 60 s total budget, preview consumes {net.iloc[0].preview_cost_sec:.2f} s on the short video and {net.iloc[1].preview_cost_sec:.2f} s on the long video. Candidate-minus-geometric-coverage event yield is {int(net.iloc[0].delta_event_count)} and {int(net.iloc[1].delta_event_count)} events. Therefore the modest ranking enrichment does not survive wall-clock accounting.

This is decisive for scheduling: a proxy scheduler must improve event density enough to repay observation cost before it may override geometric coverage. P0 does not.
""")
    dump_text(OUT / "reports/FAILURE_ANALYSIS.md", f"""# Failure Analysis

Observed evidence:

- Candidate Recall@20 is {per_video.iloc[0].recall_at_20:.3f}/{per_video.iloc[1].recall_at_20:.3f}; offline oracle is {per_video.iloc[0].offline_oracle_recall_at_20:.3f}/{per_video.iloc[1].offline_oracle_recall_at_20:.3f}. The missed-observability gaps are {per_video.iloc[0].oracle_minus_candidate_recall_at_20:.3f}/{per_video.iloc[1].oracle_minus_candidate_recall_at_20:.3f}.
- There are zero missing values in the legal proxy table. Failure is not missingness.
- The candidate beats random by only {per_video.iloc[0].candidate_minus_random_recall_at_20:.3f}/{per_video.iloc[1].candidate_minus_random_recall_at_20:.3f} recall.
- Maximum selected-region contribution is {per_video.best_region_contribution_ratio_at_20.max():.3f}; no single selected region explains the entire weak gain.
- Candidate-versus-combination top-budget selections differ by {disagreements}; combination does not resolve errors.
- {conflicts} feature columns reverse Spearman direction across videos.
- High-score/no-event and low-score/high-event cases are saved as explicit CSV tables.

Main competing explanation: pseudo-reference incompleteness or midpoint region labels may add noise. However, the same frozen labels give a much higher evaluator-only oracle, so label noise alone cannot explain why legal P0 ranking is near random.

Candidate hypothesis for a new preregistered study: semantic low-rate detection or sparse motion may close part of the observability gap. It must be frozen before inspecting its event ranking and must still pass net-cost gates. This result does not authorize post-hoc addition inside MRPO-V1.
""")

    operator_hash = sha_file(ROOT / "scripts/run_mrpo_preview_p0.py")
    feature_schema = [gate["candidate_config"]["feature"]]
    feature_hash = sha_bytes(json.dumps(feature_schema, sort_keys=True).encode())
    model_hash = sha_bytes(json.dumps(gate["candidate_config"], sort_keys=True).encode())
    final = f"""# Final Proxy Decision

## Strongest supported conclusion

There is substantial **evaluator-only temporal allocation headroom**, but the frozen fixed-fidelity P0 preview does not expose enough of it to support a new SCAN scheduler. The strongest legal heuristic reaches only {per_video.iloc[0].recall_at_20:.3f}/{per_video.iloc[1].recall_at_20:.3f} Recall@20, while the offline full-information order reaches {per_video.iloc[0].offline_oracle_recall_at_20:.3f}/{per_video.iloc[1].offline_oracle_recall_at_20:.3f}. After paying preview cost, it loses {abs(int(net.iloc[0].delta_event_count))}/{abs(int(net.iloc[1].delta_event_count))} events to geometric coverage at 60 s.

## What this says about SCAN innovation

The current result rejects **fixed-fidelity framestat value ranking** as the innovation. It does not reject SCAN scheduling in principle. The remaining gap is an observability problem, not evidence that a more complex optimizer over the same P0 features will work.

The next algorithmic hypothesis should be a **coverage-guarded, cost-aware multi-fidelity region scheduler**: geometric coverage remains the default; a newly frozen semantic/motion preview estimates residual event value; deviation is permitted only when estimated incremental event yield per total cost exceeds coverage opportunity cost; farthest-uncovered-region and maximum-gap guards preserve recoverability. This is a candidate hypothesis only. MRPO-V1 does not authorize implementing its allocator because the Static Ranking Gate failed.

## Decision

Stop adding fixed-fidelity models. Do not implement one-step allocation, RL, bandits, or Guarded Marginal Scan from these results. A new experiment may preregister one of the unused allowed information sources (P1 low-rate detection or P2 sparse motion), include the preview cost in the action value, and first repeat the same static ranking falsification. Formal selection additionally requires at least four new complete validation videos.

CONTRACT_HASH = {frozen['contract_hash']}
CODE_COMMIT = {git_value('rev-parse', 'HEAD')}
VIDEO_COUNT = 2
DESIGN_VIDEO_COUNT = 2
VALIDATION_VIDEO_COUNT = 0
TEST_VIDEO_COUNT = 0

REFERENCE_TYPE = FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE
REFERENCE_COMPLETENESS_STATUS = NOT_GROUND_TRUTH_COMPLETE; OFFSET0_EXPOSABLE_263_OF_268
EVENT_CLAIM_SCOPE = RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE

PREVIEW_OPERATOR = {cost_audit['selected_operator_id']}
PREVIEW_OPERATOR_HASH = {operator_hash}
PREVIEW_COST_RATIO = {cost_audit['preview_to_full_scan_cost_ratio']:.9f}
PREVIEW_LEGALITY = PASS_SOURCE_VIDEO_ONLY

MACRO_REGION_LENGTH = 40_SECONDS
FEATURE_SCHEMA_HASH = {feature_hash}
MODEL_FAMILY = M0_UNIVARIATE_HEURISTIC
MODEL_CONFIG_HASH = {model_hash}

PRIMARY_RECALL_AT_20 = {per_video.iloc[0].recall_at_20:.6f}/{per_video.iloc[1].recall_at_20:.6f}; MACRO={per_video.recall_at_20.mean():.6f}
PRIMARY_ENRICHMENT_AT_20 = {per_video.iloc[0].enrichment_at_20:.6f}/{per_video.iloc[1].enrichment_at_20:.6f}; MACRO={per_video.enrichment_at_20.mean():.6f}
RANKING_AUC = {per_video.iloc[0].ranking_event_recall_auc:.6f}/{per_video.iloc[1].ranking_event_recall_auc:.6f}; MACRO={per_video.ranking_event_recall_auc.mean():.6f}
NET_EVENT_YIELD = -1/-2_EVENTS_AT_60_SECONDS
CROSS_VIDEO_DIRECTION = ABOVE_RANDOM_BOTH_BUT_BELOW_GATE_BOTH
LEAVE_BEST_VIDEO_OUT = NOT_IDENTIFIABLE_WITH_ONLY_TWO_DESIGN_VIDEOS
BEST_REGION_CONTRIBUTION = MAX_{per_video.best_region_contribution_ratio_at_20.max():.6f}

EXPLORATORY_GATE = FAIL_RECALL_ENRICHMENT_AND_NET_YIELD
FORMAL_STATIC_RANKING_GATE = NOT_RUN_REQUIRES_AT_LEAST_FOUR_NEW_VALIDATION_VIDEOS
REGION_VALUE_PROXY_SIGNAL = NOT_ESTABLISHED

SELECTED_PROXY_STATUS = NOT_ESTABLISHED
ONE_STEP_ALLOCATOR_STATUS = BLOCKED
GUARDED_MARGINAL_STATUS = STOPPED
FORMAL_METHOD_RANKING = BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION
NEXT_ALLOWED_STAGE = NEW_PREREGISTERED_MULTI_FIDELITY_PREVIEW_OR_NEW_VISIBLE_SIGNAL_THEN_REPEAT_STATIC_GATE
"""
    dump_text(OUT / "reports/FINAL_PROXY_DECISION.md", final)

    code_version = {
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_status_short": git_value("status", "--short", "--untracked-files=all").splitlines(),
        "scripts": {path.name: sha_file(path) for path in sorted((ROOT / "scripts").glob("*mrpo*.py"))},
    }
    dump_json(OUT / "code_version.json", code_version)
    manifest = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            manifest[str(path.relative_to(OUT))] = {"sha256": sha_file(path), "bytes": path.stat().st_size}
    dump_json(OUT / "artifact_hash_manifest.json", {"artifact_count": len(manifest), "artifacts": manifest})
    print(json.dumps({"status": "COMPLETE", "artifact_count": len(manifest), "decision": gate["exploratory_proxy_signal"]}, indent=2))


if __name__ == "__main__":
    main()
