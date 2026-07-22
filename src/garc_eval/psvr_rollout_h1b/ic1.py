"""IC1 full-horizon execution and compact deterministic-evidence primitives.

The approximate path still consists solely of ``ApproximatePlanner`` plus a
visible-state paired model.  Exact diagnostics are calculated later, in this
module's executor, after an action was selected.
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from math import sqrt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from garc_eval.psvr_rollout_toy.r2 import (ActionR2, CONFIRM_SUPPORT_TICKS,
    ExactPosterior, R2Environment, SCAN_SUPPORT_TICKS, ShieldedPi0R2,
    finite_world_library, replay)
from .approximate_rollout import ApproximatePlanner, PlannerConfig
from .advantage import paired_advantage
from .a4 import A4PlannerKernel
from .exact_reference import ExactReferenceEvaluator
from .posterior_sampling import fixed_posterior_indices
from .types import ActionView, VisibleDecisionState
from .uncertainty import paired_lcb_95

IDENTITY_FIELDS = (
    "development_episode_id", "configuration_id", "method_id", "posterior_budget_id",
    "trajectory_budget_id", "error_target", "error_form", "error_magnitude",
    "error_direction", "planning_cost_id", "fallback_variant", "attempt_ordinal",
    "canonical_spec_hash", "implementation_hash", "development_universe_hash",
)


class ContinuationReturnCache:
    """Bounded content-addressed cache for exact B1-continuation returns.

    The cache is an execution-only optimization.  A key binds the complete
    visible history, world, action, and continuation implementation; hits and
    evictions cannot affect any returned value or any policy decision.
    """
    def __init__(self, capacity: int = 50_000) -> None:
        if capacity < 1:
            raise ValueError("cache capacity must be positive")
        self.capacity = capacity
        self._values: OrderedDict[tuple[object, ...], float] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: tuple[object, ...]) -> float | None:
        value = self._values.get(key)
        if value is None:
            self.misses += 1
            return None
        self._values.move_to_end(key)
        self.hits += 1
        return value

    def put(self, key: tuple[object, ...], value: float) -> float:
        self._values[key] = value
        self._values.move_to_end(key)
        if len(self._values) > self.capacity:
            self._values.popitem(last=False)
            self.evictions += 1
        return value

    def snapshot(self) -> dict[str, int]:
        return {"capacity": self.capacity, "entries": len(self._values), "hits": self.hits,
                "misses": self.misses, "evictions": self.evictions}


def canonical_identity(identity: dict) -> dict:
    missing = [field for field in IDENTITY_FIELDS if field not in identity]
    if missing:
        raise ValueError(f"missing-scientific-identity-fields:{','.join(missing)}")
    if identity["error_form"] not in {"independent_variance", "systematic_optimism", "systematic_pessimism", "state_dependent_calibration"}:
        raise ValueError("unknown-error-form")
    if float(identity["error_magnitude"]) not in {0.0, 0.05, 0.1, 0.2}:
        raise ValueError("unknown-error-magnitude")
    for field in ("canonical_spec_hash", "implementation_hash", "development_universe_hash"):
        value = identity[field]
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"invalid-{field}")
    return {field: identity[field] for field in IDENTITY_FIELDS}


def identity_hash(identity: dict) -> str:
    return hashlib.sha256(json.dumps(canonical_identity(identity), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def visible(env: R2Environment) -> VisibleDecisionState:
    state = env.visible_state()
    def minimum_remaining_ticks(action: ActionR2) -> int:
        if action.kind == "SCAN":
            return SCAN_SUPPORT_TICKS + CONFIRM_SUPPORT_TICKS
        if action.kind == "CONFIRM":
            return CONFIRM_SUPPORT_TICKS
        return 0
    actions = tuple(ActionView(a.identifier, a.kind, region_id=a.region_id,
                              hypothesis_id=a.hypothesis_id, witness_id=a.witness_id,
                              minimum_remaining_ticks=minimum_remaining_ticks(a))
                    for a in env.safe_actions())
    frontier = tuple(ActionView(f"CONFIRM::{candidate.hypothesis_id}:{candidate.witness_id}", "CONFIRM", candidate.score_bin, candidate.hypothesis_id, candidate.witness_id) for candidate in state.frontier)
    return VisibleDecisionState(env.history.digest, len(env.history.actions), state.remaining_ticks, actions, frontier)


def actual(action: ActionView, env: R2Environment) -> ActionR2:
    return next(candidate for candidate in env.safe_actions() if candidate.identifier == action.identifier)


def base_policy(state: VisibleDecisionState) -> ActionView:
    confirms = [action for action in state.ordered_actions() if action.kind == "CONFIRM"]
    if confirms:
        return confirms[0]
    scans = [action for action in state.ordered_actions() if action.kind == "SCAN"]
    return scans[0] if scans else next((action for action in state.ordered_actions() if action.kind == "STOP"), ActionView("STOP:::", "STOP"))


class _PosteriorSupport:
    def __init__(self, history):
        self._support = ExactPosterior(finite_world_library()).supported(history)
    def support_size(self, state: VisibleDecisionState) -> int:
        return len(self._support)


class _CachedSupportSize:
    """Minimal sampler interface for fixed_posterior_indices after support build."""
    def __init__(self, size: int):
        self._size = size

    def support_size(self, state: VisibleDecisionState) -> int:
        return self._size


class IC1PairedModel:
    """Deterministic prefix-sampled, error-perturbed visible-history model.

    Values are generated from keys on demand; neither the execution path nor
    its evidence representation needs to retain a duplicated JSON scalar per
    draw.  The model has no exact-evaluator object.
    """
    def __init__(self, history, seed: int, identity: dict, accrued_utility: float = 0.0,
                 continuation_cache: ContinuationReturnCache | None = None,
                 history_completion_ticks: tuple[int, ...] | None = None):
        self.history, self.seed, self.identity = history, seed, canonical_identity(identity)
        # Visible history intentionally excludes planning time.  The executor
        # passes the already accrued net D1 rewards explicitly so simulations
        # can attach future commits to the actual SMDP clock.
        self._accrued_utility = float(accrued_utility)
        self._history_completion_ticks = history_completion_ticks
        self._support = _PosteriorSupport(history)._support
        self._sampler = _CachedSupportSize(len(self._support))
        self._continuation_cache = continuation_cache
        self._cache: dict[tuple[str, str, int, int], tuple[tuple[float, ...], tuple[float, ...]]] = {}
        # This is evidence, not an optimization cache.  Every paired return
        # used for a planner decision retains its canonical A4 transitions so
        # a verifier can reproduce the paired differences and LCB without
        # asking production code to simulate a replacement trace.
        self._record_cache: dict[tuple[object, ...], tuple[dict, ...]] = {}
        self._pair_evidence: dict[tuple[str, str, int, int], tuple[dict, ...]] = {}

    def _continuation_key(self, root_index: int, world, state: VisibleDecisionState,
                          action: ActionView, trajectory: int) -> tuple[object, ...]:
        timing_hash = hashlib.sha256(json.dumps(self._history_completion_ticks, separators=(",", ":")).encode()).hexdigest()
        return ("H1B_A4_CONTINUATION_V1", identity_hash(self.identity), self.history.digest, timing_hash,
                state.remaining_ticks, root_index, world.world_id, action.identifier, trajectory,
                "B1_SHIELDED_PI0")

    def _incremental_return(self, root_index: int, world, state: VisibleDecisionState,
                            action: ActionView, trajectory: int) -> float:
        """Net D1 reward from this post-planning state onward.

        The cache deliberately stores only this incremental quantity.  Past
        reward is common to every candidate action and may differ between
        executor calls with the same visible history, whereas remaining time
        is decision-relevant and therefore bound into the cache key.
        """
        key = self._continuation_key(root_index, world, state, action, trajectory)
        if self._continuation_cache is not None:
            cached = self._continuation_cache.get(key)
            if cached is not None and key in self._record_cache:
                return cached
        kernel = A4PlannerKernel(world, self.history, state, self.identity, self.seed,
                                 root_index, trajectory, self._history_completion_ticks)
        incremental, records = kernel.rollout(action)
        self._record_cache[key] = records
        if self._continuation_cache is not None:
            # A cache hit from a previous model instance has no records in this
            # instance.  Re-execute solely to recover the required evidence,
            # then fail closed if the cached scalar disagrees.
            if cached is not None and cached != incremental:
                raise ValueError("a4-continuation-cache-evidence-mismatch")
            return self._continuation_cache.put(key, incremental) if cached is None else cached
        return incremental

    def _return(self, root_index: int, world, state: VisibleDecisionState, action: ActionView,
                trajectory: int) -> float:
        return self._accrued_utility + self._incremental_return(root_index, world, state, action, trajectory)

    def paired_returns(self, state: VisibleDecisionState, action: ActionView, base: ActionView, worlds: int, trajectories: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
        key = (action.identifier, base.identifier, worlds, trajectories)
        if key in self._cache:
            return self._cache[key]
        # A4 freezes posterior roots at the decision, not candidate-action,
        # level.  Candidate branches differ only after they share these roots.
        pair = "H1B_A4_SHARED_POSTERIOR_ROOTS"
        # One maximal frozen root-world stream is shared across every budget;
        # smaller budgets consume its literal prefix.  Error transforms remain
        # identity-specific and are never cached across error configurations.
        indices = fixed_posterior_indices(state, self._sampler, self.seed, pair, (256, 256), worlds)
        action_values, base_values, samples = [], [], []
        for world_index in indices:
            world = self._support[world_index]
            for trajectory in range(trajectories):
                value = self._return(world_index, world, state, action, trajectory)
                baseline = self._return(world_index, world, state, base, trajectory)
                action_values.append(value)
                base_values.append(baseline)
                action_key = self._continuation_key(world_index, world, state, action, trajectory)
                base_key = self._continuation_key(world_index, world, state, base, trajectory)
                samples.append({"posterior_root_index": world_index, "posterior_world_id": world.world_id,
                                "trajectory_index": trajectory, "action_return": value,
                                "base_return": baseline, "paired_difference": value - baseline,
                                "action_transitions": list(self._record_cache[action_key]),
                                "base_transitions": list(self._record_cache[base_key])})
        answer = (tuple(action_values), tuple(base_values))
        self._cache[key] = answer
        self._pair_evidence[key] = tuple(samples)
        return answer

    def lossless_evidence(self) -> dict:
        """Canonical compact record set for the samples used at this decision."""
        pairs = []
        for (action, base, worlds, trajectories), samples in sorted(self._pair_evidence.items()):
            differences = [sample["paired_difference"] for sample in samples]
            count = len(differences)
            mean = sum(differences) / count
            variance = 0.0 if count == 1 else sum((item - mean) ** 2 for item in differences) / (count - 1)
            lcb = mean if count == 1 or variance == 0.0 else mean - 1.96 * sqrt(variance) / count ** .5
            pairs.append({"action": action, "base_action": base, "posterior_worlds": worlds,
                          "trajectories": trajectories, "samples": list(samples),
                          "paired_mean": mean, "paired_variance": variance, "paired_lcb_95": lcb})
        return {"schema": "H1B_A4_LOSSLESS_PAIRED_EVIDENCE_V1", "pairs": pairs}

    def paired_summary(self, state: VisibleDecisionState, action: ActionView, base: ActionView, worlds: int, trajectories: int) -> tuple[float, float, int]:
        """Exact mean/SD of the same ordered sample array without storing it.

        For a root world the deterministic continuation difference is constant;
        only the frozen error transform varies by trajectory.  Expanding the
        Cartesian product would be a lossless-but-needlessly-large temporary.
        """
        values, base_values = self.paired_returns(state, action, base, worlds, trajectories)
        differences = tuple(value - baseline for value, baseline in zip(values, base_values))
        count = len(differences)
        mean = sum(differences) / count
        variance = 0.0 if count == 1 else sum((value - mean) ** 2 for value in differences) / (count - 1)
        return mean, sqrt(variance), count

    def replay_commitment(self, state: VisibleDecisionState, worlds: int, trajectories: int) -> str:
        payload = {"root_world_key": str(self.seed), "posterior_root_stream":"H1B_A4_SHARED_POSTERIOR_ROOTS", "posterior_support": [world.world_id for world in self._support], "visible_history_hash": state.history_hash, "history_completion_ticks": self._history_completion_ticks, "posterior_sample_count": worlds, "trajectory_count": trajectories, "budget_prefix_schedule": [256, 256], "rng_namespace_key": "H1B_A4", "replay_implementation": "IC1PairedModel-A4-v1", "identity": canonical_identity(self.identity)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compact_commitment(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass
class EpisodeResult:
    trace: dict
    evaluator: list[dict]


def execute_full_horizon(
    identity: dict,
    seed: int,
    evaluator: ExactReferenceEvaluator | None = None,
    continuation_cache: ContinuationReturnCache | None = None,
) -> EpisodeResult:
    """Execute a policy from initial state until it selects STOP or the deadline."""
    identity = canonical_identity(identity)
    world = finite_world_library()[abs(seed) % len(finite_world_library())]
    env, evaluator = R2Environment(world), (evaluator or ExactReferenceEvaluator())
    decisions: list[dict] = []
    history_completion_ticks: list[int] = []
    net_utility = 0.0
    utility_timeline = [{"tick": 0, "utility": 0}]
    exact_sidecar: list[dict] = []
    while env.visible_state().remaining_ticks > 0 and not env.visible_state().stopped:
        pre = visible(env)
        method = identity["method_id"]
        if method == "B1_SHIELDED_PI0":
            selected, planner_trace = base_policy(pre), {"visible_history_hash": pre.history_hash, "planning_admitted": False, "planning_time": 0, "selected_action": base_policy(pre).identifier, "base_action": base_policy(pre).identifier, "paired_advantages": {}, "lcbs": {}, "fallback_reason": "BASELINE", "post_planning_remaining_time": pre.remaining_ticks, "post_planning_feasible": True, "samples_used": 0}
        else:
            worlds, trajectories = int(identity["posterior_budget_id"].split("-")[1]), int(identity["trajectory_budget_id"].split("-")[1])
            modes = {"APPROX_NO_FALLBACK": "UNGATED", "APPROX_POINT_ESTIMATE_FALLBACK": "POINT", "APPROX_LCB_FALLBACK": "LCB", "APPROX_PLANNING_ADMISSION_LCB": "LCB"}
            model = IC1PairedModel(env.history, seed, identity, net_utility, continuation_cache,
                                   tuple(history_completion_ticks))
            selected, planner = ApproximatePlanner(base_policy, model, PlannerConfig(worlds, trajectories, int(identity["planning_cost_id"].split("-")[1]), modes[method], "JOINT_CORNER" if identity["error_target"] == "JOINT_CORNER" else "STANDARD")).decide(pre)
            planner_trace = planner.to_dict()
            planner_trace["replay_commitment"] = model.replay_commitment(pre, worlds, trajectories)
            planner_trace["a4_lossless_evidence"] = model.lossless_evidence()
            # Planning time is a real SMDP cost.  The planner's post-planning
            # state is used for selection; the environment must consume it too.
            if planner.planning_admitted:
                env._elapsed += planner.planning_time
        # Evidence is a JSON contract.  Normalize tuples now so independent
        # replay compares semantic records rather than Python container types.
        planner_trace = json.loads(json.dumps(planner_trace, sort_keys=True))
        # Preserve the pre-action evaluator inputs.  The sidecar itself is
        # calculated only after the action record becomes durable below.
        evaluator_history = env.history
        post_for_exact = visible(env)
        accrued_before_action = net_utility
        observation = env.execute(actual(selected, env))
        decisions.append({"decision_index": pre.decision_index, "visible_history_hash": pre.history_hash, "action": selected.identifier, "observation": observation.outcome, "duration": observation.duration_ticks, "planner": planner_trace, "committed_token": observation.committed_token})
        if observation.outcome == "NEW_COMMIT":
            net_utility += env.history.horizon_ticks - env.visible_state().elapsed_ticks
        utility_timeline.append({"tick": env.visible_state().elapsed_ticks, "utility": net_utility})
        history_completion_ticks.append(env.visible_state().elapsed_ticks)
        exact = evaluator.reference_for_history(evaluator_history, post_for_exact,
                                                accrued_utility=accrued_before_action)
        exact_sidecar.append(json.loads(json.dumps({"visible_history_hash": exact.visible_history_hash, "safe_actions": exact.safe_actions, "remaining_ticks": exact.remaining_ticks, "exact_action": exact.exact_action.identifier, "exact_q": exact.action_values, "exact_kernel_hash": exact.exact_kernel_hash, "approximate_selected_action": selected.identifier}, sort_keys=True)))
        if selected.kind == "STOP":
            break
    payload = {"identity": identity, "identity_hash": identity_hash(identity), "episode_world_commitment": hashlib.sha256(world.world_id.encode()).hexdigest(), "visible_history_hashes": [row["visible_history_hash"] for row in decisions], "action_sequence": [row["action"] for row in decisions], "planning_admission_sequence": [bool(row["planner"]["planning_admitted"]) for row in decisions], "planning_time": [row["planner"]["planning_time"] for row in decisions], "selected_fallback_actions": [{"selected": row["action"], "fallback_reason": row["planner"].get("fallback_reason")} for row in decisions], "committed_event_timeline": [{"tick": point["tick"], "utility": point["utility"]} for point in utility_timeline], "utility_timeline": utility_timeline, "completion_status": "STOPPED" if env.visible_state().stopped else "DEADLINE", "stop_time": env.visible_state().elapsed_ticks, "decisions": decisions, "deterministic_replay_key": {"episode_seed": seed, "world_index": abs(seed) % len(finite_world_library()), "implementation": "IC1PairedModel-v1"}}
    payload["raw_evidence_commitment"] = compact_commitment(payload)
    return EpisodeResult(payload, exact_sidecar)
