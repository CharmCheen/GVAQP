#!/usr/bin/env python3
"""Two-video trusted-policy SCAN scheduling headroom audit.

This script performs evaluator-side analysis only.  Causal policies are frozen
in ``garc_eval.scan_headroom.trusted_policies`` and never receive the hidden
objects loaded below.
"""
from __future__ import annotations

import ast
import bisect
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for directory in (SRC, SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from garc_eval.scan_headroom.trusted_policies import (  # noqa: E402
    CAUSAL_POLICY_IDS,
    PublicScanState,
    PublicUnit,
    make_policy,
)
from partial_scan_pilot_common import (  # noqa: E402
    BASE_FEATURES,
    TEMPORAL_NMS_IOU,
    atomic_csv,
    atomic_json,
    atomic_text,
    temporal_iou,
    transition,
)


BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"
IMM = BENCH / "immutable"
DER = BENCH / "derived"
PHYSICAL = DER / "policy_runs/physical"
OUT = ROOT / "outputs/scan_optimization_headroom_audit_v1"
POLICY_SOURCE = SRC / "garc_eval/scan_headroom/trusted_policies.py"
CHECKPOINTS = (0.05, 0.10, 0.20, 0.30, 0.40, 0.60, 0.80, 1.00)
RANDOM_SEEDS = tuple(range(50))
PHYSICAL_BUDGET_SEC = 60.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_cost(previous: dict[str, Any] | None, selected: dict[str, Any], model: dict) -> tuple[float, dict]:
    tr = transition(previous, selected)
    key = f"{tr['transition_class']}|{tr['same_or_cross_gop']}|CONTROLLED_WARM"
    cost = float(
        model["strata"].get(key, {}).get(
            "q90_action_cost_sec", model["fallback_q90_sec"]
        )
    )
    return cost, tr


def public_units(units: pd.DataFrame) -> tuple[PublicUnit, ...]:
    return tuple(
        PublicUnit(str(row.unit_id), float(row.start_sec), float(row.end_sec))
        for row in units.itertuples(index=False)
    )


def causal_order(policy_id: str, seed: int, units: pd.DataFrame, model: dict, budget: float) -> list[dict]:
    policy = make_policy(policy_id, seed)
    frozen_units = public_units(units)
    by_id = {str(row["unit_id"]): row for row in units.to_dict("records")}
    scanned: list[str] = []
    rows: list[dict] = []
    previous = None
    elapsed = 0.0
    while len(scanned) < len(units):
        state = PublicScanState(
            units=frozen_units,
            scanned_unit_ids=tuple(scanned),
            current_unit_id=None if previous is None else str(previous["unit_id"]),
            remaining_budget_sec=max(0.0, budget - elapsed),
            past_action_costs_sec=tuple(row["estimated_action_cost_sec"] for row in rows),
            revealed_candidate_ids=(),
        )
        selected_id = policy.choose_next_unit(state)
        if selected_id in scanned or selected_id not in by_id:
            raise RuntimeError(f"invalid action from {policy_id}: {selected_id}")
        selected = by_id[selected_id]
        cost, tr = frozen_cost(previous, selected, model)
        elapsed += cost
        scanned.append(selected_id)
        rows.append(
            {
                "action_index": len(scanned),
                "unit_id": selected_id,
                "estimated_action_cost_sec": cost,
                "cumulative_estimated_cost_sec": elapsed,
                **tr,
            }
        )
        previous = selected
    return rows


def unit_event_map(mapping: pd.DataFrame) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in mapping.itertuples(index=False):
        for unit_id in json.loads(row.source_unit_ids):
            result.setdefault(str(unit_id), set()).add(str(row.reference_event_id))
    return result


def oracle_greedy_order(units: pd.DataFrame, model: dict, events_by_unit: dict[str, set[str]]) -> list[dict]:
    """Feasible hidden-information greedy comparator, not a proven optimum."""
    by_id = {str(row["unit_id"]): row for row in units.to_dict("records")}
    index = dict(zip(units.unit_id.astype(str), units.unit_index.astype(int)))
    remaining = set(by_id)
    exposed: set[str] = set()
    previous = None
    elapsed = 0.0
    rows: list[dict] = []
    while remaining:
        scored = []
        for unit_id in remaining:
            cost, tr = frozen_cost(previous, by_id[unit_id], model)
            gain = len(events_by_unit.get(unit_id, set()) - exposed)
            distance = 0.0 if previous is None else abs(
                float(by_id[unit_id]["start_sec"]) - float(previous["start_sec"])
            )
            scored.append((gain / max(cost, 1e-12), gain, -cost, -distance, -index[unit_id], unit_id, tr))
        *_, selected_id, tr = max(scored)
        selected = by_id[selected_id]
        cost, _ = frozen_cost(previous, selected, model)
        exposed |= events_by_unit.get(selected_id, set())
        elapsed += cost
        remaining.remove(selected_id)
        rows.append(
            {
                "action_index": len(rows) + 1,
                "unit_id": selected_id,
                "estimated_action_cost_sec": cost,
                "cumulative_estimated_cost_sec": elapsed,
                **tr,
            }
        )
        previous = selected
    return rows


def max_unobserved_gap(scanned: list[str], units: pd.DataFrame) -> tuple[int, float]:
    if not scanned:
        return len(units), float(units.end_sec.max() - units.start_sec.min())
    by_id = dict(zip(units.unit_id.astype(str), units.unit_index.astype(int)))
    indices = sorted(by_id[unit_id] for unit_id in scanned)
    gaps = [indices[0], len(units) - 1 - indices[-1]]
    gaps.extend(right - left - 1 for left, right in zip(indices, indices[1:]))
    gap_units = max(gaps, default=0)
    return gap_units, gap_units * float((units.end_sec - units.start_sec).median())


def load_raw(video_id: str, units: pd.DataFrame) -> dict[str, list[dict]]:
    result = {}
    for unit_id in units.unit_id.astype(str):
        path = IMM / "scan_outputs" / video_id / unit_id / "raw_candidates.json"
        result[unit_id] = json.loads(path.read_text())
    return result


def exact_visible(
    video_id: str,
    scanned: list[str],
    raw_by_unit: dict[str, list[dict]],
    references: pd.DataFrame,
) -> tuple[set[str], int, int, int]:
    raw = [row for unit_id in scanned for row in raw_by_unit.get(unit_id, [])]
    if raw:
        frame = pd.DataFrame(raw)
        normalized = []
        for feature in BASE_FEATURES:
            values = pd.to_numeric(frame[feature], errors="coerce").fillna(0.0)
            ranks = pd.Series(0.0, index=frame.index)
            positive = values > 0
            if positive.any():
                ranks.loc[positive] = values.loc[positive].rank(
                    method="average", pct=True
                )
            normalized.append(ranks)
        frame["candidate_score"] = pd.concat(normalized, axis=1).mean(axis=1)
        ordered = frame.sort_values(
            ["candidate_score", "candidate_id"], ascending=[False, True]
        )
        max_duration = float(
            (ordered.candidate_end_sec - ordered.candidate_start_sec).max()
        )
        admitted: list[dict] = []
        admitted_starts: list[float] = []
        for row in ordered.to_dict("records"):
            start = float(row["candidate_start_sec"])
            end = float(row["candidate_end_sec"])
            left = bisect.bisect_left(admitted_starts, start - max_duration)
            right = bisect.bisect_right(admitted_starts, end)
            if any(
                temporal_iou(row, prior) >= TEMPORAL_NMS_IOU
                for prior in admitted[left:right]
            ):
                continue
            location = bisect.bisect_right(admitted_starts, start)
            admitted_starts.insert(location, start)
            admitted.insert(location, row)
        candidates = pd.DataFrame(admitted)
        candidates["generation_state_hash"] = "HEADROOM_EVALUATOR_REPLAY"
    else:
        candidates = pd.DataFrame(columns=[
            "candidate_id", "video_id", "source_unit_ids",
            "candidate_start_sec", "candidate_end_sec", "generation_state_hash",
        ])
    relevant = references[references.actor_type.eq("motor_vehicle")]
    if len(candidates) and len(relevant):
        candidate_start = candidates.candidate_start_sec.to_numpy(float)[:, None]
        candidate_end = candidates.candidate_end_sec.to_numpy(float)[:, None]
        reference_start = relevant.event_start_sec.to_numpy(float)[None, :]
        reference_end = relevant.event_end_sec.to_numpy(float)[None, :]
        intersection = np.maximum(
            0.0,
            np.minimum(candidate_end, reference_end)
            - np.maximum(candidate_start, reference_start),
        )
        midpoint = (reference_start + reference_end) / 2.0
        matched = (intersection >= 0.5) | (
            (candidate_start <= midpoint) & (midpoint <= candidate_end)
        )
        event_mask = matched.any(axis=0)
        events = set(relevant.reference_event_id.astype(str).to_numpy()[event_mask])
        mapped_candidates = int(matched.any(axis=1).sum())
        redundant_matches = max(0, int(matched.sum()) - len(events))
    else:
        events = set()
        mapped_candidates = 0
        redundant_matches = 0
    return events, len(candidates), mapped_candidates, redundant_matches


def prefix_at_budget(order: list[dict], deadline: float) -> list[dict]:
    return [
        row for row in order
        if float(row["cumulative_estimated_cost_sec"]) <= deadline + 1e-9
    ]


def grid_auc(frame: pd.DataFrame, value: str) -> float:
    ordered = frame.sort_values("budget_fraction")
    x = np.r_[0.0, ordered.budget_fraction.to_numpy(float)]
    y = np.r_[0.0, ordered[value].to_numpy(float)]
    return float(np.trapezoid(y, x))


def static_policy_audit() -> dict:
    source = POLICY_SOURCE.read_text()
    tree = ast.parse(source)
    forbidden_tokens = {
        "reference_events", "candidate_event_map", "scan_outputs",
        "hidden_state", "future_runtime", "evaluator", "open(", "subprocess",
    }
    imports = []
    calls = []
    attributes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call):
            calls.append(ast.unparse(node.func))
        elif isinstance(node, ast.Attribute):
            attributes.append(ast.unparse(node))
    bad_tokens = sorted(token for token in forbidden_tokens if token in source)
    bad_calls = sorted(
        call for call in calls
        if call in {"open", "exec", "eval", "compile", "__import__"}
    )
    allowed_imports = {"__future__", "dataclasses", "math", "random"}
    bad_imports = sorted(set(imports) - allowed_imports)
    allowed_state_fields = {
        "units", "scanned_unit_ids", "current_unit_id", "remaining_budget_sec",
        "past_action_costs_sec", "revealed_candidate_ids",
        "revealed_observations",
    }
    state_attributes = {
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "public_state"
    }
    bad_state_fields = sorted(state_attributes - allowed_state_fields)
    passed = not (bad_tokens or bad_calls or bad_imports or bad_state_fields)
    return {
        "status": "PASS" if passed else "FAIL",
        "policy_source": str(POLICY_SOURCE.relative_to(ROOT)),
        "policy_source_sha256": sha256(POLICY_SOURCE),
        "causal_policy_ids": list(CAUSAL_POLICY_IDS),
        "allowed_public_state_fields": sorted(allowed_state_fields),
        "observed_public_state_fields": sorted(state_attributes),
        "forbidden_token_hits": bad_tokens,
        "forbidden_calls": bad_calls,
        "forbidden_imports": bad_imports,
        "forbidden_state_fields": bad_state_fields,
        "arbitrary_external_policy_submission": False,
    }


