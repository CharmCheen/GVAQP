#!/usr/bin/env python3
"""Fair ARC/RC-SEM time-budget replay on the old query-bound oracle cache.

This is a physical-latency-calibrated cached replay, not a physical run.  Both
methods receive the same cold-load charge, per-VERIFY mean complete-path charge,
frozen inputs, strict K3 materializer, and event evaluator.  The only method
difference is the causal query order already produced by the common-input
replay.  RC-SEM's failed risk gate means that only oracle-confirmed units are
published here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


METHOD_ARC = "ARC-CACHED-REPLAY-v1"
METHOD_RCSEM = "RC-SEM-CACHED-COMMON-v1"
METHODS = (METHOD_ARC, METHOD_RCSEM)
TIME_BUDGET_MINUTES = (2, 5, 10, 20, 30, 40)
SEEDS = (0, 1, 2, 3, 4)
MAX_CALLS = 100
DOMAIN = "dataset3_development"
PROMPT_SHA256 = "12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33"
EVALUATOR_SHA256 = "0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610"
K3_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_capacity(budget_seconds: float, load_seconds: float, verify_seconds: float) -> int:
    if verify_seconds <= 0:
        raise ValueError("verify_seconds must be positive")
    return max(0, math.floor((budget_seconds - load_seconds) / verify_seconds + 1e-12))


def load_cost_profile(probe_root: Path) -> dict[str, object]:
    protocol_path = probe_root / "PROBE_PROTOCOL.json"
    results_path = probe_root / "32b_results.json"
    summary_path = probe_root / "summary.json"
    protocol = json.loads(protocol_path.read_text())
    results = json.loads(results_path.read_text())
    summary = json.loads(summary_path.read_text())
    if protocol["prompt_sha256"] != PROMPT_SHA256:
        raise RuntimeError("physical probe prompt does not match the old query")
    totals = [float(row["stage_seconds"]["total"]) for row in results["calls"]]
    if not totals:
        raise RuntimeError("physical probe has no completed 32B calls")
    load_seconds = float(summary["load_seconds"]["32b"])
    return {
        "classification": "small_same_prompt_physical_probe_not_representative",
        "model": protocol["models"]["32b"],
        "prompt_sha256": protocol["prompt_sha256"],
        "cold_load_seconds": load_seconds,
        "complete_path_call_seconds": totals,
        "mean_complete_path_call_seconds": float(np.mean(totals)),
        "min_complete_path_call_seconds": min(totals),
        "max_complete_path_call_seconds": max(totals),
        "unique_clip_count": len({row["clip_id"] for row in results["calls"]}),
        "completed_call_count": len(totals),
        "protocol_sha256": sha256_file(protocol_path),
        "results_sha256": sha256_file(results_path),
        "summary_sha256": sha256_file(summary_path),
    }


def trace_path(common: Path, method: str, seed: int, logical_budget: int) -> Path:
    if method == METHOD_ARC:
        root = common / "selection_traces/arc_cached_replay_v1/arc_cached_replay_v1"
    else:
        root = common / "selection_traces/rc_sem_cached_common_v1"
    return root / DOMAIN / f"seed_{seed:03d}_budget_{logical_budget:03d}.csv"


def assert_prefix_stability(common: Path) -> None:
    checkpoints = (5, 10, 20, 50, 80)
    for method in METHODS:
        for seed in SEEDS:
            maximum = pd.read_csv(trace_path(common, method, seed, MAX_CALLS)).unit_id.tolist()
            for budget in checkpoints:
                observed = pd.read_csv(trace_path(common, method, seed, budget)).unit_id.tolist()
                if observed != maximum[:budget]:
                    raise RuntimeError(f"non-prefix causal trace: {method}, seed={seed}, B={budget}")


def markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for values in frame[list(columns)].itertuples(index=False, name=None):
        rendered = [f"{v:.3f}" if isinstance(v, (float, np.floating)) else str(v) for v in values]
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def execute(arc_root: Path, common: Path, probe_root: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)

    common_config = json.loads((common / "CONFIG.json").read_text())
    common_provenance = json.loads((common / "DATA_PROVENANCE.json").read_text())
    common_checks = json.loads((common / "validation_checks.json").read_text())
    if common_checks["status"] != "PASS":
        raise RuntimeError("source common-input replay did not pass validation")
    if common_config["evaluator_hash"] != EVALUATOR_SHA256:
        raise RuntimeError("source evaluator identity changed")
    if common_provenance["dataset3_prompt_hash"] != PROMPT_SHA256:
        raise RuntimeError("source cache does not match old query")
    diagnostics = pd.read_csv(common / "rcsem_per_run_diagnostics.csv")
    primary_diag = diagnostics[diagnostics.domain == DOMAIN]
    if primary_diag.risk_threshold_found.astype(bool).any() or primary_diag.probable_event_count.sum() != 0:
        raise RuntimeError("RC-SEM publication state changed; cached trace prefix is insufficient")
    assert_prefix_stability(common)

    benchmark_lib = arc_root / (
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
        "clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
    )
    if sha256_file(benchmark_lib) != EVALUATOR_SHA256:
        raise RuntimeError("shared evaluator bytes changed")
    bench = load_module("time_budget_benchmark", benchmark_lib)
    frozen = arc_root / "BSEC_AQP_Development_Gate_v1/outputs/native_arc_vs_pstr/frozen_inputs" / DOMAIN
    units = pd.read_csv(frozen / "units.csv")
    reference = pd.read_csv(frozen / "reference_events.csv")
    cost = load_cost_profile(probe_root)
    load_seconds = float(cost["cold_load_seconds"])
    verify_seconds = float(cost["mean_complete_path_call_seconds"])

    rows: list[dict[str, object]] = []
    for budget_minutes in TIME_BUDGET_MINUTES:
        budget_seconds = float(budget_minutes * 60)
        capacity = min(MAX_CALLS, call_capacity(budget_seconds, load_seconds, verify_seconds))
        for method in METHODS:
            for seed in SEEDS:
                full_trace = pd.read_csv(trace_path(common, method, seed, MAX_CALLS))
                trace = full_trace.iloc[:capacity].copy()
                variant = (
                    "causal_historical_arc_trace_strict_shared_k3"
                    if method == METHOD_ARC
                    else "cross_source_posterior_ranking_risk_gate_strict_shared_k3"
                )
                meta = {
                    "benchmark_id": str(units.benchmark_id.iloc[0]),
                    "run_id": f"time_budget_{method.lower()}_s{seed:03d}_t{budget_minutes:03d}m",
                    "method": method,
                    "method_variant": variant,
                    "seed": seed,
                    "horizon_budget": capacity,
                }
                predictions = bench.materialize_from_trace(
                    trace[["unit_id", "oracle_label_after_query"]],
                    units,
                    meta,
                    "k3_bridge_safe",
                    K3_CONFIG,
                )
                matches, metrics = bench.evaluate_events(predictions, reference, meta, EVALUATOR_SHA256)
                metric_map = dict(zip(metrics.metric_name, metrics.metric_value))
                positives = int((trace.oracle_label_after_query.str.lower() == "positive").sum())
                matched = int(matches.matched.astype(bool).sum()) if len(matches) else 0
                rows.append({
                    "domain": DOMAIN,
                    "method": method,
                    "method_variant": variant,
                    "seed": seed,
                    "time_budget_minutes": budget_minutes,
                    "time_budget_seconds": budget_seconds,
                    "logical_call_capacity": capacity,
                    "logical_oracle_calls": len(trace),
                    "calibrated_consumed_seconds": load_seconds + len(trace) * verify_seconds,
                    "verified_positive_units": positives,
                    "returned_event_count": len(predictions),
                    "matched_reference_events": matched,
                    "event_precision": float(metric_map["event_precision"]),
                    "event_recall": float(metric_map["event_recall"]),
                    "event_f1": float(metric_map["event_f1"]),
                })

    per_run = pd.DataFrame(rows).sort_values(["time_budget_minutes", "method", "seed"])
    per_run.to_csv(output / "per_run_metrics.csv", index=False)
    curve = per_run.groupby(["time_budget_minutes", "time_budget_seconds", "logical_call_capacity", "method"], as_index=False).agg(
        event_precision=("event_precision", "mean"),
        event_recall=("event_recall", "mean"),
        event_f1=("event_f1", "mean"),
        returned_event_count=("returned_event_count", "mean"),
        matched_reference_events=("matched_reference_events", "mean"),
    )
    curve.to_csv(output / "time_budget_curve.csv", index=False)
    wide = curve.pivot(index=["time_budget_minutes", "logical_call_capacity"], columns="method", values=["event_precision", "event_recall", "event_f1", "returned_event_count"]).reset_index()
    wide.columns = [
        "_".join(str(x) for x in col if str(x)) if isinstance(col, tuple) else str(col)
        for col in wide.columns
    ]
    short = {METHOD_ARC: "arc", METHOD_RCSEM: "rcsem"}
    wide = wide.rename(columns={c: c.replace(METHOD_ARC, short[METHOD_ARC]).replace(METHOD_RCSEM, short[METHOD_RCSEM]) for c in wide.columns})
    wide["delta_f1_rcsem_minus_arc"] = wide["event_f1_rcsem"] - wide["event_f1_arc"]
    columns = [
        "time_budget_minutes", "logical_call_capacity",
        "event_precision_arc", "event_precision_rcsem",
        "event_recall_arc", "event_recall_rcsem",
        "event_f1_arc", "event_f1_rcsem", "delta_f1_rcsem_minus_arc",
        "returned_event_count_arc", "returned_event_count_rcsem",
    ]
    table = markdown_table(wide, columns)
    report = f"""# ARC vs full RC-SEM under equal calibrated time budgets

