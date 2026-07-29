"""Global fail-stop, zero-retry, and cost accounting for V3 full-grid execution."""

from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path
from typing import Any

from .oracle_v3_manifest import atomic_text, canonical_hash, load_json


FAIL_STOP_TRIGGERS = {
    "authentication_mismatch",
    "frame_hash_mismatch",
    "processed_input_identity_mismatch",
    "unauthorized_model_reload",
    "duplicate_unit_attempt",
    "missing_attempt_ledger_transition",
    "extra_call",
    "retry",
    "gpu_binding_mismatch",
    "output_path_collision",
    "parser_implementation_mismatch",
    "unknown_runner_version",
    "cost_envelope_exceeded",
    "generation_failed",
    "uncertain_interruption",
    "post_load_process_fault",
    "integrity_mismatch",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    previous = None
    for row in rows:
        claimed = row.get("event_sha256")
        unsigned = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("previous_event_sha256") != previous or claimed != canonical_hash(unsigned):
            raise RuntimeError(f"invalid hash chain: {path}")
        previous = claimed
    return rows


def append_hash_chain(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    rows = _read_jsonl(path)
    payload = {
        **event,
        "recorded_at_unix_ns": event.get("recorded_at_unix_ns", time.time_ns()),
        "previous_event_sha256": rows[-1]["event_sha256"] if rows else None,
    }
    payload["event_sha256"] = canonical_hash(payload)
    atomic_text(
        path,
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in [*rows, payload]),
    )
    return payload


def emergency_global_stop(root: Path, trigger: str, detail: str) -> None:
    """Stop an initialized run even when package validation can no longer load.

    This path is used by the sealed CLI when a post-initialization binding
    check fails before the normal coordinator can be reconstructed.
    """
    if trigger not in FAIL_STOP_TRIGGERS:
        raise ValueError("unknown global fail-stop trigger")
    state_path = root / "GLOBAL_EXECUTION_STATE.json"
    ledger_path = root / "GLOBAL_EXECUTION_LEDGER.jsonl"
    lock_path = root / "GLOBAL_EXECUTION.lock"
    if not state_path.exists():
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        state = load_json(state_path)
        if state.get("status") not in {"STOPPED", "PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS"}:
            state["status"] = "STOPPED"
            state["stop_trigger"] = trigger
            state["stop_detail"] = detail
            atomic_text(state_path, json.dumps(state, indent=2, sort_keys=True) + "\n")
            append_hash_chain(ledger_path, {
                "event": "GLOBAL_FAIL_STOP", "trigger": trigger, "detail": detail,
            })
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class GlobalFailStopCoordinator:
    """A file-locked coordinator shared by the three fixed video workers.

    No method permits resume.  An existing state file therefore belongs to one
    immutable execution run.  Any hard trigger transitions the whole run to a
    terminal stopped state and all later call reservations fail closed.
    """

    def __init__(
        self,
        root: Path,
        *,
        execution_seal_sha256: str,
        worker_bindings: dict[str, dict[str, Any]],
        envelope_a100_gpu_hours: float,
        call_reservation_wall_seconds: float,
        model_load_reservation_wall_seconds: float,
    ):
        self.root = root
        self.state_path = root / "GLOBAL_EXECUTION_STATE.json"
        self.ledger_path = root / "GLOBAL_EXECUTION_LEDGER.jsonl"
        self.lock_path = root / "GLOBAL_EXECUTION.lock"
        self.execution_seal_sha256 = execution_seal_sha256
        self.worker_bindings = worker_bindings
        self.envelope_gpu_seconds = envelope_a100_gpu_hours * 3600.0
        self.call_reservation_gpu_seconds = 2.0 * call_reservation_wall_seconds
        self.load_reservation_gpu_seconds = 2.0 * model_load_reservation_wall_seconds

    def initialize(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._locked():
            if self.state_path.exists() or self.ledger_path.exists():
                raise RuntimeError("execution state already exists; in-approval resume is forbidden")
            state = {
                "status": "READY",
                "execution_seal_sha256": self.execution_seal_sha256,
                "worker_bindings": self.worker_bindings,
                "envelope_gpu_seconds": self.envelope_gpu_seconds,
                "actual_gpu_seconds": 0.0,
                "reserved_gpu_seconds": 0.0,
                "model_load_workers": [],
                "model_load_completed_workers": [],
                "attempted_unit_ids": [],
                "in_flight_unit_ids": [],
                "completed_unit_ids": [],
                "stop_trigger": None,
                "stop_detail": None,
            }
            self._write_state(state)
            append_hash_chain(self.ledger_path, {
                "event": "RUN_INITIALIZED",
                "execution_seal_sha256": self.execution_seal_sha256,
            })
            return state

    def state(self) -> dict[str, Any]:
        state = load_json(self.state_path)
        if state.get("execution_seal_sha256") != self.execution_seal_sha256:
            raise RuntimeError("coordinator execution-seal mismatch")
        _read_jsonl(self.ledger_path)
        return state

    def start_model_load(self, worker_id: str, gpu_pair: list[int]) -> None:
        with self._locked():
            state = self.state()
            self._require_running(state)
            self._require_worker(worker_id, gpu_pair)
            if worker_id in state["model_load_workers"]:
                self._stop_locked(state, "unauthorized_model_reload", worker_id)
                raise RuntimeError("model reload is forbidden")
            if len(state["model_load_workers"]) >= 3:
                self._stop_locked(state, "unauthorized_model_reload", "fourth model load")
                raise RuntimeError("fourth model load is forbidden")
            self._reserve_or_stop(state, self.load_reservation_gpu_seconds)
            state["model_load_workers"].append(worker_id)
            state["reserved_gpu_seconds"] += self.load_reservation_gpu_seconds
            self._write_state(state)
            append_hash_chain(self.ledger_path, {
                "event": "MODEL_LOAD_STARTED",
                "worker_id": worker_id,
                "gpu_pair": gpu_pair,
                "reserved_gpu_seconds": self.load_reservation_gpu_seconds,
            })

    def complete_model_load(self, worker_id: str, wall_seconds: float) -> None:
        with self._locked():
            state = self.state()
            self._require_running(state)
            if worker_id not in state["model_load_workers"]:
                self._stop_locked(state, "missing_attempt_ledger_transition", worker_id)
                raise RuntimeError("model load completed without start")
            if worker_id in state["model_load_completed_workers"]:
                self._stop_locked(state, "unauthorized_model_reload", worker_id)
                raise RuntimeError("duplicate model load completion")
            actual = 2.0 * wall_seconds
            state["reserved_gpu_seconds"] -= self.load_reservation_gpu_seconds
            state["actual_gpu_seconds"] += actual
            state["model_load_completed_workers"].append(worker_id)
            if actual > self.load_reservation_gpu_seconds + 1e-9:
                self._stop_locked(state, "cost_envelope_exceeded", f"model_load:{worker_id}")
                raise RuntimeError("model load exceeded its sealed reservation")
            if state["actual_gpu_seconds"] + state["reserved_gpu_seconds"] > (
                state["envelope_gpu_seconds"] + 1e-9
            ):
                self._stop_locked(state, "cost_envelope_exceeded", worker_id)
                raise RuntimeError("model load exceeded cost envelope")
            self._write_state(state)
            append_hash_chain(self.ledger_path, {
                "event": "MODEL_LOAD_COMPLETED",
                "worker_id": worker_id,
                "wall_seconds": wall_seconds,
                "actual_gpu_seconds": actual,
            })

    def reserve_call(
        self,
        *,
        worker_id: str,
        gpu_pair: list[int],
        unit_id: str,
        call_spec_sha256: str,
    ) -> None:
        with self._locked():
            state = self.state()
            self._require_running(state)
            self._require_worker(worker_id, gpu_pair)
            if worker_id not in state["model_load_completed_workers"]:
                self._stop_locked(state, "missing_attempt_ledger_transition", unit_id)
                raise RuntimeError("call attempted before completed model load")
            expected_units = self.worker_bindings[worker_id]["unit_ids"]
            if unit_id not in expected_units:
                self._stop_locked(state, "extra_call", unit_id)
                raise RuntimeError("unit is not assigned to worker")
            if unit_id in state["attempted_unit_ids"]:
                self._stop_locked(state, "duplicate_unit_attempt", unit_id)
                raise RuntimeError("duplicate unit attempt")
            self._reserve_or_stop(state, self.call_reservation_gpu_seconds)
            state["attempted_unit_ids"].append(unit_id)
            state["in_flight_unit_ids"].append(unit_id)
            state["reserved_gpu_seconds"] += self.call_reservation_gpu_seconds
            self._write_state(state)
            append_hash_chain(self.ledger_path, {
                "event": "CALL_RESERVED",
                "worker_id": worker_id,
                "unit_id": unit_id,
                "call_spec_sha256": call_spec_sha256,
                "reserved_gpu_seconds": self.call_reservation_gpu_seconds,
            })

    def complete_call(self, *, worker_id: str, unit_id: str, wall_seconds: float) -> None:
        with self._locked():
            state = self.state()
            self._require_running(state)
            if unit_id not in state["in_flight_unit_ids"]:
                self._stop_locked(state, "missing_attempt_ledger_transition", unit_id)
                raise RuntimeError("call completed without reservation")
            actual = 2.0 * wall_seconds
            state["in_flight_unit_ids"].remove(unit_id)
            state["completed_unit_ids"].append(unit_id)
            state["reserved_gpu_seconds"] -= self.call_reservation_gpu_seconds
            state["actual_gpu_seconds"] += actual
            if actual > self.call_reservation_gpu_seconds + 1e-9:
                self._stop_locked(state, "cost_envelope_exceeded", f"call:{unit_id}")
                raise RuntimeError("call exceeded its sealed reservation")
            if state["actual_gpu_seconds"] + state["reserved_gpu_seconds"] > (
                state["envelope_gpu_seconds"] + 1e-9
            ):
                self._stop_locked(state, "cost_envelope_exceeded", unit_id)
                raise RuntimeError("call exceeded cost envelope")
            self._write_state(state)
            append_hash_chain(self.ledger_path, {
                "event": "CALL_COMPLETED",
                "worker_id": worker_id,
                "unit_id": unit_id,
                "wall_seconds": wall_seconds,
                "actual_gpu_seconds": actual,
            })

    def trigger_stop(self, trigger: str, detail: str) -> None:
        if trigger not in FAIL_STOP_TRIGGERS:
            raise ValueError("unknown global fail-stop trigger")
        with self._locked():
            state = self.state()
            if state["status"] != "STOPPED":
                self._stop_locked(state, trigger, detail)

    def mark_complete(self, expected_unit_count: int) -> None:
        with self._locked():
            state = self.state()
            self._require_running(state)
            if not all((
                len(state["model_load_workers"]) == 3,
                len(state["model_load_completed_workers"]) == 3,
                len(state["attempted_unit_ids"]) == expected_unit_count,
                len(state["completed_unit_ids"]) == expected_unit_count,
                not state["in_flight_unit_ids"],
            )):
                self._stop_locked(state, "integrity_mismatch", "incomplete terminal accounting")
                raise RuntimeError("cannot mark incomplete run complete")
            state["status"] = "PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS"
            self._write_state(state)
            append_hash_chain(self.ledger_path, {"event": "PHYSICAL_CALLS_COMPLETE"})

    def _reserve_or_stop(self, state: dict[str, Any], reservation: float) -> None:
        projected = state["actual_gpu_seconds"] + state["reserved_gpu_seconds"] + reservation
        if projected > state["envelope_gpu_seconds"] + 1e-9:
            self._stop_locked(state, "cost_envelope_exceeded", f"projected={projected}")
            raise RuntimeError("cost reservation exceeds authorization envelope")

    def _require_running(self, state: dict[str, Any]) -> None:
        if state["status"] != "READY":
            raise RuntimeError(f"global execution is not accepting work: {state['status']}")

    def _require_worker(self, worker_id: str, gpu_pair: list[int]) -> None:
        binding = self.worker_bindings.get(worker_id)
        if binding is None or binding.get("physical_gpu_ids") != gpu_pair:
            state = self.state()
            self._stop_locked(state, "gpu_binding_mismatch", f"{worker_id}:{gpu_pair}")
            raise RuntimeError("worker/GPU binding mismatch")

    def _stop_locked(self, state: dict[str, Any], trigger: str, detail: str) -> None:
        state["status"] = "STOPPED"
        state["stop_trigger"] = trigger
        state["stop_detail"] = detail
        self._write_state(state)
        append_hash_chain(self.ledger_path, {
            "event": "GLOBAL_FAIL_STOP",
            "trigger": trigger,
            "detail": detail,
        })

    def _write_state(self, state: dict[str, Any]) -> None:
        payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
        atomic_text(self.state_path, payload)

    class _Lock:
        def __init__(self, path: Path):
            self.path = path
            self.handle = None

        def __enter__(self):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.path.open("a+", encoding="utf-8")
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            return self.handle

        def __exit__(self, exc_type, exc, tb):
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()

    def _locked(self):
        return self._Lock(self.lock_path)
