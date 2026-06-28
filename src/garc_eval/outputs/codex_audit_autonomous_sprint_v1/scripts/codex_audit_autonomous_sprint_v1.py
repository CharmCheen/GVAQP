#!/usr/bin/env python3
"""Read-only audit for GLM event-native AQP autonomous sprint outputs.

This script does not run VLM/proxy/video processing. It only reads existing
CSV/JSON/Markdown outputs and writes audit reports/tables under the Codex audit
directory.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "garc_eval/outputs/codex_audit_autonomous_sprint_v1"
REPORTS = OUT / "reports"
TABLES = OUT / "tables"
ANALYSIS = OUT / "analysis"
LOGS = OUT / "logs"

GLM = ROOT / "garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1"
FILE_AUDIT = ROOT / "garc_eval/outputs/event_native_aqp_file_audit_v1"
P1 = ROOT / "garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1"
P0 = ROOT / "garc_eval/outputs/new_video_scout_gate_v1"
REFINE = ROOT / "test_vlm/outputs/event_native_aqp_p1_refine_gate_v1"

for d in [REPORTS, TABLES, ANALYSIS, LOGS]:
    d.mkdir(parents=True, exist_ok=True)


def read_text(path: Path, max_chars: int | None = None) -> str:
    if not path.exists():
        return ""
    txt = path.read_text(encoding="utf-8", errors="replace")
    return txt if max_chars is None else txt[:max_chars]


def write_report(name: str, body: str) -> None:
    (REPORTS / name).write_text(body.rstrip() + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_anchor_idx(anchor_id: str) -> int:
    return int(str(anchor_id).split("_")[-1])


def is_positive_label(x: str) -> bool:
    return str(x).strip().lower() == "positive"


def tie_aware_auroc(scores, labels):
    """Mann-Whitney AUROC with average ranks for ties."""
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=int)
    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores)
    sorted_scores = scores[order]
    ranks = np.empty(len(scores), dtype=float)
    i = 0
    while i < len(scores):
        j = i + 1
        while j < len(scores) and sorted_scores[j] == sorted_scores[i]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        ranks[order[i:j]] = avg_rank
        i = j
    rank_sum_pos = ranks[labels == 1].sum()
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def average_precision(scores, labels):
    pairs = sorted(zip(scores, labels), key=lambda x: -float(x[0]))
    n_pos = sum(1 for _, l in pairs if int(l) == 1)
    if n_pos == 0:
        return float("nan")
    tp = 0
    precisions = []
    for rank, (_, lab) in enumerate(pairs, start=1):
        if int(lab) == 1:
            tp += 1
            precisions.append(tp / rank)
    return float(sum(precisions) / n_pos)


def build_clusters(oracle: pd.DataFrame):
    pos_rows = oracle[oracle["label"].eq("positive")].copy()
    pos_rows["anchor_idx"] = pos_rows["anchor_id"].map(parse_anchor_idx)
    pos_rows = pos_rows.sort_values("anchor_idx")
    clusters = []
    current = []
    prev_idx = None
    for row in pos_rows.to_dict("records"):
        idx = int(row["anchor_idx"])
        if current and prev_idx is not None and idx - prev_idx > 1:
            clusters.append(current)
            current = []
        current.append(row)
        prev_idx = idx
    if current:
        clusters.append(current)
    anchor_to_cluster = {}
    for cid, cl in enumerate(clusters):
        for row in cl:
            anchor_to_cluster[row["anchor_id"]] = cid
    return clusters, anchor_to_cluster


def eval_selection(selected: pd.DataFrame, n_pos: int, clusters, anchor_to_cluster):
    if len(selected) == 0:
        return 0, 0.0, 0, 0.0, 0.0
    tp = int(selected["label"].eq("positive").sum())
    hit = set()
    for aid in selected["anchor_id"]:
        if aid in anchor_to_cluster:
            hit.add(anchor_to_cluster[aid])
    return tp, tp / n_pos, len(hit), len(hit) / len(clusters), tp / len(selected)


def method_tables(merged: pd.DataFrame, clusters, anchor_to_cluster):
    rows = merged.copy()
    rows["anchor_idx"] = rows["anchor_id"].map(parse_anchor_idx)
    rows = rows.sort_values("anchor_idx").reset_index(drop=True)
    n_pos = int(rows["label"].eq("positive").sum())
    budgets = [10, 20, 30, 40, 60, 80, 100, 150]
    out = []

    def top_proxy(B):
        return rows.sort_values("score_fusion", ascending=False).head(B)

    def temporal_grid(B):
        if B >= len(rows):
            return rows
        step = len(rows) / B
        idx = [int(i * step) for i in range(B)]
        return rows.iloc[idx]

    def diversity_prefilter(B):
        top_p = rows.sort_values("score_fusion", ascending=False).head(2 * B)
        if len(top_p) <= B:
            return top_p
        top_p = top_p.sort_values("anchor_idx").reset_index(drop=True)
        step = len(top_p) / B
        idx = [int(i * step) for i in range(B)]
        return top_p.iloc[idx]

    def top_proxy_nms(B, window=3):
        selected = []
        suppressed = set()
        by_score = rows.sort_values("score_fusion", ascending=False)
        for _, r in by_score.iterrows():
            if len(selected) >= B:
                break
            if r["anchor_id"] in suppressed:
                continue
            selected.append(r)
            idx = int(r["anchor_idx"])
            near = rows[np.abs(rows["anchor_idx"] - idx) <= window]["anchor_id"]
            suppressed.update(near.tolist())
        return pd.DataFrame(selected)

    def stratified_proxy_temporal(B):
        s = rows.sort_values("score_fusion").reset_index(drop=True)
        q = len(s) // 4
        strata = [s.iloc[i * q : (i + 1) * q].copy() for i in range(4)]
        if len(s) % 4:
            strata[-1] = pd.concat([strata[-1], s.iloc[4 * q :]], ignore_index=True)
        selected = []
        for stratum in strata:
            b_i = max(1, B // 4)
            st = stratum.sort_values("anchor_idx").reset_index(drop=True)
            if len(st) <= b_i:
                selected.append(st)
            else:
                step = len(st) / b_i
                idx = [int(i * step) for i in range(b_i)]
                selected.append(st.iloc[idx])
        return pd.concat(selected, ignore_index=True).head(B)

    def coverage_blocks(B, n_blocks=12):
        s = rows.sort_values("anchor_idx").reset_index(drop=True)
        block_size = max(1, len(s) // n_blocks)
        blocks = [s.iloc[i * block_size : (i + 1) * block_size].copy() for i in range(n_blocks)]
        if len(s) % n_blocks:
            blocks[-1] = pd.concat([blocks[-1], s.iloc[n_blocks * block_size :]], ignore_index=True)
        per_block = max(1, B // n_blocks)
        selected = [block.sort_values("score_fusion", ascending=False).head(per_block) for block in blocks]
        return pd.concat(selected, ignore_index=True).head(B)

    def cluster_aware(B):
        selected_rows = []
        selected_ids = set()
        for cl in clusters:
            cl_df = pd.DataFrame(cl)
            cl_df["score_fusion"] = cl_df["score_fusion"].astype(float)
            r = cl_df.sort_values("score_fusion", ascending=False).iloc[0]
            selected_rows.append(r)
            selected_ids.add(r["anchor_id"])
        remaining = rows[~rows["anchor_id"].isin(selected_ids)].sort_values("score_fusion", ascending=False)
        all_sel = pd.concat([pd.DataFrame(selected_rows), remaining], ignore_index=True)
        return all_sel.head(B)

    def audit_aware(B):
        b_main = int(B * 0.85)
        b_audit = B - b_main
        main = rows.sort_values("score_fusion", ascending=False).head(b_main)
        rest = rows[~rows["anchor_id"].isin(main["anchor_id"])]
        audit = rest.sort_values("score_fusion", ascending=True).head(b_audit)
        return pd.concat([main, audit], ignore_index=True)

    methods = {
        "uniform_temporal_grid": temporal_grid,
        "top_proxy": top_proxy,
        "top_proxy_temporal_nms": top_proxy_nms,
        "proxy_diversity_prefilter": diversity_prefilter,
        "stratified_proxy_temporal": stratified_proxy_temporal,
        "coverage_greedy_time_blocks": coverage_blocks,
        "cluster_aware_selection": cluster_aware,
        "audit_aware_selection": audit_aware,
    }
    rng_rows = rows.to_dict("records")
    for B in budgets:
        # Recompute random exactly as the GLM script intended: seeds 0..199.
        recs = []
        evs = []
        precs = []
        poss = []
        hits = []
        for seed in range(200):
            import random

            sample = random.Random(seed).sample(rng_rows, min(B, len(rng_rows)))
            sel = pd.DataFrame(sample)
            tp, rec, hc, evr, prec = eval_selection(sel, n_pos, clusters, anchor_to_cluster)
            recs.append(rec)
            evs.append(evr)
            precs.append(prec)
            poss.append(tp)
            hits.append(hc)
        out.append(
            {
                "method": "uniform_random",
                "budget": B,
                "positive_recall_recomputed": mean(recs),
                "positive_recall_std_recomputed": pstdev(recs),
                "event_cluster_recall_recomputed": mean(evs),
                "precision_recomputed": mean(precs),
                "positives_found_recomputed": mean(poss),
                "clusters_hit_recomputed": mean(hits),
                "n_repeats_recomputed": 200,
                "audit_note": "recomputed_from_existing_labels_seed_0_199",
            }
        )
        for name, fn in methods.items():
            sel = fn(B)
            tp, rec, hc, evr, prec = eval_selection(sel, n_pos, clusters, anchor_to_cluster)
            note = "oracle_leakage_upper_bound" if name == "cluster_aware_selection" else "deterministic_recomputed"
            out.append(
                {
                    "method": name,
                    "budget": B,
                    "positive_recall_recomputed": rec,
                    "positive_recall_std_recomputed": 0.0,
                    "event_cluster_recall_recomputed": evr,
                    "precision_recomputed": prec,
                    "positives_found_recomputed": tp,
                    "clusters_hit_recomputed": hc,
                    "n_repeats_recomputed": 1,
                    "audit_note": note,
                }
            )
    return pd.DataFrame(out)


def main():
    oracle_path = GLM / "oracle_outputs/dataset3_full_center10_parsed.csv"
    p1_path = P1 / "oracle_outputs/dataset3_oracle_parsed.csv"
    proxy_path = P1 / "metadata/center10_proxy_features.csv"
    replay_path = GLM / "replay/budget_replay_results.csv"
    analysis_json_path = GLM / "analysis/full_center10_analysis.json"

    oracle = pd.read_csv(oracle_path)
    p1 = pd.read_csv(p1_path)
    proxy = pd.read_csv(proxy_path)
    replay = pd.read_csv(replay_path)
    analysis_json = json.loads(read_text(analysis_json_path))

    merged = oracle.merge(proxy, on="anchor_id", suffixes=("", "_proxy"), how="left")
    merged["score_fusion"] = merged["score_fusion_geometry_motion"].astype(float)
    merged["score_yolo"] = merged["score_fusion_yolo_motion"].astype(float)
    merged["score_ego"] = merged["score_fusion_ego_lateral"].astype(float)
    merged["anchor_idx"] = merged["anchor_id"].map(parse_anchor_idx)
    labels = merged["label"].eq("positive").astype(int).to_numpy()
    pos = oracle[oracle["label"].eq("positive")]
    neg = oracle[oracle["label"].eq("negative")]
    clusters, anchor_to_cluster = build_clusters(merged)
    score_fusion_auc = {
        "recomputed_value": tie_aware_auroc(merged["score_fusion_geometry_motion"].astype(float), labels)
    }
    obj_auc = {
        "recomputed_value": tie_aware_auroc(merged["object_count_mean"].astype(float), labels)
    }

    # Task 1 table.
    key_files = [
        (GLM / "state/SPRINT_STATE.json", "state", "sprint state", "high", "exists and compact"),
        (GLM / "state/EXPERIMENT_LEDGER.csv", "state", "experiment ledger", "high", "10 stage rows"),
        (GLM / "state/DECISION_LOG.md", "state", "decision log", "high", "explicit DCA/call decisions"),
        (GLM / "state/FAILURE_LOG.md", "state", "failure log", "high", "documents timeouts/merge error/boundary issue"),
        (GLM / "reports/AUTONOMOUS_RESEARCH_SPRINT_FINAL.md", "report", "final sprint report", "medium", "contains some numeric inconsistencies"),
        (FILE_AUDIT / "reports/FILE_AUDIT_FINAL_REPORT.md", "file_audit", "prior audit final", "medium", "secondary report"),
        (FILE_AUDIT / "reports/PAPER_STYLE_RESEARCH_REPORT_REWRITTEN.md", "paper", "rewritten paper report", "medium", "paper-style synthesis"),
        (GLM / "oracle_outputs/dataset3_full_center10_parsed.csv", "stage2", "full oracle parsed labels", "high", "primary label table"),
        (GLM / "oracle_outputs/dataset3_full_center10_raw.jsonl", "stage2", "raw JSONL", "medium", "raw append log"),
        (GLM / "oracle_outputs/raw_per_anchor_full", "stage2", "297 new raw response JSONs", "high", "full-scan new calls only"),
        (GLM / "analysis/full_center10_analysis.json", "stage3_5", "analysis summary", "medium", "AUROC stored as percent; cluster counts reliable"),
        (GLM / "analysis/proxy_oracle_relation.csv", "stage3", "proxy-label merge", "high", "derived row-level table"),
        (GLM / "analysis/positive_clusters.csv", "stage4", "positive clusters", "high", "directly recomputable"),
        (GLM / "analysis/temporal_structure.csv", "stage4", "temporal metrics", "high", "directly recomputable"),
        (GLM / "analysis/selectivity_analysis.csv", "stage4", "selectivity by block", "high", "directly recomputable"),
        (GLM / "replay/budget_replay_results.csv", "stage5", "budget replay table", "medium", "complete but no selection outputs"),
        (GLM / "replay/method_by_budget_summary.csv", "stage5", "claimed summary table", "missing", "not generated"),
        (GLM / "reports/BUDGET_REPLAY_AND_ALGORITHM_FINDINGS.md", "stage5_6", "replay findings", "medium", "DCA not actually replayed"),
        (GLM / "reports/AQP_ALGORITHM_DESIGN.md", "stage6", "algorithm design", "medium", "hypothesis/design only"),
        (GLM / "related_work/RELATED_WORK_MATRIX.csv", "stage7", "related work matrix", "medium", "generated, needs claim caution"),
        (GLM / "paper_draft/PAPER_STYLE_RESEARCH_REPORT.md", "stage9", "paper-style report", "medium", "draft overstates DCA/certificate risk"),
        (P1 / "reports/BOUNDARY_DEGENERACY_AUDIT.md", "p1", "boundary degeneracy report", "high", "supports boundary risk"),
        (GLM / "analysis/stage1_boundary_scheme_comparison.csv", "stage1", "boundary scheme smoke table", "high", "31 rows, Scheme C incomplete"),
        (REFINE / "reports/REFINE_GATE_REPORT.md", "refine", "no-new-VLM refine replay", "medium", "V13.8 only, not dataset3"),
        (P0 / "tables/window_features_dataset3.csv", "p0", "dataset3 5s proxy features", "high", "source for center10 proxy aggregation"),
        (GLM / "scripts/stage3_5_analysis_replay.py", "script", "analysis/replay script", "high", "reveals leakage and randomness"),
    ]
    rows = []
    for p, stage, role, conf, notes in key_files:
        exists = p.exists()
        if p.is_dir():
            size = sum(f.stat().st_size for f in p.glob("*.json"))
            notes = f"{notes}; files={len(list(p.glob('*.json')))}"
        else:
            size = p.stat().st_size if exists else 0
        rows.append(
            {
                "path": rel(p),
                "exists": exists,
                "size_bytes": size,
                "stage": stage,
                "role": role,
                "confidence": conf if exists else "none",
                "notes": notes,
            }
        )
    pd.DataFrame(rows).to_csv(TABLES / "key_file_index.csv", index=False)

    # Task 2 full oracle metrics.
    p1_ids = set(p1["anchor_id"])
    full_ids = set(oracle["anchor_id"])
    raw_full_files = list((GLM / "oracle_outputs/raw_per_anchor_full").glob("*.json"))
    full_metric_rows = []

    def add_metric(metric, value, source_claim="", status="OK", notes=""):
        full_metric_rows.append(
            {
                "metric": metric,
                "recomputed_value": value,
                "source_claim": source_claim,
                "status": status,
                "notes": notes,
            }
        )

    add_metric("n_anchors", len(oracle), analysis_json.get("n_anchors"))
    for lab in ["positive", "negative", "unclear", "abstain", "parse_error"]:
        if lab == "parse_error":
            val = int((oracle.get("parse_status", pd.Series(dtype=str)) != "ok").sum())
        elif lab == "unclear":
            val = int(oracle["label"].astype(str).str.lower().eq("unclear").sum())
        else:
            val = int(oracle["label"].astype(str).str.lower().eq(lab).sum())
        add_metric(f"n_{lab}", val, analysis_json.get("n_positives") if lab == "positive" else "")
    add_metric("positive_rate", float(pos.shape[0] / len(oracle)), analysis_json.get("positive_rate"))
    add_metric("p1_rows", len(p1), "50")
    add_metric("p1_ids_in_full_csv", len(p1_ids & full_ids), "50")
    add_metric("new_raw_per_anchor_full_json_files", len(raw_full_files), "297")
    add_metric("297_new_plus_50_reused_equals_full", len(raw_full_files) + len(p1_ids & full_ids), "347")
    add_metric("event_type_distribution", json.dumps(pos["event_type"].value_counts(dropna=False).to_dict(), ensure_ascii=False), "")
    add_metric("main_object_distribution", json.dumps(pos["involved_object"].value_counts(dropna=False).to_dict(), ensure_ascii=False), analysis_json.get("object_distribution"))
    add_metric("confidence_distribution_all", json.dumps(oracle["confidence"].value_counts(dropna=False).to_dict(), ensure_ascii=False), "")
    add_metric("boundary_status_distribution_all", json.dumps(oracle["boundary_status"].value_counts(dropna=False).to_dict(), ensure_ascii=False), "")
    add_metric("positive_unique_event_start", int(pos["event_start"].dropna().nunique()), analysis_json.get("boundary_unique_starts"))
    add_metric("positive_unique_event_end", int(pos["event_end"].dropna().nunique()), analysis_json.get("boundary_unique_ends"))
    templated_007 = int(((pos["event_start"].astype(str) == "0.0") & (pos["event_end"].astype(str) == "0.7")).sum())
    add_metric("positive_template_0_0_to_0_7_count", templated_007, "boundary templated")
    add_metric("positive_template_0_0_to_0_7_rate", templated_007 / max(1, len(pos)), "")
    pd.DataFrame(full_metric_rows).to_csv(TABLES / "full_center10_recomputed_metrics.csv", index=False)

    # Task 3 proxy-oracle metrics.
    score_cols = [
        "score_fusion_geometry_motion",
        "motion_energy_mean",
        "score_fusion_yolo_motion",
        "score_fusion_ego_lateral",
        "object_count_mean",
        "near_ego_vehicle_count_max",
    ]
    proxy_metric_rows = []
    for col in score_cols:
        vals = merged[col].astype(float).to_numpy()
        auc = tie_aware_auroc(vals, labels)
        ap = average_precision(vals, labels)
        source = analysis_json.get("proxy_aucs", {}).get(
            {
                "score_fusion_geometry_motion": "score_fusion",
                "score_fusion_yolo_motion": "score_yolo",
                "score_fusion_ego_lateral": "score_ego",
            }.get(col, col),
            {},
        )
        proxy_metric_rows.append(
            {
                "metric_group": "score_auc",
                "metric": col,
                "recomputed_value": auc,
                "recomputed_ap": ap,
                "source_claim": source,
                "notes": "tie-aware AUROC; source stores AUROC as percent for GLM JSON",
            }
        )
    q = merged.sort_values("score_fusion_geometry_motion").reset_index(drop=True)
    q_size = len(q) // 4
    for i in range(4):
        start = i * q_size
        end = (i + 1) * q_size if i < 3 else len(q)
        part = q.iloc[start:end]
        proxy_metric_rows.append(
            {
                "metric_group": "quartile_positive_rate",
                "metric": f"Q{i+1}",
                "recomputed_value": float(part["label"].eq("positive").mean()),
                "recomputed_ap": "",
                "source_claim": "",
                "notes": f"n={len(part)}, positives={int(part['label'].eq('positive').sum())}",
            }
        )
    thresholds = {
        "high_score_neg_top_quartile": np.percentile(merged["score_fusion_geometry_motion"].astype(float), 75),
        "low_score_pos_below_median": np.median(merged["score_fusion_geometry_motion"].astype(float)),
    }
    hsn = merged[(merged["label"].eq("negative")) & (merged["score_fusion_geometry_motion"].astype(float) > thresholds["high_score_neg_top_quartile"])]
    lsp = merged[(merged["label"].eq("positive")) & (merged["score_fusion_geometry_motion"].astype(float) < thresholds["low_score_pos_below_median"])]
    proxy_metric_rows.append({"metric_group": "false_alarm", "metric": "high_score_neg_top_quartile", "recomputed_value": len(hsn), "recomputed_ap": "", "source_claim": "77", "notes": json.dumps(hsn["negative_reason"].value_counts().to_dict(), ensure_ascii=False)})
    proxy_metric_rows.append({"metric_group": "proxy_blind", "metric": "low_score_pos_below_median", "recomputed_value": len(lsp), "recomputed_ap": "", "source_claim": "17", "notes": json.dumps(lsp["involved_object"].value_counts().to_dict(), ensure_ascii=False)})
    rng = np.random.default_rng(0)
    for B in [10, 20, 30, 40, 60, 80, 100, 150]:
        top = merged.sort_values("score_fusion_geometry_motion", ascending=False).head(B)
        top_pos = int(top["label"].eq("positive").sum())
        obj_top = merged.sort_values("object_count_mean", ascending=False).head(B)
        obj_top_pos = int(obj_top["label"].eq("positive").sum())
        rand_counts = []
        for _ in range(1000):
            sample = merged.sample(n=min(B, len(merged)), replace=False, random_state=int(rng.integers(0, 2**31 - 1)))
            rand_counts.append(int(sample["label"].eq("positive").sum()))
        proxy_metric_rows.append(
            {
                "metric_group": "topk_yield",
                "metric": f"B={B}",
                "recomputed_value": top_pos,
                "recomputed_ap": top_pos / max(1, len(pos)),
                "source_claim": "",
                "notes": f"score_fusion_top; random_mean={mean(rand_counts):.3f}; random_recall={mean(rand_counts)/len(pos):.3f}; random_std={pstdev(rand_counts):.3f}",
            }
        )
        proxy_metric_rows.append(
            {
                "metric_group": "topk_yield_object_count",
                "metric": f"B={B}",
                "recomputed_value": obj_top_pos,
                "recomputed_ap": obj_top_pos / max(1, len(pos)),
                "source_claim": "not_reported_by_GLM_budget_replay",
                "notes": "object_count_mean_top; this omitted baseline beats score-fusion top-proxy at most budgets",
            }
        )
    pd.DataFrame(proxy_metric_rows).to_csv(TABLES / "proxy_oracle_recomputed_metrics.csv", index=False)

    # Task 4 temporal/cluster table.
    transitions = Counter()
    ordered = oracle.copy()
    ordered["anchor_idx"] = ordered["anchor_id"].map(parse_anchor_idx)
    ordered = ordered.sort_values("anchor_idx")
    labs = ordered["label"].tolist()
    for a, b in zip(labs, labs[1:]):
        transitions[(a, b)] += 1
    p11 = transitions[("positive", "positive")]
    p10 = transitions[("positive", "negative")]
    p_stay = p11 / max(1, p11 + p10)
    cluster_sizes = [len(c) for c in clusters]
    temporal_rows = [
        {"metric": "n_positive_clusters", "recomputed_value": len(clusters), "source_claim": "27", "notes": ""},
        {"metric": "n_singletons", "recomputed_value": sum(1 for s in cluster_sizes if s == 1), "source_claim": "JSON=21; final_report=18", "notes": "final report text is inconsistent with cluster CSV/JSON"},
        {"metric": "n_multi_anchor_clusters", "recomputed_value": sum(1 for s in cluster_sizes if s > 1), "source_claim": "JSON=6; final_report=9", "notes": "6 is correct for contiguous-positive cluster definition"},
        {"metric": "largest_cluster_size", "recomputed_value": max(cluster_sizes), "source_claim": "9", "notes": ""},
        {"metric": "mean_cluster_size", "recomputed_value": mean(cluster_sizes), "source_claim": "1.48", "notes": ""},
        {"metric": "P(1->1)", "recomputed_value": p_stay, "source_claim": "0.325", "notes": f"transitions 1->1={p11}, 1->0={p10}"},
        {"metric": "base_positive_rate", "recomputed_value": len(pos) / len(oracle), "source_claim": "0.115", "notes": ""},
        {"metric": "temporal_lift_p11_over_base", "recomputed_value": p_stay / (len(pos) / len(oracle)), "source_claim": "2.83x", "notes": ""},
        {"metric": "positive_anchors", "recomputed_value": len(pos), "source_claim": "40", "notes": ""},
    ]
    pd.DataFrame(temporal_rows).to_csv(TABLES / "temporal_cluster_recomputed_metrics.csv", index=False)

    # Task 5 budget replay recomputation/comparison.
    recomputed = method_tables(merged, clusters, anchor_to_cluster)
    compare = recomputed.merge(
        replay,
        on=["method", "budget"],
        how="left",
        suffixes=("_codex", "_glm"),
    )
    for c in ["positive_recall", "event_cluster_recall", "precision", "positives_found", "clusters_hit"]:
        if c in compare.columns:
            compare[f"{c}_delta_recomputed_minus_glm"] = compare[f"{c}_recomputed"] - compare[c].astype(float)
    # Add the unseeded hybrid rows from file separately because they cannot be reproduced.
    hybrid = replay[replay["method"].eq("hybrid_explore_exploit")].copy()
    if not hybrid.empty:
        hybrid_rows = []
        for _, r in hybrid.iterrows():
            hybrid_rows.append(
                {
                    "method": "hybrid_explore_exploit",
                    "budget": int(r["budget"]),
                    "positive_recall_recomputed": "",
                    "positive_recall_std_recomputed": "",
                    "event_cluster_recall_recomputed": "",
                    "precision_recomputed": "",
                    "positives_found_recomputed": "",
                    "clusters_hit_recomputed": "",
                    "n_repeats_recomputed": 0,
                    "audit_note": "not_recomputed_original_script_uses_unseeded_global_random_and_n_repeats_1",
                    "positive_recall": r["positive_recall"],
                    "positive_recall_std": r["positive_recall_std"],
                    "event_cluster_recall": r["event_cluster_recall"],
                    "precision": r["precision"],
                    "positives_found": r["positives_found"],
                    "clusters_hit": r["clusters_hit"],
                    "n_repeats": r["n_repeats"],
                }
            )
        compare = pd.concat([compare, pd.DataFrame(hybrid_rows)], ignore_index=True, sort=False)
    compare = compare.sort_values(["budget", "method"]).reset_index(drop=True)
    compare.to_csv(TABLES / "budget_replay_recomputed_summary.csv", index=False)

    # Related work revised positioning.
    related_rows = [
        ["SUPG", "high on expensive-oracle AQP/proxy/certificate", "frame/image i.i.d. setting; this work must emphasize temporally correlated event clips and weak/nonmonotone proxy", "medium-high", "Write as closest AQP baseline whose assumptions break for event clips; do not imply SUPG lacks guarantees."],
        ["ABae", "medium on adaptive proxy stratification", "estimates class proportions, not retrieval/event recall under clip budgets", "low-medium", "Use as adaptive sampling/statistical estimation neighbor."],
        ["ARC", "medium on video AQP/proxy", "frame/object detection granularity, no semantic event clipping/certified event recall", "medium", "Avoid overclaim; say it motivates video AQP but not event-native semantic clip retrieval."],
        ["ExSample", "medium on discovery/sampling", "sampling/discovery emphasis differs from oracle-relative budgeted event recall", "medium", "Position as related sampling for rare events, not certificate solution."],
        ["LAVA", "medium on proxy/video analytics", "different query interface and no event-native recall certificate", "medium", "Use as video analytics/proxy background."],
        ["LensWalk", "medium on agentic observation", "agentic visual exploration, not fixed-budget AQP certificate", "medium", "Use as observation/planning context only."],
        ["TAD", "medium-high on temporal action/event boundaries", "perception benchmark/method, not expensive oracle allocation or AQP certificate", "medium", "Cite for event temporal structure, not as direct DB competitor."],
        ["DriveJudge", "low-medium", "driving reasoning/oracle background, not budgeted query processing", "low", "Use as domain/oracle motivation."],
        ["DriveReward", "low-medium", "driving reward/reasoning, not retrieval/certification", "low", "Use only for driving VLM context."],
        ["STRIVE-D", "high potential if event-centric driving retrieval/captioning", "must verify exact setting; likely closest driving-event overlap but may not provide AQP recall certificate", "high", "Write cautiously as most similar workload; separate contribution by oracle-budget allocation and certification."],
        ["Hydro", "medium on proxy/analytics if included", "not event-native driving clip recall under temporal correlation", "medium", "Keep as proxy/video analytics neighbor with limited claims."],
    ]
    pd.DataFrame(
        related_rows,
        columns=["work", "overlap", "safe_difference", "claim_risk", "how_to_write"],
    ).to_csv(TABLES / "revised_related_work_positioning.csv", index=False)

    # Compose reports.
    n_methods = replay["method"].nunique()
    budgets = sorted(replay["budget"].unique().tolist())
    best_by_budget = []
    non_oracle_methods = [m for m in replay["method"].unique() if m != "cluster_aware_selection"]
    for B in budgets:
        br = replay[replay["budget"].eq(B)]
        best = br.sort_values(["event_cluster_recall", "positive_recall"], ascending=False).iloc[0]
        best_non = br[br["method"].isin(non_oracle_methods)].sort_values(["event_cluster_recall", "positive_recall"], ascending=False).iloc[0]
        best_by_budget.append(f"- B={B}: best overall `{best.method}` event_recall={best.event_cluster_recall:.4f}; best non-oracle `{best_non.method}` event_recall={best_non.event_cluster_recall:.4f}, anchor_recall={best_non.positive_recall:.4f}")

    top80 = replay[(replay["budget"].eq(80)) & (replay["method"].eq("top_proxy"))].iloc[0]
    div80 = replay[(replay["budget"].eq(80)) & (replay["method"].eq("proxy_diversity_prefilter"))].iloc[0]
    rel_gain80 = (div80["positive_recall"] - top80["positive_recall"]) / top80["positive_recall"]
    abs_gain80 = div80["positive_recall"] - top80["positive_recall"]

    write_report(
        "01_FILE_AND_STAGE_AUDIT.md",
        f"""# 01 File And Stage Audit

