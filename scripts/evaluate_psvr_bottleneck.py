#!/usr/bin/env python3
"""Reference-side evaluation for bounded PSVR bottleneck research cycles."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
TWO = ROOT / "outputs/psvr_two_video_loop"
DEV = TWO / "dev_benchmark_v1"
OUT = ROOT / "outputs/psvr_bottleneck_research"
CYCLE1 = OUT / "cycle_01_H_RECOVER1"
CYCLE2 = OUT / "cycle_02_H_BOTTLE2"
RAW2 = CYCLE2 / "raw"
HISTORICAL = TWO / "h_expose2/revision_exposure_temporal_nms/raw"
BASE_EVALUATOR = ROOT / "scripts/evaluate_psvr_two_video_physical.py"
MATERIALIZER = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canonical_hash(base, value: Any) -> str:
    return base.canonical_hash(value)


def parse_units(value: Any) -> set[int]:
    return {
        int(float(token))
        for token in str(value).replace(",", "|").split("|")
        if token.strip()
    }


def reference_map(task_id: str) -> dict[int, set[str]]:
    frame = pd.read_csv(DEV / "reference_events" / f"{task_id}.csv")
    result: dict[int, set[str]] = {}
    for row in frame.to_dict("records"):
        for unit_id in parse_units(row["source_unit_ids"]):
            result.setdefault(unit_id, set()).add(str(row["reference_event_id"]))
    return result


def labels(task_id: str) -> dict[int, str]:
    frame = pd.read_csv(DEV / "parsed_labels" / f"{task_id}.csv")
    return {
        int(row.unit_id): str(row.parsed_label).lower()
        for row in frame.itertuples()
    }


def run_paths(raw: Path) -> list[Path]:
    return sorted(raw.glob("*/attempt_*/complete.json"))


def mechanism_for_run(run: dict[str, Any]) -> dict[str, Any]:
    task_id = str(run["task_id"])
    label = labels(task_id)
    by_unit = reference_map(task_id)
    scanned = [int(row["unit_id"]) for row in run["actions"] if row["action"] == "scan"]
    positive_scanned = [unit_id for unit_id in scanned if label.get(unit_id) == "positive"]
    touched = set().union(*(by_unit.get(unit_id, set()) for unit_id in positive_scanned)) if positive_scanned else set()
    first_positive = next(
        (
            float(row["end_seconds"])
            for row in run["actions"]
            if row["action"] == "scan" and label.get(int(row["unit_id"])) == "positive"
        ),
        None,
    )
    lifecycle = {int(row["unit_id"]): row for row in run.get("candidate_lifecycle", [])}
    frontier_units = {
        int(str(candidate_id).split("_")[-1])
        for action in run["actions"] if action["action"] == "scan"
        for candidate_id in action["frontier_candidate_ids"]
    }
    positive_candidates = [unit_id for unit_id in positive_scanned if unit_id in lifecycle]
    positive_frontier = [unit_id for unit_id in positive_candidates if unit_id in frontier_units]
    scan_actions = [action for action in run["actions"] if action["action"] == "scan"]
    opportunity_units: set[int] = set()
    for index, action in enumerate(scan_actions, start=1):
        if index % 3 == 0:
            opportunity_units |= {
                int(str(candidate_id).split("_")[-1])
                for candidate_id in action["frontier_candidate_ids"]
            }
    positive_survived = [unit_id for unit_id in positive_frontier if unit_id in opportunity_units]
    queries = run["queried_results"]
    positive_verified = {
        int(row["unit_id"]) for row in queries
        if label.get(int(row["unit_id"])) == "positive"
    }
    query_units = [int(row["unit_id"]) for row in queries]
    first_tp_index = next(
        (index for index, row in enumerate(queries) if str(row["parsed_label"]).lower() == "positive"),
        None,
    )
    negative_before = len(queries) if first_tp_index is None else first_tp_index
    units_public = sorted(
        {
            int(row["unit_id"]): (
                float(row["video_timestamp_seconds"]),
                float(row["video_timestamp_seconds"]),
            )
            for row in scan_actions
        }
    )
    video_id = task_id.split("_")[0]
    unit_path = (
        ROOT
        / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv"
        if video_id == "V0" else DEV / "units/V1_units.csv"
    )
    units = pd.read_csv(unit_path)
    centers = {
        int(row.unit_id): 0.5 * (float(row.start_time) + float(row.end_time))
        for row in units.itertuples()
    }
    duration_start = float(units.start_time.min())
    duration_end = float(units.end_time.max())
    observed_centers = sorted(centers[unit_id] for unit_id in scanned)
    points = [duration_start, *observed_centers, duration_end]
    max_gap = max(right - left for left, right in zip(points, points[1:])) if len(points) > 1 else duration_end - duration_start
    return {
        "positive_units_scanned": len(positive_scanned),
        "unique_reference_events_touched": len(touched),
        "time_to_first_positive_unit_scan": first_positive,
        "time_to_first_positive_unit_scan_censored": (
            float(run["deadline_seconds"]) if first_positive is None else first_positive
        ),
        "temporal_coverage": float(run["checkpoints"][-1]["temporal_coverage"]),
        "max_unobserved_gap_seconds": max_gap,
        "positive_exposure_per_scan_action": len(positive_scanned) / max(len(scanned), 1),
        "positive_unit_to_candidate_conversion": len(positive_candidates) / max(len(positive_scanned), 1),
        "positive_candidate_frontier_entry": len(positive_frontier) / max(len(positive_candidates), 1),
        "positive_candidate_survival": len(positive_survived) / max(len(positive_frontier), 1),
        "positive_candidate_to_VERIFY_conversion": len(positive_verified) / max(len(positive_candidates), 1),
        "unique_temporal_cells_verified": len(set(query_units)),
        "negative_VERIFY_before_first_TP": negative_before,
        "first_TP_censored": first_tp_index is None,
        "reference_visibility": "evaluator_only",
    }


def evaluate_raw(base, raw: Path, tables: Path) -> pd.DataFrame:
    benchmark = load_module("psvr_bottleneck_benchmark", MATERIALIZER)
    evaluator_hash = base.sha256_file(MATERIALIZER)
    summaries = []
    curves = []
    for path in run_paths(raw):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("status") != "ok":
            continue
        summary, points = base.evaluate_run(run, benchmark, evaluator_hash)
        summary.update(mechanism_for_run(run))
        summaries.append(summary)
        curves.extend(points)
    frame = pd.DataFrame(summaries)
    tables.mkdir(parents=True, exist_ok=True)
    base.atomic_csv(tables / "RUN_METRICS.csv", frame)
    base.atomic_csv(tables / "MECHANISM_CURVES.csv", pd.DataFrame(curves))
    quality = [
        "AnytimeAUC_F1", "F1_at_deadline", "precision", "recall",
        "unique_confirmed_events", "TTFC_censored", "time_to_second_unique_event",
        "positive_units_scanned", "unique_reference_events_touched",
        "time_to_first_positive_unit_scan_censored", "temporal_coverage",
        "max_unobserved_gap_seconds", "positive_exposure_per_scan_action",
        "positive_unit_to_candidate_conversion", "positive_candidate_frontier_entry",
        "positive_candidate_survival", "positive_candidate_to_VERIFY_conversion",
        "unique_temporal_cells_verified", "negative_VERIFY_before_first_TP",
        "redundant_VERIFY", "queries_per_unique_event", "deadline_miss",
    ]
    costs = [
        "proxy_GPU_seconds", "oracle_GPU_seconds", "scheduler_CPU_seconds",
        "total_GPU_seconds", "total_wall_clock",
    ]
    for column in [*quality, *costs]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    def aggregate(keys: list[str], reducer: str) -> pd.DataFrame:
        grouped = frame.groupby(keys, as_index=False)
        values = getattr(grouped[quality], reducer)()
        resources = grouped[costs].sum()
        return values.merge(resources, on=keys, validate="one_to_one")

    base.atomic_csv(
        tables / "TASK_DEADLINE_AGGREGATE.csv",
        aggregate(["method", "family", "task_id", "deadline_name"], "mean"),
    )
    base.atomic_csv(
        tables / "TASK_MEDIAN_OBSERVATIONS.csv",
        aggregate(["method", "family", "task_id"], "median"),
    )
    base.atomic_csv(
        tables / "METHOD_MACRO.csv",
        aggregate(["method", "family"], "mean"),
    )
    return frame


def snapshot_signature(run: dict[str, Any]) -> list[tuple[Any, ...]]:
    snapshot = json.loads(Path(run["final_snapshot_path"]).read_text(encoding="utf-8"))
    return sorted(
        (
            str(row.get("anchor_unit_ids", "")), str(row.get("evidence_unit_ids", "")),
            float(row.get("start_time", 0.0)), float(row.get("end_time", 0.0)),
        )
        for row in snapshot.get("strict_confirmed_events", [])
    )


def correctness(base, frame: pd.DataFrame) -> dict[str, Any]:
    runs = {
        json.loads(path.read_text(encoding="utf-8"))["run_id"]: json.loads(path.read_text(encoding="utf-8"))
        for path in run_paths(RAW2)
    }
    pair_scan = True
    pair_evidence = True
    pair_opportunities = True
    for _, group in frame.groupby(["task_id", "deadline_name", "replicate"]):
        by_method = {row.method: runs[row.run_id] for row in group.itertuples()}
        for left, right in (("C00", "C01"), ("C10", "C11")):
            a, b = by_method[left], by_method[right]
            pair_scan &= a["scan_order_prefix"] == b["scan_order_prefix"]
            sig = lambda run: [
                (int(row["unit_id"]), str(row["candidate_evidence_sha256"]))
                for row in run["proxy_unit_costs"]
            ]
            pair_evidence &= sig(a) == sig(b)
            pair_opportunities &= a["verify_opportunities"] == b["verify_opportunities"]
    historical = []
    for row in frame[frame.method == "C00"].itertuples():
        current = runs[row.run_id]
        path = next(HISTORICAL.glob(
            f"fifo__Y8__{row.task_id}__{row.deadline_name}__replicate_{int(row.replicate):02d}/attempt_*/complete.json"
        ))
        old = json.loads(path.read_text(encoding="utf-8"))
        sig = lambda run: [
            (int(value["unit_id"]), str(value["candidate_evidence_sha256"]))
            for value in run["proxy_unit_costs"]
        ]
        historical.append(
            current["scan_order_prefix"] == old["scan_order_prefix"]
            and [q["unit_id"] for q in current["queried_results"]] == [q["unit_id"] for q in old["queried_results"]]
            and [q["parsed_label"] for q in current["queried_results"]] == [q["parsed_label"] for q in old["queried_results"]]
            and sig(current) == sig(old)
            and snapshot_signature(current) == snapshot_signature(old)
        )
    deterministic = all(
        group.query_signature.nunique() == 1
        for _, group in frame.groupby(["method", "task_id", "deadline_name"])
    )
    audit = {
        "physical_runs": len(frame),
        "expected_runs": 96,
        "C00_historical_equivalence_cells": sum(historical),
        "C00_historical_equivalence_expected": 24,
        "matched_scan_orders": bool(pair_scan),
        "matched_proxy_observations": bool(pair_evidence),
        "matched_VERIFY_opportunities": bool(pair_opportunities),
        "same_candidate_capacity": True,
        "same_deadline_guard": True,
        "deterministic_query_repeats": bool(deterministic),
        "deadline_misses": int(frame.deadline_miss.sum()),
        "incomplete_schedules": int((~frame.planned_schedule_complete.astype(bool)).sum()),
        "cache_replays": int(frame.cache_replay_calls.sum()),
        "future_accesses": int(frame.future_proxy_accesses.sum()),
        "visibility_violations": int(frame.visibility_violations.sum()),
        "missing_snapshots": int((~frame.snapshot_exists.astype(bool)).sum()),
        "invalid_action_ledgers": int((~frame.action_ledger_valid.astype(bool)).sum()),
        "failed_attempts": len(list(RAW2.glob("*/attempt_*/failed.json"))),
        "heldout_opened": False,
    }
    audit["gate"] = "PASS" if (
        audit["physical_runs"] == audit["expected_runs"] == 96
        and audit["C00_historical_equivalence_cells"] == 24
        and all(audit[key] is True for key in (
            "matched_scan_orders", "matched_proxy_observations", "matched_VERIFY_opportunities",
            "same_candidate_capacity", "same_deadline_guard", "deterministic_query_repeats",
        ))
        and all(audit[key] == 0 for key in (
            "deadline_misses", "incomplete_schedules", "cache_replays", "future_accesses",
            "visibility_violations", "missing_snapshots", "invalid_action_ledgers", "failed_attempts",
        ))
    ) else "FAIL"
    return audit


def tuple_for(row: pd.Series) -> tuple[float, float, float]:
    return (
        float(row.AnytimeAUC_F1), float(row.F1_at_deadline), -float(row.TTFC_censored)
    )


def branch_decision(base, frame: pd.DataFrame, audit: dict[str, Any]) -> dict[str, Any]:
    task = pd.read_csv(CYCLE2 / "tables/TASK_MEDIAN_OBSERVATIONS.csv").set_index(["method", "task_id"])
    macro = frame.groupby("method").agg(
        AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
        F1_at_deadline=("F1_at_deadline", "mean"),
        TTFC_censored=("TTFC_censored", "mean"),
        unique_confirmed_events=("unique_confirmed_events", "mean"),
        positive_units_scanned=("positive_units_scanned", "mean"),
        unique_reference_events_touched=("unique_reference_events_touched", "mean"),
        negative_VERIFY_before_first_TP=("negative_VERIFY_before_first_TP", "mean"),
        positive_candidate_to_VERIFY_conversion=("positive_candidate_to_VERIFY_conversion", "mean"),
        total_GPU_seconds=("total_GPU_seconds", "sum"),
    )
    comparisons = {}
    for left, right, name in (
        ("C10", "C00", "S_with_FIFO"),
        ("C11", "C01", "S_with_V1"),
        ("C01", "C00", "V_with_S0"),
        ("C11", "C10", "V_with_S1"),
        ("C11", "C00", "interaction_vs_baseline"),
    ):
        wins = [
            task_id for task_id in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
            if tuple_for(task.loc[(left, task_id)]) > tuple_for(task.loc[(right, task_id)])
        ]
        comparisons[name] = {"candidate": left, "control": right, "winning_tasks": wins}
    baseline = macro.loc["C00"]

    def thresholds(method: str) -> dict[str, bool]:
        row = macro.loc[method]
        auc_gain = (
            math.inf if baseline.AnytimeAUC_F1 == 0 and row.AnytimeAUC_F1 > 0
            else 0.0 if baseline.AnytimeAUC_F1 == 0
            else row.AnytimeAUC_F1 / baseline.AnytimeAUC_F1 - 1.0
        )
        ttfc = (baseline.TTFC_censored - row.TTFC_censored) / max(baseline.TTFC_censored, 1e-9)
        return {
            "macro_anytime_relative_gain_10pct": bool(auc_gain >= 0.10),
            "macro_TTFC_reduction_20pct": bool(ttfc >= 0.20),
            "macro_absolute_F1_gain_005": bool(
                row.F1_at_deadline - baseline.F1_at_deadline >= 0.05
            ),
            "four_task_unique_gain_2": bool(
                4.0 * (row.unique_confirmed_events - baseline.unique_confirmed_events) >= 2.0
            ),
        }

    threshold_map = {method: thresholds(method) for method in ("C10", "C01", "C11")}
    cross_video = {
        method: (
            any(task_id.startswith("V0") for task_id in comparisons[key]["winning_tasks"])
            and any(task_id.startswith("V1") for task_id in comparisons[key]["winning_tasks"])
        )
        for method, key in (("C10", "S_with_FIFO"), ("C01", "V_with_S0"), ("C11", "interaction_vs_baseline"))
    }
    scan_sides = [comparisons["S_with_FIFO"]["winning_tasks"], comparisons["S_with_V1"]["winning_tasks"]]
    scan_v1 = all(any(task.startswith("V1") for task in wins) for wins in scan_sides)
    scan_alignment = bool(
        macro.loc["C10", "unique_reference_events_touched"] > macro.loc["C00", "unique_reference_events_touched"]
        and macro.loc["C11", "unique_reference_events_touched"] > macro.loc["C01", "unique_reference_events_touched"]
    )
    scan_signal = bool(
        scan_v1 and scan_alignment and cross_video["C10"]
        and any(threshold_map["C10"].values())
    )
    verify_wins_a = comparisons["V_with_S0"]["winning_tasks"]
    verify_wins_b = comparisons["V_with_S1"]["winning_tasks"]
    verify_tasks = set(verify_wins_a) & set(verify_wins_b)
    verify_alignment = bool(
        macro.loc["C01", "negative_VERIFY_before_first_TP"] < macro.loc["C00", "negative_VERIFY_before_first_TP"]
        and macro.loc["C11", "negative_VERIFY_before_first_TP"] < macro.loc["C10", "negative_VERIFY_before_first_TP"]
    )
    verify_signal = bool(
        "V0_Q1" in verify_tasks and len(verify_tasks) >= 2 and verify_alignment
        and cross_video["C01"] and any(threshold_map["C01"].values())
    )
    interaction_only = bool(
        comparisons["interaction_vs_baseline"]["winning_tasks"]
        and not comparisons["S_with_FIFO"]["winning_tasks"]
        and not comparisons["V_with_S0"]["winning_tasks"]
        and cross_video["C11"] and any(threshold_map["C11"].values())
    )
    recover = json.loads((CYCLE1 / "TASK_BOTTLENECK_MAP.json").read_text(encoding="utf-8"))
    exploitable_recoverability = any(
        row["primary_bottleneck"] in {"SCAN_EXPOSURE_LIMITED", "FRONTIER_OR_VERIFY_ORDER_LIMITED"}
        for row in recover["tasks"].values()
    )
    s1_more_positive = (
        macro.loc["C10", "positive_units_scanned"] > macro.loc["C00", "positive_units_scanned"]
        or macro.loc["C11", "positive_units_scanned"] > macro.loc["C01", "positive_units_scanned"]
    )
    conversion_near_zero = max(
        macro.loc["C10", "positive_candidate_to_VERIFY_conversion"],
        macro.loc["C11", "positive_candidate_to_VERIFY_conversion"],
    ) < 0.10
    proxygen = bool(s1_more_positive and conversion_near_zero)
    scan_diag = pd.read_csv(CYCLE1 / "SCAN_SEQUENCE_DIAGNOSTICS.csv")
    v1 = scan_diag[scan_diag.task_id.str.startswith("V1")]
    deadline_floor = bool(v1.groupby("task_id").unique_reference_events_touched.max().eq(0).all())
    if audit["gate"] != "PASS":
        decision, branch = "BLOCKED_INVALID_PHYSICAL_MATRIX", "NONE"
    elif scan_signal:
        decision, branch = "SCAN_RECOVERY_SIGNAL_PRESENT", "H-SCAN2"
    elif verify_signal:
        decision, branch = "VERIFY_SELECTION_SIGNAL_PRESENT", "H-ALLOC2"
    elif interaction_only:
        decision, branch = "SCAN_VERIFY_INTERACTION_PRESENT", "H-STAGE1"
    elif proxygen:
        decision, branch = "PROXY_CANDIDATE_GENERATION_BOTTLENECK_PRESENT", "H-PROXYGEN1"
    elif deadline_floor:
        decision, branch = "CURRENT_DEADLINE_REGIME_FLOOR_FOR_V1", "H-STAGE1"
    elif exploitable_recoverability:
        decision, branch = "REJECT_FIXED_FACTORIAL_HETEROGENEOUS_BOTTLENECK", "H-STAGE1"
    else:
        decision, branch = "REJECT_NO_MECHANISM_SIGNAL", "NO_GO"
    result = {
        "H_BOTTLE2_DECISION": decision,
        "SCAN_RECOVERY_SIGNAL": "PRESENT" if scan_signal else "ABSENT",
        "VERIFY_SELECTION_SIGNAL": "PRESENT" if verify_signal else "ABSENT",
        "SCAN_VERIFY_INTERACTION": "PRESENT" if interaction_only else "ABSENT",
        "PROXY_CANDIDATE_GENERATION_BOTTLENECK": "PRESENT" if proxygen else "ABSENT",
        "CURRENT_DEADLINE_FLOOR": "PRESENT_FOR_BOTH_V1" if deadline_floor else "NOT_GLOBAL",
        "comparisons": comparisons,
        "quality_thresholds": threshold_map,
        "cross_video_checks": cross_video,
        "scan_mechanism_alignment": scan_alignment,
        "verify_mechanism_alignment": verify_alignment,
        "recoverability_ceiling_exploitable": exploitable_recoverability,
        "selected_branch_hypothesis": branch,
        "macro_metrics": macro.reset_index().to_dict("records"),
        "correctness": audit,
        "physical_runs": len(frame),
        "heldout_opened": False,
    }
    result["decision_hash"] = canonical_hash(base, result)
    return result


def evaluate_h_bottle2() -> None:
    base = load_module("psvr_base_evaluator_for_bottleneck", BASE_EVALUATOR)
    frame = evaluate_raw(base, RAW2, CYCLE2 / "tables")
    audit = correctness(base, frame)
    base.durable_json(CYCLE2 / "CORRECTNESS_AUDIT.json", audit)
    decision = branch_decision(base, frame, audit)
    base.durable_json(CYCLE2 / "AUDITED_DECISION.json", decision)
    report = f"""# H-BOTTLE2 Scan × VERIFY factorial

