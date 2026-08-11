#!/usr/bin/env python3
"""Non-semantic monitor: finalize V9 only after the sealed runner is complete."""
from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/full_grid_execution_staged_v9_runtime_recovery/GLOBAL_EXECUTION_STATE.json"
LOG = ROOT / "outputs/long_horizon_evidence_convergence_v1/V9_MONITOR.jsonl"


def recovery_module():
    os.environ["AEQ_V3_FULL_GRID_RECOVERY_VERSION"] = "V9"
    path = ROOT / "scripts/v8_full_grid_runtime_recovery.py"
    spec = importlib.util.spec_from_file_location("v9recovery", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def append(row: dict) -> None:
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def finalize_v9() -> dict:
    recovery = recovery_module()
    recovery._patch()
    import garc_eval.accelerated_event_query.oracle_v3_full_grid_analyzer as analyzer
    import garc_eval.accelerated_event_query.oracle_v3_full_grid_finalizer as finalizer
    analyzer.EXECUTION = recovery.V8_EXEC
    analyzer.PACKAGE = recovery.V8
    analyzer.SCHEDULE = recovery.V8 / "FULL_GRID_WORKER_SCHEDULE.json"
    analyzer.UNITS = recovery.V8 / "FULL_GRID_UNIT_MANIFEST.json"
    finalizer.EXECUTION = recovery.V8_EXEC
    finalizer.PACKAGE = recovery.V8
    finalizer.DECISIONS = recovery.V8 / "FULL_GRID_DECISION_MAPPING.json"
    return finalizer.finalize_execution(execution_root=recovery.V8_EXEC, allow_mock=False)


def main() -> None:
    while True:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        row = {
            "time_unix": time.time(),
            "status": state["status"],
            "completed": len(state["completed_unit_ids"]),
            "in_flight": len(state["in_flight_unit_ids"]),
            "stop_trigger": state["stop_trigger"],
        }
        append(row)
        if state["status"] == "PHYSICAL_CALLS_COMPLETE_AWAITING_ANALYSIS":
            result = finalize_v9()
            append({"time_unix": time.time(), "event": "FINALIZER", "result": result})
            return
        if state["status"] == "STOPPED":
            append({"time_unix": time.time(), "event": "ABORTED_NO_FINALIZER"})
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
