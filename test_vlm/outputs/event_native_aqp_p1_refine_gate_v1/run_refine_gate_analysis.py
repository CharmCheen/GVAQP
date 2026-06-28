#!/usr/bin/env python3
"""
P1 REFINE Gate Analysis - No new VLM/YOLO/GPU calls.
Reads existing V13.x CSV assets and produces:
  1. refine_candidate_audit_table.csv
  2. refine_replay_metrics.csv
  3. refine_minimal_oracle_plan.csv
All outputs go to the current directory.
"""
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

BASE = "/qiuyeqing/llama_prl/G-ARC"
OUT_DIR = os.path.join(BASE, "test_vlm/outputs/event_native_aqp_p1_refine_gate_v1")

# ---------------------------------------------------------------------------
# 1. Load V13.8 full oracle labels
# ---------------------------------------------------------------------------
v138_path = os.path.join(BASE, "experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv")
with open(v138_path) as f:
    v138_rows = list(csv.DictReader(f))
v138_by_id = {r["anchor_id"]: r for r in v138_rows}
v138_pos = [r for r in v138_rows if r["label"] == "positive"]
v138_neg = [r for r in v138_rows if r["label"] == "negative"]

# ---------------------------------------------------------------------------
# 2. Load stitched events (reference boundaries)
# ---------------------------------------------------------------------------
events_path = os.path.join(BASE, "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv")
with open(events_path) as f:
    events = list(csv.DictReader(f))

# Map anchor_id -> event_id
anchor_to_event = {}
for e in events:
    for aid in e["supporting_anchor_ids"].split("|"):
        anchor_to_event[aid.strip()] = e

# ---------------------------------------------------------------------------
# 3. Load proxy features
# ---------------------------------------------------------------------------
proxy_path = os.path.join(BASE, "experiments/v13/v13_7_multimethod_replay/tables/center10_proxy_features.csv")
with open(proxy_path) as f:
    proxy_rows = list(csv.DictReader(f))
proxy_by_id = {r["anchor_id"]: r for r in proxy_rows}

# ---------------------------------------------------------------------------
# 4. Load V13.7 labeled eval subset (shifted center observations)
# ---------------------------------------------------------------------------
v137_path = os.path.join(BASE, "experiments/v13/v13_7_multimethod_replay/tables/center10_labeled_eval_subset.csv")
with open(v137_path) as f:
    v137_rows = list(csv.DictReader(f))

# Build index of V13.7 observations by time proximity
v137_obs = []
for r in v137_rows:
    ct = float(r["center_time"])
    st = float(r["start_time"])
    en = float(r["end_time"])
    v137_obs.append({
        "center": ct, "start": st, "end": en,
        "label": r["label"], "is_positive": r["is_positive"],
        "event_start": r.get("event_start", ""), "event_end": r.get("event_end", ""),
    })

# ---------------------------------------------------------------------------
# 5. Load V13.6 clip construction labels (multi-window observations)
# ---------------------------------------------------------------------------
v136_path = os.path.join(BASE, "experiments/v13/v13_6_clip_construction/tables/clip_construction_vlm_labels.csv")
with open(v136_path) as f:
    v136_rows = list(csv.DictReader(f))

# Build index by center_time -> list of policy labels
v136_by_center = defaultdict(list)
for r in v136_rows:
    ct = float(r["center_time"])
    v136_by_center[ct].append(r)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_neighbor(anchor_id, direction):
    """Get left (direction=-1) or right (direction=+1) neighbor anchor."""
    idx = int(anchor_id.split("_")[-1])
    nb_idx = idx + direction
    nb_id = f"center10_anchor_{nb_idx:04d}"
    return v138_by_id.get(nb_id, None)

def interval_iou(a_start, a_end, b_start, b_end):
    """IoU of two temporal intervals."""
    if a_end <= a_start or b_end <= b_start:
        return 0.0
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union

