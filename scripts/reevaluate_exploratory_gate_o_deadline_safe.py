#!/usr/bin/env python3
"""Deterministically re-evaluate existing exploratory traces; never runs inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rc_sem.exploratory_deadline_evaluation import deadline_safe_summary
from rc_sem.exploratory_gate_o import POLICIES

RUN = ROOT / "outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s"
REFERENCE_SHA256 = "32474c7e42fa63cad86cc7777a7cec2234d73986f4669c41246fc56f6ed6242c"
DEADLINE = 300.0


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    reference_payload = json.loads((RUN / "reference_labels.json").read_text(encoding="utf-8"))
    if canonical_hash(reference_payload) != REFERENCE_SHA256:
        raise RuntimeError("reference canonical SHA-256 mismatch")
    reference = {int(key): value["label"] for key, value in reference_payload.items()}
    results = []
    for policy in POLICIES:
        path = RUN / f"{policy}.trace.json"
        trace = json.loads(path.read_text(encoding="utf-8"))
        results.append({"policy": policy, "raw_trace_path": str(path.relative_to(ROOT)), "raw_trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **deadline_safe_summary(trace, reference, DEADLINE)})
    by_policy = {row["policy"]: row for row in results}
    b, a, c = (by_policy[POLICIES[1]], by_policy[POLICIES[0]], by_policy[POLICIES[2]])
    deltas = {key: {"B_minus_A": b[key] - a[key], "B_minus_C": b[key] - c[key]} for key in ("event_recall_auc", "event_f1_auc", "event_recall_at_deadline", "event_f1_at_deadline")}
    status = "ORDER_SIGNAL_POSITIVE_EXPLORATORY" if b["event_recall_auc"] > max(a["event_recall_auc"], c["event_recall_auc"]) and b["distinct_confirmed_events_at_deadline"] > max(a["distinct_confirmed_events_at_deadline"], c["distinct_confirmed_events_at_deadline"]) else "NO_USEFUL_ORDER_SIGNAL_AT_300S_EXPLORATORY"
    output = {"scientific_status": status, "evaluation_mode": "STRICT_HARD_DEADLINE_COMPLETION", "deadline_seconds": DEADLINE, "raw_execution_reused": True, "policy_rerun": False, "oracle_rerun": False, "reference_reused": True, "reference_sha256": REFERENCE_SHA256, "results": results, "deltas": deltas}
    (RUN / "RESULTS_DEADLINE_SAFE.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Deadline-safe exploratory results", "", "`STRICT_HARD_DEADLINE_COMPLETION`; raw traces reused; no policy or oracle rerun.", "", "| Policy | Recall AUC | Recall@300 | F1 AUC | F1@300 | Events@300 | SCAN<=300 | VERIFY<=300 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in results:
        lines.append(f"| {row['policy']} | {row['event_recall_auc']:.9f} | {row['event_recall_at_deadline']:.9f} | {row['event_f1_auc']:.9f} | {row['event_f1_at_deadline']:.9f} | {row['distinct_confirmed_events_at_deadline']} | {row['scan_actions_completed_at_deadline']} | {row['verify_actions_completed_at_deadline']} |")
    (RUN / "RESULTS_DEADLINE_SAFE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
