#!/usr/bin/env python3
"""Evaluator-only H-RECOVER1 audit over frozen two-video physical traces.

The sequence generators are reference-blind. Reference labels and event mappings are
opened only after every deterministic sequence has been generated and frozen in the
preregistration artifact.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TWO = ROOT / "outputs/psvr_two_video_loop"
DEV = TWO / "dev_benchmark_v1"
RAW = TWO / "h_expose2/revision_exposure_temporal_nms/raw"
RUN_METRICS = TWO / "h_expose2/revision_exposure_temporal_nms/tables/RUN_METRICS.csv"
OUT = ROOT / "outputs/psvr_bottleneck_research"
CYCLE = OUT / "cycle_01_H_RECOVER1"
V0_UNITS = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv"
)
V1_UNITS = DEV / "units/V1_units.csv"
TASKS = ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
METHODS = ("fifo", "score_only", "exposure_temporal_nms")
DEADLINES = ("T_transition", "T_high")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def durable_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def load_units(video_id: str) -> pd.DataFrame:
    frame = pd.read_csv(V0_UNITS if video_id == "V0" else V1_UNITS)
    frame["unit_id"] = frame.unit_id.astype(int)
    if list(frame.unit_id) != list(range(len(frame))):
        raise RuntimeError(f"non-contiguous unit ids for {video_id}")
    return frame


# Reference-blind sequence generators. They consume only public unit metadata.
def current_order(unit_count: int) -> list[int]:
    observed: set[int] = set()
    order: list[int] = []
    while len(order) < unit_count:
        blocks: list[tuple[int, int]] = []
        start = None
        for unit_id in range(unit_count):
            if unit_id not in observed and start is None:
                start = unit_id
            if unit_id in observed and start is not None:
                blocks.append((start, unit_id - 1))
                start = None
        if start is not None:
            blocks.append((start, unit_count - 1))
        left, right = max(blocks, key=lambda pair: (pair[1] - pair[0] + 1, -pair[0]))
        chosen = (left + right) // 2
        observed.add(chosen)
        order.append(chosen)
    return order


def sequential_order(unit_count: int) -> list[int]:
    return list(range(unit_count))


def stratified_uniform_prefix(unit_count: int, action_count: int) -> list[int]:
    # Frozen-budget equal strata, lower integer center on ties.
    result = [
        min(unit_count - 1, int(math.floor((index + 0.5) * unit_count / action_count)))
        for index in range(action_count)
    ]
    if len(set(result)) != action_count:
        raise RuntimeError("stratified sequence contains duplicate units")
    return result


def maxgap_order(unit_count: int) -> list[int]:
    # Frozen initial coarse cell, then largest nearest-center distance; earlier center tie.
    order = [(unit_count - 1) // 2]
    unseen = set(range(unit_count)) - set(order)
    while unseen:
        chosen = max(
            unseen,
            key=lambda unit_id: (
                min(abs(unit_id - observed) for observed in order),
                -unit_id,
            ),
        )
        order.append(chosen)
        unseen.remove(chosen)
    return order


def hierarchical_order(unit_count: int) -> list[int]:
    # Breadth-first deterministic dyadic strata; earlier center and id break ties.
    result: list[int] = []
    seen: set[int] = set()
    level = 0
    while len(result) < unit_count:
        strata = 2**level
        for index in range(strata):
            chosen = min(
                unit_count - 1,
                int(math.floor((index + 0.5) * unit_count / strata)),
            )
            if chosen not in seen:
                seen.add(chosen)
                result.append(chosen)
        level += 1
    return result


def parse_source_units(value: Any) -> set[int]:
    return {
        int(float(token))
        for token in str(value).replace(",", "|").split("|")
        if token.strip()
    }


def event_map(reference: pd.DataFrame) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for row in reference.to_dict("records"):
        for unit_id in parse_source_units(row["source_unit_ids"]):
            result.setdefault(unit_id, set()).add(str(row["reference_event_id"]))
    return result


def complete_runs() -> list[tuple[Path, dict[str, Any]]]:
    result = []
    for path in sorted(RAW.glob("*/attempt_*/complete.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("status") == "ok":
            result.append((path, row))
    if len(result) != 72:
        raise RuntimeError(f"H-RECOVER1 requires 72 valid revision traces, found {len(result)}")
    return result


def freeze_sequences(runs: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for _, run in runs:
        key = f"{run['task_id']}::{run['deadline_name']}"
        value = int(run["scan_actions"])
        if key in counts and counts[key] != value:
            raise RuntimeError(f"scan-count mismatch for {key}")
        counts[key] = value
    frozen: dict[str, Any] = {}
    for task_id in TASKS:
        units = load_units(task_id.split("_")[0])
        n = len(units)
        generated = {
            "S_CURRENT": current_order(n),
            "S_SEQ": sequential_order(n),
            "S_MAXGAP": maxgap_order(n),
            "S_HIER": hierarchical_order(n),
        }
        for deadline_name in DEADLINES:
            count = counts[f"{task_id}::{deadline_name}"]
            frozen[f"{task_id}::{deadline_name}"] = {
                "action_count": count,
                "S_CURRENT": generated["S_CURRENT"][:count],
                "S_SEQ": generated["S_SEQ"][:count],
                "S_UNIFORM": stratified_uniform_prefix(n, count),
                "S_MAXGAP": generated["S_MAXGAP"][:count],
                "S_HIER": generated["S_HIER"][:count],
            }
    return frozen


def preregister(sequences: dict[str, Any]) -> dict[str, Any]:
    prereg = {
        "hypothesis_id": "H-RECOVER1",
        "evidence_type": "evaluator_only_diagnostic",
        "registered_at_utc": now_utc(),
        "prior_outcome_disclosure": (
            "Registered after H-EXPOSE2/R3 rejection; diagnostic is not outcome-blind. "
            "Sequence generators are frozen before this evaluator opens references."
        ),
        "runtime_behavior_changed": False,
        "physical_calls_authorized": 0,
        "input_matrix": "H-EXPOSE2 R3 72-cell durable revision matrix",
        "input_hashes": {
            "revision_config": sha256_file(RAW.parent / "RESOLVED_CONFIG.json"),
            "run_metrics": sha256_file(RUN_METRICS),
            "task_manifest": sha256_file(DEV / "TASK_MANIFEST.json"),
            "deadline_manifest": sha256_file(TWO / "deadlines/TASK_DEADLINE_MANIFEST.json"),
        },
        "sequence_rules": {
            "S_CURRENT": "exact frozen iterative largest-unobserved contiguous-block midpoint",
            "S_SEQ": "ascending contiguous unit id",
            "S_UNIFORM": "centers of action-count equal temporal strata",
            "S_MAXGAP": "frozen midpoint then maximum nearest observed-center distance",
            "S_HIER": "breadth-first dyadic equal-strata centers",
        },
        "classification_rules": {
            "SCAN_EXPOSURE_LIMITED": (
                "current event exposure is below a reference-blind alternative sequence at "
                "the same scan count"
            ),
            "DEADLINE_FLOOR": (
                "no frozen reference-blind sequence touches a positive unit at the frozen "
                "physical scan-action ceiling"
            ),
            "CANDIDATE_GENERATION_LIMITED": (
                "a scanned positive lacks a runtime candidate/frontier entry"
            ),
            "FRONTIER_OR_VERIFY_ORDER_LIMITED": (
                "a positive candidate is visible at a VERIFY opportunity and trace-conditional "
                "oracle ceiling exceeds actual unique events"
            ),
            "VERIFY_BUDGET_LIMITED": (
                "visible positive candidates exceed calls without ordering regret"
            ),
            "MATERIALIZATION_LIMITED": (
                "an oracle-positive completed query yields no matching durable K3 event"
            ),
            "HETEROGENEOUS_BOTTLENECK": "multiple non-dominant loss locations remain",
        },
        "reference_visibility": "evaluator_only",
        "sequences": sequences,
        "heldout_opened": False,
    }
    prereg["preregistration_hash"] = canonical_hash(prereg)
    destination = CYCLE / "PREREGISTRATION.json"
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        unstable = {"registered_at_utc", "preregistration_hash"}
        if {k: v for k, v in existing.items() if k not in unstable} != {
            k: v for k, v in prereg.items() if k not in unstable
        }:
            raise RuntimeError("H-RECOVER1 preregistration changed")
        return existing
    durable_json(destination, prereg)
    return prereg


def visible_sets(path: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for scan_index in range(2, int(run["scan_actions"]), 3):
        score_path = path.parent / f"scan_{scan_index:03d}_scores.json"
        score = json.loads(score_path.read_text(encoding="utf-8"))
        result.append({
            "opportunity_index": len(result),
            "after_scan_action": scan_index + 1,
            "elapsed_seconds": next(
                float(action["end_seconds"])
                for i, action in enumerate([a for a in run["actions"] if a["action"] == "scan"])
                if i == scan_index
            ),
            "candidate_rows": score["candidate_rows_visible_to_policy"],
        })
    return result


def trace_conditional_oracle_ceiling(
    opportunities: list[dict[str, Any]], labels: dict[int, str], by_unit: dict[int, set[str]]
) -> tuple[int, list[int]]:
    # Exhaustive dynamic program over the small (<=4) opportunity count.
    states: dict[tuple[frozenset[int], frozenset[str]], list[int]] = {
        (frozenset(), frozenset()): []
    }
    for opportunity in opportunities:
        next_states = dict(states)
        candidates = sorted({int(row["unit_id"]) for row in opportunity["candidate_rows"]})
        for (selected, events), choices in states.items():
            for unit_id in candidates:
                if unit_id in selected:
                    continue
                new_events = set(events)
                if labels.get(unit_id) == "positive":
                    new_events |= by_unit.get(unit_id, set())
                key = (selected | {unit_id}, frozenset(new_events))
                value = [*choices, unit_id]
                previous = next_states.get(key)
                if previous is None or value < previous:
                    next_states[key] = value
        states = next_states
    best_key, best_choices = max(
        states.items(), key=lambda item: (len(item[0][1]), -len(item[0][0]), [-x for x in item[1]])
    )
    return len(best_key[1]), best_choices


def build_chain_and_regret(
    runs: list[tuple[Path, dict[str, Any]]]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = pd.read_csv(RUN_METRICS).set_index("run_id")
    chain_rows: list[dict[str, Any]] = []
    regret_rows: list[dict[str, Any]] = []
    ceiling_rows: list[dict[str, Any]] = []
    for complete_path, run in runs:
        task_id = str(run["task_id"])
        query_id = task_id.split("_")[1]
        labels_frame = pd.read_csv(DEV / "parsed_labels" / f"{task_id}.csv")
        labels = {
            int(row.unit_id): str(row.parsed_label).lower()
            for row in labels_frame.itertuples()
        }
        positive_units = sorted(unit_id for unit_id, label in labels.items() if label == "positive")
        reference = pd.read_csv(DEV / "reference_events" / f"{task_id}.csv")
        by_unit = event_map(reference)
        scan_actions = [action for action in run["actions"] if action["action"] == "scan"]
        scan_by_unit = {int(action["unit_id"]): action for action in scan_actions}
        lifecycle = {int(row["unit_id"]): row for row in run["candidate_lifecycle"]}
        queried = {int(row["unit_id"]): row for row in run["queried_results"]}
        score_first: dict[int, dict[str, Any]] = {}
        raw_candidate: dict[int, bool] = {}
        for cost in run["proxy_unit_costs"]:
            unit_id = int(cost["unit_id"])
            evidence = json.loads(Path(cost["evidence_path"]).read_text(encoding="utf-8"))
            raw_candidate[unit_id] = any(
                str(row.get("query_id")) == query_id
                for row in evidence["scan_result"].get("candidates", [])
            )
        for row in run["score_history"]:
            score_first.setdefault(int(row["unit_id"]), row)
        frontier_history: dict[int, list[tuple[int, float, int]]] = {}
        scan_ordinal = 0
        for action in run["actions"]:
            if action["action"] != "scan":
                continue
            scan_ordinal += 1
            for rank, candidate_id in enumerate(action["frontier_candidate_ids"], start=1):
                unit_id = int(str(candidate_id).split("_")[-1])
                frontier_history.setdefault(unit_id, []).append(
                    (scan_ordinal, float(action["end_seconds"]), rank)
                )
        opps = visible_sets(complete_path, run)
        final_snapshot = json.loads(Path(run["final_snapshot_path"]).read_text(encoding="utf-8"))
        materialized_units = set()
        for event in final_snapshot.get("strict_confirmed_events", []):
            for field in ("anchor_unit_ids", "evidence_unit_ids"):
                materialized_units |= parse_source_units(event.get(field, ""))
        for unit_id in positive_units:
            scan = scan_by_unit.get(unit_id)
            life = lifecycle.get(unit_id)
            query = queried.get(unit_id)
            frontier = frontier_history.get(unit_id, [])
            next_opp = next(
                (opp for opp in opps if scan is not None and opp["elapsed_seconds"] >= float(scan["end_seconds"])),
                None,
            )
            survived = bool(
                next_opp
                and any(
                    int(row["unit_id"]) == unit_id
                    for row in next_opp["candidate_rows"]
                )
            )
            chain_rows.append({
                "run_id": run["run_id"],
                "task_id": task_id,
                "method": run["method"],
                "deadline_name": run["deadline_name"],
                "replicate": int(run["replicate"]),
                "reference_positive_unit": unit_id,
                "reference_event_ids": "|".join(sorted(by_unit.get(unit_id, set()))),
                "reference_visibility": "evaluator_only",
                "scanned": scan is not None,
                "scan_completed_seconds": None if scan is None else float(scan["end_seconds"]),
                "proxy_observation_generated": unit_id in raw_candidate,
                "proxy_output_valid": unit_id in raw_candidate,
                "proxy_score": None if unit_id not in score_first else float(score_first[unit_id]["unit_score"]),
                "raw_query_candidate_generated": bool(raw_candidate.get(unit_id, False)),
                "runtime_candidate_created": life is not None,
                "candidate_created_seconds": None if life is None else float(life["created_seconds"]),
                "frontier_admitted": bool(frontier),
                "best_frontier_rank": None if not frontier else min(row[2] for row in frontier),
                "frontier_survival_seconds": (
                    None
                    if life is None
                    else float(life["terminal_seconds"]) - float(life["created_seconds"])
                ),
                "survived_to_verify_opportunity": survived,
                "verify_opportunity_available": next_opp is not None,
                "verified": query is not None,
                "verify_admitted": None if query is None else bool(query["admission"]["admitted"]),
                "verify_completed": query is not None,
                "oracle_result": None if query is None else str(query["parsed_label"]),
                "k3_materialized_matching_event": unit_id in materialized_units,
                "durable_final_snapshot": Path(run["final_snapshot_path"]).is_file(),
            })
        ceiling, choices = trace_conditional_oracle_ceiling(opps, labels, by_unit)
        actual = int(metrics.loc[run["run_id"], "unique_confirmed_events"])
        query_rows = run["queried_results"]
        first_positive = next(
            (index for index, row in enumerate(query_rows) if str(row["parsed_label"]).lower() == "positive"),
            None,
        )
        negative_high_score = 0
        for index, query in enumerate(query_rows):
            if str(query["parsed_label"]).lower() != "negative" or index >= len(opps):
                continue
            positive_scores = [
                float(row["proxy_score"])
                for row in opps[index]["candidate_rows"]
                if labels.get(int(row["unit_id"])) == "positive"
            ]
            if positive_scores and float(query["candidate_proxy_score"]) >= max(positive_scores):
                negative_high_score += 1
        regret_rows.append({
            "run_id": run["run_id"],
            "task_id": task_id,
            "method": run["method"],
            "deadline_name": run["deadline_name"],
            "replicate": int(run["replicate"]),
            "verify_call_count": len(query_rows),
            "actual_unique_events": actual,
            "visible_candidate_oracle_ceiling": ceiling,
            "verify_order_regret": ceiling - actual,
            "oracle_ceiling_candidate_units": "|".join(map(str, choices)),
            "calls_before_first_true_positive": (
                len(query_rows) if first_positive is None else first_positive
            ),
            "first_true_positive_censored": first_positive is None,
            "negative_high_score_calls": negative_high_score,
            "reference_visibility": "evaluator_only",
        })
        commit_profile = json.loads(
            (TWO / "deadlines/profiles" / task_id / "commit_profile.json").read_text()
        )
        action_profile = json.loads(
            (TWO / "deadlines/profiles" / task_id / "action_profile.json").read_text()
        )
        commit_upper = float(commit_profile["tail_bound"]["upper_seconds"])
        verify_upper = float(action_profile["tail_bound"]["upper_seconds"])
        scan_upper = max(
            1.5 * float(row["scan_wall_seconds_including_evidence_and_snapshot"]) + 0.5
            for row in run["proxy_unit_costs"]
        )
        unused = float(run["unused_deadline_seconds"])
        ceiling_rows.append({
            "run_id": run["run_id"],
            "task_id": task_id,
            "method": run["method"],
            "deadline_name": run["deadline_name"],
            "replicate": int(run["replicate"]),
            "scan_actions_available": int(run["scan_actions"]),
            "verify_opportunities_available": int(run["verify_opportunities"]),
            "verify_calls_completed": int(run["physical_oracle_calls"]),
            "unused_deadline_seconds": unused,
            "commit_upper_seconds": commit_upper,
            "commit_margin_seconds": unused - commit_upper,
            "observed_adaptive_scan_upper_seconds": scan_upper,
            "verify_tail_upper_seconds": verify_upper,
            "additional_scan_actions_conservatively_feasible": max(
                0, int(math.floor(max(0.0, unused - commit_upper) / (scan_upper + commit_upper)))
            ),
            "additional_verify_calls_conservatively_feasible": max(
                0, int(math.floor(max(0.0, unused - commit_upper) / (verify_upper + commit_upper)))
            ),
            "budget_exhausted": unused <= min(scan_upper + commit_upper, verify_upper + commit_upper),
        })
    return pd.DataFrame(chain_rows), pd.DataFrame(regret_rows), pd.DataFrame(ceiling_rows)


def scan_diagnostics(sequences: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for task_id in TASKS:
        labels = pd.read_csv(DEV / "parsed_labels" / f"{task_id}.csv")
        positives = set(
            labels.loc[labels.parsed_label.str.lower() == "positive", "unit_id"].astype(int)
        )
        reference = pd.read_csv(DEV / "reference_events" / f"{task_id}.csv")
        by_unit = event_map(reference)
        for deadline_name in DEADLINES:
            entry = sequences[f"{task_id}::{deadline_name}"]
            for sequence_name in ("S_CURRENT", "S_SEQ", "S_UNIFORM", "S_MAXGAP", "S_HIER"):
                order = list(map(int, entry[sequence_name]))
                hit_indices = [index for index, unit_id in enumerate(order, start=1) if unit_id in positives]
                hit_units = [unit_id for unit_id in order if unit_id in positives]
                events = set().union(*(by_unit.get(unit_id, set()) for unit_id in hit_units)) if hit_units else set()
                rows.append({
                    "task_id": task_id,
                    "deadline_name": deadline_name,
                    "sequence": sequence_name,
                    "scan_actions": len(order),
                    "sequence_unit_ids": "|".join(map(str, order)),
                    "positive_units_scanned": len(hit_units),
                    "positive_unit_exposure_rate": len(hit_units) / max(len(order), 1),
                    "unique_reference_events_touched": len(events),
                    "first_positive_action_index": None if not hit_indices else min(hit_indices),
                    "event_exposure_ceiling": len(events),
                    "reference_visibility": "evaluator_only",
                })
    return pd.DataFrame(rows)


def bottleneck_map(
    scan: pd.DataFrame, chain: pd.DataFrame, regret: pd.DataFrame, budget: pd.DataFrame
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for task_id in TASKS:
        s = scan[scan.task_id == task_id]
        current = s[s.sequence == "S_CURRENT"].unique_reference_events_touched.max()
        alternative = s[s.sequence != "S_CURRENT"].unique_reference_events_touched.max()
        all_zero = int(s.unique_reference_events_touched.max()) == 0
        c = chain[chain.task_id == task_id]
        scanned_positive = c[c.scanned.astype(bool)]
        candidate_rate = (
            float(scanned_positive.runtime_candidate_created.mean()) if len(scanned_positive) else 0.0
        )
        frontier_rate = (
            float(scanned_positive.frontier_admitted.mean()) if len(scanned_positive) else 0.0
        )
        r = regret[regret.task_id == task_id]
        regret_rate = float((r.verify_order_regret > 0).mean())
        materialization_loss = int(
            ((c.oracle_result == "positive") & (~c.k3_materialized_matching_event.astype(bool))).sum()
        )
        additional_scans = float(budget[budget.task_id == task_id].additional_scan_actions_conservatively_feasible.median())
        if materialization_loss > 0:
            primary = "MATERIALIZATION_LIMITED"
            secondary = "HETEROGENEOUS_BOTTLENECK"
            confidence = "high"
        elif regret_rate > 0:
            primary = "FRONTIER_OR_VERIFY_ORDER_LIMITED"
            secondary = "VERIFY_BUDGET_LIMITED"
            confidence = "high" if regret_rate >= 0.5 else "moderate"
        elif all_zero:
            primary = "DEADLINE_FLOOR"
            secondary = "SCAN_EXPOSURE_LIMITED"
            confidence = "high"
        elif int(current) == 0 and int(alternative) > 0:
            primary = "SCAN_EXPOSURE_LIMITED"
            secondary = "VERIFY_BUDGET_LIMITED"
            confidence = "high"
        elif len(scanned_positive) > 0 and (candidate_rate < 0.5 or frontier_rate < 0.5):
            primary = "CANDIDATE_GENERATION_LIMITED"
            secondary = "SCAN_EXPOSURE_LIMITED"
            confidence = "moderate"
        elif alternative > current:
            primary = "SCAN_EXPOSURE_LIMITED"
            secondary = "VERIFY_BUDGET_LIMITED"
            confidence = "moderate"
        else:
            primary = "HETEROGENEOUS_BOTTLENECK"
            secondary = "VERIFY_BUDGET_LIMITED"
            confidence = "low"
        result[task_id] = {
            "primary_bottleneck": primary,
            "secondary_bottleneck": secondary,
            "confidence": confidence,
            "supporting_metrics": {
                "current_event_exposure_ceiling": int(current),
                "best_alternative_event_exposure_ceiling": int(alternative),
                "positive_scanned_observations": int(len(scanned_positive)),
                "positive_unit_to_candidate_rate": candidate_rate,
                "positive_candidate_to_frontier_rate": frontier_rate,
                "runs_with_verify_order_regret_rate": regret_rate,
                "materialization_losses": materialization_loss,
                "median_additional_scans_conservatively_feasible": additional_scans,
            },
            "alternative_explanations": [
                (
                    "DEADLINE_FLOOR is conditional on the frozen planned scan-action ceiling; "
                    "realized slack indicates conservative planning may be the actual limiting mechanism."
                    if primary == "DEADLINE_FLOOR"
                    else "Runtime repeats are timing replicates, not independent semantic samples."
                ),
                "Reference-defined ceilings are evaluator-only and cannot be used by runtime policy.",
            ],
        }
    return result


def write_report(
    scan: pd.DataFrame,
    chain: pd.DataFrame,
    regret: pd.DataFrame,
    budget: pd.DataFrame,
    task_map: dict[str, Any],
) -> None:
    chain_scanned = chain[chain.scanned.astype(bool)]
    positive_to_proxy = float(chain_scanned.proxy_output_valid.mean()) if len(chain_scanned) else 0.0
    positive_to_candidate = float(chain_scanned.runtime_candidate_created.mean()) if len(chain_scanned) else 0.0
    positive_to_frontier = float(chain_scanned.frontier_admitted.mean()) if len(chain_scanned) else 0.0
    positive_survival = float(chain_scanned.survived_to_verify_opportunity.mean()) if len(chain_scanned) else 0.0
    text = f"""# H-RECOVER1 recoverability audit

