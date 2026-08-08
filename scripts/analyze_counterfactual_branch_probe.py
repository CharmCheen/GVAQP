#!/usr/bin/env python3
"""Offline-only annotation of frozen one-step branch evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s"
OUT = RUN / "counterfactual_probe_v1"
REFERENCE_SHA256 = "32474c7e42fa63cad86cc7777a7cec2234d73986f4669c41246fc56f6ed6242c"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    plan = json.loads((OUT / "COUNTERFACTUAL_BRANCH_PROBE_PLAN.json").read_text())
    reference = json.loads((RUN / "reference_labels.json").read_text())
    if canonical_hash(reference) != REFERENCE_SHA256:
        raise RuntimeError("frozen evaluator reference hash mismatch")
    rows = []
    for state in plan["states"]:
        before = len(state["state_snapshot"]["confirmed_positive_units"])
        parent_after = len(state["parent_b_transition"]["event_relation_after"])
        parent_delta = parent_after - before
        parent_cost = state["parent_b_transition"]["physical_cost_seconds"]
        parent_completion = state["parent_b_transition"]["completion_seconds"]
        for action in state["alternatives"]:
            path = OUT / "branches" / state["state_id"] / f"{action['kind']}_{action['target']}.json"
            branch = json.loads(path.read_text())
            branch_delta = branch["event_relation_delta"]
            cost_delta = branch["physical_cost_seconds"] - parent_cost
            if branch_delta > parent_delta and branch["completed_by_logical_deadline"]:
                verdict = "STRONG_LOCAL_POSITIVE"
            elif branch_delta == parent_delta and branch["physical_cost_seconds"] < parent_cost:
                verdict = "POTENTIAL_FUTURE_HEADROOM"
            elif branch_delta < parent_delta or (branch_delta == parent_delta and branch["physical_cost_seconds"] > parent_cost):
                verdict = "WORSE"
            else:
                verdict = "NEUTRAL"
            rows.append({
                "state_id": state["state_id"], "stratum": state["stratum"], "parent_b_action": state["parent_b_action"],
                "alternative": action, "parent_cost_seconds": parent_cost, "parent_completion_seconds": parent_completion,
                "parent_event_delta": parent_delta, "alternative_cost_seconds": branch["physical_cost_seconds"],
                "alternative_completion_seconds": branch["completion_seconds"], "alternative_outcome": branch["outcome"],
                "alternative_event_delta": branch_delta, "cost_delta_seconds": cost_delta, "local_verdict": verdict,
                "branch_path": str(path.relative_to(ROOT)), "branch_sha256": sha256(path),
            })
    counts = {name: sum(row["local_verdict"] == name for row in rows) for name in ("STRONG_LOCAL_POSITIVE", "POTENTIAL_FUTURE_HEADROOM", "NEUTRAL", "WORSE")}
    decision = "TARGETED_REACHABLE_HEADROOM_SIGNAL_POSITIVE" if counts["STRONG_LOCAL_POSITIVE"] >= 2 else "TARGETED_REACHABLE_HEADROOM_SIGNAL_INCONCLUSIVE" if counts["STRONG_LOCAL_POSITIVE"] or counts["POTENTIAL_FUTURE_HEADROOM"] else "NO_MEANINGFUL_TARGETED_REACHABLE_HEADROOM_SIGNAL"
    next_steps = {
        "TARGETED_REACHABLE_HEADROOM_SIGNAL_POSITIVE": "EXPAND_TARGETED_COUNTERFACTUAL_EVIDENCE_FOR_GATE_H",
        "TARGETED_REACHABLE_HEADROOM_SIGNAL_INCONCLUSIVE": "DO_NOT_IMPLEMENT_MAB_YET",
        "NO_MEANINGFUL_TARGETED_REACHROOM_SIGNAL": "STOP_MAB_ROUTE_FOR_CURRENT_REGIME",
    }
    next_step = next_steps[decision]
    integrity = {
        "parent_b_trace_sha256": sha256(RUN / "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.trace.json"),
        "deadline_safe_results_sha256": sha256(RUN / "RESULTS_DEADLINE_SAFE.json"),
        "reference_file_sha256": sha256(RUN / "reference_labels.json"),
        "reference_canonical_sha256": canonical_hash(reference),
        "h0_audit_sha256": sha256(RUN / "H0_CAUSAL_REACHABILITY_AUDIT.json"),
    }
    result = {"schema_version": "COUNTERFACTUAL_BRANCH_PROBE_RESULTS_V1", "reference_used_only_after_execution": True, "full_policy_rerun": False, "mab_implemented": False, "planned_branch_count": plan["planned_branch_count"], "executed_branch_count": len(rows), "scan_branch_count": sum(row["alternative"]["kind"] == "SCAN" for row in rows), "verify_branch_count": sum(row["alternative"]["kind"] == "VERIFY" for row in rows), "counts": counts, "decision": decision, "next_step": next_step, "rows": rows}
    (OUT / "COUNTERFACTUAL_BRANCH_PROBE_RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUT / "INTEGRITY.json").write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n")
    lines = ["# Counterfactual branch probe results", "", f"`{decision}`", "", "| State | B action | Alternative | B cost | Alt cost | Event delta | Verdict |", "|---|---|---|---:|---:|---:|---|"]
    for row in rows:
        parent, alt = row["parent_b_action"], row["alternative"]
        lines.append(f"| {row['state_id']} | {parent['kind']}:{parent['target']} | {alt['kind']}:{alt['target']} | {row['parent_cost_seconds']:.3f} | {row['alternative_cost_seconds']:.3f} | {row['alternative_event_delta'] - row['parent_event_delta']:+d} | {row['local_verdict']} |")
    (OUT / "COUNTERFACTUAL_BRANCH_PROBE_RESULTS.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"decision": decision, "next_step": next_step, "counts": counts, "branches": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