def replay_audit() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    timeline = pd.read_csv(IMM / "timeline_units.csv")
    references = pd.read_csv(IMM / "reference_events.csv")
    mapping = pd.read_parquet(DER / "candidate_event_map.parquet")
    mapping = mapping[mapping.partition_offset_sec.eq(0)].copy()
    model = json.loads((DER / "cost_calibration/conservative_cost_model.json").read_text())
    all_order_rows: list[dict] = []
    checkpoint_rows: list[dict] = []
    summary_rows: list[dict] = []

    for video_id, units in timeline.groupby("video_id", sort=True):
        units = units.sort_values("unit_index").reset_index(drop=True)
        refs = references[references.video_id.eq(video_id)].copy()
        video_map = mapping[mapping.video_id.eq(video_id)]
        events_by_unit = unit_event_map(video_map)
        ceiling_events = set(video_map.reference_event_id.astype(str))
        all_reference_count = len(refs)
        raw_by_unit = load_raw(video_id, units)

        sequential = causal_order("SEQUENTIAL", 0, units, model, float("inf"))
        common_bmax = float(sequential[-1]["cumulative_estimated_cost_sec"])
        runs: list[tuple[str, int, list[dict], str]] = []
        for policy_id in CAUSAL_POLICY_IDS:
            seeds = RANDOM_SEEDS if policy_id == "RANDOM_WITHOUT_REPLACEMENT" else (0,)
            for seed in seeds:
                runs.append((policy_id, seed, causal_order(policy_id, seed, units, model, common_bmax), "CAUSAL"))
        runs.append(("OFFLINE_EVENT_ORACLE_GREEDY", -1, oracle_greedy_order(units, model, events_by_unit), "EVALUATOR_ONLY_NONCAUSAL"))

        for policy_id, seed, order, method_class in runs:
            fast_ever: set[str] = set()
            fast_counts: list[int] = []
            for row in order:
                fast_ever |= events_by_unit.get(str(row["unit_id"]), set())
                fast_counts.append(len(fast_ever))
                all_order_rows.append(
                    {
                        "video_id": video_id, "policy_id": policy_id,
                        "seed": seed, "method_class": method_class,
                        **row, "fast_distinct_events_exposed": len(fast_ever),
                    }
                )

            run_checkpoints = []
            for fraction in CHECKPOINTS:
                deadline = fraction * common_bmax
                prefix = prefix_at_budget(order, deadline)
                scanned = [str(row["unit_id"]) for row in prefix]
                fast_events = set().union(
                    *(events_by_unit.get(unit_id, set()) for unit_id in scanned)
                ) if scanned else set()
                exact_current, candidate_count, mapped_candidates, redundant = exact_visible(
                    video_id, scanned, raw_by_unit, refs
                )
                gap_units, gap_sec = max_unobserved_gap(scanned, units)
                elapsed = float(prefix[-1]["cumulative_estimated_cost_sec"]) if prefix else 0.0
                transition_distances = [float(row["seek_distance_sec"]) for row in prefix]
                covered = float(
                    units[units.unit_id.astype(str).isin(scanned)]
                    .eval("end_sec - start_sec").sum()
                )
                payload = {
                    "video_id": video_id, "policy_id": policy_id, "seed": seed,
                    "method_class": method_class, "budget_fraction": fraction,
                    "deadline_sec": deadline, "action_count": len(prefix),
                    "used_estimated_cost_sec": elapsed,
                    "unused_budget_sec": deadline - elapsed,
                    "distinct_events_exposed": len(fast_events),
                    "exposure_recall_offset0_ceiling": len(fast_events) / max(1, len(ceiling_events)),
                    "exposure_recall_all_reference": len(fast_events) / max(1, all_reference_count),
                    "exact_current_visible_event_count": len(exact_current),
                    "fast_vs_exact_current_delta": len(fast_events) - len(exact_current),
                    "visible_candidate_count": candidate_count,
                    "mapped_candidate_count": mapped_candidates,
                    "candidate_event_match_redundancy_count": redundant,
                    "candidate_event_match_redundancy_rate": redundant / max(1, mapped_candidates),
                    "maximum_unobserved_gap_units": gap_units,
                    "maximum_unobserved_gap_sec": gap_sec,
                    "covered_duration_sec": covered,
                    "seek_count": sum(distance > 10.000001 for distance in transition_distances),
                    "mean_transition_distance_sec": float(np.mean(transition_distances)) if transition_distances else 0.0,
                    "distinct_events_per_estimated_second": len(fast_events) / max(elapsed, 1e-12),
                }
                checkpoint_rows.append(payload)
                run_checkpoints.append(payload)

            run_frame = pd.DataFrame(run_checkpoints)
            first_rows = [row for row in order if events_by_unit.get(str(row["unit_id"]), set())]
            first_time = float(first_rows[0]["cumulative_estimated_cost_sec"]) if first_rows else np.nan
            replay_60 = [
                (float(row["cumulative_estimated_cost_sec"]), fast_counts[index] / max(1, len(ceiling_events)))
                for index, row in enumerate(order)
                if float(row["cumulative_estimated_cost_sec"]) <= PHYSICAL_BUDGET_SEC
            ]
            summary_rows.append(
                {
                    "video_id": video_id, "policy_id": policy_id, "seed": seed,
                    "method_class": method_class,
                    "common_full_scan_budget_sec": common_bmax,
                    "exposure_grid_auc": grid_auc(run_frame, "exposure_recall_offset0_ceiling"),
                    "exposure_all_reference_grid_auc": grid_auc(run_frame, "exposure_recall_all_reference"),
                    "exposure_step_auc_at_60sec": step_auc(
                        [value[0] for value in replay_60],
                        [value[1] for value in replay_60],
                        PHYSICAL_BUDGET_SEC,
                    ),
                    "time_to_first_event_estimated_sec": first_time,
                    "recall_at_10pct": float(run_frame.loc[run_frame.budget_fraction.eq(.10), "exposure_recall_offset0_ceiling"].iloc[0]),
                    "recall_at_20pct": float(run_frame.loc[run_frame.budget_fraction.eq(.20), "exposure_recall_offset0_ceiling"].iloc[0]),
                    "recall_at_40pct": float(run_frame.loc[run_frame.budget_fraction.eq(.40), "exposure_recall_offset0_ceiling"].iloc[0]),
                    "recall_at_60pct": float(run_frame.loc[run_frame.budget_fraction.eq(.60), "exposure_recall_offset0_ceiling"].iloc[0]),
                    "offset0_exposable_event_count": len(ceiling_events),
                    "all_reference_event_count": all_reference_count,
                }
            )

    order_frame = pd.DataFrame(all_order_rows)
    checkpoint_frame = pd.DataFrame(checkpoint_rows)
    summary_frame = pd.DataFrame(summary_rows)
    return order_frame, checkpoint_frame, summary_frame


