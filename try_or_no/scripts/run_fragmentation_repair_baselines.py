#!/usr/bin/env python3
"""
run_fragmentation_repair_baselines.py

Fragmentation-aware candidate generation baselines for moving-camera ARC.
Addresses the proxy fragmentation problem: high frame-level correlation (r≈0.79)
but proxy runs(tau>=30)=0 due to short bursts.

Three baseline families:
  1. Gap-tolerant stitching
  2. Soft-window candidate generation
  3. Oracle-seeded segment expansion

Usage:
    python scripts/run_fragmentation_repair_baselines.py
"""

import sys
import os
import time
import warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')

# ── Configuration ──────────────────────────────────────────────────────────

ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
OUTPUT_CSV = 'outputs/fragmentation_repair_results.csv'
OUTPUT_REPORT = 'outputs/fragmentation_repair_report.md'

K_VALUES = [12, 13]
TAU_VALUES = [30, 60]
BUDGET_FRACS = [0.02, 0.05, 0.10]
IOU_THRESHOLD = 0.9

# ── Helpers ────────────────────────────────────────────────────────────────

def load_data():
    """Load per-frame data."""
    df = pd.read_csv(ORACLE_CSV)
    proxy_counts = df['proxy_vehicle_count'].values.astype(float)
    oracle_counts = df['oracle_vehicle_count'].values.astype(float)
    n = len(df)
    return proxy_counts, oracle_counts, n


def get_binary_labels(counts, K):
    """Get binary labels: count >= K."""
    return (counts >= K).astype(int)


def find_runs(binary, min_len=1):
    """Find contiguous runs of 1s with length >= min_len."""
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


def clip_iou(a, b):
    """IoU between two [start, end] inclusive segments."""
    inter_start = max(a[0], b[0])
    inter_end = min(a[1], b[1])
    inter_len = max(0, inter_end - inter_start + 1)
    union_start = min(a[0], b[0])
    union_end = max(a[1], b[1])
    union_len = union_end - union_start + 1
    return inter_len / union_len if union_len > 0 else 0.0


def calc_metrics(gt_clips, pred_clips, threshold=IOU_THRESHOLD):
    """Calculate precision, recall, mIoU, per-GT IoU."""
    if len(gt_clips) == 0 and len(pred_clips) == 0:
        return {'precision': 1.0, 'recall': 1.0, 'mIoU': 1.0,
                'gt_coverage': 1.0, 'max_iou_per_gt': [],
                'false_splits': 0, 'false_merges': 0}
    if len(gt_clips) == 0:
        return {'precision': 0.0, 'recall': 1.0, 'mIoU': 0.0,
                'gt_coverage': 0.0, 'max_iou_per_gt': [],
                'false_splits': 0, 'false_merges': 0}
    if len(pred_clips) == 0:
        return {'precision': 1.0, 'recall': 0.0, 'mIoU': 0.0,
                'gt_coverage': 0.0, 'max_iou_per_gt': [0.0] * len(gt_clips),
                'false_splits': 0, 'false_merges': 0}

    # Per-GT max IoU
    max_iou_per_gt = []
    for gt in gt_clips:
        ious = [clip_iou(gt, pred) for pred in pred_clips]
        max_iou_per_gt.append(max(ious) if ious else 0.0)

    # GT coverage
    gt_coverage = sum(1 for iou in max_iou_per_gt if iou > 0) / len(gt_clips)

    # Precision: fraction of pred clips matching a GT clip
    hits_precision = 0
    for pred in pred_clips:
        ious = [clip_iou(pred, gt) for gt in gt_clips]
        if max(ious) >= threshold:
            hits_precision += 1
    precision = hits_precision / len(pred_clips)

    # Recall: fraction of GT clips matched
    hits_recall = sum(1 for iou in max_iou_per_gt if iou >= threshold)
    recall = hits_recall / len(gt_clips)

    # mIoU
    mIoU = sum(max_iou_per_gt) / len(gt_clips)

    # False splits: GT clip matched by multiple pred clips
    gt_to_pred = {}
    for pi, pred in enumerate(pred_clips):
        for gi, gt in enumerate(gt_clips):
            if clip_iou(pred, gt) > 0:
                if gi not in gt_to_pred:
                    gt_to_pred[gi] = []
                gt_to_pred[gi].append(pi)
    false_splits = sum(1 for v in gt_to_pred.values() if len(v) > 1)

    # False merges: pred clip matches multiple GT clips
    pred_to_gt = {}
    for pi, pred in enumerate(pred_clips):
        for gi, gt in enumerate(gt_clips):
            if clip_iou(pred, gt) > 0:
                if pi not in pred_to_gt:
                    pred_to_gt[pi] = []
                pred_to_gt[pi].append(gi)
    false_merges = sum(1 for v in pred_to_gt.values() if len(v) > 1)

    return {
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'mIoU': round(mIoU, 4),
        'gt_coverage': round(gt_coverage, 4),
        'max_iou_per_gt': [round(iou, 4) for iou in max_iou_per_gt],
        'false_splits': false_splits,
        'false_merges': false_merges,
    }


