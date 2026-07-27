from __future__ import annotations

from typing import Any

from .action import Action, ActionResult
from .common_utility import CommonUtilityModel, congestion_bucket, predicted_common_values, score_bucket


class FreeCommonUtilityController:
    def __init__(self, model: CommonUtilityModel):
        self.model = model

    def choose_action(self, env) -> dict[str, Any]:
        state = env.public_state()
        scan_legal = state["estimated_scan_cost_sec"] <= state["remaining_budget_sec"]
        confirm_legal = state["frontier_size"] > 0 and state["estimated_confirm_cost_sec"] <= state["remaining_budget_sec"]
        if not scan_legal and not confirm_legal: return {"action": "STOP", "reason": "no_complete_action_fits"}
        if state["frontier_size"] == 0: return {"action": "SCAN" if scan_legal else "STOP", "reason": "frontier_empty"}
        if not scan_legal: return {"action": "CONFIRM", "reason": "scan_illegal"}
        if not confirm_legal: return {"action": "SCAN", "reason": "confirm_illegal"}
        values = predicted_common_values(env, self.model)
        action = "CONFIRM" if values["uvps_confirm"] > values["uvps_scan"] else "SCAN"
        return {"action": action, "reason": "common_utility_uvps", **values}

    def observe(self, before: dict[str, Any], before_units: set[int], env, result: ActionResult) -> None:
        if result.action is Action.SCAN:
            counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
            for row in env.frontier.rows():
                if row.unit_id not in before_units:
                    counts[score_bucket(row.score)] += 1
            self.model.observe_scan({
                "coverage_bucket": "LOW" if before["coverage_fraction"] < 1/3 else "MEDIUM" if before["coverage_fraction"] < 2/3 else "HIGH",
                "congestion_bucket": congestion_bucket(before["frontier_size"]),
                **{f"arrivals_{k}": v for k, v in counts.items()},
            })
        elif result.action is Action.CONFIRM and result.score_bucket:
            self.model.observe_confirm(result.score_bucket, congestion_bucket(before["frontier_size"]), result.new_distinct_utility)


class RatioAnchoredCommonUtilityController(FreeCommonUtilityController):
    def __init__(self, model: CommonUtilityModel, target: float = .25, epsilon: float = .05):
        super().__init__(model); self.target = target; self.epsilon = epsilon

    def choose_action(self, env) -> dict[str, Any]:
        state = env.public_state()
        scan_legal = state["estimated_scan_cost_sec"] <= state["remaining_budget_sec"]
        confirm_legal = state["frontier_size"] > 0 and state["estimated_confirm_cost_sec"] <= state["remaining_budget_sec"]
        if not scan_legal and not confirm_legal: return {"action": "STOP", "reason": "no_complete_action_fits"}
        if state["frontier_size"] == 0: return {"action": "SCAN" if scan_legal else "STOP", "reason": "frontier_empty"}
        scan_time = sum(r["actual_action_cost_sec"] for r in env.ledger if r["action"] == "SCAN")
        confirm_time = sum(r["actual_action_cost_sec"] for r in env.ledger if r["action"] == "CONFIRM")
        rho = scan_time / max(scan_time + confirm_time, 1e-12)
        if scan_time + confirm_time == 0 or rho < self.target - self.epsilon:
            desired, reason = Action.SCAN, "below_ratio_band"
        elif rho > self.target + self.epsilon:
            desired, reason = Action.CONFIRM, "above_ratio_band"
        else:
            values = predicted_common_values(env, self.model)
            if values["uvps_confirm"] > values["uvps_scan"]: desired, reason = Action.CONFIRM, "common_utility_confirm"
            elif values["uvps_scan"] > values["uvps_confirm"]: desired, reason = Action.SCAN, "common_utility_scan"
            else: desired, reason = (Action.SCAN, "r4_tie") if rho < self.target else (Action.CONFIRM, "r4_tie")
        if desired is Action.SCAN and scan_legal: return {"action": "SCAN", "reason": reason, "scan_share": rho}
        if desired is Action.CONFIRM and confirm_legal: return {"action": "CONFIRM", "reason": reason, "scan_share": rho}
        fallback = "CONFIRM" if confirm_legal else "SCAN" if scan_legal else "STOP"
        return {"action": fallback, "reason": reason + ":legal_fallback", "scan_share": rho}
