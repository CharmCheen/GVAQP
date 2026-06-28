#!/usr/bin/env python3
"""V13.10 Part B Sensitivity — same-base comparison + window-width sweep + boost waste rate."""
import csv, random, numpy as np, sys
from collections import defaultdict

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_10"
V13_8 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_8_center10_full_oracle_reference_v1"
V13_7 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_7_center10_multi_method_replay_v1"

# ── Load data ──
oracle_labels = {}
with open(f"{V13_8}/tables/center10_full_oracle_labels.csv") as f:
    for row in csv.DictReader(f): oracle_labels[row["anchor_id"]] = row

proxies = {}
with open(f"{V13_7}/tables/center10_proxy_features.csv") as f:
    for row in csv.DictReader(f): proxies[row["anchor_id"]] = row

events = list(csv.DictReader(open(f"{V13_8}/tables/center10_vlm_oracle_events.csv")))
anchor_to_events = {}
for ev in events:
    for aid in ev["supporting_anchor_ids"].split("|"):
        anchor_to_events.setdefault(aid, set()).add(ev["event_id"])

anchors_ordered = sorted(proxies.keys())
n_total = len(anchors_ordered)
all_event_ids = set(ev["event_id"] for ev in events)
oracle_lookup = {B: min(B, 51) / 51 for B in range(1, 100)}

# ── Base scores ──
def base_uniform(aid): return 0.0
def base_yolo(aid): return float(proxies.get(aid, {}).get("yolo_vehicle_max", 0))
def base_fusion(aid): return float(proxies.get(aid, {}).get("score_fusion_geometry_motion", 0))

BASE_CONFIGS = [
    ("BASE_A_uniform", base_uniform, True),
    ("BASE_B_yolo_vehicle_max", base_yolo, False),
    ("BASE_C_fusion_geometry_motion", base_fusion, False),
]

def base_score_name_to_static_method(name):
    """Map base score name to corresponding static method."""
    mapping = {
        "BASE_A_uniform": "uniform_anchor_10s",
        "BASE_B_yolo_vehicle_max": "top_yolo_vehicle_max",
        "BASE_C_fusion_geometry_motion": "top_fusion_geometry_motion",
    }
    return mapping.get(name, name)

BUDGETS = [5, 10, 20, 40, 80]

# ── Load static results for same-base comparison ──
static_rows = list(csv.DictReader(open(f"{ROOT}/tables/static_methods_efficiency_v13_10.csv")))

def static_eff_for_method(method, B):
    for r in static_rows:
        if r["method"] == method and r["budget"] == str(B):
            return float(r["efficiency_ratio"])
    return 0.0

# ── Adaptive algorithms with configurable window ──
def adaptive_priority_boost(base_fn, B, window=3, seed=0):
    n = n_total
    visited = [False] * n
    base_scores = [base_fn(anchors_ordered[i]) for i in range(n)]
    priorities = list(base_scores)
    boost_amount = max(priorities) - min(priorities) + 1.0 if max(priorities) != min(priorities) else 1.0

    selected = []
    events_found = set()
    stats = {"from_global": 0, "from_boost": 0, "boost_pos": 0, "boost_neg": 0}

    for step in range(B):
        best_idx = max((i for i in range(n) if not visited[i]), key=lambda i: priorities[i], default=None)
        if best_idx is None: break

        from_boost = False
        # Check if this anchor would have been selected by original ranking (unboosted)
        # An anchor got boosted if its priority > base_score + some epsilon
        if abs(priorities[best_idx] - base_scores[best_idx]) > 0.01 * boost_amount:
            from_boost = True

        aid = anchors_ordered[best_idx]
        visited[best_idx] = True
        selected.append(aid)
        events_found.update(anchor_to_events.get(aid, set()))

        if from_boost:
            stats["from_boost"] += 1
            if oracle_labels.get(aid, {}).get("label") == "positive":
                stats["boost_pos"] += 1
            else:
                stats["boost_neg"] += 1
        else:
            stats["from_global"] += 1

        if oracle_labels.get(aid, {}).get("label") == "positive":
            for offset in range(1, window + 1):
                for nb in [best_idx - offset, best_idx + offset]:
                    if 0 <= nb < n and not visited[nb]:
                        priorities[nb] += boost_amount / offset

    return selected, len(events_found), stats


