from garc_eval.scan_headroom.trusted_policies import (
    CAUSAL_POLICY_IDS,
    PublicObservation,
    PublicScanState,
    PublicUnit,
    make_policy,
    make_refinement_policy,
)


def state(scanned=()):
    units = tuple(
        PublicUnit(f"u{i}", float(i * 10), float((i + 1) * 10))
        for i in range(9)
    )
    return PublicScanState(units, tuple(scanned), None, 100.0, ())


def test_all_frozen_policies_return_available_units():
    for policy_id in CAUSAL_POLICY_IDS:
        policy = make_policy(policy_id, seed=7)
        first = policy.choose_next_unit(state())
        second = policy.choose_next_unit(state((first,)))
        assert first != second
        assert first.startswith("u") and second.startswith("u")


def test_macro_policy_executes_contiguous_units_after_global_anchor():
    policy = make_policy("MACRO_REGION_LARGEST_GAP")
    first = policy.choose_next_unit(state())
    second = policy.choose_next_unit(state((first,)))
    assert (first, second) == ("u4", "u5")


def test_one_neighbor_refines_only_after_visible_lateral_signal():
    policy = make_refinement_policy("LG_ONE_NEIGHBOR")
    first = policy.choose_next_unit(state())
    base = state((first,))
    observed = PublicScanState(
        base.units, base.scanned_unit_ids, first, base.remaining_budget_sec,
        base.past_action_costs_sec, (), (PublicObservation(first, True),),
    )
    second = policy.choose_next_unit(observed)
    assert (first, second) == ("u4", "u5")
