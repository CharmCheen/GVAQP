import os
import subprocess
import sys
import time

import pytest

import garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor as supervisor
from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import (
    GlobalFailStopCoordinator,
    _read_jsonl,
    signal_global_stop_intent,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor import (
    WorkerProcess,
    _lease_violation,
    _loaded_worker_idle_violation,
    supervise_staged_workers,
    supervise_workers,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_runner import (
    CALL_RESERVATION_WALL_SECONDS,
)
from garc_eval.accelerated_event_query.oracle_v3_manifest import atomic_text


WORKERS = {
    "W0": {"physical_gpu_ids": [1, 2], "unit_ids": ["U0"]},
    "W1": {"physical_gpu_ids": [3, 5], "unit_ids": ["U1"]},
    "W2": {"physical_gpu_ids": [6, 7], "unit_ids": ["U2"]},
}


class FakeProcess:
    def __init__(self, returncode):
        self.returncode = returncode
        self.pid = 999999

    def poll(self):
        return self.returncode


def test_production_call_lease_has_exact_35_second_boundary(tmp_path):
    coordinator = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=WORKERS,
        envelope_a100_gpu_hours=29.0,
        call_reservation_wall_seconds=CALL_RESERVATION_WALL_SECONDS,
        model_load_reservation_wall_seconds=30.0,
    )
    coordinator.initialize()
    coordinator.start_model_load("W0", [1, 2])
    coordinator.complete_model_load("W0", 0.01)
    coordinator.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    reserved = _read_jsonl(tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl")[-1][
        "recorded_at_unix_ns"
    ]
    exact = reserved + int(CALL_RESERVATION_WALL_SECONDS * 1e9)
    assert _lease_violation(tmp_path, exact) is None
    violation = _lease_violation(tmp_path, exact + 1)
    assert violation is not None
    assert violation.startswith("call:U0:")
    assert "limit=35.000000" in violation


def test_abrupt_worker_death_stops_peers_before_another_reservation(
    tmp_path, monkeypatch
):
    coordinator = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=WORKERS,
        envelope_a100_gpu_hours=19.4,
        call_reservation_wall_seconds=23.579961206763983,
        model_load_reservation_wall_seconds=30.0,
    )
    coordinator.initialize()
    coordinator.start_model_load("W0", [1, 2])
    coordinator.complete_model_load("W0", 0.01)
    coordinator.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    processes = [FakeProcess(-9), FakeProcess(None), FakeProcess(None)]

    def terminate_all(_workers):
        for process in processes:
            if process.returncode is None:
                process.returncode = -15

    monkeypatch.setattr(supervisor, "_terminate_all", terminate_all)
    rows = [WorkerProcess(
        worker_id=worker_id,
        gpu_pair=WORKERS[worker_id]["physical_gpu_ids"],
        process=process,
        spawned_at_unix_ns=time.time_ns(),
    ) for worker_id, process in zip(WORKERS, processes)]
    with pytest.raises(RuntimeError, match="abrupt_worker_exit"):
        supervise_workers(
            rows,
            execution_root=tmp_path,
            coordinator=coordinator,
            sleep=lambda _value: None,
        )
    assert coordinator.state()["stop_trigger"] == "post_load_process_fault"
    assert processes[1].poll() == processes[2].poll() == -15
    with pytest.raises(RuntimeError, match="not accepting"):
        coordinator.reserve_call(
            worker_id="W1", gpu_pair=[3, 5], unit_id="U1", call_spec_sha256="b"
        )


