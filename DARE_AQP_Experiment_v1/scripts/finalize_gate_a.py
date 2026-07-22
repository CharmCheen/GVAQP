#!/usr/bin/env python3
"""Post-seal evaluator-only Gate A diagnostics and frozen materializer replay."""

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def write_csv(path, rows):
    if not rows: raise ValueError(f"empty output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def verify_seal(score_path, inference_dir, config):
    complete = json.loads((inference_dir / "INFERENCE_COMPLETE.json").read_text())
    if complete["status"] != "COMPLETE" or complete["scores_sha256"] != sha256(score_path):
        raise RuntimeError("unsealed or changed raw score file")
    scores = pd.read_csv(score_path)
    with score_path.open(newline="", encoding="utf-8") as handle:
        exact_rows = list(csv.DictReader(handle))
    expected = set(config["methods"])
    if set(scores.signal_id) != expected: raise RuntimeError("score signal set mismatch")
    manifest = pd.read_csv(inference_dir / "sealed_ranking_manifest.csv")
    for signal in sorted(expected):
        part = [row for row in exact_rows if row["signal_id"] == signal]
        order = [int(row["unit_id"]) for row in sorted(part, key=lambda row: (-float(row["score"]), int(row["unit_id"])))]
        row = manifest[manifest.signal_id == signal].iloc[0]
        path = Path(row.path)
        if sha256(path) != row.sha256: raise RuntimeError(f"ranking hash mismatch: {signal}")
        sealed = pd.read_csv(path).sort_values("rank").unit_id.astype(int).tolist()
        if order != sealed: raise RuntimeError(f"ranking recomputation mismatch: {signal}")
    return scores


def load_benchmark_lib(strict_root):
    path = strict_root / "scripts/benchmark_lib.py"
    spec = importlib.util.spec_from_file_location("frozen_benchmark_lib", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module, path


def reference_maps(units, reference):
    unit_to_events = {int(uid): set() for uid in units.unit_id}
    anchors = {}
    for row in reference.itertuples():
        source = {int(x) for x in str(row.source_unit_ids).split("|")}
        for uid in source: unit_to_events[uid].add(row.reference_event_id)
        hit = units[(units.start_time <= row.canonical_anchor_time) & (units.end_time > row.canonical_anchor_time)]
        if len(hit) != 1: raise RuntimeError("non-unique canonical anchor")
        anchors[row.reference_event_id] = int(hit.iloc[0].unit_id)
    return unit_to_events, anchors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PACKAGE / "config/gate_a_frozen.json")
    parser.add_argument("--inference-dir", type=Path, default=PACKAGE / "outputs/gate_a_final")
    parser.add_argument("--output", type=Path, default=PACKAGE / "outputs/gate_a_final/evaluation")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    scores_path = args.inference_dir / "raw_scores.csv"
    scores = verify_seal(scores_path, args.inference_dir, config)
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(PACKAGE / "scripts/evaluate_gate_a.py"),
                    "--config", str(args.config), "--scores", str(scores_path),
                    "--final", "--output", str(args.output)], check=True)

    units_path = REPO / config["inputs"]["units"]
    reference_path = REPO / config["inputs"]["events"]
    strict_root = reference_path.parent.parent
    units, reference = pd.read_csv(units_path), pd.read_csv(reference_path)
    oracle = pd.read_csv(strict_root / "frozen_inputs/oracle_observations.csv")
    labels = dict(zip(oracle.unit_id.astype(int), oracle.parsed_label.astype(str)))
    budgets = json.loads((strict_root / "configs/FROZEN_BUDGETS.json").read_text())["budgets"]
    evaluator_config = json.loads((strict_root / "frozen_inputs/evaluator_config.json").read_text())
    lib, lib_path = load_benchmark_lib(strict_root)
    unit_to_events, anchors = reference_maps(units, reference)
    score_maps = {s: dict(zip(g.unit_id.astype(int), g.score.astype(float))) for s, g in scores.groupby("signal_id")}
    public_orders = {s: sorted(m, key=lambda uid: (-m[uid], uid)) for s, m in score_maps.items()}
    ideal_order = [anchors[event] for event in sorted(anchors)]
    ideal_order += [uid for uid in units.unit_id.astype(int) if uid not in set(ideal_order)]
    write_csv(args.output / "ideal_oracle_ranking.csv", [{"signal_id": "ideal_oracle_ceiling", "rank": i, "unit_id": uid} for i, uid in enumerate(ideal_order, 1)])

    first_rows, diagnostic_rows = [], []
    for signal, order in {**public_orders, "ideal_oracle_ceiling": ideal_order}.items():
        rank = {uid: i for i, uid in enumerate(order, 1)}
        for event in sorted(anchors):
            source = next(set(int(x) for x in str(row.source_unit_ids).split("|")) for row in reference.itertuples() if row.reference_event_id == event)
            discovery = min(rank[x] for x in source)
            first_rows.append({"signal_id": signal, "reference_event_id": event,
                               "first_discovery_rank": discovery, "canonical_anchor_rank": rank[anchors[event]]})
        for budget in sorted(set(budgets + config["top_k"])):
            selected = order[:budget]; found = set(); positive_hits = 0
            for uid in selected:
                found |= unit_to_events[uid]
                positive_hits += bool(unit_to_events[uid])
            blocks = [0] * config["temporal_block_count"]
            for uid in selected: blocks[min(len(blocks)-1, uid * len(blocks) // len(units))] += 1
            probs = [x / len(selected) for x in blocks if x]
            entropy = -sum(p * math.log(p) for p in probs) / math.log(len(blocks))
            diagnostic_rows.append({"signal_id": signal, "budget": budget,
                "distinct_events": len(found), "positive_unit_hits": positive_hits,
                "duplicate_event_burden": max(0, positive_hits - len(found)),
                "duplicate_burden_per_positive_hit": max(0, positive_hits-len(found))/positive_hits if positive_hits else 0.0,
                "temporal_block_counts": "|".join(map(str, blocks)), "position_uniformity_normalized_entropy": entropy,
                "public_to_ideal_distinct_event_gap": min(budget, len(reference)) - len(found)})
    write_csv(args.output / "unique_event_first_discovery.csv", first_rows)
    write_csv(args.output / "ranking_diagnostics.csv", diagnostic_rows)

    materializer_rows, auc_rows = [], []
    mat_cfg = evaluator_config["materializers"]["k3_bridge_safe"]
    evaluator_hash = sha256(lib_path)
    for signal, order in {**public_orders, "ideal_oracle_ceiling": ideal_order}.items():
        f1s = []
        for budget in budgets:
            selected = order[:budget]
            trace = pd.DataFrame({"unit_id": selected, "oracle_label_after_query": [labels[x] for x in selected]})
            meta = {"benchmark_id": str(units.iloc[0].benchmark_id), "run_id": f"gate_a_{signal}_b{budget}",
                    "method": signal, "method_variant": "frozen_ranking_k3_bridge_safe", "seed": 0, "horizon_budget": budget}
            predicted = lib.materialize_from_trace(trace, units, meta, "k3_bridge_safe", mat_cfg)
            matches = lib.match_events(predicted, reference, meta)
            metrics = lib.compute_metrics(predicted, reference, matches, meta, evaluator_hash)
            values = dict(zip(metrics.metric_name, metrics.metric_value.astype(float)))
            row = {"signal_id": signal, "budget": budget, "event_f1": values["event_f1"],
                   "event_precision": values["event_precision"], "event_recall": values["event_recall"],
                   "predicted_event_count": values["predicted_event_count"], "returned_seconds": values["returned_seconds"]}
            materializer_rows.append(row); f1s.append(row["event_f1"])
        auc_rows.append({"signal_id": signal, "event_f1_auc": float(np.trapezoid(f1s, budgets)/(budgets[-1]-budgets[0])),
                         "valid_budget_count": len(budgets), "materializer": "k3_bridge_safe"})
    write_csv(args.output / "per_budget_event_metrics.csv", materializer_rows)
    write_csv(args.output / "event_f1_auc.csv", auc_rows)

    # Reuse the frozen Gate A metric implementation for the evaluator-only ideal ceiling.
    eval_spec = importlib.util.spec_from_file_location("frozen_gate_a_evaluator", PACKAGE / "scripts/evaluate_gate_a.py")
    gate_eval = importlib.util.module_from_spec(eval_spec); eval_spec.loader.exec_module(gate_eval)
    _, unit_ids, events, unit_events = gate_eval.load_population(config)
    ideal_scores = {uid: float(len(unit_ids) - rank) for rank, uid in enumerate(ideal_order)}
    ideal_metrics = gate_eval.ranking_metrics({"ideal_oracle_ceiling": ideal_scores}, unit_ids, events,
                                              unit_events, config["top_k"], config["temporal_block_count"])
    write_csv(args.output / "ideal_oracle_ranking_metrics.csv", ideal_metrics)
    public_metrics = pd.read_csv(args.output / "ranking_metrics.csv")
    ideal_metric = ideal_metrics[0]
    gap_fields = ["full_video_anchor_auroc_descriptive", "full_video_anchor_ap_descriptive"] + [f"top_{k}_distinct_events" for k in config["top_k"]]
    gap_rows = []
    for row in public_metrics.to_dict("records"):
        gap_rows.append({"signal_id": row["signal_id"], **{f"ideal_minus_{field}": float(ideal_metric[field]) - float(row[field]) for field in gap_fields}})
    write_csv(args.output / "public_to_oracle_gap.csv", gap_rows)
    ideal_gate = pd.read_csv(PACKAGE / "outputs/gate_b/stage_decisions.csv")
    ideal_gate = ideal_gate[(ideal_gate.policy == "oracle_anchor_ceiling") &
                            (ideal_gate.recall_target.astype(float) == config["gate_b"]["recall_target"])]
    ideal_gate.to_csv(args.output / "ideal_oracle_gate_b_ceiling.csv", index=False)

    traces = pd.read_csv(strict_root / "baselines/baseline_action_traces.csv")
    current = pd.read_csv(strict_root / "current_method/current_action_traces.csv")
    arc = traces[(traces.method == "B5_ARC_native") & (traces.method_variant == "arc_refinement_th0.4_native") & (traces.seed == 0) & (traces.horizon_budget == 100)].sort_values("call_idx").unit_id.astype(int).tolist()
    map_order = current[(current.method == "M1_MAP_anchor_only") & (current.method_variant == "K3_BRIDGE_SAFE") & (current.seed == 0) & (current.horizon_budget == 100)].sort_values("call_idx").unit_id.astype(int).tolist()
    overlap_rows = []
    for signal, order in public_orders.items():
        for baseline, base_order in [("ARC_native", arc), ("MAP_K3_bridge_safe", map_order)]:
            for budget in budgets:
                left, right = set(order[:budget]), set(base_order[:budget]); union = left | right
                overlap_rows.append({"signal_id": signal, "baseline": baseline, "budget": budget,
                                     "overlap_count": len(left & right), "jaccard_overlap": len(left & right)/len(union),
                                     "set_divergence": 1-len(left & right)/len(union)})
    write_csv(args.output / "arc_map_overlap_divergence.csv", overlap_rows)

    runtime = pd.read_csv(args.inference_dir / "runtime_ledger.csv").set_index("signal_id")
    per_unit_rows = []
    for method in ["image_text", "video_text"]:
        for path in sorted((args.inference_dir / "checkpoints" / method).glob("unit_*.json")):
            value = json.loads(path.read_text())
            per_unit_rows.append({"signal_id": method, "unit_id": value["unit_id"],
                "frames": value["frames"], "data_loading_seconds": value["data_loading_seconds"],
                "preprocessing_cpu_seconds": value["preprocessing_cpu_seconds"],
                "model_forward_seconds": value["model_forward_seconds"],
                "total_unit_seconds": value["data_loading_seconds"] + value["preprocessing_cpu_seconds"] + value["model_forward_seconds"]})
    write_csv(args.output / "per_unit_runtime.csv", per_unit_rows)
    cost_rows = []
    gate = pd.read_csv(args.output / "gate_b_link.csv")
    for signal in sorted(public_orders):
        rt = runtime.loc[signal] if signal in runtime.index else None
        if signal == "rank_fusion":
            cold = float(runtime.loc["image_text","cold_total_inference_seconds"] + runtime.loc["video_text","cold_total_inference_seconds"])
            warm = float(runtime.loc["image_text","warm_index_query_seconds"] + runtime.loc["video_text","warm_index_query_seconds"])
        elif rt is not None:
            cold, warm = float(rt.cold_total_inference_seconds), float(rt.warm_index_query_seconds)
        else: cold = warm = math.nan
        for row in gate[gate.signal_id == signal].itertuples():
            cost_rows.append({"signal_id": signal, "discovery_budget": row.discovery_budget,
                "events_discovered_pre_audit": row.events_discovered_pre_audit,
                "gate_b_total_calls": row.median_total_cost, "dense_cost_ratio": row.cost_ratio,
                "cold_semantic_seconds": cold, "warm_index_query_seconds": warm,
                "physical_exact_oracle_vlm_calls": 0})
    write_csv(args.output / "query_cost_normalized_results.csv", cost_rows)
    seal_files = sorted(p for p in args.output.iterdir() if p.is_file())
    write_csv(args.output / "EVALUATION_FILE_MANIFEST.csv", [{"path": str(p), "size_bytes": p.stat().st_size, "sha256": sha256(p)} for p in seal_files])
    print(args.output)


if __name__ == "__main__": main()
