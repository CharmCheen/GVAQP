#!/usr/bin/env python3
"""ARC transfer stress test on real moving-camera video.

Answers: does ARC-style proxy pruning + temporal clustering + oracle
refinement transfer to real dashcam footage?

Four experiment groups:
  1. Proxy candidate upper bound (proxy-only + oracle-refined unlimited)
  2. Budgeted ARC-like refinement
  3. Temporal clustering ablation
  4. Non-candidate miss analysis

Usage:
    python experiments/clip_boundary/run_arc_transfer_stress.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --label-col label_K10 \
        --min-len 15 \
        --budgets 50,100,200,400,800,1200 \
        --seed 42 \
        --out-dir experiments/clip_boundary/arc_transfer_K10
"""

import argparse
import json
import os

import numpy as np
import pandas as pd


# ===========================================================================
# Unified evaluation (identical to prior experiments)
# ===========================================================================
def labels_to_clips(labels, min_len=15):
    clips = []
    start = None
    for i, y in enumerate(labels):
        if y == 1 and start is None:
            start = i
        is_end = (y == 0) or (i == len(labels) - 1)
        if is_end and start is not None:
            end = i - 1 if y == 0 else i
            if end - start + 1 >= min_len:
                clips.append((start, end))
            start = None
    return clips


def clip_iou(a, b):
    s1, e1 = a
    s2, e2 = b
    inter = max(0, min(e1, e2) - max(s1, s2) + 1)
    union = max(e1, e2) - min(s1, s2) + 1
    return inter / union if union > 0 else 0.0


def length_bucket(s, e):
    L = e - s + 1
    if L < 40:
        return "short"
    if L < 100:
        return "medium"
    return "long"


def eval_clips(pred_clips, true_clips, labels):
    """Unified clip evaluation.  label only read here, never in methods."""
    if not true_clips:
        return {"recall": 0.0, "precision": 0.0, "invalid_rate": 0.0,
                "mIoU": 0.0, "num_pred_clips": len(pred_clips),
                "short_recall": 0.0, "medium_recall": 0.0, "long_recall": 0.0,
                "per_clip_hit": []}

    # invalid: predicted clip contains any label==0
    invalid_count = 0
    for s, e in pred_clips:
        for k in range(s, e + 1):
            if labels[k] == 0:
                invalid_count += 1
                break
    invalid_rate = invalid_count / len(pred_clips) if pred_clips else 0.0

    # recall
    hits = []
    for tc in true_clips:
        hit = any(clip_iou(tc, pc) >= 0.5 for pc in pred_clips)
        hits.append(hit)
    recall = sum(hits) / len(true_clips)

    # precision
    prec_hits = 0
    for pc in pred_clips:
        if any(clip_iou(tc, pc) >= 0.5 for tc in true_clips):
            prec_hits += 1
    precision = prec_hits / len(pred_clips) if pred_clips else 0.0

    # mIoU
    ious = []
    for pc in pred_clips:
        best = max((clip_iou(tc, pc) for tc in true_clips), default=0.0)
        ious.append(best)
    mIoU = np.mean(ious) if ious else 0.0

    # length-bucket recall
    buckets = {"short": [], "medium": [], "long": []}
    for i, (s, e) in enumerate(true_clips):
        buckets[length_bucket(s, e)].append(hits[i])
    short_r = np.mean(buckets["short"]) if buckets["short"] else 0.0
    med_r = np.mean(buckets["medium"]) if buckets["medium"] else 0.0
    long_r = np.mean(buckets["long"]) if buckets["long"] else 0.0

    return {
        "recall": recall, "precision": precision, "invalid_rate": invalid_rate,
        "mIoU": mIoU, "num_pred_clips": len(pred_clips),
        "short_recall": short_r, "medium_recall": med_r, "long_recall": long_r,
        "per_clip_hit": hits,
    }


# ===========================================================================
# Oracle wrapper — methods must not read labels directly
# ===========================================================================
class Oracle:
    def __init__(self, labels):
        self._labels = labels
        self.cache = {}
        self.phase_calls = {}

    def query(self, idx, phase="oracle"):
        idx = int(idx)
        if idx not in self.cache:
            self.cache[idx] = int(self._labels[idx])
            self.phase_calls[phase] = self.phase_calls.get(phase, 0) + 1
        return self.cache[idx]

    @property
    def calls(self):
        return len(self.cache)


# ===========================================================================
# Helpers
# ===========================================================================
def merge_pos_frames(pos_frames, gap):
    """Merge sorted positive-frame indices into (start, end) intervals.

    Two frames are in the same segment if their index difference <= gap+1
    (i.e., at most `gap` frames of separation between them).
    """
    if not pos_frames:
        return []
    clips = []
    seg_start = pos_frames[0]
    for j in range(1, len(pos_frames)):
        if pos_frames[j] - pos_frames[j - 1] > gap + 1:
            clips.append((seg_start, pos_frames[j - 1]))
            seg_start = pos_frames[j]
    clips.append((seg_start, pos_frames[-1]))
    return clips


