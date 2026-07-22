"""Trusted wall-clock primitives for complete PSVR observation and snapshot commits."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Callable

import pandas as pd

from .sandbox import isolated_materialize


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def durable_json(path: Path, value) -> dict:
    """Serialize, fsync, atomically replace, and fsync the containing directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    total_start = time.perf_counter_ns()
    start = time.perf_counter_ns()
    payload = (json.dumps(value, indent=2, sort_keys=True, default=str) + "\n").encode()
    serialize_seconds = (time.perf_counter_ns() - start) / 1e9
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload); handle.flush()
            start = time.perf_counter_ns(); os.fsync(handle.fileno())
            fsync_seconds = (time.perf_counter_ns() - start) / 1e9
        start = time.perf_counter_ns(); os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        atomic_replace_seconds = (time.perf_counter_ns() - start) / 1e9
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "serialize_seconds": serialize_seconds,
        "fsync_seconds": fsync_seconds,
        "atomic_replace_seconds": atomic_replace_seconds,
        "total_seconds": (time.perf_counter_ns() - total_start) / 1e9,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }


class ActionLedger:
    """Append-only, hash-chained physical action ledger."""

    def __init__(self, path: Path, run_start_ns: int, clock_ns: Callable[[], int] = time.perf_counter_ns) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_start_ns = int(run_start_ns); self.clock_ns = clock_ns
        self.previous_hash: str | None = None
        if self.path.exists():
            rows = verify_action_ledger(self.path, expected_run_start_ns=self.run_start_ns)
            if rows:
                raise FileExistsError(f"refusing to append a second attempt to {self.path}")

    def append(self, event_type: str, **fields) -> dict:
        wall_ns = self.clock_ns()
        row = {
            "event_type": event_type,
            "wall_ns": wall_ns,
            "run_start_ns": self.run_start_ns,
            "elapsed_seconds": (wall_ns - self.run_start_ns) / 1e9,
            "previous_event_sha256": self.previous_hash,
            **fields,
        }
        row["event_sha256"] = canonical_hash(row)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        self.previous_hash = row["event_sha256"]
        return row


def strict_indexed_json_paths(directory: Path, prefix: str) -> list[Path]:
    """Return only canonical attempt summaries, never oracle/snapshot sidecars."""

    if not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
        raise ValueError("invalid indexed-record prefix")
    pattern = re.compile(rf"^{re.escape(prefix)}_([0-9]{{3}})\.json$")
    indexed: list[tuple[int, Path]] = []
    for path in Path(directory).glob(f"{prefix}_*.json"):
        match = pattern.fullmatch(path.name)
        if match:
            indexed.append((int(match.group(1)), path))
    indexed.sort(key=lambda item: item[0])
    indices = [index for index, _ in indexed]
    if len(indices) != len(set(indices)):
        raise RuntimeError("duplicate indexed-record id")
    return [path for _, path in indexed]


def attempt_artifact_indices(directory: Path, prefix: str) -> set[int]:
    """Discover reserved attempt ids from summaries, ledgers, and sidecars."""

    if not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
        raise ValueError("invalid attempt prefix")
    pattern = re.compile(rf"^{re.escape(prefix)}_([0-9]{{3}})(?:$|[_.])")
    indices = set()
    for path in Path(directory).glob(f"{prefix}_*"):
        match = pattern.match(path.name)
        if match:
            indices.add(int(match.group(1)))
    return indices


def verify_action_ledger(path: Path, *, expected_run_start_ns: int,
                         expected_terminal_event: str | None = None) -> list[dict]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    previous = None
    for index, row in enumerate(rows):
        claimed = row.get("event_sha256")
        unsigned = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("previous_event_sha256") != previous:
            raise RuntimeError(f"broken action-ledger predecessor at row {index}")
        if row.get("run_start_ns") != int(expected_run_start_ns):
            raise RuntimeError(f"action-ledger run identity mismatch at row {index}")
        if claimed != canonical_hash(unsigned):
            raise RuntimeError(f"broken action-ledger hash at row {index}")
        previous = claimed
    if expected_terminal_event is not None and (not rows or rows[-1].get("event_type") != expected_terminal_event):
        raise RuntimeError(f"action ledger lacks terminal event {expected_terminal_event}")
    return rows


def materialize_and_commit(
    *,
    materializer_path: Path,
    units: pd.DataFrame,
    queried_rows: list[dict],
    snapshot_path: Path,
    run_config: dict,
    raw_observation: dict | None = None,
    raw_observation_path: Path | None = None,
    materializer_service=None,
) -> tuple[list[dict], dict]:
    """Persist new evidence, execute unchanged isolated K3, and durably commit a snapshot."""
    total_start = time.perf_counter_ns(); stage: dict[str, float] = {}
    raw_commit = None
    if raw_observation is not None:
        if raw_observation_path is None:
            raise ValueError("raw_observation_path is required when raw evidence is provided")
        raw_commit = durable_json(raw_observation_path, raw_observation)
        stage["observation_persist"] = raw_commit["total_seconds"]
    trace = pd.DataFrame(
        [{"unit_id": int(row["unit_id"]), "oracle_label_after_query": row["parsed_label"]} for row in queried_rows],
        columns=["unit_id", "oracle_label_after_query"],
    )
    start = time.perf_counter_ns()
    if materializer_service is None:
        result = isolated_materialize(
            materializer_path, trace, units, run_config, "k3_bridge_safe",
            {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
        )
        events = result["events"]
        materializer_mode = "per_commit_clean_spawn"
    else:
        events = materializer_service.materialize(trace.to_dict("records"), units.to_dict("records"), run_config)
        materializer_mode = "persistent_clean_spawn_predeadline"
    stage["materialize"] = (time.perf_counter_ns() - start) / 1e9
    snapshot = {
        "strict_confirmed_events": events,
        "boundary_state": "unit_interval_censored_no_refinement",
        "queried_unit_ids": [int(row["unit_id"]) for row in queried_rows],
        "verification_state": "oracle_confirmed_only",
    }
    snapshot_commit = durable_json(snapshot_path, snapshot)
    stage["serialize"] = snapshot_commit["serialize_seconds"]
    stage["fsync"] = snapshot_commit["fsync_seconds"]
    stage["atomic_replace"] = snapshot_commit["atomic_replace_seconds"]
    return events, {
        "stage_seconds": stage,
        "raw_observation_commit": raw_commit,
        "snapshot_commit": snapshot_commit,
        "total_seconds": (time.perf_counter_ns() - total_start) / 1e9,
        "snapshot_path": str(snapshot_path),
        "materializer_mode": materializer_mode,
    }