def boundary_error(pred_start, pred_end, ref_start, ref_end):
    """Absolute boundary errors in seconds."""
    se = abs(pred_start - ref_start)
    ee = abs(pred_end - ref_end)
    return se, ee, (se + ee) / 2.0

def find_v137_near(anchor_time, radius=5.0):
    """Find V13.7 observations within radius of anchor_time."""
    return [o for o in v137_obs if abs(o["center"] - anchor_time) <= radius]

def find_v136_near(anchor_time, radius=5.0):
    """Find V13.6 observations within radius of anchor_time."""
    result = []
    for ct, rs in v136_by_center.items():
        if abs(ct - anchor_time) <= radius:
            result.extend(rs)
    return result

# ---------------------------------------------------------------------------
# TASK 2: Build candidate audit table
# ---------------------------------------------------------------------------

audit_rows = []
for r in v138_pos:
    aid = r["anchor_id"]
    anchor_time = float(r["anchor_time"])
    clip_start = float(r["start_time"])
    clip_end = float(r["end_time"])
    ev_start_rel = float(r["event_start"]) if r["event_start"] else None
    ev_end_rel = float(r["event_end"]) if r["event_end"] else None
    ev_start_abs = float(r["event_start_absolute"]) if r["event_start_absolute"] else None
    ev_end_abs = float(r["event_end_absolute"]) if r["event_end_absolute"] else None

    left_nb = get_neighbor(aid, -1)
    right_nb = get_neighbor(aid, +1)
    left_label = left_nb["label"] if left_nb else "no_anchor"
    right_label = right_nb["label"] if right_nb else "no_anchor"

    # V13.7 shifted observations near this anchor
    v137_near = find_v137_near(anchor_time, radius=7.5)
    v137_pos_near = [o for o in v137_near if o["is_positive"] == "True" or o["label"] == "positive"]
    v137_times = [f"{o['center']:.1f}({o['label'][:3]})" for o in v137_near]

    # V13.6 multi-window observations near this anchor
    v136_near = find_v136_near(anchor_time, radius=7.5)
    v136_policies = list(set(r2["construction_policy"] for r2 in v136_near))
    v136_pos_policies = list(set(r2["construction_policy"] for r2 in v136_near if r2["label"] == "positive"))

    # Reference event
    ref_event = anchor_to_event.get(aid)
    has_ref = ref_event is not None
    ref_start = float(ref_event["event_start"]) if has_ref else None
    ref_end = float(ref_event["event_end"]) if has_ref else None

    # Truncation flags
    truncated_left = ev_start_rel is not None and ev_start_rel < 0.01
    truncated_right = ev_end_rel is not None and ev_end_rel >= float(r["duration"]) - 0.01

    # Proxy score
    pf = proxy_by_id.get(aid, {})
    proxy_score = pf.get("object_count_mean", "")

    # Evaluation flags
    can_eval_candidate_only = ev_start_abs is not None and ev_end_abs is not None
    can_eval_boundary = can_eval_candidate_only and (left_nb is not None or right_nb is not None)
    can_eval_stitch = has_ref and int(ref_event["num_supporting_anchors"]) > 1

    # Failure reasons
    failure_reasons = []
    if not can_eval_candidate_only:
        failure_reasons.append("no_event_boundary")
    if left_nb is None:
        failure_reasons.append("no_left_neighbor")
    if right_nb is None:
        failure_reasons.append("no_right_neighbor")
    if not v137_near:
        failure_reasons.append("no_shifted_v137_obs")
    if not v136_near:
        failure_reasons.append("no_multi_window_v136_obs")

    notes_parts = []
    if truncated_left:
        notes_parts.append(f"truncated_left(left_nb={left_label})")
    if truncated_right:
        notes_parts.append(f"truncated_right(right_nb={right_label})")
    if v136_pos_policies:
        notes_parts.append(f"v136_pos_policies={','.join(v136_pos_policies)}")
    if not notes_parts:
        notes_parts.append("no_truncation_detected")

    audit_rows.append({
        "candidate_id": aid,
        "source_file": "v13_8_full_oracle/tables/center10_full_oracle_labels.csv",
        "video_id": r["video_id"],
        "coarse_start": f"{clip_start:.3f}",
        "coarse_end": f"{clip_end:.3f}",
        "coarse_duration": r["duration"],
        "anchor_time": f"{anchor_time:.3f}",
        "proxy_method": "object_count_mean",
        "proxy_score": proxy_score,
        "center_oracle_label": r["label"],
        "center_oracle_confidence": r["confidence"],
        "available_left_observations": left_label,
        "available_right_observations": right_label,
        "available_context_or_stitch_observations": ref_event["num_supporting_anchors"] if ref_event else "0",
        "left_observation_times": f"{float(left_nb['start_time']):.1f}-{float(left_nb['end_time']):.1f}" if left_nb else "",
        "right_observation_times": f"{float(right_nb['start_time']):.1f}-{float(right_nb['end_time']):.1f}" if right_nb else "",
        "has_reference_boundary": str(has_ref),
        "reference_start": f"{ref_start:.3f}" if ref_start is not None else "",
        "reference_end": f"{ref_end:.3f}" if ref_end is not None else "",
        "reference_source": "center10_vlm_oracle_events.csv(stitched)" if has_ref else "",
        "can_evaluate_candidate_only": str(can_eval_candidate_only),
        "can_evaluate_boundary_refine": str(can_eval_boundary),
        "can_evaluate_stitch_or_context": str(can_eval_stitch),
        "failure_reason_if_not_evaluable": ";".join(failure_reasons) if failure_reasons else "",
        "notes": ";".join(notes_parts),
        # Extra fields for replay
        "_ev_start_abs": ev_start_abs,
        "_ev_end_abs": ev_end_abs,
        "_ref_start": ref_start,
        "_ref_end": ref_end,
        "_left_label": left_label,
        "_right_label": right_label,
        "_left_nb": left_nb,
        "_right_nb": right_nb,
        "_truncated_left": truncated_left,
        "_truncated_right": truncated_right,
        "_anchor_time": anchor_time,
        "_event_id": ref_event["event_id"] if ref_event else "",
        "_num_anchors": int(ref_event["num_supporting_anchors"]) if ref_event else 0,
    })