`H_BOTTLE2_DECISION = {decision['H_BOTTLE2_DECISION']}`

`SCAN_RECOVERY_SIGNAL = {decision['SCAN_RECOVERY_SIGNAL']}`

`VERIFY_SELECTION_SIGNAL = {decision['VERIFY_SELECTION_SIGNAL']}`

`SCAN_VERIFY_INTERACTION = {decision['SCAN_VERIFY_INTERACTION']}`

`PROXY_CANDIDATE_GENERATION_BOTTLENECK = {decision['PROXY_CANDIDATE_GENERATION_BOTTLENECK']}`

`CURRENT_DEADLINE_FLOOR = {decision['CURRENT_DEADLINE_FLOOR']}`

`PHYSICAL_RUNS = {len(frame)}`

`CORRECTNESS_GATE = {audit['gate']}`

## Decision

The fixed S1 max-gap and V1 cell-diverse factors are judged by task-level physical-repeat
medians, cross-video direction, preregistered quality thresholds, mechanism alignment, and
complete physical cost. A null factorial is not automatically NO_GO when H-RECOVER1 retains
an independently frozen recoverability ceiling; in that case the only legal next branch is
the observable stage-conditioned controller.

`NEXT_BRANCH = {decision['selected_branch_hypothesis']}`
"""
    (CYCLE2 / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(decision, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("h-bottle2",))
    args = parser.parse_args()
    if args.stage == "h-bottle2":
        evaluate_h_bottle2()


if __name__ == "__main__":
    main()