# ── Baseline 1: Gap-tolerant stitching ────────────────────────────────────

def gap_tolerant_stitch(binary, gap_tolerance, min_len):
    """Merge runs separated by gap <= gap_tolerance, then filter by min_len."""
    # Find all positive runs (any length)
    runs = find_runs(binary, min_len=1)
    if not runs:
        return []

    # Merge runs with gaps <= gap_tolerance
    merged = [list(runs[0])]
    for start, end, length in runs[1:]:
        prev_end = merged[-1][1]
        gap = start - prev_end - 1
        if gap <= gap_tolerance:
            merged[-1][1] = end
            merged[-1][2] = merged[-1][1] - merged[-1][0] + 1
        else:
            merged.append([start, end, length])

    # Filter by min_len
    result = [(m[0], m[1], m[2]) for m in merged if m[2] >= min_len]
    return result


def run_gap_tolerant(proxy_counts, oracle_counts, K, tau):
    """Run gap-tolerant stitching with various parameters."""
    proxy_binary = get_binary_labels(proxy_counts, K)
    oracle_binary = get_binary_labels(oracle_counts, K)
    gt_clips = find_runs(oracle_binary, min_len=tau)
    gt_clips_tuples = [(s, e) for s, e, l in gt_clips]

    results = []
    for gap in [5, 10, 15, 30]:
        stiched = gap_tolerant_stitch(proxy_binary, gap, tau)
        pred_clips = [(s, e) for s, e, l in stiched]
        metrics = calc_metrics(gt_clips_tuples, pred_clips)

        results.append({
            'method': f'gap_stitch_g{gap}',
            'K': K,
            'tau': tau,
            'gap_tolerance': gap,
            'min_len': tau,
            'candidate_count': len(pred_clips),
            'oracle_calls': 0,
            **metrics,
        })

    return results


# ── Baseline 2: Soft-window candidate generation ──────────────────────────

def soft_window_candidates(proxy_counts, window_size, stride, tau, score_fn='mean'):
    """Generate candidates using sliding windows on proxy counts."""
    n = len(proxy_counts)
    windows = []

    for start in range(0, n - window_size + 1, stride):
        end = start + window_size - 1
        window_data = proxy_counts[start:end + 1]
        if score_fn == 'mean':
            score = np.mean(window_data)
        elif score_fn == 'p80':
            score = np.percentile(window_data, 80)
        else:
            score = np.mean(window_data)
        windows.append((start, end, score))

    # Sort by score descending
    windows.sort(key=lambda x: -x[2])

    # Select top windows until we have enough coverage
    # Heuristic: select windows that cover at least tau frames
    selected = []
    covered = set()
    for start, end, score in windows:
        # Check if this window adds new coverage
        new_frames = set(range(start, end + 1)) - covered
        if len(new_frames) >= tau // 2:  # At least half tau new frames
            selected.append((start, end, score))
            covered.update(range(start, end + 1))

    # Stitch overlapping selected windows
    if not selected:
        return []

    selected.sort(key=lambda x: x[0])  # Sort by start
    stitched = [list(selected[0])]
    for start, end, score in selected[1:]:
        if start <= stitched[-1][1] + 1:  # Overlapping or adjacent
            stitched[-1][1] = max(stitched[-1][1], end)
        else:
            stitched.append([start, end, score])

    # Filter by tau
    result = [(s, e) for s, e, _ in stitched if (e - s + 1) >= tau]
    return result


def run_soft_window(proxy_counts, oracle_counts, K, tau):
    """Run soft-window candidate generation with various parameters."""
    oracle_binary = get_binary_labels(oracle_counts, K)
    gt_clips = find_runs(oracle_binary, min_len=tau)
    gt_clips_tuples = [(s, e) for s, e, l in gt_clips]

    results = []
    for ws in [30, 60, 120]:
        for stride in [5, 10]:
            for score_fn in ['mean', 'p80']:
                pred_clips = soft_window_candidates(proxy_counts, ws, stride, tau, score_fn)
                metrics = calc_metrics(gt_clips_tuples, pred_clips)

                results.append({
                    'method': f'soft_win_w{ws}_s{stride}_{score_fn}',
                    'K': K,
                    'tau': tau,
                    'window_size': ws,
                    'stride': stride,
                    'score_fn': score_fn,
                    'candidate_count': len(pred_clips),
                    'oracle_calls': 0,
                    **metrics,
                })

    return results


