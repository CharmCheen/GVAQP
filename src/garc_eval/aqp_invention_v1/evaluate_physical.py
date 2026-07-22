"""Post-hoc evaluator for the frozen VERA physical pilot.

The strict event reference enters only here, never in inference-time state.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .contract import owner_accepts, reconcile_owned_fragments
from .physical_common import (
    PACKAGE,
    PHYSICAL,
    ROOT,
    STRICT,
    atomic_csv,
    atomic_json,
    atomic_text,
    load_json,
    sha256_file,
    verify_freeze,
)


def _benchmark_module():
    path = STRICT / "scripts/benchmark_lib.py"
    spec = importlib.util.spec_from_file_location("vera_frozen_benchmark_lib", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load strict benchmark evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_results() -> list[dict[str, Any]]:
    return [
        load_json(path)
        for path in sorted((PHYSICAL / "attempts").glob("*.complete.json"))
    ]


def _call_ledger(results: list[dict[str, Any]]) -> pd.DataFrame:
    started_paths = sorted((PHYSICAL / "attempts").glob("*.started.json"))
    complete = {row["attempt_id"]: row for row in results}
    rows = []
    for started_path in started_paths:
        started = load_json(started_path)
        attempt_id = started["attempt_id"]
        result = complete.get(attempt_id, {})
        task = started["task"]
        rows.append({
            "attempt_id": attempt_id,
            "operator": started["operator"],
            "role": task.get("role"),
            "window_id": task.get("window_id", ""),
            "unit_id": task.get("unit_id", ""),
            "input_start": task.get("input_start"),
            "input_end": task.get("input_end"),
            "core_start": task.get("core_start"),
            "core_end": task.get("core_end"),
            "frame_count": result.get("frame_count", task.get("frame_count")),
            "input_identity_sha256": started["input_identity_sha256"],
            "rendered_prompt_sha256": started["rendered_prompt_sha256"],
            "raw_response_path": result.get("raw_response_path"),
            "raw_response_sha256": result.get("raw_response_sha256"),
            "status": result.get("status", "UNCERTAIN_INTERRUPTED"),
            "parse_status": result.get("parse_status", "not_completed"),
            "decision_gpu_seconds": result.get("decision_gpu_seconds", math.nan),
            "cuda_event_seconds": result.get("cuda_event_seconds", math.nan),
            "generation_wall_seconds": result.get("generation_wall_seconds", math.nan),
            "total_call_wall_seconds": result.get("total_call_wall_seconds", math.nan),
            "frame_decode_hash_seconds": result.get("frame_decode_hash_seconds", math.nan),
            "processor_seconds": result.get("processor_seconds", math.nan),
            "input_token_count": result.get("input_token_count", math.nan),
            "output_token_count": result.get("output_token_count", math.nan),
            "peak_memory_bytes": result.get("peak_memory_bytes", math.nan),
            "retry_number": result.get("retry_number", 0),
            "cache_reuse": result.get("cache_reuse", False),
            "cold_warm_state": result.get("cold_warm_state", "unknown"),
            "physical_call_count": 1,
        })
    return pd.DataFrame(rows)


def _enumeration_fragments(
    results: list[dict[str, Any]], timeline_end: float, ownership: bool,
) -> list[dict[str, Any]]:
    fragments = []
    for result in results:
        if result.get("operator") != "EVENT_ENUMERATE" or result.get("status") != "VALID":
            continue
        parsed = result.get("parsed_response") or {}
        if parsed.get("clip_status") != "ok":
            continue
        task = result["task"]
        for local_index, event in enumerate(parsed["events"]):
            absolute_start = float(task["input_start"]) + float(event["event_start"])
            absolute_end = float(task["input_start"]) + float(event["event_end"])
            accepted = owner_accepts(
                absolute_start, absolute_end,
                float(task["core_start"]), float(task["core_end"]), timeline_end,
            )
            fragments.append({
                "fragment_id": f"{result['attempt_id']}_event_{local_index:02d}",
                "source_window_id": task["window_id"],
                "attempt_id": result["attempt_id"],
                "start_time": absolute_start,
                "end_time": absolute_end,
                "core_start": float(task["core_start"]),
                "core_end": float(task["core_end"]),
                "input_start": float(task["input_start"]),
                "input_end": float(task["input_end"]),
                "owned": accepted,
                **event,
            })
    return [row for row in fragments if row["owned"] or not ownership]


def _dense_fallback_segments(results: list[dict[str, Any]], units: pd.DataFrame) -> list[dict[str, Any]]:
    positives = []
    for result in results:
        if result.get("operator") != "DENSE_UNIT_FALLBACK" or result.get("status") != "VALID":
            continue
        parsed = result.get("parsed_response") or {}
        if parsed.get("label") == "positive":
            positives.append(int(result["task"]["unit_id"]))
    groups: list[list[int]] = []
    for unit_id in sorted(set(positives)):
        if groups and unit_id == groups[-1][-1] + 1:
            groups[-1].append(unit_id)
        else:
            groups.append([unit_id])
    by_id = units.set_index("unit_id")
    rows = []
    for index, group in enumerate(groups):
        rows.append({
            "fragment_id": f"dense_fallback_group_{index:04d}",
            "source_window_id": "DENSE_FALLBACK",
            "attempt_id": "|".join(f"dense_fallback_u{x:04d}_a001" for x in group),
            "start_time": float(by_id.loc[group[0], "start_time"]),
            "end_time": float(by_id.loc[group[-1], "end_time"]),
            "core_start": float(by_id.loc[group[0], "start_time"]),
            "core_end": float(by_id.loc[group[-1], "end_time"]),
            "input_start": float(by_id.loc[group[0], "start_time"]),
            "input_end": float(by_id.loc[group[-1], "end_time"]),
            "owned": True,
            "event_type": "enter_ego_path",
            "involved_object": "unknown",
            "object_identity": f"K3-safe dense fallback units {'|'.join(map(str, group))}",
            "ego_relevant": True,
            "boundary_status": "uncertain",
            "complete_event_visible": False,
            "confidence": "medium",
            "evidence": "preregistered dense fallback positive unit group",
            "fallback_unit_ids": "|".join(map(str, group)),
        })
    return rows


def _segments(fragments: Iterable[dict[str, Any]], units: pd.DataFrame, variant: str) -> pd.DataFrame:
    unit_rows = units[["unit_id", "start_time", "end_time"]]
    confidence = {"low": 0.33, "medium": 0.67, "high": 1.0}
    rows = []
    for index, fragment in enumerate(fragments):
        start, end = float(fragment["start_time"]), float(fragment["end_time"])
        overlap = unit_rows[(unit_rows.end_time > start) & (unit_rows.start_time < end)]
        ids = overlap.unit_id.astype(int).tolist()
        rows.append({
            "benchmark_id": "cbbv2_514c0d360fd5b2a4b5fe",
            "run_id": f"vera_physical_{variant}",
            "method": "VERA",
            "method_variant": variant,
            "seed": 20260711,
            "horizon_budget": 200,
            "event_id": f"vera_{variant}_{index:04d}",
            "start_time": start,
            "core_start_time": start,
            "core_end_time": end,
            "end_time": end,
            "anchor_unit_ids": "|".join(map(str, ids)),
            "evidence_unit_ids": "|".join(map(str, ids)),
            "num_positive_anchors": 0,
            "num_negative_barriers": 0,
            "verification_state": "physical_event_enumeration",
            "confidence": confidence.get(str(fragment.get("confidence")), 0.0),
            "returned_seconds": end - start,
            "materializer": "vera_single_owner_relation_composer_v1",
            "materializer_config_hash": sha256_file(PHYSICAL / "FROZEN_PHYSICAL_CONFIG.json"),
        })
    return pd.DataFrame(rows)


def _metric_dict(metrics: pd.DataFrame) -> dict[str, float]:
    return {str(row.metric_name): float(row.metric_value) for row in metrics.itertuples()}


def _evaluate(benchmark: Any, predicted: pd.DataFrame, reference: pd.DataFrame, variant: str):
    run_meta = {
        "benchmark_id": "cbbv2_514c0d360fd5b2a4b5fe",
        "run_id": f"vera_physical_{variant}",
        "method": "VERA",
        "method_variant": variant,
        "seed": 20260711,
        "horizon_budget": 200,
    }
    evaluator_hash = sha256_file(STRICT / "scripts/benchmark_lib.py")
    return benchmark.evaluate_events(predicted, reference, run_meta, evaluator_hash)


def _prefix_curve(
    benchmark: Any,
    results: list[dict[str, Any]],
    reference: pd.DataFrame,
    units: pd.DataFrame,
    timeline_end: float,
    fallback_fragments: list[dict[str, Any]],
) -> pd.DataFrame:
    ordered = sorted(
        [r for r in results if r.get("operator") == "EVENT_ENUMERATE"],
        key=lambda r: int(r["task"]["order"]),
    )
    cumulative_gpu = 0.0
    cumulative_wall = 0.0
    rows = []
    partial: list[dict[str, Any]] = []
    for call_index, result in enumerate(ordered, 1):
        cumulative_gpu += float(result.get("decision_gpu_seconds") or 0.0)
        cumulative_wall += float(result.get("total_call_wall_seconds") or 0.0)
        partial.extend(_enumeration_fragments([result], timeline_end, ownership=True))
        composed = reconcile_owned_fragments(partial)
        predicted = _segments(composed, units, f"prefix_{call_index:03d}")
        _, metrics = _evaluate(benchmark, predicted, reference, f"prefix_{call_index:03d}")
        values = _metric_dict(metrics)
        rows.append({
            "stage": "enumeration_prefix",
            "selected_logical_calls": call_index,
            "selected_physical_calls": call_index,
            "cumulative_gpu_seconds": cumulative_gpu,
            "cumulative_wall_seconds": cumulative_wall,
            "event_precision": values["event_precision"],
            "event_recall": values["event_recall"],
            "event_f1": values["event_f1"],
            "predicted_event_count": values["predicted_event_count"],
        })
    fallback_results = [r for r in results if r.get("operator") == "DENSE_UNIT_FALLBACK"]
    if fallback_results:
        cumulative_gpu += sum(float(r.get("decision_gpu_seconds") or 0.0) for r in fallback_results)
        cumulative_wall += sum(float(r.get("total_call_wall_seconds") or 0.0) for r in fallback_results)
        composed = reconcile_owned_fragments(partial) + fallback_fragments
        predicted = _segments(composed, units, "with_fallback")
        _, metrics = _evaluate(benchmark, predicted, reference, "with_fallback")
        values = _metric_dict(metrics)
        rows.append({
            "stage": "dense_fallback_complete",
            "selected_logical_calls": len(ordered) + len(fallback_results),
            "selected_physical_calls": len(ordered) + len(fallback_results),
            "cumulative_gpu_seconds": cumulative_gpu,
            "cumulative_wall_seconds": cumulative_wall,
            "event_precision": values["event_precision"],
            "event_recall": values["event_recall"],
            "event_f1": values["event_f1"],
            "predicted_event_count": values["predicted_event_count"],
        })
    return pd.DataFrame(rows)


def evaluate() -> dict[str, Any]:
    config = verify_freeze()
    (PACKAGE / "results").mkdir(parents=True, exist_ok=True)
    (PACKAGE / "diagnostics").mkdir(parents=True, exist_ok=True)
    benchmark = _benchmark_module()
    results = _complete_results()
    ledger = _call_ledger(results)
    max_calls = int(config["plan"]["maximum_physical_calls"])
    if len(ledger) > max_calls:
        raise RuntimeError(f"physical-call cap violated: {len(ledger)} > {max_calls}")
    ledger.to_csv(PHYSICAL / "CALL_LEDGER.csv", index=False)

    units = pd.read_csv(STRICT / "frozen_inputs/unit_table.csv")
    reference = pd.read_csv(STRICT / "frozen_inputs/event_reference.csv")
    timeline_end = float(config["video"]["duration_seconds"])
    all_enum = _enumeration_fragments(results, timeline_end, ownership=False)
    owned_enum = [x for x in all_enum if x["owned"]]
    reconciled_enum = reconcile_owned_fragments(owned_enum)
    fallback_fragments = _dense_fallback_segments(results, units)
    full_fragments = reconciled_enum + fallback_fragments
    pd.DataFrame(all_enum).to_csv(PACKAGE / "results/VERA_EVENT_FRAGMENTS.csv", index=False)
    full_segments = _segments(full_fragments, units, "full")
    full_segments.to_csv(PACKAGE / "results/VERA_EVENT_SEGMENTS.csv", index=False)
    matches, metrics = _evaluate(benchmark, full_segments, reference, "full")
    matches.to_csv(PACKAGE / "results/VERA_EVENT_MATCHES.csv", index=False)
    metrics.to_csv(PACKAGE / "results/VERA_METRICS_LONG.csv", index=False)
    values = _metric_dict(metrics)

    ablation_specs = {
        "VERA_full": full_fragments,
        "without_single_owner": all_enum + fallback_fragments,
        "without_exact_duplicate_reconciliation": owned_enum + fallback_fragments,
        "without_dense_fallback": reconciled_enum,
    }
    ablation_rows = []
    for name, fragments in ablation_specs.items():
        predicted = _segments(fragments, units, name)
        _, ablation_metrics = _evaluate(benchmark, predicted, reference, name)
        metric = _metric_dict(ablation_metrics)
        ablation_rows.append({
            "variant": name,
            "event_precision": metric["event_precision"],
            "event_recall": metric["event_recall"],
            "event_f1": metric["event_f1"],
            "predicted_event_count": metric["predicted_event_count"],
            "physical_reuse": True,
            "interpretation_scope": "relation-composition ablation on identical raw outputs",
        })
    pd.DataFrame(ablation_rows).to_csv(PACKAGE / "results/PHYSICAL_ABLATIONS.csv", index=False)

    prefix = _prefix_curve(
        benchmark, results, reference, units, timeline_end, fallback_fragments
    )
    prefix.to_csv(PACKAGE / "results/VERA_PREFIX_CURVE.csv", index=False)

    cal = ledger[ledger.operator == "DENSE_UNIT_CALIBRATION"].copy()
    selected = ledger[ledger.operator.isin(["EVENT_ENUMERATE", "DENSE_UNIT_FALLBACK"])].copy()
    valid_cal_costs = cal.loc[cal.decision_gpu_seconds.notna(), "decision_gpu_seconds"].astype(float)
    if valid_cal_costs.empty:
        dense_median_gpu = math.nan
        dense_gpu = math.nan
    else:
        dense_median_gpu = float(valid_cal_costs.median())
        dense_gpu = 347.0 * dense_median_gpu
    selected_gpu = float(selected.decision_gpu_seconds.fillna(0).sum())
    gpu_ratio = selected_gpu / dense_gpu if dense_gpu and math.isfinite(dense_gpu) else math.inf
    dense_median_wall = float(cal.total_call_wall_seconds.dropna().astype(float).median()) if cal.total_call_wall_seconds.notna().any() else math.nan
    selected_wall = float(selected.total_call_wall_seconds.fillna(0).sum())
    dense_wall = dense_median_wall * 347 if math.isfinite(dense_median_wall) else math.nan
    run_metadata = load_json(PHYSICAL / "RUN_METADATA.json") if (PHYSICAL / "RUN_METADATA.json").exists() else {}
    model_load = float(run_metadata.get("model_load_wall_seconds", math.nan))
    cost_rows = [
        {"metric": "physical_attempts_all_roles", "value": len(ledger), "unit": "calls"},
        {"metric": "selected_algorithm_calls", "value": len(selected), "unit": "calls"},
        {"metric": "calibration_calls", "value": len(cal), "unit": "calls"},
        {"metric": "selected_gpu_seconds", "value": selected_gpu, "unit": "seconds"},
        {"metric": "dense_median_gpu_seconds_per_unit", "value": dense_median_gpu, "unit": "seconds"},
        {"metric": "estimated_dense_gpu_seconds", "value": dense_gpu, "unit": "seconds"},
        {"metric": "gpu_cost_ratio", "value": gpu_ratio, "unit": "ratio"},
        {"metric": "selected_warm_wall_seconds", "value": selected_wall, "unit": "seconds"},
        {"metric": "estimated_dense_warm_wall_seconds", "value": dense_wall, "unit": "seconds"},
        {"metric": "model_load_wall_seconds", "value": model_load, "unit": "seconds"},
        {"metric": "selected_cold_wall_seconds", "value": model_load + selected_wall, "unit": "seconds"},
        {"metric": "estimated_dense_cold_wall_seconds", "value": model_load + dense_wall, "unit": "seconds"},
        {"metric": "cold_index_cost", "value": 0.0, "unit": "seconds"},
        {"metric": "selected_frame_count", "value": float(selected.frame_count.fillna(0).sum()), "unit": "frames"},
        {"metric": "selected_peak_memory_bytes", "value": float(selected.peak_memory_bytes.max()), "unit": "bytes"},
    ]
    for workload in [1, 10, 100]:
        cost_rows.append({
            "metric": f"selected_model_load_amortized_wall_W{workload}",
            "value": selected_wall + model_load / workload,
            "unit": "seconds_per_query",
        })
    pd.DataFrame(cost_rows).to_csv(PACKAGE / "results/PHYSICAL_COST_SUMMARY.csv", index=False)

    recall_threshold_rows = []
    for threshold in [0.5, 0.8, 0.9]:
        reached = prefix[prefix.event_recall >= threshold]
        first = reached.iloc[0] if not reached.empty else None
        recall_threshold_rows.append({
            "target_recall": threshold,
            "achieved": first is not None,
            "selected_calls": int(first.selected_physical_calls) if first is not None else "",
            "gpu_seconds": float(first.cumulative_gpu_seconds) if first is not None else "",
        })
    pd.DataFrame(recall_threshold_rows).to_csv(PACKAGE / "results/COST_TO_RECALL.csv", index=False)

    same_cost_grid = config["baseline_comparison"]["same_cost_grid_dense_equivalent_units"]
    auc_points = []
    for budget in same_cost_grid:
        available = prefix[prefix.cumulative_gpu_seconds <= float(budget) * dense_median_gpu + 1e-12]
        row = available.iloc[-1] if not available.empty else None
        auc_points.append({
            "dense_equivalent_unit_budget": budget,
            "event_f1": float(row.event_f1) if row is not None else 0.0,
            "event_recall": float(row.event_recall) if row is not None else 0.0,
            "actual_gpu_seconds": float(row.cumulative_gpu_seconds) if row is not None else 0.0,
        })
    auc_frame = pd.DataFrame(auc_points)
    physical_auc = float(np.trapezoid(auc_frame.event_f1, auc_frame.dense_equivalent_unit_budget) / (max(same_cost_grid) - min(same_cost_grid)))
    auc_frame["physical_cost_normalized_event_f1_auc"] = physical_auc
    auc_frame.to_csv(PACKAGE / "results/VERA_SAME_COST_AUC.csv", index=False)

    # Determinism/reproducibility diagnostic: compare calibration labels to the
    # pre-existing strict outputs only after inference has completed.
    strict_obs = pd.read_csv(STRICT / "oracle/oracle_presence_observations.csv").set_index("unit_id")
    agreement_rows = []
    for result in results:
        if result.get("operator") != "DENSE_UNIT_CALIBRATION":
            continue
        unit_id = int(result["task"]["unit_id"])
        parsed = result.get("parsed_response") or {}
        label = parsed.get("label", "INVALID")
        reference_label = str(strict_obs.loc[unit_id, "parsed_label"])
        agreement_rows.append({
            "unit_id": unit_id,
            "new_label": label,
            "strict_frozen_label": reference_label,
            "agreement": label == reference_label,
            "evaluation_only": True,
        })
    agreement = pd.DataFrame(agreement_rows)
    agreement.to_csv(PACKAGE / "diagnostics/DENSE_CALIBRATION_AGREEMENT.csv", index=False)

    run_complete = load_json(PHYSICAL / "RUN_COMPLETE.json") if (PHYSICAL / "RUN_COMPLETE.json").exists() else {"status": "INCOMPLETE"}
    fallback_invalid = [
        r["attempt_id"] for r in results
        if r.get("operator") == "DENSE_UNIT_FALLBACK"
        and (r.get("status") != "VALID" or (r.get("parsed_response") or {}).get("label") == "abstain")
    ]
    complete = (
        run_complete.get("status") == "COMPLETE"
        and len(ledger[ledger.operator == "EVENT_ENUMERATE"]) == 70
        and len(cal) == 20
        and not fallback_invalid
    )
    quality_pass = values["event_recall"] >= 0.80 and values["event_f1"] >= 0.80
    cost_pass = gpu_ratio < 0.70
    gate_pass = bool(complete and quality_pass and cost_pass)
    decision = {
        "physical_gate": "PASS" if gate_pass else "FAIL" if complete else "INCOMPLETE",
        "complete": complete,
        "event_precision": values["event_precision"],
        "event_recall": values["event_recall"],
        "event_f1": values["event_f1"],
        "quality_pass": quality_pass,
        "selected_gpu_seconds": selected_gpu,
        "estimated_dense_gpu_seconds": dense_gpu,
        "gpu_cost_ratio": gpu_ratio,
        "cost_pass": cost_pass,
        "new_physical_calls": len(ledger),
        "selected_algorithm_calls": len(selected),
        "fallback_calls": len(ledger[ledger.operator == "DENSE_UNIT_FALLBACK"]),
        "physical_cost_normalized_event_f1_auc": physical_auc,
        "call_cap_compliant": len(ledger) <= max_calls,
        "fallback_invalid": fallback_invalid,
    }
    atomic_json(PHYSICAL / "PHYSICAL_DECISION.json", decision)

    failure_rows = []
    if not matches.empty:
        for row in matches.itertuples():
            if not bool(row.matched):
                failure_rows.append({
                    "failure_type": row.match_type,
                    "predicted_event_id": row.predicted_event_id,
                    "reference_event_id": row.reference_event_id,
                    "main_explanation": "physical enumeration miss, false event, ownership loss, or oversplit; inspect source lineage",
                })
    pd.DataFrame(failure_rows).to_csv(PACKAGE / "diagnostics/FAILURE_CASES.csv", index=False)

    agreement_rate = float(agreement.agreement.mean()) if not agreement.empty else math.nan
    report = f"""# VERA physical pilot report

