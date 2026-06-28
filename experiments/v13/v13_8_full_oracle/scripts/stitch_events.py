#!/usr/bin/env python3
"""V13.8 Event Stitching from full center10 oracle labels."""
import csv, json, os, numpy as np
from collections import defaultdict

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_8_center10_full_oracle_reference_v1"
LABELS_CSV = f"{ROOT}/tables/center10_full_oracle_labels.csv"
EVENTS_CSV = f"{ROOT}/tables/center10_vlm_oracle_events.csv"
TRACE_CSV = f"{ROOT}/tables/center10_event_stitching_trace.csv"

rows = list(csv.DictReader(open(LABELS_CSV)))
ok = [r for r in rows if r.get("parse_status","") in ("ok","parse_error") and r.get("label","")!=""]

positives = [r for r in ok if r["label"] == "positive"]
print(f"Positive anchors: {len(positives)}")

# Build event intervals from each positive anchor
raw_intervals = []
for r in positives:
    aid = r["anchor_id"]
    a_start = float(r["start_time"])
    a_end = float(r["end_time"])

    # Use absolute event boundaries if available, otherwise anchor interval
    ev_abs_start = r.get("event_start_absolute","")
    ev_abs_end = r.get("event_end_absolute","")
    if ev_abs_start and ev_abs_start != "" and ev_abs_end and ev_abs_end != "":
        try:
            es = float(ev_abs_start)
            ee = float(ev_abs_end)
        except:
            es, ee = a_start, a_end
    else:
        es, ee = a_start, a_end

    raw_intervals.append({
        "anchor_id": aid,
        "start": es,
        "end": ee,
        "event_type": r.get("event_type",""),
        "involved_object": r.get("involved_object",""),
        "confidence": r.get("confidence",""),
        "complete_event_visible": r.get("complete_event_visible",""),
        "boundary_status": r.get("boundary_status",""),
        "evidence": r.get("evidence",""),
    })

raw_intervals.sort(key=lambda x: x["start"])

# Stitching: merge intervals that overlap OR gap <= 5s
events = []
trace = []
current = None

for ri in raw_intervals:
    if current is None:
        current = {
            "start": ri["start"],
            "end": ri["end"],
            "supporting_anchors": [ri["anchor_id"]],
            "event_types": [ri["event_type"]],
            "involved_objects": [ri["involved_object"]],
            "confidences": [ri["confidence"]],
            "complete_flags": [ri["complete_event_visible"]],
            "boundary_statuses": [ri["boundary_status"]],
            "evidences": [ri["evidence"]],
        }
        trace.append({"action": "start_new", "anchor_id": ri["anchor_id"], "start": ri["start"], "end": ri["end"]})
        continue

    gap = ri["start"] - current["end"]
    same_type = ri["event_type"] == max(set(current["event_types"]), key=current["event_types"].count)

    if gap <= 5.0 or (gap <= 10.0 and same_type):
        # Merge
        current["end"] = max(current["end"], ri["end"])
        current["supporting_anchors"].append(ri["anchor_id"])
        current["event_types"].append(ri["event_type"])
        current["involved_objects"].append(ri["involved_object"])
        current["confidences"].append(ri["confidence"])
        current["complete_flags"].append(ri["complete_event_visible"])
        current["boundary_statuses"].append(ri["boundary_status"])
        current["evidences"].append(ri["evidence"])
        trace.append({"action": "merge", "anchor_id": ri["anchor_id"], "start": ri["start"], "end": ri["end"],
                       "gap": gap, "new_group_end": current["end"]})
    else:
        # Emit current, start new
        events.append(current)
        trace.append({"action": "emit_group", "num_anchors": len(current["supporting_anchors"]),
                       "start": current["start"], "end": current["end"]})
        current = {
            "start": ri["start"],
            "end": ri["end"],
            "supporting_anchors": [ri["anchor_id"]],
            "event_types": [ri["event_type"]],
            "involved_objects": [ri["involved_object"]],
            "confidences": [ri["confidence"]],
            "complete_flags": [ri["complete_event_visible"]],
            "boundary_statuses": [ri["boundary_status"]],
            "evidences": [ri["evidence"]],
        }
        trace.append({"action": "start_new", "anchor_id": ri["anchor_id"], "start": ri["start"], "end": ri["end"]})

if current is not None:
    events.append(current)
    trace.append({"action": "emit_group_final", "num_anchors": len(current["supporting_anchors"])})

print(f"Stitched events: {len(events)}")

# Write events
event_rows = []
for i, ev in enumerate(events):
    from collections import Counter
    etype_counts = Counter(ev["event_types"])
    obj_counts = Counter(ev["involved_objects"])
    event_rows.append({
        "event_id": f"realcartest_event_{i:04d}",
        "video_id": "realcartest",
        "event_start": f"{ev['start']:.3f}",
        "event_end": f"{ev['end']:.3f}",
        "event_duration": f"{ev['end']-ev['start']:.3f}",
        "event_type_majority": etype_counts.most_common(1)[0][0] if etype_counts else "",
        "involved_object_majority": obj_counts.most_common(1)[0][0] if obj_counts else "",
        "num_supporting_anchors": len(ev["supporting_anchors"]),
        "supporting_anchor_ids": "|".join(ev["supporting_anchors"]),
        "mean_confidence_proxy": "high" if ev["confidences"].count("high") > len(ev["confidences"])/2 else "medium",
        "all_boundary_statuses": "|".join(set(ev["boundary_statuses"])),
        "complete_event_visible_all": str(all(f.lower()=="true" for f in ev["complete_flags"])),
        "evidence_summary": ev["evidences"][0][:200] if ev["evidences"] else "",
        "label_source": "VLM_ORACLE_RELATIVE",
        "oracle_version": "qwen3_vl_32b_v13_6_prompt",
    })

with open(EVENTS_CSV,"w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=event_rows[0].keys())
    w.writeheader(); w.writerows(event_rows)

# Write trace
with open(TRACE_CSV,"w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=trace[0].keys())
    w.writeheader(); w.writerows(trace)

# Summary
durations = [e["end"]-e["start"] for e in events]
print(f"\nEvent duration: mean={np.mean(durations):.1f}s, median={np.median(durations):.1f}s, max={max(durations):.1f}s")
print(f"Anchors per event: mean={np.mean([e['num_supporting_anchors'] for e in events]):.1f}")
print(f"Single-anchor events: {sum(1 for e in events if e['num_supporting_anchors']==1)}")

# Total event coverage
total_event_time = sum(e["end"]-e["start"] for e in events)
print(f"Total event time: {total_event_time:.0f}s ({total_event_time/3987.104*100:.1f}% of video)")
print(f"Written {len(event_rows)} events and {len(trace)} trace rows")
