from __future__ import annotations

from dataclasses import replace

from .policy import SafeCoveragePolicy
from .state import CoverageState


def estimated_next_cost(state: CoverageState, fallback_sec: float = 1.0) -> float:
    costs = [value for value in state.past_action_costs_sec if value > 0]
    return max(costs) if costs else fallback_sec


def run_scan(
    units,
    max_actions: int,
    *,
    policy: SafeCoveragePolicy | None = None,
    budget_sec: float = float("inf"),
    action_costs: dict[str, float] | None = None,
) -> list[dict]:
    """Execute complete SCAN actions with conservative, pre-action admission."""
    policy = policy or SafeCoveragePolicy()
    state = CoverageState(tuple(units), remaining_budget_sec=budget_sec)
    rows: list[dict] = []
    costs = action_costs or {}
    for action_index in range(min(max_actions, len(state.units))):
        estimate = estimated_next_cost(state)
        if estimate > state.remaining_budget_sec:
            break
        unit_id = policy.choose_next_unit(state)
        actual = float(costs.get(unit_id, estimate))
        if actual < 0:
            raise ValueError("action cost cannot be negative")
        rows.append({"action_index": action_index + 1, "policy_id": policy.policy_id,
                     "unit_id": unit_id, "estimated_cost_sec": estimate,
                     "actual_cost_sec": actual, "completed": True})
        state = replace(state, scanned_unit_ids=state.scanned_unit_ids + (unit_id,),
                        current_unit_id=unit_id,
                        remaining_budget_sec=state.remaining_budget_sec - actual,
                        past_action_costs_sec=state.past_action_costs_sec + (actual,))
    return rows
