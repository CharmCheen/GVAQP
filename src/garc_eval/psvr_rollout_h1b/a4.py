"""A4 result-blind generative transition kernel for the approximate planner.

The frozen R2 environment remains evaluator-only truth.  This module executes
the *planner's sampled root world* through A4's error-perturbed kernels and
never receives an actual execution world's future state.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from math import ceil
from typing import Iterable

from garc_eval.psvr_rollout_toy.r2 import (
    CONFIRM_SUPPORT_TICKS, HORIZON_TICKS, SCAN_SUPPORT_TICKS, Candidate,
    VisibleHistory, World,
)
from .crn import error_key, sign
from .types import ActionView, VisibleDecisionState

A4_FAMILIES = ("candidate_yield", "grouping", "confirm_outcome", "novelty", "materialization", "duration")
GROUPING_CATEGORIES = ("CORRECT", "UNDER_MERGE", "OVER_MERGE")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def a4_key(episode_public_id: object, decision_index: int, posterior_sample_index: int,
           branch_transition_index: int, variable_family: str, entity_stable_id: str) -> tuple[object, ...]:
    if variable_family not in A4_FAMILIES:
        raise ValueError("unknown-a4-variable-family")
    return ("H1B_A4", episode_public_id, decision_index, posterior_sample_index,
            branch_transition_index, variable_family, entity_stable_id)


def keyed_uniform(*parts: object) -> float:
    """A4's unique SHA-256 keyed uniform: first eight bytes / 2**64."""
    # A pipe delimiter is not injective for arbitrary stable IDs.  Canonical
    # JSON preserves types and boundaries while retaining the frozen SHA-256
    # primitive.
    digest = hashlib.sha256(_canonical_json(list(parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def stable_hypothesis_id(episode_public_id: object, decision_index: int, region_id: str,
                         witness_id: str) -> str:
    key = f"H1B_A4_HYPOTHESIS|{episode_public_id}|{decision_index}|{region_id}|{witness_id}|hypothesis-create"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _a4_sign(seed: object, decision_index: int, mechanism: str, form: str,
             trajectory_index: int, target_identity: str, draw_index: int,
             target_score_bin: int | None, frontier_max_score_bin: int | None,
             joint: bool) -> int:
    target = "JOINT" if joint else mechanism
    if form == "systematic_optimism":
        return 1
    if form == "systematic_pessimism":
        return -1
    if form == "state_dependent_calibration":
        # A4 makes JOINT's common sign unique rather than target-specific.
        if joint or target_score_bin is None or frontier_max_score_bin is None:
            return -1
        return 1 if target_score_bin == frontier_max_score_bin else -1
    if form != "independent_variance":
        raise ValueError("unknown-error-form")
    if joint:
        # A4 resolves A2's target-specific extension for the explicitly
        # common JOINT sign: all mechanisms use one canonical JOINT variable.
        target_identity, draw_index = "JOINT", 0
    return sign(*error_key(seed, decision_index, target, form, trajectory_index,
                           target_identity, draw_index))


def perturbed_binary_probability(p0: float, *, seed: object, decision_index: int,
                                 mechanism: str, form: str, magnitude: float,
                                 trajectory_index: int, target_identity: str,
                                 draw_index: int, target_score_bin: int | None,
                                 frontier_max_score_bin: int | None, joint: bool,
                                 applies: bool) -> float:
    if not 0.0 <= p0 <= 1.0:
        raise ValueError("invalid-a4-baseline-probability")
    if not applies:
        return p0
    direction = _a4_sign(seed, decision_index, mechanism, form, trajectory_index,
                         target_identity, draw_index, target_score_bin,
                         frontier_max_score_bin, joint)
    # A1 explicitly freezes this clipping support.
    return min(.99, max(.01, p0 + direction * magnitude))


def perturbed_duration(duration: int, maximum: int, *, seed: object, decision_index: int,
                       form: str, magnitude: float, trajectory_index: int,
                       target_identity: str, draw_index: int,
                       target_score_bin: int | None, frontier_max_score_bin: int | None,
                       joint: bool, applies: bool) -> int:
    if not applies:
        return duration
    direction = _a4_sign(seed, decision_index, "action_duration", form,
                         trajectory_index, target_identity, draw_index,
                         target_score_bin, frontier_max_score_bin, joint)
    return min(maximum, max(1, ceil(duration * (1 + direction * magnitude))))


def perturbed_grouping_distribution(*, seed: object, decision_index: int, form: str,
                                    magnitude: float, trajectory_index: int,
                                    target_identity: str, draw_index: int,
                                    target_score_bin: int | None,
                                    frontier_max_score_bin: int | None,
                                    joint: bool, applies: bool) -> tuple[float, float, float]:
    if not applies:
        return (1.0, 0.0, 0.0)
    direction = _a4_sign(seed, decision_index, "grouping_transition", form,
                         trajectory_index, target_identity, draw_index,
                         target_score_bin, frontier_max_score_bin, joint)
    values = [1.0 - magnitude, magnitude if direction < 0 else 0.0,
              magnitude if direction > 0 else 0.0]
    values = [max(0.0, value) for value in values]
    total = sum(values)
    return (1.0, 0.0, 0.0) if total == 0 else tuple(value / total for value in values)  # type: ignore[return-value]


def categorical_outcome(probabilities: Iterable[float], categories: Iterable[str], uniform: float) -> str:
    ordered_probabilities, ordered_categories = tuple(probabilities), tuple(categories)
    if len(ordered_probabilities) != len(ordered_categories) or not ordered_categories:
        raise ValueError("invalid-a4-categorical-kernel")
    if any(value < 0 for value in ordered_probabilities):
        raise ValueError("negative-a4-categorical-probability")
    cumulative = 0.0
    for probability, category in zip(ordered_probabilities, ordered_categories):
        cumulative += probability
        if uniform < cumulative:
            return category
    return ordered_categories[-1]


@dataclass(frozen=True)
class ModelWitness:
    candidate: Candidate
    region_id: str
    source_index: int
    model_hypothesis_id: str
    created_at: int
    latent_event_id: str

    @property
    def stable_id(self) -> str:
        return f"{self.region_id}|{self.candidate.hypothesis_id}|{self.candidate.witness_id}|{self.source_index}"


@dataclass
class ModelHypothesis:
    hypothesis_id: str
    created_at: int
    witness_ids: set[str] = field(default_factory=set)
    verified_witness_ids: set[str] = field(default_factory=set)
    resolved: bool = False
    suppressed: bool = False
    committed_event_reference: str | None = None

    def canonical(self) -> dict:
        return {"hypothesis_id": self.hypothesis_id, "created_at": self.created_at,
                "ordered_witness_ids": sorted(self.witness_ids),
                "verified_witness_ids": sorted(self.verified_witness_ids),
                "pending_witness_ids": sorted(self.witness_ids - self.verified_witness_ids),
                "resolved": self.resolved, "suppressed": self.suppressed,
                "committed_event_reference": self.committed_event_reference}


@dataclass
class A4BranchState:
    elapsed: int
    scanned: set[str] = field(default_factory=set)
    frontier: list[ModelWitness] = field(default_factory=list)
    hypotheses: dict[str, ModelHypothesis] = field(default_factory=dict)
    committed: set[str] = field(default_factory=set)
    stopped: bool = False

    def canonical(self) -> dict:
        return {
            "elapsed": self.elapsed,
            "scanned": sorted(self.scanned),
            "frontier": [
                {"witness_id": item.candidate.witness_id, "source_hypothesis_id": item.candidate.hypothesis_id,
                 "model_hypothesis_id": item.model_hypothesis_id, "region_id": item.region_id,
                 "created_at": item.created_at}
                for item in sorted(self.frontier, key=lambda item: (item.created_at, item.model_hypothesis_id, item.candidate.witness_id))
            ],
            "hypotheses": [item.canonical() for item in sorted(self.hypotheses.values(), key=lambda item: (item.created_at, item.hypothesis_id))],
            "committed": sorted(self.committed), "stopped": self.stopped,
        }


class A4PlannerKernel:
    """Planner-only A4 sampled-root transition executor."""
    def __init__(self, world: World, history: VisibleHistory, state: VisibleDecisionState,
                 identity: dict, seed: object, posterior_sample_index: int,
                 trajectory_index: int, history_completion_ticks: tuple[int, ...] | None = None) -> None:
        self.world, self.history, self.identity, self.seed = world, history, identity, seed
        self.episode_public_id = str(identity["development_episode_id"])
        self.posterior_sample_index, self.trajectory_index = posterior_sample_index, trajectory_index
        self.decision_index = state.decision_index
        self.action_ordinal = 0
        self.history_completion_ticks = history_completion_ticks
        if history_completion_ticks is not None and len(history_completion_ticks) != len(history.actions):
            raise ValueError("a4-history-completion-tick-count-mismatch")
        self._regions = {region.region_id: region for region in world.regions}
        observed_elapsed = sum(item.duration_ticks for item in history.observations)
        elapsed = HORIZON_TICKS - state.remaining_ticks
        if elapsed < observed_elapsed:
            raise ValueError("a4-state-precedes-visible-history")
        self.state = A4BranchState(elapsed=elapsed)
        self._hydrate_history()

    @property
    def joint(self) -> bool:
        return self.identity["error_target"] == "JOINT_CORNER"

    def _applies(self, target: str) -> bool:
        return self.joint or self.identity["error_target"] == target

    def _latent_event_id(self, region_id: str, source_index: int, candidate: Candidate) -> str:
        region = self._regions[region_id]
        token = region.event_tokens[source_index]
        return token if token is not None else f"NEGATIVE|{region_id}|{candidate.hypothesis_id}|{candidate.witness_id}"

    def _hydrate_history(self) -> None:
        observed_elapsed = 0
        for index, (action, observation) in enumerate(zip(self.history.actions, self.history.observations)):
            observed_elapsed += observation.duration_ticks
            created_at = (self.history_completion_ticks[index] if self.history_completion_ticks is not None
                          else observed_elapsed)
            if action.kind == "SCAN":
                assert action.region_id is not None
                self.state.scanned.add(action.region_id)
                for candidate in observation.emitted:
                    region = self._regions[action.region_id]
                    source_index = next(index for index, item in enumerate(region.candidates) if item == candidate)
                    self._add_witness(ModelWitness(candidate, action.region_id, source_index,
                                                   candidate.hypothesis_id, created_at,
                                                   self._latent_event_id(action.region_id, source_index, candidate)))
            elif action.kind == "CONFIRM":
                selected = next((item for item in self.state.frontier if item.candidate.witness_id == action.witness_id), None)
                if selected is not None:
                    self._resolve_hypothesis(selected.model_hypothesis_id, observation.committed_token)
                if observation.committed_token is not None:
                    self.state.committed.add(observation.committed_token)
            else:
                self.state.stopped = True

    def _frontier_max_score(self) -> int | None:
        return max((item.candidate.score_bin for item in self.state.frontier), default=None)

    def _add_witness(self, witness: ModelWitness) -> None:
        hypothesis = self.state.hypotheses.get(witness.model_hypothesis_id)
        if hypothesis is None:
            hypothesis = ModelHypothesis(witness.model_hypothesis_id, witness.created_at)
            self.state.hypotheses[witness.model_hypothesis_id] = hypothesis
        if hypothesis.resolved or hypothesis.suppressed:
            raise ValueError("a4-cannot-add-witness-to-inactive-hypothesis")
        hypothesis.witness_ids.add(witness.candidate.witness_id)
        self.state.frontier.append(witness)

    def _resolve_hypothesis(self, hypothesis_id: str, committed_event: str | None) -> None:
        hypothesis = self.state.hypotheses[hypothesis_id]
        hypothesis.resolved = True
        hypothesis.suppressed = True
        hypothesis.committed_event_reference = committed_event
        hypothesis.verified_witness_ids.update(hypothesis.witness_ids)
        self.state.frontier = [item for item in self.state.frontier if item.model_hypothesis_id != hypothesis_id]

    def _draw_key(self, family: str, entity_id: str, entity_ordinal: int) -> tuple[object, ...]:
        if entity_ordinal < 0:
            raise ValueError("negative-a4-entity-ordinal")
        # This index is a canonical schedule coordinate, not an incrementing
        # runtime counter.  Unrelated draws cannot renumber later variables.
        transition_index = self.action_ordinal * 10_000_000 + A4_FAMILIES.index(family) * 1_000_000 + entity_ordinal
        return a4_key(self.episode_public_id, self.decision_index, self.posterior_sample_index,
                      transition_index, family, entity_id)

    def _uniform(self, family: str, entity_id: str, entity_ordinal: int) -> float:
        return keyed_uniform(*self._draw_key(family, entity_id, entity_ordinal))

    def _binary(self, p0: float, mechanism: str, identity: str, draw_index: int,
                score: int | None = None, frontier_max_score: int | None = None) -> tuple[bool, bool, float, float, tuple[object, ...]]:
        probability = perturbed_binary_probability(
            p0, seed=self.seed, decision_index=self.decision_index, mechanism=mechanism,
            form=self.identity["error_form"], magnitude=float(self.identity["error_magnitude"]),
            trajectory_index=self.trajectory_index, target_identity=identity, draw_index=draw_index,
            target_score_bin=score, frontier_max_score_bin=self._frontier_max_score() if frontier_max_score is None else frontier_max_score, joint=self.joint,
            applies=self._applies(mechanism))
        family = {"scan_candidate_yield": "candidate_yield",
                                 "confirm_positive_probability": "confirm_outcome",
                                 "novelty_duplicate_probability": "novelty",
                                 "materialization_success": "materialization"}[mechanism]
        key = self._draw_key(family, identity, draw_index)
        uniform = keyed_uniform(*key)
        return uniform < probability, uniform < p0, probability, uniform, key

    def _sign_evidence(self, mechanism: str, target_identity: str, draw_index: int,
                       score: int | None, frontier_max_score: int | None) -> dict:
        """Return the A1/A2 sign commitment accompanying an A4 realization.

        This is deliberately evidence, rather than a second source of sign
        semantics: the verifier can derive the same key and sign without
        importing this module.
        """
        target = "JOINT" if self.joint else mechanism
        sign_target, sign_index = ("JOINT", 0) if self.joint else (target_identity, draw_index)
        key = error_key(self.seed, self.decision_index, target,
                        self.identity["error_form"], self.trajectory_index,
                        sign_target, sign_index)
        direction = _a4_sign(self.seed, self.decision_index, mechanism,
                             self.identity["error_form"], self.trajectory_index,
                             target_identity, draw_index, score,
                             frontier_max_score, self.joint)
        return {"a1_a2_sign_key": list(key), "a1_a2_sign": direction,
                "error_mechanism": mechanism, "error_target_identity": sign_target,
                "error_draw_index": sign_index, "target_score_bin": score,
                "frontier_max_score_bin": frontier_max_score}

    def _binary_draw(self, *, family: str, mechanism: str, p0: float,
                     target_identity: str, entity: str, draw_index: int,
                     score: int | None, frontier_max_score: int | None = None) -> dict:
        perturbed, baseline, probability, uniform, key = self._binary(
            p0, mechanism, target_identity, draw_index, score, frontier_max_score)
        return {"family": family, "entity": entity, "semantic_identity": target_identity,
                "draw_index": draw_index, "a4_key": list(key), "u": uniform,
                "p0": p0, "p_error": probability, "baseline_outcome": baseline,
                "perturbed_outcome": perturbed, "outcome": perturbed,
                **self._sign_evidence(mechanism, target_identity, draw_index, score,
                                      self._frontier_max_score() if frontier_max_score is None else frontier_max_score)}

    def _duration_draw(self, *, p0: int, maximum: int, action: ActionView,
                       draw_index: int, score: int | None) -> dict:
        identity = f"DURATION|{action.identifier}"
        frontier_max = self._frontier_max_score()
        perturbed = perturbed_duration(
            p0, maximum, seed=self.seed, decision_index=self.decision_index,
            form=self.identity["error_form"], magnitude=float(self.identity["error_magnitude"]),
            trajectory_index=self.trajectory_index, target_identity=identity,
            draw_index=draw_index, target_score_bin=score,
            frontier_max_score_bin=frontier_max, joint=self.joint,
            applies=self._applies("action_duration"))
        key = self._draw_key("duration", identity, draw_index)
        return {"family": "duration", "entity": identity, "semantic_identity": identity,
                "draw_index": draw_index, "a4_key": list(key), "u": None,
                "p0": p0, "p_error": perturbed, "baseline_outcome": p0,
                "perturbed_outcome": perturbed, "outcome": perturbed,
                "duration_transformation": {"support_maximum": maximum,
                    "rule": "ceil(duration*(1+sign*magnitude)), clamped to [1, maximum]"},
                **self._sign_evidence("action_duration", identity, draw_index, score, frontier_max)}

    def safe_actions(self) -> tuple[ActionView, ...]:
        if self.state.stopped:
            return (ActionView("STOP:::", "STOP"),)
        actions: list[ActionView] = []
        if self.state.elapsed + CONFIRM_SUPPORT_TICKS <= HORIZON_TICKS:
            actions.extend(ActionView(f"CONFIRM::{item.model_hypothesis_id}:{item.candidate.witness_id}", "CONFIRM",
                                      item.candidate.score_bin, item.model_hypothesis_id, item.candidate.witness_id,
                                      minimum_remaining_ticks=CONFIRM_SUPPORT_TICKS)
                           for item in sorted(self.state.frontier, key=lambda item: (item.model_hypothesis_id, item.candidate.witness_id)))
        next_region = next((region.region_id for region in self.world.regions if region.region_id not in self.state.scanned), None)
        if next_region is not None and self.state.elapsed + SCAN_SUPPORT_TICKS + CONFIRM_SUPPORT_TICKS <= HORIZON_TICKS:
            actions.append(ActionView(f"SCAN:{next_region}::", "SCAN", region_id=next_region,
                                      minimum_remaining_ticks=SCAN_SUPPORT_TICKS + CONFIRM_SUPPORT_TICKS))
        actions.append(ActionView("STOP:::", "STOP"))
        return tuple(actions)

    def pi0(self) -> ActionView:
        actions = self.safe_actions()
        confirms = sorted((item for item in actions if item.kind == "CONFIRM"), key=lambda item: (item.hypothesis_id or "", item.witness_id or ""))
        if confirms:
            return confirms[0]
        scans = sorted((item for item in actions if item.kind == "SCAN"), key=lambda item: item.region_id or "")
        return scans[0] if scans else ActionView("STOP:::", "STOP")

    def _transition_record(self, pre: dict, action: ActionView, draws: list[dict], outcome: str,
                           action_ordinal: int) -> dict:
        record = {"canonical_pre_state": pre, "pre_state": pre,
                  "canonical_action": action.identifier, "action": action.identifier,
                  "planning_decision_index": self.decision_index, "action_ordinal": action_ordinal,
                  "draws": draws, "outcome": outcome,
                  "post_state": self.state.canonical()}
        record["transition_hash"] = hashlib.sha256(_canonical_json(record).encode()).hexdigest()
        return record

    def execute(self, action: ActionView) -> tuple[str, bool, dict]:
        if action.identifier not in {candidate.identifier for candidate in self.safe_actions()}:
            raise ValueError("illegal-a4-model-action")
        pre, draws = self.state.canonical(), []
        transition_ordinal = self.action_ordinal
        pre_actions = tuple(sorted(self.safe_actions(), key=lambda item: item.identifier))
        action_rank = next(index for index, item in enumerate(pre_actions) if item.identifier == action.identifier)
        if action.kind == "STOP":
            self.state.stopped = True
            return "STOPPED", False, self._transition_record(pre, action, draws, "STOPPED", transition_ordinal)
        if action.kind == "SCAN":
            assert action.region_id is not None
            region = self._regions[action.region_id]
            duration_draw = self._duration_draw(p0=region.scan_ticks, maximum=SCAN_SUPPORT_TICKS,
                                                action=action, draw_index=action_rank, score=None)
            duration = duration_draw["perturbed_outcome"]
            self.state.elapsed += duration
            draws.append(duration_draw)
            ordered_candidates = tuple(sorted(enumerate(region.candidates), key=lambda item: (item[1].hypothesis_id, item[1].witness_id)))
            generated_max_score = max((candidate.score_bin for _, candidate in ordered_candidates), default=None)
            retained: list[tuple[int, int, Candidate]] = []
            for rank, (index, candidate) in enumerate(ordered_candidates):
                target = f"SCAN|{region.region_id}|{candidate.hypothesis_id}|{candidate.witness_id}"
                draw = self._binary_draw(family="candidate_yield", mechanism="scan_candidate_yield",
                                         p0=1.0, target_identity=target, entity=target, draw_index=rank,
                                         score=candidate.score_bin, frontier_max_score=generated_max_score)
                draws.append(draw)
                is_retained = bool(draw["perturbed_outcome"])
                if is_retained:
                    retained.append((rank, index, candidate))
            # A2 freezes grouping draws on same-source-hypothesis unordered
            # pairs. A4's formerly unspecified post-state maps each witness
            # to the first non-CORRECT incident pair outcome (pair rank order),
            # defaulting to CORRECT when it has no incident pair.
            pair_entries: list[tuple[str, int, int, Candidate, int, int, Candidate]] = []
            # A2 freezes a draw for *every generated* same-source-hypothesis
            # pair.  Candidate yield determines which witnesses enter the
            # post-state, never which A2 pair keys/ranks exist; otherwise one
            # candidate realization would silently renumber grouping draws.
            for left in range(len(ordered_candidates)):
                for right in range(left + 1, len(ordered_candidates)):
                    left_index, left_candidate = ordered_candidates[left]
                    right_index, right_candidate = ordered_candidates[right]
                    left_rank, right_rank = left, right
                    if left_candidate.hypothesis_id != right_candidate.hypothesis_id:
                        continue
                    lo, hi = sorted((left_candidate.witness_id, right_candidate.witness_id))
                    pair_entries.append((f"GROUP|{left_candidate.hypothesis_id}|{lo}|{hi}", left_rank, left_index,
                                         left_candidate, right_rank, right_index, right_candidate))
            pair_outcomes: dict[str, list[tuple[int, str]]] = {}
            for pair_rank, (pair_id, left_rank, _left_index, left_candidate, right_rank, _right_index, right_candidate) in enumerate(sorted(pair_entries)):
                score = max(left_candidate.score_bin, right_candidate.score_bin)
                probabilities = perturbed_grouping_distribution(seed=self.seed, decision_index=self.decision_index,
                    form=self.identity["error_form"], magnitude=float(self.identity["error_magnitude"]), trajectory_index=self.trajectory_index,
                    target_identity=pair_id, draw_index=pair_rank, target_score_bin=score,
                    frontier_max_score_bin=generated_max_score, joint=self.joint, applies=self._applies("grouping_transition"))
                key = self._draw_key("grouping", pair_id, pair_rank)
                uniform = keyed_uniform(*key)
                grouping = categorical_outcome(probabilities, GROUPING_CATEGORIES, uniform)
                baseline_grouping = categorical_outcome((1.0, 0.0, 0.0), GROUPING_CATEGORIES, uniform)
                pair_outcomes.setdefault(left_candidate.witness_id, []).append((pair_rank, grouping))
                pair_outcomes.setdefault(right_candidate.witness_id, []).append((pair_rank, grouping))
                draws.append({"family":"grouping", "entity":pair_id, "semantic_identity":pair_id,
                              "draw_index":pair_rank, "a4_key":list(key), "u":uniform,
                              "p0":[1.0,0.0,0.0], "p_error":probabilities,
                              "baseline_outcome":baseline_grouping, "perturbed_outcome":grouping,
                              "outcome":grouping,
                              **self._sign_evidence("grouping_transition", pair_id, pair_rank, score, generated_max_score)})
            for rank, index, candidate in retained:
                grouping = next((outcome for _, outcome in sorted(pair_outcomes.get(candidate.witness_id, ())) if outcome != "CORRECT"), "CORRECT")
                same = [item for item in self.state.frontier if item.latent_event_id == self._latent_event_id(region.region_id, index, candidate)]
                different = [item for item in self.state.frontier if item.latent_event_id != self._latent_event_id(region.region_id, index, candidate)]
                if grouping == "OVER_MERGE" and different:
                    model_hypothesis = sorted(different, key=lambda item: (item.created_at, item.model_hypothesis_id))[0].model_hypothesis_id
                else:
                    # No H_diff is exactly the specified OVER_MERGE fallback:
                    # it must then execute the complete CORRECT transition,
                    # including attachment to an existing H_same.
                    if grouping == "OVER_MERGE":
                        grouping = "CORRECT"
                    if grouping == "CORRECT" and same:
                        model_hypothesis = sorted(same, key=lambda item: (item.created_at, item.model_hypothesis_id))[0].model_hypothesis_id
                    else:
                        model_hypothesis = stable_hypothesis_id(self.episode_public_id, self.decision_index, region.region_id, candidate.witness_id)
                witness = ModelWitness(candidate, region.region_id, index, model_hypothesis, self.state.elapsed,
                                       self._latent_event_id(region.region_id, index, candidate))
                # Apply grouping in stable witness order so a later witness
                # observes prior same-action membership, never a batch-local
                # stale frontier.
                self._add_witness(witness)
            self.state.scanned.add(region.region_id)
            self.action_ordinal += 1
            return "SCANNED", False, self._transition_record(pre, action, draws, "SCANNED", transition_ordinal)
        selected = next(item for item in self.state.frontier if item.candidate.witness_id == action.witness_id and item.model_hypothesis_id == action.hypothesis_id)
        region = self._regions[selected.region_id]
        duration_draw = self._duration_draw(p0=region.confirm_ticks[selected.source_index], maximum=CONFIRM_SUPPORT_TICKS,
                                            action=action, draw_index=action_rank, score=selected.candidate.score_bin)
        duration = duration_draw["perturbed_outcome"]
        self.state.elapsed += duration
        draws.append(duration_draw)
        ordered_frontier = tuple(sorted(self.state.frontier, key=lambda item: (item.model_hypothesis_id, item.candidate.witness_id)))
        frontier_rank = next(index for index, item in enumerate(ordered_frontier) if item == selected)
        confirm_target = f"CONFIRM|{selected.candidate.hypothesis_id}|{selected.candidate.witness_id}"
        confirm_draw = self._binary_draw(family="confirm_outcome", mechanism="confirm_positive_probability",
                                         p0=float(region.positive[selected.source_index]), target_identity=confirm_target,
                                         entity=selected.stable_id, draw_index=frontier_rank,
                                         score=selected.candidate.score_bin)
        draws.append(confirm_draw)
        positive = bool(confirm_draw["perturbed_outcome"])
        committed = False
        outcome = "ORACLE_NEGATIVE"
        event = selected.latent_event_id
        if positive:
            novelty_target = f"NOVELTY|{selected.candidate.hypothesis_id}|{selected.candidate.witness_id}"
            novelty_draw = self._binary_draw(family="novelty", mechanism="novelty_duplicate_probability",
                                             p0=float(event not in self.state.committed), target_identity=novelty_target,
                                             entity=selected.stable_id, draw_index=frontier_rank,
                                             score=selected.candidate.score_bin)
            draws.append(novelty_draw)
            novel = bool(novelty_draw["perturbed_outcome"])
            materialization_target = f"MATERIALIZE|{selected.candidate.hypothesis_id}|{selected.candidate.witness_id}"
            materialization_draw = self._binary_draw(family="materialization", mechanism="materialization_success",
                                                     p0=float(region.event_tokens[selected.source_index] is not None),
                                                     target_identity=materialization_target, entity=selected.stable_id,
                                                     draw_index=frontier_rank, score=selected.candidate.score_bin)
            draws.append(materialization_draw)
            materialized = bool(materialization_draw["perturbed_outcome"])
            if novel and materialized:
                # A4 novelty is a model-token transition.  When model error
                # makes an already committed latent event appear novel, it
                # must create a distinct model token rather than award reward
                # for re-adding the same set element.
                model_token = event if event not in self.state.committed else f"A4_NOVEL|{selected.stable_id}|{self.action_ordinal}"
                self.state.committed.add(model_token); committed = True; outcome = "NEW_COMMIT"
            elif not novel:
                outcome = "DUPLICATE"
            else:
                outcome = "MATERIALIZATION_FAILURE"
        self._resolve_hypothesis(selected.model_hypothesis_id, model_token if committed else None)
        self.action_ordinal += 1
        return outcome, committed, self._transition_record(pre, action, draws, outcome, transition_ordinal)

    def rollout(self, first_action: ActionView) -> tuple[float, tuple[dict, ...]]:
        value, records = 0.0, []
        action = first_action
        while not self.state.stopped:
            outcome, committed, record = self.execute(action)
            records.append(record)
            if committed:
                value += HORIZON_TICKS - self.state.elapsed
            if self.state.stopped:
                break
            action = self.pi0()
        return value, tuple(records)
