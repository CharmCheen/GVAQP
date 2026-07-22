#!/usr/bin/env python3
"""Atomically update clean benchmark v2 RUN_STATE.json."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "RUN_STATE.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase")
    parser.add_argument("--phase-status")
    parser.add_argument("--completed-units", type=int)
    parser.add_argument("--physical-vlm-calls", type=int)
    parser.add_argument("--completed-baseline-runs", type=int)
    parser.add_argument("--failed-baseline-runs", type=int)
    parser.add_argument("--benchmark-frozen", choices=["true", "false"])
    args = parser.parse_args()

    state = json.loads(STATE.read_text(encoding="utf-8"))
    for key in [
        "phase", "phase_status", "completed_units", "physical_vlm_calls",
        "completed_baseline_runs", "failed_baseline_runs",
    ]:
        value = getattr(args, key)
        if value is not None:
            state[key] = value
    if args.benchmark_frozen is not None:
        state["benchmark_frozen"] = args.benchmark_frozen == "true"
    state["last_checkpoint_time"] = utc_now()

    fd, temporary = tempfile.mkstemp(prefix=".RUN_STATE.", suffix=".tmp", dir=ROOT)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, STATE)
        directory_fd = os.open(ROOT, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    main()
