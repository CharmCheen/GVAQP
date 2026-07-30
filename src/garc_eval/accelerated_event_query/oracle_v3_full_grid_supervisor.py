"""Fail-closed process supervisor for the three frozen full-grid workers."""

from __future__ import annotations

import fcntl
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
    STOP_INTENT_FILENAME,
    _read_jsonl,
    append_hash_chain,
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
    LOADED_WORKER_IDLE_LEASE_SECONDS,
    MODEL_LOAD_RESERVATION_WALL_SECONDS,
    _coordinator,
    authenticate_gpu_exclusivity,
    initialize_execution,
    validate_compute_approval,
)
from .oracle_v3_manifest import atomic_text, canonical_hash, load_json, sha256_file


POLL_SECONDS = 0.20
STARTUP_LEASE_SECONDS = 120.0
TERMINATION_GRACE_SECONDS = 5.0
PAIR_AUTH_POLL_SECONDS = 10.0


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
    # A closed session must still exit promptly.  Keeping every live loaded
    # worker here closes the final session-close/process-exit window as well.
    loaded = set(state.get("model_load_completed_workers", [])) & running_worker_ids
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
    coordinator: Any,
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
                coordinator.complete_worker_process_exit(worker.worker_id)
                completed.add(worker.worker_id)
            if len(completed) < 3:
                sleep(POLL_SECONDS)
        coordinator.mark_complete(1475)
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


