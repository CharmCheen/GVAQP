#!/usr/bin/env python3
"""Freeze a label-blind, non-executing one-step counterfactual branch plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rc_sem.counterfactual_probe import build_plan, canonical_sha256

RUN = ROOT / "outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s"
OUT = RUN / "counterfactual_probe_v1"
PARENT = RUN / "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.trace.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite frozen probe namespace: {OUT}")
    parent_hash = sha256(PARENT)
    trace = json.loads(PARENT.read_text(encoding="utf-8"))
    plan = build_plan(trace, parent_trace_sha256=parent_hash)
    contract = {
        "schema_version": "COUNTERFACTUAL_BRANCH_PROBE_CONTRACT_V1",
        "protocol_class": "EXPLORATORY_MINIMAL_COUNTERFACTUAL_BRANCH_PROBE",
        "execution_authorized": False,
        "source": "Guangzhou",
        "source_sha256": "4cef5c884ac879fd00bcc7962707b5f0f5e6dec6ac97e5ec8d247561ce2ec1c6",
        "oracle": "Qwen3-VL-8B-Instruct BF16",
        "gpu_allocation": [1],
        "scan": "deterministic OpenCV frame-difference proxy",
        "logical_deadline_seconds": 300.0,
        "parent_policy": "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1",
        "parent_trace_sha256": parent_hash,
        "state_schema_version": "GUANGZHOU_B_LOGICAL_STATE_V1",
        "legal_action_generator": "rc_sem.exploratory_h0.legal_actions",
        "legal_action_generator_sha256": sha256(ROOT / "src/rc_sem/exploratory_h0.py"),
        "branch_runner_sha256": sha256(ROOT / "scripts/run_counterfactual_branch_probe.py"),
        "completion_timestamp": "timestamp_seconds + physical_cost_seconds; durable visibility surrogate used by the deadline-safe evaluator",
        "admission_semantics": {
            "rule": "current exploratory runner accepts an action when its start is before 300 seconds; no estimated cost/bound is persisted or consulted",
            "source": "scripts/run_exploratory_gate_o_guangzhou.py: run_policy",
            "mode": "exploratory_start_before_deadline",
        },
        "physical_runtime_convention": "CAUSALLY_EQUIVALENT_LOGICAL_STATE_WITH_NORMALIZED_PHYSICAL_RUNTIME: one model-resident BF16 GPU-1 session; process/model setup excluded from each isolated action cost; no runtime/policy state crosses branches",
        "state_selection": plan["selection_algorithm"],
        "maximum_selected_states": 12,
        "maximum_alternatives_per_state": 2,
        "branch_semantics": "restore immutable logical snapshot, execute exactly one alternative, durably record transition, stop",
        "result_namespace": str(OUT.relative_to(ROOT)),
        "evaluator_reference_prohibited_for_selection_and_execution": True,
    }
    contract["contract_sha256"] = canonical_sha256(contract)
    plan["contract_sha256"] = contract["contract_sha256"]
    plan["plan_sha256"] = canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})
    write(OUT / "COUNTERFACTUAL_BRANCH_PROBE_CONTRACT.json", contract)
    write(OUT / "COUNTERFACTUAL_BRANCH_PROBE_PLAN.json", plan)
    (OUT / "COUNTERFACTUAL_BRANCH_PROBE_CONTRACT.md").write_text(
        "# Counterfactual branch probe contract\n\n"
        "Frozen before branch outcomes. This is exploratory, one-step, label-blind branch evidence; it is not Gate H or a dynamic policy.\n",
        encoding="utf-8",
    )
    lines = ["# Counterfactual branch probe plan", "", "Label-blind plan frozen before semantic execution.", "", "| State | t (s) | Parent | Alternatives |", "|---|---:|---|---|"]
    for state in plan["states"]:
        parent = state["parent_b_action"]
        alts = ", ".join(f"{a['kind']}:{a['target']}" for a in state["alternatives"])
        lines.append(f"| {state['state_id']} | {state['elapsed_seconds']:.6f} | {parent['kind']}:{parent['target']} | {alts} |")
    (OUT / "COUNTERFACTUAL_BRANCH_PROBE_PLAN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"contract_sha256": contract["contract_sha256"], "plan_sha256": plan["plan_sha256"], "states": len(plan["states"]), "branches": plan["planned_branch_count"]}, indent=2))


if __name__ == "__main__":
    main()
