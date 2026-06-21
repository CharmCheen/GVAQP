#!/usr/bin/env python3
"""Kill experiment: joint allocation vs candidate-only.

Answers: does splitting oracle budget between candidate refinement and
non-candidate audit beat spending it all on candidates?

Methods:
  1. candidate_only — all budget in candidate regions
  2. audit_only — all budget uniform-sampled from non-candidate frames
  3. fixed_mix_80_20 — 80% candidate, 20% audit
  4. fixed_mix_50_50 — 50% candidate, 50% audit
  5. adaptive_greedy — batch-wise yield-based allocation

Usage:
    python experiments/clip_boundary/run_joint_allocation_kill_exp.py \
        --csv outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv \
        --label-col label_K10 \
        --min-len 15 \
        --budgets 50,100,200,400,800,1200 \
        --trials 200 \
        --seed 42 \
        --out-dir experiments/clip_boundary/joint_allocation_K10
"""

import argparse
import json
import os

import numpy as np
import pandas as pd


# ===========================================================================
# Unified evaluation
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
    if not true_clips:
        return {"recall": 0.0, "precision": 0.0, "invalid_rate": 0.0,
                "mIoU": 0.0, "num_pred_clips": len(pred_clips),
                "short_recall": 0.0, "medium_recall": 0.0, "long_recall": 0.0,
                "per_clip_hit": []}

    invalid_count = 0
    for s, e in pred_clips:
        for k in range(s, e + 1):
            if labels[k] == 0:
                invalid_count += 1
                break
    invalid_rate = invalid_count / len(pred_clips) if pred_clips else 0.0

    hits = []
    for tc in true_clips:
        hit = any(clip_iou(tc, pc) >= 0.5 for pc in pred_clips)
        hits.append(hit)
    recall = sum(hits) / len(true_clips)

    prec_hits = 0
    for pc in pred_clips:
        if any(clip_iou(tc, pc) >= 0.5 for tc in true_clips):
            prec_hits += 1
    precision = prec_hits / len(pred_clips) if pred_clips else 0.0

    ious = [max((clip_iou(tc, pc) for tc in true_clips), default=0.0)
            for pc in pred_clips]
    mIoU = np.mean(ious) if ious else 0.0

    buckets = {"short": [], "medium": [], "long": []}
    for i, (s, e) in enumerate(true_clips):
        buckets[length_bucket(s, e)].append(hits[i])

    return {
        "recall": recall, "precision": precision, "invalid_rate": invalid_rate,
        "mIoU": mIoU, "num_pred_clips": len(pred_clips),
        "short_recall": np.mean(buckets["short"]) if buckets["short"] else 0.0,
        "medium_recall": np.mean(buckets["medium"]) if buckets["medium"] else 0.0,
        "long_recall": np.mean(buckets["long"]) if buckets["long"] else 0.0,
        "per_clip_hit": hits,
    }


# ===========================================================================
# Oracle
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

    def phase_count(self, phase):
        return self.phase_calls.get(phase, 0)


# ===========================================================================
# Helpers
# ===========================================================================
def merge_pos_frames(pos_frames, gap):
    """Merge positive frame indices into (start, end) intervals.
    gap: max frames of separation to merge (gap=0 → only consecutive)."""
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


def pos_frames_to_clips(pos_frames, gap, min_len):
    """Positive frames → gap merge → filter by min_len."""
    regions = merge_pos_frames(pos_frames, gap)
    return [(s, e) for s, e in regions if e - s + 1 >= min_len]


def get_candidate_regions(df, proxy_col, threshold_val, gap):
    """Proxy → mask → merge → candidate regions."""
    if proxy_col.startswith("proxy_positive_"):
        mask = df[proxy_col].values == 1
    else:
        mask = df[proxy_col].values >= threshold_val
    pos_frames = sorted(np.where(mask)[0].tolist())
    regions = merge_pos_frames(pos_frames, gap)
    return regions, mask


def get_threshold(df, proxy_col, pct):
    vals = df[proxy_col].values.astype(float)
    return np.quantile(vals, 1.0 - pct)


def region_proxy_mean(df, proxy_col, s, e):
    vals = df[proxy_col].values.astype(float)
    return float(np.mean(vals[s:e + 1]))


def count_new_clips(pos_frames_before, pos_frames_after, gap, min_len):
    """Count clips that appear after adding new positive frames."""
    clips_before = set(pos_frames_to_clips(pos_frames_before, gap, min_len))
    clips_after = set(pos_frames_to_clips(pos_frames_after, gap, min_len))
    return len(clips_after - clips_before)


