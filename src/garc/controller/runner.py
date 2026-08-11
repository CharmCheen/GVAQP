from __future__ import annotations

import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from garc.confirm import (
    ConfirmActionError, ConfirmAdapter, DurableCommitLog, MaterializationError,
)
from garc.scan import CoverageState, PublicUnit, SafeCoveragePolicy

from .candidate import CandidateGenerationError, FrozenCandidateGenerator
from .deadline import CausalCostEstimator
from .fixed_ratio import FixedRatioController
from .frontier import FrozenFrontier
from .state import Action, ActionResult, PublicState


class ReplayControllerRunner:
    """Dependency-free replay/dry-run integration of SCAN, Frontier and CONFIRM."""

    def __init__(
        self,
        units: list[dict[str, Any]],
        budget_sec: float,
        confirm_backend,
        *,
        commit_path: Path,
        frontier_capacity: int = 10,
        scan_policy: SafeCoveragePolicy | None = None,
        candidate_generator: FrozenCandidateGenerator | None = None,
        confirm_adapter: ConfirmAdapter | None = None,
    ):
        self.unit_rows = {int(row["unit_id"]): dict(row) for row in units}
        self.units = tuple(PublicUnit(str(row["unit_id"]), float(row["start_sec"]), float(row["end_sec"])) for row in units)
        self.budget_sec = float(budget_sec)
        self.elapsed = 0.0
        self.scan_policy = scan_policy or SafeCoveragePolicy()
        self.scanned: list[str] = []
        scan_fallback = [float(row["scan_cost_sec"]) for row in units if float(row.get("scan_cost_sec", 0)) > 0]
        confirm_fallback = []
        if isinstance(confirm_backend, Mapping):
            confirm_fallback = [float(row["actual_cost_sec"]) for row in confirm_backend.values()
                                if float(row.get("actual_cost_sec", 0)) > 0]
        self.scan_estimator = CausalCostEstimator(scan_fallback or [1.0])
        self.confirm_estimator = CausalCostEstimator(confirm_fallback or [1.0])
        self.frontier = FrozenFrontier(frontier_capacity)
        self.candidates = candidate_generator or FrozenCandidateGenerator()
        self.confirm = confirm_adapter or ConfirmAdapter(confirm_backend)
        self.commit = DurableCommitLog(commit_path)
        self.controller = FixedRatioController()
        self.known_utility: set[str] = set()
        self.ever_admitted: set[int] = set()

    @staticmethod
    def _streak(rows: list[dict[str, Any]], field: str) -> int:
        count = 0
        for row in reversed(rows):
            if row.get(field, 0) != 0:
                break
            count += 1
        return count

    @staticmethod
    def _quantile(values: list[float], fraction: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        position = (len(ordered) - 1) * fraction
        lower = int(position)
        upper = min(len(ordered) - 1, lower + 1)
        weight = position - lower
        return ordered[lower] * (1 - weight) + ordered[upper] * weight

    def _maximum_gap(self) -> float:
        if not self.units:
            return 0.0
        centers = {int(unit.unit_id): 0.5 * (unit.start_sec + unit.end_sec) for unit in self.units}
        observed = {int(unit_id) for unit_id in self.scanned}
        if not observed:
            return max(unit.end_sec for unit in self.units) - min(unit.start_sec for unit in self.units)
        unseen = set(centers) - observed
        return 0.0 if not unseen else 2 * max(min(abs(centers[u] - centers[o]) for o in observed) for u in unseen)

    def public_state(self) -> dict[str, Any]:
        scores = sorted(row.score for row in self.frontier.rows())
        ages = self.frontier.ages(self.elapsed)
        remaining_units = len(self.units) - len(self.scanned)
        scans = [row for row in self.commit.rows if row["action"] == Action.SCAN.value]
        confirms = [row for row in self.commit.rows if row["action"] == Action.CONFIRM.value]
        state = PublicState(
            remaining_budget_sec=max(0.0, self.budget_sec - self.elapsed),
            coverage_fraction=len(self.scanned) / len(self.units) if self.units else 1.0,
            maximum_unobserved_gap_sec=self._maximum_gap(),
            scan_actions_completed=len(self.scanned),
            scan_time_spent_sec=sum(row["actual_cost_sec"] for row in scans),
            frontier_size=len(self.frontier),
            frontier_score_min=min(scores, default=0.0),
            frontier_score_median=statistics.median(scores) if scores else 0.0,
            frontier_score_max=max(scores, default=0.0),
            frontier_score_quantiles=[self._quantile(scores, q) for q in (.25, .5, .75)] if scores else [0.0, 0.0, 0.0],
            oldest_candidate_age_sec=max(ages, default=0.0),
            newest_candidate_age_sec=min(ages, default=0.0),
            novel_candidate_clusters_observed=len(self.ever_admitted),
            confirmed_distinct_utility_count=len(self.known_utility),
            recent_scan_novel_yield=statistics.mean(row["new_candidate_clusters"] for row in scans[-3:]) if scans else 0.0,
            recent_scan_zero_yield_streak=self._streak(scans, "new_candidate_clusters"),
            recent_confirm_success_rate=statistics.mean(row["positive"] for row in confirms[-3:]) if confirms else 0.0,
            recent_confirm_new_utility_rate=statistics.mean(row["new_distinct_utility"] for row in confirms[-3:]) if confirms else 0.0,
            recent_confirm_zero_yield_streak=self._streak(confirms, "new_distinct_utility"),
            estimated_scan_cost_sec=self.scan_estimator.estimate() if remaining_units else float("inf"),
            estimated_confirm_cost_sec=self.confirm_estimator.estimate() if len(self.frontier) else float("inf"),
            actions_completed=len(self.commit.rows),
            unused_budget_sec=max(0.0, self.budget_sec - self.elapsed),
        )
        return state.to_dict()

    def _scan(self, estimate: float) -> ActionResult:
        scan_state = CoverageState(self.units, tuple(self.scanned), self.scanned[-1] if self.scanned else None,
                                   self.budget_sec - self.elapsed, tuple(self.scan_estimator.observed))
        selected = self.scan_policy.choose_next_unit(scan_state)
        raw = self.unit_rows[int(selected)]
        cost = float(raw.get("scan_cost_sec", estimate))
        if cost < 0:
            raise ValueError("SCAN cost cannot be negative")
        self.scanned.append(selected)
        self.elapsed += cost
        visible = self.candidates.observe_scan(int(selected), raw.get("candidates", []),
                                               elapsed_sec=self.elapsed, scan_index=len(self.scanned) - 1)
        self.frontier.update(visible)
        retained = {row.unit_id for row in self.frontier.rows()}
        new_ids = retained - self.ever_admitted
        self.ever_admitted |= retained
        self.scan_estimator.observe(cost)
        return ActionResult(Action.SCAN, estimate, cost, True, len(new_ids), 0,
                            {"unit_id": int(selected), "candidate_ids": sorted(row.candidate_id for row in visible)})

    def _confirm(self, estimate: float) -> ActionResult:
        candidate = self.frontier.best()
        if candidate is None:
            return ActionResult(Action.CONFIRM, estimate, 0.0, False, payload={"illegal": "empty_frontier"})
        try:
            outcome = self.confirm.confirm(candidate)
        except (ConfirmActionError, MaterializationError) as error:
            actual_cost = float(getattr(error, "actual_cost_sec", 0.0))
            self.elapsed += actual_cost
            return ActionResult(Action.CONFIRM, estimate, actual_cost, False, payload={
                "unit_id": candidate.unit_id,
                "error_type": type(error).__name__,
                "error": str(error),
            })
        self.elapsed += outcome.actual_cost_sec
        new = set(outcome.distinct_utility_ids) - self.known_utility
        return ActionResult(Action.CONFIRM, estimate, outcome.actual_cost_sec, True, 0, len(new),
                            {"unit_id": candidate.unit_id, "candidate_id": candidate.candidate_id,
                             "positive": outcome.positive, "new_utility_ids": sorted(new),
                             "distinct_utility_ids": list(outcome.distinct_utility_ids),
                             "materialized": outcome.materialized})

    def _summary(self) -> dict[str, Any]:
        on_time = [row for row in self.commit.rows if row["elapsed_sec"] <= self.budget_sec]
        on_time_utility = max((int(row["cumulative_utility"]) for row in on_time), default=0)
        return {
            "policy": self.controller.policy_id,
            "actions_completed": len(self.commit.rows),
            "actions_on_time": len(on_time),
            "elapsed_sec": self.elapsed,
            "deadline_overrun": any(row["deadline_overrun"] for row in self.commit.rows),
            "realized_scan_fraction": self.controller.realized_scan_fraction,
            "distinct_utility_count": on_time_utility,
            "durable_distinct_utility_count": len(self.known_utility),
            "frontier_size": len(self.frontier),
        }

    def run(self, max_actions: int = 2000) -> dict[str, Any]:
        self.controller.reset(self.budget_sec, self.public_state())
        stop_reason = "no_complete_action_fits"
        final_error = None
        for _ in range(max_actions):
            state = self.public_state()
            decision = self.controller.choose_action(state)
            action = Action(decision["action"])
            if action is Action.STOP:
                stop_reason = str(decision["reason"])
                break
            estimate = state["estimated_scan_cost_sec" if action is Action.SCAN else "estimated_confirm_cost_sec"]
            try:
                result = self._scan(estimate) if action is Action.SCAN else self._confirm(estimate)
            except CandidateGenerationError as error:
                result = ActionResult(action, estimate, 0.0, False,
                                      payload={"error_type": type(error).__name__, "error": str(error)})
            if not result.completed:
                stop_reason = "action_failed"
                final_error = dict(result.payload or {})
                break
            utility = tuple(result.payload.get("distinct_utility_ids", ())) if (
                action is Action.CONFIRM and result.payload
            ) else ()
            prospective_utility = self.known_utility | set(utility)
            row = {"action": action.value, "estimated_cost_sec": estimate,
                   "actual_cost_sec": result.actual_cost_sec, "completed": True,
                   "elapsed_sec": self.elapsed, "deadline_overrun": self.elapsed > self.budget_sec,
                   "new_candidate_clusters": result.new_candidate_clusters,
                   "new_distinct_utility": result.new_distinct_utility,
                   "cumulative_utility": len(prospective_utility), **(result.payload or {})}
            self.commit.append(row, utility)
            if action is Action.CONFIRM:
                self.known_utility = prospective_utility
                self.frontier.terminalize(int(result.payload["unit_id"]))
                self.confirm_estimator.observe(result.actual_cost_sec)
            self.controller.observe(result)
        else:
            raise RuntimeError("controller failed to terminate")
        summary = self._summary()
        self.commit.finalize(summary, stop_reason=stop_reason, error=final_error)
        return summary