def _spawn_worker(row: dict[str, Any]) -> WorkerProcess:
    pair = row["physical_gpu_ids"]
    environment = os.environ.copy()
    environment["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, pair))
    environment["FULL_GRID_SUPERVISOR_PID"] = str(os.getpid())
    script = ROOT / "scripts/run_accelerated_event_query_oracle_v3_full_grid.py"
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
    return WorkerProcess(
        worker_id=row["worker_id"],
        gpu_pair=pair,
        process=process,
        spawned_at_unix_ns=time.time_ns(),
    )


def _activate_worker_if_globally_ready(
    *,
    execution_root: Path,
    activation_ledger: Path,
    row: dict[str, Any],
    snapshot: dict[str, Any],
    active_peers: list[WorkerProcess],
    spawn: Callable[[dict[str, Any]], WorkerProcess],
) -> WorkerProcess:
    """Linearize process creation before any concurrent global fail-stop.

    Authentication is necessarily outside the coordinator lock.  Reacquiring
    the exact coordinator lock and checking READY immediately before Popen
    prevents a stale loop-top observation from creating a pending worker after
    another worker has stopped the run.  A spawned child blocks on this same
    lock before it can reserve model-load residency.
    """

    lock_path = execution_root / "GLOBAL_EXECUTION.lock"
    worker: WorkerProcess | None = None
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            state = load_json(execution_root / "GLOBAL_EXECUTION_STATE.json")
            if state.get("status") != "READY":
                raise RuntimeError(
                    "global fail-stop active before worker spawn: "
                    f"{row['worker_id']}:{state.get('stop_trigger')}"
                )
            if (execution_root / STOP_INTENT_FILENAME).exists():
                raise RuntimeError(
                    "global fail-stop intent active before worker spawn: "
                    f"{row['worker_id']}"
                )
            failed_peer = _terminal_peer_exit(active_peers)
            if failed_peer is not None:
                raise RuntimeError(
                    "terminal_active_worker_exit_before_activation:"
                    f"{failed_peer[0]}:returncode={failed_peer[1]}"
                )
            append_hash_chain(activation_ledger, {
                "event": "WORKER_PAIR_AUTHENTICATED",
                "worker_id": row["worker_id"],
                "physical_gpu_ids": row["physical_gpu_ids"],
                "snapshot": snapshot,
            })
            worker = spawn(row)
            if (execution_root / STOP_INTENT_FILENAME).exists():
                raise RuntimeError(
                    "global fail-stop intent active during worker spawn: "
                    f"{row['worker_id']}"
                )
            failed_peer = _terminal_peer_exit(active_peers)
            if failed_peer is not None:
                raise RuntimeError(
                    "terminal_active_worker_exit_during_activation:"
                    f"{failed_peer[0]}:returncode={failed_peer[1]}"
                )
            append_hash_chain(activation_ledger, {
                "event": "WORKER_PROCESS_SPAWNED",
                "worker_id": row["worker_id"],
                "physical_gpu_ids": row["physical_gpu_ids"],
                "pid": worker.process.pid,
            })
            return worker
        except BaseException:
            if worker is not None:
                _terminate_all([worker])
            raise
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _terminal_peer_exit(
    active_peers: list[WorkerProcess],
) -> tuple[str, int] | None:
    for peer in active_peers:
        returncode = peer.process.poll()
        if returncode is not None:
            return peer.worker_id, returncode
    return None


def supervise_staged_workers(
    schedule: dict[str, Any],
    *,
    execution_root: Path,
    coordinator: Any,
    initial_worker_id: str,
    sleep: Callable[[float], None] = time.sleep,
    now_ns: Callable[[], int] = time.time_ns,
    authenticate: Callable[[list[int]], dict[str, Any]] = authenticate_gpu_exclusivity,
    spawn: Callable[[dict[str, Any]], WorkerProcess] = _spawn_worker,
) -> dict[str, Any]:
    """Activate frozen workers only when their own exact pair is idle.

    Pending workers have no process and consume no GPU residency.  A failure
    in any activated worker stops the global execution and prevents every
    remaining activation.  Completed shards are retained but never published
    until all three workers exit successfully and the frozen finalizer passes.
    """

    rows = {row["worker_id"]: row for row in schedule["workers"]}
    order = schedule.get("activation_order")
    if (
        schedule.get("activation_mode") != "staged_pair_authentication"
        or order != [row["worker_id"] for row in schedule["workers"]]
        or initial_worker_id != schedule.get("initial_worker_id")
        or set(order) != set(rows)
    ):
        raise ValueError("invalid frozen staged activation schedule")
    active: dict[str, WorkerProcess] = {}
    completed: set[str] = set()
    activation_snapshots: dict[str, dict[str, Any]] = {}
    activation_ledger = execution_root / "STAGED_ACTIVATION_LEDGER.jsonl"
    try:
        if activation_ledger.exists():
            detail = "preexisting_staged_activation_ledger"
            emergency_global_stop(execution_root, "output_path_collision", detail)
            raise RuntimeError(detail)
        for worker_id in order:
            append_hash_chain(activation_ledger, {
                "event": "WORKER_PENDING_GPU_AUTHENTICATION",
                "worker_id": worker_id,
                "physical_gpu_ids": rows[worker_id]["physical_gpu_ids"],
            })
        try:
            activation_snapshots[initial_worker_id] = authenticate(
                rows[initial_worker_id]["physical_gpu_ids"]
            )
        except Exception as exc:
            detail = f"initial_pair_authentication:{initial_worker_id}:{exc}"
            emergency_global_stop(
                execution_root, "authentication_mismatch", detail
            )
            raise RuntimeError(detail) from exc
        active[initial_worker_id] = _activate_worker_if_globally_ready(
            execution_root=execution_root,
            activation_ledger=activation_ledger,
            row=rows[initial_worker_id],
            snapshot=activation_snapshots[initial_worker_id],
            active_peers=[],
            spawn=spawn,
        )
        next_pair_authentication_ns = now_ns()
        while len(completed) < 3:
            state = load_json(execution_root / "GLOBAL_EXECUTION_STATE.json")
            if state.get("status") == "STOPPED":
                _terminate_all(list(active.values()))
                raise RuntimeError(f"global fail-stop active: {state.get('stop_trigger')}")
            current_ns = now_ns()
            lease = _lease_violation(execution_root, current_ns)
            if lease is not None:
                emergency_global_stop(execution_root, "cost_envelope_exceeded", lease)
                _terminate_all(list(active.values()))
                raise RuntimeError(f"worker operation exceeded sealed lease: {lease}")
            running_ids = {
                worker_id for worker_id, worker in active.items()
                if worker.process.poll() is None
            }
            idle = _loaded_worker_idle_violation(
                execution_root, running_worker_ids=running_ids, now_ns=current_ns
            )
            if idle is not None:
                emergency_global_stop(execution_root, "cost_envelope_exceeded", idle)
                _terminate_all(list(active.values()))
                raise RuntimeError(f"loaded worker exceeded idle lease: {idle}")
            started = set(state.get("model_load_workers", []))
            for worker_id, worker in list(active.items()):
                returncode = worker.process.poll()
                if returncode is None:
                    if (
                        worker_id not in started
                        and (current_ns - worker.spawned_at_unix_ns) / 1e9
                        > STARTUP_LEASE_SECONDS
                    ):
                        detail = f"startup_lease:{worker_id}"
                        emergency_global_stop(
                            execution_root, "post_load_process_fault", detail
                        )
                        _terminate_all(list(active.values()))
                        raise RuntimeError(detail)
                    continue
                if worker_id in completed:
                    continue
                if returncode != 0:
                    detail = f"abrupt_worker_exit:{worker_id}:returncode={returncode}"
                    emergency_global_stop(
                        execution_root, "post_load_process_fault", detail
                    )
                    _terminate_all(list(active.values()))
                    raise RuntimeError(detail)
                coordinator.complete_worker_process_exit(worker_id)
                completed.add(worker_id)
                append_hash_chain(activation_ledger, {
                    "event": "WORKER_PROCESS_EXITED_ZERO",
                    "worker_id": worker_id,
                    "physical_gpu_ids": rows[worker_id]["physical_gpu_ids"],
                })
            if current_ns >= next_pair_authentication_ns:
                for worker_id in order:
                    if worker_id in active:
                        continue
                    try:
                        snapshot = authenticate(rows[worker_id]["physical_gpu_ids"])
                    except RuntimeError as exc:
                        if "GPU exclusivity/idleness authentication failed" in str(exc):
                            continue
                        detail = f"pending_pair_authentication:{worker_id}:{exc}"
                        emergency_global_stop(
                            execution_root, "authentication_mismatch", detail
                        )
                        _terminate_all(list(active.values()))
                        raise RuntimeError(detail) from exc
                    activation_snapshots[worker_id] = snapshot
                    active[worker_id] = _activate_worker_if_globally_ready(
                        execution_root=execution_root,
                        activation_ledger=activation_ledger,
                        row=rows[worker_id],
                        snapshot=snapshot,
                        active_peers=[
                            peer for peer_id, peer in active.items()
                            if peer_id not in completed
                        ],
                        spawn=spawn,
                    )
                next_pair_authentication_ns = current_ns + int(
                    PAIR_AUTH_POLL_SECONDS * 1e9
                )
            if len(completed) < 3:
                sleep(POLL_SECONDS)
        coordinator.mark_complete(1475)
        state = load_json(execution_root / "GLOBAL_EXECUTION_STATE.json")
        if state.get("status") != "PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS":
            emergency_global_stop(
                execution_root, "integrity_mismatch",
                "all staged workers exited zero before complete global state",
            )
            raise RuntimeError("staged workers exited without complete global state")
        return {
            "status": "SUPERVISED_PHYSICAL_CALLS_COMPLETE",
            "worker_returncodes": {
                worker_id: active[worker_id].process.poll() for worker_id in order
            },
            "activation_snapshots": activation_snapshots,
            "execution_seal_sha256": state["execution_seal_sha256"],
        }
    except BaseException as exc:
        try:
            emergency_global_stop(
                execution_root,
                "post_load_process_fault",
                f"staged_supervisor:{type(exc).__name__}:{exc}",
            )
        finally:
            _terminate_all(list(active.values()))
        raise


def launch_supervised_execution(execution_root: Path = EXECUTION) -> dict[str, Any]:
    """Approval-gated staged launcher for the exact three frozen workers."""

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
        "activation_mode": "staged_pair_authentication",
        "initial_worker_id": schedule["initial_worker_id"],
    }
    authority["supervisor_authority_payload_sha256"] = canonical_hash(authority)
    atomic_text(
        execution_root / "SUPERVISOR_LAUNCH_AUTHORITY.json",
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
    )
    coordinator = _coordinator(schedule, sha256_file(SEAL), execution_root)
    result = supervise_staged_workers(
        schedule,
        execution_root=execution_root,
        coordinator=coordinator,
        initial_worker_id=schedule["initial_worker_id"],
    )
    audit = {
        **result,
        "initialization_payload_sha256": initialization[
            "initialization_payload_sha256"
        ],
        "supervisor_source_sha256": sha256_file(Path(__file__)),
        "dynamic_reassignment": False,
        "activation_mode": "staged_pair_authentication",
        "retry_count": 0,
    }
    audit["supervisor_audit_payload_sha256"] = canonical_hash(audit)
    atomic_text(
        execution_root / "SUPERVISOR_AUDIT.json",
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
    )
    return audit
