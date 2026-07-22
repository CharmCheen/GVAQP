"""Visible-state approximate rollout decision path with no evaluator dependency."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Protocol
from .advantage import paired_advantage
from .budgets import require_budget
from .fallback import select_with_fallback
from .planning_cost import consume_planning_time
from .plan_admission import planning_admission
from .trace_schema import PlannerTrace
from .types import ActionView, VisibleDecisionState
from .uncertainty import paired_lcb_95

class PairedModelAPI(Protocol):
    def paired_returns(self, state: VisibleDecisionState, action: ActionView, base: ActionView, worlds: int, trajectories: int) -> tuple[tuple[float, ...], tuple[float, ...]]: ...

@dataclass(frozen=True)
class PlannerConfig:
    posterior_worlds: int
    trajectories: int
    planning_ticks: int
    mode: str  # UNGATED, POINT, LCB
    error_condition: str = "STANDARD"  # STANDARD or JOINT_CORNER

    def __post_init__(self) -> None:
        require_budget(self.posterior_worlds, self.trajectories, self.planning_ticks)
        if self.mode not in {"UNGATED", "POINT", "LCB"} or self.error_condition not in {"STANDARD", "JOINT_CORNER"}: raise ValueError("unknown frozen planner configuration")

    @property
    def bias_margin(self) -> float:
        return 320.0 if self.error_condition == "JOINT_CORNER" else 0.0

class ApproximatePlanner:
    """Constructor deliberately accepts only visible base policy and paired model."""
    def __init__(self, base_policy: Callable[[VisibleDecisionState], ActionView], paired_model: PairedModelAPI, config: PlannerConfig):
        self._base_policy, self._model, self._config = base_policy, paired_model, config

    def decide(self, state: VisibleDecisionState) -> tuple[ActionView, PlannerTrace]:
        initial_base = self._base_policy(state) if state.legal_actions else None
        admission = planning_admission(state, self._config.planning_ticks, initial_base)
        if admission.status != "PLAN":
            chosen = initial_base or ActionView("STOP::::", "STOP")
            return chosen, PlannerTrace(state.history_hash, tuple(a.identifier for a in state.ordered_actions()), chosen.identifier, False, self._config.planning_ticks, 0, {}, {}, self._config.bias_margin, self._config.planning_ticks, chosen.identifier, admission.status, 0, state.remaining_ticks, False)
        transition = consume_planning_time(state, self._config.planning_ticks)
        if not transition.admitted:
            return initial_base, PlannerTrace(state.history_hash, tuple(a.identifier for a in state.ordered_actions()), initial_base.identifier, False, self._config.planning_ticks, 0, {}, {}, self._config.bias_margin, self._config.planning_ticks, initial_base.identifier, "INSUFFICIENT_REMAINING_TIME", 0, state.remaining_ticks, False)
        post = transition.post_state
        base = self._base_policy(post) if post.legal_actions else ActionView("STOP::::", "STOP")
        actions = post.ordered_actions()
        if not actions: actions = (base,)
        if base not in actions: raise ValueError("recomputed base action must be legal after planning")
        means: dict[ActionView,float] = {}; lcbs: dict[ActionView,float] = {}
        for action in actions:
            if action == base: continue
            # IC1 may provide an algebraically identical sufficient-statistic
            # path for repeated deterministic continuation trajectories.  The
            # legacy tuple path remains the frozen reference behaviour.
            summarize = getattr(self._model, "paired_summary", None)
            if summarize is not None:
                mean, sample_sd, count = summarize(post, action, base, self._config.posterior_worlds, self._config.trajectories)
                means[action] = mean
                lcbs[action] = mean if count == 1 or sample_sd == 0.0 else mean - 1.96 * sample_sd / count ** 0.5
            else:
                values, base_values = self._model.paired_returns(post, action, base, self._config.posterior_worlds, self._config.trajectories)
                estimate = paired_advantage(values, base_values)
                means[action], lcbs[action] = estimate.mean, paired_lcb_95(estimate)
        score = means if self._config.mode in {"UNGATED", "POINT"} else lcbs
        threshold = self._config.bias_margin + self._config.planning_ticks
        choice = select_with_fallback(base, score, threshold, self._config.mode)
        return choice.selected, PlannerTrace(state.history_hash, tuple(a.identifier for a in actions), base.identifier, True, self._config.planning_ticks, self._config.posterior_worlds * self._config.trajectories, {a.identifier:v for a,v in means.items()}, {a.identifier:v for a,v in lcbs.items()}, self._config.bias_margin, self._config.planning_ticks, choice.selected.identifier, choice.fallback_reason, self._config.planning_ticks, post.remaining_ticks, choice.selected in actions)
