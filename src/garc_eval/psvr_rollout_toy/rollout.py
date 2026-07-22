"""Rollout interfaces.

M1 is intentionally fail-closed.  The frozen D3/D4 assets do not define the
visible-history conditional kernel needed to distinguish M1 from the
clairvoyant C0 ceiling.  Cloning the realized episode here would leak future
latent outcomes into M1 action choice.
"""

from __future__ import annotations

from .environment import ToyEnvironment
from .schema import Action, VisibleState
from .utility import metrics_from_trace


class ProtocolBlocked(RuntimeError):
    """Raised when execution would require an unfrozen scientific choice."""


class ExactToyRolloutEvaluator:
    """Fail-closed placeholder for the missing non-clairvoyant model kernel."""

    def __init__(self, environment: ToyEnvironment):
        self.environment = environment
        self.calls: list[dict] = []

    def __call__(self, action: Action, visible_state: VisibleState) -> float:
        raise ProtocolBlocked(
            "BLOCKED_INTERNAL_INCONSISTENCY: D4 requires an exact conditional "
            "rollout from visible history, but frozen D3 defines neither a "
            "belief state nor a conditional transition sampler. Using the "
            "realized Episode would be forbidden future/latent leakage."
        )


class ClairvoyantSmallDP:
    """Exact deterministic finite-horizon ceiling for small realized worlds.

    C0 is evaluator-only and may inspect latent outcomes.  Unlike M1 it solves
    every reachable safe action recursively; it never falls back to pi0.
    """

    policy_id = "C0_CLAIRVOYANT_SMALL_DP"

    def __init__(
        self,
        environment: ToyEnvironment,
        max_safe_actions: int = 12,
        max_states: int = 100_000,
    ):
        self.environment = environment
        self.max_safe_actions = max_safe_actions
        self.max_states = max_states
        self.last_diagnostics: dict | None = None

    @staticmethod
    def _state_key(environment: ToyEnvironment) -> tuple:
        return (
            environment.elapsed.hex(),
            environment.mode,
            tuple(sorted(environment.scanned)),
            tuple(sorted(environment.emitted)),
            tuple(sorted(environment.terminal_witnesses)),
            tuple(sorted(environment.closed_hypotheses)),
            tuple(
                (row.event_id, row.committed_at.hex(), row.false_positive)
                for row in environment.committed
            ),
            environment.stopped,
        )

    @staticmethod
    def _terminal_value(environment: ToyEnvironment) -> float:
        return metrics_from_trace(environment.episode, environment.trace)[
            "time_weighted_unique_event_utility"
        ]

    def choose(self, state, safe_actions):
        if self.environment.visible_state() != state:
            raise ValueError("stale or foreign C0 state")
        if tuple(self.environment.safe_actions()) != tuple(safe_actions):
            raise ValueError("C0 safe action set mismatch")
        memo: dict[tuple, tuple[float, str]] = {}
        expanded = 0
        deepest = 0

        def solve(environment: ToyEnvironment, depth: int) -> tuple[float, str]:
            nonlocal expanded, deepest
            key = self._state_key(environment)
            if key in memo:
                return memo[key]
            expanded += 1
            deepest = max(deepest, depth)
            if expanded > self.max_states:
                raise RuntimeError("C0_STATE_SPACE_BLOCK: max_states exceeded")
            actions = environment.safe_actions()
            if len(actions) > self.max_safe_actions:
                raise RuntimeError("C0_ACTION_SPACE_BLOCK: max_safe_actions exceeded")
            best_value = self._terminal_value(environment)
            best_id = Action.stop().identifier
            for action in sorted(actions, key=lambda row: row.identifier):
                if action.kind == "STOP":
                    value = self._terminal_value(environment)
                else:
                    branch = environment.clone()
                    branch.execute(action)
                    value, _ = solve(branch, depth + 1)
                if value > best_value or (value == best_value and action.identifier < best_id):
                    best_value = value
                    best_id = action.identifier
            memo[key] = (best_value, best_id)
            return memo[key]

        value, action_id = solve(self.environment.clone(), 0)
        by_id = {action.identifier: action for action in safe_actions}
        self.last_diagnostics = {
            "optimal_value": value,
            "states_expanded": expanded,
            "memoized_states": len(memo),
            "maximum_depth": deepest,
            "clairvoyant": True,
            "continuation": "EXACT_RECURSIVE_DP",
        }
        return by_id[action_id]
