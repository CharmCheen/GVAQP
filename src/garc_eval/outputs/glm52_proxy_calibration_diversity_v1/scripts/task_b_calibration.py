#!/usr/bin/env python3
"""Task B: Proxy calibration replay (optimized).

Test whether a small calibration set can auto-select an effective cheap proxy,
then run diversity prefilter with the selected proxy. Compare against hindsight
and fixed-proxy baselines.

No new VLM/LLM/YOLO/CLIP. Calibration labels are simulated from the existing
oracle reference. Calibration selection uses a core set of distinct cheap
features; full 38-proxy inventory remains in the audit (Task A).

Note: calibration method uses seeds 0..99 (200 was too slow); random baselines
still use seeds 0..199 per the task spec.
"""
from __future__ import annotations

import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

import common as C

C.ensure_dirs()
df = C.load_data()
all_proxy_cols = C.detect_proxy_cols(df)
deployable_default = "object_count_mean"
hindsight_best = "person_count_max"

# Core distinct proxies for calibration selection (covers task-required set,
# excludes redundant duplicates like yolo_vehicle_mean==vehicle_count_mean).
CORE_CALIB_PROXIES = [
    "score_fusion_geometry_motion",
    "object_count_mean",
    "object_count_max",
    "person_count_mean",
    "person_count_max",
    "bike_count_mean",
    "bike_count_max",
    "vehicle_count_mean",
    "vehicle_count_max",
    "motion_energy_mean",
    "motion_energy_max",
    "near_ego_vehicle_count_mean",
    "near_ego_vehicle_count_max",
    "motorcycle_count_mean",
    "lateral_presence_mean",
    "lateral_presence_max",
    "bbox_cx_std_mean",
    "bbox_cx_std_max",
    "bbox_area_sum_mean",
    "bbox_area_sum_max",
    "center_roi_vehicle_count_mean",
    "bottom_roi_vehicle_count_mean",
    "score_yolo_count",
    "score_motion",
    "score_fusion_yolo_motion",
]
CORE_CALIB_PROXIES = [c for c in CORE_CALIB_PROXIES if c in all_proxy_cols]
print(f"Core calib proxies: {len(CORE_CALIB_PROXIES)}")

aids = df["anchor_id"].astype(str).to_numpy()
labels = df["is_positive"].astype(int).to_numpy()
anchor_idx = df["anchor_index"].astype(int).to_numpy()
center_t = df["center_time_s"].astype(float).to_numpy()
n = len(df)
total_pos = int(labels.sum())
# proxy matrix for core proxies (n x P)
proxy_mat = np.column_stack([df[c].astype(float).to_numpy() for c in CORE_CALIB_PROXIES])
proxy_name_by_j = {j: c for j, c in enumerate(CORE_CALIB_PROXIES)}
proxy_j_by_name = {c: j for j, c in enumerate(CORE_CALIB_PROXIES)}

hindsight_auroc = C.tie_aware_auroc(df[hindsight_best].astype(float).to_numpy(), labels.astype(float))
default_auroc = C.tie_aware_auroc(df[deployable_default].astype(float).to_numpy(), labels.astype(float))
print(f"Hindsight {hindsight_best} AUROC={hindsight_auroc:.4f}; default {deployable_default} AUROC={default_auroc:.4f}")

CALIB_BUDGETS = [5, 10, 15, 20, 30]
CALIB_POLICIES = ["calib_uniform_random", "calib_temporal_grid", "calib_stratified_time_blocks"]
SELECTION_RULES = ["calib_auroc", "calib_auprc", "calib_top_quantile_positive_rate", "calib_topk_yield", "calib_spearman"]
P_DEFAULT = 2.0
CAL_SEEDS = list(range(100))  # 100 seeds for calibration (per task: may reduce to 0..99)
RAND_SEEDS = list(range(200))


