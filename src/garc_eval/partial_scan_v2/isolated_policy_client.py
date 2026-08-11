from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
from typing import Any

from .config import POLICY_IDS
from .error_redaction import PublicPolicyError
from .protocol import (
    DEFAULT_POLICY_TIMEOUT_SEC,
    MAX_MESSAGE_BYTES,
    POLICY_PROTOCOL_VERSION,
    PUBLIC_TERMINATION_REASONS,
)
from .public_schema import (
    validate_action,
    validate_initialized,
)

POLICY_WORKER = Path(__file__).with_name("policy_worker.py")


def _canonical_line(value: dict[str, Any]) -> bytes:
    try:
        line = (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("ascii")
    except BaseException as error:
        raise PublicPolicyError("POLICY_PROTOCOL_ERROR") from error
    if len(line) > MAX_MESSAGE_BYTES:
        raise PublicPolicyError("POLICY_PROTOCOL_ERROR")
    return line


class JsonlPolicyProcess:
    """A process boundary only; deployment isolation is deliberately external.

    The evaluator owns all benchmark objects and communicates with this worker
    exclusively through the JSONL pipes created below.  This class must not be
    interpreted as capability isolation: mounts, credentials, network policy,
    and host visibility are deployment concerns audited outside this package.
    """
    def __init__(
        self,
        *,
        run_id: str,
        worker_file: str,
        worker_args: list[str],
        private_stderr_log: Path,
    ):
        self.run_id = run_id
        self.private_stderr_log = private_stderr_log
        private_stderr_log.parent.mkdir(parents=True, exist_ok=True)
        self._stderr_handle = private_stderr_log.open("ab", buffering=0)
        command = [
            sys.executable,
            "-u",
            "-I",
            "-S",
            str(POLICY_WORKER if worker_file == "policy_worker.py" else Path(__file__).with_name(worker_file)),
            *worker_args,
        ]
        environment = {
            "PYTHONUNBUFFERED": "1",
            "POLICY_RUN_ID": run_id,
            "POLICY_PROTOCOL_VERSION": POLICY_PROTOCOL_VERSION,
        }
        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr_handle,
                cwd=str(POLICY_WORKER.parent),
                env=environment,
                close_fds=True,
                bufsize=0,
            )
        except BaseException as error:
            self._stderr_handle.close()
            raise PublicPolicyError("POLICY_LAUNCH_ERROR") from error
        self._receive_buffer = bytearray()
        self.transcript: list[dict[str, Any]] = []
        self.closed = False
        self._configuration = {
            "policy_execution_mode": "OUT_OF_PROCESS",
            "policy_pid": self.process.pid,
            "policy_environment_keys": sorted(environment),
            "transport": "STDIN_STDOUT_JSONL",
            "application_boundary_only": True,
            "capability_security": "NOT_YET_ESTABLISHED",
        }

    def send(self, value: dict[str, Any]) -> dict[str, float]:
        started = time.perf_counter()
        line = _canonical_line(value)
        serialized = time.perf_counter() - started
        if self.process.stdin is None:
            raise PublicPolicyError("POLICY_EXIT_ERROR")
        descriptor = self.process.stdin.fileno()
        sent = 0
        send_started = time.perf_counter()
        try:
            while sent < len(line):
                count = os.write(descriptor, line[sent:])
                if count <= 0:
                    raise BrokenPipeError
                sent += count
        except BaseException as error:
            raise PublicPolicyError("POLICY_EXIT_ERROR") from error
        send_elapsed = time.perf_counter() - send_started
        self.transcript.append({"direction": "evaluator_to_policy", "message": value})
        return {
            "policy_request_serialize_sec": serialized,
            "ipc_send_sec": send_elapsed,
        }

    def receive(
        self, timeout_sec: float = DEFAULT_POLICY_TIMEOUT_SEC
    ) -> tuple[dict[str, Any], dict[str, float]]:
        if self.process.stdout is None:
            raise PublicPolicyError("POLICY_EXIT_ERROR")
        descriptor = self.process.stdout.fileno()
        deadline = time.monotonic() + timeout_sec
        wait_elapsed = 0.0
        read_elapsed = 0.0
        while b"\n" not in self._receive_buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PublicPolicyError("POLICY_TIMEOUT")
            wait_started = time.perf_counter()
            readable, _, _ = select.select([descriptor], [], [], remaining)
            wait_elapsed += time.perf_counter() - wait_started
            if not readable:
                raise PublicPolicyError("POLICY_TIMEOUT")
            read_started = time.perf_counter()
            chunk = os.read(descriptor, 65536)
            read_elapsed += time.perf_counter() - read_started
            if not chunk:
                raise PublicPolicyError("POLICY_EXIT_ERROR")
            self._receive_buffer.extend(chunk)
            if len(self._receive_buffer) > MAX_MESSAGE_BYTES + 1:
                raise PublicPolicyError("POLICY_PROTOCOL_ERROR")
        line, remainder = self._receive_buffer.split(b"\n", 1)
        self._receive_buffer = bytearray(remainder)
        # A response smuggling attempt commonly arrives in the same pipe write.
        ready, _, _ = select.select([descriptor], [], [], 0.01)
        if ready:
            read_started = time.perf_counter()
            additional = os.read(descriptor, 65536)
            read_elapsed += time.perf_counter() - read_started
            self._receive_buffer.extend(additional)
        if self._receive_buffer:
            raise PublicPolicyError("POLICY_PROTOCOL_ERROR")
        if len(line) > MAX_MESSAGE_BYTES:
            raise PublicPolicyError("POLICY_PROTOCOL_ERROR")
        parse_started = time.perf_counter()
        try:
            value = json.loads(line)
        except BaseException as error:
            raise PublicPolicyError("POLICY_PROTOCOL_ERROR") from error
        read_elapsed += time.perf_counter() - parse_started
        if not isinstance(value, dict):
            raise PublicPolicyError("POLICY_PROTOCOL_ERROR")
        self.transcript.append({"direction": "policy_to_evaluator", "message": value})
        return value, {
            "policy_decision_sec": wait_elapsed,
            "ipc_receive_sec": read_elapsed,
        }

    def application_attestation(self) -> dict[str, Any]:
        """Return observable application-launch facts, not security claims."""
        return dict(self._configuration)

    def transcript_hash(self) -> str:
        encoded = json.dumps(
            self.transcript,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()

    def stop(self, *, kill: bool = False) -> None:
        if self.closed:
            return
        try:
            if kill and self.process.poll() is None:
                self.process.kill()
            if self.process.stdin is not None:
                self.process.stdin.close()
            if self.process.stdout is not None:
                self.process.stdout.close()
            if self.process.poll() is None:
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
        finally:
            self._stderr_handle.close()
            self.closed = True


class IsolatedPolicyClient:
    def __init__(
        self,
        *,
        policy_id: str,
        seed: int,
        initialize_message: dict[str, Any],
        private_stderr_log: Path,
    ):
        if policy_id not in POLICY_IDS:
            raise ValueError(policy_id)
        self.policy_id = policy_id
        self.initialize_message = initialize_message
        self.known_units = {
            str(unit["unit_id"]) for unit in initialize_message["units"]
        }
        self.sandbox = JsonlPolicyProcess(
            run_id=str(initialize_message["run_id"]),
            worker_file="policy_worker.py",
            worker_args=["--policy-id", policy_id, "--seed", str(seed)],
            private_stderr_log=private_stderr_log,
        )
        try:
            sent = self.sandbox.send(initialize_message)
            response, received = self.sandbox.receive()
            validate_started = time.perf_counter()
            validate_initialized(response, str(initialize_message["run_id"]))
            validated = time.perf_counter() - validate_started
            self.initialize_timings = {
                **sent,
                **received,
                "policy_response_validate_sec": validated,
            }
            self.application = self.sandbox.application_attestation()
        except BaseException:
            self.sandbox.stop(kill=True)
            raise

    @property
    def pid(self) -> int:
        return self.sandbox.process.pid

    def choose(
        self,
        choose_message: dict[str, Any],
        available_units: set[str] | None = None,
        timeout_sec: float = DEFAULT_POLICY_TIMEOUT_SEC,
    ) -> tuple[str, dict[str, float]]:
        try:
            sent = self.sandbox.send(choose_message)
            response, received = self.sandbox.receive(timeout_sec)
            validate_started = time.perf_counter()
            validate_action(
                response,
                self.known_units if available_units is None else available_units,
                int(choose_message["step_id"]),
            )
            validated = time.perf_counter() - validate_started
            return str(response["unit_id"]), {
                **sent,
                **received,
                "policy_response_validate_sec": validated,
            }
        except PublicPolicyError:
            self.sandbox.stop(kill=True)
            raise
        except BaseException as error:
            self.sandbox.stop(kill=True)
            raise PublicPolicyError("POLICY_PROTOCOL_ERROR") from error

    def close(self, reason: str) -> None:
        if reason not in PUBLIC_TERMINATION_REASONS:
            reason = "POLICY_PROTOCOL_ERROR"
        if self.sandbox.closed:
            return
        try:
            self.sandbox.send({"type": "terminate", "reason": reason})
        except PublicPolicyError:
            self.sandbox.stop(kill=True)
            return
        self.sandbox.stop()

    def summary(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_pid": self.pid,
            "initialize_timings": self.initialize_timings,
            "application_attestation": self.application,
            "public_transcript_hash": self.sandbox.transcript_hash(),
            "public_message_count": len(self.sandbox.transcript),
        }