## Result

{table}

Precision and recall are event-level seed means under the frozen evaluator.
An empty result has precision 0 by that evaluator's convention; returned-event
count is shown so this is not confused with a false-positive rate.

## Fair comparison contract

- Primary domain only: `{DOMAIN}`, whose old-query prompt is bound to
  `{PROMPT_SHA256}`.  The two provenance-incomplete `realcartest` derivatives
  are excluded.
- Both methods use identical frozen units, proxy cache, oracle-label cache,
  strict K3 (`g_max=1`, `d_core_max=40`, `d_seg_max=60`), and evaluator bytes.
- Both pay the same 32B cold load ({load_seconds:.3f} s) and the same mean
  complete-path VERIFY charge ({verify_seconds:.3f} s).  That mean comes from
  four calls over three content-blind clips using the identical prompt.
- Time excludes the already-materialized shared proxy/oracle cache construction
  for both methods.  Controller/K3/cache-read CPU time is not physically
  measured and is not charged to either method.
- ARC and RC-SEM traces are prefix-stable at every original checkpoint.  Each
  time cutoff therefore exposes the same number of oracle labels to both.
- RC-SEM's cross-source 0.80 precision risk gate failed, so the "full" method
  publishes zero unverified probable events.  Its result here is entirely the
  verified scheduling path; it should not be described as speculative gain.

