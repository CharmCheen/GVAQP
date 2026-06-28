#!/usr/bin/env python3
"""V13.9 Latency-Aware AQP Simulation — requires V13.8 oracle to exist."""
import csv, json, os, sys, math, random, numpy as np
from collections import defaultdict, Counter

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1"
V13_8 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_8_center10_full_oracle_reference_v1"
V13_7 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_7_center10_multi_method_replay_v1"

ORACLE_LABELS = f"{V13_8}/tables/center10_full_oracle_labels.csv"
ORACLE_EVENTS = f"{V13_8}/tables/center10_vlm_oracle_events.csv"
PROXY_CSV = f"{V13_7}/tables/center10_proxy_features.csv"

for d in ["reports","tables","logs","scripts","figures"]:
    os.makedirs(f"{ROOT}/{d}", exist_ok=True)

# Verify inputs
if not os.path.exists(ORACLE_LABELS):
    print(f"ERROR: Oracle labels not found: {ORACLE_LABELS}")
    sys.exit(1)
if not os.path.exists(ORACLE_EVENTS):
    print(f"ERROR: Oracle events not found: {ORACLE_EVENTS}")
    sys.exit(1)

random.seed(42); np.random.seed(42)

# Load oracle
oracle_labels = list(csv.DictReader(open(ORACLE_LABELS)))
oracle_ok = [r for r in oracle_labels if r.get("parse_status","") in ("ok","parse_error") and r.get("label","") != ""]
print(f"Oracle labels: {len(oracle_ok)} ok / {len(oracle_labels)} total")

oracle_events = list(csv.DictReader(open(ORACLE_EVENTS)))
print(f"Oracle events: {len(oracle_events)}")

# Load proxy features
proxies = {}
with open(PROXY_CSV) as f:
    for row in csv.DictReader(f):
        proxies[row["anchor_id"]] = row
print(f"Proxy features: {len(proxies)} anchors")

# Build anchor index
anchor_list = sorted(proxies.keys())
n_total = len(anchor_list)

# Oracle event intervals
events = []
for e in oracle_events:
    events.append({
        "event_id": e["event_id"],
        "start": float(e["event_start"]),
        "end": float(e["event_end"]),
        "event_type": e.get("event_type_majority",""),
        "num_anchors": int(e.get("num_supporting_anchors",0)),
    })

# Anchor -> positive flag from oracle
anchor_pos = {}
for r in oracle_ok:
    anchor_pos[r["anchor_id"]] = (r["label"] == "positive")

total_pos_anchors = sum(1 for v in anchor_pos.values() if v)
total_events = len(events)
print(f"Positive anchors: {total_pos_anchors}/{len(anchor_pos)}")
print(f"Oracle events: {total_events}")

# Methods and scoring
METHODS = [
    "uniform_anchor_10s",
    "random_anchor_10s_seed1", "random_anchor_10s_seed2", "random_anchor_10s_seed3",
    "random_anchor_10s_seed4", "random_anchor_10s_seed5",
    "top_yolo_vehicle_mean", "top_yolo_vehicle_max",
    "top_bbox_area_sum_max", "top_center_roi_count",
    "top_motion_energy_max",
    "top_fusion_yolo_motion", "top_fusion_geometry_motion",
    "temporal_nms_yolo_vehicle_max_gap20", "temporal_nms_yolo_vehicle_max_gap30",
    "temporal_nms_yolo_vehicle_max_gap60", "temporal_nms_fusion_yolo_motion_gap30",
    "hybrid_70_proxy_30_uniform", "hybrid_50_proxy_50_uniform",
]

BUDGETS = [5, 10, 20, 40, 80]

def score_anchor(aid, method):
    p = proxies.get(aid, {})
    m = method
    if m == "uniform_anchor_10s": return 0
    if m.startswith("random"): return 0
    if m == "top_yolo_vehicle_max": return float(p.get("yolo_vehicle_max",0))
    if m == "top_yolo_vehicle_mean": return float(p.get("yolo_vehicle_mean",0))
    if m == "top_bbox_area_sum_max": return float(p.get("bbox_area_sum_max",0))
    if m == "top_center_roi_count": return float(p.get("center_roi_vehicle_count_mean",0))
    if m == "top_motion_energy_max": return float(p.get("motion_energy_max",0))
    if m == "top_fusion_yolo_motion": return float(p.get("score_fusion_yolo_motion",0))
    if m == "top_fusion_geometry_motion": return float(p.get("score_fusion_geometry_motion",0))
    if m.startswith("temporal_nms_"):
        base = m.replace("temporal_nms_","").rsplit("_gap",1)[0]
        return score_anchor(aid, base)
    if m.startswith("hybrid_"): return float(p.get("score_fusion_yolo_motion",0))
    return 0

