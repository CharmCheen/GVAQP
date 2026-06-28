#!/usr/bin/env python3
"""Task C: Diversity prefilter ablation.

Form: top-PB by proxy -> select B with temporal strategy.
Ablate pool multiplier P, proxy column, and temporal strategy.

Tie-breaking: top-PB pool is built by (proxy_score desc, anchor_index asc) so ties in
proxy score (common for count features) are broken deterministically by time order. This
makes results reproducible and removes the tie-breaking anomaly seen in Task B baselines.

No new VLM/LLM/YOLO/CLIP.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import common as C

C.ensure_dirs()
df = C.load_data()
aids = df["anchor_id"].astype(str).to_numpy()
labels = df["is_positive"].astype(int).to_numpy()
anchor_idx = df["anchor_index"].astype(int).to_numpy()
center_t = df["center_time_s"].astype(float).to_numpy()
n = len(df)
total_pos = int(labels.sum())

PROXY_COLS = [
    "score_fusion_geometry_motion",
    "object_count_mean",
    "person_count_max",
    "person_count_mean",
    "bike_count_max",
    "vehicle_count_mean",
    "motion_energy_mean",
]
# Drop proxies that are entirely missing (no signal).
PROXY_COLS = [c for c in PROXY_COLS if c in df.columns and df[c].notna().any()]
P_VALUES = [1.0, 1.25, 1.5, 2.0, 3.0, 4.0]
BUDGETS = [20, 30, 40, 60, 80, 100, 150]
RAND_SEEDS = list(range(200))
NMS_GAPS = [10, 20, 30, 60]  # in anchor_index units (10s steps)
BLOCK_SIZES = [150, 300, 600]
LAMBDAS = [0.25, 0.5, 1.0, 2.0]

proxy_arr = {c: df[c].astype(float).to_numpy() for c in PROXY_COLS}


def build_pool_tiebreak(score_col: str, P: float, B: int) -> np.ndarray:
    """Top P*B by (proxy desc, anchor_index asc). Returns row-indices."""
    pool_size = min(int(math.ceil(P * B)), n)
    s = proxy_arr[score_col]
    # lexsort: last key is primary -> primary = -s, secondary = anchor_idx
    order = np.lexsort((anchor_idx, -s))[:pool_size]
    return order


def linspace_select(pool_idx: np.ndarray, B: int) -> list[int]:
    part_aidx = anchor_idx[pool_idx]
    sort_o = np.argsort(part_aidx, kind="mergesort")
    pool_sorted = pool_idx[sort_o]
    if B >= len(pool_sorted):
        return pool_sorted.tolist()
    picks_pos = sorted(set(int(i * len(pool_sorted) / B) for i in range(B)))
    while len(picks_pos) < B:
        for j2 in range(len(pool_sorted)):
            if j2 not in picks_pos:
                picks_pos.append(j2)
                break
    return pool_sorted[picks_pos[:B]].tolist()


def greedy_maxmin_select(pool_idx: np.ndarray, B: int, score_col: str) -> list[int]:
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    s = proxy_arr[score_col][pool_idx]
    times = anchor_idx[pool_idx].astype(float)
    # start with highest proxy (pool already sorted by -s, anchor_idx asc)
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
    return [pool_idx[p] for p in chosen_pos]


def temporal_nms_select(pool_idx: np.ndarray, B: int, score_col: str, gap: float) -> list[int]:
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    # pool already sorted by -s, anchor_idx asc
    times = anchor_idx[pool_idx].astype(float)
    suppressed = np.zeros(len(pool_idx), dtype=bool)
    chosen = []
    for i in range(len(pool_idx)):
        if suppressed[i]:
            continue
        chosen.append(int(pool_idx[i]))
        if len(chosen) >= B:
            break
        for j in range(i + 1, len(pool_idx)):
            if not suppressed[j] and abs(times[j] - times[i]) <= gap:
                suppressed[j] = True
    if len(chosen) < B:
        for i in range(len(pool_idx)):
            if not suppressed[i] and int(pool_idx[i]) not in chosen:
                chosen.append(int(pool_idx[i]))
                if len(chosen) >= B:
                    break
    return chosen[:B]


def block_round_robin_select(pool_idx: np.ndarray, B: int, score_col: str, block_size: float) -> list[int]:
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    pool_aid = aids[pool_idx]
    pool_s = proxy_arr[score_col][pool_idx]
    pool_ct = center_t[pool_idx]
    pool_blocks = (pool_ct // block_size).astype(int)
    block_ids = sorted(np.unique(pool_blocks))
    chosen = []
    chosen_set = set()
    progressed = True
    while len(chosen) < B and progressed:
        progressed = False
        for b in block_ids:
            if len(chosen) >= B:
                break
            mask = (pool_blocks == b) & np.array([aid not in chosen_set for aid in pool_aid])
            if not mask.any():
                continue
            best = int(np.argmax(np.where(mask, pool_s, -1e18)))
            chosen.append(int(pool_idx[best]))
            chosen_set.add(pool_aid[best])
            progressed = True
    return chosen[:B]


def random_from_pool_select(pool_idx: np.ndarray, B: int, rng: np.random.Generator) -> list[int]:
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    pick = rng.choice(pool_idx, size=B, replace=False)
    return pick.tolist()


def score_weighted_select(pool_idx: np.ndarray, B: int, score_col: str, lam: float) -> list[int]:
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    s = proxy_arr[score_col][pool_idx]
    if np.all(np.isnan(s)):
        norm_s = np.zeros(len(s))
    else:
        s_min, s_max = np.nanmin(s), np.nanmax(s)
        norm_s = (s - s_min) / (s_max - s_min) if s_max > s_min else np.zeros_like(s)
        norm_s = np.nan_to_num(norm_s, nan=0.0)
    times = anchor_idx[pool_idx].astype(float)
    span = max(1.0, times.max() - times.min())
    first = int(np.argmax(norm_s))
    chosen = [first]
    available = np.ones(len(times), dtype=bool)
    available[first] = False
    chosen_times = np.array([times[first]])
    while len(chosen) < B and available.any():
        diffs = np.abs(times[:, None] - chosen_times[None, :])
        min_d = diffs.min(axis=1) / span
        score = norm_s + lam * min_d
        score[~available] = -1e18
        best = int(np.argmax(score))
        if not available[best]:
            break
        chosen.append(best)
        chosen_times = np.append(chosen_times, times[best])
        available[best] = False
    return [pool_idx[p] for p in chosen]


def idx_to_ids(idxs) -> list[str]:
    return [aids[i] for i in idxs]


rows: list[dict] = []
t0 = time.time()

for col in PROXY_COLS:
    for P in P_VALUES:
        for B in BUDGETS:
            pool_idx = build_pool_tiebreak(col, P, B)
            configs = []
            configs.append(("linspace_spread", "linspace_spread", linspace_select(pool_idx, B)))
            configs.append(("greedy_maxmin_time", "greedy_maxmin_time", greedy_maxmin_select(pool_idx, B, col)))
            for gap in NMS_GAPS:
                configs.append((f"temporal_nms_gap{gap}", f"temporal_nms_gap{gap}", temporal_nms_select(pool_idx, B, col, gap)))
            for bs in BLOCK_SIZES:
                configs.append((f"block_round_robin_bs{bs}", f"block_round_robin_bs{bs}", block_round_robin_select(pool_idx, B, col, bs)))
            for lam in LAMBDAS:
                configs.append((f"score_weighted_spread_lam{lam}", f"score_weighted_spread_lam{lam}", score_weighted_select(pool_idx, B, col, lam)))
            # random_from_pool (200 seeds)
            for seed in RAND_SEEDS:
                rng = np.random.default_rng(70_000 + seed + B + int(P * 100))
                sel = random_from_pool_select(pool_idx, B, rng)
                method = f"random_from_pool"
                ev = C.evaluate(df, idx_to_ids(sel), f"{method}__P{P}__{col}", B, seed, selected_proxy=col)
                rows.append({**ev, "proxy": col, "P": P, "temporal_strategy": "random_from_pool", "lambda": "", "gap": "", "block_size": ""})
                if seed < 10:
                    C.save_selection(C.selection_frame(df, idx_to_ids(sel), f"random_from_pool__P{P}__{col}", B, seed, {aid: "random_from_pool" for aid in idx_to_ids(sel)}, proxy=col, P=P, temporal_strategy="random_from_pool"), C.SEL_DIV, f"random_from_pool__P{P}__{col}", B, seed)
            for name, strat, sel in configs:
                method = f"diversity__{strat}"
                ev = C.evaluate(df, idx_to_ids(sel), f"diversity__{strat}__P{P}__{col}", B, "deterministic", selected_proxy=col)
                rows.append({**ev, "proxy": col, "P": P, "temporal_strategy": name, "lambda": "", "gap": "", "block_size": ""})
                C.save_selection(C.selection_frame(df, idx_to_ids(sel), f"diversity__{strat}__P{P}__{col}", B, "deterministic", {aid: strat for aid in idx_to_ids(sel)}, proxy=col, P=P, temporal_strategy=name), C.SEL_DIV, f"diversity__{strat}__P{P}__{col}", B, "deterministic")

long = pd.DataFrame(rows)
long.to_csv(C.REPLAY / "diversity_ablation_long.csv", index=False)
print(f"Task C selections done in {time.time()-t0:.1f}s; {len(long)} rows")

# --- Summary ---
metric_cols = [
    "n_selected", "anchor_recall", "event_cluster_recall", "singleton_cluster_recall",
    "multi_anchor_cluster_recall", "precision", "positives_found",
    "redundancy_rate", "block_coverage", "temporal_span", "avg_nn_time_gap",
]
summary_rows = []
# group by proxy, P, temporal_strategy, budget
for (proxy, P, strat, B), part in long.groupby(["proxy", "P", "temporal_strategy", "budget"]):
    row = {"proxy": proxy, "P": P, "temporal_strategy": strat, "budget": B, "n_runs": len(part)}
    for m in metric_cols:
        vals = part[m].astype(float).tolist()
        row[f"{m}_mean"] = float(np.mean(vals)) if vals else float("nan")
        row[f"{m}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        row[f"{m}_ci95"] = C.ci95(vals)
    summary_rows.append(row)
summary = pd.DataFrame(summary_rows)
summary.to_csv(C.REPLAY / "diversity_ablation_summary.csv", index=False)

# --- Best by budget ---
best_rows = []
for B in BUDGETS:
    part = summary[summary["budget"] == B]
    best = part.sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).head(1)
    if not best.empty:
        best_rows.append(best.iloc[0])
    # also best deterministic (exclude random_from_pool)
    det = part[part["temporal_strategy"] != "random_from_pool"]
    best_det = det.sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).head(1)
    if not best_det.empty:
        best_rows.append(best_det.iloc[0])
best_df = pd.DataFrame(best_rows)
best_df.to_csv(C.TABLES / "diversity_ablation_best_by_budget.csv", index=False)

# --- Factor effects (marginal means) ---
factor_rows = []
# effect of P (marginalize over proxy, strategy, budget)
for P in P_VALUES:
    part = summary[summary["P"] == P]
    factor_rows.append({"factor": "P", "level": P, "mean_event_recall": float(part["event_cluster_recall_mean"].mean()), "mean_anchor_recall": float(part["anchor_recall_mean"].mean()), "mean_singleton_recall": float(part["singleton_cluster_recall_mean"].mean())})
for col in PROXY_COLS:
    part = summary[summary["proxy"] == col]
    factor_rows.append({"factor": "proxy", "level": col, "mean_event_recall": float(part["event_cluster_recall_mean"].mean()), "mean_anchor_recall": float(part["anchor_recall_mean"].mean()), "mean_singleton_recall": float(part["singleton_cluster_recall_mean"].mean())})
strats = sorted(summary["temporal_strategy"].unique())
for strat in strats:
    part = summary[summary["temporal_strategy"] == strat]
    factor_rows.append({"factor": "temporal_strategy", "level": strat, "mean_event_recall": float(part["event_cluster_recall_mean"].mean()), "mean_anchor_recall": float(part["anchor_recall_mean"].mean()), "mean_singleton_recall": float(part["singleton_cluster_recall_mean"].mean())})
factor_df = pd.DataFrame(factor_rows)
factor_df.to_csv(C.TABLES / "diversity_ablation_factor_effects.csv", index=False)

print(f"Task C total: {time.time()-t0:.1f}s; long={len(long)} summary={len(summary)}")
print("Task C done.")
