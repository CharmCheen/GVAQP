from garc.audit.leakage import audit_public_state
from garc.controller import FixedRatioController, PublicState


def test_future_field_is_rejected():
    state = PublicState(10, estimated_scan_cost_sec=1).to_dict()
    state["future_confirm_outcomes"] = [1]
    controller = FixedRatioController()
    try:
        controller.reset(10, state)
    except ValueError:
        pass
    else:
        raise AssertionError("future information crossed the public boundary")
    assert not audit_public_state(state)["pass"]


def test_exact_public_state_passes():
    assert audit_public_state(PublicState(10).to_dict())["pass"]