def adaptive_bidirectional_expand(base_fn, B, window=3, seed=0):
    n = n_total
    visited = [False] * n
    if base_fn.__name__ == "base_uniform":
        global_order = list(range(n))
    else:
        scores = [(i, base_fn(anchors_ordered[i])) for i in range(n)]
        scores.sort(key=lambda x: x[1], reverse=True)
        global_order = [i for i, _ in scores]

    global_ptr = 0
    expansion_stack = []
    selected = []
    events_found = set()
    stats = {"from_global": 0, "from_expansion_stack": 0, "expansion_pos": 0, "expansion_neg": 0}

    for step in range(B):
        from_expansion = False
        if expansion_stack:
            idx, direction = expansion_stack.pop()
            from_expansion = True
        else:
            while global_ptr < n and visited[global_order[global_ptr]]:
                global_ptr += 1
            if global_ptr >= n: break
            idx = global_order[global_ptr]
            global_ptr += 1

        if visited[idx]: continue
        aid = anchors_ordered[idx]
        visited[idx] = True
        selected.append(aid)
        events_found.update(anchor_to_events.get(aid, set()))

        if from_expansion:
            stats["from_expansion_stack"] += 1
            if oracle_labels.get(aid, {}).get("label") == "positive":
                stats["expansion_pos"] += 1
            else:
                stats["expansion_neg"] += 1
        else:
            stats["from_global"] += 1

        if oracle_labels.get(aid, {}).get("label") == "positive":
            for offset in [1, -1]:
                nb = idx + offset
                if 0 <= nb < n and not visited[nb]:
                    expansion_stack.append((nb, offset))
                    # Continue expanding in same direction up to window
                    for w in range(2, window + 1):
                        nb2 = idx + offset * w
                        if 0 <= nb2 < n and not visited[nb2]:
                            expansion_stack.append((nb2, offset))

    return selected, len(events_found), stats


def eff_at_B(events_found, B):
    oracle_best = oracle_lookup.get(B, oracle_lookup.get(51, 1.0))
    recall = events_found / len(all_event_ids)
    return recall / oracle_best if oracle_best > 0 else 0.0


# ═══════════════════════════════════════════════════════════
# TASK 1: Same-base comparison (window=3, existing default)
# ═══════════════════════════════════════════════════════════
WINDOW_DEFAULT = 3
print("=" * 70)
print("TASK 1: Same-Base Comparison")
print("=" * 70)

same_base_rows = []

