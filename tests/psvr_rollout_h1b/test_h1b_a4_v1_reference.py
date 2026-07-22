import pytest

from garc_eval.psvr_rollout_h1b.ic1 import execute_full_horizon
from garc_eval.psvr_rollout_h1b_reference import PrimitiveEvidenceError, require_primitive_evidence


def _identity():
    return {"development_episode_id":"development-0000","configuration_id":"v1-fixture","method_id":"APPROX_LCB_FALLBACK","posterior_budget_id":"posterior-4","trajectory_budget_id":"trajectory-4","error_target":"scan_candidate_yield","error_form":"independent_variance","error_magnitude":.05,"error_direction":"STOCHASTIC","planning_cost_id":"p-2","fallback_variant":"LCB","attempt_ordinal":0,"canonical_spec_hash":"a"*64,"implementation_hash":"b"*64,"development_universe_hash":"c"*64}


def test_v1_rejects_current_compact_evidence_without_visible_history_primitives():
    trace = execute_full_horizon(_identity(), 101).trace
    with pytest.raises(PrimitiveEvidenceError, match="missing-trace-primitives:.*primitive_visible_history"):
        require_primitive_evidence(trace)
