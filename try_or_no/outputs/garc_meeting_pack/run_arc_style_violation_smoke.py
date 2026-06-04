#!/usr/bin/env python3
"""
ARC-style recall violation smoke test.

This is a SURROGATE motivation experiment, NOT an ARC reproduction.
Goal: test whether a confidence-like candidate quality metric can be high
while actual clip recall remains low.

Data: outputs/real_mvp/uadetrac_frame_table.csv (UA-DETRAC frame-level table)
"""

import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────
SEEDS = [0, 1, 2]
TAUS = [20, 30]
KS = [20, 25]           # K=20: ~8.6% oracle positive rate (medium)
                         # K=25: ~3.1% oracle positive rate (low)
BUDGET_RATIOS = [0.05, 0.10, 0.20]
THETA = 0.5             # IoU threshold for clip hit
GAMMA_VALUES = [0.9]    # target frame-level recall for SUPG-style

# Proxy score thresholds for candidate generation.
# The proxy_score is well-calibrated, so we need VERY high thresholds
# to create a meaningful gap between frame-level proxy recall and
# clip-level coverage.
# p90:  proxy_recall ~90% — candidates cover most true clips
# p95:  proxy_recall ~57% — moderate coverage
# p99:  proxy_recall ~12% — candidates are sparse, many clips missed
# p99.5: proxy_recall ~6%  — very sparse candidates
PROXY_SCORE_THRESHOLDS = {
    'p90':   0.800,   # top 10%
    'p95':   0.849,   # top 5%
    'p99':   0.907,   # top 1%
    'p99.5': 0.923,   # top 0.5%
}

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_PATH = SCRIPT_DIR.parent / "real_mvp" / "uadetrac_frame_table.csv"
OUT_DIR = SCRIPT_DIR
CSV_PATH = OUT_DIR / "arc_style_violation_smoke.csv"


# ─── Clip utilities ──────────────────────────────────────────────────────────
def find_true_clips(oracle_positive: np.ndarray, tau: int) -> list:
    """
    Find maximal consecutive runs of True with length >= tau.
    Returns list of (start, end) tuples (end exclusive).
    """
    clips = []
    n = len(oracle_positive)
    i = 0
    while i < n:
        if oracle_positive[i]:
            j = i
            while j < n and oracle_positive[j]:
                j += 1
            if j - i >= tau:
                clips.append((i, j))
            i = j
        else:
            i += 1
    return clips


def find_candidate_clips(predicted_positive: np.ndarray, tau: int) -> list:
    """Same as find_true_clips but on predicted positives."""
    return find_true_clips(predicted_positive, tau)


def clip_iou(a: tuple, b: tuple) -> float:
    """Temporal IoU between two clips (start, end) tuples."""
    inter_start = max(a[0], b[0])
    inter_end = min(a[1], b[1])
    inter = max(0, inter_end - inter_start)
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def compute_clip_metrics(true_clips: list, candidate_clips: list, theta: float):
    """
    Returns: clip_recall, clip_precision, mean_iou, num_true, num_candidate
    """
    num_true = len(true_clips)
    num_cand = len(candidate_clips)

    if num_true == 0 and num_cand == 0:
        return 1.0, 1.0, 1.0, 0, 0
    if num_true == 0:
        return 1.0, 0.0, 0.0, 0, num_cand
    if num_cand == 0:
        return 0.0, 0.0, 0.0, num_true, 0

    # For each true clip, find best matching candidate
    true_hits = []
    true_best_ious = []
    for tc in true_clips:
        best_iou = 0.0
        for cc in candidate_clips:
            iou = clip_iou(tc, cc)
            if iou > best_iou:
                best_iou = iou
        true_best_ious.append(best_iou)
        true_hits.append(best_iou >= theta)

    # For each candidate, find best matching true clip
    cand_hits = []
    cand_best_ious = []
    for cc in candidate_clips:
        best_iou = 0.0
        for tc in true_clips:
            iou = clip_iou(tc, cc)
            if iou > best_iou:
                best_iou = iou
        cand_best_ious.append(best_iou)
        cand_hits.append(best_iou >= theta)

    recall = sum(true_hits) / num_true
    precision = sum(cand_hits) / num_cand

    # Mean IoU over all matched pairs
    all_ious = true_best_ious + cand_best_ious
    miou = np.mean(all_ious) if all_ious else 0.0

    return recall, precision, miou, num_true, num_cand