# Write audit table (public fields only)
audit_fields = [
    "candidate_id", "source_file", "video_id", "coarse_start", "coarse_end",
    "coarse_duration", "anchor_time", "proxy_method", "proxy_score",
    "center_oracle_label", "center_oracle_confidence",
    "available_left_observations", "available_right_observations",
    "available_context_or_stitch_observations",
    "left_observation_times", "right_observation_times",
    "has_reference_boundary", "reference_start", "reference_end", "reference_source",
    "can_evaluate_candidate_only", "can_evaluate_boundary_refine",
    "can_evaluate_stitch_or_context",
    "failure_reason_if_not_evaluable", "notes",
]
audit_out = os.path.join(OUT_DIR, "refine_candidate_audit_table.csv")
with open(audit_out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=audit_fields)
    w.writeheader()
    for row in audit_rows:
        w.writerow({k: row[k] for k in audit_fields})
print(f"[OK] Wrote audit table: {audit_out} ({len(audit_rows)} rows)")

# ---------------------------------------------------------------------------
# TASK 3: REFINE replay
# ---------------------------------------------------------------------------

# For each positive anchor, simulate three strategies:
# 1. candidate_only: use the anchor's own event boundary
# 2. candidate_plus_boundary: extend using neighbor labels
# 3. candidate_plus_stitch: use the full stitched event boundary