def test_staged_supervisor_marks_pending_and_activates_only_after_pair_authentication(
    tmp_path,
):
    rows = [
        {
            "worker_id": worker_id,
            "physical_gpu_ids": binding["physical_gpu_ids"],
        }
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )

    class Coordinator:
        def __init__(self):
            self.exited = []

        def complete_worker_process_exit(self, worker_id):
            self.exited.append(worker_id)

        def mark_complete(self, count):
            assert count == 1475
            atomic_text(
                tmp_path / "GLOBAL_EXECUTION_STATE.json",
                '{"status":"PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS",'
                '"execution_seal_sha256":"' + "s" * 64 + '"}\n',
            )

    attempts = {"W1": 0}
    pair_to_worker = {
        tuple(row["physical_gpu_ids"]): row["worker_id"] for row in rows
    }

    def authenticate(pair):
        worker_id = pair_to_worker[tuple(pair)]
        if worker_id == "W1" and attempts["W1"] == 0:
            attempts["W1"] += 1
            raise RuntimeError("GPU exclusivity/idleness authentication failed: busy")
        return {"authenticated_exclusive_idle": True, "physical_gpu_ids": pair}

    clock = iter(range(0, 100_000_000_000, 11_000_000_000))
    result = supervise_staged_workers(
        schedule,
        execution_root=tmp_path,
        coordinator=Coordinator(),
        initial_worker_id="W0",
        sleep=lambda _value: None,
        now_ns=lambda: next(clock),
        authenticate=authenticate,
        spawn=lambda row: WorkerProcess(
            worker_id=row["worker_id"],
            gpu_pair=row["physical_gpu_ids"],
            process=FakeProcess(0),
            spawned_at_unix_ns=0,
        ),
    )
    events = _read_jsonl(tmp_path / "STAGED_ACTIVATION_LEDGER.jsonl")
    assert result["status"] == "SUPERVISED_PHYSICAL_CALLS_COMPLETE"
    assert [
        row["worker_id"] for row in events
        if row["event"] == "WORKER_PAIR_AUTHENTICATED"
    ] == ["W0", "W2", "W1"]
    assert sum(row["event"] == "WORKER_PENDING_GPU_AUTHENTICATION" for row in events) == 3


def test_staged_initial_pair_race_fails_global_state_closed(tmp_path):
    rows = [
        {"worker_id": worker_id, "physical_gpu_ids": binding["physical_gpu_ids"]}
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )

    with pytest.raises(RuntimeError, match="authentication failed"):
        supervise_staged_workers(
            schedule,
            execution_root=tmp_path,
            coordinator=object(),
            initial_worker_id="W0",
            authenticate=lambda _pair: (_ for _ in ()).throw(
                RuntimeError("GPU exclusivity/idleness authentication failed: race")
            ),
            spawn=lambda _row: pytest.fail("spawn must not occur"),
        )
    state = __import__("json").loads(
        (tmp_path / "GLOBAL_EXECUTION_STATE.json").read_text()
    )
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "authentication_mismatch"


def test_staged_initial_worker_spawn_failure_fails_global_state_closed(tmp_path):
    rows = [
        {"worker_id": worker_id, "physical_gpu_ids": binding["physical_gpu_ids"]}
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )

    with pytest.raises(OSError, match="spawn failed"):
        supervise_staged_workers(
            schedule,
            execution_root=tmp_path,
            coordinator=object(),
            initial_worker_id="W0",
            authenticate=lambda pair: {
                "authenticated_exclusive_idle": True,
                "physical_gpu_ids": pair,
            },
            spawn=lambda _row: (_ for _ in ()).throw(OSError("spawn failed")),
        )
    state = __import__("json").loads(
        (tmp_path / "GLOBAL_EXECUTION_STATE.json").read_text()
    )
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "post_load_process_fault"


