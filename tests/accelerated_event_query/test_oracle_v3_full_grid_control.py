from pathlib import Path
import json
import time

import pytest

from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import (
    GlobalFailStopCoordinator,
    emergency_global_stop,
    signal_global_stop_intent,
)
import garc_eval.accelerated_event_query.oracle_v3_full_grid_control as control


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


@pytest.mark.parametrize(
    "ordinary,process_exit,emergency",
    [(0.0, 8.0, 8.0), (3.0, 2.0, 8.0), (2.0, 9.0, 8.0)],
)
def test_loaded_worker_lease_hierarchy_fails_closed_at_construction(
    tmp_path, ordinary, process_exit, emergency
):
    with pytest.raises(ValueError, match="ordinary idle <= process exit"):
        GlobalFailStopCoordinator(
            tmp_path,
            execution_seal_sha256="s" * 64,
            worker_bindings=WORKERS,
            envelope_a100_gpu_hours=44.4,
            call_reservation_wall_seconds=52.0,
            model_load_reservation_wall_seconds=30.0,
            loaded_worker_idle_lease_wall_seconds=ordinary,
            loaded_worker_process_exit_lease_wall_seconds=process_exit,
            loaded_worker_emergency_reservation_wall_seconds=emergency,
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


def test_stop_intent_preempts_model_load_before_state_stop_commits(tmp_path):
    value = coordinator(tmp_path)
    value.initialize()
    signal_global_stop_intent(tmp_path, "post_load_process_fault", "peer failed")
    with pytest.raises(RuntimeError, match="stop intent"):
        value.start_model_load("W2", [6, 7])
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["model_load_workers"] == []
    events = [
        json.loads(line)
        for line in value.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event"] for row in events] == [
        "RUN_INITIALIZED", "GLOBAL_FAIL_STOP"
    ]


def test_redundant_trigger_stop_is_idempotent_and_preserves_first_failure(tmp_path):
    value = coordinator(tmp_path)
    value.initialize()
    value.trigger_stop("authentication_mismatch", "first")
    value.trigger_stop("post_load_process_fault", "later generic exception")
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "authentication_mismatch"
    events = [
        json.loads(line)
        for line in value.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event"] for row in events] == [
        "RUN_INITIALIZED", "GLOBAL_FAIL_STOP"
    ]


def test_first_stop_intent_controls_later_state_and_ledger_commit(tmp_path):
    value = coordinator(tmp_path)
    value.initialize()
    signal_global_stop_intent(tmp_path, "authentication_mismatch", "specific first")
    value.trigger_stop("post_load_process_fault", "later generic wrapper")
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "authentication_mismatch"
    assert state["stop_detail"] == "stop_intent:specific first"
    events = [
        json.loads(line)
        for line in value.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    stop = [row for row in events if row["event"] == "GLOBAL_FAIL_STOP"]
    assert len(stop) == 1
    assert stop[0]["trigger"] == "authentication_mismatch"
    assert stop[0]["detail"] == "stop_intent:specific first"


def test_first_stop_intent_controls_later_emergency_commit(tmp_path):
    value = coordinator(tmp_path)
    value.initialize()
    signal_global_stop_intent(tmp_path, "authentication_mismatch", "specific first")
    emergency_global_stop(tmp_path, "post_load_process_fault", "later wrapper")
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "authentication_mismatch"
    events = [
        json.loads(line)
        for line in value.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    stop = [row for row in events if row["event"] == "GLOBAL_FAIL_STOP"]
    assert len(stop) == 1
    assert stop[0]["trigger"] == "authentication_mismatch"


def test_malformed_first_stop_intent_commits_integrity_failure(tmp_path):
    value = coordinator(tmp_path)
    value.initialize()
    (tmp_path / "GLOBAL_FAIL_STOP_INTENT.json").write_text(
        "{malformed\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="stop intent"):
        value.start_model_load("W2", [6, 7])
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "integrity_mismatch"
    assert state["model_load_workers"] == []
    events = [
        json.loads(line)
        for line in value.ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    stop = [row for row in events if row["event"] == "GLOBAL_FAIL_STOP"]
    assert len(stop) == 1
    assert stop[0]["trigger"] == "integrity_mismatch"


def test_three_closed_worker_sessions_are_required_for_complete_state(tmp_path):
    value = coordinator(tmp_path)
    value.initialize()
    for worker_id, binding in WORKERS.items():
        value.start_model_load(worker_id, binding["physical_gpu_ids"])
        value.complete_model_load(worker_id, 0.01)
        for unit_id in binding["unit_ids"]:
            value.reserve_call(
                worker_id=worker_id,
                gpu_pair=binding["physical_gpu_ids"],
                unit_id=unit_id,
                call_spec_sha256=unit_id,
            )
            value.complete_call(
                worker_id=worker_id, unit_id=unit_id, wall_seconds=0.01
            )
        value.complete_worker_session(worker_id)
        value.complete_worker_process_exit(worker_id)
    value.mark_complete(4)
    state = value.state()
    assert state["status"] == "PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS"
    assert set(state["worker_sessions_completed"]) == set(WORKERS)
    assert set(state["worker_processes_exited"]) == set(WORKERS)
    assert state["reserved_gpu_seconds"] == pytest.approx(0.0)


def test_idle_cost_is_accounted_before_next_call_reservation(tmp_path, monkeypatch):
    value = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=WORKERS,
        envelope_a100_gpu_hours=78.0 / 3600.0,
        call_reservation_wall_seconds=23.5,
        model_load_reservation_wall_seconds=30.0,
        loaded_worker_idle_lease_wall_seconds=8.0,
        loaded_worker_emergency_reservation_wall_seconds=8.0,
    )
    value.initialize()
    value.start_model_load("W0", [1, 2])
    value.complete_model_load("W0", 1.0)
    previous = value.state()["last_gpu_accounted_unix_ns_by_worker"]["W0"]
    monkeypatch.setattr(control.time, "time_ns", lambda: previous + 8_000_000_000)
    with pytest.raises(RuntimeError, match="cost reservation"):
        value.reserve_call(
            worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
        )
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["actual_gpu_seconds"] <= state["envelope_gpu_seconds"]
    assert state["attempted_unit_ids"] == []


def test_atomic_idle_lease_rejects_missed_supervisor_poll_before_next_call(
    tmp_path, monkeypatch
):
    """An over-limit closed gap cannot disappear between supervisor polls."""

    value = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=WORKERS,
        envelope_a100_gpu_hours=44.4,
        call_reservation_wall_seconds=52.0,
        model_load_reservation_wall_seconds=30.0,
        loaded_worker_idle_lease_wall_seconds=2.0,
        loaded_worker_emergency_reservation_wall_seconds=8.0,
    )
    value.initialize()
    value.start_model_load("W0", [1, 2])
    value.complete_model_load("W0", 0.01)
    previous = value.state()["last_gpu_accounted_unix_ns_by_worker"]["W0"]
    monkeypatch.setattr(control.time, "time_ns", lambda: previous + 3_000_000_000)
    with pytest.raises(RuntimeError, match="idle exceeded sealed lease"):
        value.reserve_call(
            worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
        )
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "cost_envelope_exceeded"
    assert state["attempted_unit_ids"] == []
    assert state["in_flight_unit_ids"] == []


def test_atomic_idle_lease_covers_terminal_gap_transitions(
    tmp_path, monkeypatch
):
    one_worker = {
        "W0": {"physical_gpu_ids": [1, 2], "unit_ids": ["U0"]}
    }
    value = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=one_worker,
        envelope_a100_gpu_hours=44.4,
        call_reservation_wall_seconds=52.0,
        model_load_reservation_wall_seconds=30.0,
        loaded_worker_idle_lease_wall_seconds=2.0,
        loaded_worker_emergency_reservation_wall_seconds=8.0,
    )
    value.initialize()
    value.start_model_load("W0", [1, 2])
    value.complete_model_load("W0", 0.01)
    value.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    value.complete_call(worker_id="W0", unit_id="U0", wall_seconds=0.01)
    previous = value.state()["last_gpu_accounted_unix_ns_by_worker"]["W0"]
    monkeypatch.setattr(control.time, "time_ns", lambda: previous + 3_000_000_000)
    with pytest.raises(RuntimeError, match="idle exceeded sealed lease"):
        value.complete_worker_session("W0")
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "cost_envelope_exceeded"
    assert state["worker_sessions_completed"] == []


@pytest.mark.parametrize("elapsed_ns", [2_073_427_000, 8_000_000_000])
def test_process_exit_lease_accepts_v5_observation_and_exact_boundary(
    tmp_path, monkeypatch, elapsed_ns
):
    one_worker = {
        "W0": {"physical_gpu_ids": [1, 2], "unit_ids": ["U0"]}
    }
    value = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=one_worker,
        envelope_a100_gpu_hours=44.4,
        call_reservation_wall_seconds=52.0,
        model_load_reservation_wall_seconds=30.0,
        loaded_worker_idle_lease_wall_seconds=2.0,
        loaded_worker_process_exit_lease_wall_seconds=8.0,
        loaded_worker_emergency_reservation_wall_seconds=8.0,
    )
    value.initialize()
    value.start_model_load("W0", [1, 2])
    value.complete_model_load("W0", 0.01)
    value.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    value.complete_call(worker_id="W0", unit_id="U0", wall_seconds=0.01)
    value.complete_worker_session("W0")
    previous = value.state()["last_gpu_accounted_unix_ns_by_worker"]["W0"]
    monkeypatch.setattr(control.time, "time_ns", lambda: previous + elapsed_ns)
    value.complete_worker_process_exit("W0")
    assert value.state()["worker_processes_exited"] == ["W0"]


def test_process_exit_lease_rejects_above_eight_seconds(tmp_path, monkeypatch):
    one_worker = {
        "W0": {"physical_gpu_ids": [1, 2], "unit_ids": ["U0"]}
    }
    value = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=one_worker,
        envelope_a100_gpu_hours=44.4,
        call_reservation_wall_seconds=52.0,
        model_load_reservation_wall_seconds=30.0,
        loaded_worker_idle_lease_wall_seconds=2.0,
        loaded_worker_process_exit_lease_wall_seconds=8.0,
        loaded_worker_emergency_reservation_wall_seconds=8.0,
    )
    value.initialize()
    value.start_model_load("W0", [1, 2])
    value.complete_model_load("W0", 0.01)
    value.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    value.complete_call(worker_id="W0", unit_id="U0", wall_seconds=0.01)
    value.complete_worker_session("W0")
    previous = value.state()["last_gpu_accounted_unix_ns_by_worker"]["W0"]
    monkeypatch.setattr(control.time, "time_ns", lambda: previous + 8_000_000_001)
    with pytest.raises(RuntimeError, match="process exit exceeded sealed lease"):
        value.complete_worker_process_exit("W0")
    state = value.state()
    assert state["status"] == "STOPPED"
    assert state["worker_processes_exited"] == []


