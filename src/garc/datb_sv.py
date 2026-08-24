from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from garc.confirm import ConfirmAdapter, DurableCommitLog
from garc.controller import FrozenCandidateGenerator, FrozenFrontier
from garc.controller.state import Action


ALGORITHM_ID = "DATB_SV_CPU_REPLAY_V1"


def bisection_order(cell_count: int) -> tuple[int, ...]:
    """Return the frozen breadth-first temporal-bisection permutation."""
    if cell_count < 0:
        raise ValueError("cell_count must be non-negative")
    queue = [(0, cell_count - 1)]
    order: list[int] = []
    while queue:
        left, right = queue.pop(0)
        if left > right:
            continue
        middle = (left + right) // 2
        order.append(middle)
        queue.append((left, middle - 1))
        queue.append((middle + 1, right))
    return tuple(order)


@dataclass(frozen=True)
class DatbSVConfig:
    deadline_sec: float
    scan_cost_upper_sec: float
    verify_cost_upper_sec: float
    commit_reserve_sec: float = 0.0
    frontier_capacity: int = 10

    def __post_init__(self) -> None:
        for name in ("deadline_sec", "scan_cost_upper_sec", "verify_cost_upper_sec", "commit_reserve_sec"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.frontier_capacity < 1:
            raise ValueError("frontier_capacity must be positive")


class DatbSVReplayRunner:
    """Oracle-agnostic CPU replay of deterministic DATB-SV.

    The backend is a frozen mapping or callable accepted by ``ConfirmAdapter``.
    The executor never inspects how labels were produced. Only completed,
    pre-deadline actions may change the durable result.
    """

    def __init__(
        self,
        units: list[dict[str, Any]],
        confirm_backend: Mapping[int, dict[str, Any]] | Callable[[dict[str, Any]], dict[str, Any]],
        config: DatbSVConfig,
        *,
        commit_path: Path,
        oracle_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.oracle_metadata = dict(oracle_metadata or {})
        self.units = sorted((dict(row) for row in units), key=lambda row: (
            float(row["start_sec"]), float(row["end_sec"]), int(row["unit_id"])
        ))
        unit_ids = [int(row["unit_id"]) for row in self.units]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("unit_id must be unique")
        for row in self.units:
            start, end = float(row["start_sec"]), float(row["end_sec"])
            cost = float(row.get("scan_cost_sec", 0.0))
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
                raise ValueError("each unit needs a finite positive interval")
            if not math.isfinite(cost) or cost < 0:
                raise ValueError("scan_cost_sec must be finite and non-negative")
            if not isinstance(row.get("candidates", []), list):
                raise ValueError("unit candidates must be a list")

        self.order = bisection_order(len(self.units))
        self.cursor = 0
        self.elapsed_sec = 0.0
        self.next_operator = Action.SCAN
        self.frontier = FrozenFrontier(config.frontier_capacity)
        self.candidates = FrozenCandidateGenerator()
        self.confirm = ConfirmAdapter(confirm_backend)
        self.commit = DurableCommitLog(commit_path)
        self.known_utility: set[str] = set()
        self.trace: list[dict[str, Any]] = []

    def _available(self, action: Action) -> bool:
        if action is Action.SCAN:
            return self.cursor < len(self.order)
        if action is Action.CONFIRM:
            return self.frontier.best() is not None
        return False

    def _upper_cost(self, action: Action) -> float:
        return self.config.scan_cost_upper_sec if action is Action.SCAN else self.config.verify_cost_upper_sec

    def _fits(self, action: Action) -> bool:
        required = self._upper_cost(action) + self.config.commit_reserve_sec
        return self._available(action) and self.elapsed_sec + required <= self.config.deadline_sec

    def _choose(self) -> Action:
        desired = self.next_operator
        other = Action.CONFIRM if desired is Action.SCAN else Action.SCAN
        if self._fits(desired):
            return desired
        if self._fits(other):
            return other
        return Action.STOP

    def _scan(self) -> tuple[dict[str, Any], tuple[str, ...], bool]:
        row = self.units[self.order[self.cursor]]
        unit_id = int(row["unit_id"])
        cost = float(row.get("scan_cost_sec", 0.0))
        start = self.elapsed_sec
        complete = start + cost
        trace = {
            "action": Action.SCAN.value,
            "unit_id": unit_id,
            "logical_start_sec": start,
            "complete_sec": complete,
            "actual_cost_sec": cost,
            "declared_upper_cost_sec": self.config.scan_cost_upper_sec,
            "cost_bound_violation": cost > self.config.scan_cost_upper_sec,
            "completed_by_deadline": complete <= self.config.deadline_sec,
        }
        self.elapsed_sec = complete
        if complete > self.config.deadline_sec:
            return trace, (), False
        self.cursor += 1
        visible = self.candidates.observe_scan(
            unit_id,
            row.get("candidates", []),
            elapsed_sec=complete,
            scan_index=self.cursor - 1,
        )
        admitted, dropped = self.frontier.update(visible)
        trace.update({
            "completed": True,
            "candidate_ids": sorted(candidate.candidate_id for candidate in visible),
            "new_frontier_units": admitted,
            "dropped_unit_ids": dropped,
            "cumulative_utility": len(self.known_utility),
        })
        return trace, (), True

    def _verify(self) -> tuple[dict[str, Any], tuple[str, ...], bool]:
        candidate = self.frontier.best()
        if candidate is None:
            raise RuntimeError("VERIFY selected with an empty frontier")
        start = self.elapsed_sec
        outcome = self.confirm.confirm(candidate)
        complete = start + outcome.actual_cost_sec
        trace = {
            "action": Action.CONFIRM.value,
            "unit_id": candidate.unit_id,
            "candidate_id": candidate.candidate_id,
            "logical_start_sec": start,
            "complete_sec": complete,
            "actual_cost_sec": outcome.actual_cost_sec,
            "declared_upper_cost_sec": self.config.verify_cost_upper_sec,
            "cost_bound_violation": outcome.actual_cost_sec > self.config.verify_cost_upper_sec,
            "completed_by_deadline": complete <= self.config.deadline_sec,
            "positive": outcome.positive,
        }
        self.elapsed_sec = complete
        if complete > self.config.deadline_sec:
            return trace, (), False
        utility = tuple(outcome.distinct_utility_ids)
        new_utility = set(utility) - self.known_utility
        self.known_utility |= set(utility)
        self.frontier.terminalize(candidate.unit_id)
        trace.update({
            "completed": True,
            "distinct_utility_ids": list(utility),
            "new_distinct_utility": len(new_utility),
            "cumulative_utility": len(self.known_utility),
            "materialized": outcome.materialized,
        })
        return trace, utility, True

    def run(self, max_actions: int = 10000) -> dict[str, Any]:
        stop_reason = "NO_COMPLETE_ACTION_FITS"
        for _ in range(max_actions):
            action = self._choose()
            if action is Action.STOP:
                break
            row, utility, durable = self._scan() if action is Action.SCAN else self._verify()
            self.trace.append(row)
            if not durable:
                stop_reason = "POST_DEADLINE_DIAGNOSTIC_ONLY"
                break
            self.commit.append(row, utility)
            self.next_operator = Action.CONFIRM if action is Action.SCAN else Action.SCAN
            if row["cost_bound_violation"]:
                stop_reason = "DECLARED_COST_BOUND_VIOLATED"
                break
        else:
            raise RuntimeError("DATB-SV failed to terminate")

        summary = {
            "algorithm_id": ALGORITHM_ID,
            "status": "CPU_REPLAY_COMPLETE",
            "deadline_sec": self.config.deadline_sec,
            "elapsed_sec": self.elapsed_sec,
            "durable_actions": len(self.commit.rows),
            "diagnostic_actions": len(self.trace) - len(self.commit.rows),
            "scan_actions": sum(row["action"] == Action.SCAN.value for row in self.commit.rows),
            "verify_actions": sum(row["action"] == Action.CONFIRM.value for row in self.commit.rows),
            "distinct_utility_count": len(self.known_utility),
            "distinct_utility_ids": sorted(self.known_utility),
            "frontier_size": len(self.frontier),
            "unscanned_cells": len(self.order) - self.cursor,
            "stop_reason": stop_reason,
            "oracle_metadata_recorded_not_inspected": self.oracle_metadata,
            "new_inference_performed": False,
            "training_performed": False,
        }
        self.commit.finalize(summary, stop_reason=stop_reason)
        return summary