def test_staged_pending_worker_cannot_spawn_from_stale_ready_state(tmp_path):
    rows = [
        {"worker_id": worker_id, "physical_gpu_ids": binding["physical_gpu_ids"]}
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )

    class Coordinator:
        def complete_worker_process_exit(self, _worker_id):
            pass

    authentication_count = 0
    spawned = []

    def authenticate(pair):
        nonlocal authentication_count
        authentication_count += 1
        if authentication_count == 2:
            atomic_text(
                tmp_path / "GLOBAL_EXECUTION_STATE.json",
                '{"status":"STOPPED","stop_trigger":"post_load_process_fault",'
                '"model_load_workers":[],"model_load_completed_workers":[]}\n',
            )
        return {"authenticated_exclusive_idle": True, "physical_gpu_ids": pair}

    def spawn(row):
        state = __import__("json").loads(
            (tmp_path / "GLOBAL_EXECUTION_STATE.json").read_text()
        )
        spawned.append((row["worker_id"], state["status"]))
        return WorkerProcess(
            worker_id=row["worker_id"],
            gpu_pair=row["physical_gpu_ids"],
            process=FakeProcess(0),
            spawned_at_unix_ns=0,
        )

    with pytest.raises(RuntimeError, match="before worker spawn"):
        supervise_staged_workers(
            schedule,
            execution_root=tmp_path,
            coordinator=Coordinator(),
            initial_worker_id="W0",
            sleep=lambda _value: None,
            now_ns=lambda: 0,
            authenticate=authenticate,
            spawn=spawn,
        )
    assert spawned == [("W0", "READY")]
    events = _read_jsonl(tmp_path / "STAGED_ACTIVATION_LEDGER.jsonl")
    assert [
        row["worker_id"] for row in events
        if row["event"] == "WORKER_PROCESS_SPAWNED"
    ] == ["W0"]


@pytest.mark.parametrize("terminal_returncode", [-9, 0])
def test_staged_peer_exit_during_pending_auth_prevents_spawn(
    tmp_path, terminal_returncode
):
    rows = [
        {"worker_id": worker_id, "physical_gpu_ids": binding["physical_gpu_ids"]}
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )

    class Coordinator:
        def complete_worker_process_exit(self, _worker_id):
            pass

    initial = FakeProcess(None)
    spawned = []
    authentication_count = 0

    def authenticate(pair):
        nonlocal authentication_count
        authentication_count += 1
        if authentication_count == 2:
            raise RuntimeError("GPU exclusivity/idleness authentication failed: busy")
        if authentication_count == 3:
            initial.returncode = terminal_returncode
        return {"authenticated_exclusive_idle": True, "physical_gpu_ids": pair}

    def spawn(row):
        spawned.append(row["worker_id"])
        return WorkerProcess(
            worker_id=row["worker_id"],
            gpu_pair=row["physical_gpu_ids"],
            process=initial if row["worker_id"] == "W0" else FakeProcess(0),
            spawned_at_unix_ns=0,
        )

    with pytest.raises(RuntimeError, match="terminal_active_worker_exit_before_activation"):
        supervise_staged_workers(
            schedule,
            execution_root=tmp_path,
            coordinator=Coordinator(),
            initial_worker_id="W0",
            sleep=lambda _value: None,
            now_ns=lambda: 0,
            authenticate=authenticate,
            spawn=spawn,
        )
    assert spawned == ["W0"]
    state = __import__("json").loads(
        (tmp_path / "GLOBAL_EXECUTION_STATE.json").read_text()
    )
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "post_load_process_fault"
    events = _read_jsonl(tmp_path / "STAGED_ACTIVATION_LEDGER.jsonl")
    assert [
        row["worker_id"] for row in events
        if row["event"] == "WORKER_PROCESS_SPAWNED"
    ] == ["W0"]


