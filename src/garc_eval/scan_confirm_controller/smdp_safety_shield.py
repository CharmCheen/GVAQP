from __future__ import annotations

import math
from dataclasses import dataclass

from .action import Action
from .state import PublicState, validate_public_state


@dataclass(frozen=True)
class ShieldDecision:
    action: Action
    proposed_action: Action
    legal_actions: tuple[Action, ...]
    triggered: bool
    reason: str


class BinarySMDPSafetyShield:
    """Causal complete-action admission shield with frozen cost bounds."""

    def __init__(self, *, scan_cost_upper_sec: float, verify_cost_upper_sec: float) -> None:
        for name, value in (
            ("scan_cost_upper_sec", scan_cost_upper_sec),
            ("verify_cost_upper_sec", verify_cost_upper_sec),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        self.scan_cost_upper_sec = float(scan_cost_upper_sec)
        self.verify_cost_upper_sec = float(verify_cost_upper_sec)

    def legal_actions(self, public_state: dict) -> tuple[Action, ...]:
        validate_public_state(public_state)
        state = PublicState(**public_state)
        # A scan is productive only if one subsequent verification opportunity
        # remains under independently frozen complete-action upper bounds.
        scan_legal = (
            self.scan_cost_upper_sec + self.verify_cost_upper_sec
            <= state.remaining_budget_sec
        )
        verify_legal = (
            state.frontier_size > 0
            and self.verify_cost_upper_sec <= state.remaining_budget_sec
        )
        return tuple(
            action
            for action, legal in ((Action.SCAN, scan_legal), (Action.CONFIRM, verify_legal))
            if legal
        )

    def enforce(self, proposed_action: Action, public_state: dict) -> ShieldDecision:
        legal = self.legal_actions(public_state)
        if not legal:
            action, reason = Action.STOP, "no_complete_action_fits_frozen_upper_bounds"
        elif len(legal) == 1:
            action, reason = legal[0], "only_one_productive_action_legal"
        elif proposed_action in legal:
            action, reason = proposed_action, "proposal_legal"
        else:
            # STOP is not a learned action. When productive work is legal, use
            # VERIFY first, then SCAN, as the conservative deterministic repair.
            action = Action.CONFIRM if Action.CONFIRM in legal else Action.SCAN
            reason = "illegal_proposal_repaired"
        return ShieldDecision(
            action=action,
            proposed_action=proposed_action,
            legal_actions=legal,
            triggered=action is not proposed_action,
            reason=reason,
        )