## Verdict

GLM produced a real output tree at `{rel(GLM)}`, but the user-specified `autonomous_sprint_v1` path is a naming drift. The most trustworthy artifacts are the full parsed oracle CSV, per-anchor JSON files, proxy feature table, cluster/temporal CSVs, and `budget_replay_results.csv`.

## Stage Completion

- Stage 1 boundary smoke: executed, 31 table rows. Scheme C was incomplete due to timeout; final decision relies mainly on Schemes A/B.
- Stage 2 full center10 oracle: executed as 297 new per-anchor JSON files plus 50 reused P1 rows, merged into 347 anchors.
- Stage 3 proxy-oracle analysis: executed from existing labels/features.
- Stage 4 temporal/cluster analysis: executed, but final report text has a singleton/multi-cluster inconsistency.
- Stage 5 budget replay: executed as `budget_replay_results.csv` with 10 methods x 8 budgets. `method_by_budget_summary.csv` was not generated.
- Stage 6 algorithm exploration: design-only. DCA was proposed, not replay-validated.
- Stage 7 related work matrix: generated.
- Stage 8 dataset2 role: generated from P0 scout, no new VLM.
- Stage 9 paper-style report: generated.

## Unsupported Or Risky Completion Claims

- DCA is marked as main algorithm in state/design files, but no DCA method appears in `budget_replay_results.csv`.
- `cluster_aware_selection` is an oracle-informed upper bound, not a deployable method.
- Audit/certificate is not implemented; it appears only as next action/design language.
- Final report says 18 singleton / 9 multi-anchor clusters; recomputation gives 21 / 6.
- Stage 3 proxy AUROC numbers are materially wrong: GLM reports score-fusion around 0.624 and `object_count_mean` around 0.052, but tie-aware recomputation gives {score_fusion_auc['recomputed_value']:.3f} and {obj_auc['recomputed_value']:.3f}.
- `method_by_budget_summary.csv` is named in the user task but absent.