replay_rows = []
for row in audit_rows:
    aid = row["candidate_id"]
    ev_s = row["_ev_start_abs"]
    ev_e = row["_ev_end_abs"]
    ref_s = row["_ref_start"]
    ref_e = row["_ref_end"]
    left_label = row["_left_label"]
    right_label = row["_right_label"]
    trunc_l = row["_truncated_left"]
    trunc_r = row["_truncated_right"]
    left_nb = row["_left_nb"]
    right_nb = row["_right_nb"]
    num_anchors = row["_num_anchors"]

    if ev_s is None or ev_e is None or ref_s is None or ref_e is None:
        continue

    # Strategy 1: candidate_only
    cand_s, cand_e = ev_s, ev_e
    iou_cand = interval_iou(cand_s, cand_e, ref_s, ref_e)
    se_c, ee_c, me_c = boundary_error(cand_s, cand_e, ref_s, ref_e)

    # Strategy 2: candidate_plus_boundary
    # If truncated left and left neighbor is positive, extend left to left neighbor's event_start_abs
    # If truncated right and right neighbor is positive, extend right to right neighbor's event_end_abs
    bound_s, bound_e = ev_s, ev_e
    extended_left = False
    extended_right = False
    if trunc_l and left_nb and left_nb["label"] == "positive":
        l_ev_s = float(left_nb["event_start_absolute"]) if left_nb["event_start_absolute"] else None
        if l_ev_s is not None:
            bound_s = min(bound_s, l_ev_s)
            extended_left = True
        # If left neighbor also truncated left, extend further
        l_nb2 = get_neighbor(left_nb["anchor_id"], -1)
        if l_nb2 and l_nb2["label"] == "positive":
            l2_ev_s = float(l_nb2["event_start_absolute"]) if l_nb2["event_start_absolute"] else None
            if l2_ev_s is not None:
                bound_s = min(bound_s, l2_ev_s)
    if trunc_r and right_nb and right_nb["label"] == "positive":
        r_ev_e = float(right_nb["event_end_absolute"]) if right_nb["event_end_absolute"] else None
        if r_ev_e is not None:
            bound_e = max(bound_e, r_ev_e)
            extended_right = True
    # Also extend right if right neighbor positive even without truncation (event might continue)
    if not trunc_r and right_nb and right_nb["label"] == "positive":
        r_ev_e = float(right_nb["event_end_absolute"]) if right_nb["event_end_absolute"] else None
        r_ev_s = float(right_nb["event_start_absolute"]) if right_nb["event_start_absolute"] else None
        if r_ev_e is not None and r_ev_s is not None:
            bound_e = max(bound_e, r_ev_e)
            bound_s = min(bound_s, r_ev_s)
            extended_right = True
    # Also extend left if left neighbor positive even without truncation
    if not trunc_l and left_nb and left_nb["label"] == "positive":
        l_ev_e = float(left_nb["event_end_absolute"]) if left_nb["event_end_absolute"] else None
        l_ev_s = float(left_nb["event_start_absolute"]) if left_nb["event_start_absolute"] else None
        if l_ev_e is not None and l_ev_s is not None:
            bound_s = min(bound_s, l_ev_s)
            bound_e = max(bound_e, l_ev_e)
            extended_left = True

    iou_bound = interval_iou(bound_s, bound_e, ref_s, ref_e)
    se_b, ee_b, me_b = boundary_error(bound_s, bound_e, ref_s, ref_e)
    bound_dur = bound_e - bound_s
    ref_dur = ref_e - ref_s
    over_expansion = max(0, bound_dur - (ev_e - ev_s))

    # Strategy 3: candidate_plus_stitch (use full stitched event)
    stitch_s, stitch_e = ref_s, ref_e
    iou_stitch = 1.0  # by definition matches reference
    se_s, ee_s, me_s = 0.0, 0.0, 0.0

    # Classify outcome
    if iou_bound > iou_cand + 0.001:
        outcome = "improved"
    elif iou_bound < iou_cand - 0.001:
        outcome = "worsened"
    else:
        outcome = "unchanged"

    # Over-expansion: if boundary strategy made interval much longer than event
    is_over_expansion = over_expansion > 2.0  # >2s extra
    # Fragmentation: if this is a multi-anchor event, the individual 0.7s events are fragmented
    is_fragmentation = num_anchors > 1 and (ev_e - ev_s) < 1.0

    # False positive rejection: if center says positive but neighbors say negative and event is at clip start
    fp_rejected = False
    if (left_label == "negative" or left_label == "no_anchor") and (right_label == "negative" or right_label == "no_anchor"):
        if num_anchors == 1 and trunc_l:
            # Isolated positive with event at clip start - could be boundary artifact
            fp_rejected = False  # can't confirm without sub-clip obs
    # Check if neighbor labels disagree (potential false positive)
    neighbor_disagrees = False
    if left_nb and left_nb["label"] == "negative" and trunc_l:
        neighbor_disagrees = True  # event at clip start but left neighbor negative

    replay_rows.append({
        "candidate_id": aid,
        "event_id": row["_event_id"],
        "num_anchors_in_event": num_anchors,
        "anchor_time": f"{row['_anchor_time']:.1f}",
        "ev_start_abs": f"{ev_s:.3f}",
        "ev_end_abs": f"{ev_e:.3f}",
        "ev_duration": f"{ev_e - ev_s:.3f}",
        "ref_start": f"{ref_s:.3f}",
        "ref_end": f"{ref_e:.3f}",
        "ref_duration": f"{ref_e - ref_s:.3f}",
        "left_label": left_label,
        "right_label": right_label,
        "truncated_left": str(trunc_l),
        "truncated_right": str(trunc_r),
        "candidate_only_start": f"{cand_s:.3f}",
        "candidate_only_end": f"{cand_e:.3f}",
        "candidate_only_iou": f"{iou_cand:.6f}",
        "candidate_only_start_err": f"{se_c:.3f}",
        "candidate_only_end_err": f"{ee_c:.3f}",
        "candidate_only_mean_err": f"{me_c:.3f}",
        "boundary_refined_start": f"{bound_s:.3f}",
        "boundary_refined_end": f"{bound_e:.3f}",
        "boundary_refined_iou": f"{iou_bound:.6f}",
        "boundary_refined_start_err": f"{se_b:.3f}",
        "boundary_refined_end_err": f"{ee_b:.3f}",
        "boundary_refined_mean_err": f"{me_b:.3f}",
        "boundary_extended_left": str(extended_left),
        "boundary_extended_right": str(extended_right),
        "boundary_refined_duration": f"{bound_dur:.3f}",
        "over_expansion_seconds": f"{over_expansion:.3f}",
        "is_over_expansion": str(is_over_expansion),
        "is_fragmentation": str(is_fragmentation),
        "neighbor_disagrees": str(neighbor_disagrees),
        "outcome_vs_candidate_only": outcome,
        "stitch_iou": f"{iou_stitch:.6f}",
    })

