#!/usr/bin/env python3
"""
run_realcar_5k_stress_test.py

Run ARC stress test on realcar_5k moving-camera data.
Tests 7 methods × 3 tau × 3 budget = 63 experiments.

Usage:
    python scripts/run_realcar_5k_stress_test.py
"""

import sys
import os
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# Add ARC source to path
sys.path.insert(0, 'arc_source/arc')
sys.path.insert(0, 'arc_source/experiments')

from tools import generate_oracle_proxy, generate_cluster, findCandClips
from arc import arc
from refinement_phase import calculate_confidence
from pruning_phase import init_probabilities, init_cluster_uncertainties
from score_tools import entropy

# ── Configuration ──────────────────────────────────────────────────────────

CDF_PATH = 'data_moving_arc/realcar_5k/realcar_5k_K12.csv'
CLUSTER_PATH = 'data_moving_arc/realcar_5k/cluster/realcar_5k-0.001.csv'
ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
OUTPUT_CSV = 'outputs/realcar_5k_arc_stress_results.csv'
OUTPUT_REPORT = 'outputs/realcar_5k_arc_stress_test_report.md'

K = 12
ARC_CONSTANT = 0  # ARC always uses constant=0 at runtime
DATA_CONSTANT = K - 1  # Used only for generate_oracle_proxy column selection

TAU_VALUES = [30, 60, 120]
BUDGET_FRACS = [0.02, 0.05, 0.10]

METHODS = [
    ('Oracle-Only', None),
    ('YOLOv8n-Only', None),
    ('CMDN-Uniform', None),
    ('CMDN-Importance', None),
    ('ARC', None),
    ('ARC-noTC', None),
    ('ARC-noLP', None),
]

CONFIDENCE = 0.9
IOU_THRESHOLD = 0.9

# ── Helpers ────────────────────────────────────────────────────────────────

def load_data():
    """Load ARC inputs and original data."""
    oracle, proxy, oracle_score, proxy_score = generate_oracle_proxy(
        CDF_PATH, '>', DATA_CONSTANT)
    clusters = generate_cluster(CLUSTER_PATH)
    orig = pd.read_csv(ORACLE_CSV)

    n = len(oracle)
    B_max = int(max(BUDGET_FRACS) * n)

    # Proxy score from YOLOv8n (for YOLOv8n-Only baseline)
    yolo_score = (orig['proxy_vehicle_count'].values >= K).astype(int)

    return oracle, proxy, oracle_score, proxy_score, clusters, yolo_score, n, orig


def compute_gt_clips(oracle_score, tau):
    """Find ground-truth clips."""
    return findCandClips(oracle_score, '>', 0, tau)


def calc_iou(seg1, seg2):
    """IoU between two [start, end] inclusive segments."""
    inter_start = max(seg1[0], seg2[0])
    inter_end = min(seg1[1], seg2[1])
    inter_len = max(0, inter_end - inter_start + 1)
    union_start = min(seg1[0], seg2[0])
    union_end = max(seg1[1], seg2[1])
    union_len = union_end - union_start + 1
    return inter_len / union_len if union_len > 0 else 0.0


def calc_precision_recall_iou(gt_clips, pred_clips, threshold=0.9):
    """Calculate precision, recall, mIoU."""
    if len(gt_clips) == 0 and len(pred_clips) == 0:
        return 1.0, 1.0, 1.0
    if len(gt_clips) == 0:
        return 0.0, 1.0, 0.0
    if len(pred_clips) == 0:
        return 1.0, 0.0, 0.0

    # Precision: fraction of pred clips that match a GT clip
    hits_precision = 0
    for pred in pred_clips:
        ious = np.array([calc_iou(pred, gt) for gt in gt_clips])
        if np.any(ious >= threshold):
            hits_precision += 1
    precision = hits_precision / len(pred_clips)

    # Recall: fraction of GT clips matched by a pred clip
    hits_recall = 0
    total_iou = 0.0
    for gt in gt_clips:
        ious = np.array([calc_iou(gt, pred) for pred in pred_clips])
        max_iou = np.max(ious) if len(ious) > 0 else 0.0
        if max_iou >= threshold:
            hits_recall += 1
        total_iou += max_iou
    recall = hits_recall / len(gt_clips)
    miou = total_iou / len(gt_clips)

    return precision, recall, miou


def run_oracle_only(oracle_score, tau):
    """Oracle-Only baseline: use all oracle labels."""
    clips = findCandClips(oracle_score, '>', 0, tau)
    oracle_calls = len(oracle_score)
    return clips, oracle_calls