def get_threshold(df, proxy_col, pct):
    """Return threshold for top-pct fraction of a continuous proxy."""
    vals = df[proxy_col].values.astype(float)
    return np.quantile(vals, 1.0 - pct)


def get_candidate_mask(df, proxy_col, threshold_val):
    """Boolean mask of candidate frames from proxy."""
    if proxy_col.startswith("proxy_positive_"):
        return df[proxy_col].values == 1
    return df[proxy_col].values >= threshold_val


def get_candidate_regions(df, proxy_col, threshold_val, gap, min_len=1):
    """Proxy → mask → merge → candidate regions (no min_len filter here)."""
    mask = get_candidate_mask(df, proxy_col, threshold_val)
    pos_frames = sorted(np.where(mask)[0].tolist())
    regions = merge_pos_frames(pos_frames, gap)
    return regions, mask


def region_proxy_mean(df, proxy_col, s, e):
    """Mean proxy score in [s, e]."""
    vals = df[proxy_col].values.astype(float)
    return float(np.mean(vals[s:e + 1]))


# ===========================================================================
# Experiment Group 1: Proxy candidate upper bound
# ===========================================================================
def run_exp1_proxy_only(df, proxy_col, threshold_val, gap, min_len, labels,
                        true_clips, N):
    """A. Proxy-only: candidate regions directly as predicted clips."""
    regions, mask = get_candidate_regions(df, proxy_col, threshold_val, gap)
    pred_clips = [(s, e) for s, e in regions if e - s + 1 >= min_len]
    ev = eval_clips(pred_clips, true_clips, labels)
    return {
        "proxy_col": proxy_col,
        "gap": gap,
        "proxy_only_recall": ev["recall"],
        "proxy_only_precision": ev["precision"],
        "proxy_only_invalid_rate": ev["invalid_rate"],
        "proxy_only_mIoU": ev["mIoU"],
        "proxy_only_num_clips": ev["num_pred_clips"],
        "candidate_frame_fraction": float(mask.sum() / N),
        "num_candidate_regions": len(regions),
    }


def run_exp1_refined_unlimited(df, proxy_col, threshold_val, gap, min_len,
                                labels, true_clips, N):
    """B. Oracle-refined unlimited: dense oracle verify in all regions."""
    regions, mask = get_candidate_regions(df, proxy_col, threshold_val, gap)
    oracle = Oracle(labels)
    pred_clips = []
    for s, e in regions:
        region_pos = []
        for k in range(s, e + 1):
            if oracle.query(k, phase="refine") == 1:
                region_pos.append(k)
        region_clips = merge_pos_frames(region_pos, 0)
        for rc in region_clips:
            if rc[1] - rc[0] + 1 >= min_len:
                pred_clips.append(rc)
    ev = eval_clips(pred_clips, true_clips, labels)
    return {
        "refined_unlimited_recall": ev["recall"],
        "refined_unlimited_precision": ev["precision"],
        "refined_unlimited_invalid_rate": ev["invalid_rate"],
        "refined_unlimited_mIoU": ev["mIoU"],
        "refined_unlimited_num_clips": ev["num_pred_clips"],
        "oracle_frames_needed_for_full_refine": oracle.calls,
    }


def experiment_group_1(df, labels, true_clips, N, min_len):
    """Sweep proxy configs × gaps for upper bound analysis."""
    continuous_cfgs = [
        ("proxy_score", [0.05, 0.10, 0.20, 0.30, 0.40, 0.50]),
        ("proxy_vehicle_count", [0.05, 0.10, 0.20, 0.30, 0.40, 0.50]),
    ]
    binary_cfgs = ["proxy_positive_K5", "proxy_positive_K10",
                    "proxy_positive_K20"]
    gaps = [0, 1, 3, 5, 10, 15, 30]

    rows = []
    total = 0
    for pcol, pcts in continuous_cfgs:
        if pcol not in df.columns:
            continue
        for pct in pcts:
            thr = get_threshold(df, pcol, pct)
            for gap in gaps:
                r1 = run_exp1_proxy_only(df, pcol, thr, gap, min_len,
                                         labels, true_clips, N)
                r2 = run_exp1_refined_unlimited(df, pcol, thr, gap, min_len,
                                                labels, true_clips, N)
                row = {"proxy_col": pcol, "threshold_desc": f"top{int(pct*100)}%"}
                row.update(r1)
                row.update(r2)
                rows.append(row)
                total += 1

    for bcol in binary_cfgs:
        if bcol not in df.columns:
            continue
        for gap in gaps:
            r1 = run_exp1_proxy_only(df, bcol, None, gap, min_len,
                                     labels, true_clips, N)
            r2 = run_exp1_refined_unlimited(df, bcol, None, gap, min_len,
                                            labels, true_clips, N)
            row = {"proxy_col": bcol, "threshold_desc": "binary"}
            row.update(r1)
            row.update(r2)
            rows.append(row)
            total += 1

    print(f"  Group 1: {total} configs done", flush=True)
    return pd.DataFrame(rows)


