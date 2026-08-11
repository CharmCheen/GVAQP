import pytest

from garc_eval.accelerated_event_query.state import RuntimePublicState, validate_public_state


def minimal_state() -> dict:
    return RuntimePublicState(
        total_budget_sec=60.0,
        remaining_budget_sec=50.0,
        remaining_budget_fraction=5 / 6,
        scan_cost_estimate=1.0,
        scan_cost_upper=2.0,
        verify_cost_estimate=20.0,
        verify_cost_upper=45.0,
        estimated_remaining_scan_slots=25,
        estimated_remaining_verify_slots=1,
        scan_then_verify_slack=3.0,
        coverage_fraction=0.1,
        largest_unscanned_gap=100.0,
        number_of_unscanned_regions=9,
        recent_scan_region_yield=1.0,
        estimated_unexplored_event_mass=0.5,
        frontier_size=1,
    ).to_dict()


def test_public_state_accepts_complete_causal_schema():
    validate_public_state(minimal_state())


@pytest.mark.parametrize("field", [
    "unverified_32b_labels", "unscanned_candidates", "future_action_costs",
    "reference_events", "future_k3_results", "final_recall", "final_precision",
])
def test_public_state_rejects_future_or_evaluator_information(field):
    value = minimal_state()
    value[field] = 1
    with pytest.raises(ValueError, match="boundary violation"):
        validate_public_state(value)
