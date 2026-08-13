#!/usr/bin/env python3
"""Fail-closed orchestrator for the already-frozen P1 execution chain.

This script makes no scientific choice. It only waits for the two externally
produced frozen inputs, invokes the pre-existing verifiers/analysis in their
required order, and logs its actions. P1 PASS is deliberately a handoff point:
P2 may only be designed after that observed gate result.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
QWEN = OUT / "qwen32_oracle"
QCOMPLETE = QWEN / "P1_QWEN32_ORACLE_COMPLETION.json"
HUMAN = OUT / "human_reference_package"
HMANIFEST = HUMAN / "P1_HUMAN_REFERENCE_MANIFEST.json"
CHARACTERIZATION = OUT / "P1_PROXY_CHARACTERIZATION_REPORT.md"
DECISION = OUT / "P1_DECISION.json"
FINAL = OUT / "FINAL_RESEARCH_DECISION.md"
LOG = OUT / "P1_GATE_WATCHDOG.log"


def log(message: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(script: str, *args: str) -> None:
    command = [sys.executable, script, *args]
    log("invoke " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def qwen_complete() -> bool:
    if not QCOMPLETE.exists():
        return False
    try:
        return json.loads(QCOMPLETE.read_text()).get("status") == "COMPLETE"
    except json.JSONDecodeError:
        return False


def human_complete() -> bool:
    if not HMANIFEST.exists():
        return False
    try:
        return json.loads(HMANIFEST.read_text()).get("status") == "FROZEN_COMPLETE_ADJUDICATED_HUMAN_REFERENCE"
    except json.JSONDecodeError:
        return False


def main() -> None:
    log("gate_watchdog_started")
    announced_qwen = announced_human = False
    while True:
        try:
            if qwen_complete():
                if not announced_qwen:
                    run("scripts/verify_p1_qwen32_oracle.py")
                    log("qwen_completion_verified")
                    announced_qwen = True
                if not CHARACTERIZATION.exists():
                    run("scripts/characterize_p1_proxies.py", "run")
                    log("proxy_characterization_complete")
            if human_complete():
                if not announced_human:
                    log("human_reference_manifest_detected")
                    announced_human = True
                if not DECISION.exists():
                    if not qwen_complete():
                        log("human_ready_waiting_for_qwen_completion")
                    else:
                        run("scripts/analyze_p1_independent_geometry.py")
                        log("p1_analysis_complete")
                if DECISION.exists():
                    decision=json.loads(DECISION.read_text()).get("decision")
                    if decision == "FAIL":
                        if not FINAL.exists():
                            run("scripts/finalize_p1_no_go.py")
                        log("terminal_p1_no_go_complete")
                        return
                    if decision == "PASS":
                        log("p1_pass_handoff_to_p2_required")
                        return
                    raise RuntimeError(f"unrecognized P1 decision: {decision!r}")
        except Exception as exc:
            # Never infer a scientific result from a failed invocation. Preserve
            # the error and keep checking so an operator can correct an
            # environmental/transient issue without losing the monitor.
            log(f"fail_closed_error type={type(exc).__name__} message={exc}")
        time.sleep(60)


if __name__ == "__main__":
    main()