# ===========================================================================
# Experiment Group 2: Budgeted ARC-like refinement
# ===========================================================================
def run_budgeted_refinement(df, proxy_col, threshold_val, gap, min_len,
                            oracle, budget, N, priority="region_length_desc"):
    """Budgeted ARC-like: proxy candidates → priority sort → budgeted oracle."""
    regions, mask = get_candidate_regions(df, proxy_col, threshold_val, gap)
    if not regions:
        return [], oracle.calls, float(mask.sum() / N)

    # Priority sort
    if priority == "region_length_desc":
        ranked = sorted(regions, key=lambda r: -(r[1] - r[0] + 1))
    elif priority == "proxy_score_desc":
        ranked = sorted(regions,
                        key=lambda r: -region_proxy_mean(df, "proxy_score",
                                                          r[0], r[1]))
    elif priority == "proxy_mean_desc":
        ranked = sorted(regions,
                        key=lambda r: -region_proxy_mean(df, proxy_col,
                                                          r[0], r[1]))
    elif priority == "uncertainty_first":
        # Uncertainty = frames near proxy threshold → sort by |proxy - thr|
        vals = df[proxy_col].values.astype(float) if not proxy_col.startswith(
            "proxy_positive_") else df[proxy_col].values.astype(float)
        thr_val = threshold_val if threshold_val is not None else 0.5
        def uncertainty(r):
            region_vals = vals[r[0]:r[1] + 1]
            return -float(np.mean(np.abs(region_vals - thr_val)))
        ranked = sorted(regions, key=uncertainty)
    else:
        ranked = regions

    # Budgeted oracle refinement
    pred_clips = []
    for s, e in ranked:
        if oracle.calls >= budget:
            break
        region_pos = []
        for k in range(s, e + 1):
            if oracle.calls >= budget:
                break
            if oracle.query(k, phase="refine") == 1:
                region_pos.append(k)
        # Only emit clips from fully-verified sub-regions
        region_clips = merge_pos_frames(region_pos, 0)
        for rc in region_clips:
            if rc[1] - rc[0] + 1 >= min_len:
                pred_clips.append(rc)

    return pred_clips, oracle.calls, float(mask.sum() / N)


def experiment_group_2(df, labels, true_clips, N, min_len, budgets, seed):
    """Budgeted ARC-like refinement on selected configs."""
    # Good configs from exp1 heuristic
    configs = [
        ("proxy_score", 0.30, "top30%", 1),
        ("proxy_score", 0.20, "top20%", 3),
        ("proxy_score", 0.10, "top10%", 5),
        ("proxy_vehicle_count", 0.30, "top30%", 3),
        ("proxy_vehicle_count", 0.20, "top20%", 5),
        ("proxy_vehicle_count", 0.10, "top10%", 10),
    ]
    # Add binary configs
    for bcol in ["proxy_positive_K10", "proxy_positive_K5"]:
        for gap in [3, 5, 10]:
            configs.append((bcol, None, "binary", gap))

    priorities = ["region_length_desc", "proxy_score_desc", "proxy_mean_desc",
                  "uncertainty_first"]

    rows = []
    total = 0
    for budget in budgets:
        for pcol, thr_val, thr_desc, gap in configs:
            if pcol not in df.columns:
                continue
            # Compute threshold for continuous proxies
            if thr_val is not None:
                threshold = get_threshold(df, pcol, thr_val)
            else:
                threshold = None

            for priority in priorities:
                oracle = Oracle(labels)
                pred_clips, calls, cand_frac = run_budgeted_refinement(
                    df, pcol, threshold, gap, min_len, oracle, budget, N,
                    priority)
                ev = eval_clips(pred_clips, true_clips, labels)
                rows.append({
                    "method": "arc_like_budgeted",
                    "proxy_col": pcol,
                    "threshold_desc": thr_desc,
                    "gap": gap,
                    "priority": priority,
                    "budget": budget,
                    "recall": ev["recall"],
                    "precision": ev["precision"],
                    "mIoU": ev["mIoU"],
                    "invalid_rate": ev["invalid_rate"],
                    "oracle_calls": calls,
                    "candidate_frame_fraction": cand_frac,
                    "num_pred_clips": ev["num_pred_clips"],
                    "short_recall": ev["short_recall"],
                    "medium_recall": ev["medium_recall"],
                    "long_recall": ev["long_recall"],
                })
                total += 1

    print(f"  Group 2: {total} runs done", flush=True)
    return pd.DataFrame(rows)


