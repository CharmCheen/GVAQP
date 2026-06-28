#!/usr/bin/env python3
"""V13.10 — Oracle Upper Bound, Efficiency Audit, Adaptive Search Simulation.
Pure CPU analysis. No VLM, no GPU, no new data."""

import csv, json, os, sys, random, numpy as np
from collections import defaultdict, Counter

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_10"
V13_8 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_8_center10_full_oracle_reference_v1"
V13_7 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_7_center10_multi_method_replay_v1"
V13_9 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1"

os.makedirs(f"{ROOT}/tables", exist_ok=True)
os.makedirs(f"{ROOT}/reports", exist_ok=True)

# ═══════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════

# 1. Oracle labels (399 anchors)
oracle_labels = {}
with open(f"{V13_8}/tables/center10_full_oracle_labels.csv") as f:
    for row in csv.DictReader(f):
        oracle_labels[row["anchor_id"]] = row

# 2. Stitched events (51 events)
events = list(csv.DictReader(open(f"{V13_8}/tables/center10_vlm_oracle_events.csv")))
print(f"Loaded {len(events)} stitched events")

# Map anchor_id → stitched event_id (from supporting_anchor_ids)
anchor_to_events = defaultdict(set)
event_to_anchors = defaultdict(set)
for ev in events:
    eid = ev["event_id"]
    anchor_ids = ev["supporting_anchor_ids"].split("|")
    for aid in anchor_ids:
        anchor_to_events[aid].add(eid)
        event_to_anchors[eid].add(aid)

# 3. Proxy features (399 anchors)
proxies = {}
with open(f"{V13_7}/tables/center10_proxy_features.csv") as f:
    for row in csv.DictReader(f):
        proxies[row["anchor_id"]] = row

# 4. Anchor grid (temporal order)
anchors_ordered = []
with open(f"{V13_7}/tables/center10_anchor_grid.csv") as f:
    for row in csv.DictReader(f):
        anchors_ordered.append(row["anchor_id"])
n_total = len(anchors_ordered)
print(f"Loaded {n_total} anchors in temporal order")

# 5. V13.9 results (for cross-reference)
v13_9_results = list(csv.DictReader(open(f"{V13_9}/tables/method_budget_results.csv")))

# Build label arrays
anchor_labels = {}
positive_anchor_set = set()
for aid, row in oracle_labels.items():
    anchor_labels[aid] = row["label"]
    if row["label"] == "positive":
        positive_anchor_set.add(aid)

print(f"Positive anchors: {len(positive_anchor_set)}/{n_total}")

# ═══════════════════════════════════════════════════════════
# A-1: Anchor-to-event uniqueness check
# ═══════════════════════════════════════════════════════════
multi_event_anchors = []
for aid, ev_set in anchor_to_events.items():
    if len(ev_set) > 1:
        multi_event_anchors.append((aid, ev_set))

a1_simple = len(multi_event_anchors) == 0
print(f"\nA-1: Multi-event anchors: {len(multi_event_anchors)}")
if multi_event_anchors:
    for aid, ev_set in multi_event_anchors[:5]:
        print(f"  {aid}: events {ev_set}")
else:
    print("  Every positive anchor belongs to exactly one event → simple OracleBest formula applies")

# Build the event-covered-by-anchor matrix for budgeted max-coverage
# event_id -> set of anchor_ids that cover it
# anchor_id -> set of event_ids it covers
anchor_covers = {}
for aid in anchors_ordered:
    anchor_covers[aid] = anchor_to_events.get(aid, set())

# ═══════════════════════════════════════════════════════════
# A-2: OracleBest@B (budgeted maximum coverage)
# ═══════════════════════════════════════════════════════════