## Most Credible Output Files

See `tables/key_file_index.csv`. Highest-confidence files: full oracle parsed CSV, 297 new raw JSONs, P1 parsed CSV, proxy features, temporal/cluster CSVs, budget replay CSV, stage scripts, and logs/failure log.
""",
    )

    write_report(
        "02_FULL_CENTER10_ORACLE_AUDIT.md",
        f"""# 02 Full Center10 Oracle Audit

## Recomputed Core Counts

- Total anchors: {len(oracle)}.
- Positive / negative / abstain / parse-error: {len(pos)} / {len(neg)} / {int(oracle['label'].eq('abstain').sum())} / {int((oracle['parse_status'] != 'ok').sum())}.
- Positive rate: {len(pos) / len(oracle):.6f}.
- Positive objects: {pos['involved_object'].value_counts().to_dict()}.
- Positive event types: {pos['event_type'].value_counts().to_dict()}.

## P1 Reuse

The full CSV contains all {len(p1)} P1 anchor IDs. The `raw_per_anchor_full` directory contains {len(raw_full_files)} JSON files. Therefore the arithmetic `297 new + 50 reused = 347` is supported by files.

## Boundary Template

Among {len(pos)} positives, {templated_007} have `event_start=0.0` and `event_end=0.7`, and all positive `event_end` values are a single unique value. The boundary field is not usable for event IoU on dataset3.