def select_anchors(method, B):
    if method == "uniform_anchor_10s":
        step = n_total // B
        return [anchor_list[i] for i in range(0, n_total, step)][:B]

    if method.startswith("random_anchor"):
        seed = int(method.split("seed")[1]) if "seed" in method else 42
        rng = random.Random(seed)
        idx = list(range(n_total))
        rng.shuffle(idx)
        return [anchor_list[i] for i in idx[:B]]

    if method.startswith("temporal_nms_"):
        base = method.replace("temporal_nms_","").rsplit("_gap",1)[0]
        gap = float(method.rsplit("_gap",1)[1])
        sorted_aids = sorted(anchor_list, key=lambda a: score_anchor(a, base), reverse=True)
        pool = sorted_aids[:B*3]
        selected = []
        for aid in pool:
            at = float(proxies[aid]["anchor_time"])
            too_close = any(abs(at - float(proxies[s]["anchor_time"])) < gap for s in selected)
            if not too_close:
                selected.append(aid)
            if len(selected) >= B:
                break
        return selected[:B]

    if method.startswith("hybrid_"):
        parts = method.split("_")
        proxy_pct = int(parts[1]) / 100.0
        n_proxy = int(B * proxy_pct)
        n_uniform = B - n_proxy
        sorted_aids = sorted(anchor_list, key=lambda a: score_anchor(a, "top_fusion_yolo_motion"), reverse=True)
        proxy_picks = sorted_aids[:n_proxy]
        selected = list(proxy_picks)
        remaining = [a for a in anchor_list if a not in set(selected)]
        step = max(1, len(remaining) // n_uniform) if n_uniform > 0 else 1
        selected.extend([remaining[i] for i in range(0, len(remaining), step)][:n_uniform])
        return selected[:B]

    # Default: proxy ranking
    sorted_aids = sorted(anchor_list, key=lambda a: score_anchor(a, method), reverse=True)
    return sorted_aids[:B]

def compute_event_hits(selected_aids):
    """Count events hit by selected anchors."""
    hit_events = set()
    hit_iou03 = set()
    hit_iou05 = set()

    for aid in selected_aids:
        row = None
        for r in oracle_ok:
            if r["anchor_id"] == aid:
                row = r
                break
        if row is None:
            continue

        a_start = float(row["start_time"])
        a_end = float(row["end_time"])

        # Also use event_start_absolute if available
        ev_abs_start = row.get("event_start_absolute","")
        ev_abs_end = row.get("event_end_absolute","")
        if ev_abs_start and ev_abs_start != "" and ev_abs_end and ev_abs_end != "":
            try:
                a_start = float(ev_abs_start) - 1.0  # 1s margin
                a_end = float(ev_abs_end) + 1.0
            except:
                pass

        for ev in events:
            # Overlap check
            overlap = max(0, min(a_end, ev["end"]) - max(a_start, ev["start"]))
            if overlap > 0:
                hit_events.add(ev["event_id"])
                # IoU
                union = max(a_end, ev["end"]) - min(a_start, ev["start"])
                iou = overlap / union if union > 0 else 0
                if iou >= 0.3:
                    hit_iou03.add(ev["event_id"])
                if iou >= 0.5:
                    hit_iou05.add(ev["event_id"])

    return len(hit_events), len(hit_iou03), len(hit_iou05)

def evaluate(method, B):
    sids = select_anchors(method, B)
    pos_selected = sum(1 for a in sids if anchor_pos.get(a, False))
    precision = pos_selected / len(sids) if sids else 0
    recall = pos_selected / total_pos_anchors if total_pos_anchors else 0

    ev_hit, ev_iou03, ev_iou05 = compute_event_hits(sids)
    ev_recall = ev_hit / total_events if total_events else 0
    ev_recall_03 = ev_iou03 / total_events if total_events else 0
    ev_recall_05 = ev_iou05 / total_events if total_events else 0

    # Duration: use 10s per anchor
    coarse_dur = len(sids) * 10.0

    wall_time = len(sids) * 20.0  # ~20s per 32B call

    return {
        "method": method, "B32": str(B),
        "num_selected_anchors": len(sids),
        "positive_anchors_selected": pos_selected,
        "positive_anchor_precision": precision,
        "positive_anchor_recall": recall,
        "events_hit_overlap": ev_hit,
        "events_hit_iou_0p3": ev_iou03,
        "events_hit_iou_0p5": ev_iou05,
        "event_count_total": total_events,
        "event_recall_overlap": ev_recall,
        "event_recall_iou_0p3": ev_recall_03,
        "event_recall_iou_0p5": ev_recall_05,
        "returned_duration_coarse_seconds": coarse_dur,
        "returned_duration_fraction_coarse": coarse_dur / 3987.104,
        "estimated_wall_time_seconds": wall_time,
        "estimated_wall_time_minutes": wall_time / 60.0,
        "recall_per_32B_call": ev_recall / B if B else 0,
        "speedup_vs_full_center10_scan": 399.0 / B if B else float("inf"),
        "uses_proxy": "false" if method in ("uniform_anchor_10s") or method.startswith("random") else "true",
        "uses_uniform_defense": "true" if "hybrid" in method else "false",
        "claim_scope": "FULL_CENTER10_ORACLE_RELATIVE",
    }

# Run all evaluations
print(f"\nEvaluating {len(METHODS)} methods × {len(BUDGETS)} budgets...")
all_results = []
all_selections = []

for B in BUDGETS:
    for method in METHODS:
        result = evaluate(method, B)
        all_results.append(result)
        sids = select_anchors(method, B)
        for sid in sids:
            all_selections.append({"method": method, "B32": str(B), "anchor_id": sid, "is_positive": str(anchor_pos.get(sid, False))})

# Write results
res_fields = list(all_results[0].keys())
with open(f"{ROOT}/tables/method_budget_results.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=res_fields)
    w.writeheader(); w.writerows(all_results)

with open(f"{ROOT}/tables/method_selected_anchors.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=["method","B32","anchor_id","is_positive"])
    w.writeheader(); w.writerows(all_selections)

# Event hit trace
hit_trace = []
for B in [5,10,20,40]:
    for method in METHODS:
        sids = select_anchors(method, B)
        ev_hit, ev_iou03, ev_iou05 = compute_event_hits(sids)
        hit_trace.append({"method": method, "B32": str(B), "events_hit_overlap": str(ev_hit),
                          "events_hit_iou_0p3": str(ev_iou03), "events_hit_iou_0p5": str(ev_iou05),
                          "total_events": str(total_events)})

with open(f"{ROOT}/tables/event_hit_trace.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=hit_trace[0].keys())
    w.writeheader(); w.writerows(hit_trace)

# Random seed summary
rand_results = [r for r in all_results if r["method"].startswith("random_anchor")]
rand_by_budget = defaultdict(list)
for r in rand_results:
    rand_by_budget[r["B32"]].append(float(r["event_recall_overlap"]))

rand_summary = []
for B in sorted(rand_by_budget.keys(), key=int):
    vals = rand_by_budget[B]
    rand_summary.append({"B32": B, "random_mean_event_recall": np.mean(vals),
                         "random_std_event_recall": np.std(vals),
                         "random_min": min(vals), "random_max": max(vals)})

with open(f"{ROOT}/tables/random_seed_summary.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=rand_summary[0].keys())
    w.writeheader(); w.writerows(rand_summary)

# Best methods by budget
best_by_budget = []
for B in sorted(set(r["B32"] for r in all_results), key=int):
    br = [r for r in all_results if r["B32"] == B]
    best = max(br, key=lambda r: float(r["event_recall_overlap"]))
    rand_mean = rand_summary[[i for i,rs in enumerate(rand_summary) if rs["B32"]==B][0]]["random_mean_event_recall"]
    best_by_budget.append({**best, "random_mean_event_recall": rand_mean})

with open(f"{ROOT}/tables/best_methods_by_budget.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=best_by_budget[0].keys())
    w.writeheader(); w.writerows(best_by_budget)

# Print key results
print(f"\n=== RESULTS ===")
print(f"Oracle: {total_pos_anchors} positive anchors, {total_events} events")
for bb in best_by_budget:
    B = bb["B32"]
    rm = float(bb["random_mean_event_recall"])
    er = float(bb["event_recall_overlap"])
    delta = er - rm
    print(f"B={B:3s}: best={bb['method']:40s} event_recall={er:.3f} (random_mean={rm:.3f}, delta={delta:+.3f})")

# Decision
print(f"\n=== DECISION ===")
b20 = [r for r in all_results if r["B32"]=="20"]
b40 = [r for r in all_results if r["B32"]=="40"]
best20 = max(b20, key=lambda r: float(r["event_recall_overlap"]))
best40 = max(b40, key=lambda r: float(r["event_recall_overlap"]))
rand20 = rand_summary[[i for i,rs in enumerate(rand_summary) if rs["B32"]=="20"][0]]["random_mean_event_recall"]
rand40 = rand_summary[[i for i,rs in enumerate(rand_summary) if rs["B32"]=="40"][0]]["random_mean_event_recall"]

er20 = float(best20["event_recall_overlap"])
er40 = float(best40["event_recall_overlap"])
d20 = er20 - rand20
d40 = er40 - rand40

strong = (er20 >= 0.60 and d20 >= 0.15 and er40 >= 0.75)
pass_cond = ((er20 >= 0.45 and d20 >= 0.15) or er40 >= 0.60)
partial = (d20 >= 0.10 and not pass_cond)

if strong:
    decision = "LATENCY_AWARE_AQP_STRONG_PASS"
elif pass_cond:
    decision = "LATENCY_AWARE_AQP_PASS"
elif partial:
    decision = "LATENCY_AWARE_AQP_PARTIAL"
else:
    decision = "LATENCY_AWARE_AQP_FAIL"

print(f"Best B=20: {best20['method']} event_recall={er20:.3f} delta={d20:+.3f}")
print(f"Best B=40: {best40['method']} event_recall={er40:.3f} delta={d40:+.3f}")
print(f"STRONG: {strong} PASS: {pass_cond} PARTIAL: {partial}")
print(f"DECISION: {decision}")
