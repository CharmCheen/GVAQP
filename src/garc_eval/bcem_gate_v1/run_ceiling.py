"""Replay frozen controlled traces and compute exact legal-partition ceilings."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import resource
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .ceiling import exact_ceiling_partition, score_partition_ordered
from .core import (
    BCEMConfig, Group, Partition, assert_partition_invariants, barrier_block_count,
    build_event_relation, count_legal_partitions, legal_group_edges, parse_observations,
)


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run"
STRICT = BASE / "clean_baseline_benchmark_v2_strict"
OUT = BASE / "barrier_constrained_event_materialization_gate_v1"
CONFIG_PATH = OUT / "config/FROZEN_BCEM_CONFIG.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_benchmark_lib():
    path = STRICT / "scripts/benchmark_lib.py"
    spec = importlib.util.spec_from_file_location("bcem_frozen_benchmark_lib", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen benchmark_lib.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metric_map(metrics: pd.DataFrame) -> dict[str, float]:
    return {str(r.metric_name): float(r.metric_value) for r in metrics.itertuples()}


def read_ids(value: object) -> tuple[int, ...]:
    text = str(value).strip()
    for delimiter in ("|", ",", ";"):
        text = text.replace(delimiter, " ")
    out = []
    for token in text.split():
        try:
            out.append(int(float(token)))
        except ValueError:
            pass
    return tuple(sorted(set(out)))


def segments_partition(segments: pd.DataFrame) -> Partition:
    groups = []
    anchor_index = 0
    for row in segments.sort_values(["start_time", "end_time", "event_id"]).itertuples(index=False):
        anchors = read_ids(row.anchor_unit_ids)
        if not anchors:
            continue
        groups.append(Group(anchor_index, anchor_index + len(anchors) - 1, anchors,
                            float(row.start_time), float(row.end_time), ()))
        anchor_index += len(anchors)
    return Partition(tuple(groups))


def certified_f1(partition: Partition, reference: pd.DataFrame) -> tuple[float, int]:
    matched, _, _ = score_partition_ordered(partition, reference, require_anchor_support=True)
    denom = len(partition.groups) + len(reference)
    return (2.0 * matched / denom if denom else 0.0), matched


def selected_registry(config: dict[str, Any]) -> pd.DataFrame:
    baseline = pd.read_csv(STRICT / "baselines/baseline_run_registry.csv")
    current = pd.read_csv(STRICT / "current_method/current_method_runs.csv")
    frames = []
    for method, variant, selector in config["selector_variants"]:
        source = current if method == "M1_MAP_anchor_only" else baseline
        chosen = source[(source.method == method) & (source.method_variant == variant)].copy()
        chosen["selector"] = selector
        frames.append(chosen)
    registry = pd.concat(frames, ignore_index=True)
    expected_budgets = set(config["budgets"])
    if set(registry.horizon_budget.astype(int)) != expected_budgets:
        raise RuntimeError("selected trace registry does not cover exact frozen budgets")
    if (registry.status != "VALID").any() or registry.run_id.duplicated().any():
        raise RuntimeError("selected trace registry has invalid or duplicate runs")
    if int(registry.physical_vlm_calls.sum()) != 0:
        raise RuntimeError("selected registry reports physical VLM calls")
    return registry.sort_values(["selector", "seed", "horizon_budget"]).reset_index(drop=True)


def run() -> None:
    if (OUT / "ceilings/per_trace_partition_ceiling.csv").exists():
        raise RuntimeError("ceiling output already exists; frozen gate will not overwrite")
    config_raw = json.loads(CONFIG_PATH.read_text())
    expected_hash = config_raw["source_hashes"]
    if sha(ROOT / "src/garc_eval/bcem_gate_v1/core.py") != expected_hash["bcem_core_py"]:
        raise RuntimeError("frozen BCEM core hash mismatch")
    if sha(ROOT / "src/garc_eval/bcem_gate_v1/ceiling.py") != expected_hash["bcem_ceiling_py"]:
        raise RuntimeError("frozen ceiling hash mismatch")
    if sha(STRICT / "scripts/benchmark_lib.py") != expected_hash["benchmark_lib_py"]:
        raise RuntimeError("frozen benchmark library hash mismatch")
    for rel in ["ceilings", "runs", "aggregates", "diagnostics", "tests", "logs"]:
        (OUT / rel).mkdir(parents=True, exist_ok=True)
    cfg = BCEMConfig(config_raw["core_cap_seconds"], config_raw["output_cap_seconds"],
                     config_raw["unit_seconds"], "evaluator_only_legal_partition_ceiling")
    benchmark = load_benchmark_lib()
    evaluator_cfg = json.loads((STRICT / "frozen_inputs/evaluator_config.json").read_text())
    units = pd.read_csv(STRICT / "frozen_inputs/units.csv")
    reference = pd.read_csv(STRICT / "frozen_inputs/event_reference.csv")
    reference = reference.sort_values(["start_time", "end_time"]).reset_index(drop=True)
    reference["duration_seconds"] = reference.end_time - reference.start_time
    nonpath = reference[reference.duration_seconds <= config_raw["ceiling_objective"]["pathological_reference_threshold_seconds"]].copy()
    registry = selected_registry(config_raw)
    rows, relation_rows, match_rows, trace_audit = [], [], [], []
    evaluator_hash = json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["compatibility"]["evaluator_hash"]
    for ordinal, reg in enumerate(registry.itertuples(index=False), 1):
        run_dir = STRICT / str(reg.run_path)
        trace_path = run_dir / "action_trace.csv"
        if not trace_path.exists() or sha(trace_path) != reg.action_trace_sha256:
            raise RuntimeError(f"trace hash mismatch: {reg.run_id}")
        trace = pd.read_csv(trace_path).sort_values("call_idx").reset_index(drop=True)
        if (len(trace) != int(reg.logical_oracle_calls)
                or len(trace) > int(reg.horizon_budget)
                or trace.unit_id.duplicated().any()):
            raise RuntimeError(f"trace budget/duplicate violation: {reg.run_id}")
        if set(trace.oracle_label_after_query.astype(str).str.lower()) - {"positive", "negative"}:
            raise RuntimeError(f"non-binary observation in frozen trace: {reg.run_id}")
        state = parse_observations(trace)
        edges = legal_group_edges(units, state, cfg) if state.positives else {}
        legal_count = count_legal_partitions(edges, len(state.positives))
        t0 = time.perf_counter()
        ceiling = exact_ceiling_partition(edges, len(state.positives), reference)
        certified = exact_ceiling_partition(edges, len(state.positives), reference, require_anchor_support=True)
        ceiling_nonpath = exact_ceiling_partition(edges, len(state.positives), nonpath)
        elapsed = time.perf_counter() - t0
        for partition in [ceiling.partition, certified.partition, ceiling_nonpath.partition]:
            assert_partition_invariants(partition, state, cfg)
        meta = {"benchmark_id": reg.benchmark_id, "run_id": reg.run_id, "method": reg.method,
                "method_variant": reg.method_variant, "seed": int(reg.seed),
                "horizon_budget": int(reg.horizon_budget)}
        mats = {}
        for name in ["original_k3", "k3_bridge_safe"]:
            mats[name] = benchmark.materialize_from_trace(trace, units, meta, name,
                                                           evaluator_cfg["materializers"][name])
        ceiling_segments = build_event_relation(ceiling.partition, state, cfg, meta,
                                                 materializer="evaluator_only_legal_partition_ceiling")
        cert_segments = build_event_relation(certified.partition, state, cfg, meta,
                                              materializer="evaluator_only_anchor_certified_ceiling")
        nonpath_segments = build_event_relation(ceiling_nonpath.partition, state, cfg, meta,
                                                 materializer="evaluator_only_nonpath_ceiling")
        evaluations = {}
        matches = {}
        for name, segments, refs in [
            ("original_k3", mats["original_k3"], reference),
            ("k3_safe", mats["k3_bridge_safe"], reference),
            ("ceiling", ceiling_segments, reference),
            ("original_k3_nonpath", mats["original_k3"], nonpath),
            ("k3_safe_nonpath", mats["k3_bridge_safe"], nonpath),
            ("ceiling_nonpath", nonpath_segments, nonpath),
        ]:
            matched, metrics = benchmark.evaluate_events(segments, refs, meta, evaluator_hash)
            evaluations[name] = metric_map(metrics)
            matches[name] = matched
        if abs(evaluations["ceiling"]["event_f1"] - ceiling.event_f1) > 1e-12:
            raise RuntimeError(f"ceiling DP disagrees with authoritative evaluator: {reg.run_id}")
        saved_metrics = pd.read_csv(run_dir / "metrics.csv")
        saved_f1 = float(saved_metrics[saved_metrics.metric_name == "event_f1"].metric_value.iloc[0])
        k3_repro_diff = abs(evaluations["k3_safe"]["event_f1"] - saved_f1)
        if k3_repro_diff > 1e-12:
            raise RuntimeError(f"K3-safe reproduction mismatch: {reg.run_id} diff={k3_repro_diff}")
        k3_partition = segments_partition(mats["k3_bridge_safe"])
        k3_cert_f1, k3_cert_matches = certified_f1(k3_partition, reference)
        cert_relation_f1, cert_matches = certified_f1(certified.partition, reference)
        ref_reached = sum(bool(set(read_ids(r.source_unit_ids)) & set(state.positives)) for r in reference.itertuples())
        standard_matches = matches["ceiling"]
        matched_predictions = set(standard_matches.loc[standard_matches.matched.astype(bool), "predicted_event_id"].astype(str))
        unmatched_groups = len(ceiling_segments) - len(matched_predictions)
        legal_violation = 0
        row = {
            "benchmark_id": reg.benchmark_id, "run_id": reg.run_id, "selector": reg.selector,
            "method": reg.method, "method_variant": reg.method_variant, "seed": int(reg.seed),
            "budget": int(reg.horizon_budget), "queried_positive_count": len(state.positives),
            "queried_negative_count": len(state.negatives), "queried_abstain_count": len(state.abstains),
            "k3_safe_event_f1": evaluations["k3_safe"]["event_f1"],
            "original_k3_event_f1": evaluations["original_k3"]["event_f1"],
            "legal_partition_ceiling_event_f1": evaluations["ceiling"]["event_f1"],
            "ceiling_minus_k3_safe": evaluations["ceiling"]["event_f1"] - evaluations["k3_safe"]["event_f1"],
            "ceiling_minus_original_k3": evaluations["ceiling"]["event_f1"] - evaluations["original_k3"]["event_f1"],
            "k3_safe_precision": evaluations["k3_safe"]["event_precision"],
            "k3_safe_recall": evaluations["k3_safe"]["event_recall"],
            "ceiling_precision": evaluations["ceiling"]["event_precision"],
            "ceiling_recall": evaluations["ceiling"]["event_recall"],
            "k3_safe_predicted_event_count": evaluations["k3_safe"]["predicted_event_count"],
            "original_k3_predicted_event_count": evaluations["original_k3"]["predicted_event_count"],
            "ceiling_predicted_event_count": evaluations["ceiling"]["predicted_event_count"],
            "reference_event_count": len(reference), "reference_events_reached_by_positive_evidence": ref_reached,
            "k3_safe_overmerge": evaluations["k3_safe"]["overmerge"],
            "k3_safe_oversplit": evaluations["k3_safe"]["oversplit"],
            "ceiling_overmerge": evaluations["ceiling"]["overmerge"],
            "ceiling_oversplit": evaluations["ceiling"]["oversplit"],
            "boundary_contribution": 0.0,
            "partition_only_contribution": evaluations["ceiling"]["event_f1"] - evaluations["k3_safe"]["event_f1"],
            "unmatched_positive_anchor_groups": unmatched_groups,
            "number_legal_partitions": str(legal_count), "barrier_block_count": barrier_block_count(state),
            "anchor_certified_k3_safe_f1": k3_cert_f1,
            "anchor_certified_ceiling_f1": cert_relation_f1,
            "anchor_certified_ceiling_minus_k3_safe": cert_relation_f1 - k3_cert_f1,
            "anchor_certified_k3_safe_matches": k3_cert_matches,
            "anchor_certified_ceiling_matches": cert_matches,
            "k3_safe_nonpath_f1": evaluations["k3_safe_nonpath"]["event_f1"],
            "ceiling_nonpath_f1": evaluations["ceiling_nonpath"]["event_f1"],
            "ceiling_minus_k3_safe_nonpath": evaluations["ceiling_nonpath"]["event_f1"] - evaluations["k3_safe_nonpath"]["event_f1"],
            "pathological_reference_count": len(reference) - len(nonpath),
            "ceiling_returned_seconds": evaluations["ceiling"]["returned_seconds"],
            "ceiling_dp_states_visited": ceiling.states_visited,
            "ceiling_cpu_seconds": elapsed, "legality_violations": legal_violation,
            "k3_safe_reproduction_abs_difference": k3_repro_diff,
        }
        rows.append(row)
        if len(ceiling_segments):
            out_relation = ceiling_segments.copy()
            out_relation.insert(0, "selector", reg.selector)
            relation_rows.append(out_relation)
        if len(standard_matches):
            out_matches = standard_matches.copy()
            out_matches.insert(0, "selector", reg.selector)
            match_rows.append(out_matches)
        trace_audit.append({"run_id": reg.run_id, "selector": reg.selector, "trace_path": str(trace_path.relative_to(ROOT)),
                            "expected_sha256": reg.action_trace_sha256, "observed_sha256": sha(trace_path),
                            "rows_expected": int(reg.logical_oracle_calls), "rows_observed": len(trace),
                            "duplicate_queries": int(trace.unit_id.duplicated().sum()), "status": "PASS"})
        if ordinal % 100 == 0:
            print(f"ceiling {ordinal}/{len(registry)}", flush=True)
    per_trace = pd.DataFrame(rows)
    per_trace.to_csv(OUT / "ceilings/per_trace_partition_ceiling.csv", index=False)
    pd.DataFrame(trace_audit).to_csv(OUT / "audit/FIXED_TRACE_INTEGRITY_AUDIT.csv", index=False)
    if relation_rows:
        pd.concat(relation_rows, ignore_index=True).to_csv(OUT / "runs/ceiling_event_relations.csv.gz", index=False, compression="gzip")
    if match_rows:
        pd.concat(match_rows, ignore_index=True).to_csv(OUT / "runs/ceiling_event_matches.csv.gz", index=False, compression="gzip")
    budget_cols = [c for c in per_trace if c.endswith("_f1") or c.startswith("ceiling_minus") or c in {
        "k3_safe_event_f1", "original_k3_event_f1", "legal_partition_ceiling_event_f1",
        "k3_safe_precision", "k3_safe_recall", "ceiling_precision", "ceiling_recall"}]
    per_budget = per_trace.groupby(["selector", "budget"])[budget_cols].mean().reset_index()
    per_budget.to_csv(OUT / "ceilings/per_budget_partition_ceiling.csv", index=False)
    selector_rows = []
    for selector, data in per_budget.groupby("selector"):
        data = data.sort_values("budget")
        x = data.budget.to_numpy(float)
        def auc(column: str) -> float:
            return float(np.trapezoid(data[column].to_numpy(float), x) / (x[-1] - x[0]))
        selector_rows.append({"selector": selector, "seeds": int(per_trace[per_trace.selector == selector].seed.nunique()),
            "traces": int((per_trace.selector == selector).sum()),
            "k3_safe_auc": auc("k3_safe_event_f1"), "original_k3_auc": auc("original_k3_event_f1"),
            "legal_partition_ceiling_auc": auc("legal_partition_ceiling_event_f1"),
            "ceiling_minus_k3_safe_auc": auc("legal_partition_ceiling_event_f1") - auc("k3_safe_event_f1"),
            "anchor_certified_k3_safe_auc": auc("anchor_certified_k3_safe_f1"),
            "anchor_certified_ceiling_auc": auc("anchor_certified_ceiling_f1"),
            "anchor_certified_ceiling_minus_k3_safe_auc": auc("anchor_certified_ceiling_f1") - auc("anchor_certified_k3_safe_f1"),
            "k3_safe_nonpath_auc": auc("k3_safe_nonpath_f1"), "ceiling_nonpath_auc": auc("ceiling_nonpath_f1"),
            "ceiling_minus_k3_safe_nonpath_auc": auc("ceiling_nonpath_f1") - auc("k3_safe_nonpath_f1")})
    per_selector = pd.DataFrame(selector_rows).sort_values("selector")
    per_selector.to_csv(OUT / "ceilings/per_selector_partition_ceiling.csv", index=False)
    decomposition = per_trace[["run_id", "selector", "seed", "budget", "ceiling_minus_k3_safe",
        "boundary_contribution", "partition_only_contribution", "anchor_certified_ceiling_minus_k3_safe",
        "ceiling_minus_k3_safe_nonpath", "reference_events_reached_by_positive_evidence",
        "unmatched_positive_anchor_groups", "pathological_reference_count"]]
    decomposition.to_csv(OUT / "ceilings/ceiling_gap_decomposition.csv", index=False)
    nonrandom = per_selector[per_selector.selector != "RANDOM_CONTROLLED"]
    eps = float(config_raw["headroom_gate"]["numerical_epsilon"])
    positive_selectors = int((nonrandom.ceiling_minus_k3_safe_auc > eps).sum())
    positive_nonpath = int((nonrandom.ceiling_minus_k3_safe_nonpath_auc > eps).sum())
    positive_certified = int((nonrandom.anchor_certified_ceiling_minus_k3_safe_auc > eps).sum())
    nonrandom_budget = per_budget[per_budget.selector != "RANDOM_CONTROLLED"].groupby("budget")[[
        "legal_partition_ceiling_event_f1", "k3_safe_event_f1"]].mean()
    positive_budgets = int(((nonrandom_budget.legal_partition_ceiling_event_f1 - nonrandom_budget.k3_safe_event_f1) > eps).sum())
    gate_cfg = config_raw["headroom_gate"]
    headroom_go = (
        positive_selectors >= gate_cfg["minimum_nonrandom_selector_variants_with_positive_auc_gap"]
        and positive_budgets >= gate_cfg["minimum_aggregate_budgets_with_positive_gap"]
        and positive_nonpath >= gate_cfg["minimum_nonrandom_selector_variants_with_positive_nonpathological_auc_gap"]
        and positive_certified >= gate_cfg["minimum_nonrandom_selector_variants_with_positive_anchor_certified_auc_gap"]
        and int(per_trace.legality_violations.sum()) == 0
    )
    decision = "MATERIALIZER_HEADROOM_GO" if headroom_go else "MATERIALIZER_HEADROOM_NO_GO"
    summary = {"decision": decision, "fixed_traces_evaluated": len(per_trace),
        "selectors_evaluated": per_trace.selector.nunique(), "budgets_evaluated": sorted(per_trace.budget.unique().tolist()),
        "selector_macro_k3_safe_auc": float(per_selector.k3_safe_auc.mean()),
        "selector_macro_legal_partition_ceiling_auc": float(per_selector.legal_partition_ceiling_auc.mean()),
        "selector_macro_ceiling_minus_k3_safe_auc": float(per_selector.ceiling_minus_k3_safe_auc.mean()),
        "nonrandom_positive_auc_gap_selectors": positive_selectors,
        "nonrandom_positive_nonpath_auc_gap_selectors": positive_nonpath,
        "nonrandom_positive_anchor_certified_gap_selectors": positive_certified,
        "aggregate_positive_gap_budgets": positive_budgets,
        "legality_violations": int(per_trace.legality_violations.sum()),
        "k3_safe_reproduction_max_abs_difference": float(per_trace.k3_safe_reproduction_abs_difference.max()),
        "pathological_reference_count": len(reference) - len(nonpath),
        "physical_vlm_calls": 0, "baseline_acquisition_reruns": 0,
        "ceiling_cpu_seconds": float(per_trace.ceiling_cpu_seconds.sum()),
        "peak_rss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)}
    (OUT / "aggregates/HEADROOM_GATE.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    report = f"""# Exact Legal-Partition Ceiling Report

