from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .action import Action, ActionResult
from .fixed_ratio import FixedPolicyController
from .runner import DEV, PROXY, TraceReplayEnvironment
from .vps import bucket

SCORE_BUCKETS = ("LOW", "MEDIUM", "HIGH")


def score_bucket(score: float) -> str:
    return bucket(float(score), (1 / 3, 2 / 3))


def coverage_bucket(value: float) -> str:
    return bucket(float(value), (1 / 3, 2 / 3))


def congestion_bucket(size: int) -> str:
    return "LOW" if int(size) <= 4 else "HIGH"


class FixedUpperCostEstimator:
    def __init__(self, samples: list[float]):
        values = np.asarray(samples, dtype=float)
        self.mean = float(values.mean())
        q99 = float(np.quantile(values, 0.99))
        self.delta = max(0.25, float(values.max()) - q99 + 0.25)
        self.bound = q99 + self.delta
        self.q99 = q99
        self.observed_max = float(values.max())

    def estimate(self) -> float:
        return self.bound

    def observe(self, value: float) -> None:
        return None


class SafeTraceReplayEnvironment(TraceReplayEnvironment):
    def __init__(self, task_id: str, budget_sec: float):
        super().__init__(task_id, budget_sec, cost_quantile=0.99)
        self.scan_estimator = FixedUpperCostEstimator(list(self.scan_costs.values()))
        self.confirm_estimator = FixedUpperCostEstimator(list(self.confirm_costs.values()))


@dataclass
class AlignmentObservations:
    task_id: str
    arrivals: list[dict[str, Any]]
    conversions: list[dict[str, Any]]


def candidate_is_useful(env: TraceReplayEnvironment, unit_id: int, confirmed: set[str] | None = None) -> int:
    confirmed = env.confirmed_events if confirmed is None else confirmed
    return int(env.labels[int(unit_id)] == "positive" and bool(env.event_by_unit.get(int(unit_id), set()) - confirmed))


def collect_alignment_observations(task_id: str) -> AlignmentObservations:
    """One nonduplicated 240-second R4 path plus exhaustive external conversion support."""
    env = SafeTraceReplayEnvironment(task_id, 240.0)
    controller = FixedPolicyController("R4_RATIO_25_75", 0)
    controller.reset(240.0, env.public_state())
    arrivals: list[dict[str, Any]] = []
    while True:
        before = env.public_state(); decision = controller.choose_action(before); action = Action(decision["action"])
        if action is Action.STOP:
            break
        prior = set(r.unit_id for r in env.frontier.rows())
        result = env.step(action)
        if not result.completed:
            break
        if action is Action.SCAN:
            now = {r.unit_id: r for r in env.frontier.rows()}
            counts = {name: 0 for name in SCORE_BUCKETS}
            for unit_id in set(now) - prior:
                counts[score_bucket(now[unit_id].score)] += 1
            arrivals.append({
                "task_id": task_id,
                "coverage_bucket": coverage_bucket(before["coverage_fraction"]),
                "congestion_bucket": congestion_bucket(before["frontier_size"]),
                **{f"arrivals_{name}": counts[name] for name in SCORE_BUCKETS},
            })
        controller.observe(result)
    # Complete physical outcomes are external development support, never held-group input.
    units = pd.read_csv(PROXY / env.video_id / "UNIT_SCORES.csv").query("query_id == @env.query_id")
    conversions = []
    for row in units.to_dict("records"):
        if pd.isna(row.get("top_track_id")):
            continue
        unit_id = int(row["unit_id"])
        conversions.append({
            "task_id": task_id,
            "score_bucket": score_bucket(float(row["unit_score"])),
            "congestion_bucket": "GLOBAL",
            "useful": candidate_is_useful(env, unit_id, set()),
            "unit_score": float(row["unit_score"]),
        })
    return AlignmentObservations(task_id, arrivals, conversions)


class CommonUtilityModel:
    def __init__(self, observations: list[AlignmentObservations], strength: float = 2.0):
        self.minimum_support = 5
        self.arrival_rows = [row for obs in observations for row in obs.arrivals]
        self.conversion_rows = [row for obs in observations for row in obs.conversions]
        global_rate = float(np.mean([r["useful"] for r in self.conversion_rows])) if self.conversion_rows else 0.5
        self.global_alpha = max(1e-6, strength * global_rate)
        self.global_beta = max(1e-6, strength * (1 - global_rate))
        self.online_arrivals: list[dict[str, Any]] = []
        self.online_conversions: list[dict[str, Any]] = []

    def conversion_probability(self, score_name: str, congestion_name: str) -> float:
        rows = self.conversion_rows + self.online_conversions
        primary = [r for r in rows if r["score_bucket"] == score_name and r.get("congestion_bucket") == congestion_name]
        score_only = [r for r in rows if r["score_bucket"] == score_name]
        selected = primary if len(primary) >= self.minimum_support else score_only if len(score_only) >= self.minimum_support else rows
        successes = sum(int(r["useful"]) for r in selected)
        return (self.global_alpha + successes) / (self.global_alpha + self.global_beta + len(selected))

    def arrival_rate(self, coverage_name: str, congestion_name: str, score_name: str) -> float:
        rows = self.arrival_rows + self.online_arrivals
        primary = [r for r in rows if r["coverage_bucket"] == coverage_name and r["congestion_bucket"] == congestion_name]
        coverage_only = [r for r in rows if r["coverage_bucket"] == coverage_name]
        selected = primary if len(primary) >= self.minimum_support else coverage_only if len(coverage_only) >= self.minimum_support else rows
        total = sum(int(r[f"arrivals_{score_name}"]) for r in selected)
        global_mean = sum(int(r[f"arrivals_{score_name}"]) for r in rows) / max(len(rows), 1)
        alpha = max(1e-6, 2 * global_mean); beta = 2.0
        return (alpha + total) / (beta + len(selected))

    def observe_scan(self, row: dict[str, Any]) -> None:
        self.online_arrivals.append(dict(row))

    def observe_confirm(self, score_name: str, congestion_name: str, useful: int) -> None:
        self.online_conversions.append({"score_bucket": score_name, "congestion_bucket": congestion_name, "useful": int(useful)})

    def constant_conversion_rate(self) -> float:
        rows = self.conversion_rows
        return float(np.mean([r["useful"] for r in rows])) if rows else 0.5


