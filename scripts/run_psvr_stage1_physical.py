#!/usr/bin/env python3
"""Execute the preregistered H-STAGE1 fixed-versus-observable controller matrix."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
OUT = ROOT / "outputs/psvr_bottleneck_research"
CYCLE2 = OUT / "cycle_02_H_BOTTLE2"
CYCLE3 = OUT / "cycle_03_H_STAGE1"
RAW = CYCLE3 / "raw"
HISTORICAL = CYCLE2 / "raw"
PREREG = CYCLE3 / "PREREGISTRATION.json"
BASE_PATH = ROOT / "scripts/run_psvr_two_video_physical.py"
METHODS = {
    "F0": {
        "scan_policy": "S1",
        "verify_policy": "fifo",
        "action_policy": "fixed_periodic",
    },
    "ST1": {
        "scan_policy": "S1",
        "verify_policy": "cell_diverse_conservative",
        "action_policy": "stage_conditioned_v1",
    },
}


def load_base():
    spec = importlib.util.spec_from_file_location("psvr_stage1_base_runner", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load physical runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def preregistration() -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    parent = json.loads((CYCLE2 / "AUDITED_DECISION.json").read_text(encoding="utf-8"))
    if parent.get("selected_branch_hypothesis") != "H-STAGE1":
        raise RuntimeError("H-BOTTLE2 did not select H-STAGE1")
    if prereg["parent_decision_hash"] != parent["decision_hash"]:
        raise RuntimeError("H-STAGE1 parent decision hash mismatch")
    return prereg


def jobs(base) -> list[dict[str, Any]]:
    prereg = preregistration()
    family = json.loads(
        (base.FINAL_PROXY / "FINAL_PROXY_CONFIG.json").read_text(encoding="utf-8")
    )["selected_proxy_config"]
    tasks = [
        row["task_id"]
        for row in json.loads(
            (base.DEV / "TASK_MANIFEST.json").read_text(encoding="utf-8")
        )["tasks"]
    ]
    result = []
    for method, definition in METHODS.items():
        for task_id in tasks:
            for deadline_name in ("T_transition", "T_high"):
                frozen_control = load_cell(
                    HISTORICAL, "C10", task_id, deadline_name, 0
                )
                target_scans = int(frozen_control["target_scan_actions"])
                target_verifies = int(frozen_control["target_verify_opportunities"])
                for replicate in range(3):
                    result.append({
                        "kind": "h_stage1",
                        "method": method,
                        **definition,
                        "family": family,
                        "task_id": task_id,
                        "deadline_name": deadline_name,
                        "deadline_seconds": base.task_deadline(task_id, deadline_name),
                        "replicate": replicate,
                        "parameters": {},
                        "target_scan_actions": target_scans,
                        "target_verify_opportunities": target_verifies,
                        "experiment_preregistration_hash": base.canonical_hash(prereg),
                    })
    return result


def load_cell(raw: Path, method: str, task: str, deadline: str, replicate: int) -> dict[str, Any]:
    pattern = (
        f"{method}__Y8__{task}__{deadline}__replicate_{replicate:02d}"
        "/attempt_*/complete.json"
    )
    matches = sorted(raw.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one complete cell for {pattern}, got {len(matches)}")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def evidence_signature(run: dict[str, Any]) -> list[tuple[int, str]]:
    return [
        (int(row["unit_id"]), str(row["candidate_evidence_sha256"]))
        for row in run["proxy_unit_costs"]
    ]


def snapshot_signature(run: dict[str, Any]) -> list[tuple[Any, ...]]:
    snapshot = json.loads(Path(run["final_snapshot_path"]).read_text(encoding="utf-8"))
    return sorted(
        (
            str(row.get("anchor_unit_ids", "")),
            str(row.get("evidence_unit_ids", "")),
            float(row.get("start_time", 0.0)),
            float(row.get("end_time", 0.0)),
        )
        for row in snapshot.get("strict_confirmed_events", [])
    )


def smoke_gate(base) -> dict[str, Any]:
    rows = [
        load_cell(RAW, method, task, "T_transition", 0)
        for method in METHODS
        for task in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
    ]
    equivalence = []
    for task in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"):
        current = load_cell(RAW, "F0", task, "T_transition", 0)
        old = load_cell(HISTORICAL, "C10", task, "T_transition", 0)
        equivalence.append({
            "task_id": task,
            "scan_equal": current["scan_order_prefix"] == old["scan_order_prefix"],
            "query_equal": [row["unit_id"] for row in current["queried_results"]]
            == [row["unit_id"] for row in old["queried_results"]],
            "labels_equal": [row["parsed_label"] for row in current["queried_results"]]
            == [row["parsed_label"] for row in old["queried_results"]],
            "proxy_evidence_equal": evidence_signature(current) == evidence_signature(old),
            "snapshot_equal": snapshot_signature(current) == snapshot_signature(old),
        })
    stage_rows = [row for row in rows if row["method"] == "ST1"]
    stage_state_complete = all(
        all("stage_state" in action for action in row["actions"] if action["action"] == "scan")
        for row in stage_rows
    )
    safety = {
        "completed": len(rows),
        "expected": 8,
        "failed_attempts": len(list(RAW.glob("*/attempt_*/failed.json"))),
        "deadline_misses": sum(not row["deadline_met"] for row in rows),
        "cache_replays": sum(int(row["cache_replay_calls"]) for row in rows),
        "future_accesses": sum(int(row["future_proxy_accesses"]) for row in rows),
        "visibility_violations": sum(
            int(row["candidate_observation_violations"])
            + int(row["reference_visibility_violations"])
            for row in rows
        ),
        "missing_snapshots": sum(
            not Path(row["final_snapshot_path"]).is_file() for row in rows
        ),
    }
    gate = {
        "hypothesis_id": "H-STAGE1",
        "fixed_control_equivalence": equivalence,
        "stage_state_complete": stage_state_complete,
        "safety": safety,
        "heldout_opened": False,
        "reference_visible_to_runtime": False,
    }
    equivalent = all(
        all(value for key, value in row.items() if key != "task_id")
        for row in equivalence
    )
    gate["H_STAGE1_SMOKE_GATE"] = "PASS" if (
        equivalent
        and stage_state_complete
        and safety["completed"] == safety["expected"]
        and all(value == 0 for key, value in safety.items() if key not in {"completed", "expected"})
    ) else "FAIL"
    base.durable_json(CYCLE3 / "SMOKE_GATE.json", gate)
    print(json.dumps(gate, indent=2, sort_keys=True))
    return gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("check", "smoke", "smoke-gate", "formal"))
    args = parser.parse_args()
    base = load_base()
    all_jobs = jobs(base)
    if args.stage == "check":
        print(json.dumps({
            "status": "PREREGISTRATION_VALID",
            "jobs": len(all_jobs),
            "preregistration_hash": base.canonical_hash(preregistration()),
        }, sort_keys=True))
        return
    if args.stage == "smoke":
        selected = [
            job for job in all_jobs
            if job["deadline_name"] == "T_transition" and int(job["replicate"]) == 0
        ]
        base.run_jobs(
            kind="H_STAGE1_PHYSICAL_V1",
            raw=RAW,
            jobs=selected,
            config_jobs=all_jobs,
            physical_cap=48,
        )
    elif args.stage == "smoke-gate":
        smoke_gate(base)
    else:
        gate = json.loads((CYCLE3 / "SMOKE_GATE.json").read_text(encoding="utf-8"))
        if gate.get("H_STAGE1_SMOKE_GATE") != "PASS":
            raise RuntimeError("H-STAGE1 smoke gate is not PASS")
        base.run_jobs(
            kind="H_STAGE1_PHYSICAL_V1", raw=RAW, jobs=all_jobs, physical_cap=48
        )


if __name__ == "__main__":
    main()