@pytest.mark.parametrize("terminal_returncode", [-9, 0])
def test_staged_peer_exit_during_spawn_kills_uncommitted_child(
    tmp_path, monkeypatch, terminal_returncode
):
    rows = [
        {"worker_id": worker_id, "physical_gpu_ids": binding["physical_gpu_ids"]}
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )

    class Coordinator:
        def complete_worker_process_exit(self, _worker_id):
            pass

    initial = FakeProcess(None)
    candidate = FakeProcess(None)
    terminated = []
    authentication_count = 0

    def terminate_all(workers):
        terminated.extend(worker.worker_id for worker in workers)
        for worker in workers:
            if worker.process.poll() is None:
                worker.process.returncode = -15

    monkeypatch.setattr(supervisor, "_terminate_all", terminate_all)

    def authenticate(pair):
        nonlocal authentication_count
        authentication_count += 1
        if authentication_count == 2:
            raise RuntimeError("GPU exclusivity/idleness authentication failed: busy")
        return {"authenticated_exclusive_idle": True, "physical_gpu_ids": pair}

    def spawn(row):
        if row["worker_id"] == "W0":
            process = initial
        else:
            initial.returncode = terminal_returncode
            process = candidate
        return WorkerProcess(
            worker_id=row["worker_id"],
            gpu_pair=row["physical_gpu_ids"],
            process=process,
            spawned_at_unix_ns=0,
        )

    with pytest.raises(RuntimeError, match="terminal_active_worker_exit_during_activation"):
        supervise_staged_workers(
            schedule,
            execution_root=tmp_path,
            coordinator=Coordinator(),
            initial_worker_id="W0",
            sleep=lambda _value: None,
            now_ns=lambda: 0,
            authenticate=authenticate,
            spawn=spawn,
        )
    assert candidate.returncode == -15
    assert "W2" in terminated
    events = _read_jsonl(tmp_path / "STAGED_ACTIVATION_LEDGER.jsonl")
    assert [
        row["worker_id"] for row in events
        if row["event"] == "WORKER_PROCESS_SPAWNED"
    ] == ["W0"]


def test_staged_stop_intent_during_spawn_kills_uncommitted_child(
    tmp_path, monkeypatch
):
    rows = [
        {"worker_id": worker_id, "physical_gpu_ids": binding["physical_gpu_ids"]}
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )

    class Coordinator:
        def complete_worker_process_exit(self, _worker_id):
            pass

    initial = FakeProcess(None)
    candidate = FakeProcess(None)
    terminated = []
    authentication_count = 0

    def terminate_all(workers):
        terminated.extend(worker.worker_id for worker in workers)
        for worker in workers:
            if worker.process.poll() is None:
                worker.process.returncode = -15

    monkeypatch.setattr(supervisor, "_terminate_all", terminate_all)

    def authenticate(pair):
        nonlocal authentication_count
        authentication_count += 1
        if authentication_count == 2:
            raise RuntimeError("GPU exclusivity/idleness authentication failed: busy")
        return {"authenticated_exclusive_idle": True, "physical_gpu_ids": pair}

    def spawn(row):
        if row["worker_id"] == "W0":
            process = initial
        else:
            signal_global_stop_intent(
                tmp_path, "post_load_process_fault", "peer fault contending"
            )
            process = candidate
        return WorkerProcess(
            worker_id=row["worker_id"],
            gpu_pair=row["physical_gpu_ids"],
            process=process,
            spawned_at_unix_ns=0,
        )

    with pytest.raises(RuntimeError, match="stop intent active during worker spawn"):
        supervise_staged_workers(
            schedule,
            execution_root=tmp_path,
            coordinator=Coordinator(),
            initial_worker_id="W0",
            sleep=lambda _value: None,
            now_ns=lambda: 0,
            authenticate=authenticate,
            spawn=spawn,
        )
    assert candidate.returncode == -15
    assert "W2" in terminated
    events = _read_jsonl(tmp_path / "STAGED_ACTIVATION_LEDGER.jsonl")
    assert [
        row["worker_id"] for row in events
        if row["event"] == "WORKER_PROCESS_SPAWNED"
    ] == ["W0"]


