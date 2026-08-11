from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from .action import Action
from .fixed_ratio import FixedPolicyController
from .myopic_controller import MyopicVPSController
from .smdp_oracle import (
    ConditionedActionValues,
    conditioned_action_values,
    evaluator_state_hash,
    legal_binary_actions,
    verify_cost_upper,
)


def _estimator_mean(estimator: Any) -> float:
    if hasattr(estimator, "mean"):
        return float(estimator.mean)
    observed = getattr(estimator, "observed", ())
    fallback = getattr(estimator, "fallback_samples", ())
    source = observed or fallback
    return float(np.mean(source)) if source else float("inf")


def _unit_position_fraction(env: Any, unit_id: int | None) -> float:
    if unit_id is None:
        return 0.0
    rows = env.units
    match = rows[rows.unit_id.astype(int) == int(unit_id)]
    if match.empty:
        return 0.0
    start = float(rows.start_time.min())
    end = float(rows.end_time.max())
    center = 0.5 * (float(match.iloc[0].start_time) + float(match.iloc[0].end_time))
    return (center - start) / max(end - start, 1e-12)


def public_v1_features(env: Any) -> dict[str, Any]:
    """Causal PUBLIC_V1 feature map; evaluator outcomes are deliberately absent."""
    v0 = env.public_state()
    remaining = float(v0["remaining_budget_sec"])
    scan_upper = float(v0["estimated_scan_cost_sec"])
    verify_upper = verify_cost_upper(env, v0)
    scan_mean = _estimator_mean(env.scan_estimator)
    verify_mean = _estimator_mean(env.confirm_estimator)
    rows = sorted(
        env.frontier.rows(),
        key=lambda row: (-row.score, row.unit_id, row.track_id, row.candidate_id),
    )
    scores = np.asarray([float(row.score) for row in rows], dtype=float)
    ages = np.asarray([float(env.elapsed - row.created_elapsed_sec) for row in rows], dtype=float)
    padded_scores = scores.tolist()[:10] + [0.0] * max(0, 10 - len(scores))
    padded_ages = ages.tolist()[:10] + [0.0] * max(0, 10 - len(ages))
    positive_scores = np.maximum(scores, 0.0)
    if positive_scores.size and positive_scores.sum() > 0:
        probabilities = positive_scores / positive_scores.sum()
        entropy = float(-(probabilities * np.log(np.maximum(probabilities, 1e-12))).sum())
    else:
        entropy = 0.0
    confirmed_units = [
        int(row["unit_id"])
        for row in env.ledger
        if row["action"] == "CONFIRM" and int(row.get("new_distinct_utility", 0)) > 0
    ]
    top = rows[0] if rows else None
    top_position = _unit_position_fraction(env, top.unit_id if top else None)
    confirmed_positions = [_unit_position_fraction(env, unit) for unit in confirmed_units]
    nearest_confirmed = min((abs(top_position - pos) for pos in confirmed_positions), default=1.0)
    recent_scans = [row for row in env.ledger if row["action"] == "SCAN"][-3:]
    serviceable_yields = []
    for row in recent_scans:
        slots = int(max(0.0, float(row.get("remaining_budget", 0.0))) // verify_upper) if math.isfinite(verify_upper) else 0
        serviceable_yields.append(min(int(row.get("new_candidate_clusters", 0)), slots))
    return {
        **v0,
        "public_state_version": "PUBLIC_V1",
        "total_budget_sec": float(env.budget_sec),
        "remaining_budget_fraction": remaining / max(float(env.budget_sec), 1e-12),
        "scan_cost_mean": scan_mean,
        "scan_cost_upper": scan_upper,
        "verify_cost_mean": verify_mean,
        "verify_cost_upper": verify_upper,
        "estimated_remaining_scan_slots": int(remaining // scan_upper) if math.isfinite(scan_upper) and scan_upper > 0 else 0,
        "estimated_remaining_verify_slots": int(remaining // verify_upper) if math.isfinite(verify_upper) and verify_upper > 0 else 0,
        "scan_then_verify_slack": remaining - scan_upper - verify_upper,
        "largest_unscanned_gap": float(v0["maximum_unobserved_gap_sec"]),
        "frontier_top10_scores": padded_scores,
        "frontier_top10_ages": padded_ages,
        "top1_top2_margin": float(scores[0] - scores[1]) if len(scores) >= 2 else float(scores[0]) if len(scores) else 0.0,
        "frontier_score_mean": float(scores.mean()) if len(scores) else 0.0,
        "frontier_score_std": float(scores.std()) if len(scores) else 0.0,
        "frontier_score_entropy": entropy,
        "frontier_replacement_margin": float(scores[-1]) if len(scores) == 10 else 0.0,
        "recent_scan_candidate_yield": float(v0["recent_scan_novel_yield"]),
        "recent_scan_serviceable_yield": float(np.mean(serviceable_yields)) if serviceable_yields else 0.0,
        "recent_verify_positive_rate": float(v0["recent_confirm_success_rate"]),
        "recent_verify_new_distinct_rate": float(v0["recent_confirm_new_utility_rate"]),
        "top_candidate_position_fraction": top_position,
        "distance_to_nearest_already_confirmed_event": nearest_confirmed,
    }


def _ratio_action(env: Any, target: float, scan_time: float, verify_time: float) -> Action:
    legal = legal_binary_actions(env)
    rho = scan_time / max(scan_time + verify_time, 1e-12)
    desired = Action.SCAN if scan_time + verify_time == 0 or rho < target else Action.CONFIRM
    return desired if desired in legal else legal[0]


@dataclass
class BehaviorPolicy:
    name: str
    seed: int = 0
    scan_time: float = 0.0
    verify_time: float = 0.0
    step_index: int = 0
    _controller: Any = field(default=None, init=False, repr=False)

    def reset(self, env: Any) -> None:
        self.scan_time = self.verify_time = 0.0
        self.step_index = 0
        if self.name == "MYOPIC_VPS":
            self._controller = MyopicVPSController()
            self._controller.reset(env.budget_sec, env.public_state())
        else:
            self._controller = None
        self._rng = random.Random(self.seed)

    def choose(self, env: Any) -> Action | None:
        legal = legal_binary_actions(env)
        if not legal:
            return None
        if self.name == "SCAN_FIRST":
            desired = Action.SCAN
        elif self.name in {"VERIFY_FIRST", "FRONTIER_RULE"}:
            desired = Action.CONFIRM
        elif self.name == "ALTERNATING":
            desired = Action.SCAN if self.step_index % 2 == 0 else Action.CONFIRM
        elif self.name == "RANDOM_LEGAL":
            return self._rng.choice(legal)
        elif self.name == "RATIO_75_25":
            return _ratio_action(env, 0.75, self.scan_time, self.verify_time)
        elif self.name == "RATIO_50_50":
            return _ratio_action(env, 0.50, self.scan_time, self.verify_time)
        elif self.name == "R4_RATIO_25_75":
            return _ratio_action(env, 0.25, self.scan_time, self.verify_time)
        elif self.name == "MYOPIC_VPS":
            desired = Action(self._controller.choose_action(env.public_state())["action"])
        else:
            raise ValueError(f"unknown behavior policy {self.name}")
        return desired if desired in legal else legal[0]

    def observe(self, result: Any) -> None:
        self.step_index += 1
        if result.action is Action.SCAN:
            self.scan_time += result.actual_cost_sec
        elif result.action is Action.CONFIRM:
            self.verify_time += result.actual_cost_sec
        if self._controller is not None:
            self._controller.observe(result)


@dataclass
class CollectedState:
    state_hash: str
    video_id: str
    query_id: str
    budget_sec: float
    behavior_policy: str
    behavior_seed: int
    action_prefix: tuple[str, ...]
    environment_factory: Any = field(repr=False)
    behavior_policies: set[str] = field(default_factory=set)
    behavior_seeds: set[int] = field(default_factory=set)

    def materialize(self) -> Any:
        env = self.environment_factory(f"{self.video_id}_{self.query_id}", self.budget_sec)
        for name in self.action_prefix:
            result = env.step(Action(name))
            if not result.completed:
                raise RuntimeError(f"failed to replay collected prefix at {name}")
        actual_hash = evaluator_state_hash(env)
        if actual_hash != self.state_hash:
            raise RuntimeError(f"collected state replay hash mismatch: {actual_hash} != {self.state_hash}")
        return env


def collect_behavior_states(
    environment_factory: Any,
    *,
    tasks: Iterable[str],
    budgets: Iterable[float],
    policies: Iterable[BehaviorPolicy],
    safety_failures: list[dict[str, Any]] | None = None,
) -> dict[str, CollectedState]:
    states: dict[str, CollectedState] = {}
    for task in tasks:
        for budget in budgets:
            for policy_template in policies:
                policy = BehaviorPolicy(policy_template.name, policy_template.seed)
                env = environment_factory(task, float(budget))
                policy.reset(env)
                while True:
                    legal = legal_binary_actions(env)
                    if len(legal) == 2:
                        state_hash = evaluator_state_hash(env)
                        if state_hash not in states:
                            states[state_hash] = CollectedState(
                                state_hash=state_hash,
                                video_id=env.video_id,
                                query_id=env.query_id,
                                budget_sec=float(budget),
                                behavior_policy=policy.name,
                                behavior_seed=policy.seed,
                                action_prefix=tuple(row["action"] for row in env.ledger),
                                environment_factory=environment_factory,
                            )
                        states[state_hash].behavior_policies.add(policy.name)
                        states[state_hash].behavior_seeds.add(policy.seed)
                    action = policy.choose(env)
                    if action is None:
                        break
                    result = env.step(action)
                    if not result.completed or env.elapsed > env.budget_sec or (
                        env.ledger and env.ledger[-1].get("deadline_overrun", False)
                    ):
                        if safety_failures is not None:
                            safety_failures.append({
                                "task_id": task,
                                "budget_sec": float(budget),
                                "behavior_policy": policy.name,
                                "behavior_seed": policy.seed,
                                "action": action.value,
                                "completed": bool(result.completed),
                                "elapsed_sec": float(env.elapsed),
                                "deadline_overrun": bool(
                                    env.ledger and env.ledger[-1].get("deadline_overrun", False)
                                ),
                            })
                        break
                    policy.observe(result)
    return states


def labeled_state_row(state: CollectedState, env: Any, values: ConditionedActionValues) -> dict[str, Any]:
    return {
        "state_hash": state.state_hash,
        "video_id": state.video_id,
        "query_id": state.query_id,
        "budget_sec": state.budget_sec,
        "behavior_policy": state.behavior_policy,
        "behavior_seed": state.behavior_seed,
        "behavior_policies": sorted(state.behavior_policies),
        "behavior_seeds": sorted(state.behavior_seeds),
        **public_v1_features(env),
        "q_scan_final_events": values.scan.final_distinct_events,
        "q_verify_final_events": values.verify.final_distinct_events,
        "delta_final_events": values.delta_final_events,
        "q_scan_anytime": values.scan.anytime_auc,
        "q_verify_anytime": values.verify.anytime_auc,
        "delta_anytime": values.delta_anytime,
        "oracle_action": values.oracle_action,
        "label_class": values.label_class,
        "label_stable": values.label_stable,
        "oracle_exact": values.oracle_exact,
        "beam_width": values.beam_width,
        "beam_widths_checked": list(values.widths_checked),
        "scan_expanded_states": values.scan.expanded_states,
        "verify_expanded_states": values.verify.expanded_states,
        "scan_pruned_states": values.scan.pruned_states,
        "verify_pruned_states": values.verify.pruned_states,
        "scan_invalid_transitions": values.scan.invalid_transitions,
        "verify_invalid_transitions": values.verify.invalid_transitions,
        "confirm_cost_imputed_fraction": len(getattr(env, "confirm_cost_imputed_units", ())) / max(len(env.confirm_costs), 1),
    }
