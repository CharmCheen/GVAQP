import os
import subprocess
import sys
import time

import pytest

import garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor as supervisor
from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import (
    GlobalFailStopCoordinator,
    _read_jsonl,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor import (
    WorkerProcess,
    _loaded_worker_idle_violation,
    supervise_workers,
)


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