# ─── Methods ─────────────────────────────────────────────────────────────────

def method_full_oracle(oracle_positive: np.ndarray, tau: int, **kwargs):
    """Upper bound: use oracle labels for all frames."""
    predicted = oracle_positive.copy()
    return predicted, 1.0, None  # oracle_ratio, reported_confidence


def method_uniform_sampling_stitch(oracle_positive: np.ndarray, tau: int,
                                    budget_ratio: float, seed: int, **kwargs):
    """
    Sample budget_ratio * N frames uniformly.
    Use oracle labels on sampled frames, mark unsampled as negative.
    Stitch predicted positive frames into clips.
    """
    n = len(oracle_positive)
    rng = np.random.RandomState(seed)
    budget = max(1, int(budget_ratio * n))
    sampled_idx = rng.choice(n, size=min(budget, n), replace=False)

    predicted = np.zeros(n, dtype=bool)
    predicted[sampled_idx] = oracle_positive[sampled_idx]

    oracle_ratio = len(sampled_idx) / n
    return predicted, oracle_ratio, None


def method_fixed_proxy_threshold_stitch(proxy_score: np.ndarray, oracle_positive: np.ndarray,
                                         tau: int, proxy_thresh: float, **kwargs):
    """
    Use proxy_score >= threshold to mark positive frames.
    Stitch positive frames into clips.
    oracle_ratio = 0 (no oracle used).
    """
    predicted = proxy_score >= proxy_thresh
    return predicted, 0.0, None


def method_supg_style_frame_selection_stitch(proxy_score: np.ndarray, oracle_positive: np.ndarray,
                                              tau: int, budget_ratio: float, seed: int,
                                              gamma: float = 0.9, **kwargs):
    """
    SUPG-style SURROGATE (not exact SUPG).
    1. Sample frames with probability biased toward high proxy score.
    2. Estimate proxy threshold T from oracle samples targeting frame recall gamma.
    3. Return all frames with proxy_score >= T, stitch into clips.
    """
    n = len(oracle_positive)
    rng = np.random.RandomState(seed)
    budget = max(1, int(budget_ratio * n))

    # Defensive mixture: 50% proxy-biased, 50% uniform
    half = budget // 2
    # Proxy-biased half
    weights = proxy_score + 1e-8
    weights = weights / weights.sum()
    biased_idx = rng.choice(n, size=min(half, n), replace=False, p=weights)
    # Uniform half
    uniform_idx = rng.choice(n, size=min(budget - half, n), replace=False)
    sampled_idx = np.unique(np.concatenate([biased_idx, uniform_idx]))

    # Oracle labels on sampled frames
    oracle_labels = oracle_positive[sampled_idx]
    sample_scores = proxy_score[sampled_idx]

    # Calibrate threshold T: find score such that frame-level recall >= gamma
    pos_mask = oracle_labels
    if pos_mask.sum() == 0:
        # No oracle positives in sample; use high quantile as fallback
        T = np.percentile(proxy_score, 90)
    else:
        pos_scores = sample_scores[pos_mask]
        sorted_scores = np.sort(pos_scores)
        idx = max(0, int(np.floor((1 - gamma) * len(sorted_scores))) - 1)
        T = sorted_scores[idx]

    predicted = proxy_score >= T
    oracle_ratio = len(sampled_idx) / n
    return predicted, oracle_ratio, None