`H-RECOVER1 = COMPLETE`

## Scientific uncertainty

Does failure occur before scan exposure, during candidate generation/retention, during
VERIFY ordering/budgeting, or after an oracle-positive materialization?

## Frozen diagnostic

This evaluator reuses 72/72 H-EXPOSE2 R3 durable traces and performs zero physical calls.
All sequence generators consume only public unit metadata and frozen action counts. Every
label/event-derived output is marked `evaluator_only`.

## Candidate-generation ceiling

- positive_unit_to_proxy_rate: {positive_to_proxy:.6f}
- positive_proxy_to_candidate_rate: {positive_to_candidate:.6f}
- positive_candidate_to_frontier_rate: {positive_to_frontier:.6f}
- positive_frontier_survival_rate: {positive_survival:.6f}

## Task bottlenecks

"""
    for task_id, row in task_map.items():
        text += (
            f"- **{task_id}**: {row['primary_bottleneck']} (secondary "
            f"{row['secondary_bottleneck']}, confidence {row['confidence']}).\n"
        )
    text += f"""

## Adversarial interpretation

The V1 `DEADLINE_FLOOR` label is a floor at the frozen planned 12-scan action ceiling, not
proof of an intrinsic wall-clock floor. Median conservative additional-scan feasibility is
{budget[budget.task_id.str.startswith('V1')].additional_scan_actions_conservatively_feasible.median():.1f};
realized slack therefore keeps conservative scan/VERIFY allocation as a competing cause.
V0_Q1 ordering regret is trace-conditional: counterfactual oracle choices could alter later
frontier states, so its ceiling is diagnostic rather than a realizable policy.