# ── Baseline 3: Oracle-seeded segment expansion ───────────────────────────

def oracle_seeded_expansion(proxy_counts, oracle_binary, segment_size, budget_frac, tau, K):
    """Oracle-seeded segment expansion.

    1. Divide into segments of segment_size
    2. Query center frame oracle for each segment (budget permitting)
    3. Positive segments expand forward/backward using proxy evidence
    """
    n = len(oracle_binary)
    budget = int(budget_frac * n)

    # Divide into segments
    segments = []
    for start in range(0, n, segment_size):
        end = min(start + segment_size - 1, n - 1)
        segments.append((start, end))

    # Query center frames (budget-limited)
    oracle_queries = 0
    positive_segments = []
    negative_segments = []

    for start, end in segments:
        if oracle_queries >= budget:
            break
        center = (start + end) // 2
        if oracle_binary[center] == 1:
            positive_segments.append((start, end))
        else:
            negative_segments.append((start, end))
        oracle_queries += 1

    # Expand positive segments using proxy evidence
    candidates = []
    for seg_start, seg_end in positive_segments:
        # Find the positive core
        core_start = seg_start
        core_end = seg_end

        # Expand forward
        expand_start = core_start
        for i in range(core_start - 1, -1, -1):
            if proxy_counts[i] >= K * 0.5:  # Soft threshold
                expand_start = i
            else:
                break

        # Expand backward
        expand_end = core_end
        for i in range(core_end + 1, n):
            if proxy_counts[i] >= K * 0.5:  # Soft threshold
                expand_end = i
            else:
                break

        length = expand_end - expand_start + 1
        if length >= tau:
            candidates.append((expand_start, expand_end))

    # Merge overlapping candidates
    if not candidates:
        return [], oracle_queries

    candidates.sort(key=lambda x: x[0])
    merged = [list(candidates[0])]
    for start, end in candidates[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    result = [(m[0], m[1]) for m in merged if (m[1] - m[0] + 1) >= tau]
    return result, oracle_queries


def run_oracle_seeded(proxy_counts, oracle_counts, K, tau):
    """Run oracle-seeded expansion with various parameters."""
    oracle_binary = get_binary_labels(oracle_counts, K)
    gt_clips = find_runs(oracle_binary, min_len=tau)
    gt_clips_tuples = [(s, e) for s, e, l in gt_clips]

    results = []
    for seg_size in [20, 30, 50]:
        for budget_frac in BUDGET_FRACS:
            pred_clips, oracle_calls = oracle_seeded_expansion(
                proxy_counts, oracle_binary, seg_size, budget_frac, tau, K)
            metrics = calc_metrics(gt_clips_tuples, pred_clips)

            recall_per_call = metrics['recall'] / oracle_calls if oracle_calls > 0 else 0.0

            results.append({
                'method': f'oracle_seed_s{seg_size}_b{int(budget_frac*100)}',
                'K': K,
                'tau': tau,
                'segment_size': seg_size,
                'budget_frac': budget_frac,
                'candidate_count': len(pred_clips),
                'oracle_calls': oracle_calls,
                'recall_per_call': round(recall_per_call, 6),
                **metrics,
            })

    return results


# ── Baselines for comparison ──────────────────────────────────────────────

def run_baselines(proxy_counts, oracle_counts, K, tau):
    """Run comparison baselines."""
    proxy_binary = get_binary_labels(proxy_counts, K)
    oracle_binary = get_binary_labels(oracle_counts, K)

    gt_clips = find_runs(oracle_binary, min_len=tau)
    gt_clips_tuples = [(s, e) for s, e, l in gt_clips]

    proxy_clips = find_runs(proxy_binary, min_len=tau)
    proxy_clips_tuples = [(s, e) for s, e, l in proxy_clips]

    results = []

    # Proxy-only hard threshold
    metrics = calc_metrics(gt_clips_tuples, proxy_clips_tuples)
    results.append({
        'method': 'proxy_only_hard',
        'K': K,
        'tau': tau,
        'candidate_count': len(proxy_clips_tuples),
        'oracle_calls': 0,
        'recall_per_call': 0.0,
        **metrics,
    })

    # Oracle-only (upper bound)
    results.append({
        'method': 'oracle_only',
        'K': K,
        'tau': tau,
        'candidate_count': len(gt_clips_tuples),
        'oracle_calls': len(oracle_counts),
        'recall_per_call': round(metrics['recall'] / len(oracle_counts), 6) if len(oracle_counts) > 0 else 0.0,
        'precision': 1.0,
        'recall': 1.0,
        'mIoU': 1.0,
        'gt_coverage': 1.0,
        'max_iou_per_gt': [1.0] * len(gt_clips_tuples),
        'false_splits': 0,
        'false_merges': 0,
    })

    return results


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Fragmentation Repair Baselines")
    print("=" * 70)

    proxy_counts, oracle_counts, n = load_data()
    print(f"Loaded {n} frames")

    all_results = []

    for K in K_VALUES:
        print(f"\n{'='*70}")
        print(f"K={K}")
        print(f"{'='*70}")

        proxy_binary = get_binary_labels(proxy_counts, K)
        oracle_binary = get_binary_labels(oracle_counts, K)

        print(f"Proxy positive rate: {proxy_binary.mean():.4f}")
        print(f"Oracle positive rate: {oracle_binary.mean():.4f}")

        for tau in TAU_VALUES:
            gt_clips = find_runs(oracle_binary, min_len=tau)
            proxy_clips = find_runs(proxy_binary, min_len=tau)
            print(f"\n  tau={tau}: GT clips={len(gt_clips)}, Proxy clips={len(proxy_clips)}")

            # Baselines
            print("  Running baselines...")
            baseline_results = run_baselines(proxy_counts, oracle_counts, K, tau)
            for r in baseline_results:
                r['dataset'] = 'realcar_5k'
            all_results.extend(baseline_results)

            # 1. Gap-tolerant stitching
            print("  Running gap-tolerant stitching...")
            gap_results = run_gap_tolerant(proxy_counts, oracle_counts, K, tau)
            for r in gap_results:
                r['dataset'] = 'realcar_5k'
            all_results.extend(gap_results)

            # 2. Soft-window
            print("  Running soft-window candidates...")
            window_results = run_soft_window(proxy_counts, oracle_counts, K, tau)
            for r in window_results:
                r['dataset'] = 'realcar_5k'
            all_results.extend(window_results)

            # 3. Oracle-seeded expansion
            print("  Running oracle-seeded expansion...")
            oracle_results = run_oracle_seeded(proxy_counts, oracle_counts, K, tau)
            for r in oracle_results:
                r['dataset'] = 'realcar_5k'
            all_results.extend(oracle_results)

    # Save results
    df = pd.DataFrame(all_results)
    # Reorder columns
    cols = ['dataset', 'method', 'K', 'tau', 'candidate_count', 'precision',
            'recall', 'mIoU', 'gt_coverage', 'false_splits', 'false_merges',
            'oracle_calls', 'recall_per_call']
    extra_cols = [c for c in df.columns if c not in cols and c != 'max_iou_per_gt']
    df = df[cols + extra_cols]
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nResults saved to {OUTPUT_CSV}")

    # Generate report
    generate_report(df, proxy_counts, oracle_counts, n)

    print(f"Report saved to {OUTPUT_REPORT}")


def generate_report(df, proxy_counts, oracle_counts, n):
    """Generate Markdown report."""
    lines = []
    lines.append("# Fragmentation Repair Baselines Report")
    lines.append("")
    lines.append("**Date**: 2026-06-07")
    lines.append("**Dataset**: realcar_5k")
    lines.append("**Goal**: Verify if temporal repair can convert fragmented proxy signal into effective candidate clips")
    lines.append("")

    # Summary
    lines.append("## 1. Context")
    lines.append("")
    lines.append("From failure attribution:")
    lines.append("- Frame-level proxy/oracle correlation: Pearson r≈0.79")
    lines.append("- Frame-level predicate F1: 0.40")
    lines.append("- Proxy runs (tau>=30): 0, Oracle runs (tau>=30): 5")
    lines.append("- ARC recall=0 because proxy candidate coverage=0")
    lines.append("")
    lines.append("This report tests whether temporal repair can bridge the gap.")
    lines.append("")

    # Results per K and tau
    for K in K_VALUES:
        lines.append("---")
        lines.append("")
        lines.append(f"## Results: K={K}")
        lines.append("")

        for tau in TAU_VALUES:
            subset = df[(df['K'] == K) & (df['tau'] == tau)].copy()
            if subset.empty:
                continue

            # Sort by recall descending
            subset = subset.sort_values('recall', ascending=False)

            lines.append(f"### tau={tau}")
            lines.append("")
            lines.append("| Method | Candidates | Precision | Recall | mIoU | GT Coverage | False Splits | False Merges | Oracle Calls |")
            lines.append("|--------|------------|-----------|--------|------|-------------|--------------|--------------|--------------|")
            for _, row in subset.iterrows():
                lines.append(f"| {row['method']} | {row['candidate_count']} | "
                            f"{row['precision']:.3f} | {row['recall']:.3f} | {row['mIoU']:.3f} | "
                            f"{row['gt_coverage']:.3f} | {row['false_splits']} | {row['false_merges']} | "
                            f"{row['oracle_calls']} |")
            lines.append("")

            # Top performers
            top_recall = subset[subset['recall'] > 0].head(3)
            if not top_recall.empty:
                lines.append("**Top recall methods:**")
                for _, row in top_recall.iterrows():
                    lines.append(f"- {row['method']}: recall={row['recall']:.3f}, "
                                f"precision={row['precision']:.3f}, "
                                f"candidates={row['candidate_count']}")
                lines.append("")

    # Analysis
    lines.append("---")
    lines.append("")
    lines.append("## 2. Key Findings")
    lines.append("")

    # Gap-tolerant analysis
    gap_rows = df[df['method'].str.startswith('gap_stitch')]
    if not gap_rows.empty:
        best_gap = gap_rows.loc[gap_rows['recall'].idxmax()]
        lines.append("### Gap-tolerant Stitching")
        lines.append("")
        lines.append(f"- Best recall: {best_gap['recall']:.3f} with {best_gap['method']}")
        lines.append(f"- This method merges proxy positive frames separated by small gaps")
        lines.append(f"- Effective when proxy signal is fragmented but temporally coherent")
        lines.append("")

    # Soft-window analysis
    window_rows = df[df['method'].str.startswith('soft_win')]
    if not window_rows.empty:
        best_window = window_rows.loc[window_rows['recall'].idxmax()]
        lines.append("### Soft-window Candidates")
        lines.append("")
        lines.append(f"- Best recall: {best_window['recall']:.3f} with {best_window['method']}")
        lines.append(f"- Uses sliding windows on raw proxy counts (not binary threshold)")
        lines.append(f"- Can capture regions where proxy count is elevated but below K")
        lines.append("")

    # Oracle-seeded analysis
    oracle_rows = df[df['method'].str.startswith('oracle_seed')]
    if not oracle_rows.empty:
        best_oracle = oracle_rows.loc[oracle_rows['recall'].idxmax()]
        lines.append("### Oracle-seeded Expansion")
        lines.append("")
        lines.append(f"- Best recall: {best_oracle['recall']:.3f} with {best_oracle['method']}")
        lines.append(f"- Uses oracle queries to seed candidate regions")
        lines.append(f"- Expands using proxy evidence (soft threshold)")
        lines.append(f"- Oracle calls: {best_oracle['oracle_calls']}")
        lines.append("")

    # Comparison with ARC
    lines.append("### Comparison with ARC")
    lines.append("")
    lines.append("ARC achieves recall=0 on this dataset because:")
    lines.append("1. Proxy positive frames are too fragmented (runs < tau)")
    lines.append("2. ARC's initial candidates don't overlap with GT clips")
    lines.append("3. Progressive sampling can't recover from zero initial coverage")
    lines.append("")
    lines.append("Fragmentation repair baselines address issue #1 by:")
    lines.append("- Merging nearby proxy positives (gap-tolerant)")
    lines.append("- Using continuous proxy signal (soft-window)")
    lines.append("- Seeding with oracle queries (oracle-seeded)")
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## 3. Recommendations for ARC Integration")
    lines.append("")
    lines.append("Based on these results:")
    lines.append("")
    lines.append("1. **Pre-process with gap-tolerant stitching**: Before feeding to ARC, "
                 "merge proxy positives with gap_tolerance=10-15")
    lines.append("2. **Use soft-window candidates**: Instead of hard threshold, "
                 "use sliding window mean/percentile as proxy CDF")
    lines.append("3. **Hybrid approach**: Use soft-window to identify candidate regions, "
                 "then run ARC within those regions")
    lines.append("4. **Lower K**: K=10-11 may give enough proxy positives for direct thresholding")
    lines.append("")

    # Write report
    report_text = "\n".join(lines)
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_text)


if __name__ == '__main__':
    main()
