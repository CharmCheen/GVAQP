#!/usr/bin/env python3
"""V13.7 Center10 Multi-Method Replay — Stages 0-6.
No new VLM. All processing from existing V13.5/V13.6 artifacts."""

import csv, json, os, sys, math, random, numpy as np
from collections import defaultdict, Counter

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_7_center10_multi_method_replay_v1"
V13_5 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
V13_6 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1"
VIDEO_DURATION = 3987.104

for d in ["tables","reports","logs"]:
    os.makedirs(f"{ROOT}/{d}", exist_ok=True)

random.seed(42)
np.random.seed(42)

# ═══════════════════════════════════════════════════════════
# STAGE 0: Input Audit
# ═══════════════════════════════════════════════════════════
inputs = {
    "coarse_5s_clip_grid.csv": f"{V13_5}/tables/coarse_5s_clip_grid.csv",
    "proxy_features_5s.csv": f"{V13_5}/tables/proxy_features_5s.csv",
    "clip_construction_samples.csv": f"{V13_6}/tables/clip_construction_samples.csv",
    "clip_construction_vlm_labels.csv": f"{V13_6}/tables/clip_construction_vlm_labels.csv",
    "clip_construction_policy_summary.csv": f"{V13_6}/tables/clip_construction_policy_summary.csv",
    "full_video_call_cost_estimates.csv": f"{V13_6}/tables/full_video_call_cost_estimates.csv",
    "V13_6_FINAL_REPORT.md": f"{V13_6}/reports/FINAL_REPORT.md",
}

inv = []
all_ok = True
for name, path in inputs.items():
    exists = os.path.exists(path)
    if not exists: all_ok = False
    nrows = 0
    if exists and path.endswith(".csv"):
        with open(path) as f:
            nrows = sum(1 for _ in f) - 1
    inv.append({"input_name": name, "path": path, "exists": str(exists), "rows": str(nrows)})