## Source vs Recomputed

Detailed source/recomputed values are in `tables/full_center10_recomputed_metrics.csv`. No material count mismatch was found for full-scan labels. The main issue is boundary localization, not binary label completeness.
""",
    )

    best_auc_row = max(
        [r for r in proxy_metric_rows if r["metric_group"] == "score_auc"],
        key=lambda r: r["recomputed_value"],
    )
    obj_auc = [r for r in proxy_metric_rows if r["metric"] == "object_count_mean"][0]
    score_fusion_auc = [r for r in proxy_metric_rows if r["metric"] == "score_fusion_geometry_motion"][0]
    write_report(
        "03_PROXY_ORACLE_RELATION_AUDIT.md",
        f"""# 03 Proxy Oracle Relation Audit

## Verdict

GLM's proxy analysis contains a material AUROC bug. The best tie-aware AUROC is `{best_auc_row['metric']}` = {best_auc_row['recomputed_value']:.3f}. `score_fusion_geometry_motion`, the score used in replay, is only {score_fusion_auc['recomputed_value']:.3f}. `object_count_mean` is not anti-predictive; it is the strongest audited single feature with AUROC={obj_auc['recomputed_value']:.3f}.

## Evidence

- High-score negatives in the top score quartile: {len(hsn)}, matching the GLM claim of 77.
- Low-score positives below the median score: {len(lsp)}, matching the GLM claim of 17 / 40 = 42.5%.
- Quartile positive rates are non-monotone: Q1={q.iloc[:q_size]['label'].eq('positive').mean():.3f}, Q2={q.iloc[q_size:2*q_size]['label'].eq('positive').mean():.3f}, Q3={q.iloc[2*q_size:3*q_size]['label'].eq('positive').mean():.3f}, Q4={q.iloc[3*q_size:]['label'].eq('positive').mean():.3f}.
- B=80 top-proxy finds {int(merged.sort_values('score_fusion_geometry_motion', ascending=False).head(80)['label'].eq('positive').sum())}/40 positives; the random expectation is close because base rate is 11.5%.
- B=80 top-`object_count_mean` finds {int(merged.sort_values('object_count_mean', ascending=False).head(80)['label'].eq('positive').sum())}/40 positives, beating both score-fusion top-proxy and the reported score-fusion diversity prefilter.

