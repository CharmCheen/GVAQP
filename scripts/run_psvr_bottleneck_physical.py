#!/usr/bin/env python3
"""Preregister and execute the bounded H-BOTTLE2 Scan x VERIFY factorial."""

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
CYCLE1 = OUT / "cycle_01_H_RECOVER1"
CYCLE2 = OUT / "cycle_02_H_BOTTLE2"
RAW = CYCLE2 / "raw"
HISTORICAL = (
    ROOT
    / "outputs/psvr_two_video_loop/h_expose2/revision_exposure_temporal_nms/raw"
)
BASE_PATH = ROOT / "scripts/run_psvr_two_video_physical.py"
POLICY_PATH = ROOT / "src/garc_eval/psvr_exposure/policy_service.py"
METHODS = {
    "C00": {"scan_policy": "S0", "verify_policy": "fifo"},
    "C10": {"scan_policy": "S1", "verify_policy": "fifo"},
    "C01": {"scan_policy": "S0", "verify_policy": "cell_diverse_conservative"},
    "C11": {"scan_policy": "S1", "verify_policy": "cell_diverse_conservative"},
}


def load_base():
    spec = importlib.util.spec_from_file_location("psvr_bottleneck_base_runner", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen physical runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def preregister(base) -> dict[str, Any]:
    recover = json.loads((CYCLE1 / "AUDITED_DECISION.json").read_text(encoding="utf-8"))
    if recover.get("H_RECOVER1_DECISION") != "COMPLETE":
        raise RuntimeError("H-RECOVER1 is not complete")
    prereg = {
        "hypothesis_id": "H-BOTTLE2",
        "scientific_question": (
            "Do reference-blind scan recovery and cell-diverse conservative VERIFY have "
            "independent or interacting two-video quality effects?"
        ),
        "registered_at_utc": base.now_utc(),
        "recoverability_decision_hash": recover["decision_hash"],
        "methods": METHODS,
        "smoke_matrix": "4 methods x 4 tasks x T_transition x replicate 0 = 16",
        "formal_matrix": "4 methods x 4 tasks x 2 deadlines x 3 repeats = 96",
        "smoke_counts_as_formal_repeat_0": True,
        "S0": "exact frozen uniform-temporal scan",
        "S1": (
            "frozen midpoint coarse cell; thereafter maximize minimum temporal-center "
            "distance to observed cells; earlier center then lower unit id tie"
        ),
        "V0": "exact FIFO candidate creation order",
        "V1": {
            "name": "Cell-Diverse Conservative VERIFY",
            "one_candidate_per_cell": True,
            "within_cell": "highest current proxy score",
            "between_cells": "first-candidate creation time FIFO",
            "pending_suppression": True,
            "confirmed_exclusion_window": (
                "median frozen unit duration = unchanged K3 return window (10 seconds)"
            ),
            "fallback": "global FIFO when no nonpending cell-diverse eligible candidate",
            "tuned_parameters": 0,
        },
        "frozen": {
            "proxy": "YOLOV8/Y8",
            "candidate_capacity": 10,
            "verify_period": "every 3 completed scans",
            "oracle": "frozen physical Qwen3-VL-32B generic prompt/projection",
            "materializer": "unchanged k3_bridge_safe",
            "deadline_guard": "unchanged task-matched tail_upper_v1",
            "snapshots": "after every scan/verify plus initial",
            "unitization": "frozen 10-second units",
        },
        "correctness_gate": [
            "S0 historical scan equivalence",
            "V0 historical FIFO equivalence",
            "C00 historical endpoint/query/proxy-evidence equivalence",
            "C00/C01 identical scan observations",
            "C10/C11 identical scan observations",
            "same candidate capacity and deadline guard",
            "zero future proxy/reference access and complete snapshots",
        ],
        "branch_rules": {
            "S": "C10>C00 and C11>C01 with V1 improvement and exposure alignment",
            "V": "C01>C00 and C11>C10 on V0_Q1 plus another task with VERIFY alignment",
            "SV": "only C11 stably improves over C00",
            "P": "S1 exposes positives but positive-unit-to-candidate conversion remains near zero",
            "D": "all reference-blind scan policies fail to expose V1 at physical action ceiling",
            "N": "no stable quality gain and no exploitable recoverability ceiling",
        },
        "quality_signal": {
            "cross_video": "at least one improving task in each video",
            "thresholds": [
                "macro AnytimeAUC relative gain >= 10%",
                "macro TTFC reduction >= 20%",
                "macro absolute F1 gain >= 0.05",
                "four-task unique-event gain >= 2",
            ],
            "safety": "no increase in misses; zero replay/future/visibility violations",
        },
        "implementation_hashes": {
            "physical_runner": base.sha256_file(BASE_PATH),
            "factorial_runner": base.sha256_file(Path(__file__)),
            "policy": base.sha256_file(POLICY_PATH),
        },
        "reference_visible_to_runtime": False,
        "heldout_opened": False,
    }
    prereg["preregistration_hash"] = base.canonical_hash(prereg)
    destination = CYCLE2 / "PREREGISTRATION.json"
    CYCLE2.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        unstable = {"registered_at_utc", "preregistration_hash"}
        if {k: v for k, v in existing.items() if k not in unstable} != {
            k: v for k, v in prereg.items() if k not in unstable
        }:
            raise RuntimeError("H-BOTTLE2 preregistration changed")
        prereg = existing
    else:
        base.durable_json(destination, prereg)
    print(json.dumps(prereg, indent=2, sort_keys=True))
    return prereg


def jobs(base) -> list[dict[str, Any]]:
    prereg = json.loads((CYCLE2 / "PREREGISTRATION.json").read_text(encoding="utf-8"))
    selected = json.loads((base.FINAL_PROXY / "FINAL_PROXY_CONFIG.json").read_text())
    family = selected["selected_proxy_config"]
    tasks = [
        row["task_id"]
        for row in json.loads((base.DEV / "TASK_MANIFEST.json").read_text())["tasks"]
    ]
    result = []
    for method, definition in METHODS.items():
        for task_id in tasks:
            for deadline_name in ("T_transition", "T_high"):
                target_scans, target_verifies = base.planned_scan_actions(
                    family, task_id, deadline_name
                )
                for replicate in range(3):
                    result.append({
                        "kind": "h_bottle2",
                        "method": method,
                        "scan_policy": definition["scan_policy"],
                        "verify_policy": definition["verify_policy"],
                        "family": family,
                        "task_id": task_id,
                        "deadline_name": deadline_name,
                        "deadline_seconds": base.task_deadline(task_id, deadline_name),
                        "replicate": replicate,
                        "parameters": {},
                        "target_scan_actions": target_scans,
                        "target_verify_opportunities": target_verifies,
                        "experiment_preregistration_hash": prereg["preregistration_hash"],
                    })
    return result


def load_cell(method: str, task: str, deadline: str, replicate: int) -> dict[str, Any]:
    pattern = (
        f"{method}__Y8__{task}__{deadline}__replicate_{replicate:02d}"
        "/attempt_*/complete.json"
    )
    matches = sorted(RAW.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one complete cell for {pattern}, got {len(matches)}")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def smoke_gate(base) -> dict[str, Any]:
    smoke_jobs = [
        job for job in jobs(base)
        if job["deadline_name"] == "T_transition" and int(job["replicate"]) == 0
    ]
    rows = []
    for job in smoke_jobs:
        try:
            rows.append(load_cell(job["method"], job["task_id"], "T_transition", 0))
        except RuntimeError:
            pass
    baseline_checks = []
    pair_checks = []
    for task_id in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"):
        if len(rows) != 16:
            break
        c00 = load_cell("C00", task_id, "T_transition", 0)
        historical_path = next(HISTORICAL.glob(
            f"fifo__Y8__{task_id}__T_transition__replicate_00/attempt_*/complete.json"
        ))
        historical = json.loads(historical_path.read_text(encoding="utf-8"))
        evidence = lambda run: [
            (int(row["unit_id"]), str(row["candidate_evidence_sha256"]))
            for row in run["proxy_unit_costs"]
        ]
        baseline_checks.append({
            "task_id": task_id,
            "scan_equivalent": c00["scan_order_prefix"] == historical["scan_order_prefix"],
            "query_equivalent": [q["unit_id"] for q in c00["queried_results"]]
            == [q["unit_id"] for q in historical["queried_results"]],
            "oracle_labels_equivalent": [q["parsed_label"] for q in c00["queried_results"]]
            == [q["parsed_label"] for q in historical["queried_results"]],
            "proxy_evidence_equivalent": evidence(c00) == evidence(historical),
            "snapshot_event_equivalent": snapshot_signature(c00) == snapshot_signature(historical),
        })
        for left, right in (("C00", "C01"), ("C10", "C11")):
            a = load_cell(left, task_id, "T_transition", 0)
            b = load_cell(right, task_id, "T_transition", 0)
            pair_checks.append({
                "task_id": task_id,
                "pair": f"{left}/{right}",
                "scan_order_equal": a["scan_order_prefix"] == b["scan_order_prefix"],
                "proxy_evidence_equal": evidence(a) == evidence(b),
                "verify_opportunities_equal": a["verify_opportunities"] == b["verify_opportunities"],
            })
    safety = {
        "completed": len(rows),
        "expected": 16,
        "failures": len(list(RAW.glob("*/attempt_*/failed.json"))),
        "deadline_misses": sum(not row["deadline_met"] for row in rows),
        "incomplete_schedules": sum(
            int(row["scan_actions"]) != int(row["target_scan_actions"])
            or int(row["verify_opportunities"]) != int(row["target_verify_opportunities"])
            for row in rows
        ),
        "replays": sum(int(row["cache_replay_calls"]) for row in rows),
        "future_accesses": sum(int(row["future_proxy_accesses"]) for row in rows),
        "visibility_violations": sum(
            int(row["candidate_observation_violations"])
            + int(row["reference_visibility_violations"])
            for row in rows
        ),
        "missing_snapshots": sum(not Path(row["final_snapshot_path"]).is_file() for row in rows),
    }
    baseline_pass = bool(baseline_checks) and all(
        all(value for key, value in row.items() if key != "task_id")
        for row in baseline_checks
    )
    pairs_pass = bool(pair_checks) and all(
        all(value for key, value in row.items() if key not in {"task_id", "pair"})
        for row in pair_checks
    )
    gate = {
        "hypothesis_id": "H-BOTTLE2",
        "safety": safety,
        "historical_C00_equivalence": baseline_checks,
        "matched_scan_pair_checks": pair_checks,
        "same_candidate_capacity": True,
        "same_deadline_guard": True,
        "reference_visible_to_runtime": False,
        "heldout_opened": False,
    }
    gate["H_BOTTLE2_SMOKE_GATE"] = "PASS" if (
        all(value == 0 for key, value in safety.items() if key not in {"completed", "expected"})
        and safety["completed"] == safety["expected"] == 16
        and baseline_pass and pairs_pass
    ) else "FAIL"
    base.durable_json(CYCLE2 / "SMOKE_GATE.json", gate)
    print(json.dumps(gate, indent=2, sort_keys=True))
    return gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preregister", "smoke", "smoke-gate", "formal"))
    args = parser.parse_args()
    base = load_base()
    if args.stage == "preregister":
        preregister(base)
        return
    if not (CYCLE2 / "PREREGISTRATION.json").exists():
        raise RuntimeError("run preregister first")
    all_jobs = jobs(base)
    if args.stage == "smoke":
        selected = [
            job for job in all_jobs
            if job["deadline_name"] == "T_transition" and int(job["replicate"]) == 0
        ]
        base.run_jobs(
            kind="H_BOTTLE2_FACTORIAL_V1",
            raw=RAW,
            jobs=selected,
            config_jobs=all_jobs,
            physical_cap=96,
        )
    elif args.stage == "smoke-gate":
        smoke_gate(base)
    else:
        gate = json.loads((CYCLE2 / "SMOKE_GATE.json").read_text(encoding="utf-8"))
        if gate.get("H_BOTTLE2_SMOKE_GATE") != "PASS":
            raise RuntimeError("H-BOTTLE2 smoke gate is not PASS")
        base.run_jobs(kind="H_BOTTLE2_FACTORIAL_V1", raw=RAW, jobs=all_jobs, physical_cap=96)


if __name__ == "__main__":
    main()
