from __future__ import annotations

from typing import Any

from .deadline import action_fits
from .state import Action, ActionResult, PublicState, validate_public_state


class FixedRatioController:
    """Selected R4 controller using realized wall-clock, with a 25% SCAN target."""

    policy_id = "R4_FIXED_TIME_RATIO_25_75"
    scan_target_fraction = 0.25

    def reset(self, total_budget_sec: float, public_initial_state: dict[str, Any]) -> None:
        validate_public_state(public_initial_state)
        self.total_budget_sec = float(total_budget_sec)
        self.scan_time = 0.0
        self.confirm_time = 0.0
        self.step = 0

    def choose_action(self, public_state: dict[str, Any]) -> dict[str, Any]:
        validate_public_state(public_state)
        state = PublicState(**public_state)
        scan = action_fits(state.estimated_scan_cost_sec, state.remaining_budget_sec)
        confirm = state.frontier_size > 0 and action_fits(
            state.estimated_confirm_cost_sec, state.remaining_budget_sec
        )
        legal = ([Action.SCAN] if scan else []) + ([Action.CONFIRM] if confirm else [])
        if not legal:
            return {"action": Action.STOP.value, "reason": "no_complete_action_fits"}
        elapsed = self.scan_time + self.confirm_time
        ratio = self.scan_time / max(elapsed, 1e-12)
        desired = Action.SCAN if ratio < self.scan_target_fraction or elapsed == 0 else Action.CONFIRM
        choice = desired if desired in legal else legal[0]
        return {"action": choice.value, "reason": self.policy_id}

    def observe(self, action_result: ActionResult) -> None:
        if action_result.completed:
            self.step += 1
            if action_result.action is Action.SCAN:
                self.scan_time += action_result.actual_cost_sec
            elif action_result.action is Action.CONFIRM:
                self.confirm_time += action_result.actual_cost_sec

    @property
    def realized_scan_fraction(self) -> float:
        total = self.scan_time + self.confirm_time
        return self.scan_time / total if total else 0.0