# ===========================================================================
# Method 1: candidate_only
# ===========================================================================
def run_candidate_only(df, proxy_col, threshold_val, cand_gap, oracle,
                       budget, N, min_len, priority, gap, rng):
    """All budget in candidate regions, priority-ordered."""
    regions, mask = get_candidate_regions(df, proxy_col, threshold_val,
                                          cand_gap)
    if not regions:
        return [], oracle.calls, 0, 0

    # Priority sort
    if priority == "proxy_mean_desc":
        ranked = sorted(regions,
                        key=lambda r: -region_proxy_mean(df, proxy_col,
                                                          r[0], r[1]))
    elif priority == "region_length_desc":
        ranked = sorted(regions, key=lambda r: -(r[1] - r[0] + 1))
    else:
        ranked = regions

    pos_before = sorted(oracle.cache.keys())
    all_pos = list(pos_before)

    for s, e in ranked:
        if oracle.calls >= budget:
            break
        for k in range(s, e + 1):
            if oracle.calls >= budget:
                break
            if oracle.query(k, phase="candidate_refine") == 1:
                all_pos.append(k)

    all_pos = sorted(set(all_pos))
    pred_clips = pos_frames_to_clips(all_pos, gap, min_len)
    new_clips = count_new_clips(pos_before, all_pos, gap, min_len)
    cand_calls = oracle.phase_count("candidate_refine")

    return pred_clips, oracle.calls, cand_calls, new_clips


# ===========================================================================
# Method 2: audit_only
# ===========================================================================
def run_audit_only(df, proxy_col, threshold_val, cand_gap, oracle,
                   budget, N, min_len, gap, rng):
    """All budget uniform-sampled from non-candidate frames."""
    _, mask = get_candidate_regions(df, proxy_col, threshold_val, cand_gap)
    non_cand = np.where(~mask)[0].tolist()

    if not non_cand:
        return [], oracle.calls, 0, 0

    sample_size = min(budget, len(non_cand))
    sampled = rng.choice(non_cand, size=sample_size, replace=False)

    pos_before = sorted(oracle.cache.keys())
    all_pos = list(pos_before)

    for idx in sampled:
        if oracle.query(int(idx), phase="audit") == 1:
            all_pos.append(int(idx))

    all_pos = sorted(set(all_pos))
    pred_clips = pos_frames_to_clips(all_pos, gap, min_len)
    new_clips = count_new_clips(pos_before, all_pos, gap, min_len)
    audit_calls = oracle.phase_count("audit")

    return pred_clips, oracle.calls, audit_calls, new_clips


# ===========================================================================
# Method 3/4: fixed_mix
# ===========================================================================
def run_fixed_mix(df, proxy_col, threshold_val, cand_gap, oracle,
                  budget, N, min_len, priority, gap, rng, cand_frac):
    """Fixed split: cand_frac to candidate, rest to audit."""
    n_cand = max(1, int(cand_frac * budget))
    n_audit = budget - n_cand

    # --- candidate portion ---
    regions, mask = get_candidate_regions(df, proxy_col, threshold_val,
                                          cand_gap)
    if priority == "proxy_mean_desc":
        ranked = sorted(regions,
                        key=lambda r: -region_proxy_mean(df, proxy_col,
                                                          r[0], r[1]))
    elif priority == "region_length_desc":
        ranked = sorted(regions, key=lambda r: -(r[1] - r[0] + 1))
    else:
        ranked = regions

    pos_before = sorted(oracle.cache.keys())
    all_pos = list(pos_before)
    cand_calls_used = 0

    for s, e in ranked:
        if cand_calls_used >= n_cand:
            break
        for k in range(s, e + 1):
            if cand_calls_used >= n_cand:
                break
            if oracle.calls >= budget:
                break
            if oracle.query(k, phase="candidate_refine") == 1:
                all_pos.append(k)
            cand_calls_used += 1

    clips_after_cand = set(pos_frames_to_clips(sorted(set(all_pos)),
                                                gap, min_len))

    # --- audit portion ---
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
    new_clips = count_new_clips(pos_before, all_pos, gap, min_len)
    cand_calls = oracle.phase_count("candidate_refine")
    audit_calls = oracle.phase_count("audit")

    return pred_clips, oracle.calls, cand_calls, audit_calls, new_clips