replay_out = os.path.join(OUT_DIR, "refine_replay_metrics.csv")
with open(replay_out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(replay_rows[0].keys()))
    w.writeheader()
    w.writerows(replay_rows)
print(f"[OK] Wrote replay metrics: {replay_out} ({len(replay_rows)} rows)")

# ---------------------------------------------------------------------------
# Compute aggregate metrics
# ---------------------------------------------------------------------------

n_total = len(replay_rows)
n_improved = sum(1 for r in replay_rows if r["outcome_vs_candidate_only"] == "improved")
n_worsened = sum(1 for r in replay_rows if r["outcome_vs_candidate_only"] == "worsened")
n_unchanged = sum(1 for r in replay_rows if r["outcome_vs_candidate_only"] == "unchanged")
n_over_exp = sum(1 for r in replay_rows if r["is_over_expansion"] == "True")
n_frag = sum(1 for r in replay_rows if r["is_fragmentation"] == "True")
n_neighbor_disagree = sum(1 for r in replay_rows if r["neighbor_disagrees"] == "True")

iou_cand_vals = [float(r["candidate_only_iou"]) for r in replay_rows]
iou_bound_vals = [float(r["boundary_refined_iou"]) for r in replay_rows]
me_cand_vals = [float(r["candidate_only_mean_err"]) for r in replay_rows]
me_bound_vals = [float(r["boundary_refined_mean_err"]) for r in replay_rows]