def run_yolo_only(yolo_score, tau):
    """YOLOv8n-Only baseline: use proxy labels directly."""
    clips = findCandClips(yolo_score, '>', 0, tau)
    oracle_calls = 0
    return clips, oracle_calls


def run_cmdn_uniform(proxy, oracle, proxy_score, oracle_score, B, tau, seed=42):
    """CMDN-Uniform: uniform random sampling + label propagation."""
    rng = np.random.RandomState(seed)
    n = len(proxy)
    score = proxy_score.copy()

    sampled = np.zeros(n, dtype=bool)
    budget_used = 0

    for _ in range(B):
        not_sampled = np.where(~sampled)[0]
        if len(not_sampled) == 0:
            break
        idx = rng.choice(not_sampled)
        score[idx] = oracle_score[idx]
        sampled[idx] = True
        budget_used += 1

    clips = findCandClips(score, '>', 0, tau)
    return clips, budget_used


def run_cmdn_importance(proxy, oracle, proxy_score, oracle_score, B, tau, seed=42):
    """CMDN-Importance: importance-weighted sampling."""
    rng = np.random.RandomState(seed)
    n = len(proxy)
    score = proxy_score.copy()

    # Importance weights from proxy[:,1] (positive probability)
    weights = np.sqrt(np.maximum(proxy[:, 1], 1e-10))
    weights = weights / weights.sum()
    uniform = np.ones(n) / n
    mixed = weights * 0.9 + uniform * 0.1

    sampled = np.zeros(n, dtype=bool)
    budget_used = 0

    for _ in range(B):
        not_sampled = np.where(~sampled)[0]
        if len(not_sampled) == 0:
            break
        # Sample from mixed distribution over unsampled indices
        sub_weights = mixed[not_sampled]
        sub_weights = sub_weights / sub_weights.sum()
        idx = rng.choice(not_sampled, p=sub_weights)
        score[idx] = oracle_score[idx]
        sampled[idx] = True
        budget_used += 1

    clips = findCandClips(score, '>', 0, tau)
    return clips, budget_used


def run_arc_variant(proxy, oracle, proxy_score, oracle_score, B, tau,
                    clusters, tc_enabled=True, lp_enabled=True):
    """Run ARC or a variant (noTC, noLP)."""
    try:
        result = arc(
            proxy, oracle, proxy_score, oracle_score,
            B, '>', ARC_CONSTANT, tau,
            CONFIDENCE, IOU_THRESHOLD, clusters,
            tc_enabled=tc_enabled, ps_enabled=True, lp_enabled=lp_enabled
        )
        clips = result['cand_clips']
        oracle_calls = result['B']
        return clips, oracle_calls, result
    except Exception as e:
        return np.empty((0, 2), dtype=int), 0, {'error': str(e)[:100]}


def compute_cluster_stats(clusters):
    """Compute cluster statistics."""
    unique, counts = np.unique(clusters, return_counts=True)
    return {
        'cluster_count': len(unique),
        'avg_cluster_len': float(np.mean(counts)),
        'median_cluster_len': float(np.median(counts)),
    }


def compute_proxy_oracle_corr(proxy_score, oracle_score):
    """Compute correlation between proxy and oracle scores."""
    if np.std(proxy_score) == 0 or np.std(oracle_score) == 0:
        return 0.0
    return float(np.corrcoef(proxy_score, oracle_score)[0, 1])