Physical gate: `{decision['physical_gate']}`.

The run started {len(ledger)} new Qwen3-VL calls: {len(cal)} reference-independent dense hardware calibrations, {len(ledger[ledger.operator == 'EVENT_ENUMERATE'])} full-timeline enumeration calls, and {decision['fallback_calls']} preregistered dense fallback calls. The 200-call cap was {'respected' if decision['call_cap_compliant'] else 'VIOLATED'}.

## Primary frozen endpoints

| Metric | Result | Frozen threshold | Pass |
|---|---:|---:|---|
| Event precision | {values['event_precision']:.6f} | diagnostic | — |
| Event recall | {values['event_recall']:.6f} | >= 0.80 | {values['event_recall'] >= 0.80} |
| Event F1 | {values['event_f1']:.6f} | >= 0.80 | {values['event_f1'] >= 0.80} |
| Selected GPU seconds | {selected_gpu:.3f} | diagnostic | — |
| Estimated dense GPU seconds on this GPU | {dense_gpu:.3f} | denominator | — |
| GPU-cost ratio | {gpu_ratio:.6f} | < 0.70 | {cost_pass} |

The cost denominator is 347 times the median synchronized generation wall time of the 20 uniformly spaced dense calibration calls. Calibration quality agreement with the pre-existing strict outputs, checked only after inference, is {agreement_rate:.3f}.

## Interpretation

This is single-video, VLM-pseudo-oracle-relative development evidence. A valid empty enumeration does not trigger fallback, so misses are not hidden by the fallback policy. Single-owner reconciliation performs no heuristic cross-window merge; oversplitting remains visible to the frozen evaluator. The cost-normalized event-F1 AUC on the predeclared dense-equivalent budget grid is {physical_auc:.6f}.
"""
    atomic_text(PHYSICAL / "PILOT_REPORT.md", report)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    evaluate()


if __name__ == "__main__":
    main()
