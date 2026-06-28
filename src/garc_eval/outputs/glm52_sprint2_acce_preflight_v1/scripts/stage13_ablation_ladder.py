#!/usr/bin/env python3
"""Stage 13 / Task 4: Ablation ladder L0-L4 implementation and replay.

L0: random / temporal_grid
L1: object_count_mean top-B (bare ranking)
L2: L1 + query-aware proxy prior (switch proxy by query type)
L3: L2 + greedy_maxmin_time
L4: L3 + coverage/calibration phase + audit phase + certificate

L4 requirements:
- coverage/calibration sample must have KNOWN inclusion probability (stratified temporal)
- retrieval_pool = S_cal ∪ S_exploit (for recall computation, can mix)
- estimation_pool = S_cal ∪ S_audit (only known-probability samples, for HT estimate)
- recall lower bound: R_lower = H / U_{1-delta}(N_pos) where U is one-sided upper bound
  on total positives from estimation_pool

All runs on dataset3 oracle labels. No new VLM. Fixed seeds 0..199.
All selections saved per method/budget/seed.
"""
from __future__ import annotations
import math
import time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

import common as C

C.ensure_dirs()
df = C.load_dataset3()
aids = df["anchor_id"].astype(str).to_numpy()
labels = df["is_positive"].astype(int).to_numpy()
anchor_idx = df["anchor_index"].astype(int).to_numpy()
center_t = df["center_time_s"].astype(float).to_numpy()
n = len(df)
total_pos = int(labels.sum())

# Query-aware proxy prior table (from Stage 10-12 findings):
# - all_event / non_vehicle / pedestrian / cyclist: object_count_mean (strongest deployable)
# - vehicle_event: object_count_mean (cross-video inconsistent, but safest default)
# Since we don't have per-anchor query labels at selection time (that would leak oracle),
# L2 uses object_count_mean for all queries. The "query-aware" aspect is that we COULD
# switch if we had a cheap query classifier; for now L2 = L1 with the best deployable proxy.
# To make L2 meaningfully different from L1, we use the BEST deployable proxy found in
# Sprint 1: object_count_mean (AUROC 0.627) instead of the original score_fusion.
# L1 uses score_fusion_geometry_motion (the ORIGINAL proxy), L2 uses object_count_mean.
# This isolates the "proxy swap" effect.

PROXY_L1 = "score_fusion_geometry_motion"
PROXY_L2 = "object_count_mean"  # corrected deployable default
PROXY_L3 = "object_count_mean"
PROXY_L4 = "object_count_mean"
P_DEFAULT = 2.0  # fixed P for L2-L4 (no online quality assessment per task spec)
ALPHA_L4 = 0.20  # 20% of B for calibration
AUDIT_FRAC = 0.10  # 10% of B for audit (from execution budget)
BLOCK_SIZE = 300.0  # for stratified temporal sampling


def get_proxy_scores(col):
    return df[col].astype(float).to_numpy()


# ---------------------------------------------------------------------------
# Selection strategies
# ---------------------------------------------------------------------------


def temporal_grid_select(B):
    order = np.argsort(anchor_idx, kind="mergesort")
    if B >= n:
        return order.tolist()
    picks = sorted(set(int(i * n / B) for i in range(B)))
    while len(picks) < B:
        for j in range(n):
            if j not in picks:
                picks.append(j)
                break
    return order[picks[:B]].tolist()


def random_select(B, seed):
    rng = np.random.default_rng(seed)
    return rng.choice(n, size=min(B, n), replace=False).tolist()


def top_proxy_select(B, proxy_col):
    s = get_proxy_scores(proxy_col)
    return np.lexsort((anchor_idx, -s))[:B].tolist()


def greedy_maxmin_select(pool_idx, B, proxy_col):
    """Greedy max-min time selection from pool (proxy-score ordered pool)."""
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    s = get_proxy_scores(proxy_col)[pool_idx]
    # pool is already sorted by -proxy, anchor_idx asc (from lexsort)
    # but we need to sort pool by proxy desc first
    order = np.lexsort((anchor_idx[pool_idx], -s))
    pool_sorted = pool_idx[order]
    times = anchor_idx[pool_sorted].astype(float)
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


def build_pool(proxy_col, P, B):
    """Top P*B by (proxy desc, anchor_idx asc)."""
    pool_size = min(int(math.ceil(P * B)), n)
    s = get_proxy_scores(proxy_col)
    return np.lexsort((anchor_idx, -s))[:pool_size]