for base_name, base_fn, is_random in BASE_CONFIGS:
    static_method = base_score_name_to_static_method(base_name)
    print(f"\n{base_name} (static={static_method}):")
    print(f"  {'Budget':<6} {'static_alone':>12} {'prio_boost':>12} {'bidir_expand':>12} {'prio_vs_static':>14} {'bidir_vs_static':>14}")

    for B in BUDGETS:
        static_eff = static_eff_for_method(static_method, B)

        # Priority boost
        if is_random:
            recalls_pb = []
            for seed in range(50):
                _, n_ev, _ = adaptive_priority_boost(base_fn, B, WINDOW_DEFAULT, seed=seed)
                recalls_pb.append(n_ev)
            pb_eff = eff_at_B(np.mean(recalls_pb), B)
        else:
            _, n_ev, _ = adaptive_priority_boost(base_fn, B, WINDOW_DEFAULT)
            pb_eff = eff_at_B(n_ev, B)

        # Bidirectional expand
        if is_random:
            recalls_be = []
            for seed in range(50):
                _, n_ev, _ = adaptive_bidirectional_expand(base_fn, B, WINDOW_DEFAULT, seed=seed)
                recalls_be.append(n_ev)
            be_eff = eff_at_B(np.mean(recalls_be), B)
        else:
            _, n_ev, _ = adaptive_bidirectional_expand(base_fn, B, WINDOW_DEFAULT)
            be_eff = eff_at_B(n_ev, B)

        pb_delta = pb_eff - static_eff
        be_delta = be_eff - static_eff

        same_base_rows.append({
            "base_score": base_name, "static_method": static_method, "budget": str(B),
            "static_eff": f"{static_eff:.4f}", "prio_boost_eff": f"{pb_eff:.4f}",
            "bidir_expand_eff": f"{be_eff:.4f}", "prio_vs_static": f"{pb_delta:+.4f}",
            "bidir_vs_static": f"{be_delta:+.4f}",
        })

        best_adapt = max(pb_eff, be_eff)
        verdict = "HELPS" if best_adapt > static_eff + 0.01 else ("HURTS" if best_adapt < static_eff - 0.01 else "SAME")
        print(f"  {B:<6} {static_eff:>12.4f} {pb_eff:>12.4f} {be_eff:>12.4f} {pb_delta:>+14.4f} {be_delta:>+14.4f}  {verdict}")

# Print per-base summary
print(f"\n  Per-base summary:")
for base_name, _, _ in BASE_CONFIGS:
    sbr = [r for r in same_base_rows if r['base_score'] == base_name]
    pb_deltas = [float(r['prio_vs_static']) for r in sbr]
    be_deltas = [float(r['bidir_vs_static']) for r in sbr]
    pb_mean = np.mean(pb_deltas)
    be_mean = np.mean(be_deltas)
    pb_best = max(pb_deltas)
    print(f"    {base_name}: prio_boost mean_delta={pb_mean:+.3f} best={pb_best:+.3f}  "
          f"bidir_expand mean_delta={be_mean:+.3f} best={max(be_deltas):+.3f}")

# ═══════════════════════════════════════════════════════════
# TASK 2: Window-width sensitivity
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TASK 2: Window-Width Sensitivity")
print("=" * 70)

WINDOWS = [1, 2, 3]
window_rows = []

for base_name, base_fn, is_random in BASE_CONFIGS:
    for B in BUDGETS:
        print(f"\n{base_name} B={B}:")
        print(f"  {'window':<8} {'prio_eff':>10} {'prio_waste':>10} {'bidir_eff':>10} {'bidir_waste':>10}")
        for w in WINDOWS:
            # Priority boost
            if is_random:
                pb_recalls, pb_boost_pos, pb_boost_neg = [], [], []
                for seed in range(50):
                    _, n_ev, st = adaptive_priority_boost(base_fn, B, w, seed=seed)
                    pb_recalls.append(n_ev)
                    pb_boost_pos.append(st["boost_pos"])
                    pb_boost_neg.append(st["boost_neg"])
                pb_eff = eff_at_B(np.mean(pb_recalls), B)
                pb_waste = np.mean(pb_boost_neg) / (np.mean(pb_boost_pos) + np.mean(pb_boost_neg)) if (np.mean(pb_boost_pos) + np.mean(pb_boost_neg)) > 0 else 0
            else:
                _, n_ev, st = adaptive_priority_boost(base_fn, B, w)
                pb_eff = eff_at_B(n_ev, B)
                pb_waste = st["boost_neg"] / (st["boost_pos"] + st["boost_neg"]) if (st["boost_pos"] + st["boost_neg"]) > 0 else 0

            # Bidirectional expand
            if is_random:
                be_recalls, be_exp_pos, be_exp_neg = [], [], []
                for seed in range(50):
                    _, n_ev, st = adaptive_bidirectional_expand(base_fn, B, w, seed=seed)
                    be_recalls.append(n_ev)
                    be_exp_pos.append(st["expansion_pos"])
                    be_exp_neg.append(st["expansion_neg"])
                be_eff = eff_at_B(np.mean(be_recalls), B)
                be_waste = np.mean(be_exp_neg) / (np.mean(be_exp_pos) + np.mean(be_exp_neg)) if (np.mean(be_exp_pos) + np.mean(be_exp_neg)) > 0 else 0
            else:
                _, n_ev, st = adaptive_bidirectional_expand(base_fn, B, w)
                be_eff = eff_at_B(n_ev, B)
                be_waste = st["expansion_neg"] / (st["expansion_pos"] + st["expansion_neg"]) if (st["expansion_pos"] + st["expansion_neg"]) > 0 else 0

            window_rows.append({
                "base_score": base_name, "budget": str(B), "window": str(w),
                "prio_boost_eff": f"{pb_eff:.4f}", "prio_boost_waste_rate": f"{pb_waste:.3f}",
                "bidir_expand_eff": f"{be_eff:.4f}", "bidir_expand_waste_rate": f"{be_waste:.3f}",
            })
            print(f"  {w:<8} {pb_eff:>10.4f} {pb_waste:>10.3f} {be_eff:>10.4f} {be_waste:>10.3f}")

