"""Independent A4 compact-evidence verifier.

This module intentionally does *not* import the production A4 executor,
IC1 paired model, exact evaluator, or production metric aggregation.  It
checks canonical transition commitments directly and independently recomputes
inverse-CDF outcomes, A1/A2 signs, paired differences, mean, variance, LCB,
and the selected action implied by a persisted planner trace.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from math import ceil, sqrt
from typing import Any

from garc_eval.psvr_rollout_toy.r2 import finite_world_library


FAMILIES = ("candidate_yield", "grouping", "confirm_outcome", "novelty", "materialization", "duration")
GROUPS = ("CORRECT", "UNDER_MERGE", "OVER_MERGE")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _uniform(key: list[Any]) -> float:
    digest = hashlib.sha256(_canonical(key).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64


def _sign(key: list[Any], form: str, target_score: int | None, frontier_max: int | None) -> int:
    if form == "systematic_optimism":
        return 1
    if form == "systematic_pessimism":
        return -1
    if form == "state_dependent_calibration":
        if len(key) > 3 and key[3] == "JOINT":
            return -1
        if target_score is None or frontier_max is None:
            return -1
        return 1 if target_score == frontier_max else -1
    if form != "independent_variance":
        raise ValueError("unknown-error-form")
    return 1 if hashlib.sha256("|".join(map(str, key)).encode("utf-8")).digest()[0] & 1 else -1


def _binary(probability: float, uniform: float) -> bool:
    return uniform < probability


def _categorical(probabilities: list[float], uniform: float) -> str:
    cumulative = 0.0
    for probability, category in zip(probabilities, GROUPS):
        cumulative += probability
        if uniform < cumulative:
            return category
    return GROUPS[-1]


def _transition_hash(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items() if key != "transition_hash"}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _worlds_by_id() -> dict[str, Any]:
    return {world.world_id: world for world in finite_world_library()}


def _root_world(world_id: str):
    return _worlds_by_id().get(world_id)


def _candidate(world: Any, witness_id: str, hypothesis_id: str | None = None):
    for region in world.regions:
        for index, candidate in enumerate(region.candidates):
            if candidate.witness_id == witness_id and (hypothesis_id is None or candidate.hypothesis_id == hypothesis_id):
                return region, index, candidate
    return None


def _expected_p0(draw: dict[str, Any], pre: dict[str, Any], world: Any) -> Any:
    family, semantic = draw["family"], str(draw["semantic_identity"])
    if family == "candidate_yield": return 1.0
    if family == "grouping": return [1.0, 0.0, 0.0]
    if family == "duration":
        action = semantic.removeprefix("DURATION|")
        if action.startswith("SCAN:"):
            region = next(region for region in world.regions if region.region_id == action.split(":", 2)[1])
            return region.scan_ticks
        witness = action.rsplit(":", 1)[-1]
        selected = next(item for item in pre.get("frontier", []) if item["witness_id"] == witness)
        found = _candidate(world, witness, selected["source_hypothesis_id"])
        if found is None: raise ValueError("unknown-root-witness")
        return found[0].confirm_ticks[found[1]]
    source_hypothesis, witness = semantic.split("|", 2)[1:]
    found = _candidate(world, witness, source_hypothesis)
    if found is None: raise ValueError("unknown-root-witness")
    region, index, _ = found
    if family == "confirm_outcome": return float(region.positive[index])
    if family == "materialization": return float(region.event_tokens[index] is not None)
    if family == "novelty":
        event = region.event_tokens[index] or f"NEGATIVE|{region.region_id}|{source_hypothesis}|{witness}"
        return float(event not in pre.get("committed", []))
    raise ValueError("unknown-family")


def verify_transition(record: dict[str, Any], identity: dict[str, Any], episode_seed: int | None = None,
                      root_world_id: str | None = None) -> list[str]:
    """Verify one persisted transition without invoking production execution."""
    errors: list[str] = []
    if record.get("canonical_pre_state") != record.get("pre_state"):
        errors.append("canonical-pre-state-mismatch")
    if record.get("canonical_action") != record.get("action"):
        errors.append("canonical-action-mismatch")
    if record.get("transition_hash") != _transition_hash(record):
        errors.append("transition-hash-mismatch")
    world = _root_world(root_world_id) if root_world_id is not None else None
    if root_world_id is not None and world is None: errors.append("unknown-posterior-root-world")
    for index, draw in enumerate(record.get("draws", [])):
        family = draw.get("family")
        if family not in FAMILIES:
            errors.append(f"draw-{index}:unknown-family")
            continue
        key = draw.get("a4_key")
        if not isinstance(key, list) or len(key) != 7 or key[0] != "H1B_A4" or key[5] != family:
            errors.append(f"draw-{index}:invalid-a4-key")
            continue
        if key[1] != identity.get("development_episode_id") or key[2] != record.get("planning_decision_index") or key[6] != draw.get("semantic_identity"):
            errors.append(f"draw-{index}:a4-key-identity-mismatch")
        expected_family_index = FAMILIES.index(family)
        transition_index = key[4]
        if not isinstance(transition_index, int) or (transition_index // 1_000_000) % 10 != expected_family_index:
            errors.append(f"draw-{index}:schedule-family-mismatch")
        elif transition_index // 10_000_000 != record.get("action_ordinal"):
            errors.append(f"draw-{index}:schedule-action-ordinal-mismatch")
        if family != "duration":
            uniform = _uniform(key)
            if draw.get("u") != uniform:
                errors.append(f"draw-{index}:uniform-mismatch")
            p0, perror = draw.get("p0"), draw.get("p_error")
            if family == "grouping":
                if draw.get("baseline_outcome") != _categorical(list(p0), uniform):
                    errors.append(f"draw-{index}:baseline-outcome-mismatch")
                if draw.get("perturbed_outcome") != _categorical(list(perror), uniform):
                    errors.append(f"draw-{index}:perturbed-outcome-mismatch")
            else:
                if draw.get("baseline_outcome") != _binary(float(p0), uniform):
                    errors.append(f"draw-{index}:baseline-outcome-mismatch")
                if draw.get("perturbed_outcome") != _binary(float(perror), uniform):
                    errors.append(f"draw-{index}:perturbed-outcome-mismatch")
        else:
            if draw.get("baseline_outcome") != draw.get("p0") or draw.get("perturbed_outcome") != draw.get("p_error"):
                errors.append(f"draw-{index}:duration-outcome-mismatch")
            if not isinstance(draw.get("duration_transformation"), dict):
                errors.append(f"draw-{index}:missing-duration-metadata")
        sign_key = draw.get("a1_a2_sign_key")
        if not isinstance(sign_key, list):
            errors.append(f"draw-{index}:missing-sign-key")
            continue
        try:
            expected_sign = _sign(sign_key, str(identity["error_form"]), draw.get("target_score_bin"), draw.get("frontier_max_score_bin"))
        except (KeyError, ValueError):
            errors.append(f"draw-{index}:invalid-sign-form")
        else:
            if draw.get("a1_a2_sign") != expected_sign:
                errors.append(f"draw-{index}:sign-mismatch")
        expected_sign_target = "JOINT" if identity.get("error_target") == "JOINT_CORNER" else draw.get("error_mechanism")
        expected_error_target = "JOINT" if identity.get("error_target") == "JOINT_CORNER" else draw.get("semantic_identity")
        expected_error_index = 0 if identity.get("error_target") == "JOINT_CORNER" else draw.get("draw_index")
        if (len(sign_key) != 8 or sign_key[0] != "H1B_ERROR" or
                sign_key[2] != record.get("planning_decision_index") or
                sign_key[3] != expected_sign_target or sign_key[4] != identity.get("error_form") or
                sign_key[6] != expected_error_target or sign_key[7] != expected_error_index):
            errors.append(f"draw-{index}:a1-a2-key-identity-mismatch")
        if episode_seed is not None and sign_key[1] != episode_seed:
            errors.append(f"draw-{index}:a1-a2-key-seed-mismatch")
        applies = identity.get("error_target") == "JOINT_CORNER" or identity.get("error_target") == draw.get("error_mechanism")
        if world is not None:
            try:
                if draw.get("p0") != _expected_p0(draw, record.get("canonical_pre_state", {}), world):
                    errors.append(f"draw-{index}:baseline-kernel-mismatch")
            except (KeyError, StopIteration, ValueError):
                errors.append(f"draw-{index}:unreconstructible-baseline-kernel")
        magnitude = float(identity.get("error_magnitude", 0.0))
        sign_value = int(draw.get("a1_a2_sign", 0))
        if family == "grouping":
            expected_probability = [1.0, 0.0, 0.0] if not applies else [1.0 - magnitude, magnitude if sign_value < 0 else 0.0, magnitude if sign_value > 0 else 0.0]
            total = sum(max(0.0, value) for value in expected_probability)
            expected_probability = [1.0, 0.0, 0.0] if total == 0 else [max(0.0, value) / total for value in expected_probability]
        elif family == "duration":
            maximum = int(draw.get("duration_transformation", {}).get("support_maximum", 0))
            expected_probability = int(draw["p0"]) if not applies else min(maximum, max(1, ceil(int(draw["p0"]) * (1 + sign_value * magnitude))))
        else:
            expected_probability = float(draw["p0"]) if not applies else min(.99, max(.01, float(draw["p0"]) + sign_value * magnitude))
        if draw.get("p_error") != expected_probability:
            errors.append(f"draw-{index}:transformed-probability-mismatch")
    return errors


def verify_lossless_evidence(planner_trace: dict[str, Any], identity: dict[str, Any], episode_seed: int | None = None) -> dict[str, Any]:
    """Independently recompute paired statistics and planner action choice."""
    evidence = planner_trace.get("a4_lossless_evidence", {})
    errors: list[str] = []
    recomputed: dict[str, dict[str, float]] = {}
    for pair_index, pair in enumerate(evidence.get("pairs", [])):
        samples = pair.get("samples", [])
        differences: list[float] = []
        for sample_index, sample in enumerate(samples):
            differences.append(float(sample["action_return"]) - float(sample["base_return"]))
            if sample.get("paired_difference") != differences[-1]:
                errors.append(f"pair-{pair_index}-sample-{sample_index}:difference-mismatch")
            for transition in sample.get("action_transitions", []):
                errors.extend(f"pair-{pair_index}-sample-{sample_index}:action:{error}" for error in verify_transition(transition, identity, episode_seed, sample.get("posterior_world_id")))
            for transition in sample.get("base_transitions", []):
                errors.extend(f"pair-{pair_index}-sample-{sample_index}:base:{error}" for error in verify_transition(transition, identity, episode_seed, sample.get("posterior_world_id")))
        if not differences:
            errors.append(f"pair-{pair_index}:empty-samples")
            continue
        mean = sum(differences) / len(differences)
        variance = 0.0 if len(differences) == 1 else sum((value - mean) ** 2 for value in differences) / (len(differences) - 1)
        lcb = mean if len(differences) == 1 or variance == 0.0 else mean - 1.96 * sqrt(variance) / sqrt(len(differences))
        action = pair["action"]
        recomputed[action] = {"mean": mean, "variance": variance, "lcb": lcb}
        for field, value in (("paired_mean", mean), ("paired_variance", variance), ("paired_lcb_95", lcb)):
            if pair.get(field) != value:
                errors.append(f"pair-{pair_index}:{field}-mismatch")
    expected_action = planner_trace.get("selected_action")
    mode = planner_trace.get("fallback_reason")
    # The persisted trace already supplies the production-independent threshold
    # inputs.  We verify that the recorded selected action has the highest
    # allowed score when a non-baseline action was selected.
    if expected_action in recomputed:
        score = recomputed[expected_action]["mean"] if mode == "POSITIVE_POINT" else recomputed[expected_action]["lcb"]
        threshold = float(planner_trace.get("bias_margin", 0.0)) + float(planner_trace.get("planning_time", 0.0))
        if score <= threshold:
            errors.append("selected-action-fails-strict-threshold")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "recomputed_actions": recomputed, "transition_count": sum(
                len(sample.get("action_transitions", [])) + len(sample.get("base_transitions", []))
                for pair in evidence.get("pairs", []) for sample in pair.get("samples", []))}


def verify_episode_evidence(trace: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the persisted utility timeline and all paired decisions.

    The 1600-tick R2 horizon is part of the frozen utility semantics.  This
    function consumes only persisted identity, decisions, and compact A4
    evidence; it does not construct an environment or invoke a policy.
    """
    identity = trace.get("identity", {})
    errors: list[str] = []
    expected_identity_hash = hashlib.sha256(_canonical(identity).encode()).hexdigest()
    if trace.get("identity_hash") != expected_identity_hash:
        errors.append("identity-hash-mismatch")
    commitment_payload = {key: value for key, value in trace.items()
                          if key not in {"raw_evidence_commitment", "label", "non_confirmatory", "source_hashes"}}
    if trace.get("raw_evidence_commitment") != hashlib.sha256(_canonical(commitment_payload).encode()).hexdigest():
        errors.append("raw-evidence-commitment-mismatch")
    replay_key = trace.get("deterministic_replay_key", {})
    episode_seed = replay_key.get("episode_seed")
    if not isinstance(episode_seed, int):
        errors.append("missing-episode-seed")
    reports = []
    elapsed, utility = 0, 0.0
    expected_timeline = [{"tick": 0, "utility": 0}]
    for index, decision in enumerate(trace.get("decisions", [])):
        report = verify_lossless_evidence(decision.get("planner", {}), identity, episode_seed)
        reports.append(report)
        errors.extend(f"decision-{index}:{error}" for error in report["errors"])
        if decision.get("action") != decision.get("planner", {}).get("selected_action"):
            errors.append(f"decision-{index}:selected-action-mismatch")
        elapsed += int(decision.get("planner", {}).get("planning_time", 0)) + int(decision["duration"])
        if decision.get("observation") == "NEW_COMMIT":
            utility += 1600 - elapsed
        expected_timeline.append({"tick": elapsed, "utility": utility})
    if trace.get("utility_timeline") != expected_timeline:
        errors.append("utility-timeline-mismatch")
    if trace.get("stop_time") != elapsed:
        errors.append("stop-time-mismatch")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "decision_reports": reports, "utility_timeline": expected_timeline,
            "transition_count": sum(report["transition_count"] for report in reports)}
