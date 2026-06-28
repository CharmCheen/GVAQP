#!/usr/bin/env python3
"""Stages 3-5: Proxy-Oracle Analysis, AQP Structure Analysis, Budget Replay.

No new VLM calls. Uses the full center10 oracle reference + proxy features.
VLM_ORACLE_RELATIVE labels. Oracle-relative replay.
"""
import csv, json, os, sys, math, random
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

OUT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1"
ORACLE_CSV = f"{OUT}/oracle_outputs/dataset3_full_center10_parsed.csv"
PROXY_CSV = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/metadata/center10_proxy_features.csv"
BUDGETS = [10, 20, 30, 40, 60, 80, 100, 150]
N_RANDOM_REPEATS = 200

# Load data
oracle_rows = list(csv.DictReader(open(ORACLE_CSV)))
proxy_rows = {r["anchor_id"]: r for r in csv.DictReader(open(PROXY_CSV))}
print(f"Loaded {len(oracle_rows)} oracle rows, {len(proxy_rows)} proxy rows")

# Merge oracle + proxy
merged = []
for o in oracle_rows:
    aid = o["anchor_id"]
    p = proxy_rows.get(aid, {})
    m = dict(o)
    m["score_fusion"] = float(p.get("score_fusion_geometry_motion", "0") or "0")
    m["score_yolo"] = float(p.get("score_fusion_yolo_motion", "0") or "0")
    m["score_ego"] = float(p.get("score_fusion_ego_lateral", "0") or "0")
    m["object_count_mean"] = float(p.get("object_count_mean", "0") or "0")
    m["near_ego_count_max"] = float(p.get("near_ego_vehicle_count_max", "0") or "0")
    m["motion_energy_mean"] = float(p.get("motion_energy_mean", "0") or "0")
    m["person_count_max"] = int(float(p.get("person_count_max", "0") or "0"))
    m["bicycle_count_mean"] = float(p.get("bicycle_count_mean", "0") or "0")
    m["motorcycle_count_mean"] = float(p.get("motorcycle_count_mean", "0") or "0")
    m["bbox_cx_std_max"] = float(p.get("bbox_cx_std_max", "0") or "0")
    m["anchor_idx"] = int(aid.split("_")[-1])
    m["anchor_time_float"] = float(o["anchor_time"])
    merged.append(m)

pos = [m for m in merged if m["label"] == "positive"]
neg = [m for m in merged if m["label"] == "negative"]
n_pos = len(pos)
n_total = len(merged)
print(f"Positives: {n_pos}/{n_total} = {n_pos/n_total*100:.1f}%")

# ====================== STAGE 3: Proxy-Oracle Analysis ======================
print("\n" + "="*60)
print("STAGE 3: Proxy-Oracle Relationship Analysis")
print("="*60)

# 3.1 AUROC / AUPRC for each proxy score
def auroc(scores, labels):
    """Compute AUROC. labels: 1 for positive, 0 for negative."""
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0: return 0.5
    pairs = sorted(zip(scores, labels), key=lambda x: -x[0])
    tp = 0
    fp = 0
    auroc_val = 0
    prev_score = None
    for s, l in pairs:
        if prev_score is not None and s != prev_score:
            auroc_val += tp * fp - tp * (fp - 1) / 2  # trapezoidal
        if l == 1: tp += 1
        else: fp += 1
        prev_score = s
    auroc_val += tp * fp - tp * (fp - 1) / 2
    return auroc_val / (n_pos * n_neg)

def auprc(scores, labels):
    """Compute AUPRC (average precision)."""
    pairs = sorted(zip(scores, labels), key=lambda x: -x[0])
    tp = 0
    fp = 0
    ap = 0
    for s, l in pairs:
        if l == 1: tp += 1
        else: fp += 1
        precision = tp / (tp + fp)
        recall = tp / max(1, sum(labels))
        ap += precision * (1 if l == 1 else 0)
    return ap / max(1, sum(labels))

labels_bin = [1 if m["label"] == "positive" else 0 for m in merged]
proxy_aucs = {}
for score_name in ["score_fusion", "score_yolo", "score_ego", "object_count_mean", "motion_energy_mean", "near_ego_count_max"]:
    scores = [m[score_name] for m in merged]
    auc = auroc(scores, labels_bin)
    ap = auprc(scores, labels_bin)
    proxy_aucs[score_name] = {"auroc": auc, "auprc": ap}
    print(f"  {score_name}: AUROC={auc:.3f}, AUPRC={ap:.3f}")