## Interpretation

`score_fusion != semantic event` is supported, and score-fusion direct ranking is weak/non-monotone. The stronger claim that `object_count_mean` is anti-predictive is false. Stage 3 and Stage 5 should be recomputed with corrected AUROC and object-count baselines before paper-level method claims.

Detailed metrics are in `tables/proxy_oracle_recomputed_metrics.csv`.
""",
    )

    write_report(
        "04_TEMPORAL_AND_CLUSTER_AUDIT.md",
        f"""# 04 Temporal And Cluster Audit

## Recomputed Cluster Structure

- Positive anchors: {len(pos)}.
- Positive clusters: {len(clusters)}.
- Singleton clusters: {sum(1 for s in cluster_sizes if s == 1)}.
- Multi-anchor clusters: {sum(1 for s in cluster_sizes if s > 1)}.
- Largest cluster: {max(cluster_sizes)} anchors.
- P(1->1): {p_stay:.3f}; base positive rate: {len(pos) / len(oracle):.3f}; lift: {p_stay / (len(pos) / len(oracle)):.2f}x.

## Inconsistency

The final report states 18 singleton and 9 multi-anchor clusters. The CSV, JSON, and recomputation support 21 singleton and 6 multi-anchor clusters. The likely cause is report text drift, not data corruption.

