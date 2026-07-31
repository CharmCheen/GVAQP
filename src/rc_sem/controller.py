from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .types import Action, ActionOption, ControllerState, Decision


@dataclass(frozen=True)
class ControllerConfig:
    uncertainty_beta: float = 1.0
    scan_margin: float = 0.0
    verify_margin: float = 0.0
    stop_margin: float = 0.0
    fallback_action: Action = Action.VERIFY
    scan_requires_verify_reserve: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("uncertainty_beta", self.uncertainty_beta),
            ("scan_margin", self.scan_margin),
            ("verify_margin", self.verify_margin),
            ("stop_margin", self.stop_margin),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.fallback_action not in {Action.SCAN, Action.VERIFY}:
            raise ValueError("fallback_action must be SCAN or VERIFY")


class RCSEMController:
    """Conservative binary action selector with an always-legal STOP action."""

    def __init__(self, config: ControllerConfig | None = None) -> None:
        self.config = config or ControllerConfig()

    def choose(
        self,
        state: ControllerState,
        options: Iterable[ActionOption],
    ) -> Decision:
        best_by_action = self._best_options(options)
        safe = self._safe_options(state, best_by_action)
        safe_actions = tuple(action for action in (Action.SCAN, Action.VERIFY) if action in safe)

        if not safe:
            return Decision(Action.STOP, None, "no_complete_action_fits", safe_actions)

        optimistic = {
            action: option.value_mean
            + self.config.uncertainty_beta * option.value_uncertainty
            for action, option in safe.items()
        }
        if max(optimistic.values()) <= self.config.stop_margin:
            return Decision(Action.STOP, None, "no_positive_optimistic_value", safe_actions)

        if len(safe) == 1:
            action, option = next(iter(safe.items()))
            return Decision(action, option.target_id, "only_one_safe_productive_action", safe_actions)

        scan = safe[Action.SCAN]
        verify = safe[Action.VERIFY]
        delta_mean = scan.value_mean - verify.value_mean
        delta_uncertainty = math.hypot(
            scan.value_uncertainty,
            verify.value_uncertainty,
        )
        lower = delta_mean - self.config.uncertainty_beta * delta_uncertainty
        upper = delta_mean + self.config.uncertainty_beta * delta_uncertainty

        if lower > self.config.scan_margin:
            chosen, reason = scan, "scan_conservative_advantage"
        elif upper < -self.config.verify_margin:
            chosen, reason = verify, "verify_conservative_advantage"
        else:
            fallback = self.config.fallback_action
            chosen = safe[fallback]
            reason = "uncertain_advantage_frozen_fallback"

        return Decision(
            action=chosen.action,
            target_id=chosen.target_id,
            reason=reason,
            safe_actions=safe_actions,
            delta_mean=delta_mean,
            delta_uncertainty=delta_uncertainty,
        )

    def _best_options(self, options: Iterable[ActionOption]) -> dict[Action, ActionOption]:
        by_action: dict[Action, ActionOption] = {}
        for option in options:
            prior = by_action.get(option.action)
            conservative = (
                option.value_mean
                - self.config.uncertainty_beta * option.value_uncertainty
            )
            key = (conservative, option.value_mean, -option.cost_upper_sec, option.target_id)
            if prior is None:
                by_action[option.action] = option
                continue
            prior_conservative = (
                prior.value_mean
                - self.config.uncertainty_beta * prior.value_uncertainty
            )
            prior_key = (
                prior_conservative,
                prior.value_mean,
                -prior.cost_upper_sec,
                prior.target_id,
            )
            if key > prior_key:
                by_action[option.action] = option
        return by_action

    def _safe_options(
        self,
        state: ControllerState,
        options: dict[Action, ActionOption],
    ) -> dict[Action, ActionOption]:
        safe = {
            action: option
            for action, option in options.items()
            if option.cost_upper_sec <= state.remaining_sec
            and not (action is Action.VERIFY and state.frontier_size == 0)
        }
        scan = safe.get(Action.SCAN)
        reserve_required = scan is not None and (
            self.config.scan_requires_verify_reserve
            or not scan.can_directly_materialize
        )
        if reserve_required:
            verify = options.get(Action.VERIFY)
            if verify is None or (
                scan.cost_upper_sec + verify.cost_upper_sec > state.remaining_sec
            ):
                del safe[Action.SCAN]
        return safe