def calib_sample(policy: str, c: int, seed: int) -> np.ndarray:
    if policy == "calib_uniform_random":
        rng = np.random.default_rng(seed)
        return rng.choice(n, size=min(c, n), replace=False)
    if policy == "calib_temporal_grid":
        order = np.argsort(anchor_idx, kind="mergesort")
        if c >= n:
            return order
        picks_pos = sorted(set(int(i * n / c) for i in range(c)))
        while len(picks_pos) < c:
            for j2 in range(n):
                if j2 not in picks_pos:
                    picks_pos.append(j2)
                    break
        return order[picks_pos[:c]]
    if policy == "calib_stratified_time_blocks":
        blocks = (center_t // 300).astype(int)
        block_ids = sorted(np.unique(blocks))
        rng = np.random.default_rng(seed)
        per = max(1, c // len(block_ids))
        picks = []
        for b in block_ids:
            members = np.where(blocks == b)[0]
            take = min(per, len(members))
            picks.extend(rng.choice(members, size=take, replace=False).tolist())
        remaining = c - len(picks)
        if remaining > 0:
            pool = np.array([i for i in range(n) if i not in set(picks)])
            picks.extend(rng.choice(pool, size=min(remaining, len(pool)), replace=False).tolist())
        return np.array(picks[:c])
    raise ValueError(policy)


def fast_auroc(s: np.ndarray, y: np.ndarray) -> float:
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    mask = ~np.isnan(s)
    s2 = s[mask]
    y2 = y[mask]
    if len(s2) < 2:
        return float("nan")
    ranks = rankdata(s2, method="average")
    return float((ranks[y2 == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def fast_ap(s: np.ndarray, y: np.ndarray) -> float:
    mask = ~np.isnan(s)
    s2 = s[mask]
    y2 = y[mask]
    n_pos = int(y2.sum())
    if n_pos == 0:
        return float("nan")
    order = np.argsort(-s2, kind="mergesort")
    ys = y2[order]
    tp = np.cumsum(ys)
    prec = tp / np.arange(1, len(ys) + 1)
    return float((prec * ys).sum() / n_pos)


def fast_spearman(s: np.ndarray, y: np.ndarray) -> float:
    mask = ~np.isnan(s)
    s2 = s[mask]
    y2 = y[mask].astype(float)
    if len(s2) < 3 or np.unique(s2).size < 2:
        return float("nan")
    rs = rankdata(s2)
    ry = rankdata(y2)
    rs_c = rs - rs.mean()
    ry_c = ry - ry.mean()
    denom = math.sqrt((rs_c ** 2).sum() * (ry_c ** 2).sum())
    if denom == 0:
        return float("nan")
    return float((rs_c * ry_c).sum() / denom)


def top_quantile_positive_rate(s: np.ndarray, y: np.ndarray) -> float:
    mask = ~np.isnan(s)
    s2 = s[mask]
    y2 = y[mask]
    if len(s2) < 2:
        return float("nan")
    thr = np.quantile(s2, 0.75)
    top = y2[s2 >= thr]
    return float(top.mean()) if len(top) else 0.0


def topk_yield(s: np.ndarray, y: np.ndarray, k: int) -> float:
    mask = ~np.isnan(s)
    s2 = s[mask]
    y2 = y[mask]
    k = min(k, len(s2))
    if k <= 0:
        return float("nan")
    order = np.argsort(-s2, kind="mergesort")[:k]
    return float(y2[order].sum())


def select_proxy_by_rule(rule: str, cal_idx: np.ndarray, exec_size: int) -> tuple[str, bool]:
    cal_labs = labels[cal_idx]
    n_pos_cal = int(cal_labs.sum())
    n_neg_cal = len(cal_labs) - n_pos_cal
    if n_pos_cal == 0 or n_neg_cal == 0:
        return deployable_default, True
    cal_mat = proxy_mat[cal_idx, :]
    best_j = -1
    best_val = -1e18
    for j in range(proxy_mat.shape[1]):
        s = cal_mat[:, j]
        if np.all(np.isnan(s)):
            continue
        if rule == "calib_auroc":
            v = fast_auroc(s, cal_labs)
        elif rule == "calib_auprc":
            v = fast_ap(s, cal_labs)
        elif rule == "calib_top_quantile_positive_rate":
            v = top_quantile_positive_rate(s, cal_labs)
        elif rule == "calib_topk_yield":
            v = topk_yield(s, cal_labs, min(exec_size, len(cal_labs)))
        elif rule == "calib_spearman":
            v = fast_spearman(s, cal_labs)
        else:
            raise ValueError(rule)
        if math.isnan(v):
            continue
        if v > best_val:
            best_val = v
            best_j = j
    if best_j < 0:
        return deployable_default, True
    return proxy_name_by_j[best_j], False


def diversity_prefilter_exec_vec(exec_pool_idx: np.ndarray, proxy_col_idx: int, exec_budget: int, P: float) -> list[int]:
    if exec_budget <= 0 or len(exec_pool_idx) == 0:
        return []
    pool_size = min(int(math.ceil(P * exec_budget)), len(exec_pool_idx))
    s = proxy_mat[exec_pool_idx, proxy_col_idx]
    order = np.argsort(-s, kind="mergesort")[:pool_size]
    pool_idx = exec_pool_idx[order]
    pool_aidx = anchor_idx[pool_idx]
    sort_o = np.argsort(pool_aidx, kind="mergesort")
    pool_sorted = pool_idx[sort_o]
    if exec_budget >= len(pool_sorted):
        return pool_sorted.tolist()
    picks_pos = sorted(set(int(i * len(pool_sorted) / exec_budget) for i in range(exec_budget)))
    while len(picks_pos) < exec_budget:
        for j2 in range(len(pool_sorted)):
            if j2 not in picks_pos:
                picks_pos.append(j2)
                break
    return pool_sorted[picks_pos[:exec_budget]].tolist()


def baseline_top_proxy(B: int, proxy_col_idx: int) -> list[int]:
    s = proxy_mat[:, proxy_col_idx]
    return np.argsort(-s, kind="mergesort")[:B].tolist()


def baseline_diversity_prefilter(B: int, proxy_col_idx: int, P: float = 2.0) -> list[int]:
    pool_size = min(int(math.ceil(P * B)), n)
    s = proxy_mat[:, proxy_col_idx]
    order = np.argsort(-s, kind="mergesort")[:pool_size]
    pool_aidx = anchor_idx[order]
    sort_o = np.argsort(pool_aidx, kind="mergesort")
    pool_sorted = order[sort_o]
    if B >= len(pool_sorted):
        return pool_sorted.tolist()
    picks_pos = sorted(set(int(i * len(pool_sorted) / B) for i in range(B)))
    while len(picks_pos) < B:
        for j2 in range(len(pool_sorted)):
            if j2 not in picks_pos:
                picks_pos.append(j2)
                break
    return pool_sorted[picks_pos[:B]].tolist()


def baseline_diversity_prefilter_anycol(B: int, score_col: str, P: float = 2.0) -> list[int]:
    """Diversity prefilter for any column (not just core proxies)."""
    s = df[score_col].astype(float).to_numpy()
    pool_size = min(int(math.ceil(P * B)), n)
    order = np.argsort(-s, kind="mergesort")[:pool_size]
    pool_aidx = anchor_idx[order]
    sort_o = np.argsort(pool_aidx, kind="mergesort")
    pool_sorted = order[sort_o]
    if B >= len(pool_sorted):
        return pool_sorted.tolist()
    picks_pos = sorted(set(int(i * len(pool_sorted) / B) for i in range(B)))
    while len(picks_pos) < B:
        for j2 in range(len(pool_sorted)):
            if j2 not in picks_pos:
                picks_pos.append(j2)
                break
    return pool_sorted[picks_pos[:B]].tolist()


def baseline_top_proxy_anycol(B: int, score_col: str) -> list[int]:
    s = df[score_col].astype(float).to_numpy()
    return np.argsort(-s, kind="mergesort")[:B].tolist()


def baseline_uniform_temporal_grid(B: int) -> list[int]:
    order = np.argsort(anchor_idx, kind="mergesort")
    if B >= n:
        return order.tolist()
    picks_pos = sorted(set(int(i * n / B) for i in range(B)))
    while len(picks_pos) < B:
        for j2 in range(n):
            if j2 not in picks_pos:
                picks_pos.append(j2)
                break
    return order[picks_pos[:B]].tolist()


def baseline_uniform_random(B: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    return rng.choice(n, size=min(B, n), replace=False).tolist()


def idx_to_ids(idxs) -> list[str]:
    return [aids[i] for i in idxs]


rows: list[dict] = []
proxy_selection_counts: Counter = Counter()
regret_rows: list[dict] = []
t0 = time.time()

# --- Baselines (deterministic) ---
core_j = {c: j for j, c in enumerate(CORE_CALIB_PROXIES)}
for B in C.BUDGETS:
    sel = baseline_uniform_temporal_grid(B)
    ev = C.evaluate(df, idx_to_ids(sel), "uniform_temporal_grid", B, "deterministic")
    rows.append({**ev, "calib_policy": "none", "selection_rule": "none", "c": 0, "fallback": 0, "hindsight": 0})
    C.save_selection(C.selection_frame(df, idx_to_ids(sel), "uniform_temporal_grid", B, "deterministic", {aid: "temporal_grid" for aid in idx_to_ids(sel)}), C.SEL_CAL, "uniform_temporal_grid", B, "deterministic")

    for name, col, kind in [
        ("top_proxy_score_fusion_geometry_motion", "score_fusion_geometry_motion", "top"),
        ("diversity_prefilter_score_fusion_geometry_motion", "score_fusion_geometry_motion", "diversity"),
        ("top_proxy_object_count_mean", "object_count_mean", "top"),
        ("diversity_prefilter_object_count_mean", "object_count_mean", "diversity"),
        ("top_proxy_person_count_max_hindsight", "person_count_max", "top"),
        ("diversity_prefilter_person_count_max_hindsight", "person_count_max", "diversity"),
    ]:
        if kind == "top":
            sel = baseline_top_proxy_anycol(B, col)
        else:
            sel = baseline_diversity_prefilter_anycol(B, col)
        ev = C.evaluate(df, idx_to_ids(sel), name, B, "deterministic", selected_proxy=col)
        hindsight_flag = 1 if "hindsight" in name else 0
        rows.append({**ev, "calib_policy": "none", "selection_rule": "none", "c": 0, "fallback": 0, "hindsight": hindsight_flag})
        role = "proxy_ranked" if kind == "top" else "top_2B_temporal_spread"
        C.save_selection(C.selection_frame(df, idx_to_ids(sel), name, B, "deterministic", {aid: role for aid in idx_to_ids(sel)}, hindsight=bool(hindsight_flag)), C.SEL_CAL, name, B, "deterministic")

# --- Baselines (random) ---
for B in C.BUDGETS:
    for seed in RAND_SEEDS:
        sel = baseline_uniform_random(B, seed)
        ev = C.evaluate(df, idx_to_ids(sel), "uniform_random", B, seed)
        rows.append({**ev, "calib_policy": "none", "selection_rule": "none", "c": 0, "fallback": 0, "hindsight": 0})
        if seed < 20:
            C.save_selection(C.selection_frame(df, idx_to_ids(sel), "uniform_random", B, seed, {aid: "uniform_random" for aid in idx_to_ids(sel)}), C.SEL_CAL, "uniform_random", B, seed)

# random_proxy_selected_diversity_prefilter
for B in C.BUDGETS:
    for seed in RAND_SEEDS:
        rng = np.random.default_rng(50_000 + seed + B)
        col = CORE_CALIB_PROXIES[int(rng.integers(0, len(CORE_CALIB_PROXIES)))]
        sel = baseline_diversity_prefilter_anycol(B, col)
        ev = C.evaluate(df, idx_to_ids(sel), "random_proxy_selected_diversity_prefilter", B, seed, selected_proxy=col)
        rows.append({**ev, "calib_policy": "none", "selection_rule": "random_proxy", "c": 0, "fallback": 0, "hindsight": 0})
        if seed < 20:
            C.save_selection(C.selection_frame(df, idx_to_ids(sel), "random_proxy_selected_diversity_prefilter", B, seed, {aid: "top_2B_temporal_spread" for aid in idx_to_ids(sel)}), C.SEL_CAL, "random_proxy_selected_diversity_prefilter", B, seed)

print(f"Baselines done in {time.time()-t0:.1f}s; {len(rows)} rows")

# --- Calibration-selected diversity prefilter ---
t1 = time.time()
calib_run_count = 0
method = "calibration_selected_diversity_prefilter"
for B in C.BUDGETS:
    for c in CALIB_BUDGETS:
        if c >= B:
            continue
        exec_size = B - c
        for policy in CALIB_POLICIES:
            for rule in SELECTION_RULES:
                for seed in CAL_SEEDS:
                    cal_idx = calib_sample(policy, c, seed)
                    chosen_proxy, fallback = select_proxy_by_rule(rule, cal_idx, exec_size)
                    pj = proxy_j_by_name[chosen_proxy]
                    mask = np.ones(n, dtype=bool)
                    mask[cal_idx] = False
                    exec_pool_idx = np.where(mask)[0]
                    exec_idx = diversity_prefilter_exec_vec(exec_pool_idx, pj, exec_size, P_DEFAULT)
                    all_idx = list(cal_idx) + list(exec_idx)
                    cal_pos = int(labels[cal_idx].sum())
                    exec_pos = int(labels[exec_idx].sum())
                    sel_ids = idx_to_ids(all_idx)
                    role_by_id = {aids[i]: "calibration" for i in cal_idx}
                    role_by_id.update({aids[i]: "diversity_prefilter_exec" for i in exec_idx})
                    ev = C.evaluate(
                        df, sel_ids, method, B, seed, role_by_id=role_by_id,
                        selected_proxy=chosen_proxy, calibration_positives=cal_pos,
                        execution_positives=exec_pos, cal_size=c, exec_size=exec_size,
                    )
                    rows.append({**ev, "calib_policy": policy, "selection_rule": rule, "c": c, "fallback": int(fallback), "hindsight": 0})
                    proxy_selection_counts[(policy, rule, c, chosen_proxy)] += 1
                    calib_run_count += 1
                    if seed < 5:
                        C.save_selection(C.selection_frame(df, sel_ids, method, B, seed, role_by_id, selected_proxy=chosen_proxy, calib_policy=policy, selection_rule=rule, c=c, fallback=int(fallback)), C.SEL_CAL, f"{method}__{policy}__{rule}__c{c}", B, seed)

print(f"Calibration runs done in {time.time()-t1:.1f}s; {calib_run_count} runs")

long = pd.DataFrame(rows)
long.to_csv(C.REPLAY / "proxy_calibration_replay_long.csv", index=False)

# --- Summary ---
metric_cols = [
    "n_selected", "anchor_recall", "event_cluster_recall", "singleton_cluster_recall",
    "multi_anchor_cluster_recall", "precision", "positives_found",
    "redundancy_rate", "block_coverage", "temporal_span", "avg_nn_time_gap",
]
summary_rows = []
for (mname, B), part in long.groupby(["method", "budget"]):
    row = {"method": mname, "budget": B, "n_runs": len(part)}
    for m in metric_cols:
        vals = part[m].astype(float).tolist()
        row[f"{m}_mean"] = float(np.mean(vals)) if vals else float("nan")
        row[f"{m}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        row[f"{m}_ci95"] = C.ci95(vals)
    summary_rows.append(row)

cal_mask = long["method"] == method
cal_long = long[cal_mask].copy()
cal_long["c"] = cal_long["c"].astype(int)
for (mname, B, c, policy, rule), part in cal_long.groupby(["method", "budget", "c", "calib_policy", "selection_rule"]):
    row = {"method": mname, "budget": B, "c": c, "calib_policy": policy, "selection_rule": rule, "n_runs": len(part)}
    for m in metric_cols:
        vals = part[m].astype(float).tolist()
        row[f"{m}_mean"] = float(np.mean(vals)) if vals else float("nan")
        row[f"{m}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        row[f"{m}_ci95"] = C.ci95(vals)
    pc = Counter(part["selected_proxy"].tolist())
    row["top_selected_proxy"] = pc.most_common(1)[0][0] if pc else ""
    row["top_proxy_freq"] = pc.most_common(1)[0][1] if pc else 0
    row["fallback_rate"] = float(part["fallback"].astype(int).mean()) if "fallback" in part.columns else float("nan")
    summary_rows.append(row)

summary = pd.DataFrame(summary_rows)
summary.to_csv(C.REPLAY / "proxy_calibration_replay_summary.csv", index=False)

# --- Proxy selection frequency ---
freq_rows = []
for (policy, rule, c, proxy), cnt in sorted(proxy_selection_counts.items()):
    freq_rows.append({"calib_policy": policy, "selection_rule": rule, "c": c, "selected_proxy": proxy, "count": cnt})
freq = pd.DataFrame(freq_rows).sort_values(["calib_policy", "selection_rule", "c", "count"], ascending=[True, True, True, False])
freq.to_csv(C.TABLES / "proxy_selection_frequency.csv", index=False)

# --- Regret ---
base_for_regret = {}
for B in C.BUDGETS:
    for name, col in [("diversity_prefilter_person_count_max_hindsight", "person_count_max"), ("diversity_prefilter_object_count_mean", "object_count_mean")]:
        sel = baseline_diversity_prefilter_anycol(B, col)
        ev = C.evaluate(df, idx_to_ids(sel), name, B, "deterministic", selected_proxy=col)
        base_for_regret[(B, name)] = ev["event_cluster_recall"]

for (B, c, policy, rule), part in cal_long.groupby(["budget", "c", "calib_policy", "selection_rule"]):
    mean_er = float(part["event_cluster_recall"].mean())
    mean_ar = float(part["anchor_recall"].mean())
    hindsight_er = base_for_regret.get((B, "diversity_prefilter_person_count_max_hindsight"), float("nan"))
    default_er = base_for_regret.get((B, "diversity_prefilter_object_count_mean"), float("nan"))
    regret_rows.append({
        "budget": B, "c": int(c), "calib_policy": policy, "selection_rule": rule,
        "mean_event_cluster_recall": mean_er, "mean_anchor_recall": mean_ar,
        "hindsight_best_event_recall": hindsight_er, "default_event_recall": default_er,
        "regret_vs_hindsight": hindsight_er - mean_er, "regret_vs_default": default_er - mean_er,
    })
regret = pd.DataFrame(regret_rows)
regret.to_csv(C.TABLES / "proxy_calibration_regret.csv", index=False)

print(f"Task B total: {time.time()-t0:.1f}s; long={len(long)} summary={len(summary)} regret={len(regret)}")
print("Task B done.")
