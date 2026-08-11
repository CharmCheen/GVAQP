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
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and strictly positive")
        self.scan_cost_upper_sec = float(scan_cost_upper_sec)
        self.verify_cost_upper_sec = float(verify_cost_upper_sec)

    def effective_costs(self, public_state: dict) -> dict[str, float | None]:
        validate_public_state(public_state)
        state = PublicState(**public_state)
        if not math.isfinite(state.estimated_scan_cost_sec) or state.estimated_scan_cost_sec <= 0:
            scan_required = None
        else:
            scan_required = max(self.scan_cost_upper_sec, state.estimated_scan_cost_sec)
        if not math.isfinite(state.estimated_confirm_cost_sec) or state.estimated_confirm_cost_sec <= 0:
            verify_current_required = None
        else:
            verify_current_required = max(
                self.verify_cost_upper_sec, state.estimated_confirm_cost_sec
            )
        # With an empty frontier, infinity means VERIFY is not currently
        # available; it does not invalidate the independently frozen reserve
        # for a candidate that a productive SCAN may create.
        verify_reserve_required = (
            self.verify_cost_upper_sec
            if state.frontier_size == 0 and verify_current_required is None
            else verify_current_required
        )
        return {
            "scan": scan_required,
            "verify_current": verify_current_required,
            "verify_reserve_after_scan": verify_reserve_required,
        }

    def legal_actions(self, public_state: dict) -> tuple[Action, ...]:
        validate_public_state(public_state)
        state = PublicState(**public_state)
        costs = self.effective_costs(public_state)
        # A scan is productive only if one subsequent verification opportunity
        # remains. Never reduce a larger currently visible causal cost signal.
        scan_legal = (
            costs["scan"] is not None
            and costs["verify_reserve_after_scan"] is not None
            and costs["scan"] + costs["verify_reserve_after_scan"]
            <= state.remaining_budget_sec
        )
        verify_legal = (
            state.frontier_size > 0
            and costs["verify_current"] is not None
            and costs["verify_current"] <= state.remaining_budget_sec
        )
        return tuple(
            action
            for action, legal in ((Action.SCAN, scan_legal), (Action.CONFIRM, verify_legal))
            if legal
        )

    def enforce(self, proposed_action: Action, public_state: dict) -> ShieldDecision:
        legal = self.legal_actions(public_state)
        if proposed_action is Action.STOP:
            # A safety layer may downgrade work to STOP, never upgrade a
            # baseline STOP into an action.
            action, reason = Action.STOP, "baseline_stop_preserved"
        elif not legal:
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
