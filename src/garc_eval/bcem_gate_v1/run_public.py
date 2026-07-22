"""Evaluate the frozen public BCEM-DP on saved controlled traces only."""

from __future__ import annotations

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

from .ceiling import score_partition_ordered
from .core import BCEMConfig, Partition, assert_partition_invariants, parse_observations
from .public import IncrementalBCEM, batch_materialize
from .run_ceiling import load_benchmark_lib, selected_registry, sha


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run"
STRICT = BASE / "clean_baseline_benchmark_v2_strict"
OUT = BASE / "barrier_constrained_event_materialization_gate_v1"


def signature(frame: pd.DataFrame) -> tuple:
    if frame.empty:
        return ()
    columns = ["event_id", "start_time", "end_time", "anchor_unit_ids", "relation_hash"]
    return tuple(tuple(row) for row in frame[columns].itertuples(index=False, name=None))


def metric_map(metrics: pd.DataFrame) -> dict[str, float]:
    return {str(r.metric_name): float(r.metric_value) for r in metrics.itertuples()}


def family(selector: str) -> str:
    if selector.startswith("SUPG_"):
        return "SUPG"
    return selector.replace("_CONTROLLED", "").replace("_M1", "")


def mean_boundary(matches: pd.DataFrame, column: str) -> float:
    """Return a finite conditional mean; zero is paired with an explicit flag.

    Boundary error is undefined when no prediction is matched.  Gate artifacts
    require finite numeric metrics, so callers also emit
    ``public_bcem_boundary_error_defined`` to distinguish the finite sentinel
    from an observed zero error.
    """
    if matches.empty:
        return 0.0
    values = pd.to_numeric(matches.loc[matches.matched.astype(bool), column], errors="coerce").dropna()
    return float(values.mean()) if len(values) else 0.0


def boundary_error_defined(matches: pd.DataFrame) -> bool:
    if matches.empty:
        return False
    matched = matches.loc[matches.matched.astype(bool)]
    return bool(len(matched) and matched[["boundary_start_error", "boundary_end_error"]].notna().all(axis=None))


def anchor_certified_f1(partition: Partition, reference: pd.DataFrame) -> float:
    matched, _, _ = score_partition_ordered(partition, reference, require_anchor_support=True)
    denom = len(partition.groups) + len(reference)
    return 2.0 * matched / denom if denom else 0.0


def load_trace(row: object) -> pd.DataFrame:
    path = STRICT / str(getattr(row, "run_path")) / "action_trace.csv"
    if not path.exists() or sha(path) != getattr(row, "action_trace_sha256"):
        raise RuntimeError(f"trace hash mismatch: {getattr(row, 'run_id')}")
    trace = pd.read_csv(path).sort_values("call_idx").reset_index(drop=True)
    if len(trace) != int(getattr(row, "logical_oracle_calls")) or len(trace) > int(getattr(row, "horizon_budget")):
        raise RuntimeError(f"trace length mismatch: {getattr(row, 'run_id')}")
    return trace


def build_incremental_cache(registry: pd.DataFrame, units: pd.DataFrame, cfg: BCEMConfig) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    cache: dict[tuple[str, int], tuple] = {}
    diagnostic_rows = []
    prefix_rows = []
    for (selector, seed), group in registry.groupby(["selector", "seed"]):
        records = list(group.sort_values("horizon_budget").itertuples(index=False))
        maximal = max(records, key=lambda r: (len(load_trace(r)), int(r.horizon_budget)))
        max_trace = load_trace(maximal)
        max_pairs = list(zip(max_trace.unit_id.astype(int), max_trace.oracle_label_after_query.astype(str).str.lower()))
        for row in records:
            trace = load_trace(row)
            pairs = list(zip(trace.unit_id.astype(int), trace.oracle_label_after_query.astype(str).str.lower()))
            passed = pairs == max_pairs[:len(pairs)]
            prefix_rows.append({"selector": selector, "seed": int(seed), "run_id": row.run_id,
                                "rows": len(pairs), "maximal_run_id": maximal.run_id,
                                "is_exact_maximal_prefix": passed})
            engine = IncrementalBCEM(units, cfg)
            prefix = []
            final_signature = ()
            for call_index, (uid, label) in enumerate(pairs, 1):
                prefix.append({"unit_id": uid, "oracle_label_after_query": label})
                incremental, diag = engine.apply(uid, label)
                batch, batch_partition, _ = batch_materialize(units, pd.DataFrame(prefix), cfg)
                equal = signature(incremental) == signature(batch) and engine.partition.anchor_tuples == batch_partition.anchor_tuples
                if not equal:
                    raise RuntimeError(f"incremental/batch mismatch run={row.run_id} call={call_index}")
                final_signature = signature(incremental)
                diagnostic_rows.append({"run_id": row.run_id, "selector": selector, "seed": int(seed),
                    "call_index": call_index, "selected_unit_id": uid, "observation": label,
                    "incremental_batch_equal": equal, **diag})
            cache[(row.run_id, len(pairs))] = final_signature
    return cache, pd.DataFrame(diagnostic_rows), pd.DataFrame(prefix_rows)