def test_atomic_idle_lease_accepts_exact_two_second_boundary(tmp_path, monkeypatch):
    value = loaded(coordinator(tmp_path))
    previous = value.state()["last_gpu_accounted_unix_ns_by_worker"]["W0"]
    monkeypatch.setattr(control.time, "time_ns", lambda: previous + 2_000_000_000)
    value.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    state = value.state()
    assert state["status"] == "READY"
    assert state["attempted_unit_ids"] == ["U0"]


def test_complete_call_accounts_coordinator_state_read_gap(tmp_path, monkeypatch):
    """Regression for the rejected-v6 post-caller-timer accounting hole."""

    value = loaded(coordinator(tmp_path))
    value.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    original_state = value.state
    before = original_state()["actual_gpu_seconds"]

    def delayed_state():
        result = original_state()
        time.sleep(0.03)
        return result

    monkeypatch.setattr(value, "state", delayed_state)
    value.complete_call(worker_id="W0", unit_id="U0", wall_seconds=0.0)
    after = original_state()["actual_gpu_seconds"]
    assert after - before >= 0.05  # two GPUs times at least 25 ms
    completed = [
        json.loads(line)
        for line in value.ledger_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["event"] == "CALL_COMPLETED"
    ][0]
    assert completed["caller_observed_wall_seconds"] == 0.0
    assert completed["accounted_wall_seconds"] >= 0.025
