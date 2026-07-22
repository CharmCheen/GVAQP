#!/usr/bin/env python3
"""Evaluator-only Stage-4 component attribution and mechanism audit."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs/psvr_autonomous_research/stage_4_scan_component_ablation"
NEW_RAW = OUT / "raw_matrix"
OLD_RAW = REPO / "outputs/psvr_autonomous_research/stage_3_factorization/raw_matrix"
TABLES = OUT / "tables"; REPORTS = OUT / "reports"
STAGE2_RUNNER = REPO / "scripts/run_psvr_core_pilot.py"
METHOD_MAP = {"C0": "S0", "C1": "S1"}
METHODS = ("S0", "S1", "S2", "S3", "S4")
DEADLINES = ("T_transition", "T_high")


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def load_stage2():
    spec = importlib.util.spec_from_file_location("psvr_stage4_evaluator_runtime", STAGE2_RUNNER)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def semantic_event_set(run: dict) -> tuple[str, ...]:
    snapshot = json.loads(Path(run["final_snapshot_path"]).read_text())
    return tuple(sorted(f"{float(e['start_time']):.3f}:{float(e['end_time']):.3f}:{e['anchor_unit_ids']}"
                        for e in snapshot["strict_confirmed_events"]))


def event_units(reference: pd.DataFrame) -> set[int]:
    result = set()
    for value in reference.source_unit_ids.astype(str):
        for token in value.replace("|", " ").replace(",", " ").split():
            result.add(int(float(token)))
    return result


def blocks(n: int, observed: set[int]) -> list[tuple[int, int]]:
    result, start = [], None
    for unit in range(n):
        if unit not in observed and start is None:
            start = unit
        if unit in observed and start is not None:
            result.append((start, unit - 1)); start = None
    if start is not None:
        result.append((start, n - 1))
    return result


def local_signal(unit: int, scores: dict[int, float]) -> float:
    if not scores:
        return 0.0
    scale = max(1.0, max(abs(value) for value in scores.values()))
    return max((max(0.0, value) / scale) / (1.0 + abs(unit - seen)) for seen, value in scores.items())


def parent_level(n: int, target: tuple[int, int]) -> tuple[str | None, int]:
    current, parent, level = (0, n - 1), None, 0
    while current != target:
        left, right = current; midpoint = (left + right) // 2
        children = [(left, midpoint - 1), (midpoint + 1, right)]
        match = next((cell for cell in children if cell[0] <= cell[1] and cell[0] <= target[0] <= target[1] <= cell[1]), None)
        if match is None:
            return None, -1
        parent, current, level = current, match, level + 1
    return (None if parent is None else f"{parent[0]}:{parent[1]}", level)


def full_candidates(n: int, observed: set[int], scores: dict[int, float]) -> list[dict]:
    norm = math.log2(n + 1.0); result = []
    for left, right in blocks(n, observed):
        span = right - left + 1; unit = (left + right) // 2
        duration = span / n; debt = 0.5 * math.log2(span + 1.0) / norm; proxy = 0.25 * local_signal(unit, scores)
        parent, level = parent_level(n, (left, right))
        result.append({"unit_id": unit, "cell_id": f"{left}:{right}", "parent_cell_id": parent,
                       "scan_level": level, "unobserved_duration_component": duration,
                       "debt_component": debt, "proxy_component": proxy,
                       "total_priority": duration + debt + proxy})
    return sorted(result, key=lambda row: (-row["total_priority"], row["unit_id"]))


def integrate(checkpoints: list[dict], key: str, deadline: float, initial: float) -> float:
    time, value, area = 0.0, initial, 0.0
    for row in sorted(checkpoints, key=lambda x: float(x["elapsed_seconds"])):
        moment = min(deadline, max(time, float(row["elapsed_seconds"])))
        area += value * (moment - time); time = moment; value = float(row[key])
        if time >= deadline:
            break
    if time < deadline:
        area += value * (deadline - time)
    return area / deadline


def trace_and_diagnostics(run: dict, method: str, positives: set[int], n: int) -> tuple[list[dict], dict]:
    observed, scores, queried = set(), {}, set(); trace = []
    first_event_scan = first_positive_proxy = first_candidate = None
    positive_frontier_scan_states = 0; scan_actions = 0
    for action_index, action in enumerate(run["actions"]):
        if action["action"] == "scan":
            temporary = set(observed)
            for within, (unit, score) in enumerate(zip(action["unit_ids"], action["scores"])):
                unit = int(unit); score = float(score)
                if method == "S0":
                    detail = {"cell_id": f"fixed_grid:{unit}", "parent_cell_id": None, "scan_level": 0,
                              "unobserved_duration_component": None, "debt_component": None,
                              "proxy_component": None, "total_priority": None, "selected_rank": 1,
                              "next_best_cell": None}
                elif method == "S1":
                    candidates = full_candidates(n, temporary, scores); selected = candidates[0]
                    if selected["unit_id"] != unit:
                        raise RuntimeError(f"reused S1 action mismatch in {run['run_id']}: {selected['unit_id']} != {unit}")
                    detail = {**selected, "selected_rank": 1,
                              "next_best_cell": None if len(candidates) < 2 else {
                                  "cell_id": candidates[1]["cell_id"], "unit_id": candidates[1]["unit_id"],
                                  "total_priority": candidates[1]["total_priority"]}}
                else:
                    detail = dict(action["scan_priorities"][within])
                cell = detail["cell_id"]
                if cell.startswith("fixed_grid:"):
                    left = right = unit
                else:
                    left, right = map(int, cell.split(":"))
                contains_event = any(left <= value <= right for value in positives)
                selected_is_event = unit in positives
                trace.append({"run_id": run["run_id"], "method": method, "deadline_name": run["deadline_name"],
                              "replicate": run["replicate"], "action_index": action_index,
                              "within_batch_index": within, "selected_unit_id": unit,
                              **detail,
                              "cell_event_overlap_after_execution": selected_is_event,
                              "hierarchical_interval_contains_event_after_execution": contains_event,
                              "selected_unit_event_overlap_after_execution": selected_is_event})
                temporary.add(unit)
                if unit in positives and first_event_scan is None:
                    first_event_scan = float(action["end_seconds"])
                if unit in positives and score > 0 and first_positive_proxy is None:
                    first_positive_proxy = float(action["end_seconds"])
            for unit, score in zip(action["unit_ids"], action["scores"]):
                observed.add(int(unit)); scores[int(unit)] = float(score)
            scan_actions += 1
            available = sorted(observed - queried, key=lambda unit: (-scores[unit], unit))
            if available and available[0] in positives:
                positive_frontier_scan_states += 1
                if first_candidate is None:
                    first_candidate = float(action["end_seconds"])
        else:
            queried.add(int(action["unit_id"]))
            available = sorted(observed - queried, key=lambda unit: (-scores[unit], unit))
            if available and available[0] in positives and first_candidate is None:
                first_candidate = float(action["end_seconds"])
    cells = [row["cell_id"] for row in trace]
    diagnostics = {
        "time_to_first_event_cell_scan": first_event_scan,
        "time_to_first_positive_proxy_exposure": first_positive_proxy,
        "time_to_candidate_creation": first_candidate,
        "time_to_first_physical_VERIFY": None if not run["queried_results"] else float(run["queried_results"][0]["query_start_seconds"]),
        "positive_cells_touched": len(observed & positives),
        "positive_candidate_exposure_per_scan": len(observed & positives) / scan_actions if scan_actions else 0.0,
        "positive_frontier_scan_states": positive_frontier_scan_states,
        "distinct_cells_refined": len(set(cells)),
        "repeat_refinements": len(cells) - len(set(cells)),
        "global_gap_integral": integrate(run["checkpoints"], "coverage_debt", float(run["deadline_seconds"]), 1.0),
    }
    return trace, diagnostics


def triple(series: pd.Series) -> dict:
    values = series.dropna().astype(float)
    return {"median": None if values.empty else float(values.median()),
            "min": None if values.empty else float(values.min()),
            "max": None if values.empty else float(values.max())}


def main() -> None:
    TABLES.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
    stage2 = load_stage2(); benchmark = stage2.benchmark_module()
    reference = pd.read_csv(stage2.REFERENCE_PATH); units = pd.read_csv(stage2.UNITS_PATH)
    positives = event_units(reference); evaluator_hash = stage2.sha256_file(stage2.MATERIALIZER)
    runs = []
    for method in ("C0", "C1"):
        for deadline in DEADLINES:
            for path in sorted(OLD_RAW.glob(f"{method}__{deadline}__replicate_*/attempt_*/complete.json")):
                row = json.loads(path.read_text()); row["stage4_method"] = METHOD_MAP[method]; runs.append(row)
    for path in sorted(NEW_RAW.glob("*/attempt_*/complete.json")):
        row = json.loads(path.read_text()); row["stage4_method"] = row["method"]; runs.append(row)
    if len(runs) != 30:
        raise RuntimeError(f"expected 12 reused + 18 new runs, found {len(runs)}")

    summaries, traces, curves = [], [], []
    for run in runs:
        method = run["stage4_method"]
        summary, points = stage2.evaluate_run(run, benchmark, reference, units, evaluator_hash)
        trace, diagnostic = trace_and_diagnostics(run, method, positives, len(units))
        traces.extend(traces if False else trace); curves.extend(points)
        summary.update(diagnostic); summary["method"] = method
        summary["semantic_event_set"] = "|".join(semantic_event_set(run))
        summary["time_to_confirmation"] = summary["time_to_first_confirmed_event"]
        summary["scan_actions"] = sum(a["action"] == "scan" for a in run["actions"])
        summary["verify_actions"] = sum(a["action"] == "query" for a in run["actions"])
        summary["verify_rejected"] = int(str(run["stop_reason"]).startswith("verify_not_admitted:"))
        summary["action_signature"] = repr(tuple((a["action"], tuple(a.get("unit_ids", [])), a.get("unit_id")) for a in run["actions"]))
        summaries.append(summary)
    frame = pd.DataFrame(summaries); frame.to_csv(TABLES / "RUN_METRICS.csv", index=False)
    pd.DataFrame(traces).to_csv(TABLES / "SCAN_DECISION_TRACE.csv", index=False)
    pd.DataFrame(curves).to_csv(TABLES / "MECHANISM_CURVES.csv", index=False)

    metric_fields = ["AnytimeAUC_F1", "F1_at_deadline", "precision", "recall", "unique_confirmed_events",
                     "time_to_first_event_cell_scan", "time_to_first_positive_proxy_exposure", "time_to_candidate_creation",
                     "time_to_first_physical_VERIFY", "time_to_confirmation", "positive_cells_touched",
                     "positive_candidate_exposure_per_scan", "distinct_cells_refined", "repeat_refinements",
                     "global_gap_integral", "max_unobserved_gap_auc_fraction", "max_unobserved_gap",
                     "scan_actions", "verify_actions", "GPU_seconds", "unused_deadline_seconds", "verify_rejected"]
    aggregate = []
    for method in METHODS:
        for deadline in DEADLINES:
            group = frame[(frame.method == method) & (frame.deadline_name == deadline)]
            row = {"method": method, "deadline_name": deadline, "runs": len(group),
                   "event_set_consistency": group.semantic_event_set.nunique() == 1,
                   "semantic_event_sets": sorted(group.semantic_event_set.unique().tolist()),
                   "action_trace_variation": int(group.action_signature.nunique())}
            row.update({field: triple(group[field]) for field in metric_fields}); aggregate.append(row)
    dump(TABLES / "METHOD_DEADLINE_MEDIAN_MIN_MAX.json", aggregate)

    effective = {}
    for method in METHODS:
        cells = [row for row in aggregate if row["method"] == method]
        effective[method] = all(row["unique_confirmed_events"]["min"] is not None and
                                row["unique_confirmed_events"]["min"] >= 1 and
                                row["F1_at_deadline"]["min"] > 0 and row["AnytimeAUC_F1"]["min"] > 0
                                for row in cells)
    if not effective["S2"] and effective["S3"] and effective["S4"] and effective["S1"]:
        attribution = "DEBT"
    elif not effective["S3"] and effective["S2"] and effective["S4"] and effective["S1"]:
        attribution = "PROXY_SIGNAL"
    elif not effective["S4"] and effective["S2"] and effective["S3"] and effective["S1"]:
        attribution = "DURATION_COVERAGE"
    elif effective["S1"] and not any(effective[x] for x in ("S2", "S3", "S4")):
        attribution = "COMPOSITE_INTERACTION"
    elif all(effective[x] for x in ("S2", "S3", "S4")):
        attribution = "TIE_BREAK_OR_COMMON_PATH"
    else:
        attribution = "INCONCLUSIVE"
    validity = {"combined_runs": len(runs), "reused_runs": 12, "new_physical_runs": 18,
                "new_runtime_failures": len(list(NEW_RAW.glob("*/attempt_*/failed.json"))),
                "new_deadline_misses": sum(not run["deadline_met"] for run in runs if run["stage4_method"] in ("S2", "S3", "S4")),
                "new_cache_replays": sum(run["cache_replay_calls"] for run in runs if run["stage4_method"] in ("S2", "S3", "S4")),
                "new_future_proxy_accesses": sum(run["future_proxy_accesses"] for run in runs if run["stage4_method"] in ("S2", "S3", "S4")),
                "new_candidate_observation_violations": sum(run["candidate_observation_violations"] for run in runs if run["stage4_method"] in ("S2", "S3", "S4")),
                "runtime_identity_count": len({run["runtime_identity_hash"] for run in runs}),
                "all_cells_have_three_runs": all(row["runs"] == 3 for row in aggregate),
                "all_event_sets_consistent": all(row["event_set_consistency"] for row in aggregate),
                "all_action_traces_consistent": all(row["action_trace_variation"] == 1 for row in aggregate),
                "physical_cap_respected": len(list(NEW_RAW.glob("*/attempt_*/complete.json"))) == 18,
                "heldout_opened": False}
    dump(OUT / "VALIDATION.json", validity)
    decision = {"H_SCAN_COMP1": "VALID" if all([validity["new_runtime_failures"] == 0,
                                                   validity["new_deadline_misses"] == 0,
                                                   validity["new_cache_replays"] == 0,
                                                   validity["new_future_proxy_accesses"] == 0,
                                                   validity["new_candidate_observation_violations"] == 0,
                                                   validity["runtime_identity_count"] == 1,
                                                   validity["all_cells_have_three_runs"]]) else "INVALID",
                "SCAN_COMPONENT_ATTRIBUTION": attribution,
                "conclusion": "DEBT_COMPONENT_SIGNAL = PRESENT_ON_CURRENT_DEV_TASK" if attribution == "DEBT" else attribution,
                "effectiveness": effective,
                "H_COV1": "REVISE_NARROWER_DEBT_HYPOTHESIS_REGISTERED_NOT_ACCEPTED" if attribution == "DEBT" else "REVISE",
                "GENERALIZATION": "UNTESTED", "semantic_samples": 1,
                "runtime_repeats_are_stability_only": True,
                "next_phase": ">=3 independent videos x >=2 queries; compare selected scan method, Fixed Coverage, Uniform Temporal",
                "single_video_development": "STOPPED_AFTER_THIS_COMPONENT_ABLATION",
                "not_claimed": ["H-SCAN1 accepted", "cross-task generalization", "paper-level mechanism established"]}
    dump(OUT / "DECISION.json", decision)
    print(json.dumps({"validation": validity, "decision": decision}, indent=2))


if __name__ == "__main__":
    main()