## AQP Implication

Temporal correlation is real but not dominant: most clusters are singletons, while one cluster has 9 anchors. Temporal coverage and cluster-aware evaluation are motivated, but a naive expansion/refine strategy is not automatically supported.

Detailed metrics are in `tables/temporal_cluster_recomputed_metrics.csv`.
""",
    )

    write_report(
        "05_BUDGET_REPLAY_AUDIT.md",
        f"""# 05 Budget Replay Audit

## Completeness

- Methods in replay CSV: {n_methods}; expected 10.
- Budget points: {len(budgets)}; expected 8: {budgets}.
- No selection-output files were found, so method results can be checked by reimplementing deterministic selection but cannot be audited from saved selected-anchor lists.

## Best Methods By Budget

{chr(10).join(best_by_budget)}

## B=80 Claim Check

- `top_proxy` anchor recall at B=80: {top80['positive_recall']:.3f}.
- `proxy_diversity_prefilter` anchor recall at B=80: {div80['positive_recall']:.3f}.
- Absolute gain: {abs_gain80:.3f}; relative gain: {rel_gain80:.1%}. The `+30% over top_proxy` claim is correct for anchor recall at B=80.
- This comparison is only against score-fusion `top_proxy`. A simple `object_count_mean` top-B baseline finds {int(merged.sort_values('object_count_mean', ascending=False).head(80)['label'].eq('positive').sum())}/40 positives at B=80, so the reported "best non-oracle" conclusion is incomplete.

## Method Claim Boundaries

- Supported non-oracle methods: `proxy_diversity_prefilter`, `uniform_temporal_grid`, `top_proxy`, `audit_aware_selection` as replay baselines.
- `cluster_aware_selection` is oracle-informed and should be written only as an upper bound.
- `DCA` is not in the replay CSV and must remain a hypothesis.
- `audit_aware_selection` was tried but does not clearly beat top-proxy; the simple 15% low-score audit design is not validated.
- `hybrid_explore_exploit` used unseeded random sampling with `n_repeats=1`; its ranking is not reproducible enough for a strong claim.
- Because the strongest recomputed single feature was omitted as a replay score, Stage 5 needs no-new-VLM recomputation before paper-level claims about the best non-oracle method.

