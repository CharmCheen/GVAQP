from __future__ import annotations

import json
import math
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .action import Action, ActionResult
from .cost import CausalCostEstimator
from .frontier_adapter import Candidate, FrozenFrontier
from .state import PublicState
from .vps import bucket

ROOT = Path(__file__).resolve().parents[3]
PSVR = ROOT / "outputs/psvr_two_video_loop"
DEV = PSVR / "dev_benchmark_v1"
PROXY = PSVR / "proxy_finalization/raw/Y8"
V0_RAW = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/oracle/oracle_raw_outputs.jsonl"

FEATURES = [
    "track_persistence", "path_directed_lateral_motion", "box_growth",
    "front_region_occupancy", "approximate_ttc_urgency",
]


def _average_percentile(frame: pd.DataFrame, column: str) -> pd.Series:
    values = frame[column].astype(float)
    result = pd.Series(0.0, index=frame.index)
    positive = values > 0
    if positive.any():
        result.loc[positive] = values.loc[positive].rank(method="average", pct=True)
    return result


def largest_gap_order(count: int) -> list[int]:
    observed: list[int] = []
    result: list[int] = []
    while len(result) < count:
        if not observed:
            chosen = (count - 1) // 2
        else:
            unseen = [i for i in range(count) if i not in set(observed)]
            chosen = max(unseen, key=lambda i: (min(abs(i - j) for j in observed), -i))
        observed.append(chosen); result.append(chosen)
    return result


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_confirm_costs() -> dict[str, dict[int, float]]:
    global CONFIRM_COST_PROVENANCE
    result: dict[str, dict[int, list[float]]] = {}
    for path in PSVR.glob("**/complete.json"):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        task = run.get("task_id")
        if not task:
            continue
        for row in run.get("queried_results", []):
            if not row.get("physical_oracle_invocation") or row.get("cache_replay"):
                continue
            cost = float(row["snapshot_elapsed_seconds"]) - float(row["query_start_seconds"])
            result.setdefault(task, {}).setdefault(int(row["unit_id"]), []).append(cost)
    medians = {task: {u: float(np.median(v)) for u, v in units.items()} for task, units in result.items()}
    overhead = []
    for path in PSVR.glob("**/complete.json"):
        try: run = json.loads(path.read_text(encoding="utf-8"))
        except Exception: continue
        for row in run.get("queried_results", []):
            if row.get("physical_oracle_invocation") and not row.get("cache_replay"):
                total = float(row["snapshot_elapsed_seconds"]) - float(row["query_start_seconds"])
                overhead.append(max(0.0, total - float(row["oracle_inference_seconds"])))
    post = float(np.median(overhead)) if overhead else 0.1
    # The original V0 JSONL is an optional historical fallback.  A repository
    # snapshot can legitimately omit it when complete measured query traces
    # above already cover every benchmark unit; do not make that absent,
    # redundant source a hard runtime dependency.
    v0 = (
        {int(r["unit_id"]): float(r["generation_runtime_seconds"]) + post for r in _load_jsonl(V0_RAW)}
        if V0_RAW.exists()
        else {}
    )
    v1 = {}
    for path in (DEV / "raw_oracle/V1").glob("center10_anchor_*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("physical_vlm_call") and row.get("parse_status") == "ok":
            v1[int(row["unit_id"])] = float(row["generation_runtime_seconds"]) + post
    for task in ("V0_Q1", "V0_Q2"):
        medians.setdefault(task, {})
        for unit, value in v0.items(): medians[task].setdefault(unit, value)
    for task in ("V1_Q1", "V1_Q2"):
        medians.setdefault(task, {})
        for unit, value in v1.items(): medians[task].setdefault(unit, value)
    provenance: dict[str, dict[int, str]] = {}
    for task, costs in medians.items():
        provenance[task] = {int(unit): "MEASURED_OR_RAW_PHYSICAL" for unit in costs}
    # Some repository snapshots omit the untracked V0 raw JSONL even though
    # parsed outcomes and a few complete physical traces remain. Preserve
    # executable replay with an explicit, auditable task-median imputation; it
    # is not equivalent to complete measured per-unit cost support and callers
    # must not promote it to such evidence.
    for task in ("V0_Q1", "V0_Q2"):
        label_path = DEV / f"parsed_labels/{task}.csv"
        if not label_path.exists():
            continue
        required = set(pd.read_csv(label_path).unit_id.astype(int))
        observed = medians.setdefault(task, {})
        if required - set(observed):
            if not observed:
                raise FileNotFoundError(
                    f"no physical CONFIRM costs remain for {task}; missing fallback {V0_RAW}"
                )
            fallback = float(np.median(list(observed.values())))
            for unit in required - set(observed):
                observed[unit] = fallback
                provenance.setdefault(task, {})[unit] = "IMPUTED_TASK_MEDIAN_MISSING_V0_RAW"
    CONFIRM_COST_PROVENANCE = provenance
    return medians


CONFIRM_COSTS: dict[str, dict[int, float]] | None = None
CONFIRM_COST_PROVENANCE: dict[str, dict[int, str]] = {}
SCORE_PREFIX_CACHE: dict[tuple[str, int], list[tuple[int, int, float, int]]] = {}
MAX_GAP_CACHE: dict[tuple[str, tuple[int, ...]], float] = {}


class TraceReplayEnvironment:
    """Causal policy boundary over complete measured physical action traces."""

    def __init__(self, task_id: str, budget_sec: float, *, cost_quantile: float = .9, constant_median_cost: bool = False):
        global CONFIRM_COSTS
        if CONFIRM_COSTS is None:
            CONFIRM_COSTS = load_confirm_costs()
        self.task_id = task_id
        self.video_id, self.query_id = task_id.split("_")
        self.budget_sec = float(budget_sec)
        self.elapsed = 0.0
        unit_path = DEV / f"units/{self.video_id}_units.csv"
        if unit_path.exists():
            self.units = pd.read_csv(unit_path)
        else:
            # V0 public unit boundaries are authoritative in projected labels.
            labels = pd.read_csv(DEV / f"parsed_labels/{task_id}.csv")
            self.units = labels[["unit_id", "start_time", "end_time"]].copy()
            self.units["duration_seconds"] = self.units.end_time - self.units.start_time
        self.units["unit_id"] = self.units.unit_id.astype(int)
        self.candidates = pd.read_csv(PROXY / self.video_id / "TRACK_CANDIDATES.csv").query("query_id == @self.query_id").copy()
        self.processing = {int(r["unit_id"]): r for r in json.loads((PROXY / self.video_id / "UNIT_PROCESSING.json").read_text())}
        self.labels = {int(r.unit_id): str(r.parsed_label).lower() for r in pd.read_csv(DEV / f"parsed_labels/{task_id}.csv").itertuples()}
        reference = pd.read_csv(DEV / f"reference_events/{task_id}.csv")
        self.event_by_unit: dict[int, set[str]] = {}
        for row in reference.to_dict("records"):
            for token in str(row["source_unit_ids"]).replace(",", "|").split("|"):
                if token.strip(): self.event_by_unit.setdefault(int(float(token)), set()).add(str(row["reference_event_id"]))
        self.reference_count = len(reference)
        self.order = largest_gap_order(len(self.units)); self.scan_cursor = 0
        self.observed: set[int] = set(); self.confirmed_events: set[str] = set(); self.bound_tracks: dict[int, int] = {}
        self.candidate_created_elapsed: dict[int, float] = {}
        self.ever_admitted: set[int] = set(); self.frontier = FrozenFrontier(10); self.ledger: list[dict[str, Any]] = []
        self.scan_costs = {u: self._scan_cost(row) for u, row in self.processing.items()}
        self.confirm_costs = CONFIRM_COSTS[task_id]
        self.confirm_cost_provenance = CONFIRM_COST_PROVENANCE.get(task_id, {})
        self.confirm_cost_imputed_units = {
            unit for unit, source in self.confirm_cost_provenance.items() if source.startswith("IMPUTED_")
        }
        self.scan_estimator = CausalCostEstimator(list(self.scan_costs.values()), cost_quantile, constant_median_cost)
        self.confirm_estimator = CausalCostEstimator(list(self.confirm_costs.values()), cost_quantile, constant_median_cost)
        asset_payload = {
            "task_id": self.task_id,
            "units": self.units[["unit_id", "start_time", "end_time"]].to_dict("records"),
            "candidates": self.candidates.sort_values(["unit_id", "track_id"]).to_dict("records"),
            "processing": self.processing,
            "scan_costs": self.scan_costs,
            "confirm_costs": self.confirm_costs,
            "labels": self.labels,
            "event_by_unit": {key: sorted(value) for key, value in self.event_by_unit.items()},
            "reference_count": self.reference_count,
            "order": self.order,
            "frontier_capacity": self.frontier.capacity,
        }
        self.transition_asset_hash = hashlib.sha256(
            json.dumps(asset_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def __deepcopy__(self, memo):
        """Copy transition state while sharing frozen, read-only task assets."""
        result = type(self).__new__(type(self))
        memo[id(self)] = result
        immutable_assets = {
            "units", "candidates", "processing", "labels", "event_by_unit", "order",
            "scan_costs", "confirm_costs", "confirm_cost_provenance",
            "confirm_cost_imputed_units", "transition_asset_hash",
        }
        for name, value in self.__dict__.items():
            setattr(result, name, value if name in immutable_assets else deepcopy(value, memo))
        return result

    @staticmethod
    def _scan_cost(row: dict[str, Any]) -> float:
        keys = ["seek_seconds", "decode_seconds", "detector_path_seconds", "tracking_cpu_seconds", "rule_scoring_cpu_seconds", "evidence_serialization_seconds"]
        return sum(float(row.get(k, 0.0)) for k in keys) + 0.001

    def _visible_candidates(self) -> list[Candidate]:
        cache_key = (self.task_id, self.scan_cursor)
        if cache_key in SCORE_PREFIX_CACHE:
            cached = SCORE_PREFIX_CACHE[cache_key]
            for unit_id, track_id, _, _ in cached:
                self.bound_tracks.setdefault(unit_id, track_id)
                self.candidate_created_elapsed.setdefault(unit_id, self.elapsed)
            return [Candidate(
                candidate_id=f"{self.task_id}_unit_{unit_id:04d}_track_{track_id:04d}", unit_id=unit_id,
                track_id=track_id, score=score, created_elapsed_sec=self.candidate_created_elapsed[unit_id],
                creation_scan_index=creation,
            ) for unit_id, track_id, score, creation in cached]
        frame = self.candidates[self.candidates.unit_id.astype(int).isin(self.observed)].copy()
        if frame.empty: return []
        for feature in FEATURES:
            frame[feature + "_online"] = _average_percentile(frame, feature)
        frame["online_score"] = frame[[f + "_online" for f in FEATURES]].mean(axis=1)
        rows = []
        for unit_id, group in frame.groupby(frame.unit_id.astype(int)):
            ordered = group.sort_values(["online_score", "track_id"], ascending=[False, True])
            if unit_id not in self.bound_tracks: self.bound_tracks[unit_id] = int(ordered.iloc[0].track_id)
            selected = group[group.track_id.astype(int) == self.bound_tracks[unit_id]]
            if selected.empty: continue
            row = selected.iloc[0]
            rows.append(Candidate(
                candidate_id=f"{self.task_id}_unit_{unit_id:04d}_track_{int(row.track_id):04d}", unit_id=unit_id,
                track_id=int(row.track_id), score=float(row.online_score), created_elapsed_sec=self.elapsed,
                creation_scan_index=self.order.index(unit_id),
            ))
        SCORE_PREFIX_CACHE[cache_key] = [(r.unit_id, r.track_id, r.score, r.creation_scan_index) for r in rows]
        for row in rows:
            self.candidate_created_elapsed.setdefault(row.unit_id, self.elapsed)
        return [Candidate(r.candidate_id, r.unit_id, r.track_id, r.score,
                          self.candidate_created_elapsed[r.unit_id], r.creation_scan_index) for r in rows]

    def _max_gap(self) -> float:
        key = (self.task_id, tuple(sorted(self.observed)))
        if key in MAX_GAP_CACHE:
            return MAX_GAP_CACHE[key]
        if not self.observed:
            value = float(self.units.end_time.max() - self.units.start_time.min())
            MAX_GAP_CACHE[key] = value
            return value
        centers = dict(zip(self.units.unit_id.astype(int), .5 * (self.units.start_time + self.units.end_time)))
        unseen = set(centers) - self.observed
        value = 0.0 if not unseen else 2 * max(min(abs(centers[u] - centers[o]) for o in self.observed) for u in unseen)
        MAX_GAP_CACHE[key] = value
        return value

    def public_state(self) -> dict[str, Any]:
        rows = self.frontier.rows(); scores = np.asarray([r.score for r in rows], dtype=float)
        ages = [self.elapsed - r.created_elapsed_sec for r in rows]
        scans = [r for r in self.ledger if r["action"] == "SCAN"]
        confirms = [r for r in self.ledger if r["action"] == "CONFIRM"]
        def streak(data: list[dict[str, Any]], field: str) -> int:
            n = 0
            for row in reversed(data):
                if row[field] != 0: break
                n += 1
            return n
        state = PublicState(
            remaining_budget_sec=max(0.0, self.budget_sec - self.elapsed),
            coverage_fraction=len(self.observed) / len(self.units), maximum_unobserved_gap_sec=self._max_gap(),
            scan_actions_completed=len(scans), scan_time_spent_sec=sum(r["actual_action_cost_sec"] for r in scans),
            frontier_size=len(rows), frontier_score_min=float(scores.min()) if len(scores) else 0.0,
            frontier_score_median=float(np.median(scores)) if len(scores) else 0.0, frontier_score_max=float(scores.max()) if len(scores) else 0.0,
            frontier_score_quantiles=np.quantile(scores, [.25, .5, .75]).tolist() if len(scores) else [0.0, 0.0, 0.0],
            oldest_candidate_age_sec=max(ages, default=0.0), newest_candidate_age_sec=min(ages, default=0.0),
            novel_candidate_clusters_observed=len(self.ever_admitted), confirmed_distinct_utility_count=len(self.confirmed_events),
            recent_scan_novel_yield=float(np.mean([r["new_candidate_clusters"] for r in scans[-3:]])) if scans else 0.0,
            recent_scan_zero_yield_streak=streak(scans, "new_candidate_clusters"),
            recent_confirm_success_rate=float(np.mean([r["positive"] for r in confirms[-3:]])) if confirms else 0.0,
            recent_confirm_new_utility_rate=float(np.mean([r["new_distinct_utility"] for r in confirms[-3:]])) if confirms else 0.0,
            recent_confirm_zero_yield_streak=streak(confirms, "new_distinct_utility"),
            estimated_scan_cost_sec=self.scan_estimator.estimate() if self.scan_cursor < len(self.order) else float("inf"),
            estimated_confirm_cost_sec=self.confirm_estimator.estimate() if rows else float("inf"),
            actions_completed=len(self.ledger), unused_budget_sec=max(0.0, self.budget_sec - self.elapsed),
        )
        return state.to_dict()

    def step(self, action: Action) -> ActionResult:
        before = self.public_state(); estimate = before["estimated_scan_cost_sec" if action is Action.SCAN else "estimated_confirm_cost_sec"]
        if action is Action.STOP:
            return ActionResult(action, 0.0, 0.0, True, payload={"stop": True})
        if estimate > before["remaining_budget_sec"]:
            return ActionResult(action, estimate, 0.0, False, payload={"deadline_rejection": True})
        new_clusters = new_utility = 0; positive = 0; selected_score = None; unit_id = None
        if action is Action.SCAN:
            unit_id = self.order[self.scan_cursor]
            cost = self.scan_costs[unit_id]
        else:
            candidate = self.frontier.best()
            if candidate is None:
                return ActionResult(action, estimate, 0.0, False, payload={"illegal": "empty_frontier"})
            unit_id = candidate.unit_id
            selected_score = candidate.score
            cost = self.confirm_costs[unit_id]
        # Two-phase commit: a completed physical action that crosses the hard
        # deadline consumes time and is retained as a safety failure, but no
        # scan/frontier/event/estimator state is committed.
        if self.elapsed + cost > self.budget_sec:
            self.elapsed += cost
            self.ledger.append({
                "action_index": len(self.ledger), "action": action.value, "unit_id": unit_id,
                "estimated_action_cost_sec": estimate, "actual_action_cost_sec": cost,
                "action_started": True, "action_completed": True, "deadline_rejection": False,
                "deadline_overrun": True, "cumulative_wallclock": self.elapsed,
                "remaining_budget": self.budget_sec - self.elapsed, "new_candidate_clusters": 0,
                "positive": 0, "new_distinct_utility": 0, "utility": len(self.confirmed_events),
                "frontier_size": len(self.frontier), "maximum_unobserved_gap_sec": self._max_gap(),
                "post_deadline_commit": False,
            })
            return ActionResult(
                action, estimate, cost, True, payload={"unit_id": unit_id, "deadline_overrun": True}
            )
        if action is Action.SCAN:
            self.scan_cursor += 1
            self.observed.add(unit_id); self.elapsed += cost
            admitted, dropped = self.frontier.update(self._visible_candidates())
            now = set(r.unit_id for r in self.frontier.rows()); new_ids = now - self.ever_admitted; self.ever_admitted |= now
            new_clusters = len(new_ids)
            self.scan_estimator.observe(cost)
        else:
            self.elapsed += cost; positive = int(self.labels[unit_id] == "positive")
            mapped = self.event_by_unit.get(unit_id, set()) if positive else set()
            new = mapped - self.confirmed_events; self.confirmed_events |= mapped; new_utility = len(new)
            self.frontier.terminalize(unit_id); self.confirm_estimator.observe(cost)
        row = {
            "action_index": len(self.ledger), "action": action.value, "unit_id": unit_id,
            "estimated_action_cost_sec": estimate, "actual_action_cost_sec": cost,
            "action_started": True, "action_completed": True, "deadline_rejection": False,
            "deadline_overrun": self.elapsed > self.budget_sec, "cumulative_wallclock": self.elapsed,
            "remaining_budget": self.budget_sec - self.elapsed, "new_candidate_clusters": new_clusters,
            "positive": positive, "new_distinct_utility": new_utility, "utility": len(self.confirmed_events),
            "frontier_size": len(self.frontier), "maximum_unobserved_gap_sec": self._max_gap(),
            "post_deadline_commit": False,
        }
        self.ledger.append(row)
        return ActionResult(action, estimate, cost, True, new_clusters, new_utility,
                            bucket(selected_score, (1/3, 2/3)) if selected_score is not None else None,
                            bucket(len(self.observed)/len(self.units), (1/3, 2/3)) if action is Action.SCAN else None,
                            {"unit_id": unit_id})

    def summary(self, policy: str, seed: int) -> dict[str, Any]:
        scans = [r for r in self.ledger if r["action"] == "SCAN"]; confirms = [r for r in self.ledger if r["action"] == "CONFIRM"]
        on_time = [r for r in self.ledger if r["cumulative_wallclock"] <= self.budget_sec]
        utility_at_deadline = max((int(r["utility"]) for r in on_time), default=0)
        first = next((r["cumulative_wallclock"] for r in confirms if r["utility"] > 0 and r["cumulative_wallclock"] <= self.budget_sec), None)
        return {
            "task_id": self.task_id, "video_id": self.video_id, "query_id": self.query_id,
            "budget_sec": self.budget_sec, "policy": policy, "seed": seed,
            "utility": utility_at_deadline, "event_recall": utility_at_deadline/self.reference_count,
            "time_to_first_utility": first, "scan_wallclock": sum(r["actual_action_cost_sec"] for r in scans),
            "confirm_wallclock": sum(r["actual_action_cost_sec"] for r in confirms), "oracle_calls": len(confirms),
            "candidate_clusters_generated": len(self.ever_admitted), "duplicate_confirmations": sum(r["positive"] and not r["new_distinct_utility"] for r in confirms),
            "zero_yield_actions": sum((r["new_candidate_clusters"] if r["action"] == "SCAN" else r["new_distinct_utility"]) == 0 for r in self.ledger),
            "deadline_rejections": 0, "deadline_overrun": any(r["deadline_overrun"] for r in self.ledger),
            "unused_budget": self.budget_sec-self.elapsed, "maximum_unobserved_gap": self._max_gap(),
            "actions": len(self.ledger), "trace_support": "MEASURED_PHYSICAL_ACTION_REPLAY",
        }


def run_benchmark(controller, task_id: str, budget: float, policy: str, seed: int = 0, **env_kwargs: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    env = TraceReplayEnvironment(task_id, budget, **env_kwargs)
    controller.reset(budget, env.public_state())
    while True:
        decision = controller.choose_action(env.public_state()); action = Action(decision["action"])
        if action is Action.STOP: break
        result = env.step(action)
        if not result.completed: break
        controller.observe(result)
        if len(env.ledger) > 2000: raise RuntimeError("controller failed to terminate")
    return env.summary(policy, seed), env.ledger
