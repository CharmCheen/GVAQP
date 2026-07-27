from __future__ import annotations

import random
from typing import Any

from .action import Action, ActionResult
from .myopic_controller import ScanConfirmController
from .state import PublicState, validate_public_state


class FixedPolicyController(ScanConfirmController):
    def __init__(self, policy: str, seed: int = 0):
        self.policy = policy
        self.seed = seed

    def reset(self, total_budget_sec: float, public_initial_state: dict[str, Any]) -> None:
        validate_public_state(public_initial_state)
        self.rng = random.Random(self.seed)
        self.scan_time = self.confirm_time = 0.0
        self.step = 0

    def choose_action(self, public_state: dict[str, Any]) -> dict[str, Any]:
        validate_public_state(public_state)
        s = PublicState(**public_state)
        scan = s.estimated_scan_cost_sec <= s.remaining_budget_sec
        confirm = s.frontier_size > 0 and s.estimated_confirm_cost_sec <= s.remaining_budget_sec
        legal = ([Action.SCAN] if scan else []) + ([Action.CONFIRM] if confirm else [])
        if not legal:
            return {"action": Action.STOP.value, "reason": "no_complete_action_fits"}
        if self.policy == "R0_SCAN_FIRST":
            choice = Action.SCAN if scan else Action.CONFIRM
        elif self.policy == "R1_CONFIRM_FIRST" or self.policy == "R6_FRONTIER_RULE":
            choice = Action.CONFIRM if confirm else Action.SCAN
        elif self.policy == "R5_PERIODIC":
            desired = Action.SCAN if self.step % 2 == 0 else Action.CONFIRM
            choice = desired if desired in legal else legal[0]
        elif self.policy == "R7_RANDOM":
            choice = self.rng.choice(legal)
        else:
            target = {"R2_RATIO_75_25": .75, "R3_RATIO_50_50": .5, "R4_RATIO_25_75": .25}[self.policy]
            rho = self.scan_time / max(self.scan_time + self.confirm_time, 1e-12)
            desired = Action.SCAN if rho < target or self.scan_time + self.confirm_time == 0 else Action.CONFIRM
            choice = desired if desired in legal else legal[0]
        return {"action": choice.value, "reason": self.policy}

    def observe(self, action_result: ActionResult) -> None:
        if action_result.completed:
            self.step += 1
            if action_result.action is Action.SCAN:
                self.scan_time += action_result.actual_cost_sec
            elif action_result.action is Action.CONFIRM:
                self.confirm_time += action_result.actual_cost_sec