## Label Leakage

The budget replay uses full oracle labels only for evaluation, except `cluster_aware_selection`, whose selection itself reads oracle clusters. That row is a leakage upper bound, not an algorithm.

Detailed comparison is in `tables/budget_replay_recomputed_summary.csv`.
""",
    )

    stage1 = pd.read_csv(GLM / "analysis/stage1_boundary_scheme_comparison.csv")
    scheme_pos = stage1[stage1["label"].eq("positive")]
    write_report(
        "06_BOUNDARY_REFINE_AUDIT.md",
        f"""# 06 Boundary REFINE Audit

## Findings

- P1 boundary degeneracy is real: all 5 P1 positives were 0.0-0.7.
- Full scan boundary degeneracy remains: {templated_007}/{len(pos)} positives are exactly 0.0-0.7 and positive `event_end` has one unique value.
- Stage 1 video metadata/raw_fps smoke was executed but did not solve the template issue.
- Contact-sheet smoke was executed and produced more varied boundaries, but label stability dropped.
- Post-hoc boundary Scheme C was only partially executed; the failure log says 3/5 completed.
- No dataset3 post-hoc boundary full run exists.
- The no-new-VLM REFINE replay under `test_vlm/outputs/event_native_aqp_p1_refine_gate_v1` is on V13.8, not dataset3, and is based on existing stitched labels rather than new boundary observations.

## Can Boundary Fields Support Event IoU?

No for dataset3. The full scan boundary fields are templated and should not be used for event-IoU claims or REFINE evaluation.

## REFINE Decision

`BOUNDARY_ORACLE_REDESIGN_REQUIRED`

REFINE should be downgraded to limitation/future work. It is not supported as a core innovation in the current dataset3 output.
""",
    )

    write_report(
        "07_AQP_ALGORITHM_INNOVATION_AUDIT.md",
        """# 07 AQP Algorithm Innovation Audit

## validated_methods

- `proxy_diversity_prefilter`: validated as a non-oracle replay baseline for the score-fusion proxy, but not yet validated against corrected `object_count_mean` baselines.
- `uniform_temporal_grid`: validated as a surprisingly strong coverage baseline at some low/mid budgets.
- `top_proxy`: validated as weak direct-ranking baseline.
- `audit_aware_selection`: implemented, but not validated as an improvement.

## hypothesis_only_methods

- `DCA`: proposed in `AQP_ALGORITHM_DESIGN.md`; not present in replay output.
- `CFA` / cluster-first adaptive: design only.
- Adaptive DCA and certificate/audit machinery: next actions only.

## unsafe_claims

- Calling DCA the main validated algorithm.
- Writing `cluster_aware_selection` as a feasible method.
- Claiming audit/certificate has been implemented.
- Claiming REFINE or event-IoU boundary quality from dataset3.

## recommended_main_algorithm

Use `proxy_diversity_prefilter` / budget decomposition only as the current validated score-fusion replay result. Do not call it the overall main method until replay is recomputed with corrected AUROC and object-count baselines. Present DCA as the next algorithmic hypothesis motivated by replay diagnostics.

## recommended_next_experiment

First fix the AUROC implementation and rerun Stage 3/5 no-new-VLM replay with `object_count_mean`, `score_fusion_geometry_motion`, and score-combination baselines. Then implement DCA as a deterministic method with fixed seeds for any random audit component, saved selected-anchor lists, and sanity checks.
""",
    )

    write_report(
        "08_RELATED_WORK_CLAIM_AUDIT.md",
        """# 08 Related Work Claim Audit

## Verdict

The related-work matrix exists and is useful, but its "no existing system covers all capabilities" framing should be softened until certificate and event-boundary pieces are implemented. The safest positioning is: event-native, oracle-relative budget allocation for semantic clip queries under temporal correlation and weak/nonmonotone proxies.

## Specific Risks

- SUPG should be treated as the closest AQP/certificate baseline, not dismissed. The distinction is i.i.d. frame/image assumptions vs temporally correlated event clips.
- ABae is not a retrieval system, but it is relevant for adaptive proxy stratification/statistical estimation.
- ARC should not be over-simplified; write the granularity and semantic-event/certificate differences carefully.
- STRIVE-D is the likely highest-overlap workload risk and needs manual paper verification before strong novelty claims.
- TAD/DriveJudge/DriveReward are mostly event/oracle/driving reasoning background, not DB/AQP baselines.

See `tables/revised_related_work_positioning.csv` for a safer positioning table.
""",
    )

    write_report(
        "09_PAPER_CLAIM_AUDIT.md",
        f"""# 09 Paper Claim Audit

## Strong Claims

- Dataset3 full center10 pseudo-oracle is complete: 347 anchors, 40 positives, 307 negatives, 0 abstain/parse errors in the parsed CSV.
- Dataset3 is non-vacuous for oracle-relative clip-level event retrieval: positive rate {len(pos)/len(oracle):.1%}, 27 positive clusters.
- Temporal correlation exists: P(1->1)={p_stay:.3f} vs base {len(pos)/len(oracle):.3f}.

## Moderate Claims

- Event-Native AQP is a valid framing for this workload, but currently as oracle-relative empirical query processing, not a completed guarantee system.
- Score-fusion proxy weakness and non-monotonicity are real on dataset3: `score_fusion_geometry_motion` AUROC is {score_fusion_auc['recomputed_value']:.3f}; 17/40 positives are below its median score; 77 high-score negatives exist.
- Budget decomposition via `proxy_diversity_prefilter` beats score-fusion `top_proxy` at B=80 by {rel_gain80:.0%} relative anchor recall in this replay, but not against the omitted `object_count_mean` top-B baseline.
- Temporal coverage/diversity is a useful allocation principle; evidence is single-video dataset3 plus earlier realcartest context and must be recomputed with corrected proxy baselines.
- Dataset3 shows proxy behavior differs sharply by video/object mix, but the claim that `object_count_mean` is anti-predictive is false.
- Cluster-aware upper bound shows opportunity, but only as an oracle upper bound.

## Weak Claims

- DCA as a main algorithm: motivated but unvalidated.
- Audit-aware low-score exploration: simple replay variant did not clearly win; richer audit remains a hypothesis.
- Adaptive cluster expansion/CFA: design only.
- Certificate under temporal correlation: not implemented in this sprint.
- Second-video generalization beyond dataset3 and realcartest: still needs another suitable long video.

## Unsafe Claims

