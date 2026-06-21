#!/usr/bin/env python3
"""Bounded auto research: joint allocation generalization + proxy degradation.

Runs Steps 2-5 of the auto research plan:
  - Step 2: Clip distribution probe (filter settings)
  - Step 3: Joint allocation across valid settings
  - Step 4: Proxy degradation (noise + dropout)
  - Step 5: Unified summary

Usage:
    python experiments/clip_boundary/run_auto_research.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --label-col label_K10 \
        --budgets 50,100,200,400,800,1200 \
        --trials 200 \
        --seed 42 \
        --out-dir experiments/clip_boundary/auto_research_joint_allocation
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

# Reuse existing code
sys.path.insert(0, os.path.dirname(__file__))
from run_joint_allocation_kill_exp import (
    labels_to_clips, clip_iou, length_bucket, eval_clips,
    Oracle, merge_pos_frames, pos_frames_to_clips,
    get_threshold, get_candidate_regions, region_proxy_mean,
    run_candidate_only, run_audit_only, run_fixed_mix, run_adaptive_greedy,
)


# ===========================================================================
# Step 2: Setting probe
# ===========================================================================
def probe_settings(df, label_cols, min_lens):
    """Filter settings by clip count and positive ratio."""
    valid = []
    for lc in label_cols:
        if lc not in df.columns:
            continue
        labels = df[lc].astype(int).tolist()
        N = len(labels)
        pos_ratio = sum(labels) / N
        for ml in min_lens:
            clips = labels_to_clips(labels, ml)
            ok = len(clips) >= 5 and 0.02 <= pos_ratio <= 0.6
            status = "VALID" if ok else "FILTERED"
            reason = ""
            if len(clips) < 5:
                reason = f"too few clips ({len(clips)})"
            elif pos_ratio < 0.02:
                reason = f"pos_ratio too low ({pos_ratio:.4f})"
            elif pos_ratio > 0.6:
                reason = f"pos_ratio too high ({pos_ratio:.4f})"
            print(f"  {lc} min_len={ml}: clips={len(clips)}, "
                  f"pos_ratio={pos_ratio:.4f} [{status}]"
                  f"{f' — {reason}' if reason else ''}")
            if ok:
                valid.append({
                    "label_col": lc, "min_len": ml,
                    "true_clip_count": len(clips),
                    "positive_frame_ratio": pos_ratio,
                })
    return valid


# ===========================================================================
# Proxy configs (tight, proven good)
# ===========================================================================
PROXY_CONFIGS = [
    {"proxy_col": "proxy_vehicle_count", "threshold_desc": "top20%",
     "cand_gap": 5},
    {"proxy_col": "proxy_score", "threshold_desc": "top30%",
     "cand_gap": 5},
    {"proxy_col": "proxy_vehicle_count", "threshold_desc": "top30%",
     "cand_gap": 3},
]

CLIP_GAPS = [1, 5, 10, 15, 30]


# ===========================================================================
# Single setting runner
# ===========================================================================
def run_one_setting(df, labels, true_clips, N, min_len, budgets, trials,
                    seed, proxy_configs, setting_label):
    """Run all methods for one setting. Returns rows list."""
    all_rows = []

    for pconf in proxy_configs:
        pcol = pconf["proxy_col"]
        thr_desc = pconf["threshold_desc"]
        cand_gap = pconf["cand_gap"]
        config_label = f"{pcol}_{thr_desc}_g{cand_gap}"

        if thr_desc == "binary":
            threshold_val = None
        else:
            pct = float(thr_desc.replace("top", "").replace("%", "")) / 100
            threshold_val = get_threshold(df, pcol, pct)

        for budget in budgets:
            for t in range(trials):
                # candidate_only (best priority)
                best_cand_recall = -1
                best_cand_row = None
                for priority in ["proxy_mean_desc", "region_length_desc"]:
                    rng = np.random.RandomState(
                        seed + t * 1000 + budget + hash(priority) % 10000)
                    best_d, best_g = None, None
                    for gap in CLIP_GAPS:
                        oracle = Oracle(labels)
                        pred, calls, cc, nc = run_candidate_only(
                            df, pcol, threshold_val, cand_gap, oracle,
                            budget, N, min_len, priority, gap, rng)
                        ev = eval_clips(pred, true_clips, labels)
                        d = {"recall": ev["recall"], "precision": ev["precision"],
                             "invalid_rate": ev["invalid_rate"], "mIoU": ev["mIoU"],
                             "num_pred_clips": ev["num_pred_clips"],
                             "oracle_calls": calls, "candidate_calls": cc,
                             "new_clips_from_candidate": nc}
                        if best_d is None or ev["recall"] > best_d["recall"]:
                            best_d, best_g = d, gap
                    if best_d["recall"] > best_cand_recall:
                        best_cand_recall = best_d["recall"]
                        best_cand_row = {
                            "method": "candidate_only", "setting": setting_label,
                            "proxy_config": config_label, "budget": budget,
                            "trial": t, "best_gap": best_g, **best_d,
                            "audit_calls": 0, "new_clips_from_audit": 0}
                all_rows.append(best_cand_row)

                # audit_only
                rng = np.random.RandomState(seed + t * 1000 + budget + 999)
                best_d, best_g = None, None
                for gap in CLIP_GAPS:
                    oracle = Oracle(labels)
                    pred, calls, ac, nc = run_audit_only(
                        df, pcol, threshold_val, cand_gap, oracle,
                        budget, N, min_len, gap, rng)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"recall": ev["recall"], "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"], "mIoU": ev["mIoU"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls, "audit_calls": ac,
                         "new_clips_from_audit": nc}
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d, best_g = d, gap
                all_rows.append({
                    "method": "audit_only", "setting": setting_label,
                    "proxy_config": config_label, "budget": budget,
                    "trial": t, "best_gap": best_g, **best_d,
                    "candidate_calls": 0, "new_clips_from_candidate": 0})

                # fixed_mix
                for mix_label, cand_frac in [("fixed_mix_80_20", 0.8),
                                              ("fixed_mix_50_50", 0.5)]:
                    rng = np.random.RandomState(
                        seed + t * 1000 + budget + hash(mix_label) % 10000)
                    best_d, best_g = None, None
                    for gap in CLIP_GAPS:
                        oracle = Oracle(labels)
                        pred, calls, cc, ac, nc = run_fixed_mix(
                            df, pcol, threshold_val, cand_gap, oracle,
                            budget, N, min_len, "proxy_mean_desc", gap,
                            rng, cand_frac)
                        ev = eval_clips(pred, true_clips, labels)
                        d = {"recall": ev["recall"], "precision": ev["precision"],
                             "invalid_rate": ev["invalid_rate"], "mIoU": ev["mIoU"],
                             "num_pred_clips": ev["num_pred_clips"],
                             "oracle_calls": calls, "candidate_calls": cc,
                             "audit_calls": ac, "new_clips_from_audit": nc}
                        if best_d is None or ev["recall"] > best_d["recall"]:
                            best_d, best_g = d, gap
                    all_rows.append({
                        "method": mix_label, "setting": setting_label,
                        "proxy_config": config_label, "budget": budget,
                        "trial": t, "best_gap": best_g, **best_d,
                        "new_clips_from_candidate": 0})

                # adaptive_greedy
                rng = np.random.RandomState(seed + t * 1000 + budget + 5555)
                best_d, best_g = None, None
                for gap in CLIP_GAPS:
                    oracle = Oracle(labels)
                    pred, calls, cc, ac, nc = run_adaptive_greedy(
                        df, pcol, threshold_val, cand_gap, oracle,
                        budget, N, min_len, "proxy_mean_desc", gap,
                        rng, batch_size=25)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"recall": ev["recall"], "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"], "mIoU": ev["mIoU"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls, "candidate_calls": cc,
                         "audit_calls": ac, "new_clips_from_audit": nc}
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d, best_g = d, gap
                all_rows.append({
                    "method": "adaptive_greedy", "setting": setting_label,
                    "proxy_config": config_label, "budget": budget,
                    "trial": t, "best_gap": best_g, **best_d,
                    "new_clips_from_candidate": 0})

    return all_rows


# ===========================================================================
# Step 4: Proxy degradation
# ===========================================================================
def degrade_proxy_score(df, proxy_col, noise_std, rng):
    """Add Gaussian noise to proxy scores."""
    vals = df[proxy_col].values.astype(float).copy()
    noise = rng.normal(0, noise_std, size=len(vals))
    return vals + noise


def degrade_proxy_dropout(df, proxy_col, threshold_val, dropout, rng):
    """Randomly drop some proxy-positive frames."""
    if proxy_col.startswith("proxy_positive_"):
        mask = df[proxy_col].values == 1
    else:
        mask = df[proxy_col].values >= threshold_val
    pos_indices = np.where(mask)[0]
    n_drop = int(dropout * len(pos_indices))
    drop_indices = rng.choice(pos_indices, size=n_drop, replace=False)
    mask[drop_indices] = False
    return mask


def run_degraded_candidate_only(df, degraded_vals, proxy_col, threshold_val,
                                 cand_gap, oracle, budget, N, min_len, gap,
                                 rng):
    """Candidate-only with degraded proxy values."""
    if proxy_col.startswith("proxy_positive_"):
        mask = degraded_vals == 1
    elif isinstance(degraded_vals, np.ndarray) and degraded_vals.dtype == bool:
        mask = degraded_vals
    else:
        mask = degraded_vals >= threshold_val

    pos_frames = sorted(np.where(mask)[0].tolist())
    regions = merge_pos_frames(pos_frames, cand_gap)
    if not regions:
        return [], oracle.calls, 0, 0

    ranked = sorted(regions,
                    key=lambda r: -float(np.mean(degraded_vals[r[0]:r[1]+1]))
                    if not proxy_col.startswith("proxy_positive_")
                    else -(r[1] - r[0] + 1))

    pos_before = sorted(oracle.cache.keys())
    all_pos = list(pos_before)
    cc = 0
    for s, e in ranked:
        if cc >= budget:
            break
        for k in range(s, e + 1):
            if cc >= budget:
                break
            if oracle.query(k, phase="candidate_refine") == 1:
                all_pos.append(k)
            cc += 1

    all_pos = sorted(set(all_pos))
    pred_clips = pos_frames_to_clips(all_pos, gap, min_len)
    new_clips = len(set(pos_frames_to_clips(all_pos, gap, min_len)) -
                    set(pos_frames_to_clips(pos_before, gap, min_len)))
    return pred_clips, oracle.calls, cc, new_clips


def run_degraded_fixed_mix(df, degraded_vals, proxy_col, threshold_val,
                            cand_gap, oracle, budget, N, min_len, gap,
                            rng, cand_frac):
    """Fixed mix with degraded proxy."""
    n_cand = max(1, int(cand_frac * budget))
    n_audit = budget - n_cand

    if proxy_col.startswith("proxy_positive_"):
        mask = degraded_vals == 1
    elif isinstance(degraded_vals, np.ndarray) and degraded_vals.dtype == bool:
        mask = degraded_vals
    else:
        mask = degraded_vals >= threshold_val

    pos_frames = sorted(np.where(mask)[0].tolist())
    regions = merge_pos_frames(pos_frames, cand_gap)
    ranked = sorted(regions,
                    key=lambda r: -float(np.mean(degraded_vals[r[0]:r[1]+1]))
                    if not proxy_col.startswith("proxy_positive_")
                    else -(r[1] - r[0] + 1))

    pos_before = sorted(oracle.cache.keys())
    all_pos = list(pos_before)
    cc = 0
    for s, e in ranked:
        if cc >= n_cand:
            break
        for k in range(s, e + 1):
            if cc >= n_cand:
                break
            if oracle.calls >= budget:
                break
            if oracle.query(k, phase="candidate_refine") == 1:
                all_pos.append(k)
            cc += 1

    non_cand = np.where(~mask)[0].tolist()
    already = set(oracle.cache.keys())
    avail = [x for x in non_cand if x not in already]
    sample_size = min(n_audit, len(avail))
    if avail and sample_size > 0:
        sampled = rng.choice(avail, size=sample_size, replace=False)
        for idx in sampled:
            if oracle.query(int(idx), phase="audit") == 1:
                all_pos.append(int(idx))

    all_pos = sorted(set(all_pos))
    pred_clips = pos_frames_to_clips(all_pos, gap, min_len)
    ac = oracle.phase_count("audit")
    return pred_clips, oracle.calls, cc, ac, 0


def run_degraded_adaptive(df, degraded_vals, proxy_col, threshold_val,
                           cand_gap, oracle, budget, N, min_len, gap,
                           rng, batch_size=25):
    """Adaptive greedy with degraded proxy."""
    if proxy_col.startswith("proxy_positive_"):
        mask = degraded_vals == 1
    elif isinstance(degraded_vals, np.ndarray) and degraded_vals.dtype == bool:
        mask = degraded_vals
    else:
        mask = degraded_vals >= threshold_val

    pos_frames = sorted(np.where(mask)[0].tolist())
    non_cand = np.where(~mask)[0].tolist()
    regions = merge_pos_frames(pos_frames, cand_gap)
    ranked = sorted(regions,
                    key=lambda r: -float(np.mean(degraded_vals[r[0]:r[1]+1]))
                    if not proxy_col.startswith("proxy_positive_")
                    else -(r[1] - r[0] + 1))

    cand_frames = []
    for s, e in ranked:
        cand_frames.extend(range(s, e + 1))
    cand_idx = 0
    nc_avail = list(non_cand)
    rng.shuffle(nc_avail)
    nc_idx = 0

    pos_before = sorted(oracle.cache.keys())
    all_pos = list(pos_before)
    yield_cand, yield_audit = 1.0, 0.0

    while oracle.calls < budget:
        do_cand = (yield_cand >= yield_audit) if oracle.calls >= 2 * batch_size \
            else (oracle.calls // batch_size) % 2 == 0

        clips_before = len(pos_frames_to_clips(sorted(set(all_pos)), gap, min_len))
        calls_before = oracle.calls

        if do_cand:
            for _ in range(batch_size):
                if cand_idx >= len(cand_frames) or oracle.calls >= budget:
                    break
                k = cand_frames[cand_idx]; cand_idx += 1
                if oracle.query(k, phase="candidate_refine") == 1:
                    all_pos.append(k)
        else:
            for _ in range(batch_size):
                if nc_idx >= len(nc_avail) or oracle.calls >= budget:
                    break
                k = nc_avail[nc_idx]; nc_idx += 1
                if oracle.query(k, phase="audit") == 1:
                    all_pos.append(k)

        clips_after = len(pos_frames_to_clips(sorted(set(all_pos)), gap, min_len))
        calls_used = max(1, oracle.calls - calls_before)
        marginal = (clips_after - clips_before) / calls_used * 100
        if do_cand:
            yield_cand = marginal
        else:
            yield_audit = marginal

    all_pos = sorted(set(all_pos))
    pred_clips = pos_frames_to_clips(all_pos, gap, min_len)
    cc = oracle.phase_count("candidate_refine")
    ac = oracle.phase_count("audit")
    return pred_clips, oracle.calls, cc, ac, 0


def run_proxy_degradation(df, labels, true_clips, N, min_len, budgets,
                           trials, seed, pconf, setting_label):
    """Run proxy degradation experiments."""
    pcol = pconf["proxy_col"]
    thr_desc = pconf["threshold_desc"]
    cand_gap = pconf["cand_gap"]
    config_label = f"{pcol}_{thr_desc}_g{cand_gap}"

    if thr_desc == "binary":
        threshold_val = None
    else:
        pct = float(thr_desc.replace("top", "").replace("%", "")) / 100
        threshold_val = get_threshold(df, pcol, pct)

    rows = []

    # Degradation variants
    variants = [("clean", None, None)]

    # Noise
    for noise_std in [0.05, 0.1, 0.2]:
        variants.append(("noise", noise_std, None))

    # Dropout
    for dropout in [0.1, 0.3, 0.5]:
        variants.append(("dropout", None, dropout))

    for vtype, param1, param2 in variants:
        variant_name = f"{vtype}" if vtype == "clean" else \
            f"{vtype}_{param1 if param1 is not None else param2}"

        for budget in budgets:
            for t in range(trials):
                rng_base = np.random.RandomState(seed + t * 1000 + budget)

                # Generate degraded proxy
                if vtype == "clean":
                    degraded_vals = df[pcol].values.astype(float)
                    degraded_mask = None
                elif vtype == "noise":
                    degraded_vals = degrade_proxy_score(df, pcol, param1,
                                                        rng_base)
                    degraded_mask = None
                elif vtype == "dropout":
                    degraded_mask = degrade_proxy_dropout(
                        df, pcol, threshold_val, param2, rng_base)
                    degraded_vals = degraded_mask  # pass mask directly

                # candidate_only
                rng = np.random.RandomState(seed + t * 1000 + budget + 111)
                best_d, best_g = None, None
                for gap in CLIP_GAPS:
                    oracle = Oracle(labels)
                    if vtype == "dropout":
                        pred, calls, cc, nc = run_degraded_candidate_only(
                            df, degraded_mask, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng)
                    else:
                        pred, calls, cc, nc = run_degraded_candidate_only(
                            df, degraded_vals, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"recall": ev["recall"], "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls, "candidate_calls": cc}
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d, best_g = d, gap
                rows.append({
                    "method": "candidate_only", "setting": setting_label,
                    "proxy_config": config_label, "proxy_variant": variant_name,
                    "budget": budget, "trial": t, "best_gap": best_g, **best_d,
                    "audit_calls": 0})

                # fixed_mix_80_20
                rng = np.random.RandomState(seed + t * 1000 + budget + 222)
                best_d, best_g = None, None
                for gap in CLIP_GAPS:
                    oracle = Oracle(labels)
                    if vtype == "dropout":
                        pred, calls, cc, ac, _ = run_degraded_fixed_mix(
                            df, degraded_mask, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng, 0.8)
                    else:
                        pred, calls, cc, ac, _ = run_degraded_fixed_mix(
                            df, degraded_vals, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng, 0.8)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"recall": ev["recall"], "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls, "candidate_calls": cc,
                         "audit_calls": ac}
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d, best_g = d, gap
                rows.append({
                    "method": "fixed_mix_80_20", "setting": setting_label,
                    "proxy_config": config_label, "proxy_variant": variant_name,
                    "budget": budget, "trial": t, "best_gap": best_g, **best_d})

                # fixed_mix_50_50
                rng = np.random.RandomState(seed + t * 1000 + budget + 333)
                best_d, best_g = None, None
                for gap in CLIP_GAPS:
                    oracle = Oracle(labels)
                    if vtype == "dropout":
                        pred, calls, cc, ac, _ = run_degraded_fixed_mix(
                            df, degraded_mask, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng, 0.5)
                    else:
                        pred, calls, cc, ac, _ = run_degraded_fixed_mix(
                            df, degraded_vals, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng, 0.5)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"recall": ev["recall"], "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls, "candidate_calls": cc,
                         "audit_calls": ac}
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d, best_g = d, gap
                rows.append({
                    "method": "fixed_mix_50_50", "setting": setting_label,
                    "proxy_config": config_label, "proxy_variant": variant_name,
                    "budget": budget, "trial": t, "best_gap": best_g, **best_d})

                # adaptive_greedy
                rng = np.random.RandomState(seed + t * 1000 + budget + 444)
                best_d, best_g = None, None
                for gap in CLIP_GAPS:
                    oracle = Oracle(labels)
                    if vtype == "dropout":
                        pred, calls, cc, ac, _ = run_degraded_adaptive(
                            df, degraded_mask, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng, 25)
                    else:
                        pred, calls, cc, ac, _ = run_degraded_adaptive(
                            df, degraded_vals, pcol, threshold_val, cand_gap,
                            oracle, budget, N, min_len, gap, rng, 25)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"recall": ev["recall"], "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls, "candidate_calls": cc,
                         "audit_calls": ac}
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d, best_g = d, gap
                rows.append({
                    "method": "adaptive_greedy", "setting": setting_label,
                    "proxy_config": config_label, "proxy_variant": variant_name,
                    "budget": budget, "trial": t, "best_gap": best_g, **best_d})

    return rows


# ===========================================================================
# Step 5: Unified summary
# ===========================================================================
def build_unified_summary(all_rows, setting_info):
    """Build summary.csv from all experiment rows."""
    df = pd.DataFrame(all_rows)

    # Group by setting, proxy_config, proxy_variant (if any), budget, method
    group_cols = ["setting", "proxy_config", "budget", "method"]
    if "proxy_variant" in df.columns:
        group_cols_with_variant = group_cols + ["proxy_variant"]
    else:
        group_cols_with_variant = group_cols

    # Get best proxy_config per setting/budget/method (highest mean recall)
    best_configs = (df.groupby(["setting", "budget", "method"])
                    .agg(mean_recall=("recall", "mean"))
                    .reset_index())
    # For each setting/budget, find best method
    summary_rows = []
    for setting in df["setting"].unique():
        s_df = df[df["setting"] == setting]
        info = [s for s in setting_info if
                f"{s['label_col']}_min{s['min_len']}" == setting][0]

        for budget in s_df["budget"].unique():
            sb_df = s_df[s_df["budget"] == budget]

            # candidate_only best
            cand = sb_df[sb_df["method"] == "candidate_only"]
            if cand.empty:
                continue
            cand_best = cand.sort_values("recall", ascending=False).iloc[0]
            cand_recall = cand_best["recall"]
            cand_prec = cand_best["precision"]
            cand_invalid = cand_best["invalid_rate"]
            cand_calls = cand_best.get("candidate_calls", 0)

            # Best joint method
            joint_methods = ["fixed_mix_80_20", "fixed_mix_50_50",
                             "adaptive_greedy"]
            best_joint = None
            for jm in joint_methods:
                jm_df = sb_df[sb_df["method"] == jm]
                if jm_df.empty:
                    continue
                jm_best = jm_df.sort_values("recall", ascending=False).iloc[0]
                if best_joint is None or jm_best["recall"] > best_joint["recall"]:
                    best_joint = jm_best

            if best_joint is None:
                continue

            summary_rows.append({
                "setting": setting,
                "label_col": info["label_col"],
                "min_len": info["min_len"],
                "true_clip_count": info["true_clip_count"],
                "positive_frame_ratio": info["positive_frame_ratio"],
                "proxy_variant": cand_best.get("proxy_variant", "clean"),
                "proxy_config": cand_best["proxy_config"],
                "budget": budget,
                "candidate_only_recall": cand_recall,
                "candidate_only_precision": cand_prec,
                "candidate_only_invalid": cand_invalid,
                "best_joint_method": best_joint["method"],
                "best_joint_recall": best_joint["recall"],
                "best_joint_precision": best_joint["precision"],
                "best_joint_invalid": best_joint["invalid_rate"],
                "delta_recall": best_joint["recall"] - cand_recall,
                "delta_clip_count": best_joint.get("num_pred_clips", 0) -
                                    cand_best.get("num_pred_clips", 0),
                "candidate_calls": cand_calls,
                "audit_calls": best_joint.get("audit_calls", 0),
            })

    return pd.DataFrame(summary_rows)


def write_final_summary(summary_df, out_dir):
    """Write summary.md with final judgment."""
    lines = ["# Auto Research: Joint Allocation Summary\n"]

    clean = summary_df[summary_df["proxy_variant"] == "clean"]
    degraded = summary_df[summary_df["proxy_variant"] != "clean"]

    # 1. Does joint allocation win stably?
    lines.append("## 1. Does joint allocation win stably?\n")
    if not clean.empty:
        n_settings = clean["setting"].nunique()
        wins = clean[clean["delta_recall"] > 0]
        n_wins = len(wins)
        n_ge5 = len(wins[wins["delta_recall"] >= 0.05])
        n_ge10 = len(wins[wins["delta_recall"] >= 0.10])
        avg_delta = clean["delta_recall"].mean()
        max_delta = clean["delta_recall"].max()
        lines.append(f"- Settings tested: {n_settings}")
        lines.append(f"- Budget-config pairs where joint > candidate: "
                     f"{n_wins}/{len(clean)}")
        lines.append(f"- Delta >= 0.05 recall: {n_ge5}")
        lines.append(f"- Delta >= 0.10 recall: {n_ge10}")
        lines.append(f"- Average delta: {avg_delta:+.3f}")
        lines.append(f"- Max delta: {max_delta:+.3f}")

    # 2. Where does the gain come from?
    lines.append("\n## 2. Where does the gain come from?\n")
    if not clean.empty:
        by_method = (clean.groupby("best_joint_method")["delta_recall"]
                     .agg(["mean", "max", "count"]))
        lines.append("| method | mean_delta | max_delta | count |")
        lines.append("|--------|-----------|-----------|-------|")
        for method, row in by_method.iterrows():
            lines.append(f"| {method} | {row['mean']:+.3f} | "
                         f"{row['max']:+.3f} | {int(row['count'])} |")

    # 3. Weak proxy effect
    lines.append("\n## 3. Weak proxy effect\n")
    if not degraded.empty and not clean.empty:
        clean_avg = clean["delta_recall"].mean()
        for variant in degraded["proxy_variant"].unique():
            v_df = degraded[degraded["proxy_variant"] == variant]
            v_avg = v_df["delta_recall"].mean()
            lines.append(f"- {variant}: avg delta={v_avg:+.3f} "
                         f"(clean={clean_avg:+.3f})")
        # Is degradation increasing the advantage?
        degraded_avg = degraded["delta_recall"].mean()
        if degraded_avg > clean_avg + 0.02:
            lines.append("\n**Weak proxy INCREASES joint advantage.**")
        elif degraded_avg < clean_avg - 0.02:
            lines.append("\n**Weak proxy DECREASES joint advantage.**")
        else:
            lines.append("\n**Weak proxy has NO clear effect on joint advantage.**")

    # 4. Direction judgment
    lines.append("\n## 4. Direction Judgment\n")
    if not clean.empty:
        n_ge10 = len(clean[clean["delta_recall"] >= 0.10])
        max_d = clean["delta_recall"].max()
        avg_d = clean["delta_recall"].mean()
        n_settings = clean["setting"].nunique()
        n_budgets = clean["budget"].nunique()
        n_total = len(clean)
        n_wins = len(clean[clean["delta_recall"] > 0])

        if n_ge10 >= 3 or (max_d >= 0.15 and n_wins >= n_total * 0.6):
            judgment = "A"
            lines.append("**A. Continue**: joint allocation has stable and "
                         "meaningful gains across settings.")
        elif n_wins >= n_total * 0.5 and avg_d > 0.02:
            judgment = "B"
            lines.append("**B. Weak continue**: gains exist but small; "
                         "need more data/videos.")
        else:
            judgment = "C"
            lines.append("**C. Stop**: joint allocation does not beat "
                         "candidate-only reliably.")

        lines.append(f"\n- Wins: {n_wins}/{n_total} ({n_wins/n_total:.0%})")
        lines.append(f"- Delta >= 0.10: {n_ge10}")
        lines.append(f"- Max delta: {max_d:+.3f}")
        lines.append(f"- Avg delta: {avg_d:+.3f}")
    else:
        judgment = "C"
        lines.append("**C. Stop**: no valid settings found.")

    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    return judgment


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="Bounded auto research")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--label-col", required=True)
    parser.add_argument("--budgets", required=True)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",")]
    df = pd.read_csv(args.csv)

    os.makedirs(args.out_dir, exist_ok=True)

    # Step 2: Probe settings
    print("=" * 70)
    print("STEP 2: Setting Probe")
    print("=" * 70)
    label_cols = [c for c in df.columns if c.startswith("label_")]
    min_lens = [15, 30, 60]
    valid_settings = probe_settings(df, label_cols, min_lens)
    print(f"\nValid settings: {len(valid_settings)}")
    for s in valid_settings:
        print(f"  {s['label_col']}_min{s['min_len']}: "
              f"clips={s['true_clip_count']}, ratio={s['positive_frame_ratio']:.4f}")

    if not valid_settings:
        print("No valid settings. Exiting.")
        return

    # Step 3: Run joint allocation for each setting
    print("\n" + "=" * 70)
    print("STEP 3: Joint Allocation Generalization")
    print("=" * 70)

    all_rows = []
    for setting in valid_settings:
        lc = setting["label_col"]
        ml = setting["min_len"]
        setting_label = f"{lc}_min{ml}"
        labels = df[lc].astype(int).tolist()
        N = len(labels)
        true_clips = labels_to_clips(labels, ml)

        print(f"\n  Setting: {setting_label} "
              f"(clips={len(true_clips)}, ratio={setting['positive_frame_ratio']:.4f})")

        rows = run_one_setting(df, labels, true_clips, N, ml, budgets,
                                args.trials, args.seed, PROXY_CONFIGS,
                                setting_label)
        all_rows.extend(rows)
        print(f"    {len(rows)} rows done")

    # Step 4: Proxy degradation (on K10 min15)
    print("\n" + "=" * 70)
    print("STEP 4: Proxy Degradation")
    print("=" * 70)

    deg_setting = [s for s in valid_settings
                   if s["label_col"] == "label_K10" and s["min_len"] == 15]
    if not deg_setting:
        deg_setting = [valid_settings[0]]
    deg = deg_setting[0]
    deg_labels = df[deg["label_col"]].astype(int).tolist()
    deg_N = len(deg_labels)
    deg_clips = labels_to_clips(deg_labels, deg["min_len"])
    deg_label = f"{deg['label_col']}_min{deg['min_len']}"

    # Use fewer trials for degradation to save time
    deg_trials = min(args.trials, 50)
    print(f"  Base setting: {deg_label}, trials={deg_trials}")

    for pconf in PROXY_CONFIGS[:2]:  # top 2 proxy configs
        print(f"  Proxy: {pconf['proxy_col']} {pconf['threshold_desc']}")
        deg_rows = run_proxy_degradation(
            df, deg_labels, deg_clips, deg_N, deg["min_len"],
            budgets, deg_trials, args.seed, pconf, deg_label)
        all_rows.extend(deg_rows)
        print(f"    {len(deg_rows)} degradation rows done")

    # Step 5: Summary
    print("\n" + "=" * 70)
    print("STEP 5: Summary")
    print("=" * 70)

    # Save all rows
    trials_df = pd.DataFrame(all_rows)
    trials_path = os.path.join(args.out_dir, "all_trials.csv")
    trials_df.to_csv(trials_path, index=False)
    print(f"  Saved {len(trials_df)} rows to all_trials.csv")

    # Build unified summary
    summary_df = build_unified_summary(all_rows, valid_settings)
    summary_path = os.path.join(args.out_dir, "summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"  Saved summary ({len(summary_df)} rows) to summary.csv")

    # Write final summary.md
    judgment = write_final_summary(summary_df, args.out_dir)
    print(f"\n  JUDGMENT: {judgment}")

    # Config
    config = {
        "csv": os.path.abspath(args.csv),
        "label_col": args.label_col,
        "budgets": budgets,
        "trials": args.trials,
        "seed": args.seed,
        "valid_settings": valid_settings,
        "judgment": judgment,
    }
    with open(os.path.join(args.out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    # Print key table
    print("\n" + "=" * 70)
    print("KEY RESULTS: clean settings, best budget per setting")
    print("=" * 70)
    clean = summary_df[summary_df["proxy_variant"] == "clean"]
    if not clean.empty:
        print(f"  {'setting':<25s}  {'budget':>6s}  {'cand_recall':>11s}  "
              f"{'joint_recall':>12s}  {'delta':>7s}  {'method':<18s}")
        print("  " + "-" * 90)
        for setting in clean["setting"].unique():
            s_df = clean[clean["setting"] == setting]
            best = s_df.sort_values("delta_recall", ascending=False).iloc[0]
            print(f"  {best['setting']:<25s}  {int(best['budget']):>6d}  "
                  f"{best['candidate_only_recall']:>11.3f}  "
                  f"{best['best_joint_recall']:>12.3f}  "
                  f"{best['delta_recall']:>+7.3f}  "
                  f"{best['best_joint_method']:<18s}")

    print(f"\nResults saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