# ===========================================================================
# Method 5: adaptive_greedy
# ===========================================================================
def run_adaptive_greedy(df, proxy_col, threshold_val, cand_gap, oracle,
                        budget, N, min_len, priority, gap, rng,
                        batch_size=25):
    """Adaptive batch-wise allocation based on marginal yield."""
    regions, mask = get_candidate_regions(df, proxy_col, threshold_val,
                                          cand_gap)
    non_cand = np.where(~mask)[0].tolist()

    if priority == "proxy_mean_desc":
        ranked = sorted(regions,
                        key=lambda r: -region_proxy_mean(df, proxy_col,
                                                          r[0], r[1]))
    elif priority == "region_length_desc":
        ranked = sorted(regions, key=lambda r: -(r[1] - r[0] + 1))
    else:
        ranked = regions

    # Flatten candidate frames in priority order
    cand_frames = []
    for s, e in ranked:
        cand_frames.extend(range(s, e + 1))
    cand_idx = 0
    nc_avail = list(non_cand)
    rng.shuffle(nc_avail)
    nc_idx = 0

    pos_before = sorted(oracle.cache.keys())
    all_pos = list(pos_before)

    prev_cand_clips = len(pos_frames_to_clips(sorted(set(all_pos)),
                                               gap, min_len))
    prev_audit_clips = prev_cand_clips

    yield_cand = 1.0  # start favoring candidate
    yield_audit = 0.0

    while oracle.calls < budget:
        # Decide which region gets the next batch
        if oracle.calls < 2 * batch_size:
            # Warmup: alternate
            do_cand = (oracle.calls // batch_size) % 2 == 0
        else:
            do_cand = yield_cand >= yield_audit

        clips_before_batch = len(
            pos_frames_to_clips(sorted(set(all_pos)), gap, min_len))
        calls_before = oracle.calls

        if do_cand:
            # Candidate batch
            for _ in range(batch_size):
                if cand_idx >= len(cand_frames) or oracle.calls >= budget:
                    break
                k = cand_frames[cand_idx]
                cand_idx += 1
                if oracle.query(k, phase="candidate_refine") == 1:
                    all_pos.append(k)
        else:
            # Audit batch
            for _ in range(batch_size):
                if nc_idx >= len(nc_avail) or oracle.calls >= budget:
                    break
                k = nc_avail[nc_idx]
                nc_idx += 1
                if oracle.query(k, phase="audit") == 1:
                    all_pos.append(k)

        clips_after = len(
            pos_frames_to_clips(sorted(set(all_pos)), gap, min_len))
        calls_used = max(1, oracle.calls - calls_before)
        marginal = (clips_after - clips_before_batch) / calls_used * 100

        if do_cand:
            yield_cand = marginal
        else:
            yield_audit = marginal

    all_pos = sorted(set(all_pos))
    pred_clips = pos_frames_to_clips(all_pos, gap, min_len)
    new_clips = count_new_clips(pos_before, all_pos, gap, min_len)
    cand_calls = oracle.phase_count("candidate_refine")
    audit_calls = oracle.phase_count("audit")

    return pred_clips, oracle.calls, cand_calls, audit_calls, new_clips


# ===========================================================================
# Best-gap wrapper
# ===========================================================================
def find_best_gap(method_fn, method_args, gaps, min_len, true_clips, labels):
    """Run method for each gap, return best recall result + gap detail."""
    best = None
    best_gap = None
    details = []

    for gap in gaps:
        oracle = method_args["oracle"]
        # Reset oracle for each gap trial
        oracle_new = Oracle(labels)
        # Copy the args with new oracle
        args = dict(method_args)
        args["oracle"] = oracle_new

        result = method_fn(**args, gap=gap)
        pred_clips, total_calls, extra1, extra2 = result[:4]
        new_clips = result[4] if len(result) > 4 else 0

        ev = eval_clips(pred_clips, true_clips, labels)

        detail = {
            "gap": gap,
            "recall": ev["recall"],
            "precision": ev["precision"],
            "invalid_rate": ev["invalid_rate"],
            "mIoU": ev["mIoU"],
            "num_pred_clips": ev["num_pred_clips"],
            "oracle_calls": total_calls,
        }
        if method_args.get("_method_type") == "candidate_only":
            detail["candidate_calls"] = extra1
            detail["new_clips_from_candidate"] = extra2
        elif method_args.get("_method_type") == "audit_only":
            detail["audit_calls"] = extra1
            detail["new_clips_from_audit"] = extra2
        else:
            detail["candidate_calls"] = extra1
            detail["audit_calls"] = extra2
            detail["new_clips_total"] = new_clips

        details.append(detail)

        if best is None or ev["recall"] > best["recall"]:
            best = detail
            best_gap = gap

    return best, best_gap, details


# ===========================================================================
# Proxy configs
# ===========================================================================
def load_best_configs_from_arc(arc_dir, top_k=6):
    """Load configs from ARC transfer results.

    Strategy: prefer configs with moderate candidate_fraction (20-35%)
    and tight gaps (3-10) for budget-efficient refinement.
    """
    ub_path = os.path.join(arc_dir, "proxy_candidate_upper_bound.csv")
    if not os.path.exists(ub_path):
        return None

    df = pd.read_csv(ub_path)

    # Filter: moderate candidate fraction and reasonable gap
    df = df[(df["candidate_frame_fraction"] >= 0.15) &
            (df["candidate_frame_fraction"] <= 0.35) &
            (df["gap"] <= 10)]

    if df.empty:
        return None

    # Score: refined_recall weighted by gap tightness
    df["score"] = df["refined_unlimited_recall"] / (1 + df["gap"] * 0.1)
    df = df.sort_values("score", ascending=False)

    configs = []
    seen = set()
    for _, r in df.iterrows():
        pcol = r["proxy_col"]
        thr_desc = r["threshold_desc"]
        gap = int(r["gap"])
        key = (pcol, thr_desc, gap)
        if key not in seen:
            seen.add(key)
            configs.append({
                "proxy_col": pcol,
                "threshold_desc": thr_desc,
                "cand_gap": gap,
            })
        if len(configs) >= top_k:
            break
    return configs


def get_default_configs():
    """Fallback configs: known good from ARC transfer stress test.

    Selected by: best recall at budget=1200 in the stress test,
    with candidate_fraction in 20-35% range for budget efficiency.
    """
    return [
        # Best at budget=1200: recall=0.611
        {"proxy_col": "proxy_vehicle_count", "threshold_desc": "top20%",
         "cand_gap": 5},
        # Best at budget=800: recall=0.500
        {"proxy_col": "proxy_vehicle_count", "threshold_desc": "top20%",
         "cand_gap": 3},
        # Good at budget=400: recall=0.278
        {"proxy_col": "proxy_vehicle_count", "threshold_desc": "top10%",
         "cand_gap": 10},
        # proxy_score alternative
        {"proxy_col": "proxy_score", "threshold_desc": "top30%",
         "cand_gap": 5},
        # Binary proxy
        {"proxy_col": "proxy_positive_K10", "threshold_desc": "binary",
         "cand_gap": 5},
    ]


# ===========================================================================
# Main experiment runner
# ===========================================================================
def run_experiment(df, labels, true_clips, N, min_len, budgets, trials, seed,
                   proxy_configs):
    """Run all methods across all budgets and trials."""
    clip_gaps = [1, 5, 10, 15, 30]
    priorities = ["proxy_mean_desc", "region_length_desc"]

    all_rows = []
    gap_rows = []

    for pconf in proxy_configs:
        pcol = pconf["proxy_col"]
        thr_desc = pconf["threshold_desc"]
        cand_gap = pconf["cand_gap"]
        config_label = f"{pcol}_{thr_desc}_g{cand_gap}"

        # Compute threshold
        if thr_desc == "binary":
            threshold_val = None
        else:
            pct = float(thr_desc.replace("top", "").replace("%", "")) / 100
            threshold_val = get_threshold(df, pcol, pct)

        print(f"  Config: {config_label}", flush=True)

        for budget in budgets:
            for t in range(trials):
                rng_base = np.random.RandomState(seed + t * 1000 + budget)

                # --- Method 1: candidate_only (best priority) ---
                for priority in priorities:
                    rng = np.random.RandomState(seed + t * 1000 + budget +
                                                 hash(priority) % 10000)
                    oracle = Oracle(labels)

                    def cand_fn(oracle, gap):
                        return run_candidate_only(
                            df, pcol, threshold_val, cand_gap, oracle,
                            budget, N, min_len, priority, gap, rng)

                    best_d = None
                    best_g = None
                    for gap in clip_gaps:
                        oracle_g = Oracle(labels)
                        pred, calls, cc, nc = cand_fn(oracle_g, gap)
                        ev = eval_clips(pred, true_clips, labels)
                        d = {"gap": gap, "recall": ev["recall"],
                             "precision": ev["precision"],
                             "invalid_rate": ev["invalid_rate"],
                             "mIoU": ev["mIoU"],
                             "num_pred_clips": ev["num_pred_clips"],
                             "oracle_calls": calls,
                             "candidate_calls": cc,
                             "new_clips_from_candidate": nc}
                        gap_rows.append({
                            "method": "candidate_only",
                            "proxy_config": config_label,
                            "budget": budget, "trial": t,
                            "priority": priority, **d})
                        if best_d is None or ev["recall"] > best_d["recall"]:
                            best_d = d
                            best_g = gap

                    all_rows.append({
                        "method": "candidate_only",
                        "proxy_config": config_label,
                        "budget": budget, "trial": t,
                        "priority": priority, "best_gap": best_g,
                        "recall": best_d["recall"],
                        "precision": best_d["precision"],
                        "invalid_rate": best_d["invalid_rate"],
                        "mIoU": best_d["mIoU"],
                        "num_pred_clips": best_d["num_pred_clips"],
                        "oracle_calls": best_d["oracle_calls"],
                        "candidate_calls": best_d["candidate_calls"],
                        "audit_calls": 0,
                        "new_clips_from_candidate": best_d[
                            "new_clips_from_candidate"],
                        "new_clips_from_audit": 0,
                        "short_recall": 0.0, "medium_recall": 0.0,
                        "long_recall": 0.0,
                    })

                # --- Method 2: audit_only ---
                rng = np.random.RandomState(seed + t * 1000 + budget + 999)
                best_d = None
                best_g = None
                for gap in clip_gaps:
                    oracle_g = Oracle(labels)
                    pred, calls, ac, nc = run_audit_only(
                        df, pcol, threshold_val, cand_gap, oracle_g,
                        budget, N, min_len, gap, rng)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"gap": gap, "recall": ev["recall"],
                         "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"],
                         "mIoU": ev["mIoU"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls,
                         "audit_calls": ac,
                         "new_clips_from_audit": nc}
                    gap_rows.append({
                        "method": "audit_only",
                        "proxy_config": config_label,
                        "budget": budget, "trial": t,
                        "priority": "-", **d})
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d = d
                        best_g = gap

                all_rows.append({
                    "method": "audit_only",
                    "proxy_config": config_label,
                    "budget": budget, "trial": t,
                    "priority": "-", "best_gap": best_g,
                    "recall": best_d["recall"],
                    "precision": best_d["precision"],
                    "invalid_rate": best_d["invalid_rate"],
                    "mIoU": best_d["mIoU"],
                    "num_pred_clips": best_d["num_pred_clips"],
                    "oracle_calls": best_d["oracle_calls"],
                    "candidate_calls": 0,
                    "audit_calls": best_d["audit_calls"],
                    "new_clips_from_candidate": 0,
                    "new_clips_from_audit": best_d["new_clips_from_audit"],
                    "short_recall": 0.0, "medium_recall": 0.0,
                    "long_recall": 0.0,
                })

                # --- Method 3/4: fixed_mix ---
                for mix_label, cand_frac in [("fixed_mix_80_20", 0.8),
                                              ("fixed_mix_50_50", 0.5)]:
                    rng = np.random.RandomState(
                        seed + t * 1000 + budget +
                        hash(mix_label) % 10000)
                    best_d = None
                    best_g = None
                    for gap in clip_gaps:
                        oracle_g = Oracle(labels)
                        pred, calls, cc, ac, nc = run_fixed_mix(
                            df, pcol, threshold_val, cand_gap, oracle_g,
                            budget, N, min_len, "proxy_mean_desc", gap,
                            rng, cand_frac)
                        ev = eval_clips(pred, true_clips, labels)
                        d = {"gap": gap, "recall": ev["recall"],
                             "precision": ev["precision"],
                             "invalid_rate": ev["invalid_rate"],
                             "mIoU": ev["mIoU"],
                             "num_pred_clips": ev["num_pred_clips"],
                             "oracle_calls": calls,
                             "candidate_calls": cc,
                             "audit_calls": ac,
                             "new_clips_total": nc}
                        gap_rows.append({
                            "method": mix_label,
                            "proxy_config": config_label,
                            "budget": budget, "trial": t,
                            "priority": "proxy_mean_desc", **d})
                        if best_d is None or ev["recall"] > best_d["recall"]:
                            best_d = d
                            best_g = gap

                    all_rows.append({
                        "method": mix_label,
                        "proxy_config": config_label,
                        "budget": budget, "trial": t,
                        "priority": "proxy_mean_desc",
                        "best_gap": best_g,
                        "recall": best_d["recall"],
                        "precision": best_d["precision"],
                        "invalid_rate": best_d["invalid_rate"],
                        "mIoU": best_d["mIoU"],
                        "num_pred_clips": best_d["num_pred_clips"],
                        "oracle_calls": best_d["oracle_calls"],
                        "candidate_calls": best_d["candidate_calls"],
                        "audit_calls": best_d["audit_calls"],
                        "new_clips_from_candidate": 0,
                        "new_clips_from_audit": best_d["new_clips_total"],
                        "short_recall": 0.0, "medium_recall": 0.0,
                        "long_recall": 0.0,
                    })

                # --- Method 5: adaptive_greedy ---
                rng = np.random.RandomState(seed + t * 1000 + budget + 5555)
                best_d = None
                best_g = None
                for gap in clip_gaps:
                    oracle_g = Oracle(labels)
                    pred, calls, cc, ac, nc = run_adaptive_greedy(
                        df, pcol, threshold_val, cand_gap, oracle_g,
                        budget, N, min_len, "proxy_mean_desc", gap,
                        rng, batch_size=25)
                    ev = eval_clips(pred, true_clips, labels)
                    d = {"gap": gap, "recall": ev["recall"],
                         "precision": ev["precision"],
                         "invalid_rate": ev["invalid_rate"],
                         "mIoU": ev["mIoU"],
                         "num_pred_clips": ev["num_pred_clips"],
                         "oracle_calls": calls,
                         "candidate_calls": cc,
                         "audit_calls": ac,
                         "new_clips_total": nc}
                    gap_rows.append({
                        "method": "adaptive_greedy",
                        "proxy_config": config_label,
                        "budget": budget, "trial": t,
                        "priority": "proxy_mean_desc", **d})
                    if best_d is None or ev["recall"] > best_d["recall"]:
                        best_d = d
                        best_g = gap

                all_rows.append({
                    "method": "adaptive_greedy",
                    "proxy_config": config_label,
                    "budget": budget, "trial": t,
                    "priority": "proxy_mean_desc",
                    "best_gap": best_g,
                    "recall": best_d["recall"],
                    "precision": best_d["precision"],
                    "invalid_rate": best_d["invalid_rate"],
                    "mIoU": best_d["mIoU"],
                    "num_pred_clips": best_d["num_pred_clips"],
                    "oracle_calls": best_d["oracle_calls"],
                    "candidate_calls": best_d["candidate_calls"],
                    "audit_calls": best_d["audit_calls"],
                    "new_clips_from_candidate": 0,
                    "new_clips_from_audit": best_d["new_clips_total"],
                    "short_recall": 0.0, "medium_recall": 0.0,
                    "long_recall": 0.0,
                })

            print(f"    budget={budget} done", flush=True)

    return pd.DataFrame(all_rows), pd.DataFrame(gap_rows)