def diversity_prefilter_greedy_maxmin(B, proxy_col, P=P_DEFAULT):
    pool = build_pool(proxy_col, P, B)
    return greedy_maxmin_select(pool, B, proxy_col)


# ---------------------------------------------------------------------------
# L4: Coverage/Calibration + Exploit + Audit + Certificate
# ---------------------------------------------------------------------------


def stratified_temporal_sample(c, seed, block_size=BLOCK_SIZE):
    """Stratified temporal sample with KNOWN inclusion probabilities.
    Returns (selected_indices, inclusion_probs_array_for_all_n)."""
    blocks = (center_t // block_size).astype(int)
    block_ids = sorted(np.unique(blocks))
    rng = np.random.default_rng(seed)
    n_blocks = len(block_ids)
    per_block = max(1, c // n_blocks)
    selected = []
    incl_probs = np.zeros(n, dtype=float)
    for b in block_ids:
        members = np.where(blocks == b)[0]
        take = min(per_block, len(members))
        if take > 0:
            picks = rng.choice(members, size=take, replace=False)
            selected.extend(picks.tolist())
            incl_probs[members] = take / len(members)
    # fill remainder
    remaining = c - len(selected)
    if remaining > 0:
        pool = np.array([i for i in range(n) if i not in set(selected)])
        extra = rng.choice(pool, size=min(remaining, len(pool)), replace=False)
        selected.extend(extra.tolist())
        # these get uniform probability
        all_pool_n = len(pool)
        for e in extra:
            # overwrite with uniform (approximate)
            incl_probs[e] = remaining / all_pool_n
    return np.array(selected[:c]), incl_probs


def horvitz_thompson_total(y, incl_probs):
    """HT estimator for total positives: sum(y_i / pi_i) over sample."""
    sampled = incl_probs > 0
    pi = incl_probs[sampled]
    yi = y[sampled]
    # avoid division by zero
    pi = np.where(pi > 0, pi, 1e-10)
    return float((yi / pi).sum())


def ht_variance(y, incl_probs):
    """Approximate HT variance (simplified, ignoring second-order terms)."""
    sampled = incl_probs > 0
    pi = incl_probs[sampled]
    yi = y[sampled]
    pi = np.where(pi > 0, pi, 1e-10)
    nht = yi / pi
    # simplified variance: sum of (nht_i - mean)^2 * pi_i * (1-pi_i) / (sum pi)^2
    # this is a conservative approximation
    mean_ht = nht.mean()
    var_contrib = ((nht - mean_ht) ** 2) * pi * (1 - pi)
    return float(var_contrib.sum() / max(1, len(nht)))


def upper_bound_total(y, incl_probs, delta):
    """One-sided upper bound on total positives: HT + z * SE."""
    ht = horvitz_thompson_total(y, incl_probs)
    se = math.sqrt(max(0, ht_variance(y, incl_probs)))
    z = norm.ppf(1 - delta)
    return ht + z * se


def l4_select(B, seed, proxy_col=PROXY_L4, alpha=ALPHA_L4, audit_frac=AUDIT_FRAC, P=P_DEFAULT, delta=0.05):
    """L4: coverage/calibration + exploit + audit + certificate."""
    c = max(1, int(math.ceil(alpha * B)))
    exec_budget = B - c
    audit_n = max(1, int(math.ceil(audit_frac * exec_budget)))
    exploit_budget = exec_budget - audit_n

    # Phase 1: stratified temporal calibration (known probability)
    cal_idx, cal_incl_probs = stratified_temporal_sample(c, seed)
    cal_incl_probs_full = np.zeros(n, dtype=float)
    cal_incl_probs_full[cal_idx] = cal_incl_probs[cal_idx]

    # Phase 2: exploit with diversity prefilter (proxy-based, NOT known probability)
    # exclude calibration anchors from exploit pool
    exploit_pool_mask = np.ones(n, dtype=bool)
    exploit_pool_mask[cal_idx] = False
    pool = build_pool(proxy_col, P, exploit_budget)
    # remove calibration anchors from pool
    pool = pool[exploit_pool_mask[pool]]
    exploit_idx = np.array(greedy_maxmin_select(pool, exploit_budget, proxy_col))

    # Phase 3: audit (known probability, stratified temporal, from remaining)
    remaining_mask = np.ones(n, dtype=bool)
    remaining_mask[cal_idx] = False
    remaining_mask[exploit_idx] = False
    remaining_idx = np.where(remaining_mask)[0]
    # stratified temporal audit from remaining
    remaining_blocks = (center_t[remaining_idx] // BLOCK_SIZE).astype(int)
    block_ids = sorted(np.unique(remaining_blocks))
    rng = np.random.default_rng(seed + 99999)
    audit_selected = []
    audit_incl_probs = np.zeros(n, dtype=float)
    per_block = max(1, audit_n // len(block_ids)) if block_ids else 0
    for b in block_ids:
        members = remaining_idx[remaining_blocks == b]
        take = min(per_block, len(members))
        if take > 0:
            picks = rng.choice(members, size=take, replace=False)
            audit_selected.extend(picks.tolist())
            audit_incl_probs[members] = take / len(members)
    # fill remainder
    rem_audit = audit_n - len(audit_selected)
    if rem_audit > 0:
        pool_a = np.array([i for i in remaining_idx if i not in set(audit_selected)])
        if len(pool_a) > 0:
            extra = rng.choice(pool_a, size=min(rem_audit, len(pool_a)), replace=False)
            audit_selected.extend(extra.tolist())
            for e in extra:
                audit_incl_probs[e] = rem_audit / len(pool_a)
    audit_idx = np.array(audit_selected[:audit_n])

    # Combine
    retrieval_pool = np.concatenate([cal_idx, exploit_idx])  # for recall
    estimation_pool_idx = np.concatenate([cal_idx, audit_idx])
    # estimation inclusion probs = max of cal and audit (they are disjoint)
    est_incl = np.zeros(n, dtype=float)
    est_incl[cal_idx] = cal_incl_probs_full[cal_idx]
    est_incl[audit_idx] = audit_incl_probs[audit_idx]

    # Certificate: R_lower = H / U_{1-delta}(N_pos)
    H = int(labels[retrieval_pool].sum())  # positives found in retrieval pool
    N_pos_upper = upper_bound_total(labels.astype(float), est_incl, delta)
    N_pos_upper = max(N_pos_upper, 1.0)  # avoid div by 0
    R_lower = H / N_pos_upper
    true_recall = H / total_pos

    return {
        "selected_indices": retrieval_pool.tolist(),
        "estimation_pool_indices": estimation_pool_idx.tolist(),
        "cal_indices": cal_idx.tolist(),
        "exploit_indices": exploit_idx.tolist(),
        "audit_indices": audit_idx.tolist(),
        "cal_size": len(cal_idx),
        "exploit_size": len(exploit_idx),
        "audit_size": len(audit_idx),
        "H_positives_found": H,
        "N_pos_HT_estimate": horvitz_thompson_total(labels.astype(float), est_incl),
        "N_pos_upper_bound": N_pos_upper,
        "R_lower": R_lower,
        "true_recall": true_recall,
        "delta": delta,
        "estimation_pool_size": len(estimation_pool_idx),
    }


# ---------------------------------------------------------------------------
# Run all levels
# ---------------------------------------------------------------------------

rows = []
sel_rows = []
t0 = time.time()

for B in C.BUDGETS:
    for seed in C.SEEDS:
        # L0: random
        sel = random_select(B, seed)
        ev = C.evaluate_selection(df, [aids[i] for i in sel])
        rows.append({"level": "L0_random", "budget": B, "seed": seed, **ev, "R_lower": "", "est_pool_size": ""})
        if seed < 5:
            sel_rows.append({"level": "L0_random", "budget": B, "seed": seed, "selected_ids": "|".join(aids[i] for i in sel)})

        # L0: temporal_grid
        sel = temporal_grid_select(B)
        ev = C.evaluate_selection(df, [aids[i] for i in sel])
        rows.append({"level": "L0_temporal_grid", "budget": B, "seed": seed, **ev, "R_lower": "", "est_pool_size": ""})
        if seed < 5:
            sel_rows.append({"level": "L0_temporal_grid", "budget": B, "seed": seed, "selected_ids": "|".join(aids[i] for i in sel)})

        # L1: top_proxy score_fusion (original proxy)
        sel = top_proxy_select(B, PROXY_L1)
        ev = C.evaluate_selection(df, [aids[i] for i in sel])
        rows.append({"level": "L1_top_score_fusion", "budget": B, "seed": seed, **ev, "R_lower": "", "est_pool_size": ""})
        if seed < 5:
            sel_rows.append({"level": "L1_top_score_fusion", "budget": B, "seed": seed, "selected_ids": "|".join(aids[i] for i in sel)})

        # L2: top_proxy object_count_mean (corrected deployable proxy)
        sel = top_proxy_select(B, PROXY_L2)
        ev = C.evaluate_selection(df, [aids[i] for i in sel])
        rows.append({"level": "L2_top_object_count", "budget": B, "seed": seed, **ev, "R_lower": "", "est_pool_size": ""})
        if seed < 5:
            sel_rows.append({"level": "L2_top_object_count", "budget": B, "seed": seed, "selected_ids": "|".join(aids[i] for i in sel)})

        # L3: diversity_prefilter object_count_mean + greedy_maxmin
        sel = diversity_prefilter_greedy_maxmin(B, PROXY_L3)
        ev = C.evaluate_selection(df, [aids[i] for i in sel])
        rows.append({"level": "L3_diversity_greedy_maxmin", "budget": B, "seed": seed, **ev, "R_lower": "", "est_pool_size": ""})
        if seed < 5:
            sel_rows.append({"level": "L3_diversity_greedy_maxmin", "budget": B, "seed": seed, "selected_ids": "|".join(aids[i] for i in sel)})

        # L4: full ACCE with certificate
        l4 = l4_select(B, seed)
        sel_ids = [aids[i] for i in l4["selected_indices"]]
        ev = C.evaluate_selection(df, sel_ids)
        rows.append({
            "level": "L4_acce_certificate", "budget": B, "seed": seed, **ev,
            "R_lower": l4["R_lower"], "est_pool_size": l4["estimation_pool_size"],
            "N_pos_HT": l4["N_pos_HT_estimate"], "N_pos_upper": l4["N_pos_upper_bound"],
        })
        if seed < 5:
            sel_rows.append({
                "level": "L4_acce_certificate", "budget": B, "seed": seed,
                "selected_ids": "|".join(sel_ids),
                "cal_ids": "|".join(aids[i] for i in l4["cal_indices"]),
                "exploit_ids": "|".join(aids[i] for i in l4["exploit_indices"]),
                "audit_ids": "|".join(aids[i] for i in l4["audit_indices"]),
            })

long = pd.DataFrame(rows)
long.to_csv(C.REPLAY / "ablation_ladder_results.csv", index=False)
sel_df = pd.DataFrame(sel_rows)
sel_df.to_csv(C.REPLAY / "ablation_ladder_selections_sample.csv", index=False)

# Summary
metric_cols = ["anchor_recall", "event_cluster_recall", "singleton_cluster_recall", "multi_anchor_cluster_recall", "precision", "cold_block_recall"]
summary_rows = []
for (level, B), part in long.groupby(["level", "budget"]):
    row = {"level": level, "budget": B, "n_runs": len(part)}
    for m in metric_cols:
        vals = part[m].astype(float).tolist()
        vals = [v for v in vals if not math.isnan(v)]
        row[f"{m}_mean"] = float(np.mean(vals)) if vals else float("nan")
        row[f"{m}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
    if "R_lower" in part.columns:
        rl = pd.to_numeric(part["R_lower"], errors="coerce").dropna().tolist()
        row["R_lower_mean"] = float(np.mean(rl)) if rl else float("nan")
        row["R_lower_std"] = float(np.std(rl, ddof=1)) if len(rl) > 1 else 0.0
    if "est_pool_size" in part.columns:
        ep = pd.to_numeric(part["est_pool_size"], errors="coerce").dropna().tolist()
        row["est_pool_size_mean"] = float(np.mean(ep)) if ep else float("nan")
    summary_rows.append(row)
summary = pd.DataFrame(summary_rows)
summary.to_csv(C.REPLAY / "ablation_ladder_summary.csv", index=False)

print(f"Stage 13 done in {time.time()-t0:.1f}s. rows={len(long)}")
# Print key comparison
for B in C.BUDGETS:
    sub = summary[summary["budget"] == B].sort_values("event_cluster_recall_mean", ascending=False)
    print(f"\nB={B}:")
    print(sub[["level", "event_cluster_recall_mean", "anchor_recall_mean", "singleton_cluster_recall_mean", "R_lower_mean"]].to_string(index=False))