def oracle_best_at_budget(B, cover_map, all_events):
    """Greedy max-coverage (submodular, (1-1/e)-approximation)."""
    if B <= 0:
        return 0, set()
    remaining = set(cover_map.keys())
    covered = set()
    selected = []

    for _ in range(B):
        best_aid = None
        best_gain = 0
        for aid in remaining:
            gain = len(cover_map[aid] - covered)
            if gain > best_gain:
                best_gain = gain
                best_aid = aid
        if best_gain == 0:
            break
        selected.append(best_aid)
        covered.update(cover_map[best_aid])
        remaining.remove(best_aid)

    return len(covered), set(selected)

oracle_curve = []
all_event_ids = set(ev["event_id"] for ev in events)

# Use simple formula since A-1 confirms uniqueness
if a1_simple:
    for B in range(1, 52):
        recall = min(B, len(all_event_ids)) / len(all_event_ids)
        oracle_curve.append({"budget": str(B), "oracle_best_event_recall": f"{recall:.6f}"})
    print(f"\nA-2: Simple formula applied (every anchor→1 event)")
    # Verify with greedy to confirm
    greedy_at_51 = oracle_best_at_budget(51, anchor_covers, all_event_ids)
    print(f"  Greedy@51: {greedy_at_51[0]}/{len(all_event_ids)} events (should be {len(all_event_ids)})")
else:
    for B in range(1, 52):
        covered, _ = oracle_best_at_budget(B, anchor_covers, all_event_ids)
        oracle_curve.append({"budget": str(B), "oracle_best_event_recall": f"{covered / len(all_event_ids):.6f}"})