# ===========================================================================
# Experiment Group 3: Temporal clustering ablation
# ===========================================================================
def temporal_cluster_smooth(candidates, proxy_vals, eps):
    """Smooth candidate labels by merging adjacent frames with similar proxy.

    If |proxy[i] - proxy[i-1]| <= eps and either is a candidate,
    mark both as candidate.
    """
    N = len(candidates)
    smoothed = candidates.copy()
    for i in range(1, N):
        if abs(proxy_vals[i] - proxy_vals[i - 1]) <= eps:
            if candidates[i] or candidates[i - 1]:
                smoothed[i] = True
                smoothed[i - 1] = True
    return smoothed


def run_temporal_clustering(df, proxy_col, threshold_val, gap, min_len,
                            labels, true_clips, N, eps=None):
    """Run with optional temporal clustering, return proxy-only + refined."""
    if proxy_col.startswith("proxy_positive_"):
        raw_candidates = (df[proxy_col].values == 1)
        proxy_vals = df[proxy_col].values.astype(float)
    else:
        raw_candidates = (df[proxy_col].values >= threshold_val)
        proxy_vals = df[proxy_col].values.astype(float)

    if eps is not None:
        candidates = temporal_cluster_smooth(raw_candidates, proxy_vals, eps)
    else:
        candidates = raw_candidates

    pos_frames = sorted(np.where(candidates)[0].tolist())
    regions = merge_pos_frames(pos_frames, gap)

    # proxy-only
    pred_proxy = [(s, e) for s, e in regions if e - s + 1 >= min_len]
    ev_proxy = eval_clips(pred_proxy, true_clips, labels)

    # oracle-refined unlimited
    oracle = Oracle(labels)
    pred_refined = []
    for s, e in regions:
        region_pos = []
        for k in range(s, e + 1):
            if oracle.query(k, phase="refine") == 1:
                region_pos.append(k)
        for rc in merge_pos_frames(region_pos, 0):
            if rc[1] - rc[0] + 1 >= min_len:
                pred_refined.append(rc)
    ev_refined = eval_clips(pred_refined, true_clips, labels)

    return {
        "proxy_recall": ev_proxy["recall"],
        "proxy_precision": ev_proxy["precision"],
        "proxy_invalid_rate": ev_proxy["invalid_rate"],
        "refined_recall": ev_refined["recall"],
        "refined_precision": ev_refined["precision"],
        "refined_invalid_rate": ev_refined["invalid_rate"],
        "candidate_frame_fraction": float(candidates.sum() / N),
        "oracle_calls": oracle.calls,
        "num_candidate_regions": len(regions),
    }


def experiment_group_3(df, labels, true_clips, N, min_len):
    """Temporal clustering ablation."""
    proxy_cfgs = [
        ("proxy_score", 0.20, "top20%", 3),
        ("proxy_score", 0.30, "top30%", 5),
        ("proxy_vehicle_count", 0.20, "top20%", 3),
        ("proxy_vehicle_count", 0.30, "top30%", 5),
        ("proxy_positive_K10", None, "binary", 5),
    ]
    eps_values = [None, 0.001, 0.01, 0.05, 0.1]

    rows = []
    total = 0
    for pcol, thr_pct, thr_desc, gap in proxy_cfgs:
        if pcol not in df.columns:
            continue
        thr = get_threshold(df, pcol, thr_pct) if thr_pct is not None else None
        for eps in eps_values:
            r = run_temporal_clustering(df, pcol, thr, gap, min_len,
                                        labels, true_clips, N, eps)
            rows.append({
                "proxy_col": pcol,
                "threshold_desc": thr_desc,
                "gap": gap,
                "with_clustering": eps is not None,
                "eps": eps if eps is not None else 0.0,
                **r,
            })
            total += 1

    print(f"  Group 3: {total} runs done", flush=True)
    return pd.DataFrame(rows)


