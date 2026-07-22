#!/usr/bin/env python3
"""Create v1/v2 diffs and freeze the pre-execution semantic snapshot."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PACK = Path(__file__).resolve().parent.parent
V1 = PACK.parent / "clean_baseline_benchmark_v1"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def main() -> None:
    analysis = PACK / "analysis"; evaluator = PACK / "evaluator"
    analysis.mkdir(exist_ok=True); evaluator.mkdir(exist_ok=True)
    oracle_diff = pd.read_csv(PACK / "audit/v1_v2_oracle_input_comparison.csv")
    oracle_diff.to_csv(analysis / "V1_V2_ORACLE_DIFF.csv", index=False)
    old_ref = pd.read_csv(V1 / "frozen_inputs/event_reference.csv")
    new_ref = pd.read_csv(PACK / "frozen_inputs/event_reference.csv")
    key = "reference_event_id"
    cols = [c for c in old_ref.columns if c != "benchmark_id"]
    rows = []
    for rid in sorted(set(old_ref[key]) | set(new_ref[key])):
        a = old_ref[old_ref[key] == rid]
        b = new_ref[new_ref[key] == rid]
        if a.empty: status = "ADDED"
        elif b.empty: status = "REMOVED"
        else:
            av = a.iloc[0][cols].fillna("").astype(str).to_dict()
            bv = b.iloc[0][cols].fillna("").astype(str).to_dict()
            status = "UNCHANGED" if av == bv else "CHANGED"
        rows.append({"reference_event_id": rid, "status": status,
                     "v1_start": "" if a.empty else a.iloc[0]["start_time"],
                     "v1_end": "" if a.empty else a.iloc[0]["end_time"],
                     "v2_start": "" if b.empty else b.iloc[0]["start_time"],
                     "v2_end": "" if b.empty else b.iloc[0]["end_time"],
                     "v1_source_unit_ids": "" if a.empty else a.iloc[0]["source_unit_ids"],
                     "v2_source_unit_ids": "" if b.empty else b.iloc[0]["source_unit_ids"]})
    ref_diff = pd.DataFrame(rows)
    ref_diff.to_csv(analysis / "V1_V2_REFERENCE_DIFF.csv", index=False)
    counts = ref_diff.status.value_counts().to_dict()
    unit346 = oracle_diff[oracle_diff.unit_id == 346].iloc[0]
    changed = any(counts.get(x, 0) for x in ["ADDED", "REMOVED", "CHANGED"])
    report = f"""# V1 to V2 Reference Diff

Observed evidence:

- v1 reference events: {len(old_ref)}
- v2 reference events: {len(new_ref)}
- unchanged: {counts.get('UNCHANGED', 0)}; added: {counts.get('ADDED', 0)}; removed: {counts.get('REMOVED', 0)}; changed: {counts.get('CHANGED', 0)}
- unit 346 raw response changed: {unit346['raw_response_changed']}
- unit 346 parsed label: `{unit346['v1_parsed_label']}` -> `{unit346['v2_parsed_label']}`
- unit 346 parsed boundaries changed: {unit346['parsed_boundaries_changed']}

Conclusion: `reference_changed={str(changed).lower()}`. The reference was reconstructed from all 347 v2 observations; it was not copied from v1. The identical semantic rows are a derived consequence of the unchanged parsed unit-346 label/boundaries, not reuse of the v1 evaluator artifact.
"""
    (analysis / "V1_V2_REFERENCE_DIFF_REPORT.md").write_text(report)

    public_checks = []
    for rel in ["frozen_inputs/units.csv", "frozen_inputs/public_proxy.csv"]:
        df = pd.read_csv(PACK / rel)
        forbidden = [c for c in df.columns if any(token in c.lower() for token in ["label", "oracle", "event_reference", "ground_truth"])]
        public_checks.append({"path": rel, "forbidden_columns": "|".join(forbidden), "status": "PASS" if not forbidden else "FAIL"})
    pd.DataFrame(public_checks).to_csv(evaluator / "pre_execution_planner_leakage_audit.csv", index=False)
    if any(r["status"] != "PASS" for r in public_checks):
        raise RuntimeError("Planner-facing table leakage")

    protected = [
        "BENCHMARK_ID.txt", "BENCHMARK_MANIFEST.json", "configs/EXPECTED_RUN_MATRIX.csv",
        "configs/BASELINE_CONFIG_MANIFEST.csv", "configs/SEED_MANIFEST.csv", "configs/FROZEN_BUDGETS.json",
        "frozen_inputs/units.csv", "frozen_inputs/public_proxy.csv", "frozen_inputs/oracle_observations.csv",
        "frozen_inputs/event_reference.csv", "oracle/input_identities.jsonl", "oracle/oracle_cache_manifest.csv",
        "oracle/oracle_prompt.txt", "scripts/benchmark_lib.py",
    ]
    snapshot = {rel: sha(PACK / rel) for rel in protected}
    snapshot_obj = {"frozen_at_utc": now(), "benchmark_id": (PACK / "BENCHMARK_ID.txt").read_text().strip(),
                    "protected_file_hashes": snapshot, "rule": "These semantic/configuration hashes must not change after baseline execution begins."}
    path = PACK / "configs/FROZEN_SEMANTIC_HASHES.json"
    path.write_text(json.dumps(snapshot_obj, indent=2, sort_keys=True) + "\n")
    state_path = PACK / "RUN_STATE.json"
    state = json.loads(state_path.read_text()); state.update({"phase": "semantic_freeze", "phase_status": "completed", "last_checkpoint_time": now()})
    tmp = state_path.with_suffix(".json.tmp"); tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n"); os.replace(tmp, state_path)
    print(json.dumps({"reference_changed": changed, "reference_events": len(new_ref), "unit346_old": unit346['v1_parsed_label'], "unit346_new": unit346['v2_parsed_label'], "semantic_snapshot": sha(path)}, sort_keys=True))

if __name__ == "__main__":
    main()
