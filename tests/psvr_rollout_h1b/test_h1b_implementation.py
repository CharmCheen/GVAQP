import inspect
import hashlib

import pytest

from garc_eval.psvr_rollout_h1b.approximate_rollout import ApproximatePlanner, PlannerConfig
from garc_eval.psvr_rollout_h1b.advantage import paired_advantage
from garc_eval.psvr_rollout_h1b.crn import error_key, planning_key, sign, uniform01
from garc_eval.psvr_rollout_h1b.error_operators import ErrorContext, canonical_candidates, canonical_target, error_sign, perturb_duration, perturb_probability
from garc_eval.psvr_rollout_h1b.invariants import assert_trace_safe
from garc_eval.psvr_rollout_h1b.planning_cost import consume_planning_time
from garc_eval.psvr_rollout_h1b.plan_admission import planning_admission
from garc_eval.psvr_rollout_h1b.posterior_sampling import fixed_posterior_indices
from garc_eval.psvr_rollout_h1b.serialization import canonical_trace_json
from garc_eval.psvr_rollout_h1b.types import ActionView, VisibleDecisionState
from garc_eval.psvr_rollout_h1b.uncertainty import paired_lcb_95
from garc_eval.psvr_rollout_h1b.ic1 import ContinuationReturnCache, canonical_identity, execute_full_horizon, identity_hash, visible
from garc_eval.psvr_rollout_toy.r2 import R2Environment, finite_world_library


BASE=ActionView("CONFIRM:r:h:w0","CONFIRM",1,"h","w0")
ALT=ActionView("CONFIRM:r:h:w1","CONFIRM",3,"h","w1")

class HandModel:
    def paired_returns(self, state, action, base, worlds, trajectories):
        assert (worlds, trajectories) in {(4,4),(16,16),(64,64),(256,256)}
        return ((20.0, 20.0, 20.0, 20.0), (10.0, 10.0, 10.0, 10.0))
class InferiorModel:
    def paired_returns(self, state, action, base, worlds, trajectories):
        return ((0.0,0.0,0.0,0.0),(1.0,1.0,1.0,1.0))

def base_policy(state): return BASE if BASE in state.legal_actions else state.ordered_actions()[0]

def state(remaining=100): return VisibleDecisionState("hand-fixture", 0, remaining, (ALT, BASE), (ALT, BASE))

def test_hand_calculated_paired_advantage_and_lcb():
    estimate=paired_advantage((9.0, 11.0, 13.0), (8.0, 10.0, 12.0))
    assert estimate.samples==(1.0,1.0,1.0) and estimate.mean==1.0 and paired_lcb_95(estimate)==1.0

def test_crn_is_bit_identical_and_action_order_independent():
    key=planning_key("fixture",2,1,3,"transition")
    assert uniform01(*key)==uniform01(*key)
    assert canonical_candidates((ALT,BASE))==canonical_candidates((BASE,ALT))

def test_budget_and_positive_lcb_override():
    planner=ApproximatePlanner(base_policy,HandModel(),PlannerConfig(4,4,2,"LCB"))
    action,trace=planner.decide(state())
    assert action==ALT and trace.planning_time==2 and trace.post_planning_remaining_time==98
    assert_trace_safe(trace)

def test_strict_threshold_equality_falls_back_and_recomputes_base():
    planner=ApproximatePlanner(base_policy,HandModel(),PlannerConfig(4,4,2,"LCB"))
    action,trace=planner.decide(state())
    assert action==ALT
    planner=ApproximatePlanner(base_policy,HandModel(),PlannerConfig(4,4,2,"LCB","JOINT_CORNER"))
    action,trace=planner.decide(state())
    assert action==BASE and trace.fallback_reason=="THRESHOLD_NOT_STRICTLY_EXCEEDED"

