#!/usr/bin/env python3
"""Shared utilities for GLM-5.2 proxy calibration + diversity experiments.

No VLM/LLM/YOLO/CLIP/video processing. Reads only the canonical per-anchor
table from codex_recompute_proxy_budget_basa_v1 and writes outputs under
garc_eval/outputs/glm52_proxy_calibration_diversity_v1.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "garc_eval/outputs/glm52_proxy_calibration_diversity_v1"
TABLES = OUT / "tables"
REPLAY = OUT / "replay"
ANALYSIS = OUT / "analysis"
FIGURES = OUT / "figures"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
STATE = OUT / "state"
SEL_CAL = REPLAY / "selections" / "proxy_calibration"
SEL_DIV = REPLAY / "selections" / "diversity_ablation"
CANONICAL = ROOT / "garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv"

BUDGETS = [20, 30, 40, 60, 80, 100, 150]
SEEDS = list(range(200))

# Candidate proxy columns requested by the task spec (presence auto-detected).
CANDIDATE_PROXY_COLS = [
    "score_fusion_geometry_motion",
    "score_fusion",
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
    "near_ego_object_count_mean",
    "near_ego_object_count_max",
    "near_ego_vehicle_count_mean",
    "near_ego_vehicle_count_max",
    "bicycle_count_mean",
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
    "score_yolo_geometry",
    "score_motion",
    "score_fusion_yolo_motion",
    "score_fusion_ego_lateral",
    "yolo_vehicle_mean",
    "yolo_vehicle_max",
    "yolo_vehicle_sum",
    "max_bbox_area_mean",
    "max_bbox_area_max",
]

# Columns that must never be treated as proxies.
NON_PROXY_COLS = {
    "anchor_id", "anchor_index", "center_time_s", "start_time_s", "end_time_s",
    "oracle_label", "is_positive", "event_cluster_id", "is_singleton_cluster",
    "is_multi_anchor_cluster", "p1_reused", "source_label_file",
    "video_id_oracle", "anchor_time_oracle", "start_time_oracle", "end_time_oracle",
    "duration_oracle", "label", "event_start", "event_end",
    "event_start_absolute", "event_end_absolute", "event_type", "involved_object",
    "ego_relevant", "boundary_status", "complete_event_visible", "confidence",
    "evidence", "negative_reason", "abstain_reason", "runtime_seconds",
    "raw_response_path", "parse_status", "boundary_reliable", "video_id",
    "anchor_time", "start_time", "end_time", "duration", "source_video_path",
    "construction_policy", "num_overlapping_5s_clips", "notes",
}


def ensure_dirs() -> None:
    for d in [TABLES, REPLAY, ANALYSIS, FIGURES, REPORTS, LOGS, STATE, SEL_CAL, SEL_DIV]:
        d.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    df = pd.read_csv(CANONICAL)
    df["is_positive"] = df["is_positive"].astype(str).str.lower().eq("true")
    df["is_singleton_cluster"] = df["is_singleton_cluster"].astype(str).str.lower().eq("true")
    df["is_multi_anchor_cluster"] = df["is_multi_anchor_cluster"].astype(str).str.lower().eq("true")
    return df.sort_values("anchor_index").reset_index(drop=True)


def detect_proxy_cols(df: pd.DataFrame) -> list[str]:
    """Auto-detect usable numeric proxy columns from the canonical table."""
    cols = []
    seen = set()
    exclude_prefix = ("z_corrected_", "minmax_", "rankpct_")
    for c in CANDIDATE_PROXY_COLS:
        if c in df.columns and c not in seen and pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
            seen.add(c)
    for c in df.columns:
        if c in seen or c in NON_PROXY_COLS or c.startswith(exclude_prefix):
            continue
        if pd.api.types.is_numeric_dtype(df[c]) and any(
            k in c for k in ["score", "count", "energy", "bbox", "presence", "vehicle", "person", "bike", "bicycle", "motion", "lateral"]
        ):
            cols.append(c)
            seen.add(c)
    return cols


def tie_aware_auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    valid = ~np.isnan(scores) & ~np.isnan(labels)
    s = scores[valid].astype(float)
    y = labels[valid].astype(int)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(s, method="average")
    rank_sum_pos = ranks[y == 1].sum()
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def average_precision(scores: np.ndarray, labels: np.ndarray) -> float:
    valid = ~np.isnan(scores) & ~np.isnan(labels)
    s = scores[valid].astype(float)
    y = labels[valid].astype(int)
    n_pos = int(y.sum())
    if n_pos == 0:
        return float("nan")
    order = np.argsort(-s, kind="mergesort")
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    ranks = np.arange(1, len(y_sorted) + 1)
    precisions = tp / ranks
    return float((precisions * y_sorted).sum() / n_pos)


def spearman_corr(scores: np.ndarray, labels: np.ndarray) -> float:
    valid = ~np.isnan(scores) & ~np.isnan(labels)
    s = scores[valid].astype(float)
    y = labels[valid].astype(float)
    if len(s) < 3 or np.unique(s).size < 2:
        return float("nan")
    rs = s.argsort().argsort().astype(float)
    ry = y.argsort().argsort().astype(float)
    rs_c = rs - rs.mean()
    ry_c = ry - ry.mean()
    denom = math.sqrt((rs_c ** 2).sum() * (ry_c ** 2).sum())
    if denom == 0:
        return float("nan")
    return float((rs_c * ry_c).sum() / denom)


def ci95(values: list[float] | np.ndarray) -> float:
    vals = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    if len(vals) <= 1:
        return 0.0
    return float(1.96 * np.std(vals, ddof=1) / math.sqrt(len(vals)))


def pos_clusters(df: pd.DataFrame) -> dict[int, set[str]]:
    clusters = {}
    for cid, part in df[df["event_cluster_id"] >= 0].groupby("event_cluster_id"):
        clusters[int(cid)] = set(part["anchor_id"])
    return clusters


# ---------------------------------------------------------------------------
# Temporal selection strategies. All operate on a candidate pool (DataFrame
# subset already filtered to the top-PB proxy candidates) and return a list of
# anchor_ids of length n (or fewer if the pool is smaller).
# ---------------------------------------------------------------------------


def _by_index_order(pool: pd.DataFrame) -> pd.DataFrame:
    return pool.sort_values("anchor_index").reset_index(drop=True)


def linspace_spread(pool: pd.DataFrame, n: int, score_col: str | None = None) -> list[str]:
    """Current corrected method: top-PB then sort by anchor_index, uniformly take n."""
    part = _by_index_order(pool)
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return part["anchor_id"].tolist()
    idx = sorted(set(int(i * len(part) / n) for i in range(n)))
    j = 0
    while len(idx) < n:
        for j2 in range(len(part)):
            if j2 not in idx:
                idx.append(j2)
                break
    return part.iloc[idx[:n]]["anchor_id"].tolist()


def greedy_maxmin_time(pool: pd.DataFrame, n: int, score_col: str) -> list[str]:
    part = pool.copy()
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return _by_index_order(part)["anchor_id"].tolist()
    # Start from highest proxy score.
    order = part.sort_values(score_col, ascending=False).reset_index(drop=True)
    chosen_idx = [order.iloc[0]["anchor_index"]]
    chosen_ids = [order.iloc[0]["anchor_id"]]
    times = part["anchor_index"].astype(float).to_numpy()
    aid_by_idx = dict(zip(part["anchor_index"].astype(int), part["anchor_id"]))
    chosen_set = {chosen_ids[0]}
    for _ in range(n - 1):
        best_gap = -1.0
        best_idx = None
        for ix, t in enumerate(times):
            aid = aid_by_idx.get(int(part.iloc[ix]["anchor_index"]))
            if aid in chosen_set:
                continue
            min_dist = min(abs(t - c) for c in chosen_idx)
            if min_dist > best_gap:
                best_gap = min_dist
                best_idx = int(part.iloc[ix]["anchor_index"])
                best_aid = aid
        if best_idx is None:
            break
        chosen_idx.append(best_idx)
        chosen_ids.append(best_aid)
        chosen_set.add(best_aid)
    return chosen_ids


def greedy_maxmin_time_fast(pool: pd.DataFrame, n: int, score_col: str) -> list[str]:
    """Vectorized greedy max-min time selection (anchor_index as time proxy)."""
    part = pool.copy()
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return _by_index_order(part)["anchor_id"].tolist()
    order = part.sort_values(score_col, ascending=False).reset_index(drop=True)
    times = order["anchor_index"].astype(float).to_numpy()
    ids = order["anchor_id"].astype(str).to_numpy()
    chosen_pos = [0]
    chosen_times = [times[0]]
    available = np.ones(len(times), dtype=bool)
    available[0] = False
    while len(chosen_pos) < n and available.any():
        # min distance from each available point to chosen set
        diffs = np.abs(times[:, None] - np.array(chosen_times)[None, :])
        min_d = diffs.min(axis=1)
        min_d[~available] = -1.0
        best = int(np.argmax(min_d))
        if not available[best]:
            break
        chosen_pos.append(best)
        chosen_times.append(times[best])
        available[best] = False
    return ids[chosen_pos].tolist()


def temporal_nms(pool: pd.DataFrame, n: int, score_col: str, gap: float) -> list[str]:
    """NMS over anchor_index (time proxy). gap is in anchor_index units (10s steps)."""
    part = pool.sort_values(score_col, ascending=False).reset_index(drop=True)
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return part["anchor_id"].tolist()
    times = part["anchor_index"].astype(float).to_numpy()
    ids = part["anchor_id"].astype(str).to_numpy()
    suppressed = np.zeros(len(times), dtype=bool)
    chosen = []
    for i in range(len(times)):
        if suppressed[i]:
            continue
        chosen.append(ids[i])
        if len(chosen) >= n:
            break
        # suppress neighbors within gap
        for j in range(i + 1, len(times)):
            if not suppressed[j] and abs(times[j] - times[i]) <= gap:
                suppressed[j] = True
    # if not enough, backfill from remaining high-score candidates
    if len(chosen) < n:
        for i in range(len(times)):
            if ids[i] not in chosen and not suppressed[i]:
                chosen.append(ids[i])
                if len(chosen) >= n:
                    break
    return chosen[:n]


def block_round_robin(pool: pd.DataFrame, n: int, score_col: str, block_size: float) -> list[str]:
    """Split time axis into fixed blocks, round-robin pick highest proxy per block."""
    part = pool.copy()
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return _by_index_order(part)["anchor_id"].tolist()
    part["_block"] = (part["center_time_s"].astype(float) // block_size).astype(int)
    block_ids = sorted(part["_block"].unique())
    chosen = []
    chosen_set = set()
    progressed = True
    while len(chosen) < n and progressed:
        progressed = False
        for b in block_ids:
            if len(chosen) >= n:
                break
            block = part[(part["_block"] == b) & (~part["anchor_id"].isin(chosen_set))]
            if block.empty:
                continue
            aid = block.sort_values(score_col, ascending=False).iloc[0]["anchor_id"]
            chosen.append(aid)
            chosen_set.add(aid)
            progressed = True
    return chosen[:n]


def random_from_pool(pool: pd.DataFrame, n: int, score_col: str, rng: np.random.Generator) -> list[str]:
    if n <= 0 or len(pool) == 0:
        return []
    if n >= len(pool):
        return _by_index_order(pool)["anchor_id"].tolist()
    return pool.sample(n=n, random_state=int(rng.integers(0, 2**31 - 1)))["anchor_id"].tolist()


def score_weighted_spread(pool: pd.DataFrame, n: int, score_col: str, lam: float) -> list[str]:
    """Greedy: normalized_proxy + lambda * min_time_distance_to_selected."""
    part = pool.copy()
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return _by_index_order(part)["anchor_id"].tolist()
    s = part[score_col].astype(float).to_numpy()
    s_min, s_max = np.nanmin(s), np.nanmax(s)
    if s_max > s_min:
        norm_s = (s - s_min) / (s_max - s_min)
    else:
        norm_s = np.zeros_like(s)
    times = part["anchor_index"].astype(float).to_numpy()
    ids = part["anchor_id"].astype(str).to_numpy()
    # start with highest normalized proxy
    first = int(np.argmax(norm_s))
    chosen = [first]
    chosen_times = [times[first]]
    available = np.ones(len(times), dtype=bool)
    available[first] = False
    while len(chosen) < n and available.any():
        best_score = -1e18
        best_idx = None
        for ix in range(len(times)):
            if not available[ix]:
                continue
            min_dist = min(abs(times[ix] - c) for c in chosen_times)
            # normalize min_dist by max possible gap (rough)
            val = norm_s[ix] + lam * min_dist
            if val > best_score:
                best_score = val
                best_idx = ix
        if best_idx is None:
            break
        chosen.append(best_idx)
        chosen_times.append(times[best_idx])
        available[best_idx] = False
    return ids[chosen].tolist()


def score_weighted_spread_fast(pool: pd.DataFrame, n: int, score_col: str, lam: float) -> list[str]:
    part = pool.copy()
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return _by_index_order(part)["anchor_id"].tolist()
    s = part[score_col].astype(float).to_numpy()
    s_min, s_max = np.nanmin(s), np.nanmax(s)
    norm_s = (s - s_min) / (s_max - s_min) if s_max > s_min else np.zeros_like(s)
    times = part["anchor_index"].astype(float).to_numpy()
    ids = part["anchor_id"].astype(str).to_numpy()
    first = int(np.argmax(norm_s))
    chosen = [first]
    available = np.ones(len(times), dtype=bool)
    available[first] = False
    chosen_times = np.array([times[first]])
    span = max(1.0, times.max() - times.min())
    while len(chosen) < n and available.any():
        diffs = np.abs(times[:, None] - chosen_times[None, :])
        min_d = diffs.min(axis=1)
        min_d_norm = min_d / span
        score = norm_s + lam * min_d_norm
        score[~available] = -1e18
        best = int(np.argmax(score))
        if not available[best]:
            break
        chosen.append(best)
        available[best] = False
        chosen_times = np.append(chosen_times, times[best])
    return ids[chosen].tolist()


def select_top_proxy(pool: pd.DataFrame, n: int, score_col: str) -> list[str]:
    """P=1.0 equivalent: just top-n by proxy."""
    return pool.sort_values(score_col, ascending=False).head(n)["anchor_id"].tolist()


def build_pool(df: pd.DataFrame, P: float, B: int, score_col: str) -> pd.DataFrame:
    """Top P*B by proxy score (capped at N)."""
    pool_size = min(int(math.ceil(P * B)), len(df))
    return df.sort_values(score_col, ascending=False).head(pool_size)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    df: pd.DataFrame,
    selected_ids: list[str],
    method: str,
    budget: int,
    seed: int | str,
    role_by_id: dict[str, str] | None = None,
    selected_proxy: str = "",
    calibration_positives: int | None = None,
    execution_positives: int | None = None,
    cal_size: int = 0,
    exec_size: int = 0,
    block_size: float = 300.0,
) -> dict:
    role_by_id = role_by_id or {}
    order = {aid: i for i, aid in enumerate(selected_ids)}
    selected = df[df["anchor_id"].isin(selected_ids)].copy()
    selected["_order"] = selected["anchor_id"].map(order)
    selected = selected.sort_values("_order")
    total_pos = int(df["is_positive"].sum())
    clusters = pos_clusters(df)
    total_clusters = len(clusters)
    singleton_clusters = set(int(c) for c in df[df["is_singleton_cluster"]]["event_cluster_id"].unique())
    multi_clusters = set(int(c) for c in df[df["is_multi_anchor_cluster"]]["event_cluster_id"].unique())
    sel_pos = selected[selected["is_positive"]]
    hit_clusters = set(int(c) for c in sel_pos["event_cluster_id"] if int(c) >= 0)
    singleton_hit = len(hit_clusters & singleton_clusters)
    multi_hit = len(hit_clusters & multi_clusters)
    sel_pos_count = int(sel_pos["is_positive"].sum())
    if calibration_positives is None:
        cal_ids = [aid for aid in selected_ids if "calib" in role_by_id.get(aid, "")]
        cal_pos_df = selected[selected["anchor_id"].isin(cal_ids)]
        calibration_positives = int(cal_pos_df["is_positive"].sum()) if len(cal_pos_df) else 0
    if execution_positives is None:
        execution_positives = sel_pos_count - calibration_positives
    # block coverage
    blocks = (selected["center_time_s"].astype(float) // block_size).astype(int)
    block_coverage = int(blocks.nunique())
    # temporal span and avg NN gap
    if len(selected) >= 2:
        st = selected["anchor_index"].astype(float).sort_values().to_numpy()
        temporal_span = float(st[-1] - st[0])
        nn_gaps = np.diff(st)
        avg_nn_gap = float(nn_gaps.mean())
    else:
        temporal_span = 0.0
        avg_nn_gap = 0.0
    # redundancy: redundant positive calls (same cluster already hit) - vectorized
    sel_pos_ordered = sel_pos.sort_values("_order")
    pos_cids = sel_pos_ordered["event_cluster_id"].astype(int).to_numpy()
    seen_mask = np.zeros(len(pos_cids), dtype=bool)
    seen_set = set()
    for k_, cid in enumerate(pos_cids):
        if cid in seen_set:
            seen_mask[k_] = True
        else:
            seen_set.add(cid)
    redundant = int(seen_mask.sum())
    redundancy_rate = float(redundant / max(1, len(selected)))
    return {
        "method": method,
        "budget": budget,
        "seed": seed,
        "n_selected": len(selected),
        "positives_found": sel_pos_count,
        "anchor_recall": float(sel_pos_count / total_pos) if total_pos else 0.0,
        "event_cluster_recall": float(len(hit_clusters) / total_clusters) if total_clusters else 0.0,
        "precision": float(sel_pos_count / len(selected)) if len(selected) else 0.0,
        "clusters_hit": len(hit_clusters),
        "singleton_cluster_recall": float(singleton_hit / max(1, len(singleton_clusters))),
        "multi_anchor_cluster_recall": float(multi_hit / max(1, len(multi_clusters))),
        "redundant_positive_calls": redundant,
        "redundancy_rate": redundancy_rate,
        "block_coverage": block_coverage,
        "temporal_span": temporal_span,
        "avg_nn_time_gap": avg_nn_gap,
        "selected_proxy": selected_proxy,
        "calibration_positives": int(calibration_positives),
        "execution_positives": int(execution_positives),
        "cal_size": cal_size,
        "exec_size": exec_size,
    }


def selection_frame(df: pd.DataFrame, selected_ids: list[str], method: str, budget: int, seed: int | str, role_by_id: dict[str, str] | None = None, **flags) -> pd.DataFrame:
    role_by_id = role_by_id or {}
    idx = {aid: i for i, aid in enumerate(selected_ids)}
    sel = df[df["anchor_id"].isin(selected_ids)].copy()
    sel["selected_order"] = sel["anchor_id"].map(idx)
    sel = sel.sort_values("selected_order")
    cols = ["selected_order", "anchor_id", "anchor_index", "center_time_s", "oracle_label", "is_positive", "event_cluster_id", "is_singleton_cluster", "is_multi_anchor_cluster"]
    out = sel[cols].copy()
    out.insert(0, "method", method)
    out.insert(1, "budget", budget)
    out.insert(2, "seed", seed)
    out["selection_role"] = out["anchor_id"].map(role_by_id).fillna("selected")
    for k, v in flags.items():
        out[k] = v
    return out


def save_selection(out_df: pd.DataFrame, root: Path, method: str, budget: int, seed: int | str) -> None:
    if seed == "deterministic":
        path = root / method / f"B_{budget}" / "deterministic.csv"
    else:
        path = root / method / f"B_{budget}" / f"seed_{seed}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(path, index=False)


def summarize(long: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
    rows = []
    group_cols = [c for c in ["method", "budget"] if c in long.columns]
    for key, part in long.groupby(group_cols):
        row = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        row["n_runs"] = len(part)
        for m in metric_cols:
            vals = part[m].astype(float).tolist()
            row[f"{m}_mean"] = float(np.mean(vals)) if vals else float("nan")
            row[f"{m}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            row[f"{m}_ci95"] = ci95(vals)
        rows.append(row)
    return pd.DataFrame(rows)