## Evidence boundary

This is a **physical-latency-calibrated cached replay**, not a hard-deadline
physical run.  The four-call latency probe is too small to establish tail
latency or a safety bound.  It supports a fair expected-time x-axis only.
"""
    (output / "ARC_RCSEM_TIME_BUDGET_REPORT.md").write_text(report)

    config = {
        "schema_version": "ARC_RCSEM_TIME_BUDGET_REPLAY_V1",
        "classification": "physical_latency_calibrated_cached_replay_not_physical",
        "domain": DOMAIN,
        "time_budget_minutes": list(TIME_BUDGET_MINUTES),
        "capacity_rule": "floor((budget_seconds-cold_load_seconds)/mean_complete_path_verify_seconds)",
        "max_cached_trace_calls": MAX_CALLS,
        "seeds": list(SEEDS),
        "k3": {"name": "k3_bridge_safe", **K3_CONFIG},
        "empty_prediction_precision_convention": 0.0,
    }
    write_json(output / "CONFIG.json", config)
    write_json(output / "COST_PROFILE.json", cost)
    provenance = {
        "old_query_prompt_sha256": PROMPT_SHA256,
        "shared_evaluator_sha256": EVALUATOR_SHA256,
        "common_replay_path": str(common),
        "common_replay_config_sha256": sha256_file(common / "CONFIG.json"),
        "frozen_input_sha256": {
            name: sha256_file(frozen / name)
            for name in ("units.csv", "proxy_only.csv", "oracle_labels.csv", "reference_events.csv")
        },
        "excluded_domains": ["realcartest_0_1570", "realcartest_2000_3200"],
        "exclusion_reason": "missing prompt/parser identity in frozen derivative",
    }
    write_json(output / "DATA_PROVENANCE.json", provenance)
    expected_rows = len(TIME_BUDGET_MINUTES) * len(METHODS) * len(SEEDS)
    checks = {
        "status": "PASS",
        "expected_rows": expected_rows,
        "observed_rows": len(per_run),
        "equal_capacity_within_each_time_seed": bool(per_run.groupby(["time_budget_minutes", "seed"]).logical_oracle_calls.nunique().eq(1).all()),
        "all_calls_within_capacity": bool((per_run.logical_oracle_calls <= per_run.logical_call_capacity).all()),
        "all_consumed_time_within_budget": bool((per_run.calibrated_consumed_seconds <= per_run.time_budget_seconds + 1e-9).all()),
        "source_trace_prefix_stability": True,
        "zero_rcsem_probable_events": True,
        "metrics_finite": bool(np.isfinite(per_run[["event_precision", "event_recall", "event_f1"]].to_numpy()).all()),
    }
    if len(per_run) != expected_rows or not all(v for k, v in checks.items() if isinstance(v, bool)):
        checks["status"] = "FAIL"
    write_json(output / "validation_checks.json", checks)
    if checks["status"] != "PASS":
        raise RuntimeError(f"validation failed: {checks}")
    print(json.dumps(checks, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", type=Path, default=Path("/root/charm/GVAQP-arc-phys-baseline"))
    parser.add_argument("--common", type=Path, default=Path("outputs/arc_rcsem_common_replay"))
    parser.add_argument("--probe-root", type=Path, default=Path("/root/charm/GVAQP/outputs/binary_smdp_value_v1/hangzhou_physical"))
    parser.add_argument("--output", type=Path, default=Path("outputs/arc_rcsem_time_budget_replay_v1"))
    args = parser.parse_args()
    execute(args.arc_root.resolve(), args.common.resolve(), args.probe_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
