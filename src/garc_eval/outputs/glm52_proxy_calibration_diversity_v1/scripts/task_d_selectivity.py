#!/usr/bin/env python3
"""Task D: Selectivity diagnostic.

6.1 Block-level selectivity: classify time blocks as hot/medium/cold by positive rate,
    measure budget share and recall per block type for representative methods.
6.2 Query-level selectivity: build sub-queries by involved_object (pedestrian/cyclist/vehicle/
    non_vehicle), recompute proxy metrics and replay per sub-query.

No new VLM/LLM/YOLO/CLIP.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

import common as C

C.ensure_dirs()
df = C.load_data()
aids = df["anchor_id"].astype(str).to_numpy()
labels = df["is_positive"].astype(int).to_numpy()
anchor_idx = df["anchor_index"].astype(int).to_numpy()
center_t = df["center_time_s"].astype(float).to_numpy()
n = len(df)
total_pos = int(labels.sum())
proxy_cols = C.detect_proxy_cols(df)
inv_obj = df["involved_object"].astype(str).to_numpy()


# ---------------------------------------------------------------------------
# 6.1 Block-level selectivity
# ---------------------------------------------------------------------------


def block_classify(block_size: float) -> pd.DataFrame:
    blocks = (center_t // block_size).astype(int)
    rows = []
    for b in sorted(np.unique(blocks)):
        mask = blocks == b
        n_b = int(mask.sum())
        pos_b = int(labels[mask].sum())
        rate = pos_b / n_b if n_b else 0.0
        if rate >= 0.20:
            cls = "hot"
        elif rate >= 0.05:
            cls = "medium"
        else:
            cls = "cold"
        rows.append({"block_id": int(b), "block_size": int(block_size), "n_anchors": n_b, "n_positives": pos_b, "positive_rate": rate, "selectivity_class": cls})
    return pd.DataFrame(rows), blocks


def select_method(method: str, B: int, seed: int = 0) -> list[int]:
    """Return row-indices for a representative method."""
    if method == "uniform_random":
        rng = np.random.default_rng(seed)
        return rng.choice(n, size=min(B, n), replace=False).tolist()
    if method == "uniform_temporal_grid":
        order = np.argsort(anchor_idx, kind="mergesort")
        if B >= n:
            return order.tolist()
        picks = sorted(set(int(i * n / B) for i in range(B)))
        while len(picks) < B:
            for j2 in range(n):
                if j2 not in picks:
                    picks.append(j2)
                    break
        return order[picks[:B]].tolist()
    col_map = {
        "top_proxy_object_count_mean": "object_count_mean",
        "diversity_prefilter_object_count_mean": "object_count_mean",
        "best_calibration_selected_diversity": "person_count_mean",
    }
    col = col_map[method]
    s = df[col].astype(float).to_numpy()
    if method.startswith("top_proxy"):
        return np.lexsort((anchor_idx, -s))[:B].tolist()
    # diversity prefilter P=2.0, greedy_maxmin (best from Task C)
    pool_size = min(int(math.ceil(2.0 * B)), n)
    pool = np.lexsort((anchor_idx, -s))[:pool_size]
    pool_aidx = anchor_idx[pool]
    sort_o = np.argsort(pool_aidx, kind="mergesort")
    pool_sorted = pool[sort_o]
    if method == "diversity_prefilter_object_count_mean":
        if B >= len(pool_sorted):
            return pool_sorted.tolist()
        picks = sorted(set(int(i * len(pool_sorted) / B) for i in range(B)))
        while len(picks) < B:
            for j2 in range(len(pool_sorted)):
                if j2 not in picks:
                    picks.append(j2)
                    break
        return pool_sorted[picks[:B]].tolist()
    # best_calibration: greedy_maxmin
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


block_diag_rows = []
block_summary_rows = []
for bs in [150, 300, 600]:
    bdf, blocks = block_classify(bs)
    bdf.to_csv(C.ANALYSIS / f"block_selectivity_blocks_bs{bs}.csv", index=False)
    # class distribution
    for cls in ["hot", "medium", "cold"]:
        cb = bdf[bdf["selectivity_class"] == cls]
        block_summary_rows.append({"block_size": bs, "selectivity_class": cls, "n_blocks": len(cb), "n_anchors": int(cb["n_anchors"].sum()), "n_positives": int(cb["n_positives"].sum()), "mean_positive_rate": float(cb["positive_rate"].mean()) if len(cb) else 0.0})
    # per-method block share & recall
    methods = ["top_proxy_object_count_mean", "diversity_prefilter_object_count_mean", "best_calibration_selected_diversity", "uniform_temporal_grid", "uniform_random"]
    for B in [40, 80, 150]:
        for method in methods:
            seeds = range(50) if method == "uniform_random" else [0]
            for seed in seeds:
                sel = select_method(method, B, seed)
                sel_blocks = blocks[sel]
                sel_pos = labels[sel]
                for cls in ["hot", "medium", "cold"]:
                    cls_blocks = set(bdf[bdf["selectivity_class"] == cls]["block_id"])
                    cls_mask = np.isin(blocks, list(cls_blocks))
                    cls_total_pos = int(labels[cls_mask].sum())
                    sel_in_cls = np.isin(sel_blocks, list(cls_blocks))
                    budget_share = float(sel_in_cls.sum() / max(1, len(sel)))
                    pos_in_cls = int((sel_pos * sel_in_cls).sum())
                    recall_in_cls = float(pos_in_cls / cls_total_pos) if cls_total_pos else 0.0
                    # singleton recall in cold blocks
                    singleton_cls_pos = int(((df["is_singleton_cluster"].to_numpy()) & cls_mask & (labels == 1)).sum())
                    singleton_sel_cls = int(((df["is_singleton_cluster"].to_numpy()[sel]) & np.isin(sel_blocks, list(cls_blocks)) & (sel_pos == 1)).sum())
                    block_diag_rows.append({
                        "block_size": bs, "selectivity_class": cls, "method": method, "budget": B, "seed": seed,
                        "budget_share": budget_share, "positives_found_in_cls": pos_in_cls,
                        "recall_in_cls": recall_in_cls, "cls_total_positives": cls_total_pos,
                        "singleton_recall_in_cls": float(singleton_sel_cls / max(1, singleton_cls_pos)) if singleton_cls_pos else 0.0,
                    })

block_diag = pd.DataFrame(block_diag_rows)
# average over seeds for uniform_random
agg = block_diag.groupby(["block_size", "selectivity_class", "method", "budget"]).agg(
    budget_share=("budget_share", "mean"), positives_found_in_cls=("positives_found_in_cls", "mean"),
    recall_in_cls=("recall_in_cls", "mean"), singleton_recall_in_cls=("singleton_recall_in_cls", "mean"),
).reset_index()
block_diag.to_csv(C.ANALYSIS / "block_selectivity_diagnostic.csv", index=False)
agg.to_csv(C.ANALYSIS / "block_selectivity_diagnostic_agg.csv", index=False)
block_summary = pd.DataFrame(block_summary_rows)
block_summary.to_csv(C.TABLES / "block_selectivity_summary.csv", index=False)


# ---------------------------------------------------------------------------
# 6.2 Query-level selectivity
# ---------------------------------------------------------------------------

# Build sub-query positive masks (oracle-defined).
# all_event: all 40 positives. pedestrian/cyclist/vehicle/non_vehicle by involved_object.
inv_obj_arr = df["involved_object"].astype(str).to_numpy()
queries = {
    "all_event": labels.astype(bool),
    "pedestrian_event": (inv_obj_arr == "pedestrian") & labels.astype(bool),
    "cyclist_event": (inv_obj_arr == "cyclist") & labels.astype(bool),
    "vehicle_event": (inv_obj_arr == "vehicle") & labels.astype(bool),
    "non_vehicle_event": ((inv_obj_arr == "pedestrian") | (inv_obj_arr == "cyclist")) & labels.astype(bool),
}


def fast_auroc(s: np.ndarray, y: np.ndarray) -> float:
    mask = ~np.isnan(s)
    s2 = s[mask]
    y2 = y[mask]
    n_pos = int(y2.sum())
    n_neg = len(y2) - n_pos
    if n_pos == 0 or n_neg == 0:
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


# Per-query proxy metrics
proxy_metric_rows = []
test_proxies = ["object_count_mean", "person_count_max", "person_count_mean", "vehicle_count_mean", "bike_count_mean", "motion_energy_mean", "score_fusion_geometry_motion", "lateral_presence_max"]
test_proxies = [c for c in test_proxies if c in df.columns and df[c].notna().any()]
for qname, qmask in queries.items():
    y = qmask.astype(int)
    for col in test_proxies:
        s = df[col].astype(float).to_numpy()
        proxy_metric_rows.append({"query": qname, "proxy": col, "n_positives": int(y.sum()), "auroc": fast_auroc(s, y), "auprc": fast_ap(s, y)})
proxy_metrics_q = pd.DataFrame(proxy_metric_rows)
proxy_metrics_q.to_csv(C.ANALYSIS / "query_selectivity_proxy_metrics.csv", index=False)

# Per-query replay: top_proxy and diversity_prefilter for best deployable proxy + person proxies
replay_rows = []
for qname, qmask in queries.items():
    y = qmask.astype(int)
    total_q = int(y.sum())
    if total_q == 0:
        continue
    # best proxy by AUROC on this query (hindsight)
    qm = proxy_metrics_q[proxy_metrics_q["query"] == qname].dropna(subset=["auroc"])
    best_proxy_q = qm.sort_values("auroc", ascending=False).iloc[0]["proxy"] if not qm.empty else "object_count_mean"
    for B in [40, 80, 150]:
        for col in ["object_count_mean", "person_count_max", "person_count_mean", best_proxy_q]:
            if col not in df.columns:
                continue
            s = df[col].astype(float).to_numpy()
            # top_proxy
            sel = np.lexsort((anchor_idx, -s))[:B]
            sel_pos = int(y[sel].sum())
            replay_rows.append({"query": qname, "method": f"top_proxy_{col}", "proxy": col, "budget": B, "positives_found": sel_pos, "recall": float(sel_pos / total_q), "is_hindsight": int(col in {"person_count_max", "person_count_mean"} or col == best_proxy_q)})
            # diversity prefilter P=2.0 greedy_maxmin
            pool_size = min(int(math.ceil(2.0 * B)), n)
            pool = np.lexsort((anchor_idx, -s))[:pool_size]
            pool_aidx = anchor_idx[pool]
            sort_o = np.argsort(pool_aidx, kind="mergesort")
            pool_sorted = pool[sort_o]
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
            sel2 = [pool_sorted[p] for p in chosen_pos]
            sel2_pos = int(y[sel2].sum())
            replay_rows.append({"query": qname, "method": f"diversity_prefilter_{col}", "proxy": col, "budget": B, "positives_found": sel2_pos, "recall": float(sel2_pos / total_q), "is_hindsight": int(col in {"person_count_max", "person_count_mean"} or col == best_proxy_q)})

query_replay = pd.DataFrame(replay_rows)
query_replay.to_csv(C.ANALYSIS / "query_selectivity_replay_long.csv", index=False)
# summary: best per query/budget
qsum_rows = []
for (qname, B), part in query_replay.groupby(["query", "budget"]):
    best = part.sort_values("recall", ascending=False).head(1).iloc[0]
    dep = part[part["is_hindsight"] == 0]
    best_dep = dep.sort_values("recall", ascending=False).head(1).iloc[0] if not dep.empty else best
    qsum_rows.append({"query": qname, "budget": B, "best_method": best["method"], "best_recall": best["recall"], "best_proxy": best["proxy"], "best_deployable_method": best_dep["method"], "best_deployable_recall": best_dep["recall"], "best_deployable_proxy": best_dep["proxy"]})
qsum = pd.DataFrame(qsum_rows)
qsum.to_csv(C.ANALYSIS / "query_selectivity_replay_summary.csv", index=False)

print(f"Task D done. block_diag={len(block_diag)} block_summary={len(block_summary)} proxy_metrics_q={len(proxy_metrics_q)} query_replay={len(query_replay)}")
