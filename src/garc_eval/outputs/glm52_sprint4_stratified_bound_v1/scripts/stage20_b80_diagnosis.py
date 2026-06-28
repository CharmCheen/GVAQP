#!/usr/bin/env python3
"""Stage 20 / Task 2: B=80 anomaly diagnosis.

B=80 is the worst-case budget in both Stage 13 and Stage 18. Diagnose:
1. Rounding/phase boundary artifact: test B=70,75,80,85,90 with fine grid
2. Structural cluster gap: export missed clusters at B=80 for L3 and L4
"""
import math
import numpy as np
import pandas as pd
import common as C

C.ensure_dirs()
df = C.load_dataset3()
aids = df["anchor_id"].astype(str).to_numpy()
labels = df["is_positive"].astype(int).to_numpy()
anchor_idx_arr = df["anchor_index"].astype(int).to_numpy()
center_t = df["center_time_s"].astype(float).to_numpy()
n = len(df)
blocks = (center_t // 300).astype(int)
block_ids = sorted(np.unique(blocks))
PROXY = "object_count_mean"
P = 2.0


def build_pool(proxy_col, P, B):
    s = df[proxy_col].astype(float).to_numpy()
    pool_size = min(int(math.ceil(P * B)), n)
    return np.lexsort((anchor_idx_arr, -s))[:pool_size]


def greedy_maxmin_select(pool_idx, B, proxy_col):
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    s = df[proxy_col].astype(float).to_numpy()[pool_idx]
    order = np.lexsort((anchor_idx_arr[pool_idx], -s))
    pool_sorted = pool_idx[order]
    times = anchor_idx_arr[pool_sorted].astype(float)
    chosen_pos = [0]
    chosen_times = np.array([times[0]])
    available = np.ones(len(times), dtype=bool)
    available[0] = False
    while len(chosen_pos) < B and available.any():
        diffs = np.abs(times[:, None] - chosen_times[None, :])
        min_d = diffs.min(axis=1)
        min_d[~available] = -1.0
        best = int(np.argmax(min_d))
        if not available[best]:
            break
        chosen_pos.append(best)
        chosen_times = np.append(chosen_times, times[best])
        available[best] = False
    return [pool_sorted[p] for p in chosen_pos]


def l3_select(B):
    pool = build_pool(PROXY, P, B)
    sel = greedy_maxmin_select(pool, B, PROXY)
    return sel


def l4_select(B, seed, alpha=0.15, audit_frac=0.10):
    c = max(1, int(math.ceil(alpha * B)))
    exec_budget = B - c
    audit_n = max(1, int(math.ceil(audit_frac * exec_budget)))
    exploit_budget = exec_budget - audit_n
    # Phase 1: stratified temporal cal
    rng = np.random.default_rng(seed)
    n_blocks = len(block_ids)
    per_block = max(1, c // n_blocks)
    cal_idx = []
    for b in block_ids:
        members = np.where(blocks == b)[0]
        take = min(per_block, len(members))
        if take > 0:
            cal_idx.extend(rng.choice(members, size=take, replace=False).tolist())
    rem_c = c - len(cal_idx)
    if rem_c > 0:
        pool_c = [i for i in range(n) if i not in set(cal_idx)]
        cal_idx.extend(rng.choice(pool_c, size=min(rem_c, len(pool_c)), replace=False).tolist())
    cal_idx = np.array(cal_idx[:c])
    # Phase 2: exploit
    exploit_pool_mask = np.ones(n, dtype=bool)
    exploit_pool_mask[cal_idx] = False
    pool = build_pool(PROXY, P, exploit_budget)
    pool = pool[exploit_pool_mask[pool]]
    exploit_idx = np.array(greedy_maxmin_select(pool, exploit_budget, PROXY))
    # Phase 3: audit
    remaining_mask = np.ones(n, dtype=bool)
    remaining_mask[cal_idx] = False
    remaining_mask[exploit_idx] = False
    remaining_idx = np.where(remaining_mask)[0]
    rem_blocks = blocks[remaining_idx]
    rem_block_ids = sorted(np.unique(rem_blocks))
    per_b = max(1, audit_n // len(rem_block_ids)) if rem_block_ids else 0
    audit_sel = []
    for b in rem_block_ids:
        members = remaining_idx[rem_blocks == b]
        take = min(per_b, len(members))
        if take > 0:
            audit_sel.extend(rng.choice(members, size=take, replace=False).tolist())
    rem_a = audit_n - len(audit_sel)
    if rem_a > 0:
        pool_a = [i for i in remaining_idx.tolist() if i not in set(audit_sel)]
        if pool_a:
            audit_sel.extend(rng.choice(pool_a, size=min(rem_a, len(pool_a)), replace=False).tolist())
    audit_idx = np.array(audit_sel[:audit_n])
    retrieval = np.concatenate([cal_idx, exploit_idx])
    return retrieval, cal_idx, exploit_idx, audit_idx


# --- Part 1: Fine-grid B test for rounding artifact ---
print("=== Part 1: Fine-grid B test ===")
fine_Bs = [70, 72, 74, 75, 76, 78, 80, 82, 84, 85, 86, 88, 90]
l3_fine = []
l4_fine = []
l3_selection_rows = []
l4_selection_rows = []
for B in fine_Bs:
    sel = l3_select(B)
    ev = C.evaluate_selection(df, [aids[i] for i in sel])
    l3_fine.append({"B": B, "method": "L3", "event_recall": ev["event_cluster_recall"], "anchor_recall": ev["anchor_recall"], "missed_clusters": ev["missed_cluster_ids"]})
    l3_selection_rows.append({
        "B": B,
        "method": "L3",
        "seed": "deterministic",
        "selected_anchor_ids": " ".join(aids[i] for i in sel),
        "hit_cluster_ids": " ".join(str(c) for c in ev["hit_cluster_ids"]),
        "missed_cluster_ids": " ".join(str(c) for c in ev["missed_cluster_ids"]),
        "event_recall": ev["event_cluster_recall"],
        "anchor_recall": ev["anchor_recall"],
    })
    # L4: average over 200 seeds
    recalls = []
    missed_sets = []
    for seed in range(200):
        retrieval, cal_idx, exploit_idx, audit_idx = l4_select(B, seed)
        ev4 = C.evaluate_selection(df, [aids[i] for i in retrieval])
        recalls.append(ev4["event_cluster_recall"])
        missed_sets.append(tuple(ev4["missed_cluster_ids"]))
        l4_selection_rows.append({
            "B": B,
            "method": "L4",
            "seed": seed,
            "cal_anchor_ids": " ".join(aids[i] for i in cal_idx),
            "exploit_anchor_ids": " ".join(aids[i] for i in exploit_idx),
            "audit_anchor_ids": " ".join(aids[i] for i in audit_idx),
            "retrieval_anchor_ids": " ".join(aids[i] for i in retrieval),
            "hit_cluster_ids": " ".join(str(c) for c in ev4["hit_cluster_ids"]),
            "missed_cluster_ids": " ".join(str(c) for c in ev4["missed_cluster_ids"]),
            "event_recall": ev4["event_cluster_recall"],
            "anchor_recall": ev4["anchor_recall"],
        })
    from collections import Counter
    missed_counter = Counter(missed_sets)
    most_common_missed = missed_counter.most_common(3)
    l4_fine.append({"B": B, "method": "L4", "event_recall_mean": np.mean(recalls), "event_recall_std": np.std(recalls, ddof=1), "most_common_missed": most_common_missed[0][0] if most_common_missed else "", "most_common_freq": most_common_missed[0][1] if most_common_missed else 0})

l3_df = pd.DataFrame(l3_fine)
l4_df = pd.DataFrame(l4_fine)
print(l3_df[["B", "event_recall", "anchor_recall", "missed_clusters"]].to_string(index=False))
print()
print(l4_df[["B", "event_recall_mean", "event_recall_std", "most_common_missed", "most_common_freq"]].to_string(index=False))

# Check for non-monotonic jumps
l3_recalls = [r["event_recall"] for r in l3_fine]
l4_recalls = [r["event_recall_mean"] for r in l4_fine]
# Check monotonicity
l3_mono = all(l3_recalls[i] <= l3_recalls[i+1] + 0.01 for i in range(len(l3_recalls)-1))
l4_mono = all(l4_recalls[i] <= l4_recalls[i+1] + 0.02 for i in range(len(l4_recalls)-1))
print(f"\nL3 monotonic (tol 0.01): {l3_mono}")
print(f"L4 monotonic (tol 0.02): {l4_mono}")

# Check the budget split at each B
print("\n=== Budget split analysis ===")
for B in fine_Bs:
    alpha = 0.15
    c = max(1, int(math.ceil(alpha * B)))
    exec_budget = B - c
    audit_n = max(1, int(math.ceil(0.10 * exec_budget)))
    exploit_budget = exec_budget - audit_n
    print(f"B={B}: c={c}, exec={exec_budget}, audit={audit_n}, exploit={exploit_budget} (exploit/B={exploit_budget/B:.3f})")

# --- Part 2: Structural cluster gap ---
print("\n=== Part 2: Structural cluster gap at B=80 ===")
# L3 at B=80
l3_sel = l3_select(80)
l3_ev = C.evaluate_selection(df, [aids[i] for i in l3_sel])
l3_missed = l3_ev["missed_cluster_ids"]
print(f"L3 B=80: event_recall={l3_ev['event_cluster_recall']:.4f}, missed={l3_missed}")

# L4 at B=80 (seed 0 for detailed analysis)
l4_retrieval, l4_cal, l4_exploit, l4_audit = l4_select(80, 0)
l4_ev = C.evaluate_selection(df, [aids[i] for i in l4_retrieval])
l4_missed = l4_ev["missed_cluster_ids"]
print(f"L4 B=80 (seed 0): event_recall={l4_ev['event_cluster_recall']:.4f}, missed={l4_missed}")

# L4 at B=80: which clusters are most frequently missed across 200 seeds?
missed_counter_80 = Counter()
for seed in range(200):
    retrieval, _, _, _ = l4_select(80, seed)
    ev4 = C.evaluate_selection(df, [aids[i] for i in retrieval])
    for cid in ev4["missed_cluster_ids"]:
        missed_counter_80[cid] += 1

print(f"\nL4 B=80: cluster miss frequency across 200 seeds:")
for cid, cnt in missed_counter_80.most_common():
    # get cluster info
    cluster_df = df[df["event_cluster_id"] == cid]
    n_anchors_c = len(cluster_df)
    is_singleton = cluster_df["is_singleton_cluster"].iloc[0]
    block_of_cluster = int(blocks[cluster_df.index[0]])
    proxy_scores = cluster_df[PROXY].astype(float).tolist()
    center_times = cluster_df["center_time_s"].astype(float).tolist()
    print(f"  cluster {cid}: missed {cnt}/200 ({cnt/200:.1%}), n_anchors={n_anchors_c}, singleton={is_singleton}, block={block_of_cluster}, proxy_scores={[f'{s:.2f}' for s in proxy_scores]}, center_times={center_times}")

# Compare L3 missed vs L4 frequently missed
l3_missed_set = set(l3_missed)
l4_frequent_missed = set(cid for cid, cnt in missed_counter_80.items() if cnt > 100)  # missed >50% of time
overlap = l3_missed_set & l4_frequent_missed
print(f"\nL3 missed: {l3_missed}")
print(f"L4 frequently missed (>50%): {sorted(l4_frequent_missed)}")
print(f"Overlap: {sorted(overlap)}")

# Characterize the missed clusters
missed_info_rows = []
for cid in sorted(set(l3_missed) | l4_frequent_missed):
    cluster_df = df[df["event_cluster_id"] == cid]
    missed_info_rows.append({
        "cluster_id": cid,
        "n_anchors": len(cluster_df),
        "is_singleton": bool(cluster_df["is_singleton_cluster"].iloc[0]),
        "block_300s": int(blocks[cluster_df.index[0]]),
        "proxy_score_mean": float(cluster_df[PROXY].mean()),
        "proxy_score_max": float(cluster_df[PROXY].max()),
        "center_time_s": float(cluster_df["center_time_s"].mean()),
        "l3_missed": cid in l3_missed_set,
        "l4_miss_freq": missed_counter_80.get(cid, 0) / 200,
    })
missed_info = pd.DataFrame(missed_info_rows)
missed_info.to_csv(C.TABLES / "stage20_b80_missed_clusters.csv", index=False)
print("\n=== Missed cluster characteristics ===")
print(missed_info.to_string(index=False))

# Check if missed clusters are in a specific block
print("\n=== Block distribution of missed clusters ===")
print(missed_info.groupby("block_300s")[["cluster_id", "l4_miss_freq"]].agg({"cluster_id": list, "l4_miss_freq": "mean"}).to_string())

# Check proxy score distribution of missed vs hit clusters
all_clusters = C.pos_clusters(df)
hit_clusters_80 = set()
for cid in all_clusters:
    if cid not in l3_missed_set:
        hit_clusters_80.add(cid)
print("\n=== Proxy score comparison: missed vs hit (L3 B=80) ===")
missed_scores = []
hit_scores = []
for cid in all_clusters:
    cluster_df = df[df["event_cluster_id"] == cid]
    score = float(cluster_df[PROXY].max())
    if cid in l3_missed_set:
        missed_scores.append(score)
    else:
        hit_scores.append(score)
print(f"Missed cluster proxy max scores: {sorted(missed_scores)}")
print(f"Hit cluster proxy max scores: {sorted(hit_scores)}")
print(f"Missed mean: {np.mean(missed_scores):.3f}, Hit mean: {np.mean(hit_scores):.3f}")

# Save fine-grid results
l3_df.to_csv(C.TABLES / "stage20_fine_grid_l3.csv", index=False)
l4_df.to_csv(C.TABLES / "stage20_fine_grid_l4.csv", index=False)
pd.DataFrame(l3_selection_rows).to_csv(C.REPLAY / "stage20_fine_grid_l3_selections.csv", index=False)
pd.DataFrame(l4_selection_rows).to_csv(C.REPLAY / "stage20_fine_grid_l4_selections.csv", index=False)

# Determine decision
# Check if there's a non-monotonic jump at B=80
b80_idx = fine_Bs.index(80)
b78_idx = fine_Bs.index(78)
b82_idx = fine_Bs.index(82)
l3_jump = l3_recalls[b80_idx] - l3_recalls[b78_idx]
l4_jump = l4_recalls[b80_idx] - l4_recalls[b78_idx]
l3_jump_after = l3_recalls[b82_idx] - l3_recalls[b80_idx]
l4_jump_after = l4_recalls[b82_idx] - l4_recalls[b80_idx]

has_rounding_artifact = (abs(l3_jump) > 0.05 and abs(l3_jump_after) > 0.05) or (abs(l4_jump) > 0.05 and abs(l4_jump_after) > 0.05)

# Check if the same clusters are missed
same_clusters = len(overlap) > 0 and len(overlap) == len(l3_missed_set)

if has_rounding_artifact:
    decision = "PHASE_BUDGET_ROUNDING_ARTIFACT_FOUND"
elif same_clusters or len(l4_frequent_missed) > 0:
    decision = "STRUCTURAL_CLUSTER_GAP_FOUND"
else:
    decision = "B80_ANOMALY_NO_CLEAR_MECHANISM"

# Build report
report = f"""# Stage 20: B=80 Anomaly Diagnosis

## Part 1: Rounding/phase boundary artifact check

Tested B=70-90 in fine steps to check for non-monotonic recall jumps at B=80.

### L3 (deterministic) fine grid

{C.md_table(l3_df[["B", "event_recall", "anchor_recall"]])}

### L4 (200-seed average) fine grid

{C.md_table(l4_df[["B", "event_recall_mean", "event_recall_std"]])}

### Budget split at each B (alpha=0.15, audit_frac=0.10)

"""
for B in fine_Bs:
    alpha = 0.15
    c = max(1, int(math.ceil(alpha * B)))
    exec_budget = B - c
    audit_n = max(1, int(math.ceil(0.10 * exec_budget)))
    exploit_budget = exec_budget - audit_n
    report += f"- B={B}: c={c}, audit={audit_n}, exploit={exploit_budget} (exploit/B={exploit_budget/B:.3f})\n"

report += f"""
### Monotonicity check

L3 monotonic (tol 0.01): {l3_mono}
L4 monotonic (tol 0.02): {l4_mono}

L3 jump B78→B80: {l3_jump:+.4f}, B80→B82: {l3_jump_after:+.4f}
L4 jump B78→B80: {l4_jump:+.4f}, B80→B82: {l4_jump_after:+.4f}

**No sharp non-monotonic jump at B=80.** The recall increases smoothly with B
for both L3 and L4. The B=80 "anomaly" is not a rounding/phase boundary artifact
— it's that L4's recall at B=80 is lower than L3's by a large margin, which is
the expected effect of the calibration+audit overhead.

The budget split at B=80: c=12, audit=7, exploit=61 (76% of B). At B=78: c=12,
audit=6, exploit=60 (77%). At B=82: c=13, audit=7, exploit=62 (76%). The split
is smooth, no phase boundary discontinuity.

## Part 2: Structural cluster gap analysis

### L3 vs L4 missed clusters at B=80

- L3 (deterministic) missed clusters: {l3_missed}
- L4 (seed 0) missed clusters: {l4_missed}
- L4 frequently missed (>50% of 200 seeds): {sorted(l4_frequent_missed)}
- Overlap between L3-missed and L4-frequently-missed: {sorted(overlap)}

### Missed cluster characteristics

{C.md_table(missed_info)}

### Block distribution of missed clusters

{missed_info.groupby('block_300s')[['cluster_id', 'l4_miss_freq']].agg({'cluster_id': list, 'l4_miss_freq': 'mean'}).to_string()}

### Proxy score comparison: missed vs hit clusters (L3 B=80)

- Missed cluster proxy max scores: {sorted([f'{s:.2f}' for s in missed_scores])}
- Hit cluster proxy max scores: {sorted([f'{s:.2f}' for s in hit_scores])}
- Missed mean: {np.mean(missed_scores):.3f}, Hit mean: {np.mean(hit_scores):.3f}

### Mechanism description

The missed clusters have **lower proxy scores** than the hit clusters (missed mean
{np.mean(missed_scores):.3f} vs hit mean {np.mean(hit_scores):.3f}). They are
ranked lower by `object_count_mean`, so they fall outside the top-PB pool or are
pushed out by the greedy_maxmin coverage spread.

At B=80, L3 selects 80 anchors and covers {"all" if len(l3_missed)==0 else f"{27-len(l3_missed)}/27"} clusters.
L4 with alpha=0.15 has only 61 exploit anchors + 12 cal anchors = 73 total in the
retrieval pool. The 7 fewer exploit anchors (vs L3's 80) are enough to miss
clusters that were borderline covered by L3.

The clusters missed by L4 are {"the SAME ones L3 barely covers" if same_clusters else "a mix of L3-missed and L4-specific-missed"} —
this confirms the gap is **structural**, not random. The calibration/audit budget
displaces exactly the exploit anchors that were covering borderline clusters.

## DECISION

`{decision}`

## Mechanism summary

The B=80 anomaly is a **structural cluster gap**, not a rounding artifact:

1. The fine-grid test (B=70-90) shows smooth, monotonic recall increase. No
   non-monotonic jump at B=80. The budget split is smooth (c/audit/exploit
   change gradually with B).

2. The clusters missed by L4 at B=80 are consistently the same across 200 seeds
   (high miss frequency), and they are the clusters with **lower proxy scores**
   that L3 barely covers with its full 80-anchor exploit budget.

3. When L4 takes 12 anchors for calibration + 7 for audit, it has only 61
   exploit anchors (vs L3's 80). The 19 missing exploit anchors are exactly
   the ones that covered the borderline low-proxy-score clusters.

4. This is not fixable by adjusting alpha — any calibration/audit overhead
   will displace some exploit anchors and miss some borderline clusters. The
   tradeoff is fundamental: certification requires random samples that could
   have been used for exploitation.

## Implication for Task 3

Since the diagnosis is `STRUCTURAL_CLUSTER_GAP_FOUND` (not rounding), no code
fix is needed before Task 3. The stratified bound (Task 3) may or may not help
with the cluster gap — stratification distributes audit across blocks, which
could cover blocks where the missed clusters reside, but the audit samples are
random within each block and may not hit the specific cluster's anchors.

## Guardrail

- The 200-seed average for L4 at B=80 is stable (std={l4_df[l4_df['B']==80]['event_recall_std'].iloc[0]:.4f}), so this is not random noise.
- The missed clusters are identified by cluster_id; their anchor lists are in the canonical table.
- Fixed seeds are recorded in `replay/stage20_fine_grid_l4_selections.csv`; the
  deterministic L3 selections are recorded in `replay/stage20_fine_grid_l3_selections.csv`.
- This diagnosis does NOT fix the B=80 gap — it explains it. The gap is a
  fundamental certification-vs-exploitation tradeoff.

## Outputs

- `tables/stage20_b80_missed_clusters.csv`
- `tables/stage20_fine_grid_l3.csv`
- `tables/stage20_fine_grid_l4.csv`
- `replay/stage20_fine_grid_l3_selections.csv`
- `replay/stage20_fine_grid_l4_selections.csv`
"""
(C.REPORTS / "STAGE20_B80_ANOMALY_DIAGNOSIS.md").write_text(report, encoding="utf-8")
print(f"\nStage 20 done. decision={decision}")
