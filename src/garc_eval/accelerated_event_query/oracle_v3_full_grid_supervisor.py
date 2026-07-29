"""Fail-closed process supervisor for the three frozen full-grid workers."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .oracle_v3_full_grid_control import (
    _read_jsonl,
    emergency_global_stop,
)
from .oracle_v3_full_grid_package import (
    EXECUTION,
    ROOT,
    SCHEDULE,
    SEAL,
    validate_execution_seal,
)
from .oracle_v3_full_grid_runner import (
    CALL_RESERVATION_WALL_SECONDS,
    MODEL_LOAD_RESERVATION_WALL_SECONDS,
    initialize_execution,
    validate_compute_approval,
)
from .oracle_v3_manifest import atomic_text, canonical_hash, load_json, sha256_file


POLL_SECONDS = 0.20
STARTUP_LEASE_SECONDS = 120.0
TERMINATION_GRACE_SECONDS = 5.0
LOADED_WORKER_IDLE_LEASE_SECONDS = 2.0


@dataclass
class WorkerProcess:
    worker_id: str
    gpu_pair: list[int]
    process: Any
    spawned_at_unix_ns: int


def _open_operations(execution_root: Path) -> dict[tuple[str, str], int]:
    """Return reserved operations that lack a terminal transition."""

    rows = _read_jsonl(execution_root / "GLOBAL_EXECUTION_LEDGER.jsonl")
    opened: dict[tuple[str, str], int] = {}
    for row in rows:
        event = row.get("event")
        if event == "MODEL_LOAD_STARTED":
            opened[("load", row["worker_id"])] = row["recorded_at_unix_ns"]
        elif event == "MODEL_LOAD_COMPLETED":
            opened.pop(("load", row["worker_id"]), None)
        elif event == "CALL_RESERVED":
            opened[("call", row["unit_id"])] = row["recorded_at_unix_ns"]
        elif event == "CALL_COMPLETED":
            opened.pop(("call", row["unit_id"]), None)
    return opened


def _lease_violation(execution_root: Path, now_ns: int) -> str | None:
    for (kind, identity), started_ns in _open_operations(execution_root).items():
        limit = (
            MODEL_LOAD_RESERVATION_WALL_SECONDS
            if kind == "load" else CALL_RESERVATION_WALL_SECONDS
        )
        elapsed = (now_ns - started_ns) / 1e9
        if elapsed > limit:
            return f"{kind}:{identity}:elapsed={elapsed:.6f}:limit={limit:.6f}"
    return None


def _loaded_worker_idle_violation(
    execution_root: Path,
    *,
    running_worker_ids: set[str],
    now_ns: int,
) -> str | None:
    """Cover every GPU-loaded gap not represented by an open operation."""

    state = load_json(execution_root / "GLOBAL_EXECUTION_STATE.json")
    loaded = (
        set(state.get("model_load_completed_workers", []))
        - set(state.get("worker_sessions_completed", []))
    ) & running_worker_ids
    if not loaded:
        return None
    rows = _read_jsonl(execution_root / "GLOBAL_EXECUTION_LEDGER.jsonl")
    last_activity: dict[str, int] = {}
    open_workers: set[str] = set()
    call_worker: dict[str, str] = {}
    for row in rows:
        event = row.get("event")
        worker_id = row.get("worker_id")
        if isinstance(worker_id, str):
            last_activity[worker_id] = row["recorded_at_unix_ns"]
        if event == "MODEL_LOAD_STARTED":
            open_workers.add(row["worker_id"])
        elif event == "MODEL_LOAD_COMPLETED":
            open_workers.discard(row["worker_id"])
        elif event == "CALL_RESERVED":
            call_worker[row["unit_id"]] = row["worker_id"]
            open_workers.add(row["worker_id"])
        elif event == "CALL_COMPLETED":
            owner = call_worker.pop(row["unit_id"], row.get("worker_id"))
            if owner is not None:
                open_workers.discard(owner)
    for worker_id in sorted(loaded - open_workers):
        timestamp = last_activity.get(worker_id)
        if timestamp is None:
            return f"loaded_worker_without_activity:{worker_id}"
        elapsed = (now_ns - timestamp) / 1e9
        if elapsed > LOADED_WORKER_IDLE_LEASE_SECONDS:
            return (
                f"loaded_worker_idle:{worker_id}:elapsed={elapsed:.6f}:"
                f"limit={LOADED_WORKER_IDLE_LEASE_SECONDS:.6f}"
            )
    return None


def _terminate_all(workers: list[WorkerProcess]) -> None:
    for worker in workers:
        if worker.process.poll() is None:
            try:
                os.killpg(worker.process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                worker.process.terminate()
    deadline = time.monotonic() + TERMINATION_GRACE_SECONDS
    while time.monotonic() < deadline and any(
        worker.process.poll() is None for worker in workers
    ):
        time.sleep(min(POLL_SECONDS, max(0.0, deadline - time.monotonic())))
    for worker in workers:
        if worker.process.poll() is None:
            try:
                os.killpg(worker.process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                worker.process.kill()


def supervise_workers(
    workers: list[WorkerProcess],
    *,
    execution_root: Path,
    sleep: Callable[[float], None] = time.sleep,
    now_ns: Callable[[], int] = time.time_ns,
) -> dict[str, Any]:
    """Monitor exact workers; any nonzero death stops and kills all peers."""

    if len(workers) != 3 or len({row.worker_id for row in workers}) != 3:
        raise ValueError("supervisor requires exactly three unique workers")
    completed: set[str] = set()
    try:
        while len(completed) < 3:
            state = load_json(execution_root / "GLOBAL_EXECUTION_STATE.json")
            if state.get("status") == "STOPPED":
                _terminate_all(workers)
                raise RuntimeError(f"global fail-stop active: {state.get('stop_trigger')}")
            current_ns = now_ns()
            lease = _lease_violation(execution_root, current_ns)
            if lease is not None:
                emergency_global_stop(execution_root, "cost_envelope_exceeded", lease)
                _terminate_all(workers)
                raise RuntimeError(f"worker operation exceeded sealed lease: {lease}")
            running_ids = {
                worker.worker_id for worker in workers
                if worker.process.poll() is None
            }
            idle = _loaded_worker_idle_violation(
                execution_root,
                running_worker_ids=running_ids,
                now_ns=current_ns,
            )
            if idle is not None:
                emergency_global_stop(
                    execution_root, "cost_envelope_exceeded", idle
                )
                _terminate_all(workers)
                raise RuntimeError(f"loaded worker exceeded idle lease: {idle}")
            started = set(state.get("model_load_workers", []))
            for worker in workers:
                returncode = worker.process.poll()
                if returncode is None:
                    if (
                        worker.worker_id not in started
                        and (current_ns - worker.spawned_at_unix_ns) / 1e9
                        > STARTUP_LEASE_SECONDS
                    ):
                        detail = f"startup_lease:{worker.worker_id}"
                        emergency_global_stop(
                            execution_root, "post_load_process_fault", detail
                        )
                        _terminate_all(workers)
                        raise RuntimeError(detail)
                    continue
                if worker.worker_id in completed:
                    continue
                if returncode != 0:
                    detail = f"abrupt_worker_exit:{worker.worker_id}:returncode={returncode}"
                    emergency_global_stop(
                        execution_root, "post_load_process_fault", detail
                    )
                    _terminate_all(workers)
                    raise RuntimeError(detail)
                completed.add(worker.worker_id)
            if len(completed) < 3:
                sleep(POLL_SECONDS)
        state = load_json(execution_root / "GLOBAL_EXECUTION_STATE.json")
        if state.get("status") != "PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS":
            emergency_global_stop(
                execution_root,
                "integrity_mismatch",
                "all workers exited zero before complete global state",
            )
            raise RuntimeError("workers exited without complete global state")
        return {
            "status": "SUPERVISED_PHYSICAL_CALLS_COMPLETE",
            "worker_returncodes": {
                worker.worker_id: worker.process.poll() for worker in workers
            },
            "execution_seal_sha256": state["execution_seal_sha256"],
        }
    except BaseException:
        _terminate_all(workers)
        raise


def launch_supervised_execution(execution_root: Path = EXECUTION) -> dict[str, Any]:
    """Approval-gated sole production launcher for the exact three workers."""

    validate_execution_seal("supervisor")
    validate_compute_approval()
    if execution_root.exists():
        raise RuntimeError("execution root already exists; resume is forbidden")
    initialization = initialize_execution(execution_root)
    schedule = load_json(SCHEDULE)
    authority = {
        "status": "SUPERVISOR_AUTHORIZED_EXACT_WORKER_LAUNCH",
        "execution_seal_sha256": sha256_file(SEAL),
        "supervisor_pid": os.getpid(),
        "worker_ids": [row["worker_id"] for row in schedule["workers"]],
    }
    authority["supervisor_authority_payload_sha256"] = canonical_hash(authority)
    atomic_text(
        execution_root / "SUPERVISOR_LAUNCH_AUTHORITY.json",
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
    )
    script = ROOT / "scripts/run_accelerated_event_query_oracle_v3_full_grid.py"
    workers: list[WorkerProcess] = []
    for row in schedule["workers"]:
        pair = row["physical_gpu_ids"]
        environment = os.environ.copy()
        environment["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, pair))
        environment["FULL_GRID_SUPERVISOR_PID"] = str(os.getpid())
        process = subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--execute-worker",
                row["worker_id"],
                "--declared-physical-gpus",
                ",".join(map(str, pair)),
            ],
            cwd=ROOT,
            env=environment,
            start_new_session=True,
        )
        workers.append(WorkerProcess(
            worker_id=row["worker_id"],
            gpu_pair=pair,
            process=process,
            spawned_at_unix_ns=time.time_ns(),
        ))
    result = supervise_workers(workers, execution_root=execution_root)
    audit = {
        **result,
        "initialization_payload_sha256": initialization[
            "initialization_payload_sha256"
        ],
        "supervisor_source_sha256": sha256_file(Path(__file__)),
        "dynamic_reassignment": False,
        "retry_count": 0,
    }
    audit["supervisor_audit_payload_sha256"] = canonical_hash(audit)
    atomic_text(
        execution_root / "SUPERVISOR_AUDIT.json",
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
    )
    return audit