# ===========================================================================
# Experiment Group 4: Non-candidate miss analysis
# ===========================================================================
def experiment_group_4(df, labels, true_clips, N, min_len, seed):
    """Non-candidate miss analysis + oracle audit probe."""
    proxy_cfgs = [
        ("proxy_score", 0.20, "top20%", 3),
        ("proxy_score", 0.30, "top30%", 5),
        ("proxy_vehicle_count", 0.20, "top20%", 3),
        ("proxy_vehicle_count", 0.30, "top30%", 5),
        ("proxy_positive_K10", None, "binary", 5),
    ]
    audit_budgets = [50, 100, 200, 400]
    rng = np.random.RandomState(seed)

    rows = []
    total = 0
    for pcol, thr_pct, thr_desc, gap in proxy_cfgs:
        if pcol not in df.columns:
            continue
        thr = get_threshold(df, pcol, thr_pct) if thr_pct is not None else None
        regions, mask = get_candidate_regions(df, pcol, thr, gap)

        # Coverage: which true clips overlap with candidate regions?
        covered = []
        missed = []
        for tc_idx, (ts, te) in enumerate(true_clips):
            hit = False
            for rs, re in regions:
                if clip_iou((ts, te), (rs, re)) >= 0.1 or \
                   not (te < rs or ts > re):  # any overlap
                    hit = True
                    break
            if hit:
                covered.append(tc_idx)
            else:
                missed.append(tc_idx)

        missed_clips = [true_clips[i] for i in missed]
        missed_lengths = [e - s + 1 for s, e in missed_clips]

        # Non-candidate positive rate
        non_cand_mask = ~mask
        non_cand_labels = np.array(labels)[non_cand_mask]
        nc_pos_rate = float(non_cand_labels.sum() / len(non_cand_labels)) \
            if len(non_cand_labels) > 0 else 0.0

        # Oracle audit: uniform sample from non-candidate frames
        non_cand_indices = np.where(non_cand_mask)[0]
        audit_hits = {}
        for ab in audit_budgets:
            if len(non_cand_indices) == 0:
                audit_hits[ab] = 0
                continue
            sample_size = min(ab, len(non_cand_indices))
            sampled = rng.choice(non_cand_indices, size=sample_size,
                                 replace=False)
            # Check if sampled frames hit any missed true clip
            hit_missed = set()
            for idx in sampled:
                for mi, (ms, me) in zip(missed, missed_clips):
                    if ms <= idx <= me:
                        hit_missed.add(mi)
            audit_hits[ab] = len(hit_missed)

        rows.append({
            "proxy_col": pcol,
            "threshold_desc": thr_desc,
            "gap": gap,
            "covered_true_clips": len(covered),
            "missed_true_clips": len(missed),
            "total_true_clips": len(true_clips),
            "missed_clip_lengths": json.dumps(missed_lengths),
            "noncandidate_positive_rate": nc_pos_rate,
            "candidate_frame_fraction": float(mask.sum() / N),
            **{f"audit_hit@{ab}": v for ab, v in audit_hits.items()},
        })
        total += 1

    print(f"  Group 4: {total} configs done", flush=True)
    return pd.DataFrame(rows)


# ===========================================================================
# Predicted clips aggregation
# ===========================================================================
def collect_predicted_clips(df, labels, true_clips, N, min_len, budgets, seed):
    """Collect predicted clips from representative configs for output."""
    configs = [
        ("proxy_score", 0.30, "top30%", 1),
        ("proxy_vehicle_count", 0.30, "top30%", 3),
        ("proxy_positive_K10", None, "binary", 5),
    ]
    priorities = ["region_length_desc", "proxy_score_desc"]

    rows = []
    for budget in budgets:
        for pcol, thr_pct, thr_desc, gap in configs:
            if pcol not in df.columns:
                continue
            thr = get_threshold(df, pcol, thr_pct) if thr_pct is not None \
                else None
            for priority in priorities:
                oracle = Oracle(labels)
                pred_clips, calls, _ = run_budgeted_refinement(
                    df, pcol, thr, gap, min_len, oracle, budget, N, priority)
                for ci, (s, e) in enumerate(pred_clips):
                    # Check validity for output
                    valid = all(labels[k] == 1 for k in range(s, e + 1))
                    rows.append({
                        "proxy_col": pcol,
                        "threshold_desc": thr_desc,
                        "gap": gap,
                        "priority": priority,
                        "budget": budget,
                        "clip_id": ci,
                        "start": s,
                        "end": e,
                        "length": e - s + 1,
                        "is_valid": valid,
                        "oracle_calls": calls,
                    })

    return pd.DataFrame(rows)


