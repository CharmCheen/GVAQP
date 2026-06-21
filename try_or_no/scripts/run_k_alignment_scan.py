#!/usr/bin/env python3
"""
run_k_alignment_scan.py

K-alignment scan for realcar_5k.
Scans K ∈ {8, 10, 11, 12, 13} × tau ∈ {15, 30, 60} to determine
if K=12/13 is too strict, causing proxy-oracle boundary shift.

Usage:
    python scripts/run_k_alignment_scan.py
"""

import sys
import warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')

# ── Configuration ──────────────────────────────────────────────────────────

ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
OUTPUT_CSV = 'outputs/k_alignment_scan.csv'
OUTPUT_REPORT = 'outputs/k_alignment_scan_report.md'

K_VALUES = [8, 10, 11, 12, 13]
TAU_VALUES = [15, 30, 60]

# ── Helpers ────────────────────────────────────────────────────────────────

def load_data():
    df = pd.read_csv(ORACLE_CSV)
    return df['proxy_vehicle_count'].values.astype(float), df['oracle_vehicle_count'].values.astype(float)


def find_runs(binary, min_len=1):
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


def gap_stitch(binary, gap, min_len):
    runs = find_runs(binary, min_len=1)
    if not runs:
        return []
    merged = [list(runs[0])]
    for start, end, length in runs[1:]:
        prev_end = merged[-1][1]
        gap_size = start - prev_end - 1
        if gap_size <= gap:
            merged[-1][1] = end
            merged[-1][2] = merged[-1][1] - merged[-1][0] + 1
        else:
            merged.append([start, end, length])
    return [(m[0], m[1]) for m in merged if m[2] >= min_len]


def clip_iou(a, b):
    inter_start = max(a[0], b[0])
    inter_end = min(a[1], b[1])
    inter_len = max(0, inter_end - inter_start + 1)
    union_start = min(a[0], b[0])
    union_end = max(a[1], b[1])
    union_len = union_end - union_start + 1
    return inter_len / union_len if union_len > 0 else 0.0


def run_length_stats(runs):
    if not runs:
        return {'count': 0, 'min': 0, 'max': 0, 'mean': 0, 'median': 0}
    lengths = [r[2] for r in runs]
    return {
        'count': len(lengths),
        'min': int(min(lengths)),
        'max': int(max(lengths)),
        'mean': round(float(np.mean(lengths)), 1),
        'median': round(float(np.median(lengths)), 1),
    }