def step_auc(times: list[float], recalls: list[float], budget: float) -> float:
    area = 0.0
    for index, start in enumerate(times):
        end = times[index + 1] if index + 1 < len(times) else budget
        area += recalls[index] * max(0.0, min(end, budget) - min(start, budget))
    return area / budget


def physical_audit() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    timeline = pd.read_csv(IMM / "timeline_units.csv")
    references = pd.read_csv(IMM / "reference_events.csv")
    mapping = pd.read_parquet(DER / "candidate_event_map.parquet")
    mapping = mapping[mapping.partition_offset_sec.eq(0)].copy()
    enriched: list[dict] = []
    summaries: list[dict] = []
    trace_hashes = {}

    for trace_path in sorted(PHYSICAL.glob("*/action_trace.jsonl")):
        trace_hashes[str(trace_path.relative_to(ROOT))] = sha256(trace_path)
        source_rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
        completed = [row for row in source_rows if row.get("action_completed")]
        if not completed:
            continue
        video_id = str(completed[0]["video_id"])
        units = timeline[timeline.video_id.eq(video_id)].sort_values("unit_index").reset_index(drop=True)
        refs = references[references.video_id.eq(video_id)].copy()
        video_map = mapping[mapping.video_id.eq(video_id)]
        events_by_unit = unit_event_map(video_map)
        ceiling = set(video_map.reference_event_id.astype(str))
        raw_by_unit = load_raw(video_id, units)
        scanned: list[str] = []
        fast_ever: set[str] = set()
        exact_ever: set[str] = set()
        times: list[float] = []
        recalls: list[float] = []
        first_event_time = np.nan
        prior_count = 0
        for source in completed:
            selected = str(source["selected_unit_id"])
            scanned.append(selected)
            fast_ever |= events_by_unit.get(selected, set())
            exact_current, candidate_count, mapped_candidates, redundant = exact_visible(
                video_id, scanned, raw_by_unit, refs
            )
            exact_ever |= exact_current
            if np.isnan(first_event_time) and exact_ever:
                first_event_time = float(source["cumulative_wall_clock_sec"])
            gap_units, gap_sec = max_unobserved_gap(scanned, units)
            exact_count = len(exact_ever)
            payload = {
                **source,
                "distinct_events_exposed": exact_count,
                "new_distinct_events_exposed": max(0, exact_count - prior_count),
                "exposure_recall_offset0_ceiling": exact_count / max(1, len(ceiling)),
                "exposure_recall_all_reference": exact_count / max(1, len(refs)),
                "fast_unit_map_event_count": len(fast_ever),
                "fast_vs_exact_ever_delta": len(fast_ever) - exact_count,
                "revealed_candidate_count": candidate_count,
                "mapped_candidate_count": mapped_candidates,
                "candidate_event_match_redundancy_count": redundant,
                "maximum_unobserved_gap_units": gap_units,
                "maximum_unobserved_gap_sec": gap_sec,
            }
            enriched.append(payload)
            prior_count = exact_count
            times.append(float(source["cumulative_wall_clock_sec"]))
            recalls.append(payload["exposure_recall_offset0_ceiling"])
        summaries.append(
            {
                "run_id": completed[0]["run_id"], "video_id": video_id,
                "policy_id": completed[0]["policy_id"],
                "block_id": completed[0]["block_id"],
                "completed_action_count": len(completed),
                "physical_exposure_step_auc": step_auc(times, recalls, PHYSICAL_BUDGET_SEC),
                "final_distinct_events_exposed": len(exact_ever),
                "final_exposure_recall_offset0_ceiling": len(exact_ever) / max(1, len(ceiling)),
                "time_to_first_event_physical_sec": first_event_time,
                "final_maximum_unobserved_gap_units": enriched[-1]["maximum_unobserved_gap_units"],
                "cumulative_wall_clock_sec": times[-1],
                "fast_vs_exact_ever_final_delta": len(fast_ever) - len(exact_ever),
            }
        )
    trace_frame = pd.DataFrame(enriched)
    summary_frame = pd.DataFrame(summaries)
    evidence = {
        "status": "PASS" if len(summary_frame) == 32 else "FAIL",
        "run_count": len(summary_frame),
        "trace_hashes": trace_hashes,
        "trace_hash_count": len(trace_hashes),
        "gpu_rerun_performed": False,
        "reuse_basis": "EXISTING_32_CONTROLLED_WARM_ACTION_TRACES_PLUS_FROZEN_VISIBLE_SUBSET_REPLAY",
    }
    return trace_frame, summary_frame, evidence


