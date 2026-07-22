#!/usr/bin/env python3
"""Atomically verify and transition the strict-benchmark-to-BCM goal state."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "GOAL_STATE.json"
LOG_PATH = ROOT / "GOAL_EVENT_LOG.csv"
STATES = [
    "STRICT_BENCHMARK_BUILD",
    "STRICT_BENCHMARK_AUDIT",
    "STRICT_BENCHMARK_FREEZE_GATE",
    "BCM_PREFLIGHT",
    "BCM_BASELINE_DIAGNOSTIC",
    "BCM_IMPLEMENTATION",
    "BCM_SYNTHETIC_TESTS",
    "BCM_CEILINGS",
    "BCM_CONFIG_FREEZE",
    "BCM_CANONICAL_RUNS",
    "BCM_ABLATIONS",
    "BCM_MATERIALIZER_MATRIX",
    "BCM_ANALYSIS",
    "BCM_FINAL_AUDIT",
    "GOAL_COMPLETED",
]
TERMINAL_BLOCKED = {"BLOCKED_AT_BENCHMARK", "BLOCKED_AT_BCM_CORRECTNESS"}
FIELDS = [
    "previous_state",
    "new_state",
    "timestamp",
    "input_hashes",
    "output_hashes",
    "pass",
    "reason",
    "recovery_command",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_hashes(value: str) -> dict[str, str]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()):
        raise ValueError("hash maps must be JSON objects with string keys and values")
    return dict(sorted(parsed.items()))


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def state_bytes(state: dict) -> bytes:
    return (json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def append_log_atomic(row: dict[str, str]) -> None:
    rows: list[dict[str, str]] = []
    if LOG_PATH.exists():
        with LOG_PATH.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    rows.append(row)
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(LOG_PATH, buffer.getvalue().encode("utf-8"))


def verify() -> dict[str, object]:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    with LOG_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("GOAL_EVENT_LOG.csv contains no transition")
    last = rows[-1]
    if state.get("current_state") != last["new_state"]:
        raise RuntimeError("state/log disagreement")
    transition = state.get("last_transition", {})
    for key in FIELDS:
        if key in {"input_hashes", "output_hashes"}:
            expected = json.loads(last[key])
        elif key == "pass":
            expected = last[key].lower() == "true"
        elif key == "previous_state":
            expected = last[key] or None
        else:
            expected = last[key]
        if transition.get(key) != expected:
            raise RuntimeError(f"last_transition/log disagreement for {key}")
    return {
        "current_state": state["current_state"],
        "event_count": len(rows),
        "goal_state_sha256": hashlib.sha256(STATE_PATH.read_bytes()).hexdigest(),
        "goal_event_log_sha256": hashlib.sha256(LOG_PATH.read_bytes()).hexdigest(),
        "verified": True,
    }


def transition(args: argparse.Namespace) -> dict[str, object]:
    verify()
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    previous = str(state["current_state"])
    new = args.new_state
    if new not in STATES and new not in TERMINAL_BLOCKED:
        raise ValueError(f"unknown state: {new}")
    if new in STATES and previous in STATES and STATES.index(new) not in {STATES.index(previous), STATES.index(previous) + 1}:
        raise ValueError(f"non-adjacent transition: {previous} -> {new}")
    transition_record = {
        "previous_state": previous,
        "new_state": new,
        "timestamp": utc_now(),
        "input_hashes": parse_hashes(args.input_hashes),
        "output_hashes": parse_hashes(args.output_hashes),
        "pass": args.result == "pass",
        "reason": args.reason,
        "recovery_command": args.recovery_command,
    }
    state["current_state"] = new
    state["goal_status"] = "complete" if new == "GOAL_COMPLETED" else ("blocked" if new in TERMINAL_BLOCKED else "in_progress")
    state["last_transition"] = transition_record
    atomic_bytes(STATE_PATH, state_bytes(state))
    append_log_atomic({
        **transition_record,
        "input_hashes": json.dumps(transition_record["input_hashes"], sort_keys=True, separators=(",", ":")),
        "output_hashes": json.dumps(transition_record["output_hashes"], sort_keys=True, separators=(",", ":")),
        "pass": str(transition_record["pass"]).lower(),
    })
    return verify()


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    update = subparsers.add_parser("transition")
    update.add_argument("--new-state", required=True)
    update.add_argument("--input-hashes", required=True)
    update.add_argument("--output-hashes", required=True)
    update.add_argument("--result", choices=["pass", "fail"], required=True)
    update.add_argument("--reason", required=True)
    update.add_argument("--recovery-command", required=True)
    args = parser.parse_args()
    result = verify() if args.command == "verify" else transition(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