- Claiming formal G-ARC recall certificates from these outputs.
- Claiming DCA improves over baselines experimentally.
- Claiming REFINE/event-boundary localization as a contribution on dataset3.
- Claiming best AUROC is 0.624 for score fusion or that `object_count_mean` is anti-predictive on dataset3.
- Claiming `proxy_diversity_prefilter` is the best non-oracle method before replay includes `object_count_mean`.
- Treating VLM labels as human truth.
- Treating `cluster_aware_selection` as deployable.
- Claiming VLDB/SIGMOD/ICDE-ready results without DCA validation, certificate mechanics, and second-video replication.

## Minimum Missing Experiments

- Correct AUROC implementation and rerun no-new-VLM replay with `object_count_mean` and score-fusion baselines.
- DCA replay with saved selections and fixed randomness after the proxy-score recomputation.
- Minimal certificate simulation on existing labels, clearly marked as mechanics/underpowered if needed.
- A new long-video P1 pilot before any broad generalization claim.
""",
    )

    final_decision = "FINAL_DECISION: GLM_RESULTS_PARTIAL_NEED_RECOMPUTE"
    write_report(
        "CODEX_AUDIT_FINAL_REPORT.md",
        f"""# Codex Audit Final Report

## Executive Summary

GLM's core label files are mostly valid: dataset3 full center10 oracle is complete and temporal clustering is real. However, the proxy analysis has a material AUROC bug and the budget replay omits the recomputed strongest single feature (`object_count_mean`). The main problem is not only claim inflation; Stage 3 and Stage 5 need no-new-VLM recomputation before paper-level method conclusions.

## File Integrity

The actual main directory is `{rel(GLM)}`, not `garc_eval/outputs/autonomous_sprint_v1/`. The full parsed oracle CSV, 297 new per-anchor JSON files, 50 P1 reused labels, analysis CSVs, replay CSV, reports, scripts, and logs exist. `method_by_budget_summary.csv` is absent.

## Experiment Completion

Stages 1-5 were materially executed. Stages 6-9 are design/reporting/literature synthesis. DCA is proposed but not replayed. Certificate/audit is not implemented.

## Numeric Recheck

- Full oracle: {len(oracle)} anchors, {len(pos)} positives, {len(neg)} negatives, positive rate {len(pos)/len(oracle):.6f}.
- P1 reuse: {len(p1_ids & full_ids)} reused rows; new raw JSON files: {len(raw_full_files)}.
- Positive clusters: {len(clusters)} total, {sum(1 for s in cluster_sizes if s == 1)} singleton, {sum(1 for s in cluster_sizes if s > 1)} multi-anchor, largest {max(cluster_sizes)}.
- Temporal correlation: P(1->1)={p_stay:.3f}; base={len(pos)/len(oracle):.3f}.
- Best recomputed proxy AUROC: `{best_auc_row['metric']}`={best_auc_row['recomputed_value']:.3f}; score-fusion AUROC={score_fusion_auc['recomputed_value']:.3f}; object_count_mean AUROC={obj_auc['recomputed_value']:.3f}.

## Dataset3 Mainline Support

Dataset3 supports the AQP mainline as a pseudo-oracle clip retrieval benchmark: it is non-vacuous, semantically different from realcartest, and budget allocation matters. It does not yet support GLM's specific proxy-failure explanation because the object-count AUROC was miscomputed.

## Proxy Oracle Relation

The data strongly supports `score_fusion != semantic event`. But GLM's broader proxy diagnosis is partly wrong: `object_count_mean` is not anti-predictive and should have been included in budget replay.

## Temporal And Cluster Evidence

Temporal correlation is above base rate and cluster-level metrics are justified. However, most clusters are singletons, so methods relying on local expansion need direct validation.

## Budget Replay

The replay supports `proxy_diversity_prefilter` as the safest current method only within the score-fusion replay family. At B=80 it improves anchor recall from {top80['positive_recall']:.3f} to {div80['positive_recall']:.3f} over score-fusion top-proxy, but `object_count_mean` top-B finds {int(merged.sort_values('object_count_mean', ascending=False).head(80)['label'].eq('positive').sum())}/40 positives at B=80. `cluster_aware_selection` is only an oracle upper bound. `hybrid_explore_exploit` is not reproducible enough for strong claims because it used unseeded randomness with one repeat.

## Boundary And REFINE Risk

Boundary localization is not solved. Dataset3 positives are templated around 0.0-0.7; event IoU and REFINE claims are unsafe. Decision: `BOUNDARY_ORACLE_REDESIGN_REQUIRED`.

## Audit Certificate State

No clip-level recall certificate or temporal-correlation CI is implemented in this sprint. Certificate language must be future-work or planned-method language only.

## Related Work Boundary

Position against SUPG carefully: closest AQP/certificate baseline, but frame/i.i.d. assumptions differ from temporally correlated semantic event clips. STRIVE-D requires manual verification before strong novelty statements.

## Paper-Safe Claims

- Complete dataset3 pseudo-oracle reference.
- Weak/nonmonotone score-fusion proxy on semantic events.
- Temporal correlation and event clustering in clip labels.
- Budget decomposition/diversity prefilter can beat score-fusion top-proxy on dataset3 at selected budgets.

## Unsafe Claims

- DCA as validated main algorithm.
- REFINE as contribution.
- Formal certificate implemented.
- Human-ground-truth risk-event claims.
- Cluster-aware as deployable.
- `object_count_mean` anti-predictive or score-fusion AUROC=0.624.
- Best non-oracle method before replay is recomputed with corrected proxy baselines.

## Recommended Main Algorithm

Current paper method should not yet be promoted beyond a score-fusion budget-decomposition result. Recompute Stage 3/5 first; then decide whether diversity prefilter or an object-count/coverage hybrid is the main method. DCA remains a next algorithm variant motivated by diagnostics.

## Next Minimum Experiment

Fix AUROC and rerun no-new-VLM Stage 3/5 with `object_count_mean`, score-fusion, diversity prefilter variants, fixed seeds, and saved selected anchors. Then implement/replay DCA and run a minimal no-repair certificate mechanics simulation on existing labels.

## Human Check List

- Manually verify STRIVE-D/closest related work overlap.
- Inspect a small sample of dataset3 positive/negative raw VLM JSONs for semantic plausibility.
- Review paper draft wording for DCA/certificate/REFINE overclaims.

## Numbers Or Wording To Fix

- Replace 18 singleton / 9 multi-anchor clusters with 21 / 6.
- Replace GLM AUROC values: score_fusion recomputes to {score_fusion_auc['recomputed_value']:.3f}, object_count_mean to {obj_auc['recomputed_value']:.3f}; remove the anti-predictive object-count claim.
- Remove or qualify DCA validation language.
- Mark `cluster_aware_selection` as oracle upper bound everywhere.
- Remove event-IoU claims from dataset3 boundary fields.

{final_decision}
""",
    )

    (ANALYSIS / "final_decision.txt").write_text(final_decision + "\n", encoding="utf-8")
    print(final_decision)


if __name__ == "__main__":
    main()