# ===========================================================================
# Summary markdown
# ===========================================================================
def write_summary_md(out_dir, exp1_df, exp2_df, exp3_df, exp4_df, config):
    lines = ["# ARC Transfer Stress Test Summary\n"]
    lines.append(f"- CSV: `{config['csv']}`")
    lines.append(f"- Label: `{config['label_col']}`")
    lines.append(f"- Frames: {config['num_frames']}")
    lines.append(f"- True clips: {config['num_true_clips']}")
    lines.append(f"- Positive ratio: {config['positive_ratio']:.4f}\n")

    # Group 1 highlights
    lines.append("## Group 1: Proxy Candidate Upper Bound\n")
    if not exp1_df.empty:
        best = exp1_df.sort_values("refined_unlimited_recall",
                                    ascending=False).head(10)
        lines.append("Top 10 by refined_unlimited_recall:\n")
        lines.append("| proxy | thr | gap | proxy_recall | refined_recall | cand_frac | oracle_needed |")
        lines.append("|-------|-----|-----|-------------|---------------|-----------|--------------|")
        for _, r in best.iterrows():
            lines.append(
                f"| {r['proxy_col']} | {r['threshold_desc']} | {int(r['gap'])} | "
                f"{r['proxy_only_recall']:.3f} | {r['refined_unlimited_recall']:.3f} | "
                f"{r['candidate_frame_fraction']:.3f} | "
                f"{int(r['oracle_frames_needed_for_full_refine'])} |")

    # Group 2 highlights
    lines.append("\n## Group 2: Budgeted ARC-like Refinement\n")
    if not exp2_df.empty:
        for budget in sorted(exp2_df["budget"].unique()):
            sub = exp2_df[exp2_df["budget"] == budget]
            best = sub.sort_values("recall", ascending=False).iloc[0]
            lines.append(
                f"- Budget {budget}: best recall={best['recall']:.3f} "
                f"({best['proxy_col']}, {best['priority']}, "
                f"invalid={best['invalid_rate']:.1%})")

    # Group 3 highlights
    lines.append("\n## Group 3: Temporal Clustering Ablation\n")
    if not exp3_df.empty:
        for pcol in exp3_df["proxy_col"].unique():
            sub = exp3_df[exp3_df["proxy_col"] == pcol]
            for thr_desc in sub["threshold_desc"].unique():
                sub2 = sub[sub["threshold_desc"] == thr_desc]
                no_clust = sub2[sub2["with_clustering"] == False]
                best_clust = sub2[sub2["with_clustering"] == True].sort_values(
                    "refined_recall", ascending=False)
                if not no_clust.empty and not best_clust.empty:
                    base = no_clust.iloc[0]["refined_recall"]
                    best = best_clust.iloc[0]["refined_recall"]
                    delta = best - base
                    lines.append(
                        f"- {pcol} {thr_desc}: no-cluster={base:.3f}, "
                        f"best-cluster={best:.3f} (eps={best_clust.iloc[0]['eps']}), "
                        f"delta={delta:+.3f}")

    # Group 4 highlights
    lines.append("\n## Group 4: Non-candidate Miss Analysis\n")
    if not exp4_df.empty:
        for _, r in exp4_df.iterrows():
            lines.append(
                f"- {r['proxy_col']} {r['threshold_desc']} gap={int(r['gap'])}: "
                f"covered={int(r['covered_true_clips'])}/{int(r['total_true_clips'])}, "
                f"missed={int(r['missed_true_clips'])}, "
                f"nc_pos_rate={r['noncandidate_positive_rate']:.3f}, "
                f"audit@200={int(r.get('audit_hit@200', 0))}")

    # Judgments
    lines.append("\n## Judgments\n")
    if not exp1_df.empty:
        best_refined = exp1_df["refined_unlimited_recall"].max()
        if best_refined >= 0.8:
            lines.append("1. **refined_unlimited_recall HIGH** "
                         f"({best_refined:.3f}): ARC candidate generation is "
                         "effective. Main problem is budgeted refinement. "
                         "Research → better oracle allocation.")
        elif best_refined >= 0.5:
            lines.append("1. **refined_unlimited_recall MODERATE** "
                         f"({best_refined:.3f}): ARC candidates cover partial "
                         "ground truth. Both candidate generation and refinement "
                         "need improvement.")
        else:
            lines.append("1. **refined_unlimited_recall LOW** "
                         f"({best_refined:.3f}): Proxy candidates insufficient. "
                         "ARC-style method fails on real video. "
                         "Research → weak proxy / proxy sufficiency / audit.")

    if not exp3_df.empty:
        clustering_effects = []
        for pcol in exp3_df["proxy_col"].unique():
            for thr_desc in exp3_df[exp3_df["proxy_col"] == pcol]["threshold_desc"].unique():
                sub = exp3_df[(exp3_df["proxy_col"] == pcol) &
                              (exp3_df["threshold_desc"] == thr_desc)]
                no_c = sub[sub["with_clustering"] == False]["refined_recall"]
                yes_c = sub[sub["with_clustering"] == True]["refined_recall"]
                if not no_c.empty and not yes_c.empty:
                    clustering_effects.append(yes_c.max() - no_c.iloc[0])
        if clustering_effects:
            avg_effect = np.mean(clustering_effects)
            if avg_effect > 0.02:
                lines.append("2. **Temporal clustering HELPS** "
                             f"(avg {avg_effect:+.3f}): ARC temporal locality "
                             "holds on moving-camera video.")
            elif avg_effect < -0.02:
                lines.append("2. **Temporal clustering HURTS** "
                             f"(avg {avg_effect:+.3f}): Moving-camera destroys "
                             "ARC temporal locality assumption. Key failure mode.")
            else:
                lines.append("2. **Temporal clustering NEUTRAL** "
                             f"(avg {avg_effect:+.3f}): No effect on moving-camera "
                             "video. ARC temporal locality assumption does not "
                             "transfer.")

    if not exp4_df.empty:
        max_audit = max(
            (exp4_df[f"audit_hit@{ab}"].max() for ab in [50, 100, 200, 400]
             if f"audit_hit@{ab}" in exp4_df.columns), default=0)
        max_missed = exp4_df["missed_true_clips"].max()
        if max_missed > 0 and max_audit > 0:
            lines.append("3. **Non-candidate audit FINDS missed clips** "
                         f"(up to {int(max_audit)}/{int(max_missed)}): "
                         "Recall audit has research space under weak proxy.")
        else:
            lines.append("3. **Non-candidate audit finds few missed clips**: "
                         "Proxy blind spots too sparse, audit cost may be high.")

    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ===========================================================================