def test_planning_time_infeasible_skips_without_horizon_refund():
    result=consume_planning_time(state(2),2)
    assert not result.admitted and result.post_state.remaining_ticks==2
    action,trace=ApproximatePlanner(base_policy,HandModel(),PlannerConfig(4,4,2,"LCB")).decide(state(2))
    assert action==BASE and trace.planning_time==0 and not trace.planning_admitted
    assert planning_admission(state(2),2,BASE).status=="SKIP_TO_PI0"

def test_error_targets_probability_duration_bounds_and_canonical_pair():
    context=ErrorContext("fixture",0,"confirm_positive_probability","systematic_optimism",0,"CONFIRM|h|w1",0,3,3)
    assert perturb_probability(.98,.20,context)==.99
    assert perturb_duration(130,.20,138,context)==138
    assert canonical_target("grouping_transition",BASE,ALT)=="GROUP|h|w0|w1"

def test_trace_roundtrip_and_no_exact_evaluator_constructor_parameter():
    _,trace=ApproximatePlanner(base_policy,HandModel(),PlannerConfig(4,4,0,"POINT")).decide(state())
    assert canonical_trace_json(trace)==canonical_trace_json(trace)
    assert "ExactEvaluatorAPI" not in str(inspect.signature(ApproximatePlanner))

def test_invalid_probability_and_grid_fail_closed():
    context=ErrorContext("fixture",0,"x","systematic_optimism",0,"x",0)
    with pytest.raises(ValueError): perturb_probability(1.1,.05,context)
    with pytest.raises(ValueError): PlannerConfig(5,5,0,"LCB")

def test_ungated_keeps_base_when_no_candidate_has_positive_advantage():
    action,_=ApproximatePlanner(base_policy,InferiorModel(),PlannerConfig(4,4,0,"UNGATED")).decide(state())
    assert action==BASE

def test_post_planning_feasibility_and_stop_are_fail_closed():
    expiring=ActionView("CONFIRM:r:h:w1","CONFIRM",3,"h","w1",minimum_remaining_ticks=99)
    post=consume_planning_time(VisibleDecisionState("x",0,100,(BASE,expiring)),2).post_state
    assert expiring not in post.legal_actions and BASE in post.legal_actions
    action,trace=ApproximatePlanner(base_policy,HandModel(),PlannerConfig(4,4,0,"LCB")).decide(VisibleDecisionState("x",0,0,()))
    assert action.kind=="STOP" and trace.fallback_reason=="STOP"

def test_fixed_posterior_prefix_is_deterministic():
    class FixtureSampler:
        def support_size(self, visible): return 7
    prefix=fixed_posterior_indices(state(),FixtureSampler(),"fixture-seed","ALT|BASE",(64,64),4)
    assert prefix==fixed_posterior_indices(state(),FixtureSampler(),"fixture-seed","ALT|BASE",(64,64),4)
    assert prefix==fixed_posterior_indices(state(),FixtureSampler(),"fixture-seed","ALT|BASE",(64,64),6)[:4]

def test_a2_error_key_is_byte_exact_and_target_is_fail_closed():
    context=ErrorContext("seed",7,"confirm_positive_probability","independent_variance",3,"CONFIRM|h|w1",2)
    encoded="H1B_ERROR|seed|7|confirm_positive_probability|independent_variance|3|CONFIRM|h|w1|2".encode()
    expected=1 if hashlib.sha256(encoded).digest()[0] & 1 else -1
    assert error_sign(context)==expected==sign(*error_key("seed",7,"confirm_positive_probability","independent_variance",3,"CONFIRM|h|w1",2))
    with pytest.raises(ValueError): error_sign(ErrorContext("seed",0,"not_a_target","systematic_optimism",0,"x",0))