# ===========================================================================
# Marginal utility analysis
# ===========================================================================
def compute_marginal_utility(trials_df):
    """Compute clips-per-100-calls for candidate and audit regions."""
    rows = []
    for budget in trials_df["budget"].unique():
        sub = trials_df[trials_df["budget"] == budget]
        # Use candidate_only for candidate yield
        cand = sub[sub["method"] == "candidate_only"]
        if not cand.empty:
            cand_yield = (cand["new_clips_from_candidate"].mean() /
                          cand["candidate_calls"].mean() * 100
                          if cand["candidate_calls"].mean() > 0 else 0)
        else:
            cand_yield = 0

        # Use audit_only for audit yield
        aud = sub[sub["method"] == "audit_only"]
        if not aud.empty:
            aud_yield = (aud["new_clips_from_audit"].mean() /
                         aud["audit_calls"].mean() * 100
                         if aud["audit_calls"].mean() > 0 else 0)
        else:
            aud_yield = 0

        rows.append({
            "budget": budget,
            "candidate_clips_per_100_calls": cand_yield,
            "audit_clips_per_100_calls": aud_yield,
            "better_region": "candidate" if cand_yield >= aud_yield
                             else "audit",
        })
    return pd.DataFrame(rows)


# ===========================================================================
# Predicted clips for output
# ===========================================================================
def collect_predicted_clips(df, labels, true_clips, N, min_len, proxy_configs,
                            seed):
    """Collect predicted clips from representative runs."""
    clip_gaps = [1, 5, 10, 15, 30]
    budget = 400  # representative budget
    rows = []

    for pconf in proxy_configs[:2]:  # top 2 configs
        pcol = pconf["proxy_col"]
        thr_desc = pconf["threshold_desc"]
        cand_gap = pconf["cand_gap"]
        config_label = f"{pcol}_{thr_desc}_g{cand_gap}"

        if thr_desc == "binary":
            threshold_val = None
        else:
            pct = float(thr_desc.replace("top", "").replace("%", "")) / 100
            threshold_val = get_threshold(df, pcol, pct)

        for method in ["candidate_only", "audit_only", "fixed_mix_80_20",
                        "adaptive_greedy"]:
            rng = np.random.RandomState(seed + hash(method) % 10000)
            best_pred = None
            best_recall = -1

            for gap in clip_gaps:
                oracle = Oracle(labels)
                if method == "candidate_only":
                    pred, calls, cc, nc = run_candidate_only(
                        df, pcol, threshold_val, cand_gap, oracle,
                        budget, N, min_len, "proxy_mean_desc", gap, rng)
                elif method == "audit_only":
                    pred, calls, ac, nc = run_audit_only(
                        df, pcol, threshold_val, cand_gap, oracle,
                        budget, N, min_len, gap, rng)
                elif method == "fixed_mix_80_20":
                    pred, calls, cc, ac, nc = run_fixed_mix(
                        df, pcol, threshold_val, cand_gap, oracle,
                        budget, N, min_len, "proxy_mean_desc", gap, rng, 0.8)
                else:
                    pred, calls, cc, ac, nc = run_adaptive_greedy(
                        df, pcol, threshold_val, cand_gap, oracle,
                        budget, N, min_len, "proxy_mean_desc", gap, rng)

                ev = eval_clips(pred, true_clips, labels)
                if ev["recall"] > best_recall:
                    best_recall = ev["recall"]
                    best_pred = pred

            for ci, (s, e) in enumerate(best_pred):
                valid = all(labels[k] == 1 for k in range(s, e + 1))
                rows.append({
                    "method": method,
                    "proxy_config": config_label,
                    "budget": budget,
                    "clip_id": ci,
                    "start": s, "end": e,
                    "length": e - s + 1,
                    "is_valid": valid,
                })

    return pd.DataFrame(rows)