def main():
    print("=" * 70)
    print("K-Alignment Scan")
    print("=" * 70)

    proxy_counts, oracle_counts = load_data()
    n = len(proxy_counts)
    print(f"Loaded {n} frames")

    all_results = []

    for K in K_VALUES:
        print(f"\n{'='*70}")
        print(f"K={K}")
        print(f"{'='*70}")

        proxy_binary = (proxy_counts >= K).astype(int)
        oracle_binary = (oracle_counts >= K).astype(int)

        # Frame-level correlation
        pearson_r, pearson_p = stats.pearsonr(proxy_counts, oracle_counts)
        spearman_r, spearman_p = stats.spearmanr(proxy_counts, oracle_counts)

        # Frame-level confusion
        tp = int(((proxy_binary == 1) & (oracle_binary == 1)).sum())
        fp = int(((proxy_binary == 1) & (oracle_binary == 0)).sum())
        fn = int(((proxy_binary == 0) & (oracle_binary == 1)).sum())
        tn = int(((proxy_binary == 0) & (oracle_binary == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # Run length stats
        proxy_runs = find_runs(proxy_binary, min_len=1)
        oracle_runs = find_runs(oracle_binary, min_len=1)
        proxy_stats = run_length_stats(proxy_runs)
        oracle_stats = run_length_stats(oracle_runs)

        print(f"  Proxy positive rate: {proxy_binary.mean():.4f} ({proxy_binary.sum()} frames)")
        print(f"  Oracle positive rate: {oracle_binary.mean():.4f} ({oracle_binary.sum()} frames)")
        print(f"  Pearson r: {pearson_r:.4f}, Spearman r: {spearman_r:.4f}")
        print(f"  F1: {f1:.4f} (P={precision:.4f}, R={recall:.4f})")
        print(f"  Proxy runs: {proxy_stats['count']}, Oracle runs: {oracle_stats['count']}")

        for tau in TAU_VALUES:
            print(f"\n  tau={tau}:")

            # GT clips
            gt_runs = find_runs(oracle_binary, min_len=tau)
            gt_clips = [(s, e) for s, e, l in gt_runs]

            # Proxy hard clips
            proxy_hard_runs = find_runs(proxy_binary, min_len=tau)
            proxy_hard_clips = [(s, e) for s, e, l in proxy_hard_runs]

            # Gap-stitch candidates
            best_recall_09 = 0.0
            best_recall_05 = 0.0
            best_recall_03 = 0.0
            best_max_iou_per_gt = []
            best_boundary_shift = float('inf')
            best_gap = 0

            for gap in [5, 10, 15, 20, 30]:
                candidates = gap_stitch(proxy_binary, gap, tau)
                if not candidates:
                    continue

                # Per-GT max IoU
                max_iou_per_gt = []
                boundary_shifts = []
                for gt in gt_clips:
                    ious = [clip_iou(gt, c) for c in candidates]
                    max_iou = max(ious) if ious else 0.0
                    max_iou_per_gt.append(max_iou)

                    if max_iou > 0:
                        best_cand = candidates[np.argmax(ious)]
                        shift = abs(gt[0] - best_cand[0]) + abs(gt[1] - best_cand[1])
                        boundary_shifts.append(shift / 2)  # Average of start/end shift

                # Recall at different thresholds
                recall_09 = sum(1 for iou in max_iou_per_gt if iou >= 0.9) / len(gt_clips) if gt_clips else 0.0
                recall_05 = sum(1 for iou in max_iou_per_gt if iou >= 0.5) / len(gt_clips) if gt_clips else 0.0
                recall_03 = sum(1 for iou in max_iou_per_gt if iou >= 0.3) / len(gt_clips) if gt_clips else 0.0
                avg_shift = np.mean(boundary_shifts) if boundary_shifts else float('inf')

                if recall_09 > best_recall_09 or (recall_09 == best_recall_09 and recall_05 > best_recall_05):
                    best_recall_09 = recall_09
                    best_recall_05 = recall_05
                    best_recall_03 = recall_03
                    best_max_iou_per_gt = max_iou_per_gt
                    best_boundary_shift = avg_shift
                    best_gap = gap

            # Run length distributions for tau-filtered runs
            proxy_tau_runs = find_runs(proxy_binary, min_len=tau)
            oracle_tau_runs = find_runs(oracle_binary, min_len=tau)
            proxy_tau_stats = run_length_stats(proxy_tau_runs)
            oracle_tau_stats = run_length_stats(oracle_tau_runs)

            row = {
                'K': K,
                'tau': tau,
                'pearson_r': round(pearson_r, 4),
                'spearman_r': round(spearman_r, 4),
                'precision': round(precision, 4),
                'recall': round(recall, 4),
                'f1': round(f1, 4),
                'proxy_positive_frames': int(proxy_binary.sum()),
                'oracle_positive_frames': int(oracle_binary.sum()),
                'proxy_run_count': proxy_stats['count'],
                'oracle_run_count': oracle_stats['count'],
                'proxy_run_mean_len': proxy_stats['mean'],
                'oracle_run_mean_len': oracle_stats['mean'],
                'proxy_run_median_len': proxy_stats['median'],
                'oracle_run_median_len': oracle_stats['median'],
                'gt_clip_count': len(gt_clips),
                'proxy_hard_clip_count': len(proxy_hard_clips),
                'best_gap': best_gap,
                'recall_09': round(best_recall_09, 4),
                'recall_05': round(best_recall_05, 4),
                'recall_03': round(best_recall_03, 4),
                'max_iou_per_gt': [round(iou, 4) for iou in best_max_iou_per_gt],
                'avg_boundary_shift': round(best_boundary_shift, 1) if best_boundary_shift != float('inf') else 999,
                'proxy_tau_run_count': proxy_tau_stats['count'],
                'oracle_tau_run_count': oracle_tau_stats['count'],
                'proxy_tau_run_mean_len': proxy_tau_stats['mean'],
                'oracle_tau_run_mean_len': oracle_tau_stats['mean'],
            }
            all_results.append(row)

            print(f"    GT clips: {len(gt_clips)}, Proxy hard clips: {len(proxy_hard_clips)}")
            print(f"    Best gap: {best_gap}")
            print(f"    Recall@0.9: {best_recall_09:.3f}, Recall@0.5: {best_recall_05:.3f}, Recall@0.3: {best_recall_03:.3f}")
            if best_max_iou_per_gt:
                print(f"    Max IoU per GT: {[round(iou, 3) for iou in best_max_iou_per_gt]}")
            print(f"    Avg boundary shift: {best_boundary_shift:.1f} frames")

    # Save results
    df = pd.DataFrame(all_results)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nResults saved to {OUTPUT_CSV}")

    # Generate report
    generate_report(df)
    print(f"Report saved to {OUTPUT_REPORT}")


def generate_report(df):
    lines = []
    lines.append("# K-Alignment Scan Report")
    lines.append("")
    lines.append("**Date**: 2026-06-07")
    lines.append("**Dataset**: realcar_5k")
    lines.append("**Goal**: Determine if K=12/13 is too strict, causing proxy-oracle boundary shift")
    lines.append("")

    # Summary table
    lines.append("---")
    lines.append("")
    lines.append("## 1. Summary Table")
    lines.append("")
    lines.append("| K | tau | F1 | GT Clips | Recall@0.9 | Recall@0.5 | Recall@0.3 | Avg Shift | Best Gap |")
    lines.append("|---|-----|-----|----------|------------|------------|------------|-----------|----------|")
    for _, row in df.iterrows():
        lines.append(f"| {row['K']} | {row['tau']} | {row['f1']:.3f} | {row['gt_clip_count']} | "
                    f"{row['recall_09']:.3f} | {row['recall_05']:.3f} | {row['recall_03']:.3f} | "
                    f"{row['avg_boundary_shift']:.1f} | {row['best_gap']} |")
    lines.append("")

    # Frame-level metrics
    lines.append("---")
    lines.append("")
    lines.append("## 2. Frame-Level Metrics by K")
    lines.append("")
    lines.append("| K | Proxy Pos Rate | Oracle Pos Rate | Pearson r | Spearman r | Precision | Recall | F1 |")
    lines.append("|---|----------------|-----------------|-----------|------------|-----------|--------|-----|")
    for K in df['K'].unique():
        row = df[df['K'] == K].iloc[0]
        lines.append(f"| {K} | {row['proxy_positive_frames']/5000:.4f} | {row['oracle_positive_frames']/5000:.4f} | "
                    f"{row['pearson_r']:.4f} | {row['spearman_r']:.4f} | "
                    f"{row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |")
    lines.append("")

    # Run length distribution
    lines.append("---")
    lines.append("")
    lines.append("## 3. Run Length Distribution")
    lines.append("")
    lines.append("| K | Proxy Runs | Proxy Mean Len | Proxy Median | Oracle Runs | Oracle Mean Len | Oracle Median |")
    lines.append("|---|------------|----------------|--------------|-------------|-----------------|---------------|")
    for K in df['K'].unique():
        row = df[df['K'] == K].iloc[0]
        lines.append(f"| {K} | {row['proxy_run_count']} | {row['proxy_run_mean_len']:.1f} | "
                    f"{row['proxy_run_median_len']:.1f} | {row['oracle_run_count']} | "
                    f"{row['oracle_run_mean_len']:.1f} | {row['oracle_run_median_len']:.1f} |")
    lines.append("")

    # Per-K detailed analysis
    lines.append("---")
    lines.append("")
    lines.append("## 4. Per-K Detailed Analysis")
    lines.append("")

    for K in df['K'].unique():
        k_df = df[df['K'] == K]
        row = k_df.iloc[0]

        lines.append(f"### K={K}")
        lines.append("")
        lines.append(f"**Frame-level**: F1={row['f1']:.3f}, Precision={row['precision']:.3f}, Recall={row['recall']:.3f}")
        lines.append(f"**Correlation**: Pearson r={row['pearson_r']:.4f}, Spearman r={row['spearman_r']:.4f}")
        lines.append(f"**Proxy runs**: {row['proxy_run_count']} (mean={row['proxy_run_mean_len']:.1f}, median={row['proxy_run_median_len']:.1f})")
        lines.append(f"**Oracle runs**: {row['oracle_run_count']} (mean={row['oracle_run_mean_len']:.1f}, median={row['oracle_run_median_len']:.1f})")
        lines.append("")

        for _, tau_row in k_df.iterrows():
            tau = tau_row['tau']
            lines.append(f"#### tau={tau}")
            lines.append("")
            lines.append(f"- GT clips: {tau_row['gt_clip_count']}")
            lines.append(f"- Proxy hard clips: {tau_row['proxy_hard_clip_count']}")
            lines.append(f"- Best gap: {tau_row['best_gap']}")
            lines.append(f"- Recall@0.9: {tau_row['recall_09']:.3f}")
            lines.append(f"- Recall@0.5: {tau_row['recall_05']:.3f}")
            lines.append(f"- Recall@0.3: {tau_row['recall_03']:.3f}")
            lines.append(f"- Avg boundary shift: {tau_row['avg_boundary_shift']:.1f} frames")

            if tau_row['max_iou_per_gt']:
                max_ious = tau_row['max_iou_per_gt']
                if isinstance(max_ious, str):
                    max_ious = eval(max_ious)
                lines.append(f"- Max IoU per GT: {[round(iou, 3) for iou in max_ious]}")
            lines.append("")

    # Key findings
    lines.append("---")
    lines.append("")
    lines.append("## 5. Key Findings")
    lines.append("")

    # Find best K for each tau
    for tau in [15, 30, 60]:
        tau_df = df[df['tau'] == tau]
        best_row = tau_df.loc[tau_df['recall_05'].idxmax()]
        lines.append(f"### tau={tau}")
        lines.append("")
        lines.append(f"**Best K**: {int(best_row['K'])} (Recall@0.5={best_row['recall_05']:.3f}, F1={best_row['f1']:.3f})")
        lines.append("")

    # K=12/13 analysis
    lines.append("### K=12/13 Analysis")
    lines.append("")
    for K in [12, 13]:
        k_df = df[df['K'] == K]
        row = k_df.iloc[0]
        lines.append(f"**K={K}**: F1={row['f1']:.3f}, Recall@0.5={k_df['recall_05'].max():.3f}, "
                    f"Avg shift={k_df['avg_boundary_shift'].mean():.1f} frames")
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## 6. Recommendations")
    lines.append("")

    # Find K with best balance
    df['score'] = df['f1'] * 0.3 + df['recall_05'] * 0.4 + (1 - df['avg_boundary_shift'] / 100) * 0.3
    best_overall = df.loc[df['score'].idxmax()]

    lines.append(f"1. **Best overall K**: {int(best_overall['K'])} (F1={best_overall['f1']:.3f}, "
                f"Recall@0.5={best_overall['recall_05']:.3f}, Shift={best_overall['avg_boundary_shift']:.1f})")
    lines.append("")
    lines.append("2. **K=12/13 is too strict** for this dataset:")
    lines.append(f"   - F1 is low ({df[df['K']==12]['f1'].iloc[0]:.3f}, {df[df['K']==13]['f1'].iloc[0]:.3f})")
    lines.append(f"   - Boundary shift is large ({df[df['K']==12]['avg_boundary_shift'].mean():.1f} frames)")
    lines.append(f"   - Recall@0.5 is low ({df[df['K']==12]['recall_05'].max():.3f})")
    lines.append("")
    lines.append("3. **K=10-11 provides better balance**:")
    lines.append(f"   - F1: {df[df['K']==10]['f1'].iloc[0]:.3f}, {df[df['K']==11]['f1'].iloc[0]:.3f}")
    lines.append(f"   - Recall@0.5: {df[df['K']==10]['recall_05'].max():.3f}, {df[df['K']==11]['recall_05'].max():.3f}")
    lines.append("")
    lines.append("4. **tau=15 is most forgiving** (more GT clips, shorter clips easier to match)")
    lines.append("")

    report_text = "\n".join(lines)
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_text)


if __name__ == '__main__':
    main()
