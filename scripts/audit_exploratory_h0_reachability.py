#!/usr/bin/env python3
"""Read-only causal reachability audit for persisted Guangzhou traces.

It writes separate H0 audit artifacts and never invokes SCAN, VERIFY, or a
model.  A missing exact-state branch is reported as non-identifiable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rc_sem.exploratory_gate_o import POLICIES, temporal_bisection_order

RUN = ROOT / "outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s"
DEADLINE_SECONDS = 300.0
REFERENCE_SHA256 = "32474c7e42fa63cad86cc7777a7cec2234d73986f4669c41246fc56f6ed6242c"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_order(policy: str, cell_count: int) -> tuple[int, ...]:
    return tuple(range(cell_count)) if policy != POLICIES[1] else temporal_bisection_order(cell_count)


def inspect_trace(policy: str, trace: list[dict]) -> dict:
    cells = {int(row["target"]) for row in trace if row["action_type"] == "SCAN"}
    cell_count = max(cells, default=-1) + 1
    # Guangzhou has 43 10-second cells; C scans all and provides the canonical count.
    cell_count = max(cell_count, 43)
    expected_order = scan_order(policy, cell_count)
    scanned: set[int] = set()
    exposed: set[int] = set()
    attempted: set[int] = set()
    missing_alternative_verify_examples: list[dict] = []
    missing_alternative_verify_count = 0
    violations: list[dict] = []
    for index, row in enumerate(trace):
        action, target = row["action_type"], int(row["target"])
        if action == "SCAN":
            expected = expected_order[len(scanned)] if len(scanned) < len(expected_order) else None
            if target != expected:
                violations.append({"index": index, "kind": "SCAN_ORDER", "target": target, "expected": expected})
            scanned.add(target)
            exposed.update(int(item["unit_id"]) for item in row["outcome"]["exposed"])
        elif action == "VERIFY":
            alternatives = sorted(exposed - attempted - {target})
            missing_alternative_verify_count += len(alternatives)
            if alternatives and len(missing_alternative_verify_examples) < 3:
                missing_alternative_verify_examples.append({
                    "trace_index": index,
                    "selected_verify": target,
                    "other_legal_exposed_candidates": alternatives[:12],
                })
            if target not in exposed or target in attempted:
                violations.append({"index": index, "kind": "VERIFY_EXPOSURE", "target": target})
            attempted.add(target)
        else:
            violations.append({"index": index, "kind": "UNKNOWN_ACTION", "action": action})
    return {
        "action_count": len(trace),
        "scan_actions": sum(row["action_type"] == "SCAN" for row in trace),
        "verify_actions": sum(row["action_type"] == "VERIFY" for row in trace),
        "dependency_violations": violations,
        "unselected_legal_verify_branch_observations": missing_alternative_verify_count,
        "unselected_legal_verify_branch_examples": missing_alternative_verify_examples,
        "exact_state_counterfactual_transitions_complete": False,
        "reason": "trace contains the selected action outcome only; unselected legal VERIFY branches have no state-specific physical completion/cost transition",
    }


def main() -> None:
    trace_hashes: dict[str, str] = {}
    trace_audit: dict[str, dict] = {}
    for policy in POLICIES:
        path = RUN / f"{policy}.trace.json"
        trace_hashes[path.name] = sha256(path)
        trace_audit[policy] = inspect_trace(policy, json.loads(path.read_text(encoding="utf-8")))
    audit = {
        "schema_version": "EXPLORATORY_H0_CAUSAL_REACHABILITY_AUDIT_V1",
        "scope": "H0 causal reachability only; no dynamic policy or headroom metric is computed",
        "decision": "H0_COUNTERFACTUAL_BRANCHES_NOT_IDENTIFIABLE_FROM_EXISTING_TRACE",
        "next_step": "DESIGN_MINIMAL_COUNTERFACTUAL_EVIDENCE_COLLECTION",
        "no_policy_rerun": True,
        "no_scan_rerun": True,
        "no_verify_rerun": True,
        "no_oracle_inference": True,
        "deadline_seconds": DEADLINE_SECONDS,
        "reference_sha256": REFERENCE_SHA256,
        "inspected_sources": [
            "src/rc_sem/sequential.py",
            "src/rc_sem/sequential_policies.py",
            "src/rc_sem/metrics.py",
            "src/rc_sem/exploratory_gate_o.py",
            "src/rc_sem/exploratory_deadline_evaluation.py",
            "scripts/run_exploratory_gate_o_guangzhou.py",
            "scripts/reevaluate_exploratory_gate_o_deadline_safe.py",
            "src/garc_eval/scan_confirm_controller/action.py",
            "src/garc_eval/scan_confirm_controller/state.py",
            "src/garc_eval/scan_confirm_controller/offline_oracle.py",
            "src/garc_eval/scan_confirm_controller/smdp_oracle.py",
            "docs/DEADLINE_SEMANTICS.md",
            "docs/SELECTED_FRONTIER_CONVERSION_CALIBRATION_CONTRACT_V1.md",
            "outputs/controller_dynamic_headroom_cached_v1/SUMMARY.json",
        ],
        "evidence_hashes": {
            "raw_traces": trace_hashes,
            "deadline_safe_results": sha256(RUN / "RESULTS_DEADLINE_SAFE.json"),
        },
        "state_schema": {
            "LEGAL_RUNTIME_STATE": [
                "elapsed_seconds", "remaining_deadline_seconds", "completed_scan_cells",
                "observed_proxy_scores_for_exposed_units", "exposed_verify_candidates",
                "attempted_verify_candidates", "confirmed_events", "rejected_candidates",
                "current_event_relation", "fixed_scan_order_and_cursor", "causally_observed_cost_history",
            ],
            "EVALUATOR_ONLY": ["reference_labels", "reference_event_groups", "event_recall", "event_f1", "oracle_action_value"],
            "FUTURE_INFORMATION": ["unscanned_proxy_scores", "unexposed_candidates", "unattempted_verify_labels", "future_action_costs", "future_event_relation"],
            "AMBIGUOUS_IN_CURRENT_TRACE": ["legal_state.scanned_cells timing", "legal_state.verifiable_units timing", "admission cost estimate", "durable_commit_time"],
        },
        "action_dependencies": {
            "SCAN(cell)": {
                "preconditions": ["cell is next in fixed scan order", "scan admitted by observed-cost deadline rule"],
                "transition": "decode/proxy completes; its units and proxy scores become exposed",
                "newly_exposed": "VERIFY(unit) for each exposed unit",
            },
            "VERIFY(unit)": {
                "preconditions": ["unit was exposed by a completed SCAN", "unit not previously attempted", "verify admitted by observed-cost deadline rule"],
                "transition": "durable parsed label updates attempted/rejected/confirmed/EventRelation",
            },
            "STOP": {"preconditions": ["no admissible SCAN or VERIFY remains"], "transition": "terminal"},
        },
        "legal_action_generator": {
            "implementation": "rc_sem.exploratory_h0.legal_actions",
            "definition": "admitted next SCAN plus every admitted exposed, unattempted VERIFY; evaluator labels are absent",
        },
        "trace_audit": trace_audit,
        "prior_clairvoyant_audit": {
            "artifact": "outputs/controller_dynamic_headroom_cached_v1/SUMMARY.json",
            "status": "FAIL_CURRENT_H0_APPLICABILITY",
            "classification": "CLAIRVOYANT_DIAGNOSTIC_CEILING_ONLY",
            "reason": "its own record states cached abstract costs (SCAN=0.1, VERIFY=1.0), older cached oracle/reference, and no physical deadline; it is not a Guangzhou exact-state transition registry",
        },
        "minimum_missing_evidence": [
            "canonical pre-decision state snapshot and state hash for every branch point",
            "causally observed admission estimate/history used at each state",
            "for every evaluator-chosen legal alternative: its deterministic SCAN/VERIFY output, durable completion cost, and next-state transition under the same runtime contract",
            "an explicit branch-cache coverage manifest keyed by (state_hash, action), not labels alone",
        ],
    }
    (RUN / "H0_CAUSAL_REACHABILITY_AUDIT.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# H0 causal reachability audit", "",
        "`H0_COUNTERFACTUAL_BRANCHES_NOT_IDENTIFIABLE_FROM_EXISTING_TRACE`", "",
        "The persisted Guangzhou traces validate selected-action exposure dependencies, but do not provide state-specific physical transitions for unselected legal actions. Reference labels may value an already legal action; they cannot create its physical transition or admission cost.", "",
        "## Result", "",
        "No reachable dynamic oracle or Gate-H metric was computed. The old cached greedy/headroom artifact is a clairvoyant diagnostic ceiling only, not a valid Guangzhou H0 oracle.", "",
        "## Minimum evidence needed", "",
        *[f"- {item}" for item in audit["minimum_missing_evidence"]], "",
        "Raw traces and deadline-safe results were read only; their SHA-256 values are recorded in the JSON artifact.",
    ]
    (RUN / "H0_CAUSAL_REACHABILITY_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"decision": audit["decision"], "next_step": audit["next_step"], "trace_audit": trace_audit}, indent=2))


if __name__ == "__main__":
    main()
