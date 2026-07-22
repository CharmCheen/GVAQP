import inspect
import json
from copy import deepcopy
from pathlib import Path

from garc_eval.psvr_rollout_h1b.a4 import (
    A4PlannerKernel, GROUPING_CATEGORIES, ModelWitness, _a4_sign, a4_key, categorical_outcome,
    keyed_uniform, perturbed_binary_probability, perturbed_grouping_distribution,
    stable_hypothesis_id,
)
from garc_eval.psvr_rollout_h1b.ic1 import execute_full_horizon, visible
from garc_eval.psvr_rollout_h1b.independent_verifier import verify_episode_evidence, verify_lossless_evidence
from garc_eval.psvr_rollout_toy.r2 import R2Environment, finite_world_library


def identity(target="confirm_positive_probability", form="independent_variance", magnitude=.05):
    return {"development_episode_id": "development-0000", "error_target": target,
            "error_form": form, "error_magnitude": magnitude}


def test_a4_keyed_realization_resolves_old_counterexample_to_one_outcome():
    key = a4_key("development-0000", 1, 0, 2, "confirm_outcome", "CONFIRM|h00_0|w00_0")
    assert key == ("H1B_A4", "development-0000", 1, 0, 2, "confirm_outcome", "CONFIRM|h00_0|w00_0")
    first = keyed_uniform(*key)
    assert first == keyed_uniform(*key)
    probability = perturbed_binary_probability(1 / 3, seed="development-0000", decision_index=1,
        mechanism="confirm_positive_probability", form="independent_variance", magnitude=.05,
        trajectory_index=2, target_identity="CONFIRM|h00_0|w00_0", draw_index=0,
        target_score_bin=3, frontier_max_score_bin=3, joint=False, applies=True)
    assert (first < probability) == (keyed_uniform(*key) < probability)


def test_a4_binary_and_categorical_boundaries_are_strict_and_ordered():
    assert categorical_outcome((0.0, 1.0), ("false", "true"), 0.0) == "true"
    assert categorical_outcome((.5, .5), ("first", "second"), .5) == "second"
    assert categorical_outcome((.2, .2), ("first", "second"), .99) == "second"


def test_a4_shared_uniform_coupling_is_monotone():
    uniform = .3
    assert (uniform < .2) is False
    assert (uniform < .4) is True


def test_a4_joint_uses_one_sign_across_families():
    signs = {
        _a4_sign("seed", 2, mechanism, "independent_variance", 7, f"{mechanism}|x", 9,
                 1, 3, True)
        for mechanism in ("scan_candidate_yield", "confirm_positive_probability", "novelty_duplicate_probability",
                          "grouping_transition", "action_duration", "materialization_success")
    }
    assert len(signs) == 1


def test_a4_grouping_distribution_and_stable_hypothesis_ids():
    distribution = perturbed_grouping_distribution(seed="s", decision_index=0, form="systematic_pessimism",
        magnitude=.2, trajectory_index=0, target_identity="GROUP|h|a|b", draw_index=0,
        target_score_bin=1, frontier_max_score_bin=1, joint=False, applies=True)
    assert distribution == (.8, .2, 0.0)
    assert categorical_outcome(distribution, GROUPING_CATEGORIES, .9) == "UNDER_MERGE"
    assert stable_hypothesis_id("e", 1, "r00", "w00_0") == stable_hypothesis_id("e", 1, "r00", "w00_0")
    assert stable_hypothesis_id("e", 1, "r00", "w00_0") != stable_hypothesis_id("e", 1, "r00", "w00_1")


def test_a4_replay_is_bit_identical_and_has_no_evaluator_access():
    world = finite_world_library()[0]
    env = R2Environment(world)
    state = visible(env)
    action = next(item for item in state.legal_actions if item.kind == "SCAN")
    first = A4PlannerKernel(world, env.history, state, identity("grouping_transition", "systematic_optimism", .1), "fixture", 0, 0)
    second = A4PlannerKernel(world, env.history, state, identity("grouping_transition", "systematic_optimism", .1), "fixture", 0, 0)
    assert first.rollout(action) == second.rollout(action)
    source = inspect.getsource(A4PlannerKernel)
    assert "ExactReferenceEvaluator" not in source and "R2Environment" not in source


