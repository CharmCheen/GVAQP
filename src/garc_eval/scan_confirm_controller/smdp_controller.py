from __future__ import annotations

from typing import Any

from .action import Action, ActionResult
from .fixed_ratio import FixedPolicyController
from .myopic_controller import ScanConfirmController
from .smdp_safety_shield import BinarySMDPSafetyShield
from .state import validate_public_state


class HeadroomGateFallbackController(ScanConfirmController):
    """Fail-closed R4 controller used when value learning is not authorized.

    This class deliberately has no model input. It exists to make the frozen
    headroom-gate stop behavior executable and testable, not to stand in for a
    trained binary SMDP controller.
    """

    def __init__(self, *, scan_cost_upper_sec: float, verify_cost_upper_sec: float) -> None:
        self.baseline = FixedPolicyController("R4_RATIO_25_75", seed=0)
        self.shield = BinarySMDPSafetyShield(
            scan_cost_upper_sec=scan_cost_upper_sec,
            verify_cost_upper_sec=verify_cost_upper_sec,
        )

    def reset(self, total_budget_sec: float, public_initial_state: dict[str, Any]) -> None:
        validate_public_state(public_initial_state)
        self.baseline.reset(total_budget_sec, public_initial_state)

    def choose_action(self, public_state: dict[str, Any]) -> dict[str, Any]:
        validate_public_state(public_state)
        baseline = self.baseline.choose_action(public_state)
        baseline_action = Action(baseline["action"])
        shield = self.shield.enforce(baseline_action, public_state)
        effective_costs = self.shield.effective_costs(public_state)
        return {
            "action": shield.action.value,
            "reason": "headroom_gate_failed_r4_fallback",
            "q_scan": None,
            "q_verify": None,
            "delta_mean": None,
            "delta_uncertainty": None,
            "baseline_action": baseline_action.value,
            "final_action": shield.action.value,
            "shield_triggered": shield.triggered,
            "shield_reason": shield.reason,
            "remaining_budget": float(public_state["remaining_budget_sec"]),
            "cost_upper": {
                "scan": self.shield.scan_cost_upper_sec,
                "verify": self.shield.verify_cost_upper_sec,
            },
            "effective_admission_cost": effective_costs,
            "support_score": None,
            "ood_status": "LEARNING_NOT_AUTHORIZED_HEADROOM_GATE_FAILED",
        }

    def observe(self, action_result: ActionResult) -> None:
        self.baseline.observe(action_result)