# ===========================================================================
# Summary markdown
# ===========================================================================
def write_summary_md(out_dir, trials_df, mu_df, config):
    lines = ["# Joint Allocation Kill Experiment Summary\n"]
    lines.append(f"- CSV: `{config['csv']}`")
    lines.append(f"- Label: `{config['label_col']}`")
    lines.append(f"- Frames: {config['num_frames']}")
    lines.append(f"- True clips: {config['num_true_clips']}\n")

    # Table 1 summary per method
    lines.append("## Method Comparison (best per budget)\n")
    for budget in sorted(trials_df["budget"].unique()):
        sub = trials_df[trials_df["budget"] == budget]
        lines.append(f"### Budget {budget}\n")
        lines.append("| method | recall | precision | invalid | cand_calls | audit_calls |")
        lines.append("|--------|--------|-----------|---------|------------|-------------|")
        for method in ["candidate_only", "audit_only", "fixed_mix_80_20",
                        "fixed_mix_50_50", "adaptive_greedy"]:
            msub = sub[sub["method"] == method]
            if msub.empty:
                continue
            best = msub.sort_values("recall", ascending=False).iloc[0]
            lines.append(
                f"| {method} | {best['recall']:.3f} | "
                f"{best['precision']:.3f} | {best['invalid_rate']:.1%} | "
                f"{best['candidate_calls']:.0f} | {best['audit_calls']:.0f} |")

    # Marginal utility
    lines.append("\n## Marginal Utility\n")
    lines.append("| budget | candidate/100 | audit/100 | better |")
    lines.append("|--------|---------------|-----------|--------|")
    for _, r in mu_df.iterrows():
        lines.append(
            f"| {int(r['budget'])} | "
            f"{r['candidate_clips_per_100_calls']:.2f} | "
            f"{r['audit_clips_per_100_calls']:.2f} | "
            f"{r['better_region']} |")

    # Judgment
    lines.append("\n## Judgment\n")
    # Check if any joint method beats candidate_only by >= 0.1 recall
    max_delta = 0
    best_joint = ""
    best_budget = 0
    for budget in trials_df["budget"].unique():
        sub = trials_df[trials_df["budget"] == budget]
        cand = sub[sub["method"] == "candidate_only"]["recall"].max()
        for method in ["fixed_mix_80_20", "fixed_mix_50_50",
                        "adaptive_greedy"]:
            joint = sub[sub["method"] == method]["recall"].max()
            delta = joint - cand
            if delta > max_delta:
                max_delta = delta
                best_joint = method
                best_budget = budget

    if max_delta >= 0.1:
        lines.append(
            f"**SITUATION A: Joint allocation WINS** ({best_joint} at "
            f"budget={best_budget}, +{max_delta:.3f} recall). "
            "Non-candidate audit has substantial value. Direction is viable.")
    elif max_delta >= 0.03:
        lines.append(
            f"**SITUATION B: Marginal improvement** ({best_joint} at "
            f"budget={best_budget}, +{max_delta:.3f} recall). "
            "Audit has some value but the effect is small. Direction needs "
            "stronger evidence.")
    else:
        # Check if audit_only is competitive
        max_audit_recall = 0
        max_cand_recall = 0
        for budget in trials_df["budget"].unique():
            sub = trials_df[trials_df["budget"] == budget]
            max_audit_recall = max(max_audit_recall,
                                   sub[sub["method"] == "audit_only"][
                                       "recall"].max())
            max_cand_recall = max(max_cand_recall,
                                  sub[sub["method"] == "candidate_only"][
                                      "recall"].max())
        if max_audit_recall >= max_cand_recall * 0.8:
            lines.append(
                f"**SITUATION C: Audit is competitive** "
                f"(audit_max={max_audit_recall:.3f} vs "
                f"candidate_max={max_cand_recall:.3f}). "
                "Proxy candidates unreliable. Research → proxy sufficiency.")
        else:
            lines.append(
                f"**SITUATION D: Candidate-only wins** "
                f"(max_delta={max_delta:.3f}). "
                "ARC-like refinement is sufficient. Joint allocation adds "
                "no value. Direction should be stopped.")

    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