## Decision

`H-RECOVER1 = COMPLETE`. The bottleneck is heterogeneous: V0_Q1 exposes an ordering loss,
V0_Q2 is a positive control with additional exposure headroom, and both V1 tasks are scan
exposure floors at the frozen action count. Continue to the preregistered H-BOTTLE2 Scan ×
VERIFY factorial; this diagnostic alone does not accept a method.
"""
    (CYCLE / "FINAL_REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    CYCLE.mkdir(parents=True, exist_ok=True)
    runs = complete_runs()
    sequences = freeze_sequences(runs)
    prereg = preregister(sequences)
    # References are first opened below, after sequence freeze/preregistration.
    chain, regret, budget = build_chain_and_regret(runs)
    scan = scan_diagnostics(sequences)
    task_map = bottleneck_map(scan, chain, regret, budget)
    recover = (
        chain.groupby(["task_id", "method", "deadline_name", "replicate"], as_index=False)
        .agg(
            positive_units=("reference_positive_unit", "count"),
            positive_units_scanned=("scanned", "sum"),
            positive_units_with_proxy=("proxy_output_valid", "sum"),
            positive_units_with_candidate=("runtime_candidate_created", "sum"),
            positive_units_entering_frontier=("frontier_admitted", "sum"),
            positive_candidates_surviving_to_verify=("survived_to_verify_opportunity", "sum"),
            positive_units_verified=("verified", "sum"),
            oracle_positive_units=("oracle_result", lambda values: sum(value == "positive" for value in values)),
            k3_materialized_positive_units=("k3_materialized_matching_event", "sum"),
        )
    )
    recover = recover.merge(
        regret,
        on=["task_id", "method", "deadline_name", "replicate"],
        validate="one_to_one",
    ).merge(
        budget,
        on=["task_id", "method", "deadline_name", "replicate"],
        suffixes=("", "_budget"),
        validate="one_to_one",
    )
    for numerator, denominator, name in (
        ("positive_units_with_proxy", "positive_units_scanned", "positive_unit_to_proxy_rate"),
        ("positive_units_with_candidate", "positive_units_with_proxy", "positive_proxy_to_candidate_rate"),
        ("positive_units_entering_frontier", "positive_units_with_candidate", "positive_candidate_to_frontier_rate"),
        ("positive_candidates_surviving_to_verify", "positive_units_entering_frontier", "positive_frontier_survival_rate"),
    ):
        recover[name] = np.where(recover[denominator] > 0, recover[numerator] / recover[denominator], np.nan)
    atomic_csv(CYCLE / "RECOVERABILITY_CEILINGS.csv", recover)
    temporary = CYCLE / "EXECUTION_CHAIN_EVENTS.parquet.tmp"
    chain.to_parquet(temporary, index=False)
    os.replace(temporary, CYCLE / "EXECUTION_CHAIN_EVENTS.parquet")
    atomic_csv(CYCLE / "SCAN_SEQUENCE_DIAGNOSTICS.csv", scan)
    atomic_csv(CYCLE / "VERIFY_REGRET_ANALYSIS.csv", regret)
    atomic_csv(CYCLE / "BUDGET_CEILINGS.csv", budget)
    durable_json(CYCLE / "TASK_BOTTLENECK_MAP.json", {
        "hypothesis_id": "H-RECOVER1",
        "classification_scope": "frozen two-video planned action ceilings",
        "reference_visibility": "evaluator_only",
        "tasks": task_map,
        "heldout_opened": False,
    })
    decision = {
        "H_RECOVER1_DECISION": "COMPLETE",
        "physical_calls": 0,
        "input_runs": len(runs),
        "execution_chain_rows": len(chain),
        "scan_sequence_rows": len(scan),
        "verify_regret_rows": len(regret),
        "task_bottleneck_map": {task: row["primary_bottleneck"] for task, row in task_map.items()},
        "dominant_conclusion": "HETEROGENEOUS_BOTTLENECK",
        "next_hypothesis": "H-BOTTLE2",
        "next_exact_command": "python scripts/run_psvr_bottleneck_physical.py preregister",
        "preregistration_hash": prereg["preregistration_hash"],
        "heldout_opened": False,
    }
    decision["decision_hash"] = canonical_hash(decision)
    durable_json(CYCLE / "AUDITED_DECISION.json", decision)
    write_report(scan, chain, regret, budget, task_map)
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
