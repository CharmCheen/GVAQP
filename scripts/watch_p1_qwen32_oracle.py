#!/usr/bin/env python3
"""Keep the frozen resumable P1 Qwen32 acquisition alive until completion.

The watchdog never interprets outcomes. It only detects an absent owned runner
and restarts exactly the frozen runner command, which resumes from atomic raw
unit records. It exits as soon as the runner's completion manifest exists.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle"
COMPLETE = BASE / "P1_QWEN32_ORACLE_COMPLETION.json"
RAW = BASE / "raw"
LOG = BASE / "P1_QWEN32_WATCHDOG.log"
RUNNER_MARKER = "scripts/run_p1_qwen32_oracle.py run"


def stamp(message: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as out:
        out.write(line + "\n")


def runner_is_alive() -> bool:
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline=(proc / "cmdline").read_bytes().decode(errors="ignore").replace("\0", " ")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if RUNNER_MARKER in cmdline:
            return True
    return False


def complete() -> bool:
    if not COMPLETE.exists():
        return False
    try:
        return json.loads(COMPLETE.read_text()).get("status") == "COMPLETE"
    except json.JSONDecodeError:
        return False


def start_runner() -> None:
    env=os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES":"0,1", "TRANSFORMERS_VERBOSITY":"error"})
    run_log=(BASE / "P1_QWEN32_RUNNER.log").open("a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, "-u", "scripts/run_p1_qwen32_oracle.py", "run"],
        cwd=ROOT, env=env, stdout=run_log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    stamp(f"runner_started raw_records={len(list(RAW.glob('*.json')))}")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    stamp("watchdog_started")
    while not complete():
        if not runner_is_alive():
            start_runner()
            time.sleep(30)
        else:
            time.sleep(60)
    stamp(f"complete raw_records={len(list(RAW.glob('*.json')))}")


if __name__ == "__main__":
    main()
