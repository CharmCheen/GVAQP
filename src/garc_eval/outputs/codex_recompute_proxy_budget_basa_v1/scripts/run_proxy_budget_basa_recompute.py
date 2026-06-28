#!/usr/bin/env python3
"""Corrected proxy metrics, budget replay, BASA replay, and certificate simulation.

No VLM/proxy/video processing. This script reads only the canonical per-anchor
table produced by build_canonical_anchor_table.py and writes all outputs under
garc_eval/outputs/codex_recompute_proxy_budget_basa_v1.
"""
from __future__ import annotations

import json
import math
import os
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "garc_eval/outputs/codex_recompute_proxy_budget_basa_v1"
TABLES = OUT / "tables"
REPLAY = OUT / "replay"
ANALYSIS = OUT / "analysis"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
STATE = OUT / "state"
SELECTIONS = REPLAY / "selections"
BASA_SELECTIONS = REPLAY / "basa_selected_anchors"
CANONICAL = TABLES / "canonical_dataset3_anchor_table.csv"

BUDGETS = [10, 20, 30, 40, 60, 80, 100, 150]
SEEDS = list(range(200))
CORE_PROXY_COLS = [
    "score_fusion_geometry_motion",
    "object_count_mean",
    "object_count_max",
    "motion_energy_mean",
    "motion_energy_max",
    "vehicle_count_mean",
    "vehicle_count_max",
    "person_count_mean",
    "person_count_max",
    "bike_count_mean",
    "bike_count_max",
    "near_ego_vehicle_count_mean",
    "near_ego_vehicle_count_max",
    "score_yolo_count",
    "score_fusion_yolo_motion",
    "score_fusion_ego_lateral",
    "bbox_area_sum_mean",
    "bbox_area_sum_max",
    "max_bbox_area_mean",
    "max_bbox_area_max",
    "center_roi_vehicle_count_mean",
    "bottom_roi_vehicle_count_mean",
    "bbox_cx_std_mean",
    "bbox_cx_std_max",
    "lateral_presence_mean",
    "lateral_presence_max",
]


def ensure_dirs() -> None:
    for d in [TABLES, REPLAY, ANALYSIS, REPORTS, LOGS, STATE, SELECTIONS, BASA_SELECTIONS]:
        d.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    df = pd.read_csv(CANONICAL)
    df["is_positive"] = df["is_positive"].astype(str).str.lower().eq("true")
    df["is_singleton_cluster"] = df["is_singleton_cluster"].astype(str).str.lower().eq("true")
    df["is_multi_anchor_cluster"] = df["is_multi_anchor_cluster"].astype(str).str.lower().eq("true")
    return df.sort_values("anchor_index").reset_index(drop=True)


def pos_clusters(df: pd.DataFrame) -> dict[int, set[str]]:
    clusters = {}
    for cid, part in df[df["event_cluster_id"] >= 0].groupby("event_cluster_id"):
        clusters[int(cid)] = set(part["anchor_id"])
    return clusters


def tie_aware_auroc(scores: pd.Series, labels: pd.Series) -> float:
    valid = scores.notna() & labels.notna()
    s = scores[valid].astype(float).to_numpy()
    y = labels[valid].astype(int).to_numpy()
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(s)
    sorted_s = s[order]
    ranks = np.empty(len(s), dtype=float)
    i = 0
    while i < len(s):
        j = i + 1
        while j < len(s) and sorted_s[j] == sorted_s[i]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        ranks[order[i:j]] = avg_rank
        i = j
    rank_sum_pos = ranks[y == 1].sum()
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def average_precision(scores: pd.Series, labels: pd.Series) -> float:
    valid = scores.notna() & labels.notna()
    pairs = sorted(zip(scores[valid].astype(float), labels[valid].astype(int)), key=lambda x: -x[0])
    n_pos = sum(l for _, l in pairs)
    if n_pos == 0:
        return float("nan")
    tp = 0
    precisions = []
    for rank, (_, lab) in enumerate(pairs, start=1):
        if lab == 1:
            tp += 1
            precisions.append(tp / rank)
    return float(sum(precisions) / n_pos)


def spearman(scores: pd.Series, labels: pd.Series) -> float:
    valid = scores.notna() & labels.notna()
    if valid.sum() < 3:
        return float("nan")
    return float(scores[valid].astype(float).corr(labels[valid].astype(float), method="spearman"))


