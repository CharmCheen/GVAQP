from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy
from typing import Any

from .action import Action, ActionResult
from .posterior import BetaBernoulli, GammaPoisson
from .state import PublicState, validate_public_state
from .vps import bucket, value_per_second


class ScanConfirmController(ABC):
    @abstractmethod
    def reset(self, total_budget_sec: float, public_initial_state: dict[str, Any]) -> None: ...

    @abstractmethod
    def choose_action(self, public_state: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def observe(self, action_result: ActionResult) -> None: ...


class MyopicVPSController(ScanConfirmController):
    def __init__(
        self,
        *,
        alpha_s: float = 1.0,
        beta_s: float = 1.0,
        alpha_c: float = 1.0,
        beta_c: float = 1.0,
        margin: float = 0.0,
        tie_break: str = "SCAN",
        minimum_bucket_samples: int = 3,
        use_scan_buckets: bool = True,
        use_confirm_buckets: bool = True,
        cost_normalization: bool = True,
        shrinkage: bool = True,
        use_remaining_budget_value: bool = True,
    ):
        self.params = locals().copy()
        self.params.pop("self")
        self.reset(0.0, PublicState(0.0).to_dict())

    def reset(self, total_budget_sec: float, public_initial_state: dict[str, Any]) -> None:
        validate_public_state(public_initial_state)
        self.total_budget_sec = float(total_budget_sec)
        a_s = self.params["alpha_s"] if self.params["shrinkage"] else 0.0
        b_s = self.params["beta_s"] if self.params["shrinkage"] else 0.0
        a_c = self.params["alpha_c"] if self.params["shrinkage"] else 0.0
        b_c = self.params["beta_c"] if self.params["shrinkage"] else 0.0
        self.scan_global = GammaPoisson(a_s, b_s)
        self.confirm_global = BetaBernoulli(a_c, b_c)
        self.scan_bucket = defaultdict(lambda: GammaPoisson(a_s, b_s))
        self.confirm_bucket = defaultdict(lambda: BetaBernoulli(a_c, b_c))

    def _scan_mean(self, name: str) -> float:
        local = self.scan_bucket[name]
        if self.params["use_scan_buckets"] and local.n >= self.params["minimum_bucket_samples"]:
            return local.mean
        return self.scan_global.mean if self.scan_global.n or self.params["shrinkage"] else 0.0

    def _confirm_mean(self, name: str) -> float:
        local = self.confirm_bucket[name]
        if self.params["use_confirm_buckets"] and local.n >= self.params["minimum_bucket_samples"]:
            return local.mean
        return self.confirm_global.mean if self.confirm_global.n or self.params["shrinkage"] else 0.0

    def choose_action(self, public_state: dict[str, Any]) -> dict[str, Any]:
        validate_public_state(public_state)
        state = PublicState(**public_state)
        scan_legal = state.estimated_scan_cost_sec <= state.remaining_budget_sec
        confirm_legal = state.frontier_size > 0 and state.estimated_confirm_cost_sec <= state.remaining_budget_sec
        if not scan_legal and not confirm_legal:
            action, reason = Action.STOP, "no_complete_action_fits"
        elif state.frontier_size == 0:
            action, reason = (Action.SCAN, "frontier_empty") if scan_legal else (Action.STOP, "frontier_empty_scan_illegal")
        elif not confirm_legal:
            action, reason = (Action.SCAN, "confirm_illegal") if scan_legal else (Action.STOP, "confirm_illegal_scan_illegal")
        elif not scan_legal:
            action, reason = Action.CONFIRM, "scan_illegal"
        else:
            scan_bucket = bucket(state.coverage_fraction, (1 / 3, 2 / 3))
            confirm_bucket = bucket(state.frontier_score_max, (1 / 3, 2 / 3))
            v_scan = value_per_second(self._scan_mean(scan_bucket), state.estimated_scan_cost_sec, self.params["cost_normalization"])
            v_confirm = value_per_second(self._confirm_mean(confirm_bucket), state.estimated_confirm_cost_sec, self.params["cost_normalization"])
            if v_confirm > v_scan + self.params["margin"]:
                action, reason = Action.CONFIRM, "confirm_vps_greater"
            elif v_scan > v_confirm + self.params["margin"]:
                action, reason = Action.SCAN, "scan_vps_greater"
            else:
                action = Action(self.params["tie_break"])
                reason = "vps_tie"
            if not self.params["use_remaining_budget_value"]:
                reason += ":budget_excluded_from_value"
        return {"action": action.value, "reason": reason}

    def observe(self, action_result: ActionResult) -> None:
        if not action_result.completed:
            return
        if action_result.action is Action.SCAN:
            self.scan_global.update(action_result.new_candidate_clusters)
            self.scan_bucket[action_result.coverage_bucket or "GLOBAL"].update(action_result.new_candidate_clusters)
        elif action_result.action is Action.CONFIRM:
            self.confirm_global.update(action_result.new_distinct_utility)
            self.confirm_bucket[action_result.score_bucket or "GLOBAL"].update(action_result.new_distinct_utility)