def bucket_counts(env: TraceReplayEnvironment) -> dict[str, int]:
    counts = {name: 0 for name in SCORE_BUCKETS}
    for row in env.frontier.rows():
        counts[score_bucket(row.score)] += 1
    return counts


def _value_from_counts(counts: dict[str, float], slots: int, model: CommonUtilityModel, congestion_name: str) -> float:
    remaining = max(0.0, float(slots)); value = 0.0
    for name in reversed(SCORE_BUCKETS):
        take = min(float(counts.get(name, 0.0)), remaining)
        value += take * model.conversion_probability(name, congestion_name)
        remaining -= take
        if remaining <= 0:
            break
    return value


def predicted_common_values(env: TraceReplayEnvironment, model: CommonUtilityModel) -> dict[str, float]:
    state = env.public_state(); remaining = state["remaining_budget_sec"]
    scan_cost = state["estimated_scan_cost_sec"]; confirm_cost = state["estimated_confirm_cost_sec"]
    counts = {k: float(v) for k, v in bucket_counts(env).items()}
    congestion = congestion_bucket(state["frontier_size"])
    slots_before = int(remaining // confirm_cost) if np.isfinite(confirm_cost) and confirm_cost > 0 else 0
    before = _value_from_counts(counts, slots_before, model, congestion)
    after_counts = dict(counts)
    for name in SCORE_BUCKETS:
        after_counts[name] += model.arrival_rate(coverage_bucket(state["coverage_fraction"]), congestion, name)
    # Frozen score retention: trim low-value buckets first to capacity 10.
    overflow = max(0.0, sum(after_counts.values()) - 10.0)
    for name in SCORE_BUCKETS:
        removed = min(after_counts[name], overflow); after_counts[name] -= removed; overflow -= removed
    slots_after = int(max(0.0, remaining - scan_cost) // confirm_cost) if np.isfinite(confirm_cost) and confirm_cost > 0 else 0
    after = _value_from_counts(after_counts, slots_after, model, congestion_bucket(min(10, int(np.ceil(sum(after_counts.values()))))))
    scan_value = max(0.0, after - before)
    best = env.frontier.best()
    confirm_value = 0.0 if best is None else model.conversion_probability(score_bucket(best.score), congestion)
    return {
        "predicted_scan_value": scan_value,
        "predicted_confirm_value": confirm_value,
        "uvps_scan": scan_value / max(scan_cost, 1e-12),
        "uvps_confirm": confirm_value / max(confirm_cost, 1e-12),
        "service_slots_before": slots_before,
        "service_slots_after_scan": slots_after,
        "frontier_value_before": before,
        "frontier_value_after_scan": after,
    }


def true_frontier_value(env: TraceReplayEnvironment) -> int:
    state = env.public_state(); cost = state["estimated_confirm_cost_sec"]
    slots = int(state["remaining_budget_sec"] // cost) if np.isfinite(cost) and cost > 0 else 0
    seen = set(env.confirmed_events); gain = 0
    rows = sorted(env.frontier.rows(), key=lambda r: (-r.score, r.unit_id, r.track_id, r.candidate_id))[:slots]
    for row in rows:
        if env.labels[row.unit_id] != "positive":
            continue
        new = env.event_by_unit.get(row.unit_id, set()) - seen
        if new:
            gain += len(new); seen |= new
    return gain


def actual_common_values(env: TraceReplayEnvironment) -> dict[str, float]:
    before = true_frontier_value(env)
    confirm_gain = 0
    if env.frontier.best() is not None:
        trial = deepcopy(env); result = trial.step(Action.CONFIRM)
        confirm_gain = result.new_distinct_utility if result.completed else 0
    scan_gain = 0
    if env.scan_cursor < len(env.order):
        trial = deepcopy(env); result = trial.step(Action.SCAN)
        if result.completed:
            scan_gain = max(0, true_frontier_value(trial) - before)
    return {"actual_scan_value": float(scan_gain), "actual_confirm_value": float(confirm_gain)}