def synthesize(replay: pd.DataFrame, physical: pd.DataFrame, checkpoints: pd.DataFrame) -> tuple[pd.DataFrame, dict, str]:
    replay_agg = replay.groupby(["video_id", "policy_id", "method_class"], as_index=False).agg(
        exposure_grid_auc=("exposure_grid_auc", "mean"),
        exposure_grid_auc_sd=("exposure_grid_auc", "std"),
        exposure_step_auc_at_60sec=("exposure_step_auc_at_60sec", "mean"),
        exposure_step_auc_at_60sec_sd=("exposure_step_auc_at_60sec", "std"),
        recall_at_10pct=("recall_at_10pct", "mean"),
        recall_at_20pct=("recall_at_20pct", "mean"),
        recall_at_40pct=("recall_at_40pct", "mean"),
        recall_at_60pct=("recall_at_60pct", "mean"),
        time_to_first_event_estimated_sec=("time_to_first_event_estimated_sec", "mean"),
    )
    physical_agg = physical.groupby(["video_id", "policy_id"], as_index=False).agg(
        physical_exposure_step_auc=("physical_exposure_step_auc", "mean"),
        physical_exposure_step_auc_sd=("physical_exposure_step_auc", "std"),
        final_exposure_recall=("final_exposure_recall_offset0_ceiling", "mean"),
        time_to_first_event_physical_sec=("time_to_first_event_physical_sec", "mean"),
        final_maximum_unobserved_gap_units=("final_maximum_unobserved_gap_units", "mean"),
    )
    merged = replay_agg.merge(physical_agg, on=["video_id", "policy_id"], how="left")

    decisions = {"videos": {}, "scope": "TWO_VIDEO_MECHANISM_AUDIT"}
    lines = [
        "# SCAN Optimization Headroom Audit — Final Report", "",
        "## Strongest supported conclusion", "",
    ]
    conclusions = []
    for video_id in sorted(replay.video_id.unique()):
        local = replay_agg[replay_agg.video_id.eq(video_id)].set_index("policy_id")
        causal = local[local.method_class.eq("CAUSAL")]
        best_id = str(causal.exposure_grid_auc.idxmax())
        seq = float(local.loc["SEQUENTIAL", "exposure_grid_auc"])
        best = float(local.loc[best_id, "exposure_grid_auc"])
        oracle = float(local.loc["OFFLINE_EVENT_ORACLE_GREEDY", "exposure_grid_auc"])
        lg = float(local.loc["ANYTIME_LARGEST_GAP", "exposure_grid_auc"])
        uniform = float(local.loc["UNIFORM_PREFIX", "exposure_grid_auc"])
        coverage_gain = best - seq
        headroom = oracle - best
        cp = checkpoints[checkpoints.video_id.eq(video_id)]
        lg_gap = cp[cp.policy_id.eq("ANYTIME_LARGEST_GAP")].groupby("budget_fraction").maximum_unobserved_gap_units.mean()
        seq_gap = cp[cp.policy_id.eq("SEQUENTIAL")].groupby("budget_fraction").maximum_unobserved_gap_units.mean()
        h1 = bool((lg_gap[lg_gap.index < 1.0] < seq_gap[seq_gap.index < 1.0]).all())
        p_local = physical_agg[physical_agg.video_id.eq(video_id)].set_index("policy_id")
        physical_policy_ids = set(p_local.index)
        replay_60_candidates = causal[causal.index.isin(physical_policy_ids)]
        replay_60_best_id = str(replay_60_candidates.exposure_step_auc_at_60sec.idxmax())
        replay_60_seq = float(local.loc["SEQUENTIAL", "exposure_step_auc_at_60sec"])
        replay_60_best = float(local.loc[replay_60_best_id, "exposure_step_auc_at_60sec"])
        replay_60_gain = replay_60_best - replay_60_seq
        physical_best_id = str(p_local.physical_exposure_step_auc.idxmax())
        physical_seq = float(p_local.loc["SEQUENTIAL", "physical_exposure_step_auc"])
        physical_best = float(p_local.loc[physical_best_id, "physical_exposure_step_auc"])
        physical_gain = physical_best - physical_seq
        matched_physical = float(p_local.loc[replay_60_best_id, "physical_exposure_step_auc"])
        matched_physical_gain = matched_physical - physical_seq
        retention = (
            matched_physical_gain / replay_60_gain
            if replay_60_gain > 1e-12 else None
        )
        decisions["videos"][video_id] = {
            "best_simple_causal_policy": best_id,
            "sequential_replay_auc": seq,
            "best_simple_replay_auc": best,
            "coverage_gain_auc": coverage_gain,
            "offline_greedy_auc": oracle,
            "witnessed_remaining_headroom_auc": headroom,
            "largest_gap_replay_auc": lg,
            "uniform_replay_auc": uniform,
            "H1_largest_gap_reduces_max_gap_pre_full_checkpoints": h1,
            "best_replay_policy_at_matched_60sec": replay_60_best_id,
            "sequential_replay_auc_at_60sec": replay_60_seq,
            "best_replay_auc_at_60sec": replay_60_best,
            "matched_replay_gain_auc_at_60sec": replay_60_gain,
            "best_existing_physical_policy": physical_best_id,
            "sequential_physical_auc": physical_seq,
            "best_physical_auc": physical_best,
            "physical_gain_auc": physical_gain,
            "matched_policy_physical_gain_auc": matched_physical_gain,
            "matched_budget_gain_retention_fraction": retention,
            "matched_replay_physical_winner_agreement": replay_60_best_id == physical_best_id,
            "temporal_audit_gate": headroom >= 0.02,
        }
        conclusions.append(
            f"- `{video_id}`: best causal replay `{best_id}` AUC={best:.4f} "
            f"vs Sequential={seq:.4f}; offline greedy={oracle:.4f}. "
            f"At matched 60 s Replay, `{replay_60_best_id}` is best; actual "
            f"Physical winner is `{physical_best_id}` AUC={physical_best:.4f} "
            f"vs Sequential={physical_seq:.4f}."
        )
    temporal_gate = any(row["temporal_audit_gate"] for row in decisions["videos"].values())
    decisions["temporal_audit_gate_any_video"] = temporal_gate
    lines.extend(conclusions)
    lines.extend([
        "", "These are controlled two-video mechanism results relative to a frozen pseudo-reference, not cross-video generalization claims.",
        "", "## Interpretation", "",
        "- A positive simple-coverage gain is direct evidence that time allocation is optimizable without changing SCAN fidelity.",
        "- A positive offline-greedy gap is an achievable hidden-information witness of remaining scheduling headroom; it is not a proven optimality gap.",
        "- Replay gain that disappears physically identifies path/seek batching—not a more elaborate event score—as the next bottleneck.",
        "- Temporal refinement is tested only when the frozen headroom gate passes; guarded marginal scheduling remains gated on simple refinement.",
        "", "## Frozen status", "", "```text",
        "PUBLIC_UNTRUSTED_POLICY_BENCHMARK = BLOCKED",
        "TRUSTED_FROZEN_POLICY_EXPERIMENT = ALLOWED",
        f"TEMPORAL_CORRELATION_AUDIT_GATE = {'PASS' if temporal_gate else 'STOP'}",
        "PUBLIC_BENCHMARK_CLAIM = DEFERRED", "```", "",
    ])
    return merged, decisions, "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    code_audit = static_policy_audit()
    if code_audit["status"] != "PASS":
        raise RuntimeError(f"trusted policy audit failed: {code_audit}")
    atomic_json(OUT / "trusted_policy_code_audit.json", code_audit)

    order, checkpoints, replay = replay_audit()
    atomic_csv(OUT / "replay_action_orders.csv", order)
    atomic_csv(OUT / "replay_budget_checkpoints.csv", checkpoints)
    atomic_csv(OUT / "replay_run_summary.csv", replay)

    physical_trace, physical_summary, physical_evidence = physical_audit()
    if physical_evidence["status"] != "PASS":
        raise RuntimeError("physical trace set is incomplete")
    atomic_csv(OUT / "physical_exposure_trace.csv", physical_trace)
    atomic_csv(OUT / "physical_run_summary.csv", physical_summary)
    atomic_json(OUT / "physical_evidence_manifest.json", physical_evidence)

    comparison, decisions, report = synthesize(replay, physical_summary, checkpoints)
    atomic_csv(OUT / "replay_physical_comparison.csv", comparison)
    atomic_json(OUT / "headroom_decision.json", decisions)
    atomic_text(OUT / "FINAL_SCAN_HEADROOM_REPORT.md", report)
    print(json.dumps({
        "status": "PASS", "replay_runs": len(replay),
        "physical_runs": len(physical_summary), "decision": decisions,
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
