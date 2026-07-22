#!/usr/bin/env python3
"""Run the frozen development and cross-video AQP gate from cached oracles."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
FROZEN = PACKAGE / "config" / "frozen_protocol.json"
EXPECTED_FROZEN_SHA256 = "4eea29f266f35be771ee430bb04221babe32c48adffc7bd7dd4a64e3ac7fd42a"
STRICT = (
    REPO
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run"
    / "clean_baseline_benchmark_v2_strict"
)
sys.path.insert(0, str(STRICT / "scripts"))
from benchmark_lib import (  # noqa: E402
    evaluate_events,
    materialize_from_trace,
    sha256_file,
)


MATERIALIZER_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0}
RANDOM_SEEDS = list(range(100))


def stable_order(values: np.ndarray) -> list[int]:
    unit_ids = np.arange(len(values))
    return np.lexsort((unit_ids, -np.asarray(values, dtype=float))).astype(int).tolist()


def rank_percentile(scores: np.ndarray) -> np.ndarray:
    order = stable_order(scores)
    result = np.empty(len(scores), dtype=float)
    denominator = max(1, len(scores) - 1)
    for rank, unit_id in enumerate(order):
        result[unit_id] = 1.0 - rank / denominator
    return result


def load_embeddings(directory: Path, n_units: int) -> np.ndarray:
    rows = []
    for unit_id in range(n_units):
        path = directory / f"unit_{unit_id:04d}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if int(value["unit_id"]) != unit_id:
            raise RuntimeError(f"checkpoint unit mismatch at {path}")
        rows.append(value["embedding"])
    matrix = np.asarray(rows, dtype=float)
    if matrix.shape != (n_units, 512):
        raise RuntimeError(f"unexpected embedding matrix {matrix.shape}")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise RuntimeError("zero-norm embedding")
    return matrix / norms


def qtpc_ranking(scores: np.ndarray, radius: int = 8) -> tuple[list[int], np.ndarray]:
    contrast = np.empty(len(scores), dtype=float)
    for unit_id in range(len(scores)):
        lo = max(0, unit_id - radius)
        hi = min(len(scores), unit_id + radius + 1)
        neighbors = np.concatenate((scores[lo:unit_id], scores[unit_id + 1 : hi]))
        contrast[unit_id] = scores[unit_id] - float(np.max(neighbors)) if len(neighbors) else scores[unit_id]
    return stable_order(contrast), contrast


def temporal_nms_ranking(scores: np.ndarray, radius: int) -> list[int]:
    base = stable_order(scores)
    selected: list[int] = []
    for unit_id in base:
        if all(abs(unit_id - chosen) > radius for chosen in selected):
            selected.append(unit_id)
    selected_set = set(selected)
    selected.extend(unit_id for unit_id in base if unit_id not in selected_set)
    if sorted(selected) != list(range(len(scores))):
        raise RuntimeError("temporal NMS did not return a permutation")
    return selected


def mmr_ranking(scores: np.ndarray, embeddings: np.ndarray, lam: float = 0.5) -> list[int]:
    relevance = rank_percentile(scores)
    similarity = embeddings @ embeddings.T
    remaining = set(range(len(scores)))
    selected: list[int] = []
    max_similarity = np.zeros(len(scores), dtype=float)
    while remaining:
        best = min(
            remaining,
            key=lambda unit_id: (
                -(lam * relevance[unit_id] - (1.0 - lam) * max_similarity[unit_id]),
                unit_id,
            ),
        )
        selected.append(best)
        remaining.remove(best)
        max_similarity = np.maximum(max_similarity, similarity[:, best])
    return selected


def facility_ranking(scores: np.ndarray, embeddings: np.ndarray) -> list[int]:
    relevance = np.clip(rank_percentile(scores), 1.0 / len(scores), 1.0) ** 8
    weights = relevance / relevance.sum()
    similarity = np.clip((embeddings @ embeddings.T - 0.5) / 0.5, 0.0, 1.0)
    covered = np.zeros(len(scores), dtype=float)
    remaining = set(range(len(scores)))
    selected: list[int] = []
    while remaining:
        best = min(
            remaining,
            key=lambda unit_id: (
                -float(np.dot(weights, np.maximum(0.0, similarity[:, unit_id] - covered))),
                unit_id,
            ),
        )
        selected.append(best)
        remaining.remove(best)
        covered = np.maximum(covered, similarity[:, best])
    return selected


def bsec_ranking(scores: np.ndarray, embeddings: np.ndarray) -> list[int]:
    """Hard-cell instance of the frozen monotone-submodular BSEC surrogate."""
    n_units = len(scores)
    reliability = np.clip(rank_percentile(scores), 1.0 / n_units, 1.0) ** 8
    n_clusters = max(2, round(math.sqrt(n_units)))
    clusters = KMeans(n_clusters=n_clusters, random_state=20260712, n_init=10).fit_predict(embeddings)
    memberships: list[list[int]] = [[] for _ in range(n_units)]
    concept_weights: list[float] = []

    for cluster_id in range(n_clusters):
        concept_id = len(concept_weights)
        concept_weights.append(0.25 / n_clusters)
        for unit_id in np.flatnonzero(clusters == cluster_id):
            memberships[int(unit_id)].append(concept_id)

    temporal_widths = [8, 32, 128]
    for width in temporal_widths:
        cells = [(lo, min(n_units, lo + width)) for lo in range(0, n_units, width)]
        for lo, hi in cells:
            concept_id = len(concept_weights)
            concept_weights.append(0.75 / (len(temporal_widths) * len(cells)))
            for unit_id in range(lo, hi):
                memberships[unit_id].append(concept_id)

    weights = np.asarray(concept_weights, dtype=float)
    uncovered_product = np.ones(len(weights), dtype=float)
    remaining = set(range(n_units))
    selected: list[int] = []
    while remaining:
        best = min(
            remaining,
            key=lambda unit_id: (
                -float(
                    reliability[unit_id]
                    * np.sum(weights[memberships[unit_id]] * uncovered_product[memberships[unit_id]])
                ),
                unit_id,
            ),
        )
        selected.append(best)
        remaining.remove(best)
        uncovered_product[memberships[best]] *= 1.0 - reliability[best]
    return selected


def make_reference_from_adapter(reference: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, event in reference.iterrows():
        overlap = units[
            (units["end_time"].astype(float) > float(event.start_time))
            & (units["start_time"].astype(float) < float(event.end_time))
        ]["unit_id"].astype(int)
        rows.append(
            {
                "benchmark_id": "heldout_realcartest_2000_3200",
                "video_id": "realcartest",
                "reference_event_id": str(event.source_event_id),
                "start_time": float(event.start_time),
                "core_start_time": float(event.start_time),
                "core_end_time": float(event.end_time),
                "end_time": float(event.end_time),
                "canonical_anchor_time": float(event.start_time),
                "source_unit_ids": "|".join(map(str, overlap.tolist())),
                "event_type": str(event.event_type),
                "reference_type": "VLM_DEFINED_PSEUDO_ORACLE",
                "reference_version": "real_video_protocol_pilot_v1",
                "adjudication_status": "not_human_adjudicated",
            }
        )
    return pd.DataFrame(rows)


def load_development(config: dict) -> dict:
    spec = config["development"]
    units = pd.read_csv(REPO / spec["units"])
    oracle = pd.read_csv(REPO / spec["oracle_observations"])
    reference = pd.read_csv(REPO / spec["reference"])
    raw = pd.read_csv(REPO / spec["clip_scores"])
    score_rows = raw[raw.signal_id == "image_text"].sort_values("unit_id")
    scores = score_rows.score.to_numpy(float)
    if len(units) != 347 or len(scores) != len(units):
        raise RuntimeError("development population mismatch")
    labels = dict(zip(oracle.unit_id.astype(int), oracle.parsed_label.astype(str)))
    embeddings = load_embeddings(REPO / spec["clip_checkpoints"], len(units))
    return {
        "name": "development",
        "benchmark_id": str(units.benchmark_id.iloc[0]),
        "units": units,
        "reference": reference,
        "labels": labels,
        "scores": scores,
        "embeddings": embeddings,
    }


def load_heldout(config: dict) -> dict:
    source = pd.read_csv(REPO / config["heldout"]["units"])
    units = pd.DataFrame(
        {
            "benchmark_id": "heldout_realcartest_2000_3200",
            "video_id": source.video_id.astype(str),
            "unit_id": source.frame_idx.astype(int),
            "start_time": source.start_time.astype(float),
            "end_time": source.end_time.astype(float),
        }
    )
    if units.unit_id.tolist() != list(range(120)):
        raise RuntimeError("heldout unit grid mismatch")
    labels = {
        int(row.frame_idx): ("positive" if int(row.oracle_label) else "negative")
        for _, row in source.iterrows()
    }
    reference_adapter = pd.read_csv(REPO / config["heldout"]["reference"])
    reference = make_reference_from_adapter(reference_adapter, units)
    inference = PACKAGE / "outputs" / "heldout" / "clip_inference"
    complete = json.loads((inference / "INFERENCE_COMPLETE.json").read_text(encoding="utf-8"))
    if complete["frozen_protocol_sha256"] != EXPECTED_FROZEN_SHA256:
        raise RuntimeError("heldout inference used a different frozen protocol")
    score_rows = pd.read_csv(inference / "clip_scores.csv").sort_values("unit_id")
    scores = score_rows.score.to_numpy(float)
    embeddings = load_embeddings(inference / "checkpoints", len(units))
    return {
        "name": "heldout",
        "benchmark_id": "heldout_realcartest_2000_3200",
        "units": units,
        "reference": reference,
        "labels": labels,
        "scores": scores,
        "embeddings": embeddings,
        "proxy_scores": source.proxy_score.to_numpy(float),
    }


def development_arc_rankings(budgets: list[int]) -> dict[tuple[int, int], list[int]]:
    base = (
        STRICT
        / "baselines"
        / "controlled_track"
        / "B3_ARC_adapted"
        / "arc_refinement_th0.4_controlled"
    )
    result = {}
    for seed_dir in sorted(base.glob("seed_*")):
        seed = int(seed_dir.name.split("_")[-1])
        for budget in budgets:
            trace = pd.read_csv(seed_dir / f"budget_{budget}" / "observation_trace.csv")
            ranking = trace.sort_values("call_idx").unit_id.astype(int).tolist()
            if len(ranking) != budget or len(set(ranking)) != budget:
                raise RuntimeError(f"development ARC not exact at seed={seed}, B={budget}")
            result[(seed, budget)] = ranking
    return result


def heldout_arc_rankings(data: dict, budgets: list[int]) -> dict[tuple[int, int], list[int]]:
    base = REPO / "outputs" / "ours_vs_baselines_realcartest_v1" / "baseline_outputs"
    proxy_order = stable_order(data["proxy_scores"])
    result = {}
    for seed in range(5):
        for budget in budgets:
            path = base / f"ARC_refinement_b{budget}_s{seed}_th0.4" / "oracle_log.csv"
            trace = pd.read_csv(path)
            ranking = trace.sort_values("call_idx").unit_id.astype(int).tolist()
            seen = set(ranking)
            # Two historical B=100 runs stopped at 92/93. Fill only to enforce
            # the frozen exact-call contract; the original native rows remain descriptive.
            ranking.extend(unit_id for unit_id in proxy_order if unit_id not in seen)
            ranking = ranking[:budget]
            if len(ranking) != budget or len(set(ranking)) != budget:
                raise RuntimeError(f"heldout ARC fill failed at seed={seed}, B={budget}")
            result[(seed, budget)] = ranking
    return result


def reference_units(reference: pd.DataFrame) -> dict[str, set[int]]:
    result = {}
    for _, row in reference.iterrows():
        text = str(row.source_unit_ids)
        result[str(row.reference_event_id)] = {
            int(token) for token in text.replace("|", " ").split() if token
        }
    return result


def oracle_ranking(data: dict) -> list[int]:
    event_units = reference_units(data["reference"])
    selected = []
    seen = set()
    for event_id in sorted(event_units):
        candidates = sorted(
            event_units[event_id], key=lambda unit_id: (-data["scores"][unit_id], unit_id)
        )
        if candidates:
            unit_id = candidates[0]
            if unit_id not in seen:
                selected.append(unit_id)
                seen.add(unit_id)
    positives = [u for u, label in data["labels"].items() if label == "positive" and u not in seen]
    positives.sort(key=lambda unit_id: (-data["scores"][unit_id], unit_id))
    selected.extend(positives)
    seen.update(positives)
    selected.extend(unit_id for unit_id in stable_order(data["scores"]) if unit_id not in seen)
    return selected


def evaluate_selection(
    data: dict,
    method: str,
    variant: str,
    seed: int,
    budget: int,
    selected: list[int],
    evaluator_hash: str,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if len(selected) != budget or len(set(selected)) != budget:
        raise RuntimeError(f"{method} {variant} seed={seed} B={budget} is not exact")
    trace = pd.DataFrame(
        {
            "unit_id": selected,
            "oracle_label_after_query": [data["labels"][unit_id] for unit_id in selected],
        }
    )
    run_id = f"{data['name']}_{method}_{variant}_s{seed:03d}_b{budget}"
    meta = {
        "benchmark_id": data["benchmark_id"],
        "run_id": run_id,
        "method": method,
        "method_variant": variant,
        "seed": seed,
        "horizon_budget": budget,
    }
    predicted = materialize_from_trace(
        trace, data["units"], meta, "k3_bridge_safe", MATERIALIZER_CONFIG
    )
    matches, metrics = evaluate_events(predicted, data["reference"], meta, evaluator_hash)
    metric_map = dict(zip(metrics.metric_name, metrics.metric_value))
    event_map = reference_units(data["reference"])
    found = {
        event_id
        for event_id, source_units in event_map.items()
        if source_units.intersection(selected)
    }
    positive_hits = sum(data["labels"][unit_id] == "positive" for unit_id in selected)
    row = {
        "dataset": data["name"],
        "method": method,
        "method_variant": variant,
        "seed": seed,
        "budget": budget,
        "exact_oracle_calls": len(selected),
        "selected_positive_units": positive_hits,
        "selected_distinct_reference_events": len(found),
        "positive_duplicate_burden": max(0, positive_hits - len(found)),
        **{key: float(value) for key, value in metric_map.items()},
    }
    selection_rows = pd.DataFrame(
        [
            {
                "dataset": data["name"],
                "method": method,
                "method_variant": variant,
                "seed": seed,
                "budget": budget,
                "selection_rank": rank,
                "unit_id": unit_id,
                "clip_score": data["scores"][unit_id],
                "oracle_label": data["labels"][unit_id],
            }
            for rank, unit_id in enumerate(selected, 1)
        ]
    )
    return row, selection_rows, predicted, matches


def native_arc_rows(dataset: str, budgets: list[int]) -> tuple[list[dict], dict]:
    rows = []
    if dataset == "development":
        source = pd.read_csv(STRICT / "analysis" / "per_budget_metrics.csv")
        source = source[
            (source.method == "B5_ARC_native")
            & (source.method_variant == "arc_refinement_th0.4_native")
        ]
        for _, item in source.iterrows():
            rows.append(
                {
                    "dataset": dataset,
                    "method": "arc_native_descriptive",
                    "method_variant": "historical_native_materializer",
                    "seed": -1,
                    "budget": int(item.horizon_budget),
                    "exact_oracle_calls": float(item.logical_calls_mean),
                    "event_precision": float(item.event_precision_mean),
                    "event_recall": float(item.event_recall_mean),
                    "event_f1": float(item.event_f1_mean),
                    "returned_seconds": float(item.returned_seconds_mean),
                }
            )
    else:
        source = pd.read_csv(
            REPO / "outputs" / "ours_vs_baselines_realcartest_v1" / "tables" / "main_comparison_table.csv"
        )
        # Historical report selected threshold 0.3 at B=5/10 and 0.4 above.
        # Preserve those native rows as the strongest published descriptive curve;
        # the shared-K3 primary comparator remains fixed at threshold 0.4.
        source = source[source.method == "ARC-refinement"]
        for _, item in source.iterrows():
            rows.append(
                {
                    "dataset": dataset,
                    "method": "arc_native_descriptive",
                    "method_variant": "historical_selected_native_materializer",
                    "seed": -1,
                    "budget": int(item.budget),
                    "exact_oracle_calls": float(item.oracle_calls_mean),
                    "event_precision": float(item.event_detection_precision_mean),
                    "event_recall": float(item.event_detection_recall_mean),
                    "event_f1": float(item.event_detection_f1_mean),
                    "returned_seconds": math.nan,
                }
            )
    rows = [row for row in rows if row["budget"] in budgets]
    if len(rows) != len(budgets):
        raise RuntimeError(f"native ARC descriptive curve incomplete for {dataset}")
    return rows, {"materializer_equalized": False, "primary_gate_eligible": False}


def summarize(rows: pd.DataFrame, budgets: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    numeric = [
        "exact_oracle_calls",
        "selected_positive_units",
        "selected_distinct_reference_events",
        "positive_duplicate_burden",
        "event_precision",
        "event_recall",
        "event_f1",
        "predicted_event_count",
        "returned_seconds",
        "overcoverage_ratio",
        "matched_mean_iou",
    ]
    available = [column for column in numeric if column in rows.columns]
    grouped = rows.groupby(["dataset", "method", "method_variant", "budget"], dropna=False)
    summary = grouped[available].agg(["mean", "std", "min", "max"]).reset_index()
    summary.columns = [
        "_".join(str(part) for part in column if part).rstrip("_")
        if isinstance(column, tuple)
        else column
        for column in summary.columns
    ]
    curve_rows = []
    for (dataset, method, variant), group in summary.groupby(
        ["dataset", "method", "method_variant"], dropna=False
    ):
        group = group.sort_values("budget")
        if group.budget.tolist() != budgets:
            continue
        auc = float(
            np.trapezoid(group.event_f1_mean.to_numpy(float), group.budget.to_numpy(float))
            / (budgets[-1] - budgets[0])
        )
        curve_rows.append(
            {
                "dataset": dataset,
                "method": method,
                "method_variant": variant,
                "event_f1_auc": auc,
                "budgets": "|".join(map(str, budgets)),
                "primary_gate_eligible": method != "arc_native_descriptive",
            }
        )
    return summary, pd.DataFrame(curve_rows).sort_values(
        ["dataset", "event_f1_auc"], ascending=[True, False]
    )


def run_dataset(data: dict, budgets: list[int], output: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    output.mkdir(parents=True, exist_ok=True)
    scores = data["scores"]
    embeddings = data["embeddings"]
    qtpc, contrast = qtpc_ranking(scores, radius=8)
    rankings = {
        ("clip_topk", "raw_clip", 0): stable_order(scores),
        ("qtpc", "h8_frozen", 0): qtpc,
        ("temporal_nms", "h8", 0): temporal_nms_ranking(scores, 8),
        ("temporal_nms", "h10_dev_selected", 0): temporal_nms_ranking(scores, 10),
        ("mmr", "lambda_0.5", 0): mmr_ranking(scores, embeddings, 0.5),
        ("facility_location", "query_weight_power8", 0): facility_ranking(scores, embeddings),
        ("bsec", "hard_semantic_temporal_cover", 0): bsec_ranking(scores, embeddings),
        ("oracle_ceiling", "reference_aware", 0): oracle_ranking(data),
    }
    for seed in RANDOM_SEEDS:
        rankings[("random", "uniform_nested", seed)] = (
            np.random.default_rng(20260712 + seed).permutation(len(scores)).astype(int).tolist()
        )
    arc = (
        development_arc_rankings(budgets)
        if data["name"] == "development"
        else heldout_arc_rankings(data, budgets)
    )
    evaluator_hash = sha256_file(STRICT / "scripts" / "benchmark_lib.py")
    rows = []
    selections = []
    predicted_frames = []
    match_frames = []
    for (method, variant, seed), ranking in rankings.items():
        for budget in budgets:
            row, selection, predicted, matches = evaluate_selection(
                data, method, variant, seed, budget, ranking[:budget], evaluator_hash
            )
            rows.append(row)
            selections.append(selection)
            if method in {"clip_topk", "qtpc", "temporal_nms", "mmr", "facility_location", "bsec"}:
                predicted_frames.append(predicted)
                match_frames.append(matches)
    for (seed, budget), selection in sorted(arc.items()):
        row, selected_rows, predicted, matches = evaluate_selection(
            data,
            "arc_shared_k3",
            "threshold_0.4_exact_fill",
            seed,
            budget,
            selection,
            evaluator_hash,
        )
        rows.append(row)
        selections.append(selected_rows)
        predicted_frames.append(predicted)
        match_frames.append(matches)
    native, _ = native_arc_rows(data["name"], budgets)
    rows.extend(native)

    per_run = pd.DataFrame(rows)
    summary, auc = summarize(per_run, budgets)
    ranking_rows = []
    for (method, variant, seed), ranking in rankings.items():
        if method == "random":
            continue
        for rank, unit_id in enumerate(ranking, 1):
            ranking_rows.append(
                {
                    "dataset": data["name"],
                    "method": method,
                    "method_variant": variant,
                    "seed": seed,
                    "rank": rank,
                    "unit_id": unit_id,
                    "clip_score": scores[unit_id],
                    "qtpc_contrast": contrast[unit_id] if method == "qtpc" else math.nan,
                }
            )
    per_run.to_csv(output / "per_budget_runs.csv", index=False)
    summary.to_csv(output / "per_budget_summary.csv", index=False)
    auc.to_csv(output / "event_f1_auc.csv", index=False)
    pd.concat(selections, ignore_index=True).to_csv(output / "selections.csv", index=False)
    pd.DataFrame(ranking_rows).to_csv(output / "sealed_rankings.csv", index=False)
    pd.concat(predicted_frames, ignore_index=True).to_csv(output / "predicted_events.csv", index=False)
    pd.concat(match_frames, ignore_index=True).to_csv(output / "event_matches.csv", index=False)
    return summary, auc


def sha256_manifest(root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "OUTPUT_MANIFEST.csv":
            rows.append(
                {
                    "path": str(path.relative_to(PACKAGE)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PACKAGE / "outputs")
    args = parser.parse_args()
    frozen_hash = sha256_file(FROZEN)
    if frozen_hash != EXPECTED_FROZEN_SHA256:
        raise RuntimeError(f"frozen protocol changed: {frozen_hash}")
    config = json.loads(FROZEN.read_text(encoding="utf-8"))
    budgets = [int(value) for value in config["budgets"]]
    development = load_development(config)
    heldout = load_heldout(config)
    dev_summary, dev_auc = run_dataset(development, budgets, args.output / "development")
    held_summary, held_auc = run_dataset(heldout, budgets, args.output / "heldout")

    def auc_value(frame: pd.DataFrame, method: str, variant: str) -> float:
        row = frame[(frame.method == method) & (frame.method_variant == variant)]
        if len(row) != 1:
            raise RuntimeError(f"missing AUC row {method}/{variant}")
        return float(row.event_f1_auc.iloc[0])

    def budget_wins(summary: pd.DataFrame, left: str, right: str) -> int:
        a = summary[summary.method == left].set_index("budget").event_f1_mean
        b = summary[summary.method == right].set_index("budget").event_f1_mean
        return int((a > b).sum())

    dev_qtpc = auc_value(dev_auc, "qtpc", "h8_frozen")
    development_comparators = {
        f"{row.method}/{row.method_variant}": float(row.event_f1_auc)
        for _, row in dev_auc.iterrows()
        if row.primary_gate_eligible
        and row.method
        in {"clip_topk", "arc_shared_k3", "mmr", "facility_location", "bsec", "temporal_nms"}
    }
    dev_pass = all(dev_qtpc > value for value in development_comparators.values())
    held_qtpc = auc_value(held_auc, "qtpc", "h8_frozen")
    held_clip = auc_value(held_auc, "clip_topk", "raw_clip")
    held_arc = auc_value(held_auc, "arc_shared_k3", "threshold_0.4_exact_fill")
    held_wins = budget_wins(held_summary, "qtpc", "clip_topk")
    held_pass = held_qtpc > held_clip and held_qtpc > held_arc and held_wins >= 4
    decision = {
        "frozen_protocol_sha256": frozen_hash,
        "development": {
            "qtpc_event_f1_auc": dev_qtpc,
            "comparators": development_comparators,
            "pass": dev_pass,
        },
        "heldout": {
            "qtpc_event_f1_auc": held_qtpc,
            "clip_event_f1_auc": held_clip,
            "arc_shared_k3_event_f1_auc": held_arc,
            "qtpc_budget_wins_over_clip": held_wins,
            "pass": held_pass,
        },
        "gate_decision": "GO" if dev_pass and held_pass else "NO_GO_CONTINUE_SEARCH",
        "native_arc_primary_eligible": False,
        "physical_exact_oracle_vlm_calls": 0,
    }
    (args.output / "GATE_DECISION.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha256_manifest(PACKAGE).to_csv(PACKAGE / "OUTPUT_MANIFEST.csv", index=False)
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
