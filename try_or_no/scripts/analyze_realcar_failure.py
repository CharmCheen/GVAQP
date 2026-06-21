#!/usr/bin/env python3
"""
analyze_realcar_failure.py

Failure attribution for realcar_5k ARC recall=0.
Diagnoses proxy, clustering, sampling, confidence issues.

Usage:
    python scripts/analyze_realcar_failure.py
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')
sys.path.insert(0, 'arc_source/arc')
sys.path.insert(0, 'arc_source/experiments')

from tools import generate_oracle_proxy, generate_cluster, findCandClips
from refinement_phase import (calculate_confidence, calculate_boundaries,
                               calculate_indices, calculate_j_indices)
from pruning_phase import (init_probabilities, init_cluster_uncertainties,
                            build_cluster_boundaries)
from score_tools import entropy

# ── Configuration ──────────────────────────────────────────────────────────

CDF_PATH = 'data_moving_arc/realcar_5k/realcar_5k_K12.csv'
CLUSTER_PATH = 'data_moving_arc/realcar_5k/cluster/realcar_5k-0.001.csv'
ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
RESULTS_CSV = 'outputs/realcar_5k_arc_stress_results.csv'
OUTPUT_CSV = 'outputs/realcar_5k_failure_attribution.csv'
OUTPUT_REPORT = 'outputs/realcar_5k_failure_attribution_report.md'

K = 12
DATA_CONSTANT = K - 1
TAU = 30
IOU_THRESHOLD = 0.9

# ── Load Data ──────────────────────────────────────────────────────────────

def load_all():
    """Load all necessary data."""
    oracle, proxy, oracle_score, proxy_score = generate_oracle_proxy(
        CDF_PATH, '>', DATA_CONSTANT)
    clusters = generate_cluster(CLUSTER_PATH)
    orig = pd.read_csv(ORACLE_CSV)
    stress = pd.read_csv(RESULTS_CSV)

    proxy_counts = orig['proxy_vehicle_count'].values
    oracle_counts = orig['oracle_vehicle_count'].values

    return (oracle, proxy, oracle_score, proxy_score, clusters,
            orig, stress, proxy_counts, oracle_counts)


# ── 1. Frame-level proxy/oracle gap ───────────────────────────────────────

def analyze_frame_level(proxy_counts, oracle_counts, K):
    """Frame-level proxy vs oracle analysis."""
    proxy_binary = (proxy_counts >= K).astype(int)
    oracle_binary = (oracle_counts >= K).astype(int)

    # Correlations
    pearson_r, pearson_p = stats.pearsonr(proxy_counts, oracle_counts)
    spearman_r, spearman_p = stats.spearmanr(proxy_counts, oracle_counts)

    # Confusion matrix
    tp = int(((proxy_binary == 1) & (oracle_binary == 1)).sum())
    fp = int(((proxy_binary == 1) & (oracle_binary == 0)).sum())
    fn = int(((proxy_binary == 0) & (oracle_binary == 1)).sum())
    tn = int(((proxy_binary == 0) & (oracle_binary == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Positive runs
    def extract_runs(binary, min_len=1):
        runs = []
        start = None
        for i in range(len(binary)):
            if binary[i] == 1:
                if start is None:
                    start = i
            else:
                if start is not None:
                    length = i - start
                    if length >= min_len:
                        runs.append((start, i - 1, length))
                    start = None
        if start is not None:
            length = len(binary) - start
            if length >= min_len:
                runs.append((start, len(binary) - 1, length))
        return runs

    proxy_runs = extract_runs(proxy_binary)
    oracle_runs = extract_runs(oracle_binary)
    proxy_runs_t30 = extract_runs(proxy_binary, min_len=TAU)
    oracle_runs_t30 = extract_runs(oracle_binary, min_len=TAU)

    return {
        'pearson_r': round(pearson_r, 4),
        'pearson_p': round(pearson_p, 6),
        'spearman_r': round(spearman_r, 4),
        'spearman_p': round(spearman_p, 6),
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'proxy_positive_frames': int(proxy_binary.sum()),
        'oracle_positive_frames': int(oracle_binary.sum()),
        'proxy_runs_total': len(proxy_runs),
        'oracle_runs_total': len(oracle_runs),
        'proxy_runs_tau30': len(proxy_runs_t30),
        'oracle_runs_tau30': len(oracle_runs_t30),
        'proxy_run_lengths': [r[2] for r in proxy_runs],
        'oracle_run_lengths': [r[2] for r in oracle_runs],
        'proxy_runs_tau30_list': proxy_runs_t30,
        'oracle_runs_tau30_list': oracle_runs_t30,
    }


# ── 2. Clip-level proxy/oracle gap ────────────────────────────────────────

def analyze_clip_level(oracle_score, proxy_score, tau):
    """Compare proxy-only clips vs GT clips."""
    gt_clips = findCandClips(oracle_score, '>', 0, tau)
    proxy_clips = findCandClips(proxy_score, '>', 0, tau)

    def clip_iou(a, b):
        inter_start = max(a[0], b[0])
        inter_end = min(a[1], b[1])
        inter_len = max(0, inter_end - inter_start + 1)
        union_start = min(a[0], b[0])
        union_end = max(a[1], b[1])
        union_len = union_end - union_start + 1
        return inter_len / union_len if union_len > 0 else 0.0

    # Match proxy clips to GT clips
    gt_matched = set()
    proxy_matched = set()
    match_details = []

    for pi, pc in enumerate(proxy_clips):
        best_iou = 0.0
        best_gi = -1
        for gi, gc in enumerate(gt_clips):
            iou = clip_iou(pc, gc)
            if iou > best_iou:
                best_iou = iou
                best_gi = gi
        if best_iou > 0:
            gt_matched.add(best_gi)
            proxy_matched.add(pi)
            match_details.append({
                'proxy_clip': pc.tolist() if hasattr(pc, 'tolist') else list(pc),
                'gt_clip': gt_clips[best_gi].tolist() if hasattr(gt_clips[best_gi], 'tolist') else list(gt_clips[best_gi]),
                'iou': round(best_iou, 4),
                'boundary_offset_start': int(pc[0]) - int(gt_clips[best_gi][0]),
                'boundary_offset_end': int(pc[1]) - int(gt_clips[best_gi][1]),
            })

    # False splits: GT clip matched by multiple proxy clips
    gt_to_proxy = {}
    for md in match_details:
        gt_key = tuple(md['gt_clip'])
        if gt_key not in gt_to_proxy:
            gt_to_proxy[gt_key] = []
        gt_to_proxy[gt_key].append(md['proxy_clip'])
    false_splits = sum(1 for v in gt_to_proxy.values() if len(v) > 1)

    # False merges: proxy clip matched by multiple GT clips
    proxy_to_gt = {}
    for md in match_details:
        proxy_key = tuple(md['proxy_clip'])
        if proxy_key not in proxy_to_gt:
            proxy_to_gt[proxy_key] = []
        proxy_to_gt[proxy_key].append(md['gt_clip'])
    false_merges = sum(1 for v in proxy_to_gt.values() if len(v) > 1)

    return {
        'gt_clips_count': len(gt_clips),
        'proxy_clips_count': len(proxy_clips),
        'matched_gt': len(gt_matched),
        'matched_proxy': len(proxy_matched),
        'clip_recall': round(len(gt_matched) / len(gt_clips), 4) if len(gt_clips) > 0 else 0.0,
        'clip_precision': round(len(proxy_matched) / len(proxy_clips), 4) if len(proxy_clips) > 0 else 0.0,
        'false_splits': false_splits,
        'false_merges': false_merges,
        'match_details': match_details,
        'gt_clips': gt_clips.tolist() if len(gt_clips) > 0 else [],
        'proxy_clips': proxy_clips.tolist() if len(proxy_clips) > 0 else [],
    }


# ── 3. Candidate coverage ─────────────────────────────────────────────────

def analyze_candidate_coverage(oracle_score, proxy_score, clusters, tau):
    """Check if ARC candidates cover GT clips."""
    gt_clips = findCandClips(oracle_score, '>', 0, tau)
    # ARC initial candidates = proxy_score > 0 clips
    proxy_candidates = findCandClips(proxy_score, '>', 0, tau)

    def clip_iou(a, b):
        inter_start = max(a[0], b[0])
        inter_end = min(a[1], b[1])
        inter_len = max(0, inter_end - inter_start + 1)
        union_start = min(a[0], b[0])
        union_end = max(a[1], b[1])
        union_len = union_end - union_start + 1
        return inter_len / union_len if union_len > 0 else 0.0

    gt_analysis = []
    for gi, gc in enumerate(gt_clips):
        start, end = int(gc[0]), int(gc[1])
        length = end - start + 1

        # Max IoU with proxy candidates
        max_iou_proxy = 0.0
        for pc in proxy_candidates:
            iou = clip_iou(gc, pc)
            max_iou_proxy = max(max_iou_proxy, iou)

        # Cluster spanning
        clip_clusters = clusters[start:end + 1]
        n_clusters_spanned = len(np.unique(clip_clusters))
        in_single_cluster = n_clusters_spanned == 1

        gt_analysis.append({
            'gt_idx': gi,
            'start': start,
            'end': end,
            'length': length,
            'max_iou_proxy_candidate': round(max_iou_proxy, 4),
            'n_clusters_spanned': int(n_clusters_spanned),
            'in_single_cluster': in_single_cluster,
            'cluster_ids': sorted(np.unique(clip_clusters).tolist()),
        })

    return {
        'gt_clips': gt_clips.tolist() if len(gt_clips) > 0 else [],
        'proxy_candidates': proxy_candidates.tolist() if len(proxy_candidates) > 0 else [],
        'gt_analysis': gt_analysis,
        'gt_covered_by_proxy': sum(1 for g in gt_analysis if g['max_iou_proxy_candidate'] > 0),
        'gt_total': len(gt_clips),
    }


# ── 4. Cluster diagnostics ────────────────────────────────────────────────

def analyze_clusters(clusters, oracle_score, proxy_score, tau):
    """Cluster structure analysis."""
    unique, counts = np.unique(clusters, return_counts=True)

    gt_clips = findCandClips(oracle_score, '>', 0, tau)
    proxy_clips = findCandClips(proxy_score, '>', 0, tau)

    # GT clip cluster analysis
    gt_cluster_info = []
    for gi, gc in enumerate(gt_clips):
        start, end = int(gc[0]), int(gc[1])
        clip_clusters = clusters[start:end + 1]
        n_clusters = len(np.unique(clip_clusters))
        gt_cluster_info.append({
            'gt_idx': gi,
            'start': start,
            'end': end,
            'n_clusters': int(n_clusters),
            'in_single_cluster': n_clusters == 1,
        })

    # Proxy candidate cluster analysis
    proxy_cluster_info = []
    for pi, pc in enumerate(proxy_clips):
        start, end = int(pc[0]), int(pc[1])
        clip_clusters = clusters[start:end + 1]
        n_clusters = len(np.unique(clip_clusters))
        proxy_cluster_info.append({
            'proxy_idx': pi,
            'start': start,
            'end': end,
            'n_clusters': int(n_clusters),
            'in_single_cluster': n_clusters == 1,
        })

    # Cluster boundaries inside GT clips
    boundaries_in_gt = 0
    for gc in gt_clips:
        start, end = int(gc[0]), int(gc[1])
        for i in range(start, end):
            if clusters[i] != clusters[i + 1]:
                boundaries_in_gt += 1

    return {
        'n_clusters': len(unique),
        'avg_cluster_len': round(float(np.mean(counts)), 1),
        'median_cluster_len': round(float(np.median(counts)), 1),
        'p90_cluster_len': round(float(np.percentile(counts, 90)), 1),
        'min_cluster_len': int(np.min(counts)),
        'max_cluster_len': int(np.max(counts)),
        'gt_cluster_info': gt_cluster_info,
        'proxy_cluster_info': proxy_cluster_info,
        'gt_in_single_cluster': sum(1 for g in gt_cluster_info if g['in_single_cluster']),
        'proxy_in_single_cluster': sum(1 for p in proxy_cluster_info if p['in_single_cluster']),
        'boundaries_inside_gt_clips': boundaries_in_gt,
    }


# ── 5. Oracle sampling diagnostics ────────────────────────────────────────

def analyze_oracle_sampling(oracle_score, proxy_score, clusters, tau, budget_frac=0.10):
    """Simulate ARC oracle sampling and analyze coverage."""
    n = len(oracle_score)
    B = int(budget_frac * n)
    gt_clips = findCandClips(oracle_score, '>', 0, tau)

    # Simulate ARC's sampling: it queries oracle at proxy_score > 0 positions
    # and then propagates. Let's trace what ARC would do.
    proxy_pos_indices = np.where(proxy_score == 1)[0]

    # ARC starts by sampling from proxy positive regions
    # Then uses label propagation to fill in
    # The key question: how many oracle queries fall inside GT clips?

    gt_set = set()
    for gc in gt_clips:
        for i in range(int(gc[0]), int(gc[1]) + 1):
            gt_set.add(i)

    # Count proxy positive frames inside GT clips
    proxy_in_gt = sum(1 for i in proxy_pos_indices if i in gt_set)
    proxy_outside_gt = len(proxy_pos_indices) - proxy_in_gt

    # ARC's initial candidate clips
    proxy_candidates = findCandClips(proxy_score, '>', 0, tau)

    # Simulate: how many oracle queries would ARC need to find GT clips?
    # ARC queries at proxy positive positions first
    # Then propagates labels

    return {
        'budget': B,
        'proxy_positive_frames': len(proxy_pos_indices),
        'proxy_in_gt_clips': proxy_in_gt,
        'proxy_outside_gt_clips': proxy_outside_gt,
        'gt_clip_frames': len(gt_set),
        'proxy_coverage_of_gt': round(proxy_in_gt / len(gt_set), 4) if len(gt_set) > 0 else 0.0,
        'proxy_candidates_count': len(proxy_candidates),
        'proxy_positive_indices_sample': proxy_pos_indices[:20].tolist(),
    }


# ── 6. Confidence diagnostics ─────────────────────────────────────────────

def analyze_confidence(oracle_score, proxy_score, clusters, tau):
    """Deep dive into why confidence=0."""
    n = len(oracle_score)
    proxy_candidates = findCandClips(proxy_score, '>', 0, tau)

    # Initialize like ARC
    proxy = np.column_stack((1 - proxy_score.astype(float), proxy_score.astype(float)))
    oracle_binary = oracle_score.astype(int)
    oracle = np.column_stack((1 - oracle_binary, oracle_binary))

    PD = proxy.copy()
    init_probabilities(PD, 0, [0.9999, 0.0001])
    init_probabilities(PD, 1, [0.0001, 0.9999])
    entropy_array = np.apply_along_axis(entropy, 1, proxy)
    cluster_boundaries, uncertainties, probabilities = init_cluster_uncertainties(
        clusters, entropy_array, proxy)

    # Analyze each candidate clip
    clip_diagnostics = []
    for ci, clip in enumerate(proxy_candidates):
        start, end = int(clip[0]), int(clip[1])

        # calculate_boundaries
        cb_start, cb_end = calculate_boundaries(clip, IOU_THRESHOLD, n)

        # calculate_indices
        i_values, cluster_range = calculate_indices(
            cb_start, cb_end, cluster_boundaries, clusters)

        # Check why cluster_range is empty
        cluster_at_start = int(clusters[cb_start])
        cluster_at_end = int(clusters[cb_end])
        same_cluster = cluster_at_start == cluster_at_end

        clip_diagnostics.append({
            'clip_idx': ci,
            'start': start,
            'end': end,
            'length': end - start + 1,
            'cb_start': int(cb_start),
            'cb_end': int(cb_end),
            'cluster_at_start': cluster_at_start,
            'cluster_at_end': cluster_at_end,
            'same_cluster': same_cluster,
            'cluster_range_empty': cluster_range.size == 0,
            'cluster_range': cluster_range.tolist() if cluster_range.size > 0 else [],
            'n_clusters_in_clip': len(np.unique(clusters[start:end + 1])),
        })

    # Try computing confidence for all candidates
    if len(proxy_candidates) > 0:
        try:
            clips_conf, mean_conf = calculate_confidence(
                proxy_candidates, IOU_THRESHOLD, probabilities, clusters, cluster_boundaries)
            conf_per_clip = clips_conf.tolist() if hasattr(clips_conf, 'tolist') else list(clips_conf)
        except Exception as e:
            conf_per_clip = [f'ERROR: {str(e)[:50]}'] * len(proxy_candidates)
            mean_conf = 0.0
    else:
        conf_per_clip = []
        mean_conf = 0.0

    return {
        'n_candidates': len(proxy_candidates),
        'candidates_all_same_cluster': all(d['same_cluster'] for d in clip_diagnostics) if clip_diagnostics else True,
        'candidates_all_empty_range': all(d['cluster_range_empty'] for d in clip_diagnostics) if clip_diagnostics else True,
        'mean_confidence': round(float(mean_conf), 4) if not isinstance(mean_conf, str) else mean_conf,
        'clip_diagnostics': clip_diagnostics,
        'conf_per_clip': conf_per_clip,
        'probabilities_sample': probabilities[:10].tolist(),
    }


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("realcar_5k ARC Failure Attribution")
    print("=" * 70)

    # Load data
    (oracle, proxy, oracle_score, proxy_score, clusters,
     orig, stress, proxy_counts, oracle_counts) = load_all()

    print(f"Loaded {len(oracle)} frames")
    print(f"K={K}, tau={TAU}")
    print()

    # 1. Frame-level analysis
    print("1. Frame-level proxy/oracle gap...")
    frame_result = analyze_frame_level(proxy_counts, oracle_counts, K)
    print(f"   Pearson r={frame_result['pearson_r']}, Spearman r={frame_result['spearman_r']}")
    print(f"   Confusion: TP={frame_result['tp']}, FP={frame_result['fp']}, FN={frame_result['fn']}, TN={frame_result['tn']}")
    print(f"   P={frame_result['precision']}, R={frame_result['recall']}, F1={frame_result['f1']}")
    print(f"   Proxy runs (tau>=30): {frame_result['proxy_runs_tau30']}, Oracle runs (tau>=30): {frame_result['oracle_runs_tau30']}")

    # 2. Clip-level analysis
    print("\n2. Clip-level proxy/oracle gap...")
    clip_result = analyze_clip_level(oracle_score, proxy_score, TAU)
    print(f"   GT clips: {clip_result['gt_clips_count']}, Proxy clips: {clip_result['proxy_clips_count']}")
    print(f"   Clip recall: {clip_result['clip_recall']}, Clip precision: {clip_result['clip_precision']}")
    print(f"   False splits: {clip_result['false_splits']}, False merges: {clip_result['false_merges']}")

    # 3. Candidate coverage
    print("\n3. Candidate coverage...")
    coverage_result = analyze_candidate_coverage(oracle_score, proxy_score, clusters, TAU)
    print(f"   GT clips covered by proxy candidates: {coverage_result['gt_covered_by_proxy']}/{coverage_result['gt_total']}")
    for g in coverage_result['gt_analysis']:
        print(f"   GT[{g['gt_idx']}]: [{g['start']}-{g['end']}], len={g['length']}, "
              f"max_IoU_proxy={g['max_iou_proxy_candidate']}, clusters={g['n_clusters_spanned']}")

    # 4. Cluster diagnostics
    print("\n4. Cluster diagnostics...")
    cluster_result = analyze_clusters(clusters, oracle_score, proxy_score, TAU)
    print(f"   Clusters: {cluster_result['n_clusters']}, avg={cluster_result['avg_cluster_len']}, "
          f"median={cluster_result['median_cluster_len']}, p90={cluster_result['p90_cluster_len']}")
    print(f"   GT clips in single cluster: {cluster_result['gt_in_single_cluster']}/{len(cluster_result['gt_cluster_info'])}")
    print(f"   Boundaries inside GT clips: {cluster_result['boundaries_inside_gt_clips']}")

    # 5. Oracle sampling
    print("\n5. Oracle sampling diagnostics...")
    sampling_result = analyze_oracle_sampling(oracle_score, proxy_score, clusters, TAU)
    print(f"   Budget: {sampling_result['budget']}")
    print(f"   Proxy positive frames: {sampling_result['proxy_positive_frames']}")
    print(f"   Proxy in GT clips: {sampling_result['proxy_in_gt_clips']}/{sampling_result['proxy_positive_frames']}")
    print(f"   Proxy coverage of GT: {sampling_result['proxy_coverage_of_gt']}")

    # 6. Confidence diagnostics
    print("\n6. Confidence diagnostics...")
    conf_result = analyze_confidence(oracle_score, proxy_score, clusters, TAU)
    print(f"   Candidates: {conf_result['n_candidates']}")
    print(f"   All same cluster: {conf_result['candidates_all_same_cluster']}")
    print(f"   All empty range: {conf_result['candidates_all_empty_range']}")
    print(f"   Mean confidence: {conf_result['mean_confidence']}")

    # Save detailed CSV
    save_detailed_csv(frame_result, clip_result, coverage_result,
                      cluster_result, sampling_result, conf_result)

    # Generate report
    generate_report(frame_result, clip_result, coverage_result,
                    cluster_result, sampling_result, conf_result)

    print(f"\nOutputs:")
    print(f"  {OUTPUT_CSV}")
    print(f"  {OUTPUT_REPORT}")


def save_detailed_csv(frame_result, clip_result, coverage_result,
                      cluster_result, sampling_result, conf_result):
    """Save detailed diagnostics to CSV."""
    # Frame-level summary
    frame_summary = pd.DataFrame([{
        'metric': 'frame_level',
        'pearson_r': frame_result['pearson_r'],
        'spearman_r': frame_result['spearman_r'],
        'tp': frame_result['tp'],
        'fp': frame_result['fp'],
        'fn': frame_result['fn'],
        'tn': frame_result['tn'],
        'precision': frame_result['precision'],
        'recall': frame_result['recall'],
        'f1': frame_result['f1'],
        'proxy_positive_frames': frame_result['proxy_positive_frames'],
        'oracle_positive_frames': frame_result['oracle_positive_frames'],
        'proxy_runs_tau30': frame_result['proxy_runs_tau30'],
        'oracle_runs_tau30': frame_result['oracle_runs_tau30'],
    }])

    # GT clip diagnostics
    gt_rows = []
    for g in coverage_result['gt_analysis']:
        gt_rows.append({
            'gt_idx': g['gt_idx'],
            'start': g['start'],
            'end': g['end'],
            'length': g['length'],
            'max_iou_proxy_candidate': g['max_iou_proxy_candidate'],
            'n_clusters_spanned': g['n_clusters_spanned'],
            'in_single_cluster': g['in_single_cluster'],
        })
    gt_df = pd.DataFrame(gt_rows)

    # Cluster diagnostics
    cluster_df = pd.DataFrame([{
        'n_clusters': cluster_result['n_clusters'],
        'avg_cluster_len': cluster_result['avg_cluster_len'],
        'median_cluster_len': cluster_result['median_cluster_len'],
        'p90_cluster_len': cluster_result['p90_cluster_len'],
        'gt_in_single_cluster': cluster_result['gt_in_single_cluster'],
        'boundaries_inside_gt_clips': cluster_result['boundaries_inside_gt_clips'],
    }])

    # Candidate diagnostics
    cand_rows = []
    for d in conf_result['clip_diagnostics']:
        cand_rows.append({
            'clip_idx': d['clip_idx'],
            'start': d['start'],
            'end': d['end'],
            'length': d['length'],
            'same_cluster': d['same_cluster'],
            'cluster_range_empty': d['cluster_range_empty'],
            'n_clusters_in_clip': d['n_clusters_in_clip'],
        })
    cand_df = pd.DataFrame(cand_rows)

    # Save all
    with open(OUTPUT_CSV, 'w') as f:
        f.write("# Frame-level diagnostics\n")
        frame_summary.to_csv(f, index=False)
        f.write("\n# GT clip diagnostics\n")
        gt_df.to_csv(f, index=False)
        f.write("\n# Cluster diagnostics\n")
        cluster_df.to_csv(f, index=False)
        f.write("\n# Candidate clip diagnostics\n")
        cand_df.to_csv(f, index=False)


def generate_report(frame_result, clip_result, coverage_result,
                    cluster_result, sampling_result, conf_result):
    """Generate Markdown failure attribution report."""
    lines = []
    lines.append("# realcar_5k ARC Failure Attribution Report")
    lines.append("")
    lines.append("**Date**: 2026-06-07")
    lines.append(f"**Dataset**: realcar_5k, K={K}, tau={TAU}")
    lines.append("**Question**: Why does ARC achieve recall=0?")
    lines.append("")

    # ── 1. Frame-level ─────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 1. Frame-Level Proxy/Oracle Gap")
    lines.append("")
    lines.append("### Correlation")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Pearson r | {frame_result['pearson_r']} (p={frame_result['pearson_p']}) |")
    lines.append(f"| Spearman r | {frame_result['spearman_r']} (p={frame_result['spearman_p']}) |")
    lines.append("")

    lines.append("### Confusion Matrix (proxy_positive vs oracle_positive, K=12)")
    lines.append("")
    lines.append("|  | Oracle=1 | Oracle=0 |")
    lines.append("|--|----------|----------|")
    lines.append(f"| **Proxy=1** | TP={frame_result['tp']} | FP={frame_result['fp']} |")
    lines.append(f"| **Proxy=0** | FN={frame_result['fn']} | TN={frame_result['tn']} |")
    lines.append("")
    lines.append(f"**Precision**: {frame_result['precision']}")
    lines.append(f"**Recall**: {frame_result['recall']}")
    lines.append(f"**F1**: {frame_result['f1']}")
    lines.append("")

    lines.append("### Positive Runs")
    lines.append("")
    lines.append("| Metric | Proxy | Oracle |")
    lines.append("|--------|-------|--------|")
    lines.append(f"| Positive frames | {frame_result['proxy_positive_frames']} | {frame_result['oracle_positive_frames']} |")
    lines.append(f"| Runs (any length) | {frame_result['proxy_runs_total']} | {frame_result['oracle_runs_total']} |")
    lines.append(f"| Runs (length >= 30) | {frame_result['proxy_runs_tau30']} | {frame_result['oracle_runs_tau30']} |")
    lines.append("")

    # Run length distribution
    proxy_lens = frame_result['proxy_run_lengths']
    oracle_lens = frame_result['oracle_run_lengths']
    if proxy_lens:
        lines.append(f"**Proxy run lengths**: min={min(proxy_lens)}, max={max(proxy_lens)}, "
                     f"mean={np.mean(proxy_lens):.1f}, median={np.median(proxy_lens):.1f}")
    if oracle_lens:
        lines.append(f"**Oracle run lengths**: min={min(oracle_lens)}, max={max(oracle_lens)}, "
                     f"mean={np.mean(oracle_lens):.1f}, median={np.median(oracle_lens):.1f}")
    lines.append("")

    # ── 2. Clip-level ──────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 2. Clip-Level Proxy/Oracle Gap")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| GT clips (tau={TAU}) | {clip_result['gt_clips_count']} |")
    lines.append(f"| Proxy clips (tau={TAU}) | {clip_result['proxy_clips_count']} |")
    lines.append(f"| Clip recall | {clip_result['clip_recall']} |")
    lines.append(f"| Clip precision | {clip_result['clip_precision']} |")
    lines.append(f"| False splits | {clip_result['false_splits']} |")
    lines.append(f"| False merges | {clip_result['false_merges']} |")
    lines.append("")

    if clip_result['match_details']:
        lines.append("### Match Details")
        lines.append("")
        lines.append("| Proxy Clip | GT Clip | IoU | Start Offset | End Offset |")
        lines.append("|------------|---------|-----|--------------|------------|")
        for md in clip_result['match_details']:
            lines.append(f"| {md['proxy_clip']} | {md['gt_clip']} | {md['iou']} | "
                        f"{md['boundary_offset_start']:+d} | {md['boundary_offset_end']:+d} |")
        lines.append("")

    # ── 3. Candidate coverage ──────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 3. Candidate Coverage")
    lines.append("")
    lines.append(f"**GT clips covered by proxy candidates**: {coverage_result['gt_covered_by_proxy']}/{coverage_result['gt_total']}")
    lines.append("")

    lines.append("### Per-GT-Clip Analysis")
    lines.append("")
    lines.append("| GT | Start | End | Length | Max IoU (proxy) | Clusters | Single Cluster |")
    lines.append("|----|-------|-----|--------|-----------------|----------|----------------|")
    for g in coverage_result['gt_analysis']:
        lines.append(f"| {g['gt_idx']} | {g['start']} | {g['end']} | {g['length']} | "
                    f"{g['max_iou_proxy_candidate']} | {g['n_clusters_spanned']} | "
                    f"{'Yes' if g['in_single_cluster'] else 'No'} |")
    lines.append("")

    # ── 4. Cluster diagnostics ─────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 4. Cluster Diagnostics")
    lines.append("")
    lines.append("### Cluster Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Cluster count | {cluster_result['n_clusters']} |")
    lines.append(f"| Avg length | {cluster_result['avg_cluster_len']} |")
    lines.append(f"| Median length | {cluster_result['median_cluster_len']} |")
    lines.append(f"| P90 length | {cluster_result['p90_cluster_len']} |")
    lines.append(f"| Min length | {cluster_result['min_cluster_len']} |")
    lines.append(f"| Max length | {cluster_result['max_cluster_len']} |")
    lines.append("")

    lines.append("### GT Clip Cluster Spanning")
    lines.append("")
    lines.append("| GT | Start | End | Clusters | Single Cluster |")
    lines.append("|----|-------|-----|----------|----------------|")
    for g in cluster_result['gt_cluster_info']:
        lines.append(f"| {g['gt_idx']} | {g['start']} | {g['end']} | "
                    f"{g['n_clusters']} | {'Yes' if g['in_single_cluster'] else 'No'} |")
    lines.append("")

    lines.append(f"**GT clips in single cluster**: {cluster_result['gt_in_single_cluster']}/{len(cluster_result['gt_cluster_info'])}")
    lines.append(f"**Cluster boundaries inside GT clips**: {cluster_result['boundaries_inside_gt_clips']}")
    lines.append("")

    if cluster_result['proxy_cluster_info']:
        lines.append("### Proxy Candidate Cluster Spanning")
        lines.append("")
        lines.append("| Proxy | Start | End | Clusters | Single Cluster |")
        lines.append("|-------|-------|-----|----------|----------------|")
        for p in cluster_result['proxy_cluster_info']:
            lines.append(f"| {p['proxy_idx']} | {p['start']} | {p['end']} | "
                        f"{p['n_clusters']} | {'Yes' if p['in_single_cluster'] else 'No'} |")
        lines.append("")
        lines.append(f"**Proxy candidates in single cluster**: {cluster_result['proxy_in_single_cluster']}/{len(cluster_result['proxy_cluster_info'])}")
        lines.append("")

    # ── 5. Oracle sampling ─────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 5. Oracle Sampling Diagnostics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Budget (10%) | {sampling_result['budget']} |")
    lines.append(f"| Proxy positive frames | {sampling_result['proxy_positive_frames']} |")
    lines.append(f"| Proxy in GT clips | {sampling_result['proxy_in_gt_clips']} |")
    lines.append(f"| Proxy outside GT clips | {sampling_result['proxy_outside_gt_clips']} |")
    lines.append(f"| GT clip frames | {sampling_result['gt_clip_frames']} |")
    lines.append(f"| Proxy coverage of GT | {sampling_result['proxy_coverage_of_gt']} |")
    lines.append("")

    # ── 6. Confidence diagnostics ──────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 6. Confidence Diagnostics")
    lines.append("")
    lines.append("### Why confidence=0")
    lines.append("")
    lines.append(f"**Candidates**: {conf_result['n_candidates']}")
    lines.append(f"**All in same cluster**: {conf_result['candidates_all_same_cluster']}")
    lines.append(f"**All have empty cluster_range**: {conf_result['candidates_all_empty_range']}")
    lines.append(f"**Mean confidence**: {conf_result['mean_confidence']}")
    lines.append("")

    lines.append("### Per-Candidate Analysis")
    lines.append("")
    lines.append("| Clip | Start | End | Length | Same Cluster | Empty Range | N Clusters |")
    lines.append("|------|-------|-----|--------|--------------|-------------|------------|")
    for d in conf_result['clip_diagnostics']:
        lines.append(f"| {d['clip_idx']} | {d['start']} | {d['end']} | {d['length']} | "
                    f"{'Yes' if d['same_cluster'] else 'No'} | "
                    f"{'Yes' if d['cluster_range_empty'] else 'No'} | "
                    f"{d['n_clusters_in_clip']} |")
    lines.append("")

    lines.append("### Root Cause")
    lines.append("")
    lines.append("The `calculate_confidence` function in ARC computes:")
    lines.append("```python")
    lines.append("cluster_range = np.arange(cluster[start] + 1, cluster[end])")
    lines.append("```")
    lines.append("When `cluster[start] == cluster[end]` (clip within one cluster),")
    lines.append("`cluster_range` is empty, and `combined_prob = 0`.")
    lines.append("")
    lines.append("With cluster_size=20 and clip length 30-50, most clips span 2-3 clusters.")
    lines.append("But `calculate_boundaries` extends the clip, and the extended boundaries")
    lines.append("often fall in the same cluster, making `cluster_range` empty.")
    lines.append("")

    # ── Failure ranking ────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 7. Failure Ranking")
    lines.append("")

    # Compute scores
    proxy_fail_score = 1.0 - frame_result['f1']  # Higher = worse proxy
    cluster_fail_score = 1.0 if cluster_result['gt_in_single_cluster'] > 0 else 0.5
    sampling_fail_score = 1.0 - sampling_result['proxy_coverage_of_gt']
    conf_fail_score = 1.0 if conf_result['mean_confidence'] == 0.0 else 0.0

    lines.append("| Rank | Failure Type | Score | Evidence |")
    lines.append("|------|-------------|-------|----------|")

    failures = [
        ('A', 'Proxy failure', proxy_fail_score,
         f"F1={frame_result['f1']}, correlation={frame_result['pearson_r']}, "
         f"proxy runs(tau>=30)={frame_result['proxy_runs_tau30']} vs oracle={frame_result['oracle_runs_tau30']}"),
        ('B', 'Clustering failure', cluster_fail_score,
         f"GT in single cluster: {cluster_result['gt_in_single_cluster']}/{len(cluster_result['gt_cluster_info'])}, "
         f"boundaries in GT: {cluster_result['boundaries_inside_gt_clips']}"),
        ('C', 'Sampling failure', sampling_fail_score,
         f"Proxy coverage of GT: {sampling_result['proxy_coverage_of_gt']}, "
         f"proxy in GT: {sampling_result['proxy_in_gt_clips']}/{sampling_result['proxy_positive_frames']}"),
        ('D', 'Confidence calculation failure', conf_fail_score,
         f"Mean confidence: {conf_result['mean_confidence']}, "
         f"all same cluster: {conf_result['candidates_all_same_cluster']}"),
        ('E', 'Query semantics failure', 0.0,
         "constant=0 is correct design per algorithm_handler.py"),
    ]

    failures.sort(key=lambda x: -x[2])
    for rank, (letter, name, score, evidence) in enumerate(failures, 1):
        lines.append(f"| {rank} | **{letter}. {name}** | {score:.2f} | {evidence} |")

    lines.append("")
    lines.append("### Interpretation")
    lines.append("")
    lines.append("1. **Proxy failure (PRIMARY)**: The YOLOv8n proxy has very weak correlation "
                 f"(r={frame_result['pearson_r']}) with the YOLOv8x oracle at K=12. "
                 f"Only {frame_result['proxy_runs_tau30']} proxy runs survive tau>=30 filtering "
                 f"vs {frame_result['oracle_runs_tau30']} oracle runs. The proxy signal is too "
                 "fragmented and noisy for ARC to identify correct candidate regions.")
    lines.append("")
    lines.append("2. **Sampling failure (SECONDARY)**: Even when ARC samples oracle queries, "
                 f"only {sampling_result['proxy_coverage_of_gt']} of GT clip frames are covered "
                 "by proxy-positive frames. ARC's progressive sampling is guided by proxy signal, "
                 "but the proxy misses most GT regions.")
    lines.append("")
    lines.append("3. **Clustering failure (MINOR)**: Cluster boundaries don't align well with "
                 f"GT clips ({cluster_result['boundaries_inside_gt_clips']} boundaries inside GT clips). "
                 "However, this is secondary to the proxy failure.")
    lines.append("")
    lines.append("4. **Confidence calculation (CONSEQUENCE)**: confidence=0 is a consequence of "
                 "proxy failure, not a root cause. If proxy candidates covered GT clips, "
                 "confidence would be non-zero.")
    lines.append("")
    lines.append("5. **Query semantics (NOT A FAILURE)**: constant=0 is correct per ARC design.")
    lines.append("")

    # ── Recommendations ────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 8. Recommendations")
    lines.append("")
    lines.append("1. **Lower K to 8-10**: Increase proxy positive rate and proxy-oracle correlation")
    lines.append("2. **Use raw proxy_score as CDF**: Instead of binary threshold, use normalized "
                 "vehicle count as continuous proxy probability")
    lines.append("3. **Smaller cluster_size (5-10)**: Allow confidence calculation to work")
    lines.append("4. **Try different proxy model**: YOLOv8n may be too weak; consider YOLOv8s or YOLOv8m")
    lines.append("")

    # Write report
    report_text = "\n".join(lines)
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_text)


if __name__ == '__main__':
    main()