def test_staged_preexisting_activation_ledger_fails_global_state_closed(tmp_path):
    rows = [
        {"worker_id": worker_id, "physical_gpu_ids": binding["physical_gpu_ids"]}
        for worker_id, binding in WORKERS.items()
    ]
    schedule = {
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": "W0",
        "activation_order": ["W0", "W1", "W2"],
        "workers": rows,
    }
    atomic_text(
        tmp_path / "GLOBAL_EXECUTION_STATE.json",
        '{"status":"READY","model_load_workers":[],"model_load_completed_workers":[]}\n',
    )
    from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import append_hash_chain

    append_hash_chain(
        tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl",
        {"event": "RUN_INITIALIZED"},
    )
    atomic_text(tmp_path / "STAGED_ACTIVATION_LEDGER.jsonl", "{malformed\n")

    with pytest.raises(RuntimeError, match="preexisting_staged_activation_ledger"):
        supervise_staged_workers(
            schedule,
            execution_root=tmp_path,
            coordinator=object(),
            initial_worker_id="W0",
            authenticate=lambda _pair: pytest.fail("authentication must not occur"),
            spawn=lambda _row: pytest.fail("spawn must not occur"),
        )
    state = __import__("json").loads(
        (tmp_path / "GLOBAL_EXECUTION_STATE.json").read_text()
    )
    assert state["status"] == "STOPPED"
    assert state["stop_trigger"] == "output_path_collision"


def test_loaded_worker_idle_gap_is_cost_shielded(tmp_path):
    coordinator = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=WORKERS,
        envelope_a100_gpu_hours=19.4,
        call_reservation_wall_seconds=23.579961206763983,
        model_load_reservation_wall_seconds=30.0,
    )
    coordinator.initialize()
    coordinator.start_model_load("W0", [1, 2])
    coordinator.complete_model_load("W0", 0.01)
    rows = _read_jsonl(tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl")
    last = rows[-1]["recorded_at_unix_ns"]
    violation = _loaded_worker_idle_violation(
        tmp_path, running_worker_ids={"W0"}, now_ns=last + 3_000_000_000
    )
    assert violation.startswith("loaded_worker_idle:W0")


def test_closed_but_live_worker_remains_under_idle_lease(tmp_path):
    coordinator = GlobalFailStopCoordinator(
        tmp_path,
        execution_seal_sha256="s" * 64,
        worker_bindings=WORKERS,
        envelope_a100_gpu_hours=19.4,
        call_reservation_wall_seconds=23.579961206763983,
        model_load_reservation_wall_seconds=30.0,
    )
    coordinator.initialize()
    coordinator.start_model_load("W0", [1, 2])
    coordinator.complete_model_load("W0", 0.01)
    coordinator.reserve_call(
        worker_id="W0", gpu_pair=[1, 2], unit_id="U0", call_spec_sha256="a"
    )
    coordinator.complete_call(worker_id="W0", unit_id="U0", wall_seconds=0.01)
    coordinator.complete_worker_session("W0")
    rows = _read_jsonl(tmp_path / "GLOBAL_EXECUTION_LEDGER.jsonl")
    last = rows[-1]["recorded_at_unix_ns"]
    violation = _loaded_worker_idle_violation(
        tmp_path, running_worker_ids={"W0"}, now_ns=last + 3_000_000_000
    )
    assert violation.startswith("loaded_worker_idle:W0")


def test_worker_is_kernel_killed_when_supervisor_parent_exits(tmp_path):
    pid_file = tmp_path / "worker.pid"
    child_code = (
        "import os,time;"
        "from pathlib import Path;"
        "from garc_eval.accelerated_event_query.oracle_v3_full_grid_runner "
        "import install_supervisor_parent_death_signal;"
        "install_supervisor_parent_death_signal();"
        f"Path({str(pid_file)!r}).write_text(str(os.getpid()));"
        "time.sleep(60)"
    )
    parent_code = (
        "import os,subprocess,sys,time;"
        f"pid_file={str(pid_file)!r};"
        "env=os.environ.copy();env['FULL_GRID_SUPERVISOR_PID']=str(os.getpid());"
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}],env=env);"
        "\nfor _ in range(100):\n"
        "  if os.path.exists(pid_file): break\n"
        "  time.sleep(0.02)\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", parent_code],
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
    )
    assert parent.wait(timeout=10) == 0
    worker_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and os.path.exists(f"/proc/{worker_pid}"):
        time.sleep(0.05)
    assert not os.path.exists(f"/proc/{worker_pid}")