def run() -> None:
    target = OUT / "runs/per_trace_public_bcem.csv"
    if target.exists():
        raise RuntimeError("public BCEM output already exists; frozen gate will not overwrite")
    headroom = json.loads((OUT / "aggregates/HEADROOM_GATE.json").read_text())
    if headroom["decision"] != "MATERIALIZER_HEADROOM_GO":
        raise RuntimeError("public phase is not authorized by headroom gate")
    gate = json.loads((OUT / "config/FROZEN_BCEM_CONFIG.json").read_text())
    objective = json.loads((OUT / "config/FROZEN_PUBLIC_BCEM_OBJECTIVE.json").read_text())
    if objective["reference_inputs"] or objective["constants_provenance"]["weights_tuned_on_reference"]:
        raise RuntimeError("public objective leakage declaration invalid")
    source_manifest = pd.read_csv(OUT / "config/SOURCE_MANIFEST.csv")
    for required_source in ["src/garc_eval/bcem_gate_v1/core.py", "src/garc_eval/bcem_gate_v1/public.py"]:
        source_row = source_manifest[source_manifest.path == required_source].iloc[0]
        if sha(ROOT / source_row.path) != source_row.sha256:
            raise RuntimeError(f"frozen public source hash mismatch: {required_source}")
    cfg = BCEMConfig(gate["core_cap_seconds"], gate["output_cap_seconds"], gate["unit_seconds"], objective["objective_id"])
    units = pd.read_csv(STRICT / "frozen_inputs/units.csv")
    reference = pd.read_csv(STRICT / "frozen_inputs/event_reference.csv").sort_values(["start_time", "end_time"]).reset_index(drop=True)
    reference["duration_seconds"] = reference.end_time - reference.start_time
    nonpath = reference[reference.duration_seconds <= gate["ceiling_objective"]["pathological_reference_threshold_seconds"]].copy()
    benchmark = load_benchmark_lib()
    evaluator_hash = json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["compatibility"]["evaluator_hash"]
    registry = selected_registry(gate)
    ceiling = pd.read_csv(OUT / "ceilings/per_trace_partition_ceiling.csv")
    incremental_cache, incremental_diag, prefix_audit = build_incremental_cache(registry, units, cfg)
    incremental_diag.to_csv(OUT / "diagnostics/incremental_equivalence.csv.gz", index=False, compression="gzip")
    prefix_audit.to_csv(OUT / "audit/TRACE_PREFIX_CONSISTENCY_AUDIT.csv", index=False)
    rows, relations, matches_out, ablations = [], [], [], []
    for ordinal, reg in enumerate(registry.itertuples(index=False), 1):
        trace = load_trace(reg)
        meta = {"benchmark_id": reg.benchmark_id, "run_id": reg.run_id, "method": reg.method,
                "method_variant": reg.method_variant, "seed": int(reg.seed), "horizon_budget": int(reg.horizon_budget)}
        relation, partition, diag = batch_materialize(units, trace, cfg, meta, "full")
        repeat, repeat_partition, _ = batch_materialize(units.sample(frac=1, random_state=17),
                                                        trace.sample(frac=1, random_state=19), cfg, meta, "full")
        deterministic = signature(relation) == signature(repeat) and partition.anchor_tuples == repeat_partition.anchor_tuples
        incremental_equal = signature(relation) == incremental_cache[(reg.run_id, len(trace))]
        if not deterministic or not incremental_equal:
            raise RuntimeError(f"determinism/incremental failure: {reg.run_id}")
        state = parse_observations(trace)
        assert_partition_invariants(partition, state, cfg)
        matched, metrics = benchmark.evaluate_events(relation, reference, meta, evaluator_hash)
        values = metric_map(metrics)
        _, nonpath_metrics = benchmark.evaluate_events(relation, nonpath, meta, evaluator_hash)
        nonpath_values = metric_map(nonpath_metrics)
        ceiling_row = ceiling[ceiling.run_id == reg.run_id]
        if len(ceiling_row) != 1:
            raise RuntimeError(f"missing ceiling row: {reg.run_id}")
        c = ceiling_row.iloc[0]
        coverage = tuple(a for group in partition.groups for a in group.anchors) == state.positives
        barriers = sum(any(group.anchors[0] < n < group.anchors[-1] for n in state.negatives) for group in partition.groups)
        core_violations = sum(group.span_seconds > cfg.core_cap_seconds + 1e-9 for group in partition.groups)
        output_violations = sum(group.span_seconds > cfg.output_cap_seconds + 1e-9 for group in partition.groups)
        row = {"run_id": reg.run_id, "selector": reg.selector, "selector_family": family(reg.selector),
            "method": reg.method, "method_variant": reg.method_variant, "seed": int(reg.seed),
            "budget": int(reg.horizon_budget), "logical_oracle_calls": int(reg.logical_oracle_calls),
            "k3_safe_event_f1": c.k3_safe_event_f1, "original_k3_event_f1": c.original_k3_event_f1,
            "legal_partition_ceiling_event_f1": c.legal_partition_ceiling_event_f1,
            "public_bcem_event_f1": values["event_f1"],
            "public_bcem_minus_k3_safe": values["event_f1"] - c.k3_safe_event_f1,
            "ceiling_minus_public_bcem": c.legal_partition_ceiling_event_f1 - values["event_f1"],
            "public_bcem_precision": values["event_precision"], "public_bcem_recall": values["event_recall"],
            "public_bcem_event_count_error": values["event_count_error"],
            "public_bcem_predicted_event_count": values["predicted_event_count"],
            "public_bcem_overmerge": values["overmerge"], "public_bcem_oversplit": values["oversplit"],
            "public_bcem_matched_mean_iou": values["matched_mean_iou"],
            "public_bcem_returned_seconds": values["returned_seconds"],
            "public_bcem_mean_boundary_start_error": mean_boundary(matched, "boundary_start_error"),
            "public_bcem_mean_boundary_end_error": mean_boundary(matched, "boundary_end_error"),
            "public_bcem_boundary_error_defined": boundary_error_defined(matched),
            "public_bcem_anchor_certified_f1": anchor_certified_f1(partition, reference),
            "public_bcem_nonpath_f1": nonpath_values["event_f1"], "k3_safe_nonpath_f1": c.k3_safe_nonpath_f1,
            "public_bcem_minus_k3_safe_nonpath": nonpath_values["event_f1"] - c.k3_safe_nonpath_f1,
            "positive_anchor_coverage_pass": coverage, "barrier_safety_violations": barriers,
            "core_cap_violations": core_violations, "output_cap_violations": output_violations,
            "deterministic_replay_pass": deterministic, "incremental_batch_equivalence_pass": incremental_equal,
            "batch_cpu_seconds": diag["cpu_seconds"], "batch_legal_edges": diag["legal_edges"],
            "observed_region_size": diag["observed_region_size"],
            "physical_vlm_calls": 0, "baseline_acquisition_reruns": 0}
        rows.append(row)
        if len(relation):
            out = relation.copy(); out.insert(0, "selector", reg.selector); relations.append(out)
        if len(matched):
            out = matched.copy(); out.insert(0, "selector", reg.selector); matches_out.append(out)
        for variant, label in [("full", "FULL"), ("without_duration", "WITHOUT_DURATION_COST"),
                               ("without_gap", "WITHOUT_UNQUERIED_GAP_COST")]:
            if variant == "full":
                ab_relation, ab_partition = relation, partition
            else:
                ab_relation, ab_partition, _ = batch_materialize(units, trace, cfg, meta, variant)
            _, ab_metrics = benchmark.evaluate_events(ab_relation, reference, meta, evaluator_hash)
            av = metric_map(ab_metrics)
            ablations.append({"run_id": reg.run_id, "selector": reg.selector, "selector_family": family(reg.selector),
                "seed": int(reg.seed), "budget": int(reg.horizon_budget), "ablation": label,
                "event_f1": av["event_f1"], "predicted_event_count": av["predicted_event_count"],
                "positive_anchor_coverage_pass": tuple(a for g in ab_partition.groups for a in g.anchors) == state.positives})
        if ordinal % 100 == 0:
            print(f"public {ordinal}/{len(registry)}", flush=True)
    per_trace = pd.DataFrame(rows)
    per_trace.to_csv(target, index=False)
    if relations:
        pd.concat(relations, ignore_index=True).to_csv(OUT / "runs/public_bcem_event_relations.csv.gz", index=False, compression="gzip")
    if matches_out:
        pd.concat(matches_out, ignore_index=True).to_csv(OUT / "runs/public_bcem_event_matches.csv.gz", index=False, compression="gzip")
    ablation_frame = pd.DataFrame(ablations)
    ablation_frame.to_csv(OUT / "diagnostics/public_bcem_ablations.csv.gz", index=False, compression="gzip")
    metrics_cols = ["k3_safe_event_f1", "original_k3_event_f1", "legal_partition_ceiling_event_f1",
                    "public_bcem_event_f1", "public_bcem_precision", "public_bcem_recall",
                    "public_bcem_event_count_error", "public_bcem_overmerge", "public_bcem_oversplit",
                    "public_bcem_nonpath_f1", "k3_safe_nonpath_f1", "public_bcem_anchor_certified_f1"]
    per_budget = per_trace.groupby(["selector", "selector_family", "budget"])[metrics_cols].mean().reset_index()
    per_budget["public_bcem_minus_k3_safe"] = per_budget.public_bcem_event_f1 - per_budget.k3_safe_event_f1
    per_budget["public_bcem_minus_k3_safe_nonpath"] = per_budget.public_bcem_nonpath_f1 - per_budget.k3_safe_nonpath_f1
    per_budget.to_csv(OUT / "aggregates/public_bcem_per_budget.csv", index=False)
    selector_rows = []
    for (selector, selector_family), data in per_budget.groupby(["selector", "selector_family"]):
        data = data.sort_values("budget"); x = data.budget.to_numpy(float)
        auc = lambda col: float(np.trapezoid(data[col].to_numpy(float), x) / (x[-1] - x[0]))
        selector_rows.append({"selector": selector, "selector_family": selector_family,
            "k3_safe_auc": auc("k3_safe_event_f1"), "original_k3_auc": auc("original_k3_event_f1"),
            "public_bcem_auc": auc("public_bcem_event_f1"),
            "public_bcem_minus_k3_safe_auc": auc("public_bcem_event_f1") - auc("k3_safe_event_f1"),
            "ceiling_auc": auc("legal_partition_ceiling_event_f1"),
            "public_bcem_nonpath_auc": auc("public_bcem_nonpath_f1"),
            "k3_safe_nonpath_auc": auc("k3_safe_nonpath_f1"),
            "public_bcem_minus_k3_safe_nonpath_auc": auc("public_bcem_nonpath_f1") - auc("k3_safe_nonpath_f1")})
    per_selector = pd.DataFrame(selector_rows)
    per_selector.to_csv(OUT / "aggregates/public_bcem_per_selector.csv", index=False)
    family_budget = per_budget.groupby(["selector_family", "budget"])[metrics_cols].mean().reset_index()
    family_rows = []
    for selector_family, data in family_budget.groupby("selector_family"):
        data = data.sort_values("budget"); x = data.budget.to_numpy(float)
        auc = lambda col: float(np.trapezoid(data[col].to_numpy(float), x) / (x[-1] - x[0]))
        family_rows.append({"selector_family": selector_family, "k3_safe_auc": auc("k3_safe_event_f1"),
            "public_bcem_auc": auc("public_bcem_event_f1"),
            "public_bcem_minus_k3_safe_auc": auc("public_bcem_event_f1") - auc("k3_safe_event_f1"),
            "public_bcem_nonpath_auc": auc("public_bcem_nonpath_f1"),
            "k3_safe_nonpath_auc": auc("k3_safe_nonpath_f1"),
            "public_bcem_minus_k3_safe_nonpath_auc": auc("public_bcem_nonpath_f1") - auc("k3_safe_nonpath_f1")})
    per_family = pd.DataFrame(family_rows)
    per_family.to_csv(OUT / "aggregates/public_bcem_per_family.csv", index=False)
    eps = float(gate["headroom_gate"]["numerical_epsilon"])
    nonrandom = per_family[per_family.selector_family != "RANDOM"]
    positive_families = int((nonrandom.public_bcem_minus_k3_safe_auc > eps).sum())
    positive_nonpath_families = int((nonrandom.public_bcem_minus_k3_safe_nonpath_auc > eps).sum())
    nonrandom_budget = family_budget[family_budget.selector_family != "RANDOM"].groupby("budget")[["public_bcem_event_f1", "k3_safe_event_f1"]].mean()
    positive_budgets = int(((nonrandom_budget.public_bcem_event_f1 - nonrandom_budget.k3_safe_event_f1) > eps).sum())
    safety = bool(per_trace.positive_anchor_coverage_pass.all() and
                  per_trace[["barrier_safety_violations", "core_cap_violations", "output_cap_violations"]].to_numpy().sum() == 0)
    correctness = bool(per_trace.deterministic_replay_pass.all()
                       and per_trace.incremental_batch_equivalence_pass.all())
    macro_k3 = float(per_family.k3_safe_auc.mean())
    macro_public = float(per_family.public_bcem_auc.mean())
    operator_go = (macro_public - macro_k3 > eps and positive_families >= 2 and positive_budgets >= 2
                   and positive_nonpath_families >= 2 and safety and correctness)
    decision = "BCEM_OPERATOR_GO" if operator_go else "PUBLIC_BCEM_NO_GO"
    summary = {"decision": decision, "headroom_decision": headroom["decision"],
        "fixed_traces_evaluated": len(per_trace), "selectors_evaluated": per_trace.selector.nunique(),
        "selector_families_evaluated": per_trace.selector_family.nunique(), "budgets_evaluated": sorted(per_trace.budget.unique().tolist()),
        "family_macro_k3_safe_auc": macro_k3, "family_macro_public_bcem_auc": macro_public,
        "family_macro_public_bcem_minus_k3_safe_auc": macro_public - macro_k3,
        "nonrandom_positive_auc_gap_families": positive_families,
        "nonrandom_positive_nonpath_gap_families": positive_nonpath_families,
        "aggregate_positive_gap_budgets": positive_budgets,
        "positive_anchor_coverage_pass": bool(per_trace.positive_anchor_coverage_pass.all()),
        "barrier_safety_pass": int(per_trace.barrier_safety_violations.sum()) == 0,
        "cap_enforcement_pass": int(per_trace.core_cap_violations.sum() + per_trace.output_cap_violations.sum()) == 0,
        "determinism_pass": bool(per_trace.deterministic_replay_pass.all()),
        "incremental_equivalence_pass": bool(per_trace.incremental_batch_equivalence_pass.all()),
        "incremental_prefix_checks": len(incremental_diag),
        "public_bcem_batch_cpu_seconds": float(per_trace.batch_cpu_seconds.sum()),
        "incremental_cpu_seconds": float(incremental_diag.cpu_seconds.sum()),
        "peak_rss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "maximum_recomputed_observed_region_size": int(incremental_diag.observed_region_size.max()),
        "maximum_affected_anchor_suffix_size": int(incremental_diag.affected_anchor_suffix_size.max()),
        "physical_vlm_calls": 0, "baseline_acquisition_reruns": 0}
    (OUT / "aggregates/PUBLIC_BCEM_GATE.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    run()