# Terminal tables
# ===========================================================================
def print_tables(exp1_df, exp2_df, exp3_df, exp4_df, budgets):
    # Table 1: best proxy candidate upper bound
    print()
    print("=" * 120)
    print("TABLE 1: Best Proxy Candidate Upper Bound (top 15 by refined_recall)")
    print("=" * 120)
    hdr = (f"{'config':<40s}  {'proxy_rec':>9s}  {'proxy_prec':>10s}  "
           f"{'proxy_inv':>10s}  {'refined_rec':>11s}  {'refined_prec':>12s}  "
           f"{'cand_frac':>9s}  {'oracle_need':>11s}")
    print(hdr)
    print("-" * len(hdr))
    if not exp1_df.empty:
        top = exp1_df.sort_values("refined_unlimited_recall",
                                   ascending=False).head(15)
        for _, r in top.iterrows():
            cfg = f"{r['proxy_col']} {r['threshold_desc']} g{int(r['gap'])}"
            print(f"  {cfg:<38s}  {r['proxy_only_recall']:>9.3f}  "
                  f"{r['proxy_only_precision']:>10.3f}  "
                  f"{r['proxy_only_invalid_rate']:>10.1%}  "
                  f"{r['refined_unlimited_recall']:>11.3f}  "
                  f"{r['refined_unlimited_precision']:>12.3f}  "
                  f"{r['candidate_frame_fraction']:>9.3f}  "
                  f"{int(r['oracle_frames_needed_for_full_refine']):>11d}")

    # Table 2: budgeted ARC-like
    print()
    print("=" * 120)
    print("TABLE 2: Budgeted ARC-like Refinement (best per budget)")
    print("=" * 120)
    hdr2 = (f"{'config':<50s}  {'budget':>6s}  {'recall':>7s}  "
            f"{'prec':>6s}  {'mIoU':>6s}  {'invalid':>8s}  {'calls':>6s}")
    print(hdr2)
    print("-" * len(hdr2))
    if not exp2_df.empty:
        for budget in budgets:
            sub = exp2_df[exp2_df["budget"] == budget]
            if sub.empty:
                continue
            best = sub.sort_values("recall", ascending=False).head(3)
            for _, r in best.iterrows():
                cfg = (f"{r['proxy_col']} {r['threshold_desc']} "
                       f"g{int(r['gap'])} {r['priority'][:12]}")
                print(f"  {cfg:<48s}  {int(r['budget']):>6d}  "
                      f"{r['recall']:>7.3f}  {r['precision']:>6.3f}  "
                      f"{r['mIoU']:>6.3f}  {r['invalid_rate']:>8.1%}  "
                      f"{int(r['oracle_calls']):>6d}")

    # Table 3: temporal clustering ablation
    print()
    print("=" * 120)
    print("TABLE 3: Temporal Clustering Ablation")
    print("=" * 120)
    hdr3 = (f"{'config':<40s}  {'clust':>5s}  {'eps':>6s}  "
            f"{'proxy_rec':>9s}  {'refined_rec':>11s}  {'prec':>6s}  "
            f"{'invalid':>8s}  {'cand_frac':>9s}")
    print(hdr3)
    print("-" * len(hdr3))
    if not exp3_df.empty:
        for _, r in exp3_df.iterrows():
            cfg = f"{r['proxy_col']} {r['threshold_desc']} g{int(r['gap'])}"
            clust = "Y" if r["with_clustering"] else "N"
            eps_s = f"{r['eps']:.3f}" if r["with_clustering"] else "-"
            print(f"  {cfg:<38s}  {clust:>5s}  {eps_s:>6s}  "
                  f"{r['proxy_recall']:>9.3f}  {r['refined_recall']:>11.3f}  "
                  f"{r['refined_precision']:>6.3f}  "
                  f"{r['refined_invalid_rate']:>8.1%}  "
                  f"{r['candidate_frame_fraction']:>9.3f}")

    # Table 4: non-candidate miss analysis
    print()
    print("=" * 120)
    print("TABLE 4: Non-candidate Miss Analysis")
    print("=" * 120)
    hdr4 = (f"{'config':<35s}  {'covered':>7s}  {'missed':>6s}  "
            f"{'nc_pos':>6s}  {'@50':>5s}  {'@100':>5s}  {'@200':>5s}  {'@400':>5s}")
    print(hdr4)
    print("-" * len(hdr4))
    if not exp4_df.empty:
        for _, r in exp4_df.iterrows():
            cfg = f"{r['proxy_col']} {r['threshold_desc']} g{int(r['gap'])}"
            print(f"  {cfg:<33s}  {int(r['covered_true_clips']):>7d}  "
                  f"{int(r['missed_true_clips']):>6d}  "
                  f"{r['noncandidate_positive_rate']:>6.3f}  "
                  f"{int(r.get('audit_hit@50', 0)):>5d}  "
                  f"{int(r.get('audit_hit@100', 0)):>5d}  "
                  f"{int(r.get('audit_hit@200', 0)):>5d}  "
                  f"{int(r.get('audit_hit@400', 0)):>5d}")


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description="ARC transfer stress test on real video")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--label-col", required=True)
    parser.add_argument("--min-len", type=int, default=15)
    parser.add_argument("--budgets", required=True,
                        help="Comma-separated oracle budgets")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",")]

    # Load data
    df = pd.read_csv(args.csv)
    labels = df[args.label_col].astype(int).tolist()
    N = len(labels)
    true_clips = labels_to_clips(labels, args.min_len)

    print(f"ARC Transfer Stress Test")
    print(f"  CSV: {args.csv}")
    print(f"  Label: {args.label_col}, min_len={args.min_len}")
    print(f"  Frames: {N}, true clips: {len(true_clips)}, "
          f"positive ratio: {sum(labels)/N:.4f}")
    print(f"  Budgets: {budgets}, seed: {args.seed}")
    print(f"  Output: {args.out_dir}")
    print()

    os.makedirs(args.out_dir, exist_ok=True)

    # Run experiment groups
    print("Running experiment groups ...", flush=True)

    exp1_df = experiment_group_1(df, labels, true_clips, N, args.min_len)
    exp2_df = experiment_group_2(df, labels, true_clips, N, args.min_len,
                                 budgets, args.seed)
    exp3_df = experiment_group_3(df, labels, true_clips, N, args.min_len)
    exp4_df = experiment_group_4(df, labels, true_clips, N, args.min_len,
                                 args.seed)

    # Predicted clips
    pred_clips_df = collect_predicted_clips(df, labels, true_clips, N,
                                            args.min_len, budgets, args.seed)

    # Save outputs
    exp1_df.to_csv(os.path.join(args.out_dir,
                                "proxy_candidate_upper_bound.csv"), index=False)
    exp2_df.to_csv(os.path.join(args.out_dir,
                                "arc_like_budgeted.csv"), index=False)
    exp3_df.to_csv(os.path.join(args.out_dir,
                                "temporal_clustering_ablation.csv"), index=False)
    exp4_df.to_csv(os.path.join(args.out_dir,
                                "noncandidate_miss_analysis.csv"), index=False)
    if not pred_clips_df.empty:
        pred_clips_df.to_csv(os.path.join(args.out_dir,
                                          "predicted_clips.csv"), index=False)

    # Config
    config = {
        "csv": os.path.abspath(args.csv),
        "label_col": args.label_col,
        "min_len": args.min_len,
        "budgets": budgets,
        "seed": args.seed,
        "num_frames": N,
        "num_true_clips": len(true_clips),
        "positive_ratio": round(sum(labels) / N, 6),
    }
    with open(os.path.join(args.out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    # Summary markdown
    write_summary_md(args.out_dir, exp1_df, exp2_df, exp3_df, exp4_df, config)

    # Terminal tables
    print_tables(exp1_df, exp2_df, exp3_df, exp4_df, budgets)

    print(f"\nResults saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
