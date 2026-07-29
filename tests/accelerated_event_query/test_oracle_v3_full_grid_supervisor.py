import time

import pytest

import garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor as supervisor
from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import (
    GlobalFailStopCoordinator,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor import (
    WorkerProcess,
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
        supervise_workers(rows, execution_root=tmp_path, sleep=lambda _value: None)
    assert coordinator.state()["stop_trigger"] == "post_load_process_fault"
    assert processes[1].poll() == processes[2].poll() == -15
    with pytest.raises(RuntimeError, match="not accepting"):
        coordinator.reserve_call(
            worker_id="W1", gpu_pair=[3, 5], unit_id="U1", call_spec_sha256="b"
        )