# Split by single vs multi-anchor
single_rows = [r for r in replay_rows if int(r["num_anchors_in_event"]) == 1]
multi_rows = [r for r in replay_rows if int(r["num_anchors_in_event"]) > 1]

agg = {
    "n_total": n_total,
    "n_improved": n_improved,
    "n_worsened": n_worsened,
    "n_unchanged": n_unchanged,
    "n_over_expansion": n_over_exp,
    "n_fragmentation": n_frag,
    "n_neighbor_disagrees": n_neighbor_disagree,
    "iou_cand_mean": sum(iou_cand_vals) / len(iou_cand_vals),
    "iou_bound_mean": sum(iou_bound_vals) / len(iou_bound_vals),
    "me_cand_mean": sum(me_cand_vals) / len(me_cand_vals),
    "me_bound_mean": sum(me_bound_vals) / len(me_bound_vals),
    "n_single_anchor": len(single_rows),
    "n_multi_anchor": len(multi_rows),
    "iou_cand_single_mean": sum(float(r["candidate_only_iou"]) for r in single_rows) / len(single_rows) if single_rows else 0,
    "iou_bound_single_mean": sum(float(r["boundary_refined_iou"]) for r in single_rows) / len(single_rows) if single_rows else 0,
    "iou_cand_multi_mean": sum(float(r["candidate_only_iou"]) for r in multi_rows) / len(multi_rows) if multi_rows else 0,
    "iou_bound_multi_mean": sum(float(r["boundary_refined_iou"]) for r in multi_rows) / len(multi_rows) if multi_rows else 0,
    "me_cand_single_mean": sum(float(r["candidate_only_mean_err"]) for r in single_rows) / len(single_rows) if single_rows else 0,
    "me_bound_single_mean": sum(float(r["boundary_refined_mean_err"]) for r in single_rows) / len(single_rows) if single_rows else 0,
    "me_cand_multi_mean": sum(float(r["candidate_only_mean_err"]) for r in multi_rows) / len(multi_rows) if multi_rows else 0,
    "me_bound_multi_mean": sum(float(r["boundary_refined_mean_err"]) for r in multi_rows) / len(multi_rows) if multi_rows else 0,
    "n_fp_rejected": 0,  # cannot confirm without sub-clip obs
}

# Event boundary degeneracy statistics
deg_start0 = sum(1 for r in v138_pos if float(r["event_start"]) < 0.01)
deg_end07 = sum(1 for r in v138_pos if 0.69 <= float(r["event_end"]) <= 0.71)
deg_both = sum(1 for r in v138_pos if float(r["event_start"]) < 0.01 and 0.69 <= float(r["event_end"]) <= 0.71)
agg["deg_start0_count"] = deg_start0
agg["deg_end07_count"] = deg_end07
agg["deg_both_count"] = deg_both
agg["deg_start0_pct"] = deg_start0 / len(v138_pos) * 100
agg["deg_both_pct"] = deg_both / len(v138_pos) * 100

print(f"\n=== REPLAY AGGREGATES ===")
for k, v in agg.items():
    if isinstance(v, float):
        print(f"  {k}: {v:.6f}")
    else:
        print(f"  {k}: {v}")

# Save aggregates as JSON
agg_out = os.path.join(OUT_DIR, "refine_replay_aggregates.json")
with open(agg_out, "w") as f:
    json.dump(agg, f, indent=2)
print(f"\n[OK] Wrote aggregates: {agg_out}")

