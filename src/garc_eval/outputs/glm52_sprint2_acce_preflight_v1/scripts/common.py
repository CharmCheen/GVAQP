#!/usr/bin/env python3
"""Shared utilities for Sprint 2 (ACCE preflight + ablation ladder).

No new VLM/LLM/YOLO/CLIP. Reads only existing oracle labels and proxy features.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "garc_eval/outputs/glm52_sprint2_acce_preflight_v1"
TABLES = OUT / "tables"
REPLAY = OUT / "replay"
ANALYSIS = OUT / "analysis"
REPORTS = OUT / "reports"
STATE = OUT / "state"
LOGS = OUT / "logs"
SEL = REPLAY / "selections"

# dataset3 canonical table (347 anchors)
DS3_CANONICAL = ROOT / "garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv"
# realcartest V13.8 oracle labels (399 anchors)
RC_ORACLE = ROOT / "test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv"
# realcartest V13.7 proxy features
RC_PROXY = ROOT / "test_vlm/outputs/v13_7_center10_multi_method_replay_v1/tables/center10_proxy_features.csv"

SEEDS = list(range(200))
BUDGETS = [30, 40, 60, 80, 100, 150]


def ensure_dirs():
    for d in [TABLES, REPLAY, ANALYSIS, REPORTS, STATE, LOGS, SEL]:
        d.mkdir(parents=True, exist_ok=True)


def load_dataset3():
    df = pd.read_csv(DS3_CANONICAL)
    df["is_positive"] = df["is_positive"].astype(str).str.lower().eq("true")
    df["is_singleton_cluster"] = df["is_singleton_cluster"].astype(str).str.lower().eq("true")
    df["is_multi_anchor_cluster"] = df["is_multi_anchor_cluster"].astype(str).str.lower().eq("true")
    return df.sort_values("anchor_index").reset_index(drop=True)


def load_realcartest():
    lab = pd.read_csv(RC_ORACLE)
    proxy = pd.read_csv(RC_PROXY)
    df = lab.merge(proxy, on="anchor_id", how="inner", suffixes=("", "_p"))
    df["is_positive"] = df["label"].astype(str).str.lower().eq("positive")
    df["anchor_index"] = range(len(df))
    df["center_time_s"] = df["anchor_time"].astype(float)
    df["anchor_id"] = df["anchor_id"].astype(str)
    return df.sort_values("anchor_index").reset_index(drop=True)


def tie_aware_auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    mask = ~np.isnan(scores) & ~np.isnan(labels)
    s = scores[mask].astype(float)
    y = labels[mask].astype(int)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(s, method="average")
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def average_precision(scores: np.ndarray, labels: np.ndarray) -> float:
    mask = ~np.isnan(scores) & ~np.isnan(labels)
    s = scores[mask].astype(float)
    y = labels[mask].astype(int)
    n_pos = int(y.sum())
    if n_pos == 0:
        return float("nan")
    order = np.argsort(-s, kind="mergesort")
    ys = y[order]
    tp = np.cumsum(ys)
    prec = tp / np.arange(1, len(ys) + 1)
    return float((prec * ys).sum() / n_pos)


def ci95(values):
    vals = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    if len(vals) <= 1:
        return 0.0
    return float(1.96 * np.std(vals, ddof=1) / math.sqrt(len(vals)))


def pos_clusters(df):
    clusters = {}
    for cid, part in df[df["event_cluster_id"] >= 0].groupby("event_cluster_id"):
        clusters[int(cid)] = set(part["anchor_id"])
    return clusters


def md_table(frame: pd.DataFrame, float_fmt="%.4f") -> str:
    if frame is None or frame.empty:
        return "(empty)"
    cols = [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in frame.iterrows():
        vals = []
        for c in frame.columns:
            v = r[c]
            if isinstance(v, float):
                vals.append(float_fmt % v)
            elif pd.isna(v):
                vals.append("")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def evaluate_selection(df, selected_ids, block_size=300.0):
    """Compute recall metrics for a selected set."""
    selected = df[df["anchor_id"].isin(selected_ids)].copy()
    total_pos = int(df["is_positive"].sum())
    clusters = pos_clusters(df)
    total_clusters = len(clusters)
    singleton_clusters = set(int(c) for c in df[df["is_singleton_cluster"]]["event_cluster_id"].unique()) if "is_singleton_cluster" in df.columns else set()
    multi_clusters = set(int(c) for c in df[df["is_multi_anchor_cluster"]]["event_cluster_id"].unique()) if "is_multi_anchor_cluster" in df.columns else set()
    sel_pos = selected[selected["is_positive"]]
    hit_clusters = set(int(c) for c in sel_pos["event_cluster_id"] if int(c) >= 0) if "event_cluster_id" in sel_pos.columns else set()
    singleton_hit = len(hit_clusters & singleton_clusters)
    multi_hit = len(hit_clusters & multi_clusters)
    sel_pos_count = int(sel_pos["is_positive"].sum())
    # cold-block recall
    blocks = (df["center_time_s"].astype(float) // block_size).astype(int)
    sel_blocks = (selected["center_time_s"].astype(float) // block_size).astype(int)
    # identify cold blocks (positive rate < 5%)
    block_rates = df.groupby(blocks.map(lambda x: int(x)))["is_positive"].mean()
    cold_blocks = set(block_rates[block_rates < 0.05].index)
    cold_pos = int(((df["is_positive"]) & blocks.isin(cold_blocks)).sum())
    sel_cold_pos = int(((selected["is_positive"]) & sel_blocks.isin(cold_blocks)).sum())
    cold_recall = float(sel_cold_pos / cold_pos) if cold_pos > 0 else float("nan")
    return {
        "n_selected": len(selected),
        "positives_found": sel_pos_count,
        "anchor_recall": float(sel_pos_count / total_pos) if total_pos else 0.0,
        "event_cluster_recall": float(len(hit_clusters) / total_clusters) if total_clusters else 0.0,
        "singleton_cluster_recall": float(singleton_hit / max(1, len(singleton_clusters))),
        "multi_anchor_cluster_recall": float(multi_hit / max(1, len(multi_clusters))),
        "precision": float(sel_pos_count / len(selected)) if len(selected) else 0.0,
        "cold_block_recall": cold_recall,
        "cold_block_positives": cold_pos,
    }