# ===========================================================================
# Terminal tables
# ===========================================================================
def print_tables(trials_df, mu_df, budgets):
    # Table 1: main kill experiment
    print()
    print("=" * 110)
    print("TABLE 1: Main Kill Experiment (best proxy_config per method/budget)")
    print("=" * 110)
    hdr = (f"{'method':<22s}  {'budget':>6s}  {'recall':>7s}  "
           f"{'prec':>6s}  {'invalid':>8s}  {'cand_calls':>10s}  "
           f"{'audit_calls':>11s}")
    print(hdr)
    print("-" * len(hdr))

    for budget in budgets:
        sub = trials_df[trials_df["budget"] == budget]
        for method in ["candidate_only", "audit_only", "fixed_mix_80_20",
                        "fixed_mix_50_50", "adaptive_greedy"]:
            msub = sub[sub["method"] == method]
            if msub.empty:
                continue
            best = msub.sort_values("recall", ascending=False).iloc[0]
            print(f"  {method:<20s}  {int(best['budget']):>6d}  "
                  f"{best['recall']:>7.3f}  {best['precision']:>6.3f}  "
                  f"{best['invalid_rate']:>8.1%}  "
                  f"{best['candidate_calls']:>10.0f}  "
                  f"{best['audit_calls']:>11.0f}")
        print()

    # Table 2: budget needed
    print("=" * 110)
    print("TABLE 2: Budget Needed for Recall Thresholds")
    print("=" * 110)
    print(f"  {'method':<22s}  {'>=0.3':>10s}  {'>=0.5':>10s}  "
          f"{'>=0.8':>10s}")
    print("-" * 60)

    for method in ["candidate_only", "audit_only", "fixed_mix_80_20",
                    "fixed_mix_50_50", "adaptive_greedy"]:
        msub = trials_df[trials_df["method"] == method]
        if msub.empty:
            continue
        # Best proxy_config overall
        best_pc = (msub.groupby("proxy_config")["recall"]
                   .mean().idxmax())
        pc_sub = msub[msub["proxy_config"] == best_pc].sort_values("budget")

        targets = {}
        for thr in [0.3, 0.5, 0.8]:
            hit = pc_sub.groupby("budget")["recall"].mean()
            hit_budgets = hit[hit >= thr]
            targets[thr] = (int(hit_budgets.index[0])
                            if len(hit_budgets) > 0 else None)

        def fmt_b(v):
            return str(v) if v is not None else "-"

        print(f"  {method:<22s}  {fmt_b(targets[0.3]):>10s}  "
              f"{fmt_b(targets[0.5]):>10s}  {fmt_b(targets[0.8]):>10s}")

    # Table 3: marginal utility
    print()
    print("=" * 110)
    print("TABLE 3: Marginal Utility (clips per 100 oracle calls)")
    print("=" * 110)
    hdr3 = (f"  {'budget':>6s}  {'candidate/100':>13s}  "
            f"{'audit/100':>10s}  {'better':>10s}")
    print(hdr3)
    print("-" * 50)
    for _, r in mu_df.iterrows():
        print(f"  {int(r['budget']):>6d}  "
              f"{r['candidate_clips_per_100_calls']:>13.2f}  "
              f"{r['audit_clips_per_100_calls']:>10.2f}  "
              f"{r['better_region']:>10s}")


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Kill experiment: joint allocation vs candidate-only")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--label-col", required=True)
    parser.add_argument("--min-len", type=int, default=15)
    parser.add_argument("--budgets", required=True)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",")]

    # Load data
    df = pd.read_csv(args.csv)
    labels = df[args.label_col].astype(int).tolist()
    N = len(labels)
    true_clips = labels_to_clips(labels, args.min_len)

    print(f"Joint Allocation Kill Experiment")
    print(f"  CSV: {args.csv}")
    print(f"  Label: {args.label_col}, min_len={args.min_len}")
    print(f"  Frames: {N}, true clips: {len(true_clips)}")
    print(f"  Budgets: {budgets}, trials: {args.trials}, seed: {args.seed}")
    print()

    # Try to load best configs from ARC transfer results
    arc_dir = "experiments/clip_boundary/arc_transfer_K10"
    proxy_configs = load_best_configs_from_arc(arc_dir, top_k=4)
    if proxy_configs is None:
        proxy_configs = get_default_configs()
    print(f"  Proxy configs: {len(proxy_configs)}")
    for pc in proxy_configs:
        print(f"    {pc['proxy_col']} {pc['threshold_desc']} g{pc['cand_gap']}")
    print()

    os.makedirs(args.out_dir, exist_ok=True)

    # Run
    print("Running experiments ...", flush=True)
    trials_df, gap_df = run_experiment(
        df, labels, true_clips, N, args.min_len, budgets, args.trials,
        args.seed, proxy_configs)

    # Marginal utility
    mu_df = compute_marginal_utility(trials_df)

    # Predicted clips
    pred_df = collect_predicted_clips(df, labels, true_clips, N, args.min_len,
                                      proxy_configs, args.seed)

    # Save
    trials_df.to_csv(os.path.join(args.out_dir, "trials.csv"), index=False)
    gap_df.to_csv(os.path.join(args.out_dir, "gap_details.csv"), index=False)
    mu_df.to_csv(os.path.join(args.out_dir, "marginal_utility.csv"),
                 index=False)
    if not pred_df.empty:
        pred_df.to_csv(os.path.join(args.out_dir, "predicted_clips.csv"),
                       index=False)

    # Summary CSV
    group_cols = ["method", "proxy_config", "budget"]
    summary = (trials_df.groupby(group_cols)
               .agg(mean_recall=("recall", "mean"),
                    std_recall=("recall", "std"),
                    mean_precision=("precision", "mean"),
                    std_precision=("precision", "std"),
                    mean_invalid_rate=("invalid_rate", "mean"),
                    mean_mIoU=("mIoU", "mean"),
                    mean_oracle_calls=("oracle_calls", "mean"),
                    mean_candidate_calls=("candidate_calls", "mean"),
                    mean_audit_calls=("audit_calls", "mean"),
                    mean_new_clips_from_candidate=(
                        "new_clips_from_candidate", "mean"),
                    mean_new_clips_from_audit=(
                        "new_clips_from_audit", "mean"),
                    mean_short_recall=("short_recall", "mean"),
                    mean_medium_recall=("medium_recall", "mean"),
                    mean_long_recall=("long_recall", "mean"),
                    best_gap=("best_gap", "first"))
               .reset_index())
    # Marginal utility
    summary["mean_candidate_clips_per_100_calls"] = (
        summary["mean_new_clips_from_candidate"] /
        summary["mean_candidate_calls"].replace(0, np.nan) * 100).fillna(0)
    summary["mean_audit_clips_per_100_calls"] = (
        summary["mean_new_clips_from_audit"] /
        summary["mean_audit_calls"].replace(0, np.nan) * 100).fillna(0)

    summary.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)

    # Config
    config = {
        "csv": os.path.abspath(args.csv),
        "label_col": args.label_col,
        "min_len": args.min_len,
        "budgets": budgets,
        "trials": args.trials,
        "seed": args.seed,
        "num_frames": N,
        "num_true_clips": len(true_clips),
        "positive_ratio": round(sum(labels) / N, 6),
        "proxy_configs": proxy_configs,
    }
    with open(os.path.join(args.out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    # Summary markdown
    write_summary_md(args.out_dir, trials_df, mu_df, config)

    # Terminal
    print_tables(trials_df, mu_df, budgets)

    print(f"\nResults saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