def count_clips_in_single_cluster(clips, clusters):
    """Count how many clips fall within a single cluster."""
    if len(clips) == 0:
        return 0, 0
    single = 0
    for start, end in clips:
        clip_clusters = clusters[start:end + 1]
        if len(np.unique(clip_clusters)) == 1:
            single += 1
    return single, len(clips)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("realcar_5k ARC Stress Test")
    print("=" * 70)

    # Load data
    oracle, proxy, oracle_score, proxy_score, clusters, yolo_score, n, orig = load_data()
    print(f"Loaded {n} frames")
    print(f"Oracle positive rate: {oracle_score.mean():.4f}")
    print(f"Proxy positive rate: {proxy_score.mean():.4f}")
    print(f"Proxy-oracle correlation: {compute_proxy_oracle_corr(proxy_score, oracle_score):.4f}")
    print(f"Clusters: {len(np.unique(clusters))}")
    print()

    # Pre-compute cluster stats
    cluster_stats = compute_cluster_stats(clusters)
    proxy_oracle_corr = compute_proxy_oracle_corr(proxy_score, oracle_score)
    positive_rate = float(oracle_score.mean())

    # Results storage
    results = []

    # Run experiments
    total_experiments = len(TAU_VALUES) * len(BUDGET_FRACS) * len(METHODS)
    experiment_idx = 0

    for tau in TAU_VALUES:
        gt_clips = compute_gt_clips(oracle_score, tau)
        gt_count = len(gt_clips)
        print(f"\n{'='*70}")
        print(f"tau={tau}: GT clips = {gt_count}")
        print(f"{'='*70}")

        for budget_frac in BUDGET_FRACS:
            B = int(budget_frac * n)
            print(f"\n  Budget: {budget_frac:.0%} (B={B})")

            for method_name, _ in METHODS:
                experiment_idx += 1
                print(f"    [{experiment_idx}/{total_experiments}] {method_name}...", end=" ", flush=True)

                t0 = time.time()

                if method_name == 'Oracle-Only':
                    clips, oracle_calls = run_oracle_only(oracle_score, tau)
                    arc_result = None
                elif method_name == 'YOLOv8n-Only':
                    clips, oracle_calls = run_yolo_only(yolo_score, tau)
                    arc_result = None
                elif method_name == 'CMDN-Uniform':
                    clips, oracle_calls = run_cmdn_uniform(
                        proxy, oracle, proxy_score, oracle_score, B, tau)
                    arc_result = None
                elif method_name == 'CMDN-Importance':
                    clips, oracle_calls = run_cmdn_importance(
                        proxy, oracle, proxy_score, oracle_score, B, tau)
                    arc_result = None
                elif method_name == 'ARC':
                    clips, oracle_calls, arc_result = run_arc_variant(
                        proxy, oracle, proxy_score, oracle_score, B, tau,
                        clusters, tc_enabled=True, lp_enabled=True)
                elif method_name == 'ARC-noTC':
                    clips, oracle_calls, arc_result = run_arc_variant(
                        proxy, oracle, proxy_score, oracle_score, B, tau,
                        clusters, tc_enabled=False, lp_enabled=True)
                elif method_name == 'ARC-noLP':
                    clips, oracle_calls, arc_result = run_arc_variant(
                        proxy, oracle, proxy_score, oracle_score, B, tau,
                        clusters, tc_enabled=True, lp_enabled=False)
                else:
                    continue

                t1 = time.time()
                runtime = t1 - t0

                # Compute metrics
                precision, recall, miou = calc_precision_recall_iou(gt_clips, clips)
                recall_per_call = recall / oracle_calls if oracle_calls > 0 else 0.0

                # ARC-specific diagnostics
                final_confidence = 0.0
                if arc_result is not None and 'error' not in arc_result:
                    # Re-compute confidence for the final clips
                    if len(clips) > 0:
                        try:
                            PD = proxy.copy()
                            score = proxy_score.copy()
                            init_probabilities(PD, 0, [0.9999, 0.0001])
                            init_probabilities(PD, 1, [0.0001, 0.9999])
                            entropy_array = np.apply_along_axis(entropy, 1, proxy)
                            cb, unc, probs = init_cluster_uncertainties(
                                clusters, entropy_array, proxy)
                            _, final_confidence = calculate_confidence(
                                clips, IOU_THRESHOLD, probs, clusters, cb)
                            if np.isnan(final_confidence):
                                final_confidence = 0.0
                        except Exception:
                            final_confidence = 0.0

                # Count clips in single cluster
                single_cluster_clips, total_clips = count_clips_in_single_cluster(
                    clips, clusters)

                row = {
                    'dataset': 'realcar_5k',
                    'K': K,
                    'tau': tau,
                    'budget': budget_frac,
                    'method': method_name,
                    'clips': len(clips),
                    'precision': round(precision, 4),
                    'recall': round(recall, 4),
                    'mIoU': round(miou, 4),
                    'oracle_calls': oracle_calls,
                    'recall_per_call': round(recall_per_call, 6),
                    'final_confidence': round(float(final_confidence), 4),
                    'cluster_count': cluster_stats['cluster_count'],
                    'avg_cluster_len': round(cluster_stats['avg_cluster_len'], 1),
                    'median_cluster_len': round(cluster_stats['median_cluster_len'], 1),
                    'proxy_oracle_corr': round(proxy_oracle_corr, 4),
                    'positive_rate': round(positive_rate, 4),
                    'runtime_sec': round(runtime, 3),
                    'gt_clips': gt_count,
                    'single_cluster_clips': single_cluster_clips,
                    'total_clips_eval': total_clips,
                }
                results.append(row)

                print(f"clips={len(clips)}, P={precision:.3f}, R={recall:.3f}, "
                      f"IoU={miou:.3f}, oracle={oracle_calls}, {runtime:.2f}s")

    # Save results
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nResults saved to {OUTPUT_CSV}")

    return df


if __name__ == '__main__':
    main()