# ---------------------------------------------------------------------------
# TASK 4: Minimal oracle plan
# ---------------------------------------------------------------------------

# Select priority candidates for minimal oracle supplementation
# Priority 1: multi-anchor events (to test if sub-clip obs can resolve over-expansion)
# Priority 2: single-anchor events with truncation_left (to test if event truly starts at clip boundary)
# Priority 3: neighbor-disagreement cases (to test if center positive is a false positive)

oracle_plan = []
plan_id = 0

# Group positives by event
event_groups = defaultdict(list)
for row in audit_rows:
    eid = row["_event_id"]
    if eid:
        event_groups[eid].append(row)

# Priority 1: For each multi-anchor event, propose sub-clip obs at the first and last anchor
for eid, group in sorted(event_groups.items()):
    n = len(group)
    if n <= 1:
        continue
    # Sort by anchor time
    group_sorted = sorted(group, key=lambda x: x["_anchor_time"])
    first = group_sorted[0]
    last = group_sorted[-1]
    ev_s = first["_ev_start_abs"]
    ev_e = last["_ev_end_abs"]
    # Propose: 2s sub-clip at first anchor's event start boundary
    plan_id += 1
    oracle_plan.append({
        "candidate_id": first["candidate_id"],
        "video_id": first["video_id"],
        "coarse_start": first["coarse_start"],
        "coarse_end": first["coarse_end"],
        "proposed_timestamp_or_interval": f"[{ev_s - 2.0:.1f}, {ev_s + 2.0:.1f}]",
        "reason": f"Multi-anchor event({n} anchors): sub-clip at start boundary to test if event truly starts here or extends left",
        "reason_type": "left_boundary",
        "expected_value": "Determine true event start with 2s resolution vs current degenerate 0.0s-relative pattern",
        "estimated_oracle_cost": "1",
        "priority": "1",
        "notes": f"event={eid}; current ev_start_abs={ev_s:.1f}; over-expansion risk",
    })
    plan_id += 1
    oracle_plan.append({
        "candidate_id": last["candidate_id"],
        "video_id": last["video_id"],
        "coarse_start": last["coarse_start"],
        "coarse_end": last["coarse_end"],
        "proposed_timestamp_or_interval": f"[{ev_e - 2.0:.1f}, {ev_e + 2.0:.1f}]",
        "reason": f"Multi-anchor event({n} anchors): sub-clip at end boundary to test if event truly ends here or extends right",
        "reason_type": "right_boundary",
        "expected_value": "Determine true event end with 2s resolution vs current degenerate 0.7s-relative pattern",
        "estimated_oracle_cost": "1",
        "priority": "1",
        "notes": f"event={eid}; current ev_end_abs={ev_e:.1f}; over-expansion risk",
    })
    # Propose: gap observation between first and second anchor (to test fragmentation)
    if n >= 3:
        mid_idx = len(group_sorted) // 2
        mid = group_sorted[mid_idx]
        mid_s = mid["_ev_start_abs"]
        plan_id += 1
        oracle_plan.append({
            "candidate_id": mid["candidate_id"],
            "video_id": mid["video_id"],
            "coarse_start": mid["coarse_start"],
            "coarse_end": mid["coarse_end"],
            "proposed_timestamp_or_interval": f"[{mid_s - 5.0:.1f}, {mid_s + 5.0:.1f}]",
            "reason": f"Multi-anchor event({n} anchors): mid-gap observation to test if event is continuous or fragmented",
            "reason_type": "stitch_context",
            "expected_value": "Determine if intermediate time is truly positive or gap between separate events",
            "estimated_oracle_cost": "1",
            "priority": "1",
            "notes": f"event={eid}; tests fragmentation hypothesis",
        })