#  ═══════════════════════════════════════════════════════════
# TASK 3: Boost-mechanism waste rate (already captured in T2)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TASK 3: Boost Mechanism Waste Rate Summary")
print("=" * 70)

# Group by base and window to see pattern
print(f"\n  {'Base':<35s} {'Window':<8s} {'Priowaste_5':>11s} {'Priowaste_20':>11s} {'Priowaste_80':>11s}")
for base_name, _, _ in BASE_CONFIGS:
    for w in WINDOWS:
        wr = [r for r in window_rows if r['base_score'] == base_name and r['window'] == str(w)]
        w5 = next((float(r['prio_boost_waste_rate']) for r in wr if r['budget'] == '5'), 0)
        w20 = next((float(r['prio_boost_waste_rate']) for r in wr if r['budget'] == '20'), 0)
        w80 = next((float(r['prio_boost_waste_rate']) for r in wr if r['budget'] == '80'), 0)
        print(f"  {str(base_name):<35s} {str(w):<8s} {w5:>11.3f} {w20:>11.3f} {w80:>11.3f}")

# Save tables
def save_csv(name, rows):
    with open(f"{ROOT}/tables/{name}", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

save_csv("same_base_comparison_v13_10.csv", same_base_rows)
save_csv("window_sensitivity_v13_10.csv", window_rows)

# Decision
print("\n" + "=" * 70)
print("DECISION")
print("=" * 70)

# Check if window=1 or window=2 ever beats window=3
pb_improvements = 0
for br in window_rows:
    w = int(br['window'])
    if w < 3:
        w3_row = [r for r in window_rows if r['base_score'] == br['base_score'] and r['budget'] == br['budget'] and r['window'] == '3']
        if w3_row:
            w3_pb = float(w3_row[0]['prio_boost_eff'])
            if float(br['prio_boost_eff']) > w3_pb + 0.005:
                pb_improvements += 1

samebase_hurts = sum(1 for r in same_base_rows if float(r['prio_vs_static']) < -0.01 and float(r['bidir_vs_static']) < -0.01)
samebase_total = len(same_base_rows)

if pb_improvements >= 3:
    decision = "WINDOW_TUNING_HELPS"
elif samebase_hurts > samebase_total * 0.7:
    decision = "SAME_BASE_HURTS_CONSISTENTLY"
else:
    decision = "WINDOW_TUNING_NO_HELP"

print(f"  Window improvements (narrower beats w=3): {pb_improvements}")
print(f"  Same-base both-hurt count: {samebase_hurts}/{samebase_total}")
print(f"  ADAPTIVE_SENSITIVITY_DECISION: {decision}")
print(f"\n  ADAPTIVE_SIMULATION_DECISION unchanged: ADAPTIVE_NO_BETTER")