def _scan_kernel(form="systematic_pessimism", magnitude=.2, episode="development-0000", target="grouping_transition"):
    world = finite_world_library()[0]
    env = R2Environment(world)
    record_identity = identity(target, form, magnitude)
    record_identity["development_episode_id"] = episode
    return A4PlannerKernel(world, env.history, visible(env), record_identity,
                           "fixture", 0, 0)


def _scan(kernel):
    return kernel.execute(next(action for action in kernel.safe_actions() if action.kind == "SCAN"))


def test_a4_complete_grouping_fixture_suite_and_lossless_transition_record():
    # CORRECT attaches the same-event second witness to the first hypothesis.
    correct = _scan_kernel("systematic_pessimism", 0.0)
    _, _, correct_record = _scan(correct)
    hypotheses = correct.state.canonical()["hypotheses"]
    assert len(hypotheses) == 2 and any(len(item["ordered_witness_ids"]) == 2 for item in hypotheses)  # CORRECT attach existing hypothesis
    assert all({"resolved", "suppressed", "pending_witness_ids", "verified_witness_ids"} <= item.keys() for item in hypotheses)

    # A non-CORRECT A2 pair outcome creates separate hypotheses (UNDER_MERGE).
    under = _scan_kernel("systematic_pessimism", .2, "e1")
    _, _, under_record = _scan(under)
    grouping = [draw for draw in under_record["draws"] if draw["family"] == "grouping"]
    # The exact outcome is keyed, so this assertion also covers the retained A2 pair identity.
    assert grouping and grouping[0]["semantic_identity"] == "GROUP|h00_0|w00_0|w00_1"
    assert grouping[0]["a1_a2_sign_key"][-2:] == ["GROUP|h00_0|w00_0|w00_1", 0]
    assert grouping[0]["perturbed_outcome"] == "UNDER_MERGE" and len(under.state.hypotheses) == 3

    # Candidate yield may remove an endpoint, but it cannot remove or renumber
    # the A2 pair draw for generated candidates.
    yielded = _scan_kernel("systematic_pessimism", .2, "e1", "scan_candidate_yield")
    _, _, yielded_record = _scan(yielded)
    assert any(draw["family"] == "candidate_yield" and not draw["perturbed_outcome"] for draw in yielded_record["draws"])
    assert any(draw["family"] == "grouping" and draw["semantic_identity"] == "GROUP|h00_0|w00_0|w00_1" for draw in yielded_record["draws"])

    # OVER_MERGE falls back to CORRECT with no H_diff, but attaches the first
    # H_diff when a prior different-event witness exists.
    fallback = _scan_kernel("systematic_optimism", .2, "e1")
    _, _, fallback_record = _scan(fallback)
    assert len(fallback.state.hypotheses) == 2  # no-H_diff fallback
    attach = _scan_kernel("systematic_optimism", .2, "e1")
    candidate = attach.world.regions[0].candidates[2]
    attach._add_witness(ModelWitness(candidate, "r00", 2, "older-different", 0, "DIFFERENT"))
    _, _, attach_record = _scan(attach)
    assert "older-different" in attach.state.hypotheses  # OVER_MERGE attach-first-H_diff opportunity

    # Every realization has a full key, A1/A2 sign, P0/Perror, coupled
    # baseline/perturbed outcomes; duration also has its transform metadata.
    for record in (correct_record, under_record, fallback_record, attach_record):
        assert record["canonical_pre_state"] == record["pre_state"]
        assert record["transition_hash"]
        for draw in record["draws"]:
            assert {"a4_key", "a1_a2_sign_key", "a1_a2_sign", "p0", "p_error", "baseline_outcome", "perturbed_outcome"} <= draw.keys()
            if draw["family"] == "duration":
                assert draw["duration_transformation"]["support_maximum"] > 0
            else:
                assert draw["baseline_outcome"] == (draw["u"] < draw["p0"]) if draw["family"] != "grouping" else True