Decision: `{decision}`.

Evaluated {len(per_trace)} frozen controlled traces, {per_trace.selector.nunique()} selector variants, and budgets {sorted(per_trace.budget.unique())}. No acquisition or VLM call was executed.

Selector-macro K3-safe AUC is {summary['selector_macro_k3_safe_auc']:.9f}; the exact legal-partition ceiling is {summary['selector_macro_legal_partition_ceiling_auc']:.9f}; the gap is {summary['selector_macro_ceiling_minus_k3_safe_auc']:+.9f}.

The frozen headroom requirements are met by {positive_selectors} non-random selector variants for standard AUC, {positive_nonpath} after excluding the single >40-second reference, {positive_certified} under anchor-certified matching, and {positive_budgets} aggregate budgets. Legality violations: 0. K3-safe reproduces saved metrics with maximum absolute difference {summary['k3_safe_reproduction_max_abs_difference']:.3g}.

All legal ceiling intervals are minimal positive-anchor convex hulls, so boundary contribution is fixed to zero and all gain is attributed to partition decisions. Full per-trace, per-budget, per-selector, anchor-certified, and pathological-reference sensitivity tables accompany this report.
"""
    (OUT / "ceilings/PARTITION_CEILING_REPORT.md").write_text(report)
    print(json.dumps(summary, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    main()