# Priority 2: Single-anchor events with truncation_left (sample up to 10)
single_trunc = [r for r in audit_rows if r["_num_anchors"] == 1 and r["_truncated_left"]]
for row in single_trunc[:10]:
    ev_s = row["_ev_start_abs"]
    plan_id += 1
    oracle_plan.append({
        "candidate_id": row["candidate_id"],
        "video_id": row["video_id"],
        "coarse_start": row["coarse_start"],
        "coarse_end": row["coarse_end"],
        "proposed_timestamp_or_interval": f"[{ev_s - 2.0:.1f}, {ev_s + 2.0:.1f}]",
        "reason": "Single-anchor event truncated at left: sub-clip to test if event truly starts at clip boundary or is a VLM artifact",
        "reason_type": "left_boundary",
        "expected_value": "Determine if 0.0s-relative event_start is real or VLM default behavior",
        "estimated_oracle_cost": "1",
        "priority": "2",
        "notes": f"left_nb={row['_left_label']}; degenerate boundary pattern",
    })

# Priority 3: Neighbor disagreement cases
for row in audit_rows:
    if row["_left_label"] == "negative" and row["_truncated_left"] and row["_num_anchors"] == 1:
        ev_s = row["_ev_start_abs"]
        plan_id += 1
        oracle_plan.append({
            "candidate_id": row["candidate_id"],
            "video_id": row["video_id"],
            "coarse_start": row["coarse_start"],
            "coarse_end": row["coarse_end"],
            "proposed_timestamp_or_interval": f"[{ev_s - 3.0:.1f}, {ev_s + 1.0:.1f}]",
            "reason": "Center positive but left neighbor negative with event at clip start: test if positive is a boundary artifact / false positive",
            "reason_type": "ambiguity",
            "expected_value": "Determine if positive label is genuine or VLM boundary artifact at clip edge",
            "estimated_oracle_cost": "1",
            "priority": "3",
            "notes": f"left_nb=negative, ev at clip start; potential false positive",
        })
        if len([p for p in oracle_plan if p["reason_type"] == "ambiguity"]) >= 10:
            break

# Priority 4: Hard negatives near positives (sample a few)
for row in audit_rows[:5]:
    if row["_left_label"] == "negative":
        clip_s = float(row["coarse_start"])
        plan_id += 1
        oracle_plan.append({
            "candidate_id": row["candidate_id"],
            "video_id": row["video_id"],
            "coarse_start": row["coarse_start"],
            "coarse_end": row["coarse_end"],
            "proposed_timestamp_or_interval": f"[{clip_s - 2.0:.1f}, {clip_s + 2.0:.1f}]",
            "reason": "Hard negative near positive: sub-clip at boundary between negative and positive anchor to test label consistency",
            "reason_type": "hard_negative",
            "expected_value": "Verify label consistency at clip boundary; test if VLM labels are stable at 2s resolution",
            "estimated_oracle_cost": "1",
            "priority": "4",
            "notes": f"clip boundary between neg and pos; label stability test",
        })

plan_out = os.path.join(OUT_DIR, "refine_minimal_oracle_plan.csv")
plan_fields = [
    "candidate_id", "video_id", "coarse_start", "coarse_end",
    "proposed_timestamp_or_interval", "reason", "reason_type",
    "expected_value", "estimated_oracle_cost", "priority", "notes",
]
with open(plan_out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=plan_fields)
    w.writeheader()
    w.writerows(oracle_plan)
total_cost = sum(int(p["estimated_oracle_cost"]) for p in oracle_plan)
print(f"[OK] Wrote minimal oracle plan: {plan_out} ({len(oracle_plan)} calls, total cost={total_cost})")

# Print summary for report generation
print(f"\n=== MINIMAL ORACLE PLAN SUMMARY ===")
by_type = Counter(p["reason_type"] for p in oracle_plan)
by_priority = Counter(p["priority"] for p in oracle_plan)
print(f"  By type: {dict(by_type)}")
print(f"  By priority: {dict(by_priority)}")
print(f"  Total calls: {len(oracle_plan)}")