with open(f"{ROOT}/tables/input_inventory.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=["input_name","path","exists","rows"])
    w.writeheader(); w.writerows(inv)

print(f"Stage 0: {'ALL INPUTS PRESENT' if all_ok else 'MISSING INPUTS'}")

# ═══════════════════════════════════════════════════════════
# STAGE 1: Build full-video center10 anchor grid
# ═══════════════════════════════════════════════════════════
anchor_interval = 10.0
half_window = 5.0
n_anchors = math.ceil(VIDEO_DURATION / anchor_interval)

anchors = []
for i in range(n_anchors):
    anchor_t = i * anchor_interval + anchor_interval / 2  # center of each interval
    if anchor_t > VIDEO_DURATION:
        anchor_t = VIDEO_DURATION
    start = max(0.0, anchor_t - half_window)
    end = min(VIDEO_DURATION, anchor_t + half_window)
    anchors.append({
        "anchor_id": f"center10_anchor_{i:04d}",
        "video_id": "realcartest",
        "anchor_time": f"{anchor_t:.3f}",
        "start_time": f"{start:.3f}",
        "end_time": f"{end:.3f}",
        "duration": f"{end - start:.3f}",
        "source_video_path": "/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4",
        "construction_policy": "center_10s",
    })

with open(f"{ROOT}/tables/center10_anchor_grid.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=anchors[0].keys())
    w.writeheader(); w.writerows(anchors)

print(f"Stage 1: {len(anchors)} center10 anchors (interval={anchor_interval}s)")

# ═══════════════════════════════════════════════════════════
# STAGE 2: Aggregate 5s proxy features → center10 anchors
# ═══════════════════════════════════════════════════════════
proxies_5s = {}
with open(f"{V13_5}/tables/proxy_features_5s.csv") as f:
    for row in csv.DictReader(f):
        proxies_5s[row["clip_id"]] = row

# Map each anchor to overlapping 5s clips
anchor_features = []
for a in anchors:
    a_start = float(a["start_time"])
    a_end = float(a["end_time"])
    overlapping = []
    for cid, crow in proxies_5s.items():
        c_start = float(crow["start_time"])
        c_end = float(crow["end_time"])
        if c_end > a_start and c_start < a_end:  # any overlap
            overlapping.append(crow)

    if not overlapping:
        overlapping = [list(proxies_5s.values())[0]]  # fallback

    def agg(key, fn):
        vals = [float(r[key]) for r in overlapping if r.get(key,"") != ""]
        return fn(vals) if vals else 0.0

    feat = {
        "anchor_id": a["anchor_id"],
        "anchor_time": a["anchor_time"],
        "num_overlapping_5s_clips": len(overlapping),
        "yolo_vehicle_mean": agg("vehicle_count_mean", np.mean),
        "yolo_vehicle_max": agg("vehicle_count_mean", np.max),
        "yolo_vehicle_sum": agg("vehicle_count_mean", np.sum),
        "object_count_mean": agg("object_count_mean", np.mean),
        "object_count_max": agg("object_count_mean", np.max),
        "bbox_area_sum_mean": agg("bbox_area_sum_mean", np.mean),
        "bbox_area_sum_max": agg("bbox_area_sum_mean", np.max),
        "max_bbox_area_mean": agg("max_bbox_area_mean", np.mean),
        "max_bbox_area_max": agg("max_bbox_area_mean", np.max),
        "center_roi_vehicle_count_mean": agg("center_roi_vehicle_count_mean", np.mean),
        "bottom_roi_vehicle_count_mean": agg("bottom_roi_vehicle_count_mean", np.mean),
        "motion_energy_mean": agg("motion_energy_mean", np.mean),
        "motion_energy_max": agg("motion_energy_mean", np.max),
        "motion_energy_sum": agg("motion_energy_mean", np.sum),
    }
    anchor_features.append(feat)

# Normalized scores
vals_vm = np.array([f["yolo_vehicle_max"] for f in anchor_features])
vals_ba = np.array([f["bbox_area_sum_max"] for f in anchor_features])
vals_me = np.array([f["motion_energy_max"] for f in anchor_features])
vals_cr = np.array([f["center_roi_vehicle_count_mean"] for f in anchor_features])

z = lambda v, arr: (v - np.mean(arr)) / (np.std(arr) + 1e-8)

for f in anchor_features:
    f["z_yolo_vehicle_max"] = float(z(f["yolo_vehicle_max"], vals_vm))
    f["z_bbox_area_sum_max"] = float(z(f["bbox_area_sum_max"], vals_ba))
    f["z_motion_energy_max"] = float(z(f["motion_energy_max"], vals_me))
    f["z_center_roi_count_mean"] = float(z(f["center_roi_vehicle_count_mean"], vals_cr))
    f["score_yolo_count"] = f["z_yolo_vehicle_max"]
    f["score_yolo_geometry"] = f["z_bbox_area_sum_max"]
    f["score_motion"] = f["z_motion_energy_max"]
    f["score_fusion_yolo_motion"] = f["z_yolo_vehicle_max"] + f["z_motion_energy_max"]
    f["score_fusion_geometry_motion"] = f["z_bbox_area_sum_max"] + f["z_motion_energy_max"]

fieldnames = list(anchor_features[0].keys())
with open(f"{ROOT}/tables/center10_proxy_features.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader(); w.writerows(anchor_features)

# Invariant check
forbidden = ["vlm","oracle","label","event_start","event_end","positive","negative"]
for fn in fieldnames:
    for fb in forbidden:
        if fb in fn.lower():
            print(f"  INVARIANT FAIL: field '{fn}' matches forbidden '{fb}'")
print(f"Stage 2: {len(anchor_features)} center10 anchors with aggregated proxy features")

# ═══════════════════════════════════════════════════════════
# STAGE 3: Build labeled evaluation subset from V13.6
# ═══════════════════════════════════════════════════════════
vlm_labels = list(csv.DictReader(open(f"{V13_6}/tables/clip_construction_vlm_labels.csv")))
center10_labels = [r for r in vlm_labels if r["construction_policy"] == "center_10s" and r.get("vlm_call_status","") == "ok"]

eval_rows = []
for r in center10_labels:
    eval_rows.append({
        "eval_id": r["sample_id"],
        "source_pilot_clip_id": r["source_pilot_clip_id"],
        "center_time": r["center_time"],
        "start_time": r["start_time"],
        "end_time": r["end_time"],
        "label": r["label"],
        "is_positive": str(r["label"] == "positive"),
        "event_start": r.get("event_start",""),
        "event_end": r.get("event_end",""),
        "event_type": r.get("event_type",""),
        "involved_object": r.get("involved_object",""),
        "boundary_status": r.get("boundary_status",""),
        "complete_event_visible": r.get("complete_event_visible",""),
        "confidence": r.get("confidence",""),
        "source_sample_source": r.get("source_sample_source",""),
        "raw_response_path": f"{V13_6}/raw_vlm_responses/{r['sample_id']}.json",
    })

with open(f"{ROOT}/tables/center10_labeled_eval_subset.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=eval_rows[0].keys())
    w.writeheader(); w.writerows(eval_rows)

pos_count = sum(1 for r in eval_rows if r["label"] == "positive")
print(f"Stage 3: {len(eval_rows)} labeled center10 clips ({pos_count} positive)")

# ═══════════════════════════════════════════════════════════
# STAGE 4 + 5: Define methods and evaluate
# ═══════════════════════════════════════════════════════════

# Build anchor index
anchor_by_id = {a["anchor_id"]: a for a in anchors}
anchor_feat_by_id = {f["anchor_id"]: f for f in anchor_features}

# Map eval clips to nearest center10 anchors by center_time
# The eval subset has specific start/end times. Find which center10 anchor each belongs to.
eval_by_anchor = defaultdict(list)
for e in eval_rows:
    ct = float(e["center_time"])
    # Find nearest anchor
    best_aid = None
    best_dist = float("inf")
    for a in anchors:
        at = float(a["anchor_time"])
        dist = abs(ct - at)
        if dist < best_dist:
            best_dist = dist
            best_aid = a["anchor_id"]
    if best_dist < 6.0:  # within half window + margin
        eval_by_anchor[best_aid].append(e)

print(f"Stage 4: {len(eval_by_anchor)} anchors have labeled clips (out of {len(anchors)} total)")

# Define scoring functions
def score_method(anchor_feat, method_name):
    """Return score for an anchor under a method. Higher = more likely positive."""
    f = anchor_feat
    if method_name == "uniform_anchor_10s":
        return 0.0  # uniform — use index order
    elif method_name.startswith("random_anchor"):
        return 0.0  # random — handled separately
    elif method_name == "top_yolo_vehicle_max":
        return f["yolo_vehicle_max"]
    elif method_name == "top_yolo_vehicle_mean":
        return f["yolo_vehicle_mean"]
    elif method_name == "top_bbox_area_sum_max":
        return f["bbox_area_sum_max"]
    elif method_name == "top_center_roi_count":
        return f["center_roi_vehicle_count_mean"]
    elif method_name == "top_motion_energy_max":
        return f["motion_energy_max"]
    elif method_name == "top_fusion_yolo_motion":
        return f["score_fusion_yolo_motion"]
    elif method_name == "top_fusion_geometry_motion":
        return f["score_fusion_geometry_motion"]
    else:
        return 0.0

# All methods
proxy_methods = [
    "top_yolo_vehicle_max", "top_yolo_vehicle_mean", "top_bbox_area_sum_max",
    "top_center_roi_count", "top_motion_energy_max",
    "top_fusion_yolo_motion", "top_fusion_geometry_motion",
]
baseline_methods = ["uniform_anchor_10s"] + [f"random_anchor_seed{s}" for s in range(1,6)]
hybrid_methods = ["hybrid_70_proxy_30_uniform", "hybrid_50_proxy_50_uniform"]
nms_methods = ["temporal_nms_yolo_vehicle_max", "temporal_nms_fusion_yolo_motion"]
all_methods = baseline_methods + proxy_methods + hybrid_methods + nms_methods

budgets_absolute = [5, 10, 20, 40]
budgets_percent = [0.05, 0.10, 0.20, 0.30]

def select_anchors_by_method(method, budget_value, budget_type="absolute"):
    """Select anchors for a method and budget. Returns list of anchor_ids."""
    n_total = len(anchors)

    if budget_type == "absolute":
        n_select = min(budget_value, n_total)
    else:  # percent
        n_select = max(1, int(n_total * budget_value))

    if method == "uniform_anchor_10s":
        # Uniform sampling: every nth anchor
        step = n_total // n_select
        selected = [anchors[i]["anchor_id"] for i in range(0, n_total, step)][:n_select]

    elif method.startswith("random_anchor"):
        seed = int(method.split("seed")[1]) if "seed" in method else 42
        rng = random.Random(seed)
        indices = list(range(n_total))
        rng.shuffle(indices)
        selected = [anchors[i]["anchor_id"] for i in indices[:n_select]]

    elif method in proxy_methods:
        # Sort by proxy score descending
        sorted_anchors = sorted(anchor_features, key=lambda f: score_method(f, method), reverse=True)
        selected = [f["anchor_id"] for f in sorted_anchors[:n_select]]

    elif method.startswith("hybrid_"):
        # Parse: hybrid_70_proxy_30_uniform
        parts = method.split("_")
        proxy_pct = int(parts[1]) / 100.0
        proxy_method_name = "top_fusion_yolo_motion"  # default proxy for hybrid
        n_proxy = int(n_select * proxy_pct)
        n_uniform = n_select - n_proxy

        # Proxy picks
        sorted_anchors = sorted(anchor_features, key=lambda f: score_method(f, proxy_method_name), reverse=True)
        proxy_picks = set(f["anchor_id"] for f in sorted_anchors[:n_proxy*2])  # oversample for diversity
        selected = list(proxy_picks)[:n_proxy]

        # Uniform defensive picks from remaining
        remaining = [a["anchor_id"] for a in anchors if a["anchor_id"] not in set(selected)]
        step = max(1, len(remaining) // n_uniform) if n_uniform > 0 else 1
        uniform_picks = [remaining[i] for i in range(0, len(remaining), step)][:n_uniform]
        selected.extend(uniform_picks)
        selected = selected[:n_select]

    elif method.startswith("temporal_nms_"):
        # Extract base method and NMS gap
        base = method.replace("temporal_nms_", "")
        nms_gap = 30.0  # default 30s

        # Over-select then NMS
        sorted_anchors = sorted(anchor_features, key=lambda f: score_method(f, base), reverse=True)
        candidate_pool = sorted_anchors[:n_select * 3]

        selected = []
        for f in candidate_pool:
            at = float(f["anchor_time"])
            # Check if too close to already selected
            too_close = False
            for sid in selected:
                sat = float(anchor_feat_by_id[sid]["anchor_time"])
                if abs(at - sat) < nms_gap:
                    too_close = True
                    break
            if not too_close:
                selected.append(f["anchor_id"])
            if len(selected) >= n_select:
                break

    else:
        selected = [anchors[i]["anchor_id"] for i in range(min(n_select, n_total))]

    return selected[:n_select]


def evaluate_selection(selected_anchor_ids, method, budget_type, budget_value):
    """Evaluate a set of selected anchors against labeled subset."""
    selected_set = set(selected_anchor_ids)

    # Count labeled clips covered
    labeled_selected = []
    for aid in selected_set:
        if aid in eval_by_anchor:
            labeled_selected.extend(eval_by_anchor[aid])

    n_labeled = len(labeled_selected)
    n_pos = sum(1 for e in labeled_selected if e["label"] == "positive")
    total_pos_in_subset = sum(1 for e in eval_rows if e["label"] == "positive")

    # Compute completeness metrics
    complete_events = [e for e in labeled_selected if e["label"] == "positive" and e.get("complete_event_visible","").lower() == "true"]
    boundary_ok = [e for e in labeled_selected if e["label"] == "positive" and e.get("boundary_status","") == "ok"]

    # Enrichment vs uniform
    uniform_pos_rate = total_pos_in_subset / len(eval_rows) if eval_rows else 0
    selected_pos_rate = n_pos / n_labeled if n_labeled else 0
    enrichment = (selected_pos_rate / uniform_pos_rate - 1.0) if uniform_pos_rate > 0 else 0

    # Compute mean proxy score for selected
    scores = [score_method(anchor_feat_by_id[aid], "top_fusion_yolo_motion") for aid in selected_anchor_ids if aid in anchor_feat_by_id]
    mean_score = np.mean(scores) if scores else 0

    return {
        "method": method,
        "budget_type": budget_type,
        "budget_value": str(budget_value),
        "num_selected_anchors": len(selected_anchor_ids),
        "num_labeled_selected": n_labeled,
        "num_labeled_positive_selected": n_pos,
        "num_labeled_positive_total": total_pos_in_subset,
        "positive_recall_on_labeled_subset": n_pos / total_pos_in_subset if total_pos_in_subset else 0,
        "precision_on_labeled_subset": n_pos / n_labeled if n_labeled else 0,
        "enrichment_vs_uniform": enrichment,
        "complete_event_selected_count": len(complete_events),
        "complete_event_rate_selected": len(complete_events) / n_pos if n_pos else 0,
        "boundary_ok_selected_count": len(boundary_ok),
        "mean_proxy_score_selected": mean_score,
        "estimated_full_video_calls": len(selected_anchor_ids),
        "estimated_32B_wall_time_seconds": len(selected_anchor_ids) * 20,  # ~20s per call
        "claim_scope": "LABELED_SUBSET_RANKING_ONLY",
    }

# Run all evaluations
all_results = []
all_selections = []

# Absolute budgets
for budget in budgets_absolute:
    for method in all_methods:
        sids = select_anchors_by_method(method, budget, "absolute")
        result = evaluate_selection(sids, method, "absolute", budget)
        all_results.append(result)
        for sid in sids:
            all_selections.append({"method": method, "budget_type": "absolute", "budget_value": str(budget), "anchor_id": sid})

# Percent budgets
for pct in budgets_percent:
    for method in all_methods:
        sids = select_anchors_by_method(method, pct, "percent")
        result = evaluate_selection(sids, method, "percent", pct)
        all_results.append(result)
        for sid in sids:
            all_selections.append({"method": method, "budget_type": "percent", "budget_value": str(pct), "anchor_id": sid})

with open(f"{ROOT}/tables/method_budget_results.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=all_results[0].keys())
    w.writeheader(); w.writerows(all_results)

with open(f"{ROOT}/tables/method_selected_anchors.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=all_selections[0].keys())
    w.writeheader(); w.writerows(all_selections)

print(f"Stage 5: {len(all_results)} method×budget evaluations ({len(all_methods)} methods × {len(budgets_absolute)+len(budgets_percent)} budgets)")

# ═══════════════════════════════════════════════════════════
# STAGE 6: Fixed5 vs center10 comparison
# ═══════════════════════════════════════════════════════════
comparison = [
    {"method": "fixed_5s_nonoverlap", "coarse_unit": "5s", "full_scan_call_count": 798,
     "budgeted_call_count": 798, "estimated_call_reduction_vs_fixed5_fullscan": 0.0,
     "uses_proxy": "false", "uses_uniform_defense": "false", "requires_new_vlm": "false",
     "claim_scope": "V13.5 full oracle reference exists"},
    {"method": "center10_uniform_anchor", "coarse_unit": "10s", "full_scan_call_count": 399,
     "budgeted_call_count": 399, "estimated_call_reduction_vs_fixed5_fullscan": 0.50,
     "uses_proxy": "false", "uses_uniform_defense": "false", "requires_new_vlm": "false",
     "claim_scope": "NEEDS_FULL_ORACLE_REFERENCE"},
]
for b in budgets_absolute:
    comparison.append({"method": f"center10_top_fusion_yolo_motion_b{b}", "coarse_unit": "10s",
        "full_scan_call_count": 399, "budgeted_call_count": b,
        "estimated_call_reduction_vs_fixed5_fullscan": 1.0 - b/798,
        "uses_proxy": "true", "uses_uniform_defense": "false", "requires_new_vlm": "true",
        "claim_scope": "NEEDS_FULL_ORACLE_REFERENCE"})
    comparison.append({"method": f"center10_hybrid_70_30_b{b}", "coarse_unit": "10s",
        "full_scan_call_count": 399, "budgeted_call_count": b,
        "estimated_call_reduction_vs_fixed5_fullscan": 1.0 - b/798,
        "uses_proxy": "true", "uses_uniform_defense": "true", "requires_new_vlm": "true",
        "claim_scope": "NEEDS_FULL_ORACLE_REFERENCE"})

with open(f"{ROOT}/tables/fixed5_vs_center10_comparison.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=comparison[0].keys())
    w.writeheader(); w.writerows(comparison)

print(f"Stage 6: {len(comparison)} pipeline comparison rows")

# ═══════════════════════════════════════════════════════════
# Quick summary for Stages 5 results
# ═══════════════════════════════════════════════════════════
print("\n=== BEST METHODS BY BUDGET (labeled subset positive recall) ===")
for budget in budgets_absolute:
    budget_results = [r for r in all_results if r["budget_type"] == "absolute" and r["budget_value"] == str(budget)]
    best = max(budget_results, key=lambda r: r["positive_recall_on_labeled_subset"])
    uniform = [r for r in budget_results if r["method"] == "uniform_anchor_10s"][0]
    print(f"  B={budget:2d}: best={best['method']:35s} recall={best['positive_recall_on_labeled_subset']:.3f} "
          f"enrich={best['enrichment_vs_uniform']:.2f} "
          f"(uniform recall={uniform['positive_recall_on_labeled_subset']:.3f})")

print(f"\nLabeled subset: {len(eval_rows)} clips, {total_pos_in_subset} positive")
print(f"Best proxy method: max enrichment vs uniform = {max(r['enrichment_vs_uniform'] for r in all_results if r['method'] in proxy_methods):.2f}")
