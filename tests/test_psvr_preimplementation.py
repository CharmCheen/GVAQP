from garc_eval.psvr_preimplementation import Witness, shielded_base_action


def w(h_time=0, h_id="h0", w_time=0, w_id="w0", bound=5, **kwargs):
    return Witness(h_time, h_id, w_time, w_id, bound, **kwargs)


def test_safe_witness_confirms():
    assert shielded_base_action(
        remaining_seconds=5, witnesses=[w()], next_region_id="r0",
        scan_bound_seconds=1, standard_confirm_reserve_seconds=1,
    ) == ("CONFIRM", "h0", "w0")


def test_all_unsafe_witnesses_try_scan():
    assert shielded_base_action(
        remaining_seconds=5, witnesses=[w(bound=6)], next_region_id="r0",
        scan_bound_seconds=2, standard_confirm_reserve_seconds=3,
    ) == ("SCAN", "r0", None)


def test_scan_without_confirm_reserve_stops():
    assert shielded_base_action(
        remaining_seconds=4.9, witnesses=[], next_region_id="r0",
        scan_bound_seconds=2, standard_confirm_reserve_seconds=3,
    ) == ("STOP", None, None)


def test_no_region_no_witness_stops():
    assert shielded_base_action(
        remaining_seconds=100, witnesses=[], next_region_id=None,
        scan_bound_seconds=2, standard_confirm_reserve_seconds=3,
    ) == ("STOP", None, None)


def test_tie_break_is_deterministic_group_then_witness_fifo():
    candidates = [w(1, "h1", 0, "w2"), w(0, "h9", 2, "w1"), w(0, "h9", 1, "w0")]
    assert shielded_base_action(
        remaining_seconds=10, witnesses=candidates, next_region_id=None,
        scan_bound_seconds=None, standard_confirm_reserve_seconds=3,
    ) == ("CONFIRM", "h9", "w0")


def test_forbidden_future_fields_are_rejected():
    try:
        shielded_base_action(
            remaining_seconds=10, witnesses=[], next_region_id=None,
            scan_bound_seconds=None, standard_confirm_reserve_seconds=None,
            visible_state={"future_proxy": [1]},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("future field was silently accepted")


def test_missing_scan_numeric_binding_fails_closed():
    assert shielded_base_action(
        remaining_seconds=100, witnesses=[], next_region_id="r0",
        scan_bound_seconds=None, standard_confirm_reserve_seconds=3,
    ) == ("STOP", None, None)


def test_confirm_identity_includes_hypothesis_when_witness_ids_repeat():
    candidates = [w(1, "h1", 0, "same"), w(0, "h0", 0, "same")]
    assert shielded_base_action(
        remaining_seconds=10, witnesses=candidates, next_region_id=None,
        scan_bound_seconds=None, standard_confirm_reserve_seconds=None,
    ) == ("CONFIRM", "h0", "same")


def test_recursive_latent_leakage_and_invalid_numbers_rejected():
    for kwargs in [
        {"visible_state": {"nested": {"future_cost_draws": [1]}}},
        {"remaining_seconds": float("nan")},
        {"scan_bound_seconds": -1},
    ]:
        base = dict(remaining_seconds=10, witnesses=[], next_region_id="r0",
                    scan_bound_seconds=1, standard_confirm_reserve_seconds=1)
        base.update(kwargs)
        try:
            shielded_base_action(**base)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid input accepted: {kwargs}")