with open(f"{ROOT}/tables/oracle_upper_bound_v13_10.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["budget", "oracle_best_event_recall"])
    w.writeheader(); w.writerows(oracle_curve)

# Quick lookup for standard budgets
oracle_lookup = {int(r["budget"]): float(r["oracle_best_event_recall"]) for r in oracle_curve}
for B in [5,10,20,40,80]:
    print(f"  OracleBest@{B}: {oracle_lookup.get(B, oracle_lookup.get(51,1.0)):.4f}")

# ═══════════════════════════════════════════════════════════
# A-3: Re-derive static method selections
# ═══════════════════════════════════════════════════════════

# Proxy scoring functions (exact same as V13.9)
def score_anchor(aid, method):
    p = proxies.get(aid, {})
    m = method
    if m == "uniform_anchor_10s": return 0
    if m.startswith("random"): return 0
    if m == "top_yolo_vehicle_max": return float(p.get("yolo_vehicle_max", 0))
    if m == "top_yolo_vehicle_mean": return float(p.get("yolo_vehicle_mean", 0))
    if m == "top_bbox_area_sum_max": return float(p.get("bbox_area_sum_max", 0))
    if m == "top_center_roi_count": return float(p.get("center_roi_vehicle_count_mean", 0))
    if m == "top_motion_energy_max": return float(p.get("motion_energy_max", 0))
    if m == "top_fusion_yolo_motion": return float(p.get("score_fusion_yolo_motion", 0))
    if m == "top_fusion_geometry_motion": return float(p.get("score_fusion_geometry_motion", 0))
    if m.startswith("temporal_nms_"):
        base = m.replace("temporal_nms_", "").rsplit("_gap", 1)[0]
        return score_anchor(aid, base)
    if m.startswith("hybrid_"): return float(p.get("score_fusion_yolo_motion", 0))
    return 0

STATIC_METHODS = [
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

def select_anchors_static(method, B, seed=0):
    """Exact V13.9 selection logic."""
    if method == "uniform_anchor_10s":
        step = max(1, n_total // B)
        return [anchors_ordered[i] for i in range(0, n_total, step)][:B]

    if method.startswith("random_anchor"):
        rng = random.Random(seed)
        idx = list(range(n_total))
        rng.shuffle(idx)
        return [anchors_ordered[i] for i in idx[:B]]

    if method.startswith("temporal_nms_"):
        base = method.replace("temporal_nms_", "").rsplit("_gap", 1)[0]
        gap = float(method.rsplit("_gap", 1)[1])
        sorted_aids = sorted(anchors_ordered, key=lambda a: score_anchor(a, base), reverse=True)
        pool = sorted_aids[:B * 3]
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
        sorted_aids = sorted(anchors_ordered, key=lambda a: score_anchor(a, "top_fusion_yolo_motion"), reverse=True)
        selected = list(sorted_aids[:n_proxy])
        remaining = [a for a in anchors_ordered if a not in set(selected)]
        step = max(1, len(remaining) // n_uniform) if n_uniform > 0 else 1
        selected.extend([remaining[i] for i in range(0, len(remaining), step)][:n_uniform])
        return selected[:B]

    # Default: proxy ranking
    sorted_aids = sorted(anchors_ordered, key=lambda a: score_anchor(a, method), reverse=True)
    return sorted_aids[:B]

def compute_event_recall(selected_aids):
    """Count distinct events covered by selected anchors."""
    covered = set()
    for aid in selected_aids:
        covered.update(anchor_covers.get(aid, set()))
    return len(covered), covered

# Derive static results
print(f"\nA-3: Re-deriving static method selections...")
static_rows = []
v13_9_mismatches = []

for method in STATIC_METHODS:
    prev_events = set()

    for B in BUDGETS:
        if method.startswith("random_anchor"):
            # Average over 50 seeds — use per-seed MEAN, not union
            recalls = []
            for seed in range(50):
                sids = select_anchors_static(method, B, seed=seed)
                n_ev, cov = compute_event_recall(sids)
                recalls.append(n_ev)
            mean_recall = np.mean(recalls)
            std_recall = np.std(recalls)
            distinct_events = int(round(mean_recall))
            marginal = distinct_events - prev_distinct if B > BUDGETS[0] else ""
            prev_distinct = distinct_events
        elif method == "uniform_anchor_10s":
            sids = select_anchors_static(method, B)
            n_ev, cov = compute_event_recall(sids)
            distinct_events = n_ev
            marginal = distinct_events - len(prev_events) if B > BUDGETS[0] else ""
            prev_events = cov
        else:
            sids = select_anchors_static(method, B)
            n_ev, cov = compute_event_recall(sids)
            distinct_events = n_ev
            marginal = distinct_events - len(prev_events) if B > BUDGETS[0] else ""
            prev_events = cov

        event_recall = n_ev / len(all_event_ids) if method not in ("uniform_anchor_10s") or not method.startswith("random") else distinct_events / len(all_event_ids)
        # For deterministic methods, use n_ev; for random, use distinct_events
        if method.startswith("random_anchor") or method == "uniform_anchor_10s":
            event_recall = distinct_events / len(all_event_ids)
        else:
            event_recall = n_ev / len(all_event_ids)

        oracle_best = oracle_lookup.get(B, oracle_lookup.get(51, 1.0))
        eff = event_recall / oracle_best if oracle_best > 0 else 0

        static_rows.append({
            "method": method,
            "budget": str(B),
            "event_recall": f"{event_recall:.6f}",
            "oracle_best_event_recall": f"{oracle_best:.6f}",
            "efficiency_ratio": f"{eff:.4f}",
            "distinct_events_covered": str(distinct_events),
            "marginal_new_events": str(marginal) if marginal != "" else "",
        })

        # Cross-reference with V13.9 — compare event_recall_overlap (primary metric)
        v13_9_match = [r for r in v13_9_results if r["method"] == method and r["B32"] == str(B)]
        if v13_9_match:
            v13_9_ref = float(v13_9_match[0]["event_recall_overlap"])
            if abs(event_recall - v13_9_ref) > 0.015:
                v13_9_mismatches.append(f"MISMATCH: {method} B={B}: re-derived={event_recall:.4f} vs V13.9_overlap={v13_9_ref:.4f}")

with open(f"{ROOT}/tables/static_methods_efficiency_v13_10.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=static_rows[0].keys())
    w.writeheader(); w.writerows(static_rows)

print(f"  Static rows: {len(static_rows)}")
print(f"  Mismatches vs V13.9: {len(v13_9_mismatches)}")
for mm in v13_9_mismatches[:10]:
    print(f"    {mm}")

# ═══════════════════════════════════════════════════════════
# PART B: Adaptive Seed-and-Expand Simulation
# ═══════════════════════════════════════════════════════════
print(f"\n=== PART B: Adaptive Simulation ===")

def adaptive_priority_boost(base_score_fn, B, seed=0):
    """Priority boost adaptive algorithm."""
    n = n_total
    visited = [False] * n
    # Initialize priorities from base score
    if base_score_fn.__name__ == "base_uniform":
        priorities = [1.0 / (i + 1) for i in range(n)]  # just for tiebreaking
    elif base_score_fn.__name__ == "base_random":
        rng = random.Random(seed)
        priorities = [rng.random() for _ in range(n)]
    else:
        priorities = [base_score_fn(anchors_ordered[i]) for i in range(n)]

    boost_amount = max(priorities) - min(priorities) + 1.0 if max(priorities) != min(priorities) else 1.0

    selected = []
    events_found = set()

    for step in range(B):
        # Find best unvisited
        best_idx = max((i for i in range(n) if not visited[i]), key=lambda i: priorities[i], default=None)
        if best_idx is None:
            break

        aid = anchors_ordered[best_idx]
        visited[best_idx] = True
        selected.append(aid)
        events_found.update(anchor_covers.get(aid, set()))

        # If positive, boost neighbors
        if anchor_labels.get(aid) == "positive":
            for offset in range(1, 4):
                for nb in [best_idx - offset, best_idx + offset]:
                    if 0 <= nb < n and not visited[nb]:
                        priorities[nb] += boost_amount / offset

    return selected, len(events_found)


def adaptive_bidirectional_expand(base_score_fn, B, seed=0):
    """Bidirectional expansion adaptive algorithm."""
    n = n_total
    visited = [False] * n

    # Global queue sorted by base score
    if base_score_fn.__name__ == "base_uniform":
        global_order = list(range(n))
    elif base_score_fn.__name__ == "base_random":
        rng = random.Random(seed)
        idx = list(range(n))
        rng.shuffle(idx)
        global_order = idx
    else:
        scores = [(i, base_score_fn(anchors_ordered[i])) for i in range(n)]
        scores.sort(key=lambda x: x[1], reverse=True)
        global_order = [i for i, _ in scores]

    global_ptr = 0
    expansion_stack = []  # (index, direction) — direction: -1 or +1
    selected = []
    events_found = set()

    for step in range(B):
        if expansion_stack:
            # Pop from expansion stack
            idx, direction = expansion_stack.pop()
        else:
            # Take next from global queue
            while global_ptr < n and visited[global_order[global_ptr]]:
                global_ptr += 1
            if global_ptr >= n:
                break
            idx = global_order[global_ptr]
            global_ptr += 1
            direction = None  # starting point for expansion

        if visited[idx]:
            continue

        aid = anchors_ordered[idx]
        visited[idx] = True
        selected.append(aid)
        events_found.update(anchor_covers.get(aid, set()))

        if anchor_labels.get(aid) == "positive":
            # Push neighbors for expansion
            for offset in [1, -1]:
                nb = idx + offset
                if 0 <= nb < n and not visited[nb]:
                    expansion_stack.append((nb, offset))
                    # Continue expanding in same direction
                    nb2 = nb + offset
                    if 0 <= nb2 < n and not visited[nb2]:
                        expansion_stack.append((nb2, offset))

    return selected, len(events_found)


# Base scores
def base_uniform(aid):
    return 0.0

def base_yolo_vehicle_max(aid):
    return float(proxies.get(aid, {}).get("yolo_vehicle_max", 0))

def base_fusion_geometry_motion(aid):
    return float(proxies.get(aid, {}).get("score_fusion_geometry_motion", 0))

BASE_SCORES = [
    ("BASE_A_uniform", base_uniform, True),  # True = random variant
    ("BASE_B_yolo_vehicle_max", base_yolo_vehicle_max, False),
    ("BASE_C_fusion_geometry_motion", base_fusion_geometry_motion, False),
]

MECHANISMS = [
    ("adaptive_priority_boost", adaptive_priority_boost),
    ("adaptive_bidirectional_expand", adaptive_bidirectional_expand),
]

adaptive_rows = []

for base_name, base_fn, is_random in BASE_SCORES:
    for mech_name, mech_fn in MECHANISMS:
        print(f"  {base_name} + {mech_name}...")
        prev_events = set()

        for B in BUDGETS:
            if is_random:
                # Average over 50 seeds — per-seed mean
                recalls = []
                for seed in range(50):
                    _, n_ev = mech_fn(base_fn, B, seed=seed)
                    recalls.append(n_ev)
                mean_recall = np.mean(recalls)
                std_recall = np.std(recalls)
                distinct_events = int(round(mean_recall))
                # Use seed 0 for positive anchor count
                sids, _ = mech_fn(base_fn, B, seed=0)
                marginal = distinct_events - prev_distinct if B > BUDGETS[0] else ""
                prev_distinct = distinct_events

                oracle_best = oracle_lookup.get(B, oracle_lookup.get(51, 1.0))
                eff = (distinct_events / len(all_event_ids)) / oracle_best if oracle_best > 0 else 0

                adaptive_rows.append({
                    "method": f"{base_name}_{mech_name}",
                    "base_score": base_name,
                    "mechanism": mech_name,
                    "budget": str(B),
                    "event_recall": f"{distinct_events / len(all_event_ids):.6f}",
                    "event_recall_std": f"{std_recall:.6f}",
                    "oracle_best_event_recall": f"{oracle_best:.6f}",
                    "efficiency_ratio": f"{eff:.4f}",
                    "distinct_events_covered": str(distinct_events),
                    "marginal_new_events": str(marginal) if marginal != "" else "",
                    "anchors_visited": str(B),
                    "positive_anchors_found": str(sum(1 for aid in sids if anchor_labels.get(aid)=="positive")),
                })
            else:
                sids, n_ev = mech_fn(base_fn, B)
                cov = set()
                for aid in sids:
                    cov.update(anchor_covers.get(aid, set()))
                distinct_events = len(cov)
                marginal = distinct_events - len(prev_events) if B > BUDGETS[0] else ""
                prev_events = cov

                event_recall = distinct_events / len(all_event_ids)
                oracle_best = oracle_lookup.get(B, oracle_lookup.get(51, 1.0))
                eff = event_recall / oracle_best if oracle_best > 0 else 0

                adaptive_rows.append({
                    "method": f"{base_name}_{mech_name}",
                    "base_score": base_name,
                    "mechanism": mech_name,
                    "budget": str(B),
                    "event_recall": f"{event_recall:.6f}",
                    "event_recall_std": "",
                    "oracle_best_event_recall": f"{oracle_best:.6f}",
                    "efficiency_ratio": f"{eff:.4f}",
                    "distinct_events_covered": str(distinct_events),
                    "marginal_new_events": str(marginal) if marginal != "" else "",
                    "anchors_visited": str(B),
                    "positive_anchors_found": str(sum(1 for aid in sids if anchor_labels.get(aid)=="positive")),
                })

with open(f"{ROOT}/tables/adaptive_simulation_v13_10.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=adaptive_rows[0].keys())
    w.writeheader(); w.writerows(adaptive_rows)

print(f"  Adaptive rows: {len(adaptive_rows)}")

# ═══════════════════════════════════════════════════════════
# COMBINED TABLE
# ═══════════════════════════════════════════════════════════
combined_cols = ["method", "base_score", "mechanism", "budget", "event_recall",
                 "event_recall_std", "oracle_best_event_recall", "efficiency_ratio",
                 "distinct_events_covered", "marginal_new_events",
                 "anchors_visited", "positive_anchors_found"]

combined = []
for r in static_rows:
    cr = {k: "" for k in combined_cols}
    cr.update({"method": r["method"], "budget": r["budget"], "event_recall": r["event_recall"],
               "oracle_best_event_recall": r["oracle_best_event_recall"],
               "efficiency_ratio": r["efficiency_ratio"],
               "distinct_events_covered": r["distinct_events_covered"],
               "marginal_new_events": r["marginal_new_events"]})
    combined.append(cr)

for r in adaptive_rows:
    cr = {k: "" for k in combined_cols}
    cr.update(r)
    combined.append(cr)

with open(f"{ROOT}/tables/combined_comparison_v13_10.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=combined_cols)
    w.writeheader(); w.writerows(combined)

# ═══════════════════════════════════════════════════════════
# SUMMARY FOR REPORT
# ═══════════════════════════════════════════════════════════
print(f"\n=== KEY FINDINGS ===")

# Best static per budget
for B in BUDGETS:
    br = [r for r in static_rows if r["budget"] == str(B) and not r["method"].startswith("random")]
    best = max(br, key=lambda r: float(r["efficiency_ratio"]))
    print(f"B={B:3d}: best_static={best['method']:40s} eff={float(best['efficiency_ratio']):.4f} recall={float(best['event_recall']):.4f}")

# Best adaptive per budget
for B in BUDGETS:
    br = [r for r in adaptive_rows if r["budget"] == str(B)]
    best = max(br, key=lambda r: float(r["efficiency_ratio"]))
    print(f"B={B:3d}: best_adaptive={best['method']:45s} eff={float(best['efficiency_ratio']):.4f} recall={float(best['event_recall']):.4f}")

# Static vs adaptive delta
print(f"\n=== STATIC vs ADAPTIVE ===")
for B in BUDGETS:
    s_best = max([r for r in static_rows if r["budget"]==str(B) and not r["method"].startswith("random")],
                 key=lambda r: float(r["efficiency_ratio"]))
    a_best = max([r for r in adaptive_rows if r["budget"]==str(B)],
                 key=lambda r: float(r["efficiency_ratio"]))
    s_eff = float(s_best["efficiency_ratio"])
    a_eff = float(a_best["efficiency_ratio"])
    delta = a_eff - s_eff
    print(f"B={B:3d}: static_best_eff={s_eff:.4f} adaptive_best_eff={a_eff:.4f} delta={delta:+.4f} {'ADAPTIVE_WINS' if delta>0.01 else 'SAME_OR_STATIC_WINS'}")

# Stalled methods (marginal_new_events == 0)
stalled = [r for r in static_rows if r.get("marginal_new_events","") == "0"]
print(f"\nStalled rows (marginal_new_events==0): {len(stalled)}")
for s in stalled[:10]:
    print(f"  {s['method']:40s} B={s['budget']:3s} events={s['distinct_events_covered']}")

# Efficiency ratio assessment
effs_at_20 = [float(r["efficiency_ratio"]) for r in static_rows if r["budget"]=="20" and not r["method"].startswith("random")]
effs_at_40 = [float(r["efficiency_ratio"]) for r in static_rows if r["budget"]=="40" and not r["method"].startswith("random")]
print(f"\nMean static efficiency at B=20: {np.mean(effs_at_20):.4f}")
print(f"Mean static efficiency at B=40: {np.mean(effs_at_40):.4f}")
print(f"Best static efficiency at B=20: {max(effs_at_20):.4f}")
print(f"Best static efficiency at B=40: {max(effs_at_40):.4f}")

# Decision hints
best_s_eff = max(max(effs_at_20), max(effs_at_40))
if best_s_eff < 0.6:
    print("\nV13_10A_DECISION hint: STATIC_METHODS_FAR_BELOW_UPPER_BOUND (best eff < 0.6)")
else:
    print("\nV13_10A_DECISION hint: STATIC_METHODS_NEAR_UPPER_BOUND or MIXED")
