from pathlib import Path

import pytest

from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import (
    GlobalFailStopCoordinator,
    emergency_global_stop,
)


WORKERS = {
    "W0": {"physical_gpu_ids": [1, 2], "unit_ids": ["U0", "U1"]},
    "W1": {"physical_gpu_ids": [3, 5], "unit_ids": ["U2"]},
    "W2": {"physical_gpu_ids": [6, 7], "unit_ids": ["U3"]},
}


def coordinator(tmp_path: Path, *, envelope: float = 19.4):
    return GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=WORKERS,
        envelope_a100_gpu_hours=envelope,
        call_reservation_wall_seconds=23.5,
        model_load_reservation_wall_seconds=30.0,
    )


def loaded(coordinator):
    coordinator.initialize()
    coordinator.start_model_load("W0", [1, 2])
    coordinator.complete_model_load("W0", 1.0)
    return coordinator


def test_duplicate_attempt_stops_all_future_calls(tmp_path):
    value = loaded(coordinator(tmp_path))
    value.reserve_call(worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a")
    with pytest.raises(RuntimeError, match="duplicate"):
        value.reserve_call(worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a")
    assert value.state()["stop_trigger"] == "duplicate_unit_attempt"
    with pytest.raises(RuntimeError, match="not accepting"):
        value.reserve_call(worker_id="W0", gpu_pair=[1, 2], unit_id="U1", call_spec_sha256="b")


def test_reload_and_resume_are_forbidden(tmp_path):
    value = loaded(coordinator(tmp_path))
    with pytest.raises(RuntimeError, match="reload"):
        value.start_model_load("W0", [1, 2])
    assert value.state()["stop_trigger"] == "unauthorized_model_reload"
    with pytest.raises(RuntimeError, match="resume"):
        value.initialize()


def test_gpu_mismatch_and_cost_reservation_fail_closed(tmp_path):
    wrong = coordinator(tmp_path / "gpu")
    wrong.initialize()
    with pytest.raises(RuntimeError, match="GPU"):
        wrong.start_model_load("W0", [0, 7])
    assert wrong.state()["stop_trigger"] == "gpu_binding_mismatch"
    cost = coordinator(tmp_path / "cost", envelope=0.001)
    cost.initialize()
    with pytest.raises(RuntimeError, match="cost"):
        cost.start_model_load("W0", [1, 2])
    assert cost.state()["stop_trigger"] == "cost_envelope_exceeded"


def test_only_exact_complete_accounting_can_reach_terminal_complete(tmp_path):
    value = loaded(coordinator(tmp_path))
    value.reserve_call(worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a")
    value.complete_call(worker_id="W0", unit_id="U0", wall_seconds=1.0)
    with pytest.raises(RuntimeError, match="incomplete"):
        value.mark_complete(4)
    assert value.state()["status"] == "STOPPED"


def test_emergency_stop_covers_post_initialization_validation_failure(tmp_path):
    value = coordinator(tmp_path)
    value.initialize()
    emergency_global_stop(tmp_path, "authentication_mismatch", "source changed")
    assert value.state()["status"] == "STOPPED"
    assert value.state()["stop_trigger"] == "authentication_mismatch"
