#!/usr/bin/env python3
"""Evaluator-only H-SCAN1A metrics, mechanism analysis, and decision."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs/psvr_autonomous_research/stage_4_scan_component_ablation"
RAW = OUT / "raw_matrix"; TABLES = OUT / "tables"; REPORTS = OUT / "reports"
STAGE2 = REPO / "scripts/run_psvr_core_pilot.py"
METHODS = ("D0", "D1", "D2", "D3"); DEADLINES = ("T_transition", "T_high")


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def load_stage2():
    spec = importlib.util.spec_from_file_location("psvr_hscan1a_evaluator_runtime", STAGE2)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def event_units(reference: pd.DataFrame) -> tuple[set[int], dict[int, str]]:
    units, mapping = set(), {}
    for row in reference.itertuples():
        for token in str(row.source_unit_ids).replace("|", " ").replace(",", " ").split():
            unit = int(float(token)); units.add(unit); mapping[unit] = str(row.reference_event_id)
    return units, mapping


def integrate(checkpoints: list[dict], key: str, deadline: float, initial: float) -> float:
    t, value, area = 0.0, initial, 0.0
    for row in sorted(checkpoints, key=lambda x: float(x["elapsed_seconds"])):
        moment = min(deadline, max(t, float(row["elapsed_seconds"])))
        area += value * (moment - t); t = moment; value = float(row[key])
        if t >= deadline:
            break
    if t < deadline:
        area += value * (deadline - t)
    return area / deadline


def semantic_events(run: dict) -> tuple[str, ...]:
    snapshot = json.loads(Path(run["final_snapshot_path"]).read_text())
    return tuple(sorted(f"{float(e['start_time']):.3f}:{float(e['end_time']):.3f}:{e['anchor_unit_ids']}"
                        for e in snapshot["strict_confirmed_events"]))


def run_mechanism(run: dict, positives: set[int], ref_by_unit: dict[int, str]) -> tuple[dict, list[dict], dict]:
    positive_targets = [int(q["unit_id"]) for q in run["queried_results"] if q["parsed_label"] == "positive"]
    eventual = positive_targets[0] if positive_targets else None
    observed, scores, queried = set(), {}, set(); trace = []
    first_touch = first_relevant = first_ref_frontier = None; positive_exposure = 0
    scan_units, scan_levels, creation_sequence = [], [], []
    action_commit_durations = []
    for index, (action, checkpoint) in enumerate(zip(run["actions"], run["checkpoints"])):
        action_end = float(action["end_seconds"])
        action_commit_durations.append(max(0.0, float(checkpoint["elapsed_seconds"]) - action_end))
        if action["action"] == "scan":
            levels = [int(row.get("scan_level", 0)) for row in action["scan_priorities"]]
            scan_levels.extend(levels); scan_units.extend(map(int, action["unit_ids"]))
            for unit, score in zip(action["unit_ids"], action["scores"]):
                unit = int(unit); score = float(score); observed.add(unit); scores[unit] = score
                if unit in positives and first_touch is None:
                    first_touch = action_end
                if unit in positives and score > 0 and first_relevant is None:
                    first_relevant = action_end
            positive_exposure = len(observed & positives)
        else:
            queried.add(int(action["unit_id"]))
        frontier = sorted(observed - queried, key=lambda unit: (-scores[unit], unit))
        top = frontier[0] if frontier else None
        if top in positives and first_ref_frontier is None:
            first_ref_frontier = action_end
        rank = None if eventual is None or eventual not in frontier else frontier.index(eventual) + 1
        creation_sequence.append(top)
        trace.append({"run_id": run["run_id"], "method": run["method"], "deadline_name": run["deadline_name"],
                      "replicate": run["replicate"], "action_index": index,
                      "action": action["action"], "elapsed_seconds": float(checkpoint["elapsed_seconds"]),
                      "temporal_coverage": float(checkpoint["temporal_coverage"]),
                      "max_unobserved_gap": float(checkpoint["max_unobserved_gap_seconds"]),
                      "coverage_debt": float(checkpoint["coverage_debt"]),
                      "candidate_frontier_size": len(frontier), "candidate_top_unit": top,
                      "positive_event_cells_exposed": positive_exposure,
                      "eventual_positive_candidate_unit": eventual,
                      "eventual_positive_candidate_rank": rank,
                      "visibility": "evaluator_only" if any(x is not None for x in (positive_exposure, eventual, rank)) else "runtime_public"})
    positive_query = next((q for q in run["queried_results"] if q["parsed_label"] == "positive"), None)
    positive_action = next((a for a in run["actions"] if a["action"] == "query" and a["unit_id"] == eventual), None) if eventual is not None else None
    positive_checkpoint = next((c for c in run["checkpoints"] if positive_query and
                                c["action"] == "query" and c["elapsed_seconds"] == positive_query["snapshot_elapsed_seconds"]), None)
    timeline = {"first_event_cell_touch": first_touch, "first_relevant_proxy_observation": first_relevant,
                "reference_positive_candidate_creation": first_ref_frontier,
                "positive_candidate_unit": eventual,
                "positive_candidate_reference_event": None if eventual is None else ref_by_unit.get(eventual),
                "VERIFY_admission": None if positive_action is None else positive_action["admission"],
                "oracle_completion": None if positive_query is None else positive_query["query_end_seconds"],
                "event_confirmation": None if positive_query is None else positive_query["snapshot_elapsed_seconds"],
                "durable_snapshot_commit": None if positive_checkpoint is None else positive_checkpoint["elapsed_seconds"]}
    metrics = {"time_to_first_reference_event_cell_touch": first_touch,
               "time_to_first_relevant_proxy_observation": first_relevant,
               "time_to_first_reference_positive_frontier": first_ref_frontier,
               "positive_event_cells_touched": len(observed & positives),
               "candidate_exposure_per_scan": len(observed & positives) / max(1, sum(a["action"] == "scan" for a in run["actions"])),
               "global_gap_integral": integrate(run["checkpoints"], "coverage_debt", float(run["deadline_seconds"]), 1.0),
               "scan_cell_sequence": json.dumps(scan_units), "scan_level_sequence": json.dumps(scan_levels),
               "refinement_depth_distribution": json.dumps(dict(sorted(Counter(scan_levels).items()))),
               "candidate_creation_sequence": json.dumps(creation_sequence),
               "positive_event_cell_exposure_over_time": json.dumps([[row["elapsed_seconds"], row["positive_event_cells_exposed"]] for row in trace]),
               "candidate_frontier_size_over_time": json.dumps([[row["elapsed_seconds"], row["candidate_frontier_size"]] for row in trace]),
               "eventual_positive_candidate_rank_over_time": json.dumps([[row["elapsed_seconds"], row["eventual_positive_candidate_rank"]] for row in trace]),
               "scan_actions": sum(a["action"] == "scan" for a in run["actions"]),
               "refinement_actions": 0 if run["method"] == "D0" else sum(a["action"] == "scan" for a in run["actions"]),
               "proxy_batches": sum(a["action"] == "scan" for a in run["actions"]),
               "decoded_frames": sum(row.get("operator") == "decode_seek" and row.get("status") == "ok" for row in run["proxy_operator_rows"]),
               "physical_VERIFY_calls": run["physical_oracle_calls"], "VERIFY_admitted": run["physical_oracle_calls"],
               "VERIFY_rejected": int(str(run["stop_reason"]).startswith("verify_not_admitted:")),
               "scheduler_overhead_seconds": None,
               "snapshot_commit_seconds": sum(action_commit_durations),
               "final_snapshot_commit_elapsed_seconds": run["snapshot_elapsed_seconds"],
               "confirmed_event_ids": json.dumps(sorted({ref_by_unit[u] for u in positive_targets if u in ref_by_unit})),
               "semantic_event_set": json.dumps(semantic_events(run)),
               "exact_action_trace": repr(tuple((a["action"], tuple(a.get("unit_ids", [])), a.get("unit_id")) for a in run["actions"])),
               "scan_prefix": repr(tuple(scan_units)), "mechanism_timeline": json.dumps(timeline)}
    return metrics, trace, timeline


def triple(series: pd.Series) -> tuple[float | None, float | None, float | None]:
    values = series.dropna().astype(float)
    return ((None, None, None) if values.empty else (float(values.median()), float(values.min()), float(values.max())))


def main() -> None:
    stage2 = load_stage2(); benchmark = stage2.benchmark_module()
    reference = pd.read_csv(stage2.REFERENCE_PATH); units = pd.read_csv(stage2.UNITS_PATH)
    positives, ref_by_unit = event_units(reference); evaluator_hash = stage2.sha256_file(stage2.MATERIALIZER)
    runs = [json.loads(path.read_text()) for path in sorted(RAW.glob("*/attempt_*/complete.json"))]
    if len(runs) != 24:
        raise RuntimeError(f"expected 24 formal runs, found {len(runs)}")
    summaries, traces, timelines = [], [], []
    for run in runs:
        summary, _ = stage2.evaluate_run(run, benchmark, reference, units, evaluator_hash)
        mechanism, trace, timeline = run_mechanism(run, positives, ref_by_unit)
        summary.update(mechanism); summary["TP"] = int(round(summary["recall"] * len(reference)))
        summary["FP"] = int(summary["confirmed_events"] - summary["TP"]); summary["FN"] = len(reference) - summary["TP"]
        summaries.append(summary); traces.extend(trace); timelines.append({"run_id": run["run_id"], **timeline})
    frame = pd.DataFrame(summaries); frame.to_csv(OUT / "METHOD_DEADLINE_METRICS.csv", index=False)
    frame.to_csv(TABLES / "PHYSICAL_RUN_METRICS.csv", index=False)
    pd.DataFrame(traces).to_csv(OUT / "MECHANISM_METRICS.csv", index=False)
    pd.DataFrame(traces).to_csv(TABLES / "MECHANISM_TRACE.csv", index=False)
    dump(TABLES / "MECHANISM_TIMELINES.json", timelines)

    numeric = ["AnytimeAUC_F1", "F1_at_deadline", "precision", "recall", "TP", "FP", "FN",
               "unique_confirmed_events", "time_to_first_confirmed_event", "time_to_first_candidate",
               "time_to_first_reference_event_cell_touch", "time_to_first_relevant_proxy_observation",
               "time_to_first_reference_positive_frontier", "positive_event_cells_touched", "candidate_exposure_per_scan",
               "global_gap_integral", "max_unobserved_gap_auc_fraction", "max_unobserved_gap", "scan_actions",
               "refinement_actions", "proxy_batches", "decoded_frames", "physical_VERIFY_calls", "VERIFY_admitted",
               "VERIFY_rejected", "GPU_seconds", "unused_deadline_seconds", "snapshot_commit_seconds",
               "final_snapshot_commit_elapsed_seconds"]
    aggregates, flat = [], []
    for method in METHODS:
        for deadline in DEADLINES:
            group = frame[(frame.method == method) & (frame.deadline_name == deadline)]
            row = {"method": method, "deadline_name": deadline, "runs": len(group),
                   "exact_action_trace_consistency": group.exact_action_trace.nunique() == 1,
                   "scan_prefix_consistency": group.scan_prefix.nunique() == 1,
                   "confirmed_event_set_consistency": group.semantic_event_set.nunique() == 1,
                   "confirmed_event_sets": sorted(group.semantic_event_set.unique().tolist()),
                   "scheduler_overhead_seconds": "UNAVAILABLE_IN_INHERITED_RUNTIME"}
            flatrow = {k: row[k] for k in ("method", "deadline_name", "runs", "exact_action_trace_consistency", "scan_prefix_consistency", "confirmed_event_set_consistency")}
            for metric in numeric:
                med, low, high = triple(group[metric]); row[metric] = {"median": med, "min": low, "max": high}
                flatrow[f"{metric}_median"], flatrow[f"{metric}_min"], flatrow[f"{metric}_max"] = med, low, high
            aggregates.append(row); flat.append(flatrow)
    dump(TABLES / "METHOD_DEADLINE_MEDIAN_MIN_MAX.json", aggregates)
    pd.DataFrame(flat).to_csv(TABLES / "METHOD_DEADLINE_AGGREGATE.csv", index=False)

    effective = {}
    for method in METHODS:
        rows = [row for row in aggregates if row["method"] == method]
        effective[method] = all(row["F1_at_deadline"]["min"] and row["AnytimeAUC_F1"]["min"] for row in rows)
    if effective["D2"] and not effective["D3"] and effective["D1"]:
        branch, hscan, hcov = "S-A", "ACCEPT_STRUCTURAL_SIGNAL", "REVISE_MORE_SPECIFIC"
    elif effective["D3"] and not effective["D2"]:
        branch, hscan, hcov = "S-B", "ACCEPT_PROXY_DRIVER", "REJECT"
    elif effective["D1"] and not effective["D2"] and not effective["D3"]:
        branch, hscan, hcov = "S-C", "ACCEPT_COMPONENT_INTERACTION", "REVISE_INTERACTION"
    elif effective["D2"] and effective["D3"]:
        branch, hscan, hcov = "S-D", "SIMPLER_COMPONENT_SUFFICIENT", "REVISE"
    elif not effective["D1"]:
        branch, hscan, hcov = "S-E", "REJECT_UNSTABLE_FULL_METHOD", "REVISE"
    else:
        branch, hscan, hcov = "S-F", "REJECT", "REJECT"
    method_summary = frame.groupby("method").agg(AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
                                                   TTFC=("time_to_first_confirmed_event", "median"),
                                                   unique_events=("unique_confirmed_events", "max"),
                                                   deadline_misses=("deadline_met", lambda x: int((~x).sum())),
                                                   GPU_seconds=("GPU_seconds", "mean")).reset_index()
    auc_best = str(method_summary.loc[method_summary.AnytimeAUC_F1.idxmax(), "method"])
    ttfc_valid = method_summary.dropna(subset=["TTFC"]); ttfc_best = str(ttfc_valid.loc[ttfc_valid.TTFC.idxmin(), "method"])
    event_best = method_summary[method_summary.unique_events == method_summary.unique_events.max()].method.tolist()
    d1_auc = float(method_summary[method_summary.method == "D1"].AnytimeAUC_F1.iloc[0])
    d2_auc = float(method_summary[method_summary.method == "D2"].AnytimeAUC_F1.iloc[0])
    recommendation = "D2" if branch == "S-A" else auc_best
    current = ("D2" if branch == "S-A" and d2_auc >= d1_auc - 1e-12 else "D1")
    decision = {"H_SCAN1A": hscan, "branch": branch,
                "COVERAGE_STRUCTURAL_SIGNAL": "PRESENT" if branch == "S-A" else "NOT_ESTABLISHED",
                "OBSERVED_PROXY_EXPLOITATION_DRIVER": "NOT_SUPPORTED" if branch == "S-A" else "UNRESOLVED",
                "H_COV1": hcov, "effectiveness": effective,
                "PSVR_CORE_INNOVATION_PILOT": "WEAK",
                "best_method_by_AnytimeAUC": auc_best, "best_method_by_TTFC": ttfc_best,
                "best_methods_by_unique_events": event_best,
                "recommended_scientific_candidate": recommendation,
                "current_best_H_SCAN1A_method": current,
                "current_best_update_reason": "D2 is simpler and mechanism-informative, but D1 remains operational best if D2 mean AnytimeAUC is lower.",
                "method_summary": json.loads(method_summary.to_json(orient="records")),
                "semantic_samples": 1, "runtime_repeats_are_stability_only": True,
                "pre_existing_related_evidence_disclosed": True,
                "next_experiment": "Register H-SCAN1B to split unobserved-duration/coverage from scan-level/hierarchical debt; do not execute it in this cycle.",
                "next_exact_command": "python scripts/preregister_psvr_hscan1b.py",
                "stop_after_decision": True}
    dump(OUT / "AUDITED_DECISION.json", decision)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