# 3.2 Proxy quartile positive rate
print("\n  Proxy quartile positive rate:")
scores_sorted = sorted(merged, key=lambda m: m["score_fusion"])
q_size = len(scores_sorted) // 4
quartile_rates = []
for qi in range(4):
    q_start = qi * q_size
    q_end = (qi + 1) * q_size if qi < 3 else len(scores_sorted)
    q_rows = scores_sorted[q_start:q_end]
    q_pos = sum(1 for m in q_rows if m["label"] == "positive")
    q_rate = q_pos / len(q_rows)
    quartile_rates.append({"quartile": qi+1, "n": len(q_rows), "positives": q_pos, "rate": q_rate})
    print(f"    Q{qi+1}: {q_pos}/{len(q_rows)} = {q_rate*100:.1f}%")

# 3.3 Top-k positive yield vs random
print("\n  Top-k positive yield vs random baseline:")
topk_results = []
for k in BUDGETS:
    # Top proxy
    top_proxy = sorted(merged, key=lambda m: -m["score_fusion"])[:k]
    tp_proxy = sum(1 for m in top_proxy if m["label"] == "positive")
    # Random baseline (200 repeats)
    random_yields = []
    for _ in range(N_RANDOM_REPEATS):
        sample = random.sample(merged, min(k, len(merged)))
        random_yields.append(sum(1 for m in sample if m["label"] == "positive"))
    rand_mean = np.mean(random_yields)
    rand_std = np.std(random_yields)
    rand_ci95 = 1.96 * rand_std / math.sqrt(N_RANDOM_REPEATS)
    topk_results.append({
        "budget": k, "top_proxy_positives": tp_proxy,
        "random_mean": f"{rand_mean:.2f}", "random_std": f"{rand_std:.2f}",
        "random_ci95": f"{rand_ci95:.2f}",
        "top_proxy_recall": f"{tp_proxy/n_pos:.3f}",
        "random_recall": f"{rand_mean/n_pos:.3f}",
    })
    print(f"    B={k}: top_proxy={tp_proxy} (recall={tp_proxy/n_pos:.3f}), random={rand_mean:.1f}±{rand_std:.1f} (recall={rand_mean/n_pos:.3f})")

# 3.4 High-score negatives (false alarms)
high_score_neg = [m for m in neg if m["score_fusion"] > np.percentile([m["score_fusion"] for m in merged], 75)]
print(f"\n  High-score negatives (top quartile score, negative label): {len(high_score_neg)}")
high_score_neg_reasons = Counter(m["negative_reason"] for m in high_score_neg)
print(f"    Reasons: {dict(high_score_neg_reasons)}")

# 3.5 Low-score positives (missed by proxy)
low_score_pos = [m for m in pos if m["score_fusion"] < np.median([m["score_fusion"] for m in merged])]
print(f"  Low-score positives (below median score, positive label): {len(low_score_pos)}")
for m in low_score_pos[:5]:
    print(f"    {m['anchor_id']} score={m['score_fusion']:.3f} obj={m['involved_object']}")

# Save proxy-oracle analysis
proxy_analysis = []
for m in merged:
    proxy_analysis.append({
        "anchor_id": m["anchor_id"], "anchor_time": m["anchor_time"],
        "label": m["label"], "involved_object": m["involved_object"],
        "score_fusion": f"{m['score_fusion']:.4f}", "score_yolo": f"{m['score_yolo']:.3f}",
        "object_count_mean": f"{m['object_count_mean']:.2f}",
        "near_ego_count_max": f"{m['near_ego_count_max']:.0f}",
        "negative_reason": m["negative_reason"],
        "is_high_score_neg": m["score_fusion"] > np.percentile([x["score_fusion"] for x in merged], 75) and m["label"] == "negative",
        "is_low_score_pos": m["score_fusion"] < np.median([x["score_fusion"] for x in merged]) and m["label"] == "positive",
    })
