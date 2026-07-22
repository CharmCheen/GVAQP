"""Evaluator-only H1B reference; never accepted by :class:`ApproximatePlanner`.

This module is deliberately a one-way boundary.  It receives an already
realised *visible* history and reuses the frozen R2 finite-support conditional
kernel.  It is used only after a policy action is durable in an execution
trace; no approximate-planner module imports this file.
"""
from __future__ import annotations
from dataclasses import dataclass
from .types import ActionView, VisibleDecisionState
from garc_eval.psvr_rollout_toy.r2 import (
    ActionR2, ExactConditionalRollout, ExactPosterior, ShieldedPi0R2,
    VisibleHistory, finite_world_library,
)

@dataclass(frozen=True)
class ExactReferenceRecord:
    visible_history_hash: str
    exact_action: ActionView
    action_values: dict[str, float]
    safe_actions: tuple[str, ...] = ()
    remaining_ticks: int = 0
    exact_kernel_hash: str = "R2_FINITE_VISIBLE_HISTORY_CONDITIONAL"

class ExactEvaluatorAPI:
    def reference(self, state: VisibleDecisionState) -> ExactReferenceRecord:  # pragma: no cover - interface only
        raise NotImplementedError


class ExactReferenceEvaluator(ExactEvaluatorAPI):
    """Memoized evaluator-only adapter for the frozen exact R2 M1 kernel.

    The cache key includes the visible history, horizon, safe action set and
    kernel identity.  It intentionally has no method which accepts an
    ``ApproximatePlanner`` or planner trace.
    """
    kernel_hash = "R2_FINITE_VISIBLE_HISTORY_CONDITIONAL"

    def __init__(self) -> None:
        self._rollout = ExactConditionalRollout(ExactPosterior(finite_world_library()), ShieldedPi0R2())
        self._cache: dict[tuple[str, int, float, tuple[str, ...], str], ExactReferenceRecord] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def cache_snapshot(self) -> dict[str, int]:
        return {"entries": len(self._cache), "hits": self.cache_hits, "misses": self.cache_misses}

    @staticmethod
    def _to_r2(action: ActionView) -> ActionR2:
        if action.kind == "SCAN":
            return ActionR2.scan(action.region_id or action.identifier.split(":")[1])
        if action.kind == "CONFIRM":
            return ActionR2.confirm(action.hypothesis_id or action.identifier.split(":")[2], action.witness_id or action.identifier.split(":")[3])
        return ActionR2.stop()

    def reference_for_history(self, history: VisibleHistory, state: VisibleDecisionState,
                              accrued_utility: float = 0.0) -> ExactReferenceRecord:
        """Evaluate post-planning actions on the actual SMDP clock.

        ``history`` is intentionally lossless only for observable actions and
        observations.  Planning time is not an observation, so callers bind
        the post-planning horizon in ``state`` and the already earned net D1
        reward separately.  The frozen R2 kernel is used only for transitions.
        """
        safe = tuple(sorted(action.identifier for action in state.ordered_actions()))
        key = (history.digest, state.remaining_ticks, float(accrued_utility), safe, self.kernel_hash)
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        actions = tuple(state.ordered_actions())
        if not actions:
            actions = (ActionView("STOP:::", "STOP"),)
        # Planning time is not an environment observation, so it is absent from
        # ``history``.  Advance each evaluator-private continuation by exactly
        # the visible remaining-horizon difference before testing actions.
        values: dict[str, float] = {}
        weights = self._rollout.posterior.weights(history)
        for action in actions:
            total = 0.0
            r2_action = self._to_r2(action)
            for world in self._rollout.posterior.worlds:
                weight = weights[world.world_id]
                if not weight:
                    continue
                from garc_eval.psvr_rollout_toy.r2 import replay
                env = replay(world, history)
                assert env is not None
                elapsed_gap = env.visible_state().remaining_ticks - state.remaining_ticks
                if elapsed_gap < 0:
                    raise ValueError("exact evaluator received a remaining horizon greater than visible history permits")
                env._elapsed += elapsed_gap
                if r2_action.identifier not in {candidate.identifier for candidate in env.safe_actions()}:
                    # The supplied safe set is authoritative.  A mismatch is
                    # integrity failure, never an evaluator fallback.
                    raise ValueError("exact evaluator safe-action mismatch")
                incremental = 0.0
                observation = env.execute(r2_action)
                if observation.outcome == "NEW_COMMIT":
                    incremental += env.history.horizon_ticks - env.visible_state().elapsed_ticks
                while not env.visible_state().stopped:
                    observation = env.execute(self._rollout.continuation.choose(env.history, env.safe_actions()))
                    if observation.outcome == "NEW_COMMIT":
                        incremental += env.history.horizon_ticks - env.visible_state().elapsed_ticks
                total += weight * (float(accrued_utility) + incremental)
            values[action.identifier] = total
        # Frozen exact kernel resolves ties deterministically by identifier,
        # preserving its STOP preference only when values are otherwise tied.
        selected = max(actions, key=lambda action: (values[action.identifier], action.kind == "STOP", action.identifier))
        record = ExactReferenceRecord(history.digest, selected, values, safe, state.remaining_ticks, self.kernel_hash)
        self._cache[key] = record
        return record

    def reference(self, state: VisibleDecisionState) -> ExactReferenceRecord:
        raise RuntimeError("ExactReferenceEvaluator requires the visible R2 history; use reference_for_history")