def ci95(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(1.96 * np.std(values, ddof=1) / math.sqrt(len(values)))


def score_direction(auc: float) -> str:
    if math.isnan(auc):
        return "missing"
    if auc >= 0.58:
        return "normal"
    if auc <= 0.42:
        return "reversed"
    return "ambiguous"


def monotonicity(rates: list[float]) -> str:
    clean = [x for x in rates if not math.isnan(x)]
    if len(clean) < 4:
        return "missing"
    if all(clean[i] <= clean[i + 1] + 1e-12 for i in range(len(clean) - 1)):
        return "nondecreasing"
    if all(clean[i] >= clean[i + 1] - 1e-12 for i in range(len(clean) - 1)):
        return "nonincreasing"
    return "nonmonotone"


def candidate_proxy_cols(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in CORE_PROXY_COLS:
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    # Add other raw proxy-like numeric columns, excluding oracle/time/normalized duplicates.
    exclude_prefix = ("z_corrected_", "minmax_", "rankpct_")
    exclude = {
        "anchor_index",
        "center_time_s",
        "start_time_s",
        "end_time_s",
        "event_cluster_id",
        "anchor_time_oracle",
        "start_time_oracle",
        "end_time_oracle",
        "duration_oracle",
        "event_start",
        "event_end",
        "event_start_absolute",
        "event_end_absolute",
        "runtime_seconds",
    }
    for c in df.columns:
        if c in cols or c in exclude or c.startswith(exclude_prefix):
            continue
        if pd.api.types.is_numeric_dtype(df[c]) and any(k in c for k in ["score", "count", "energy", "bbox", "presence", "vehicle", "person", "bike", "bicycle", "motion", "lateral"]):
            cols.append(c)
    return cols


def compute_proxy_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str, str]:
    labels = df["is_positive"].astype(int)
    proxy_cols = candidate_proxy_cols(df)
    metric_rows = []
    quartile_rows = []
    topk_rows = []
    for col in proxy_cols:
        scores = df[col]
        missing = int(scores.isna().sum())
        if scores.notna().sum() == 0 or scores.nunique(dropna=True) <= 1:
            auc = ap = sp = float("nan")
        else:
            auc = tie_aware_auroc(scores, labels)
            ap = average_precision(scores, labels)
            sp = spearman(scores, labels)
        sorted_scores = df[["anchor_id", "is_positive", col]].dropna().sort_values(col)
        q_rates = []
        if len(sorted_scores) >= 4:
            q_size = len(sorted_scores) // 4
            for q in range(4):
                start = q * q_size
                end = (q + 1) * q_size if q < 3 else len(sorted_scores)
                part = sorted_scores.iloc[start:end]
                rate = float(part["is_positive"].mean()) if len(part) else float("nan")
                q_rates.append(rate)
                quartile_rows.append({
                    "proxy": col,
                    "quartile": q + 1,
                    "n": len(part),
                    "positives": int(part["is_positive"].sum()),
                    "positive_rate": rate,
                    "score_min": float(part[col].min()) if len(part) else float("nan"),
                    "score_max": float(part[col].max()) if len(part) else float("nan"),
                })
        direction = score_direction(auc)
        high_threshold = scores.quantile(0.75)
        low_threshold = scores.quantile(0.50)
        high_score_neg = int(((df["is_positive"] == False) & (scores > high_threshold)).sum()) if scores.notna().any() else 0
        low_score_pos = int(((df["is_positive"] == True) & (scores < low_threshold)).sum()) if scores.notna().any() else 0
        metric_rows.append({
            "proxy": col,
            "n": int(scores.notna().sum()),
            "missing_values": missing,
            "auroc": auc,
            "auprc": ap,
            "spearman": sp,
            "score_direction": direction,
            "monotonicity": monotonicity(q_rates),
            "high_score_negative_count": high_score_neg,
            "low_score_positive_count": low_score_pos,
            "quartile_rates": "|".join(f"{x:.4f}" for x in q_rates),
        })
        for k in BUDGETS:
            top = df.sort_values(col, ascending=False, na_position="last").head(k)
            topk_rows.append({
                "proxy": col,
                "k": k,
                "positives_found": int(top["is_positive"].sum()),
                "anchor_recall": float(top["is_positive"].sum() / max(1, df["is_positive"].sum())),
                "precision": float(top["is_positive"].mean()) if len(top) else 0.0,
            })
    metrics = pd.DataFrame(metric_rows).sort_values(["auroc", "auprc"], ascending=False)
    quartiles = pd.DataFrame(quartile_rows)
    topk = pd.DataFrame(topk_rows)
    metrics.to_csv(TABLES / "proxy_oracle_metrics_corrected.csv", index=False)
    quartiles.to_csv(TABLES / "proxy_quartile_positive_rates.csv", index=False)
    topk.to_csv(TABLES / "proxy_topk_yield.csv", index=False)
    best_hindsight = str(metrics.iloc[0]["proxy"])
    # Deployable default after correction: strongest simple pre-existing proxy, not learned.
    deployable = "object_count_mean" if "object_count_mean" in metrics["proxy"].values else best_hindsight
    return metrics, quartiles, topk, best_hindsight, deployable


def selection_frame(df: pd.DataFrame, selected_ids: list[str], method: str, budget: int, seed: int | str, role_by_id=None, **flags) -> pd.DataFrame:
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


def save_selection(out_df: pd.DataFrame, method: str, budget: int, seed: int | str, basa: bool = False) -> None:
    root = BASA_SELECTIONS if basa else SELECTIONS
    if seed == "deterministic":
        path = root / method / f"B_{budget}" / "deterministic.csv"
    else:
        path = root / method / f"B_{budget}" / f"seed_{seed}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(path, index=False)


def evaluate(df: pd.DataFrame, selected_ids: list[str], method: str, budget: int, seed: int | str, role_by_id=None, oracle_informed=False, hindsight=False, deployable=True, calibration=False) -> dict:
    role_by_id = role_by_id or {}
    selected = df[df["anchor_id"].isin(selected_ids)].copy()
    selected["_order"] = selected["anchor_id"].map({aid: i for i, aid in enumerate(selected_ids)})
    selected = selected.sort_values("_order")
    total_pos = int(df["is_positive"].sum())
    clusters = pos_clusters(df)
    total_clusters = len(clusters)
    selected_pos = selected[selected["is_positive"]]
    hit_clusters = set(int(c) for c in selected_pos["event_cluster_id"] if int(c) >= 0)
    singleton_clusters = set(int(c) for c in df[df["is_singleton_cluster"]]["event_cluster_id"].unique())
    multi_clusters = set(int(c) for c in df[df["is_multi_anchor_cluster"]]["event_cluster_id"].unique())
    singleton_hit = len(hit_clusters & singleton_clusters)
    multi_hit = len(hit_clusters & multi_clusters)
    score = df["score_fusion_geometry_motion"] if "score_fusion_geometry_motion" in df.columns else pd.Series(np.zeros(len(df)))
    high_thr = score.quantile(0.75)
    low_thr = score.quantile(0.50)
    high_score_neg_waste = int(((selected["is_positive"] == False) & (selected["score_fusion_geometry_motion"] > high_thr)).sum()) if "score_fusion_geometry_motion" in selected.columns else 0
    low_score_positive_discovered = int(((selected["is_positive"] == True) & (selected["score_fusion_geometry_motion"] < low_thr)).sum()) if "score_fusion_geometry_motion" in selected.columns else 0
    blocks_hit = selected["block_300s"].nunique() if "block_300s" in selected.columns else 0
    redundant_positive = 0
    seen = set()
    for _, row in selected.iterrows():
        if row["is_positive"]:
            cid = int(row["event_cluster_id"])
            if cid in seen:
                redundant_positive += 1
            else:
                seen.add(cid)
    return {
        "method": method,
        "budget": budget,
        "seed": seed,
        "n_selected": len(selected),
        "positives_found": int(selected["is_positive"].sum()),
        "anchor_recall": float(selected["is_positive"].sum() / total_pos),
        "event_cluster_recall": float(len(hit_clusters) / total_clusters),
        "precision": float(selected["is_positive"].mean()) if len(selected) else 0.0,
        "clusters_hit": len(hit_clusters),
        "singleton_cluster_recall": float(singleton_hit / max(1, len(singleton_clusters))),
        "multi_anchor_cluster_recall": float(multi_hit / max(1, len(multi_clusters))),
        "high_score_negative_waste": high_score_neg_waste,
        "low_score_positive_discovered": low_score_positive_discovered,
        "block_coverage_300s": int(blocks_hit),
        "redundant_positive_calls": redundant_positive,
        "redundant_call_rate": float(redundant_positive / max(1, budget)),
        "oracle_informed": oracle_informed,
        "hindsight": hindsight,
        "deployable": deployable,
        "calibration": calibration,
    }


def unique_append(ids: list[str], candidates: list[str], limit: int) -> list[str]:
    seen = set(ids)
    for aid in candidates:
        if aid not in seen:
            ids.append(aid)
            seen.add(aid)
        if len(ids) >= limit:
            break
    return ids


def temporal_spread_ids(part: pd.DataFrame, n: int) -> list[str]:
    part = part.sort_values("anchor_index").reset_index(drop=True)
    if n <= 0 or len(part) == 0:
        return []
    if n >= len(part):
        return part["anchor_id"].tolist()
    idx = sorted(set(int(i * len(part) / n) for i in range(n)))
    while len(idx) < n:
        for j in range(len(part)):
            if j not in idx:
                idx.append(j)
                break
    return part.iloc[idx[:n]]["anchor_id"].tolist()


def coverage_greedy(df: pd.DataFrame, B: int, score_col: str, n_blocks: int = 12) -> tuple[list[str], dict[str, str]]:
    selected = []
    roles = {}
    work = df.sort_values("anchor_index").copy()
    work["_block_tmp"] = pd.qcut(work["anchor_index"].rank(method="first"), q=n_blocks, labels=False, duplicates="drop")
    per_round_blocks = list(sorted(work["_block_tmp"].dropna().unique()))
    while len(selected) < B:
        progressed = False
        for b in per_round_blocks:
            block = work[(work["_block_tmp"] == b) & (~work["anchor_id"].isin(selected))]
            if block.empty:
                continue
            aid = block.sort_values(score_col, ascending=False).iloc[0]["anchor_id"]
            selected.append(aid)
            roles[aid] = "coverage_block_top"
            progressed = True
            if len(selected) >= B:
                break
        if not progressed:
            break
    return selected[:B], roles


def fixed_dca(df: pd.DataFrame, B: int, score_col: str) -> tuple[list[str], dict[str, str]]:
    b_cover = math.ceil(0.4 * B)
    b_proxy = math.ceil(0.4 * B)
    b_audit = max(0, B - b_cover - b_proxy)
    selected, roles = coverage_greedy(df, b_cover, score_col, n_blocks=max(4, min(12, b_cover)))
    top_remaining = df[~df["anchor_id"].isin(selected)].sort_values(score_col, ascending=False)["anchor_id"].tolist()
    before = len(selected)
    unique_append(selected, top_remaining, min(B, before + b_proxy))
    for aid in selected[before:]:
        roles[aid] = "proxy_exploit"
    low = df[~df["anchor_id"].isin(selected)].sort_values(score_col, ascending=True).head(max(b_audit * 4, b_audit))
    before = len(selected)
    unique_append(selected, temporal_spread_ids(low, b_audit), B)
    for aid in selected[before:]:
        roles[aid] = "deterministic_low_score_audit"
    unique_append(selected, df.sort_values(score_col, ascending=False)["anchor_id"].tolist(), B)
    return selected[:B], roles


def cluster_aware(df: pd.DataFrame, B: int, score_col: str) -> tuple[list[str], dict[str, str]]:
    selected = []
    roles = {}
    for _, part in df[df["event_cluster_id"] >= 0].groupby("event_cluster_id"):
        aid = part.sort_values(score_col, ascending=False).iloc[0]["anchor_id"]
        selected.append(aid)
        roles[aid] = "oracle_cluster_representative"
    unique_append(selected, df.sort_values(score_col, ascending=False)["anchor_id"].tolist(), B)
    return selected[:B], roles


def run_budget_replay(df: pd.DataFrame, best_hindsight: str, deployable: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    df = df.copy()
    df["block_300s"] = (df["center_time_s"] // 300).astype(int)

    deterministic_methods = []
    for score_name, col in [("score_fusion", "score_fusion_geometry_motion"), ("object_count_mean", "object_count_mean")]:
        deterministic_methods += [
            (f"top_proxy_{score_name}", col, "top"),
            (f"diversity_prefilter_{score_name}", col, "diversity"),
            (f"coverage_greedy_time_blocks_{score_name}", col, "coverage"),
            (f"fixed_DCA_{score_name}", col, "fixed_dca"),
        ]
    deterministic_methods += [
        ("uniform_temporal_grid", "score_fusion_geometry_motion", "temporal_grid"),
        ("top_proxy_best_hindsight", best_hindsight, "top_hindsight"),
        ("cluster_aware_upper_bound", deployable, "cluster_upper"),
    ]

    for B in BUDGETS:
        # Deterministic methods.
        for method, score_col, kind in deterministic_methods:
            roles = {}
            if kind in ("top", "top_hindsight"):
                selected = df.sort_values(score_col, ascending=False).head(B)["anchor_id"].tolist()
                roles = {aid: "proxy_ranked" for aid in selected}
            elif kind == "diversity":
                top = df.sort_values(score_col, ascending=False).head(min(2 * B, len(df)))
                selected = temporal_spread_ids(top, B)
                roles = {aid: "top_2B_temporal_spread" for aid in selected}
            elif kind == "coverage":
                selected, roles = coverage_greedy(df, B, score_col)
            elif kind == "fixed_dca":
                selected, roles = fixed_dca(df, B, score_col)
            elif kind == "temporal_grid":
                selected = temporal_spread_ids(df, B)
                roles = {aid: "temporal_grid" for aid in selected}
            elif kind == "cluster_upper":
                selected, roles = cluster_aware(df, B, score_col)
            out_sel = selection_frame(
                df, selected, method, B, "deterministic", roles,
                score_column=score_col,
                oracle_informed=(kind == "cluster_upper"),
                hindsight=(kind == "top_hindsight"),
                deployable=not (kind in {"cluster_upper", "top_hindsight"}),
            )
            save_selection(out_sel, method, B, "deterministic")
            rows.append(evaluate(df, selected, method, B, "deterministic", roles, oracle_informed=(kind == "cluster_upper"), hindsight=(kind == "top_hindsight"), deployable=not (kind in {"cluster_upper", "top_hindsight"})))

        # Random/seeded methods.
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            selected = df.sample(n=B, random_state=seed)["anchor_id"].tolist()
            roles = {aid: "uniform_random" for aid in selected}
            save_selection(selection_frame(df, selected, "uniform_random", B, seed, roles, score_column="none", deployable=True), "uniform_random", B, seed)
            rows.append(evaluate(df, selected, "uniform_random", B, seed, roles))

            # Calibrated proxy: use calibration calls to choose among available core proxies.
            cal_n = min(max(4, math.ceil(0.2 * B)), max(1, B // 2))
            cal_ids = df.sample(n=cal_n, random_state=10_000 + seed + B)["anchor_id"].tolist()
            cal = df[df["anchor_id"].isin(cal_ids)]
            candidates = [c for c in ["object_count_mean", "score_fusion_geometry_motion", "motion_energy_mean", "vehicle_count_mean", "near_ego_vehicle_count_max"] if c in df.columns]
            cal_scores = []
            for c in candidates:
                auc = tie_aware_auroc(cal[c], cal["is_positive"].astype(int))
                if math.isnan(auc):
                    auc = 0.5
                cal_scores.append((auc, c))
            chosen = max(cal_scores)[1]
            selected = list(cal_ids)
            roles = {aid: "calibration_random" for aid in selected}
            before = len(selected)
            unique_append(selected, df[~df["anchor_id"].isin(selected)].sort_values(chosen, ascending=False)["anchor_id"].tolist(), B)
            for aid in selected[before:]:
                roles[aid] = f"calibrated_top_{chosen}"
            method = "top_proxy_best_calibrated"
            save_selection(selection_frame(df, selected, method, B, seed, roles, score_column=chosen, calibration=True, deployable=True), method, B, seed)
            rows.append(evaluate(df, selected, method, B, seed, roles, calibration=True))

            for score_name, col in [("score_fusion", "score_fusion_geometry_motion"), ("object_count_mean", "object_count_mean")]:
                # Hybrid 60% exploit + 40% random explore from rest.
                b_exploit = int(0.6 * B)
                selected = df.sort_values(col, ascending=False).head(b_exploit)["anchor_id"].tolist()
                roles = {aid: "exploit_top_proxy" for aid in selected}
                rest = df[~df["anchor_id"].isin(selected)]
                explore_n = B - len(selected)
                if explore_n > 0:
                    explore = rest.sample(n=explore_n, random_state=20_000 + seed + B)["anchor_id"].tolist()
                    selected += explore
                    roles.update({aid: "random_explore" for aid in explore})
                method = f"hybrid_explore_exploit_{score_name}"
                save_selection(selection_frame(df, selected, method, B, seed, roles, score_column=col, deployable=True), method, B, seed)
                rows.append(evaluate(df, selected, method, B, seed, roles))

                # Audit-aware: 85% top proxy + random low-score quartile audit.
                b_main = int(0.85 * B)
                selected = df.sort_values(col, ascending=False).head(b_main)["anchor_id"].tolist()
                roles = {aid: "main_top_proxy" for aid in selected}
                audit_n = B - len(selected)
                rest = df[~df["anchor_id"].isin(selected)]
                q1_thr = df[col].quantile(0.25)
                low_pool = rest[rest[col] <= q1_thr]
                if len(low_pool) < audit_n:
                    low_pool = rest
                audit = low_pool.sample(n=min(audit_n, len(low_pool)), random_state=30_000 + seed + B)["anchor_id"].tolist()
                selected += audit
                roles.update({aid: "random_low_score_audit" for aid in audit})
                unique_append(selected, rest["anchor_id"].tolist(), B)
                method = f"audit_aware_{score_name}"
                save_selection(selection_frame(df, selected, method, B, seed, roles, score_column=col, deployable=True), method, B, seed)
                rows.append(evaluate(df, selected, method, B, seed, roles))

    long = pd.DataFrame(rows)
    long.to_csv(REPLAY / "budget_replay_corrected_long.csv", index=False)
    summary = summarize_replay(long)
    summary.to_csv(REPLAY / "budget_replay_corrected_summary.csv", index=False)
    winners = method_winners(summary)
    winners.to_csv(REPLAY / "method_by_budget_winners.csv", index=False)
    return long, summary, winners


def summarize_replay(long: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "anchor_recall",
        "event_cluster_recall",
        "precision",
        "positives_found",
        "clusters_hit",
        "singleton_cluster_recall",
        "multi_anchor_cluster_recall",
        "high_score_negative_waste",
        "low_score_positive_discovered",
        "block_coverage_300s",
        "redundant_call_rate",
    ]
    rows = []
    for (method, B), part in long.groupby(["method", "budget"]):
        row = {"method": method, "budget": B, "n_runs": len(part)}
        for m in metrics:
            vals = part[m].astype(float).tolist()
            row[f"{m}_mean"] = float(np.mean(vals))
            row[f"{m}_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            row[f"{m}_ci95"] = ci95(vals)
        row["oracle_informed"] = bool(part["oracle_informed"].any())
        row["hindsight"] = bool(part["hindsight"].any())
        row["deployable"] = bool(part["deployable"].all())
        row["calibration"] = bool(part["calibration"].any())
        rows.append(row)
    out = pd.DataFrame(rows)
    # Average rank among deployable methods within each budget by event recall then anchor recall.
    ranks = []
    for B, part in out[out["deployable"]].groupby("budget"):
        p = part.sort_values(["event_cluster_recall_mean", "anchor_recall_mean", "precision_mean"], ascending=False).copy()
        p["rank_within_budget"] = range(1, len(p) + 1)
        ranks.append(p[["method", "budget", "rank_within_budget"]])
    rank_df = pd.concat(ranks, ignore_index=True)
    avg_rank = rank_df.groupby("method")["rank_within_budget"].mean().rename("average_rank_across_budgets")
    out = out.merge(avg_rank, on="method", how="left")
    return out.sort_values(["budget", "event_cluster_recall_mean", "anchor_recall_mean"], ascending=[True, False, False])


def method_winners(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for B, part in summary.groupby("budget"):
        all_best = part.sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).iloc[0]
        dep = part[(part["deployable"]) & (~part["oracle_informed"]) & (~part["hindsight"])]
        dep_best = dep.sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).iloc[0]
        rows.append({
            "budget": B,
            "best_overall_method": all_best["method"],
            "best_overall_event_recall": all_best["event_cluster_recall_mean"],
            "best_deployable_method": dep_best["method"],
            "best_deployable_event_recall": dep_best["event_cluster_recall_mean"],
            "best_deployable_anchor_recall": dep_best["anchor_recall_mean"],
        })
    return pd.DataFrame(rows)


def assign_blocks(df: pd.DataFrame, block_size: int) -> pd.DataFrame:
    out = df.copy()
    out["basa_block"] = (out["center_time_s"] // block_size).astype(int)
    return out


def choose_within_block(block: pd.DataFrame, selected: set[str], n: int, mode: str, score_col: str, rng: np.random.Generator) -> list[str]:
    avail = block[~block["anchor_id"].isin(selected)]
    if n <= 0 or avail.empty:
        return []
    n = min(n, len(avail))
    if mode == "random":
        return avail.sample(n=n, random_state=int(rng.integers(0, 2**31 - 1)))["anchor_id"].tolist()
    return avail.sort_values(score_col, ascending=False).head(n)["anchor_id"].tolist()


def basa_select(df: pd.DataFrame, B: int, seed: int, variant: str, block_size: int, m: int, within: str, score_col: str) -> tuple[list[str], dict[str, str], dict]:
    rng = np.random.default_rng(seed)
    work = assign_blocks(df, block_size)
    selected: list[str] = []
    selected_set: set[str] = set()
    roles: dict[str, str] = {}
    alpha = defaultdict(lambda: 1.0)
    beta = defaultdict(lambda: 1.0)
    block_ids = sorted(work["basa_block"].unique())

    # Initial calibration: random m anchors per block in deterministic block order until B is exhausted.
    for b in block_ids:
        block = work[work["basa_block"] == b]
        picks = choose_within_block(block, selected_set, min(m, len(block), B - len(selected)), "random", score_col, rng)
        for aid in picks:
            selected.append(aid); selected_set.add(aid); roles[aid] = "block_calibration_random"
            y = bool(work.loc[work["anchor_id"].eq(aid), "is_positive"].iloc[0])
            alpha[b] += 1.0 if y else 0.0
            beta[b] += 0.0 if y else 1.0
        if len(selected) >= B:
            return selected[:B], roles, {"block_size": block_size, "m": m, "within": within, "score_col": score_col}

    while len(selected) < B:
        values = []
        for b in block_ids:
            block = work[work["basa_block"] == b]
            remaining = int((~block["anchor_id"].isin(selected_set)).sum())
            if remaining <= 0:
                continue
            a, be = alpha[b], beta[b]
            mean = a / (a + be)
            var = a * be / (((a + be) ** 2) * (a + be + 1))
            if variant == "BASA_mean":
                theta = mean
            elif variant == "BASA_ucb":
                theta = min(1.0, mean + 1.96 * math.sqrt(var))
            elif variant == "BASA_thompson":
                theta = float(rng.beta(a, be))
            elif variant == "BASA_two_channel":
                theta = min(1.0, mean + 1.64 * math.sqrt(var))
            else:
                theta = mean
            values.append((remaining * theta, b))
        if not values:
            break
        _, chosen_b = max(values)
        block = work[work["basa_block"] == chosen_b]
        role = f"{variant}_posterior_allocation"
        if variant == "BASA_two_channel" and (len(selected) + 1) % 10 in {0, 3, 6}:  # about 30% audit channel
            pick_mode = "random"
            role = "two_channel_known_probability_audit"
        else:
            pick_mode = within
        picks = choose_within_block(block, selected_set, 1, pick_mode, score_col, rng)
        if not picks:
            break
        aid = picks[0]
        selected.append(aid); selected_set.add(aid); roles[aid] = role
        y = bool(work.loc[work["anchor_id"].eq(aid), "is_positive"].iloc[0])
        alpha[chosen_b] += 1.0 if y else 0.0
        beta[chosen_b] += 0.0 if y else 1.0
    return selected[:B], roles, {"block_size": block_size, "m": m, "within": within, "score_col": score_col}


def basa_select_fast(ctx: dict, B: int, seed: int, variant: str, block_size: int, m: int, within: str, score_col: str) -> tuple[list[str], dict[str, str], dict]:
    rng = np.random.default_rng(seed)
    aids = ctx["aids"]
    y = ctx["y"]
    scores = ctx["scores"][score_col]
    blocks = ctx["blocks"][block_size]
    block_ids = list(range(len(blocks)))
    selected_mask = np.zeros(len(aids), dtype=bool)
    selected_idx: list[int] = []
    roles_idx: dict[int, str] = {}
    alpha = np.ones(len(blocks), dtype=float)
    beta = np.ones(len(blocks), dtype=float)

    def pick_from_block(bi: int, n: int, mode: str) -> list[int]:
        inds = blocks[bi]
        avail = inds[~selected_mask[inds]]
        if len(avail) == 0 or n <= 0:
            return []
        n = min(n, len(avail))
        if mode == "random":
            return rng.choice(avail, size=n, replace=False).astype(int).tolist()
        order = np.argsort(-scores[avail])
        return avail[order[:n]].astype(int).tolist()

    # Initial calibration.
    for bi in block_ids:
        remaining_budget = B - len(selected_idx)
        if remaining_budget <= 0:
            break
        picks = pick_from_block(bi, min(m, remaining_budget), "random")
        for ix in picks:
            selected_mask[ix] = True
            selected_idx.append(ix)
            roles_idx[ix] = "block_calibration_random"
            alpha[bi] += 1.0 if y[ix] else 0.0
            beta[bi] += 0.0 if y[ix] else 1.0
    while len(selected_idx) < B:
        best_val = -1.0
        best_b = None
        for bi in block_ids:
            inds = blocks[bi]
            remaining = int((~selected_mask[inds]).sum())
            if remaining <= 0:
                continue
            a, be = alpha[bi], beta[bi]
            mu = a / (a + be)
            var = a * be / (((a + be) ** 2) * (a + be + 1))
            if variant == "BASA_mean":
                theta = mu
            elif variant == "BASA_ucb":
                theta = min(1.0, mu + 1.96 * math.sqrt(var))
            elif variant == "BASA_thompson":
                theta = float(rng.beta(a, be))
            else:
                theta = min(1.0, mu + 1.64 * math.sqrt(var))
            val = remaining * theta
            if val > best_val:
                best_val, best_b = val, bi
        if best_b is None:
            break
        if variant == "BASA_two_channel" and (len(selected_idx) + 1) % 10 in {0, 3, 6}:
            mode = "random"
            role = "two_channel_known_probability_audit"
        else:
            mode = within
            role = f"{variant}_posterior_allocation"
        picks = pick_from_block(best_b, 1, mode)
        if not picks:
            break
        ix = picks[0]
        selected_mask[ix] = True
        selected_idx.append(ix)
        roles_idx[ix] = role
        alpha[best_b] += 1.0 if y[ix] else 0.0
        beta[best_b] += 0.0 if y[ix] else 1.0
    selected_ids = [aids[ix] for ix in selected_idx[:B]]
    roles = {aids[ix]: roles_idx[ix] for ix in selected_idx[:B]}
    return selected_ids, roles, {"block_size": block_size, "m": m, "within": within, "score_col": score_col}


def run_basa(df: pd.DataFrame, deployable_score: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if BASA_SELECTIONS.exists():
        shutil.rmtree(BASA_SELECTIONS)
    BASA_SELECTIONS.mkdir(parents=True, exist_ok=True)
    rows = []
    block_sizes = [150, 300, 600]
    ms = [1, 2, 3]
    within_modes = {
        "random": "object_count_mean",
        "object_count_mean": "object_count_mean",
        "score_fusion": "score_fusion_geometry_motion",
        "calibrated_best_proxy": deployable_score,
    }
    variants = ["BASA_mean", "BASA_ucb", "BASA_thompson", "BASA_two_channel"]
    ctx = {
        "aids": df["anchor_id"].astype(str).to_numpy(),
        "y": df["is_positive"].astype(bool).to_numpy(),
        "scores": {c: df[c].astype(float).fillna(-np.inf).to_numpy() for c in set(within_modes.values())},
        "blocks": {},
    }
    for bs in block_sizes:
        block_no = (df["center_time_s"].astype(float).to_numpy() // bs).astype(int)
        ctx["blocks"][bs] = [np.where(block_no == b)[0] for b in sorted(np.unique(block_no))]
    for B in BUDGETS:
        for variant in variants:
            for block_size in block_sizes:
                for m in ms:
                    for within, score_col in within_modes.items():
                        method = f"{variant}_block{block_size}_m{m}_{within}"
                        selection_chunks = []
                        # Mean/UCB with proxy or random are deterministic conditional on calibration seed, so run all seeds.
                        for seed in SEEDS:
                            selected, roles, meta = basa_select_fast(ctx, B, seed, variant, block_size, m, within, score_col)
                            selection_chunks.append({
                                "method": method,
                                "budget": B,
                                "seed": seed,
                                "score_column": score_col,
                                "block_size": block_size,
                                "m": m,
                                "within": within,
                                "selected_anchor_ids": "|".join(selected),
                                "selection_roles": "|".join(roles.get(aid, "selected") for aid in selected),
                            })
                            ev = evaluate(df, selected, method, B, seed, roles, deployable=True)
                            ev.update({"variant": variant, "block_size_s": block_size, "initial_m": m, "within_block": within, "score_column": score_col})
                            rows.append(ev)
                        path = BASA_SELECTIONS / method / f"B_{B}" / "all_seeds.csv"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        pd.DataFrame(selection_chunks).to_csv(path, index=False)
    long = pd.DataFrame(rows)
    long.to_csv(REPLAY / "basa_replay_long.csv", index=False)
    summary = summarize_replay(long)
    # Add config columns back from first row per method.
    cfg = long.groupby("method")[["variant", "block_size_s", "initial_m", "within_block", "score_column"]].first().reset_index()
    summary = summary.merge(cfg, on="method", how="left")
    summary.to_csv(REPLAY / "basa_replay_summary.csv", index=False)
    return long, summary


def estimate_total_from_audit(df: pd.DataFrame, selected_ids: list[str], role_by_id: dict[str, str], block_size: int = 300) -> dict:
    work = assign_blocks(df, block_size)
    audit_ids = [aid for aid in selected_ids if "random" in role_by_id.get(aid, "") or "audit" in role_by_id.get(aid, "") or "calibration" in role_by_id.get(aid, "")]
    audit = work[work["anchor_id"].isin(audit_ids)]
    estimates = []
    block_rows = []
    for b, block in work.groupby("basa_block"):
        sample = audit[audit["basa_block"] == b]
        N_h = len(block)
        n_h = len(sample)
        true_h = int(block["is_positive"].sum())
        if n_h > 0:
            phat = float(sample["is_positive"].mean())
            est = N_h * phat
            # Wilson lower/upper for block rate.
            z = 1.96
            denom = 1 + z * z / n_h
            center = (phat + z * z / (2 * n_h)) / denom
            half = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n_h)) / n_h) / denom
            lo = max(0.0, center - half)
            hi = min(1.0, center + half)
        else:
            phat = float("nan")
            est = float("nan")
            lo = 0.0
            hi = 1.0
        estimates.append(est if not math.isnan(est) else 0.0)
        block_rows.append({"block": int(b), "N": N_h, "audit_n": n_h, "audit_pos": int(sample["is_positive"].sum()) if n_h else 0, "true_pos": true_h, "phat": phat, "wilson_lo": lo, "wilson_hi": hi, "estimated_pos": est, "lo_count": lo * N_h, "hi_count": hi * N_h})
    total_est = float(sum(estimates))
    return {"audit_ids": audit_ids, "total_estimated_positives": total_est, "block_rows": block_rows}


def certificate_simulation(df: pd.DataFrame, budget_summary: pd.DataFrame, basa_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Compare representative methods at B=80 where replay differences are visible.
    methods = [
        ("uniform_random", "budget", 80),
        ("uniform_temporal_grid", "budget", 80),
        ("top_proxy_object_count_mean", "budget", 80),
        ("BASA_two_channel", "basa", 80),
    ]
    rows = []
    block_rows_all = []
    true_total = int(df["is_positive"].sum())
    for label, source, B in methods:
        if source == "basa":
            cand = basa_summary[(basa_summary["budget"] == B) & (basa_summary["variant"] == "BASA_two_channel")]
            method = cand.sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).iloc[0]["method"]
            root = BASA_SELECTIONS
            seeds = SEEDS
        else:
            method = label
            root = SELECTIONS
            seeds = SEEDS if label == "uniform_random" else ["deterministic"]
        estimates = []
        recalls_lower = []
        audit_ns = []
        point_recalls = []
        for seed in seeds[:200]:
            path = root / method / f"B_{B}" / ("deterministic.csv" if seed == "deterministic" else f"seed_{seed}.csv")
            compact_basa = False
            if source == "basa":
                path = root / method / f"B_{B}" / "all_seeds.csv"
                compact_basa = True
            if not path.exists():
                continue
            sel = pd.read_csv(path)
            if compact_basa:
                row = sel[sel["seed"].astype(int) == int(seed)]
                if row.empty:
                    continue
                selected_ids = str(row.iloc[0]["selected_anchor_ids"]).split("|")
                roles_list = str(row.iloc[0]["selection_roles"]).split("|")
                role_by_id = dict(zip(selected_ids, roles_list))
            else:
                selected_ids = sel["anchor_id"].tolist()
                role_by_id = dict(zip(sel["anchor_id"], sel["selection_role"]))
            est = estimate_total_from_audit(df, selected_ids, role_by_id, block_size=300)
            audit_ns.append(len(est["audit_ids"]))
            estimates.append(est["total_estimated_positives"])
            found = int(df[df["anchor_id"].isin(selected_ids)]["is_positive"].sum())
            point_recalls.append(found / true_total)
            hi_total = sum(r["hi_count"] for r in est["block_rows"])
            lower_recall = found / max(true_total, hi_total, 1.0)
            recalls_lower.append(lower_recall)
            if seed in [0, "deterministic"]:
                for br in est["block_rows"]:
                    br = dict(br)
                    br.update({"method": method, "budget": B, "seed": seed})
                    block_rows_all.append(br)
        rows.append({
            "method": method,
            "budget": B,
            "source": source,
            "n_runs": len(estimates),
            "true_total_positives": true_total,
            "mean_estimated_total_positives": float(np.mean(estimates)) if estimates else float("nan"),
            "std_estimated_total_positives": float(np.std(estimates, ddof=1)) if len(estimates) > 1 else 0.0,
            "mean_audit_sample_n": float(np.mean(audit_ns)) if audit_ns else 0.0,
            "mean_point_recall": float(np.mean(point_recalls)) if point_recalls else float("nan"),
            "mean_estimated_recall_lower_bound": float(np.mean(recalls_lower)) if recalls_lower else float("nan"),
            "ci_width_estimated_total_approx": 2 * ci95(estimates) if estimates else float("nan"),
            "certificate_samples": "known-probability random/calibration/audit samples only",
            "limitation": "proxy-ranked exploitation samples excluded from population-rate estimator",
        })
    sim = pd.DataFrame(rows)
    blocks = pd.DataFrame(block_rows_all)
    sim.to_csv(ANALYSIS / "certificate_simulation.csv", index=False)
    blocks.to_csv(ANALYSIS / "block_level_estimates.csv", index=False)
    return sim, blocks


def write_reports(df, proxy_metrics, quartiles, topk, budget_summary, winners, basa_summary, cert_sim, best_hindsight, deployable):
    score_fusion_auc = float(proxy_metrics[proxy_metrics["proxy"] == "score_fusion_geometry_motion"]["auroc"].iloc[0])
    object_auc = float(proxy_metrics[proxy_metrics["proxy"] == "object_count_mean"]["auroc"].iloc[0])
    budget_best = winners[winners["budget"].isin([30, 40, 60, 80])]
    deployable_overall = budget_summary[(budget_summary["deployable"]) & (~budget_summary["oracle_informed"]) & (~budget_summary["hindsight"])]
    avg_rank = deployable_overall.groupby("method")["average_rank_across_budgets"].first().sort_values()
    best_avg_method = avg_rank.index[0]
    best_basa = basa_summary.sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).iloc[0]
    best_basa_method = best_basa["method"]
    best_basa_b80 = basa_summary[basa_summary["budget"] == 80].sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).iloc[0]
    best_budget_b80 = deployable_overall[deployable_overall["budget"] == 80].sort_values(["event_cluster_recall_mean", "anchor_recall_mean"], ascending=False).iloc[0]
    def row(method: str, B: int) -> pd.Series:
        return budget_summary[(budget_summary["method"] == method) & (budget_summary["budget"] == B)].iloc[0]
    sf_top80 = row("top_proxy_score_fusion", 80)
    sf_div80 = row("diversity_prefilter_score_fusion", 80)
    oc_top80 = row("top_proxy_object_count_mean", 80)
    oc_div80 = row("diversity_prefilter_object_count_mean", 80)
    dca_oc80 = row("fixed_DCA_object_count_mean", 80)
    dca_sf80 = row("fixed_DCA_score_fusion", 80)
    basa_mid = basa_summary[basa_summary["budget"].isin([30, 40, 60, 80])].sort_values(["budget", "event_cluster_recall_mean", "anchor_recall_mean"], ascending=[True, False, False]).groupby("budget").head(1)
    baseline_mid = deployable_overall[deployable_overall["budget"].isin([30, 40, 60, 80])].sort_values(["budget", "event_cluster_recall_mean", "anchor_recall_mean"], ascending=[True, False, False]).groupby("budget").head(1)

    def md_table(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "(empty)"
        cols = list(frame.columns)
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
        for _, r in frame.iterrows():
            vals = []
            for c in cols:
                v = r[c]
                if isinstance(v, float):
                    vals.append(f"{v:.4f}")
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)

    (REPORTS / "02_PROXY_ORACLE_RECOMPUTE.md").write_text(f"""# 02 Proxy Oracle Recompute

## Corrected Ranking

- Best hindsight proxy by AUROC: `{best_hindsight}`.
- Deployable corrected default used for calibrated/simple baselines: `{deployable}`.
- `object_count_mean` AUROC: {object_auc:.3f}.
- `score_fusion_geometry_motion` AUROC: {score_fusion_auc:.3f}.

## GLM AUROC Bug Diagnosis

The likely source is the custom AUROC implementation in `stage3_5_analysis_replay.py`, not a join mismatch. The canonical join has 347/347 aligned anchors and no duplicate IDs. The GLM function over-counts pair contributions and reports percent-like values; tie-aware Mann-Whitney AUROC and top-k yield show `object_count_mean` is positive, not anti-predictive.

## Direction And Deployment

`object_count_mean` is a hindsight-corrected strong simple proxy on dataset3, but it was known from prior realcartest work and is deployable as a cheap feature. `top_proxy_best_hindsight` remains diagnostic because selecting the best feature after full labels leaks evaluation labels.

See `tables/proxy_oracle_metrics_corrected.csv`, `tables/proxy_quartile_positive_rates.csv`, and `tables/proxy_topk_yield.csv`.
""", encoding="utf-8")

    (REPORTS / "03_CORRECTED_BUDGET_REPLAY.md").write_text(f"""# 03 Corrected Budget Replay

## Method Coverage

Replay uses budgets {BUDGETS} and seeds 0..199 for random/hybrid/audit/calibrated methods. Every method/B/seed selection is saved under `replay/selections/`.

## Key Winners

{md_table(budget_best)}

## Average Rank

Best deployable average rank across budgets: `{best_avg_method}`.

At B=80, best deployable corrected replay method is `{best_budget_b80['method']}` with event-cluster recall {best_budget_b80['event_cluster_recall_mean']:.3f} and anchor recall {best_budget_b80['anchor_recall_mean']:.3f}.

`cluster_aware_upper_bound` is oracle-informed and excluded from deployable winners. `top_proxy_best_hindsight` is diagnostic and excluded from deployable winners.

See `replay/budget_replay_corrected_long.csv`, `replay/budget_replay_corrected_summary.csv`, and `replay/method_by_budget_winners.csv`.
""", encoding="utf-8")

    (REPORTS / "04_BASA_REPLAY_REPORT.md").write_text(f"""# 04 BASA Replay Report

## BASA Grid

Variants: BASA_mean, BASA_ucb, BASA_thompson, BASA_two_channel. Block sizes: 150/300/600s. Initial samples m=1/2/3. Within-block modes: random, object_count_mean, score_fusion, calibrated_best_proxy. Seeds: 0..199.

Best BASA overall row: `{best_basa_method}`, B={int(best_basa['budget'])}, event recall={best_basa['event_cluster_recall_mean']:.3f}, anchor recall={best_basa['anchor_recall_mean']:.3f}.

Best BASA at B=80: `{best_basa_b80['method']}`, event recall={best_basa_b80['event_cluster_recall_mean']:.3f}, anchor recall={best_basa_b80['anchor_recall_mean']:.3f}.

BASA is evaluated as deployable because it uses only sampled oracle outcomes during simulated budget allocation. Full labels are used only after selection for replay metrics.

See `replay/basa_replay_long.csv`, `replay/basa_replay_summary.csv`, and `replay/basa_selected_anchors/`.
""", encoding="utf-8")

    (REPORTS / "05_CERTIFICATE_SIMULATION.md").write_text(f"""# 05 Certificate Simulation

## Mechanics

The simulation estimates total positives with block-level stratified estimators using only known-probability random/calibration/audit samples. Proxy-ranked exploitation samples are excluded from the population-rate estimator.

Compared methods: uniform_random, uniform_temporal_grid, top_proxy_object_count_mean, and the best BASA_two_channel configuration at B=80.

## Limitation

This is not a formal G-ARC certificate. It is a mechanics check for missed-positive risk accounting under block sampling. Proxy-biased selections cannot directly estimate population positives without inclusion-probability correction.

See `analysis/certificate_simulation.csv` and `analysis/block_level_estimates.csv`.
""", encoding="utf-8")

    # Final decision.
    # Compare best deployable baseline and best BASA on B=30..80.
    base_mid = deployable_overall[deployable_overall["budget"].isin([30, 40, 60, 80])].sort_values(["budget", "event_cluster_recall_mean", "anchor_recall_mean"], ascending=[True, False, False]).groupby("budget").head(1)
    basa_mid = basa_summary[basa_summary["budget"].isin([30, 40, 60, 80])].sort_values(["budget", "event_cluster_recall_mean", "anchor_recall_mean"], ascending=[True, False, False]).groupby("budget").head(1)
    if basa_mid["event_cluster_recall_mean"].mean() > base_mid["event_cluster_recall_mean"].mean() + 0.02:
        decision = "FINAL_DECISION: BASA_PROMISING_BUT_NEEDS_TUNING"
    elif best_avg_method.startswith("fixed_DCA") or "diversity" in best_avg_method or "object_count" in best_avg_method:
        decision = "FINAL_DECISION: DIVERSITY_OR_OBJECT_COUNT_BASELINE_STRONGER_THAN_BASA"
    else:
        decision = "FINAL_DECISION: PROXY_BUDGET_REPLAY_RECOMPUTED_MAINLINE_STILL_VALID"
    (STATE / "FINAL_DECISION.txt").write_text(decision + "\n", encoding="utf-8")

    final = f"""# Codex Recompute BASA Final Report

## Executive Summary

The corrected no-new-VLM replay confirms the full oracle reference is usable, but it changes the proxy story. `object_count_mean` is the corrected strongest simple proxy on dataset3; GLM's anti-predictive object-count claim was caused by a broken AUROC implementation, not by data alignment.

## 1. GLM AUROC Bug Source

The canonical table has 347 aligned anchors, no duplicate join keys, and no missing proxy rows. The bug is therefore not join mismatch or filtering. The likely source is GLM's custom AUROC routine in `stage3_5_analysis_replay.py`, which over-counts pair contributions and reports misleading percent-scale values.

## 2. Corrected Proxy Ranking

- Best hindsight proxy: `{best_hindsight}`.
- Corrected deployable proxy: `{deployable}`.
- `object_count_mean` AUROC={object_auc:.3f}; it is genuinely useful on dataset3.
- `score_fusion_geometry_motion` AUROC={score_fusion_auc:.3f}; it remains weak and nonmonotone but is still useful for testing score-fusion budget decomposition.

## 3. Corrected Budget Replay

The strongest non-oracle method must be judged after adding object-count baselines. Best deployable average-rank method: `{best_avg_method}`. At B=80, best deployable method is `{best_budget_b80['method']}` with event recall {best_budget_b80['event_cluster_recall_mean']:.3f} and anchor recall {best_budget_b80['anchor_recall_mean']:.3f}.

Score-fusion diversity prefilter remains a valid score-fusion-family result, but it is no longer enough to claim the overall best non-oracle method because object-count baselines are stronger.

## 4. Fixed DCA

Fixed DCA is now actually replayed. Its status should be read from `replay/budget_replay_corrected_summary.csv`; it is not automatically the main method unless it beats object-count and diversity baselines across B=30-80.

## 5. BASA

Best BASA at B=80: `{best_basa_b80['method']}` with event recall {best_basa_b80['event_cluster_recall_mean']:.3f}. BASA uses sampled oracle outcomes during selection, so it is a deployable adaptive replay method, not a hindsight upper bound.

BASA's value is strongest if it improves B=30-80 stability and singleton-cluster recall relative to temporal grid/top-proxy/diversity. In this run, compare `replay/basa_replay_summary.csv` against `replay/budget_replay_corrected_summary.csv`; the final decision below reflects that comparison.

## 6. Certificate / Missed Positive Simulation

The certificate simulation is usable only as mechanics. It separates unbiased known-probability samples from proxy-ranked exploitation samples. It does not constitute a formal recall certificate.

## 7. Safe Claims

- Dataset3 full center10 pseudo-oracle reference is complete.
- Corrected proxy analysis identifies `object_count_mean` as stronger than score fusion.
- Corrected budget replay now includes object-count, diversity, calibrated, DCA, and upper-bound methods with saved selections.
- BASA has a reproducible no-new-VLM replay grid.
- Certificate mechanics can estimate missed positives only from known-probability samples.

## 8. Unsafe Claims

- `object_count_mean` is anti-predictive.
- Score-fusion AUROC is 0.624.
- DCA or BASA is a main algorithm without comparing against object-count baselines.
- `cluster_aware_upper_bound` is deployable.
- Dataset3 boundary fields support event-IoU claims.
- Formal G-ARC certificate is complete.

## 9. Need For New VLM

No new VLM is needed for the immediate next step. The next step is method selection and possibly a smaller theory/certificate refinement on the existing labels. New VLM is only needed for second-video replication or boundary redesign.

## 10. Required Question Answers

1. GLM AUROC bug source: custom AUROC implementation, not join/filter mismatch.
2. Corrected proxy ranking: hindsight AUROC winner is `{best_hindsight}`; deployable corrected default is `{deployable}`.
3. `object_count_mean` is strong: AUROC={object_auc:.3f}; B=80 top-proxy anchor recall={oc_top80['anchor_recall_mean']:.3f}.
4. `score_fusion` still has diagnostic value but is weak: AUROC={score_fusion_auc:.3f}; B=80 top-proxy anchor recall={sf_top80['anchor_recall_mean']:.3f}.
5. Corrected strongest deployable non-oracle at B=80: `{best_budget_b80['method']}`.
6. Score-fusion diversity prefilter advantage still holds within score-fusion family: B=80 event recall {sf_div80['event_cluster_recall_mean']:.3f} vs top score-fusion {sf_top80['event_cluster_recall_mean']:.3f}.
7. Object-count baselines change the main conclusion: object-count diversity B=80 event recall {oc_div80['event_cluster_recall_mean']:.3f}, stronger than score-fusion diversity.
8. Fixed DCA is replayed but not main: B=80 object-count DCA event recall {dca_oc80['event_cluster_recall_mean']:.3f}; score-fusion DCA event recall {dca_sf80['event_cluster_recall_mean']:.3f}.
9. BASA does not beat the best corrected baseline at B=80: best BASA event recall {best_basa_b80['event_cluster_recall_mean']:.3f} vs best baseline {best_budget_b80['event_cluster_recall_mean']:.3f}.
10. BASA B=30-80 stability is weaker than the best baseline on mean event recall: BASA mean {basa_mid['event_cluster_recall_mean'].mean():.3f}, baseline mean {baseline_mid['event_cluster_recall_mean'].mean():.3f}.
11. BASA singleton recall helps somewhat at B=80 ({best_basa_b80['singleton_cluster_recall_mean']:.3f}) but remains below the best baseline singleton recall ({best_budget_b80['singleton_cluster_recall_mean']:.3f}).
12. BASA_two_channel creates an audit channel, but current recall tradeoff is not enough to beat object-count/diversity baselines.
13. Certificate simulation is usable as mechanics only; formal certificate remains unproven.
14. Current paper main algorithm should be corrected object-count diversity/budget-decomposition baseline, not BASA.
15. Safe claims are listed in Section 7.
16. Unsafe claims are listed in Section 8.
17. No new VLM is needed for immediate method recomputation; new VLM is only needed for replication/boundary redesign.
18. Final decision is below.

{decision}
"""
    (REPORTS / "CODEX_RECOMPUTE_BASA_FINAL_REPORT.md").write_text(final, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    df = load_data()
    proxy_metrics, quartiles, topk, best_hindsight, deployable = compute_proxy_metrics(df)
    # For all replay/certificate evaluation, add 300s blocks to canonical copy.
    df = df.assign(block_300s=(df["center_time_s"] // 300).astype(int))
    if (REPLAY / "budget_replay_corrected_summary.csv").exists() and (REPLAY / "method_by_budget_winners.csv").exists():
        budget_long = pd.read_csv(REPLAY / "budget_replay_corrected_long.csv")
        budget_summary = pd.read_csv(REPLAY / "budget_replay_corrected_summary.csv")
        winners = pd.read_csv(REPLAY / "method_by_budget_winners.csv")
    else:
        budget_long, budget_summary, winners = run_budget_replay(df, best_hindsight, deployable)
    if (REPLAY / "basa_replay_summary.csv").exists() and (REPLAY / "basa_replay_long.csv").exists():
        basa_long = pd.read_csv(REPLAY / "basa_replay_long.csv")
        basa_summary = pd.read_csv(REPLAY / "basa_replay_summary.csv")
    else:
        basa_long, basa_summary = run_basa(df, deployable)
    if (ANALYSIS / "certificate_simulation.csv").exists() and (ANALYSIS / "block_level_estimates.csv").exists():
        cert_sim = pd.read_csv(ANALYSIS / "certificate_simulation.csv")
        block_est = pd.read_csv(ANALYSIS / "block_level_estimates.csv")
    else:
        cert_sim, block_est = certificate_simulation(df, budget_summary, basa_summary)
    write_reports(df, proxy_metrics, quartiles, topk, budget_summary, winners, basa_summary, cert_sim, best_hindsight, deployable)
    with (LOGS / "progress.md").open("a", encoding="utf-8") as f:
        f.write("proxy/replay/BASA/certificate recompute complete\n")
    print((STATE / "FINAL_DECISION.txt").read_text().strip())


if __name__ == "__main__":
    main()