def test_continuation_return_cache_is_trace_equivalent_and_reuses_values():
    identity = {
        "development_episode_id": "development-0000", "configuration_id": "cache-fixture",
        "method_id": "APPROX_LCB_FALLBACK", "posterior_budget_id": "posterior-4",
        "trajectory_budget_id": "trajectory-4", "error_target": "scan_candidate_yield",
        "error_form": "independent_variance", "error_magnitude": 0.05,
        "error_direction": "STOCHASTIC", "planning_cost_id": "p-2",
        "fallback_variant": "LCB", "attempt_ordinal": 0,
        "canonical_spec_hash": "a" * 64, "implementation_hash": "b" * 64,
        "development_universe_hash": "c" * 64,
    }
    reference = execute_full_horizon(identity, 101)
    cache = ContinuationReturnCache()
    cached_first = execute_full_horizon(identity, 101, continuation_cache=cache)
    cached_second = execute_full_horizon(identity, 101, continuation_cache=cache)
    assert cached_first.trace == reference.trace and cached_first.evaluator == reference.evaluator
    assert cached_second.trace == reference.trace and cached_second.evaluator == reference.evaluator
    assert cache.hits > 0 and cache.misses > 0


def test_complete_identity_hash_binds_every_scientific_axis():
    identity = {
        "development_episode_id": "development-0000", "configuration_id": "identity-fixture",
        "method_id": "APPROX_LCB_FALLBACK", "posterior_budget_id": "posterior-4",
        "trajectory_budget_id": "trajectory-4", "error_target": "scan_candidate_yield",
        "error_form": "independent_variance", "error_magnitude": 0.05,
        "error_direction": "STOCHASTIC", "planning_cost_id": "p-2",
        "fallback_variant": "LCB", "attempt_ordinal": 0,
        "canonical_spec_hash": "a" * 64, "implementation_hash": "b" * 64,
        "development_universe_hash": "c" * 64,
    }
    baseline = identity_hash(identity)
    for field, value in {
        "error_form": "systematic_optimism", "error_magnitude": 0.1,
        "error_direction": "OPTIMISTIC", "planning_cost_id": "p-5",
        "posterior_budget_id": "posterior-16", "fallback_variant": "POINT",
        "canonical_spec_hash": "d" * 64, "implementation_hash": "e" * 64,
        "development_universe_hash": "f" * 64,
    }.items():
        changed = dict(identity); changed[field] = value
        assert identity_hash(changed) != baseline
    incomplete = dict(identity); incomplete.pop("implementation_hash")
    with pytest.raises(ValueError, match="missing-scientific-identity-fields"):
        canonical_identity(incomplete)


def test_smdp_planning_time_is_charged_in_trace_utility_and_postplanning_legality():
    identity = {
        "development_episode_id": "development-0000", "configuration_id": "smdp-fixture",
        "method_id": "APPROX_LCB_FALLBACK", "posterior_budget_id": "posterior-4",
        "trajectory_budget_id": "trajectory-4", "error_target": "scan_candidate_yield",
        "error_form": "independent_variance", "error_magnitude": 0.05,
        "error_direction": "STOCHASTIC", "planning_cost_id": "p-20",
        "fallback_variant": "LCB", "attempt_ordinal": 0,
        "canonical_spec_hash": "a" * 64, "implementation_hash": "b" * 64,
        "development_universe_hash": "c" * 64,
    }
    result = execute_full_horizon(identity, 101)
    elapsed = net_d1 = 0
    for decision, point in zip(result.trace["decisions"], result.trace["utility_timeline"][1:]):
        elapsed += decision["planner"]["planning_time"] + decision["duration"]
        if decision["observation"] == "NEW_COMMIT":
            net_d1 += 1600 - elapsed
        assert point == {"tick": elapsed, "utility": net_d1}
    # The selected fixture has both actual planning and commits, so omission of
    # planning cost would make this equality fail rather than vacuously pass.
    assert any(row["planner"]["planning_time"] for row in result.trace["decisions"])
    assert net_d1 > 0

    initial = visible(R2Environment(finite_world_library()[0]))
    assert all(action.kind != "SCAN" for action in initial.with_remaining(702).legal_actions)