with open(f"{OUT}/analysis/proxy_oracle_relation.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(proxy_analysis[0].keys()))
    w.writeheader(); w.writerows(proxy_analysis)

# ====================== STAGE 4: AQP Structure Analysis ======================
print("\n" + "="*60)
print("STAGE 4: Full-Reference AQP Structure Analysis")
print("="*60)

# 4.1 Selectivity
print("\n  4.1 Selectivity:")
time_blocks = defaultdict(list)
for m in merged:
    block = int(m["anchor_time_float"] // 300)  # 5-min blocks
    time_blocks[block].append(m)
block_rates = []
for block in sorted(time_blocks.keys()):
    rows = time_blocks[block]
    b_pos = sum(1 for m in rows if m["label"] == "positive")
    b_rate = b_pos / len(rows)
    block_rates.append({"block": block, "time_range": f"{block*300}-{(block+1)*300}s", "n": len(rows), "positives": b_pos, "rate": f"{b_rate:.3f}"})
    if b_pos > 0:
        print(f"    Block {block*300}-{(block+1)*300}s: {b_pos}/{len(rows)} = {b_rate*100:.1f}%")

# 4.2 Temporal correlation
print("\n  4.2 Temporal Correlation:")
# Adjacent anchor label correlation
sorted_anchors = sorted(merged, key=lambda m: m["anchor_idx"])
transitions = Counter()
for i in range(len(sorted_anchors) - 1):
    l1 = sorted_anchors[i]["label"]
    l2 = sorted_anchors[i+1]["label"]
    transitions[(l1, l2)] += 1
total_trans = sum(transitions.values())
p1_to_1 = transitions[("positive", "positive")]
p1_to_0 = transitions[("positive", "negative")]
p0_to_1 = transitions[("negative", "positive")]
p0_to_0 = transitions[("negative", "negative")]
base_rate = n_pos / n_total
p_stay = p1_to_1 / max(1, p1_to_1 + p1_to_0)
print(f"    P(1→1) = {p_stay:.3f} (base rate = {base_rate:.3f})")
print(f"    Transitions: 1→1={p1_to_1}, 1→0={p1_to_0}, 0→1={p0_to_1}, 0→0={p0_to_0}")

# 4.3 Positive clusters
print("\n  4.3 Positive Clusters:")
clusters = []
current_cluster = []
for m in sorted_anchors:
    if m["label"] == "positive":
        if current_cluster and m["anchor_idx"] - current_cluster[-1]["anchor_idx"] > 1:
            clusters.append(current_cluster)
            current_cluster = []
        current_cluster.append(m)
    elif current_cluster:
        clusters.append(current_cluster)
        current_cluster = []
if current_cluster:
    clusters.append(current_cluster)

print(f"    Total clusters: {len(clusters)}")
cluster_data = []
for i, cl in enumerate(clusters):
    duration = (cl[-1]["anchor_time_float"] + 5) - cl[0]["anchor_time_float"]
    objects = Counter(m["involved_object"] for m in cl)
    cluster_data.append({
        "cluster_id": i, "start_anchor": cl[0]["anchor_id"],
        "start_time": f"{cl[0]['anchor_time_float']:.0f}",
        "n_anchors": len(cl), "duration_s": f"{duration:.0f}",
        "objects": dict(objects),
        "anchor_ids": ",".join(m["anchor_id"].split("_")[-1] for m in cl),
    })
    print(f"    Cluster {i}: {cl[0]['anchor_id']} to {cl[-1]['anchor_id']}, {len(cl)} anchors, {duration:.0f}s, objects={dict(objects)}")

# 4.4 Hard negatives
print("\n  4.4 Hard Negatives:")
hard_neg_categories = {
    "high_score_normal_following": [m for m in neg if m["score_fusion"] > 0 and m["negative_reason"] == "normal_following"],
    "high_score_no_interaction": [m for m in neg if m["score_fusion"] > 0 and m["negative_reason"] == "no_ego_path_interaction"],
    "dense_traffic": [m for m in neg if m["object_count_mean"] > np.median([x["object_count_mean"] for x in merged]) and m["negative_reason"] == "normal_following"],
}
for cat, items in hard_neg_categories.items():
    print(f"    {cat}: {len(items)}")

# Save structure analysis
with open(f"{OUT}/analysis/selectivity_analysis.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["block", "time_range", "n", "positives", "rate"])
    w.writeheader(); w.writerows(block_rates)

with open(f"{OUT}/analysis/temporal_structure.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["metric", "value"])
    w.writeheader()
    w.writerow({"metric": "P(1->1)", "value": f"{p_stay:.4f}"})
    w.writerow({"metric": "base_rate", "value": f"{base_rate:.4f}"})
    w.writerow({"metric": "n_clusters", "value": str(len(clusters))})
    w.writerow({"metric": "n_singletons", "value": str(sum(1 for c in clusters if len(c) == 1))})
    w.writerow({"metric": "n_multi_anchor_clusters", "value": str(sum(1 for c in clusters if len(c) > 1))})
    w.writerow({"metric": "largest_cluster_size", "value": str(max(len(c) for c in clusters))})
    w.writerow({"metric": "mean_cluster_size", "value": f"{np.mean([len(c) for c in clusters]):.2f}"})

with open(f"{OUT}/analysis/positive_clusters.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["cluster_id", "start_anchor", "start_time", "n_anchors", "duration_s", "objects", "anchor_ids"])
    w.writeheader(); w.writerows(cluster_data)

# ====================== STAGE 5: Budget Replay ======================
print("\n" + "="*60)
print("STAGE 5: No-New-VLM Budget Replay")
print("="*60)

# Event clusters for event-level recall
event_cluster_set = set()
for i, cl in enumerate(clusters):
    for m in cl:
        event_cluster_set.add((i, m["anchor_id"]))

anchor_to_cluster = {}
for i, cl in enumerate(clusters):
    for m in cl:
        anchor_to_cluster[m["anchor_id"]] = i

def evaluate_selection(selected, all_rows, n_pos, clusters, anchor_to_cluster):
    """Evaluate a selection of anchors."""
    selected_ids = set(s["anchor_id"] for s in selected)
    tp = sum(1 for s in selected if s["label"] == "positive")
    precision = tp / max(1, len(selected))
    anchor_recall = tp / max(1, n_pos)
    # Event-cluster recall
    hit_clusters = set()
    for s in selected:
        cid = anchor_to_cluster.get(s["anchor_id"])
        if cid is not None:
            hit_clusters.add(cid)
    event_recall = len(hit_clusters) / max(1, len(clusters))
    # Temporal coverage
    selected_times = sorted(float(s["anchor_time"]) for s in selected)
    if len(selected_times) >= 2:
        time_gaps = [selected_times[i+1] - selected_times[i] for i in range(len(selected_times)-1)]
        max_gap = max(time_gaps)
        mean_gap = np.mean(time_gaps)
    else:
        max_gap = 0
        mean_gap = 0
    return {
        "positive_recall": f"{anchor_recall:.4f}",
        "event_cluster_recall": f"{event_recall:.4f}",
        "precision": f"{precision:.4f}",
        "positives_found": tp,
        "clusters_hit": len(hit_clusters),
        "max_time_gap": f"{max_gap:.1f}",
        "mean_time_gap": f"{mean_gap:.1f}",
    }

# Define methods
def method_uniform_random(rows, B, seed=42):
    rng = random.Random(seed)
    return rng.sample(rows, min(B, len(rows)))

def method_temporal_grid(rows, B):
    sorted_rows = sorted(rows, key=lambda m: m["anchor_idx"])
    n = len(sorted_rows)
    if B >= n: return sorted_rows
    step = n / B
    indices = [int(i * step) for i in range(B)]
    return [sorted_rows[i] for i in indices]

def method_top_proxy(rows, B, score="score_fusion"):
    return sorted(rows, key=lambda m: -m[score])[:B]

def method_top_proxy_temporal_nms(rows, B, score="score_fusion", nms_window=3):
    """Top proxy with temporal NMS: suppress anchors within nms_window of a higher-scoring selected anchor."""
    sorted_rows = sorted(rows, key=lambda m: -m[score])
    selected = []
    suppressed = set()
    for r in sorted_rows:
        if len(selected) >= B: break
        if r["anchor_id"] in suppressed: continue
        selected.append(r)
        # Suppress neighbors
        for other in rows:
            if other["anchor_id"] != r["anchor_id"] and abs(other["anchor_idx"] - r["anchor_idx"]) <= nms_window:
                suppressed.add(other["anchor_id"])
    return selected[:B]

def method_diversity_prefilter(rows, B, score="score_fusion", P=2):
    """Budget decomposition: select top P*B by proxy, then choose B by temporal diversity."""
    top_P = sorted(rows, key=lambda m: -m[score])[:P*B]
    if len(top_P) <= B: return top_P
    # Greedy temporal spread: pick from evenly spaced time blocks
    top_P_sorted = sorted(top_P, key=lambda m: m["anchor_idx"])
    n = len(top_P_sorted)
    step = n / B
    indices = [int(i * step) for i in range(B)]
    return [top_P_sorted[i] for i in indices]

def method_stratified_proxy_temporal(rows, B):
    """Stratify by proxy quartile, allocate B proportionally, pick temporally spread within each stratum."""
    sorted_rows = sorted(rows, key=lambda m: m["score_fusion"])
    q_size = len(sorted_rows) // 4
    strata = [sorted_rows[i*q_size:(i+1)*q_size] for i in range(4)]
    if len(sorted_rows) % 4: strata[-1].extend(sorted_rows[4*q_size:])
    # Allocate budget proportionally
    selected = []
    for si, stratum in enumerate(strata):
        b_i = max(1, B // 4)
        # Pick temporally spread
        stratum_sorted = sorted(stratum, key=lambda m: m["anchor_idx"])
        if len(stratum_sorted) <= b_i:
            selected.extend(stratum_sorted)
        else:
            step = len(stratum_sorted) / b_i
            indices = [int(i * step) for i in range(b_i)]
            selected.extend([stratum_sorted[i] for i in indices])
    return selected[:B]

def method_coverage_greedy_time_blocks(rows, B, n_blocks=12):
    """Coverage-greedy: divide video into n_blocks time blocks, pick ceil(B/n_blocks) from each by proxy score."""
    block_size = max(1, len(rows) // n_blocks)
    sorted_rows = sorted(rows, key=lambda m: m["anchor_idx"])
    blocks = [sorted_rows[i*block_size:(i+1)*block_size] for i in range(n_blocks)]
    if len(sorted_rows) % n_blocks: blocks[-1].extend(sorted_rows[n_blocks*block_size:])
    per_block = max(1, B // n_blocks)
    selected = []
    for block in blocks:
        selected.extend(sorted(block, key=lambda m: -m["score_fusion"])[:per_block])
    return selected[:B]

def method_hybrid_explore_exploit(rows, B, exploit_frac=0.6):
    """Split budget: exploit top proxy (exploit_frac*B), explore random from rest."""
    B_exploit = int(B * exploit_frac)
    B_explore = B - B_exploit
    top = sorted(rows, key=lambda m: -m["score_fusion"])[:B_exploit]
    rest = [m for m in rows if m not in top]
    explore = random.sample(rest, min(B_explore, len(rest))) if B_explore > 0 else []
    return top + explore

def method_cluster_aware(rows, B, score="score_fusion"):
    """If we knew clusters (oracle), pick one anchor per cluster first, then fill with top proxy."""
    # This is an oracle-informed upper bound, not a real method
    selected = []
    seen_clusters = set()
    # First pass: one per cluster (sorted by proxy score within cluster)
    for cl in clusters:
        cl_sorted = sorted(cl, key=lambda m: -m[score])
        if cl_sorted:
            selected.append(cl_sorted[0])
            seen_clusters.add(cl[0]["anchor_id"])
    # Second pass: fill with top proxy
    remaining = [m for m in rows if m not in selected]
    remaining_sorted = sorted(remaining, key=lambda m: -m[score])
    for r in remaining_sorted:
        if len(selected) >= B: break
        selected.append(r)
    return selected[:B]

def method_audit_aware(rows, B, score="score_fusion", audit_frac=0.15):
    """Reserve audit_frac*B for low-score audit sampling."""
    B_main = int(B * (1 - audit_frac))
    B_audit = B - B_main
    main = sorted(rows, key=lambda m: -m[score])[:B_main]
    rest = [m for m in rows if m not in main]
    # Audit: sample from low-score region
    rest_sorted = sorted(rest, key=lambda m: m[score])
    audit = rest_sorted[:B_audit] if B_audit > 0 else []
    return main + audit

methods = {
    "uniform_random": method_uniform_random,
    "uniform_temporal_grid": method_temporal_grid,
    "top_proxy": method_top_proxy,
    "top_proxy_temporal_nms": method_top_proxy_temporal_nms,
    "proxy_diversity_prefilter": method_diversity_prefilter,
    "stratified_proxy_temporal": method_stratified_proxy_temporal,
    "coverage_greedy_time_blocks": method_coverage_greedy_time_blocks,
    "hybrid_explore_exploit": method_hybrid_explore_exploit,
    "cluster_aware_selection": method_cluster_aware,
    "audit_aware_selection": method_audit_aware,
}

replay_results = []
for B in BUDGETS:
    for method_name, method_fn in methods.items():
        if method_name == "uniform_random":
            # Average over 200 repeats
            recalls = []
            event_recalls = []
            precisions = []
            for seed in range(N_RANDOM_REPEATS):
                sel = method_fn(merged, B, seed=seed)
                ev = evaluate_selection(sel, merged, n_pos, clusters, anchor_to_cluster)
                recalls.append(float(ev["positive_recall"]))
                event_recalls.append(float(ev["event_cluster_recall"]))
                precisions.append(float(ev["precision"]))
            replay_results.append({
                "method": method_name, "budget": B,
                "positive_recall": f"{np.mean(recalls):.4f}",
                "positive_recall_std": f"{np.std(recalls):.4f}",
                "event_cluster_recall": f"{np.mean(event_recalls):.4f}",
                "precision": f"{np.mean(precisions):.4f}",
                "positives_found": f"{np.mean([float(r) for r in recalls])*n_pos:.1f}",
                "clusters_hit": f"{np.mean(event_recalls)*len(clusters):.1f}",
                "n_repeats": N_RANDOM_REPEATS,
            })
        else:
            sel = method_fn(merged, B)
            ev = evaluate_selection(sel, merged, n_pos, clusters, anchor_to_cluster)
            replay_results.append({
                "method": method_name, "budget": B,
                "positive_recall": ev["positive_recall"],
                "positive_recall_std": "0",
                "event_cluster_recall": ev["event_cluster_recall"],
                "precision": ev["precision"],
                "positives_found": ev["positives_found"],
                "clusters_hit": ev["clusters_hit"],
                "n_repeats": 1,
            })
    print(f"  B={B}: " + " | ".join(f"{r['method']}={r['positive_recall']}" for r in replay_results if r['budget'] == B))

# Save replay results
with open(f"{OUT}/replay/budget_replay_results.csv", "w", newline="") as f:
    fields = ["method", "budget", "positive_recall", "positive_recall_std", "event_cluster_recall", "precision", "positives_found", "clusters_hit", "n_repeats"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(replay_results)

# Method by budget summary (best method per budget)
print("\n  Best method per budget (by event cluster recall):")
for B in BUDGETS:
    budget_results = [r for r in replay_results if r["budget"] == B]
    best = max(budget_results, key=lambda r: float(r["event_cluster_recall"]))
    print(f"    B={B}: {best['method']} (event_recall={best['event_cluster_recall']}, anchor_recall={best['positive_recall']}, precision={best['precision']})")

# Save full analysis JSON
analysis = {
    "n_anchors": n_total, "n_positives": n_pos, "positive_rate": n_pos/n_total,
    "n_clusters": len(clusters), "n_singletons": sum(1 for c in clusters if len(c) == 1),
    "n_multi_clusters": sum(1 for c in clusters if len(c) > 1),
    "largest_cluster": max(len(c) for c in clusters),
    "p_stay_positive": p_stay, "base_rate": base_rate,
    "proxy_aucs": proxy_aucs,
    "quartile_rates": quartile_rates,
    "object_distribution": dict(Counter(m["involved_object"] for m in pos)),
    "negative_reasons": dict(Counter(m["negative_reason"] for m in neg)),
    "boundary_unique_starts": len(set(m["event_start"] for m in pos if m["event_start"])),
    "boundary_unique_ends": len(set(m["event_end"] for m in pos if m["event_end"])),
}
with open(f"{OUT}/analysis/full_center10_analysis.json", "w") as f:
    json.dump(analysis, f, indent=2, ensure_ascii=False)

print(f"\nAll analysis saved to {OUT}/analysis/")
print(f"Replay results saved to {OUT}/replay/budget_replay_results.csv")