def method_arc_style_surrogate(proxy_score: np.ndarray, oracle_positive: np.ndarray,
                                tau: int, budget_ratio: float, seed: int,
                                proxy_thresh: float, **kwargs):
    """
    ARC-style SURROGATE (not ARC reproduction).

    1. Candidate generation: use proxy_score >= threshold to form candidate
       clips. Merge runs separated by gap <= tau/3.
    2. Refinement: spend oracle budget mostly inside candidate clips and near
       boundaries. Use oracle labels to refine candidate boundaries.
    3. Confidence: estimate candidate-side confidence from oracle samples
       inside candidates. Measures how likely returned candidates are hits.
       Does NOT estimate missed true clips outside candidates.
    """
    n = len(oracle_positive)
    rng = np.random.RandomState(seed)
    budget = max(1, int(budget_ratio * n))
    gap_merge = max(1, int(tau / 3))

    # ── Step 1: Candidate generation from proxy ──
    proxy_pos = proxy_score >= proxy_thresh

    # Find proxy-positive runs and merge small gaps
    runs = []
    i = 0
    while i < n:
        if proxy_pos[i]:
            j = i
            while j < n and proxy_pos[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1

    # Merge runs separated by gap <= gap_merge
    if len(runs) > 1:
        merged = [runs[0]]
        for start, end in runs[1:]:
            prev_start, prev_end = merged[-1]
            if start - prev_end <= gap_merge:
                merged[-1] = (prev_start, end)
            else:
                merged.append((start, end))
        candidate_runs = merged
    else:
        candidate_runs = runs

    # Mark initial candidate frames
    candidate_mask = np.zeros(n, dtype=bool)
    for start, end in candidate_runs:
        candidate_mask[start:end] = True

    # ── Step 2: Oracle refinement ──
    candidate_indices = np.where(candidate_mask)[0]
    non_candidate_indices = np.where(~candidate_mask)[0]

    # Allocate 80% budget to candidates, 20% outside
    cand_budget = max(1, int(0.8 * budget))
    outside_budget = budget - cand_budget

    # Sample inside candidates (biased toward boundaries)
    cand_sampled = np.array([], dtype=int)
    if len(candidate_indices) > 0 and cand_budget > 0:
        # Find boundary frames (within gap_merge of candidate start/end)
        boundary_frames = set()
        for start, end in candidate_runs:
            for offset in range(-gap_merge, gap_merge + 1):
                idx = start + offset
                if 0 <= idx < n:
                    boundary_frames.add(idx)
                idx = end - 1 + offset
                if 0 <= idx < n:
                    boundary_frames.add(idx)
        boundary_frames = np.array(sorted(boundary_frames & set(candidate_indices.tolist())))

        # 50% of cand budget on boundaries, 50% uniform inside
        half_cand = cand_budget // 2
        if len(boundary_frames) > 0:
            bnd_sample = rng.choice(boundary_frames,
                                     size=min(half_cand, len(boundary_frames)),
                                     replace=False)
        else:
            bnd_sample = np.array([], dtype=int)

        remaining_cand = cand_budget - len(bnd_sample)
        if remaining_cand > 0 and len(candidate_indices) > 0:
            uni_sample = rng.choice(candidate_indices,
                                     size=min(remaining_cand, len(candidate_indices)),
                                     replace=False)
        else:
            uni_sample = np.array([], dtype=int)

        cand_sampled = np.unique(np.concatenate([bnd_sample, uni_sample]))

    # Sample outside candidates uniformly
    out_sampled = np.array([], dtype=int)
    if len(non_candidate_indices) > 0 and outside_budget > 0:
        out_sampled = rng.choice(non_candidate_indices,
                                   size=min(outside_budget, len(non_candidate_indices)),
                                   replace=False)

    all_sampled = np.unique(np.concatenate([cand_sampled, out_sampled]))

    # Refine candidates: use oracle labels on sampled frames
    predicted = np.zeros(n, dtype=bool)

    # Inside candidates: use oracle if sampled, else keep proxy prediction
    for start, end in candidate_runs:
        for idx in range(start, end):
            if idx in all_sampled:
                predicted[idx] = oracle_positive[idx]
            else:
                predicted[idx] = proxy_pos[idx]

    # Outside candidates: only use oracle if sampled (else negative)
    for idx in out_sampled:
        predicted[idx] = oracle_positive[idx]

    # ── Step 3: Confidence estimation ──
    # The key insight: confidence measures QUALITY of candidates (precision-like),
    # NOT coverage of true clips (recall). This is the blind spot.
    # If candidates are concentrated in a subset of videos while true clips
    # are elsewhere, confidence can be high while recall is low.
    #
    # We estimate: what fraction of oracle samples inside candidates are positive?
    # This measures "are our candidates pointing at real things?"
    # It does NOT measure "did we find all real things?"
    if len(cand_sampled) > 0:
        cand_oracle = oracle_positive[cand_sampled]
        reported_confidence = float(cand_oracle.mean())
    else:
        reported_confidence = 0.0

    oracle_ratio = len(all_sampled) / n
    return predicted, oracle_ratio, reported_confidence


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    df = pd.read_csv(DATA_PATH)
    N = len(df)
    print(f"  {N} frames, {df['video_id'].nunique()} videos")

    oracle_counts = df['vehicle_count_gt'].values
    proxy_scores = df['proxy_score'].values

    # Pre-compute proxy score percentiles for reference
    for pct in [80, 90, 95]:
        thresh = np.percentile(proxy_scores, pct)
        print(f"  proxy_score p{pct} = {thresh:.3f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for K in KS:
        oracle_positive = oracle_counts >= K
        pos_rate = oracle_positive.mean()
        print(f"\n  K={K}, oracle positive rate={pos_rate:.3f}")

        for tau in TAUS:
            true_clips = find_true_clips(oracle_positive, tau)
            print(f"    tau={tau}, true clips={len(true_clips)}")

            for proxy_label, proxy_thresh in PROXY_SCORE_THRESHOLDS.items():
                proxy_pos = proxy_scores >= proxy_thresh
                proxy_recall = (proxy_pos & oracle_positive).sum() / oracle_positive.sum()
                print(f"    proxy_thresh={proxy_label} ({proxy_thresh:.3f}): "
                      f"proxy_recall={proxy_recall:.3f}")

                for budget_ratio in BUDGET_RATIOS:
                    for seed in SEEDS:
                        # ── Method 1: full_oracle (once per K, tau, proxy_thresh) ──
                        if budget_ratio == BUDGET_RATIOS[0] and seed == SEEDS[0]:
                            predicted, oracle_ratio, reported_conf = method_full_oracle(
                                oracle_positive, tau)
                            cand_clips = find_candidate_clips(predicted, tau)
                            recall, precision, miou, n_true, n_cand = compute_clip_metrics(
                                true_clips, cand_clips, THETA)
                            results.append({
                                'dataset': 'uadetrac', 'K': K, 'tau': tau,
                                'proxy_threshold': proxy_label,
                                'budget_ratio': budget_ratio, 'seed': seed,
                                'method': 'full_oracle',
                                'reported_confidence': reported_conf,
                                'actual_clip_recall': recall,
                                'actual_clip_precision': precision,
                                'mIoU': miou, 'oracle_ratio': oracle_ratio,
                                'violation_0.8': recall < 0.8,
                                'violation_0.9': recall < 0.9,
                                'num_true_clips': n_true,
                                'num_candidate_clips': n_cand,
                            })

                        # ── Method 2: uniform_sampling_stitch ──
                        predicted, oracle_ratio, reported_conf = method_uniform_sampling_stitch(
                            oracle_positive, tau, budget_ratio=budget_ratio, seed=seed)
                        cand_clips = find_candidate_clips(predicted, tau)
                        recall, precision, miou, n_true, n_cand = compute_clip_metrics(
                            true_clips, cand_clips, THETA)
                        results.append({
                            'dataset': 'uadetrac', 'K': K, 'tau': tau,
                            'proxy_threshold': proxy_label,
                            'budget_ratio': budget_ratio, 'seed': seed,
                            'method': 'uniform_sampling_stitch',
                            'reported_confidence': reported_conf,
                            'actual_clip_recall': recall,
                            'actual_clip_precision': precision,
                            'mIoU': miou, 'oracle_ratio': oracle_ratio,
                            'violation_0.8': recall < 0.8,
                            'violation_0.9': recall < 0.9,
                            'num_true_clips': n_true,
                            'num_candidate_clips': n_cand,
                        })

                        # ── Method 3: fixed_proxy_threshold_stitch ──
                        predicted, oracle_ratio, reported_conf = method_fixed_proxy_threshold_stitch(
                            proxy_scores, oracle_positive, tau=tau, proxy_thresh=proxy_thresh)
                        cand_clips = find_candidate_clips(predicted, tau)
                        recall, precision, miou, n_true, n_cand = compute_clip_metrics(
                            true_clips, cand_clips, THETA)
                        results.append({
                            'dataset': 'uadetrac', 'K': K, 'tau': tau,
                            'proxy_threshold': proxy_label,
                            'budget_ratio': budget_ratio, 'seed': seed,
                            'method': 'fixed_proxy_threshold_stitch',
                            'reported_confidence': reported_conf,
                            'actual_clip_recall': recall,
                            'actual_clip_precision': precision,
                            'mIoU': miou, 'oracle_ratio': oracle_ratio,
                            'violation_0.8': recall < 0.8,
                            'violation_0.9': recall < 0.9,
                            'num_true_clips': n_true,
                            'num_candidate_clips': n_cand,
                        })

                        # ── Method 4: supg_style_frame_selection_stitch ──
                        predicted, oracle_ratio, reported_conf = method_supg_style_frame_selection_stitch(
                            proxy_scores, oracle_positive, tau=tau,
                            budget_ratio=budget_ratio, seed=seed, gamma=0.9)
                        cand_clips = find_candidate_clips(predicted, tau)
                        recall, precision, miou, n_true, n_cand = compute_clip_metrics(
                            true_clips, cand_clips, THETA)
                        results.append({
                            'dataset': 'uadetrac', 'K': K, 'tau': tau,
                            'proxy_threshold': proxy_label,
                            'budget_ratio': budget_ratio, 'seed': seed,
                            'method': 'supg_style_frame_selection_stitch',
                            'reported_confidence': reported_conf,
                            'actual_clip_recall': recall,
                            'actual_clip_precision': precision,
                            'mIoU': miou, 'oracle_ratio': oracle_ratio,
                            'violation_0.8': recall < 0.8,
                            'violation_0.9': recall < 0.9,
                            'num_true_clips': n_true,
                            'num_candidate_clips': n_cand,
                        })

                        # ── Method 5: arc_style_surrogate ──
                        predicted, oracle_ratio, reported_conf = method_arc_style_surrogate(
                            proxy_scores, oracle_positive, tau=tau,
                            budget_ratio=budget_ratio, seed=seed,
                            proxy_thresh=proxy_thresh)
                        cand_clips = find_candidate_clips(predicted, tau)
                        recall, precision, miou, n_true, n_cand = compute_clip_metrics(
                            true_clips, cand_clips, THETA)
                        results.append({
                            'dataset': 'uadetrac', 'K': K, 'tau': tau,
                            'proxy_threshold': proxy_label,
                            'budget_ratio': budget_ratio, 'seed': seed,
                            'method': 'arc_style_surrogate',
                            'reported_confidence': reported_conf,
                            'actual_clip_recall': recall,
                            'actual_clip_precision': precision,
                            'mIoU': miou, 'oracle_ratio': oracle_ratio,
                            'violation_0.8': recall < 0.8,
                            'violation_0.9': recall < 0.9,
                            'num_true_clips': n_true,
                            'num_candidate_clips': n_cand,
                        })

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(CSV_PATH, index=False)
    print(f"\nResults saved to {CSV_PATH}")
    print(f"Total rows: {len(results_df)}")

    # Print violation summary for arc_style_surrogate
    print("\n" + "="*80)
    print("VIOLATION SUMMARY (arc_style_surrogate only):")
    arc_rows = results_df[results_df['method'] == 'arc_style_surrogate']
    violations = arc_rows[arc_rows['violation_0.8']]
    print(f"  Total arc_style_surrogate rows: {len(arc_rows)}")
    print(f"  Rows with violation_0.8: {len(violations)}")
    if len(violations) > 0:
        print("\n  Violation rows (conf >= 0.8 and recall < 0.8):")
        for _, row in violations.iterrows():
            if row['reported_confidence'] is not None and row['reported_confidence'] >= 0.8:
                print(f"    K={row['K']}, tau={row['tau']}, proxy={row['proxy_threshold']}, "
                      f"budget={row['budget_ratio']}, seed={row['seed']}: "
                      f"conf={row['reported_confidence']:.3f}, recall={row['actual_clip_recall']:.3f}")

    # Also print all arc_style_surrogate rows for inspection
    print("\n  All arc_style_surrogate rows:")
    for _, row in arc_rows.iterrows():
        marker = " *** VIOL_0.8 ***" if row['violation_0.8'] else ""
        conf_str = f"{row['reported_confidence']:.3f}" if row['reported_confidence'] is not None else "None"
        print(f"    K={row['K']}, tau={row['tau']}, proxy={row['proxy_threshold']}, "
              f"budget={row['budget_ratio']}, seed={row['seed']}: "
              f"conf={conf_str}, recall={row['actual_clip_recall']:.3f}, "
              f"prec={row['actual_clip_precision']:.3f}, "
              f"oracle_ratio={row['oracle_ratio']:.3f}{marker}")

    return results_df


if __name__ == '__main__':
    main()