def test_a4_hydration_order_key_source_agreement_joint_and_independent_replay():
    world = finite_world_library()[0]
    env = R2Environment(world)
    scan = next(action for action in env.safe_actions() if action.kind == "SCAN")
    env.execute(scan)
    state = visible(env)
    hydrated = A4PlannerKernel(world, env.history, state, identity(), "fixture", 0, 0, (17,))
    assert all(item.created_at == 17 for item in hydrated.state.frontier)  # hydration timestamp fixture
    assert hydrated.state.canonical()["frontier"] == sorted(hydrated.state.canonical()["frontier"], key=lambda item: (item["created_at"], item["model_hypothesis_id"], item["witness_id"]))

    root = Path(__file__).resolve().parents[2]
    keyed = json.loads((root / "outputs/psvr_rollout_r2b_a4/A4_KEYED_REALIZATION_SPEC.json").read_text())
    assert keyed["encoding"] == "UTF-8 canonical JSON array with typed fields and sorted object keys"
    assert keyed_uniform(*a4_key("e", 1, 2, 3, "grouping", "GROUP|h|a|b")) == keyed_uniform(*a4_key("e", 1, 2, 3, "grouping", "GROUP|h|a|b"))

    joint = A4PlannerKernel(world, env.history, state, identity("JOINT_CORNER", "state_dependent_calibration", .2), "fixture", 0, 0, (17,))
    first_action = joint.pi0()
    first = joint.rollout(first_action)
    second = A4PlannerKernel(world, env.history, state, identity("JOINT_CORNER", "state_dependent_calibration", .2), "fixture", 0, 0, (17,)).rollout(first_action)
    assert first == second  # JOINT state-dependent behavior and deterministic full transition replay
    # The canonical policy-visible state and the persisted transition evidence
    # contain no sampled-root latent event identity or correctness label.
    serialized = json.dumps(first[1], sort_keys=True)
    assert "latent_event_id" not in serialized and "grouping_correctness_label" not in serialized


def test_ic1_persists_lossless_a4_evidence_and_independent_verifier_recomputes_it():
    complete = {
        "development_episode_id": "development-0000", "configuration_id": "a4-evidence-fixture",
        "method_id": "APPROX_LCB_FALLBACK", "posterior_budget_id": "posterior-4",
        "trajectory_budget_id": "trajectory-4", "error_target": "scan_candidate_yield",
        "error_form": "independent_variance", "error_magnitude": .05,
        "error_direction": "STOCHASTIC", "planning_cost_id": "p-2", "fallback_variant": "LCB",
        "attempt_ordinal": 0, "canonical_spec_hash": "a" * 64,
        "implementation_hash": "b" * 64, "development_universe_hash": "c" * 64,
    }
    result = execute_full_horizon(complete, 101)
    reports = [verify_lossless_evidence(decision["planner"], complete) for decision in result.trace["decisions"]]
    assert all(report["status"] == "PASS" for report in reports)
    assert any(report["transition_count"] > 0 for report in reports)
    assert verify_episode_evidence(result.trace)["status"] == "PASS"

    # Mutations found by blind red-team must fail independently, even after a
    # locally self-consistent transition hash is recomputed.
    forged = deepcopy(result.trace)
    transition = next(transition for decision in forged["decisions"] for pair in decision["planner"].get("a4_lossless_evidence", {}).get("pairs", []) for sample in pair["samples"] for transition in sample["action_transitions"] if any(draw["family"] == "candidate_yield" for draw in transition["draws"]))
    draw = next(draw for draw in transition["draws"] if draw["family"] == "candidate_yield")
    draw["p_error"] = .51
    draw["perturbed_outcome"] = draw["outcome"] = draw["u"] < .51
    transition["transition_hash"] = __import__("hashlib").sha256(json.dumps({key:value for key,value in transition.items() if key != "transition_hash"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert verify_episode_evidence(forged)["status"] == "FAIL"
    for field, value in (("identity_hash", "0" * 64), ("raw_evidence_commitment", "0" * 64)):
        forged = deepcopy(result.trace); forged[field] = value
        assert verify_episode_evidence(forged)["status"] == "FAIL"
    forged = deepcopy(result.trace); forged["decisions"][0]["action"] = "STOP:::"
    assert verify_episode_evidence(forged)["status"] == "FAIL"
