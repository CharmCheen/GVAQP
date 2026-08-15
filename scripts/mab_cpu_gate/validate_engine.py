#!/usr/bin/env python3
"""Engine fidelity validation: reproduce P2 TRACE_MANIFEST EventF1 for
Q_VULNERABLE (full 1475 label grid available) using C1 + strict-overlap
matching, and compare byte-level with frozen manifest values."""
import csv, json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import (VIDEOS, QUERY_VULN, load_unit_grid, load_qwen32_labels,
                    load_p2_manifest, c1_materialize, event_f1)

grid = load_unit_grid()
labels = load_qwen32_labels()
manifest = [r for r in load_p2_manifest() if r["query_id"] == QUERY_VULN]
print(f"Q_VULNERABLE manifest rows: {len(manifest)}")

# full-grid C1 reference per video
unit_id_to_interval = {}
for v in VIDEOS:
    for u in grid[v]:
        unit_id_to_interval[u["candidate_id"]] = (u["candidate_id"], u["start_time"], u["end_time"])

references = {}
for v in VIDEOS:
    pos = [unit_id_to_interval[cid] for cid in sorted(unit_id_to_interval)
           if cid.startswith(f"{v}_") and labels.get(cid) == "relevant"]
    references[v] = c1_materialize(v, QUERY_VULN, pos)
    print(f"  {v}: positives={len(pos)} reference_events={len(references[v])}")

mismatch = 0
checked = 0
examples = []
for r in manifest:
    video = r["video_id"]
    units = json.loads(r["queried_unit_ids_json"])
    outs = json.loads(r["oracle_outcomes_json"])
    pos = [unit_id_to_interval[u] for u, o in zip(units, outs) if o == "relevant"]
    pred = c1_materialize(video, QUERY_VULN, pos)
    m = event_f1(pred, references[video])
    checked += 1
    for key in ("EventF1", "EventPrecision", "EventRecall", "TP", "FP", "FN"):
        got = m[key]
        exp = float(r[key])
        if abs(got - exp) > 1e-9:
            mismatch += 1
            if len(examples) < 5:
                examples.append((r["trace_hash"], key, got, exp))
    # reference coverage diagnostics from manifest (column exists: offline_reference_events_touched)
    if r["offline_reference_events_touched"] not in ("", "None") and len(examples) < 5:
        touched = int(r["offline_reference_events_touched"])
        if touched > len(references[video]):
            examples.append((r["trace_hash"], "offline_reference_events_touched", touched, len(references[video])))

print(f"checked={checked} mismatches={mismatch}")
for e in examples:
    print("  MISMATCH:", e)
sys.exit(0 if mismatch == 0 else 1)
