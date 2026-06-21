#!/usr/bin/env python3
"""
run_adaptive_candidate_upper_bound.py

Upper bound analysis for adaptive candidates.
Uses full oracle sequence within candidate regions to test if
strict IoU@0.9 is theoretically achievable.

Usage:
    python scripts/run_adaptive_candidate_upper_bound.py
"""

import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ── Configuration ──────────────────────────────────────────────────────────

ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
ADAPTIVE_RESULTS = 'outputs/adaptive_relaxed_candidate_results.csv'
OUTPUT_CSV = 'outputs/adaptive_candidate_upper_bound_results.csv'
OUTPUT_REPORT = 'outputs/adaptive_candidate_upper_bound_report.md'

KQ_VALUES = [12, 13]
TAU_VALUES = [15, 30, 60]
IOU_THRESHOLDS = [0.9, 0.7, 0.5, 0.3]
GAP = 15

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


def calc_metrics(gt_clips, pred_clips):
    """Calculate metrics at multiple IoU thresholds."""
    if len(gt_clips) == 0 and len(pred_clips) == 0:
        base = {'precision': 1.0, 'mIoU': 1.0, 'gt_coverage': 1.0,
                'boundary_offset_mean': 0.0, 'false_splits': 0, 'false_merges': 0}
        for t in IOU_THRESHOLDS:
            base[f'recall_{int(t*100)}'] = 1.0
        return base
    if len(gt_clips) == 0:
        base = {'precision': 0.0, 'mIoU': 0.0, 'gt_coverage': 0.0,
                'boundary_offset_mean': float('inf'), 'false_splits': 0, 'false_merges': 0}
        for t in IOU_THRESHOLDS:
            base[f'recall_{int(t*100)}'] = 1.0
        return base
    if len(pred_clips) == 0:
        base = {'precision': 1.0, 'mIoU': 0.0, 'gt_coverage': 0.0,
                'boundary_offset_mean': float('inf'), 'false_splits': 0, 'false_merges': 0}
        for t in IOU_THRESHOLDS:
            base[f'recall_{int(t*100)}'] = 0.0
        return base

    max_iou_per_gt = []
    boundary_offsets = []
    for gt in gt_clips:
        ious = [clip_iou(gt, pred) for pred in pred_clips]
        max_iou = max(ious) if ious else 0.0
        max_iou_per_gt.append(max_iou)
        if max_iou > 0:
            best_pred = pred_clips[np.argmax(ious)]
            offset = (abs(gt[0] - best_pred[0]) + abs(gt[1] - best_pred[1])) / 2
            boundary_offsets.append(offset)

    gt_coverage = sum(1 for iou in max_iou_per_gt if iou > 0) / len(gt_clips)
    hits_precision = sum(1 for pred in pred_clips if max(clip_iou(pred, gt) for gt in gt_clips) >= 0.5)
    precision = hits_precision / len(pred_clips)
    mIoU = sum(max_iou_per_gt) / len(gt_clips)

    gt_to_pred = {}
    for pi, pred in enumerate(pred_clips):
        for gi, gt in enumerate(gt_clips):
            if clip_iou(pred, gt) > 0:
                gt_to_pred.setdefault(gi, []).append(pi)
    false_splits = sum(1 for v in gt_to_pred.values() if len(v) > 1)

    pred_to_gt = {}
    for pi, pred in enumerate(pred_clips):
        for gi, gt in enumerate(gt_clips):
            if clip_iou(pred, gt) > 0:
                pred_to_gt.setdefault(pi, []).append(gi)
    false_merges = sum(1 for v in pred_to_gt.values() if len(v) > 1)

    result = {
        'precision': round(precision, 4),
        'mIoU': round(mIoU, 4),
        'gt_coverage': round(gt_coverage, 4),
        'boundary_offset_mean': round(np.mean(boundary_offsets), 1) if boundary_offsets else 999,
        'false_splits': false_splits,
        'false_merges': false_merges,
    }

    for t in IOU_THRESHOLDS:
        recall = sum(1 for iou in max_iou_per_gt if iou >= t) / len(gt_clips)
        result[f'recall_{int(t*100)}'] = round(recall, 4)

    return result


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Adaptive Candidate Upper Bound Analysis")
    print("=" * 70)

    proxy_counts, oracle_counts = load_data()
    n = len(proxy_counts)
    print(f"Loaded {n} frames")

    adaptive_df = pd.read_csv(ADAPTIVE_RESULTS)
    all_results = []

    for Kq in KQ_VALUES:
        print(f"\n{'='*70}")
        print(f"Kq={Kq}")
        print(f"{'='*70}")

        for tau in TAU_VALUES:
            oracle_binary = (oracle_counts >= Kq).astype(int)
            gt_clips = find_runs(oracle_binary, min_len=tau)
            gt_tuples = [(s, e) for s, e, l in gt_clips]
            print(f"\n  tau={tau}: GT clips={len(gt_tuples)}")

            # ── Full oracle baseline ─────────────────────────────────
            oracle_clips = gt_tuples
            oracle_metrics = calc_metrics(gt_tuples, oracle_clips)
            all_results.append({
                'method': 'full_oracle', 'Kq': Kq, 'tau': tau,
                'candidate_count': len(oracle_clips),
                'candidate_frame_fraction': 1.0,
                'oracle_scanned_fraction': 1.0,
                **oracle_metrics,
            })

            # ── Get adaptive candidates ─────────────────────────────
            adapt_row = adaptive_df[(adaptive_df['Kq'] == Kq) & (adaptive_df['tau'] == tau) &
                                   (adaptive_df['method'] == 'adaptive_relaxed')]
            if adapt_row.empty:
                print(f"  No adaptive results found, skipping")
                continue

            adapt_row = adapt_row.iloc[0]
            Kp = int(adapt_row['selected_Kp'])
            gap = int(adapt_row['selected_gap'])
            print(f"  Adaptive: Kp={Kp}, gap={gap}")

            # Generate adaptive candidates
            proxy_binary = (proxy_counts >= Kp).astype(int)
            candidates = gap_stitch(proxy_binary, gap, tau)
            print(f"  Candidates: {len(candidates)}")

            # Candidate frame fraction
            cand_frames = sum(e - s + 1 for s, e in candidates)
            cand_fraction = cand_frames / n
            print(f"  Candidate frame fraction: {cand_fraction:.4f}")

            # ── Oracle-only inside candidates ────────────────────────
            # For each candidate region, use full oracle to find clips
            oracle_refined_clips = []
            for start, end in candidates:
                # Extract oracle binary within candidate region
                region_oracle = oracle_binary[start:end + 1]
                # Find oracle clips within this region
                region_clips = find_runs(region_oracle, min_len=tau)
                # Convert to global indices
                for rs, re, rl in region_clips:
                    oracle_refined_clips.append((start + rs, start + re))

            print(f"  Oracle-refined clips: {len(oracle_refined_clips)}")

            # Calculate metrics
            oracle_refined_metrics = calc_metrics(gt_tuples, oracle_refined_clips)
            oracle_scanned_fraction = cand_fraction  # We scanned all candidate frames

            all_results.append({
                'method': 'oracle_in_candidates', 'Kq': Kq, 'tau': tau,
                'candidate_count': len(candidates),
                'candidate_frame_fraction': round(cand_fraction, 4),
                'oracle_scanned_fraction': round(oracle_scanned_fraction, 4),
                'oracle_refined_count': len(oracle_refined_clips),
                **oracle_refined_metrics,
            })

            # ── Oracle-only inside candidates (with expansion) ───────
            # Expand each candidate by 10 frames on each side before oracle scan
            oracle_expanded_clips = []
            for start, end in candidates:
                exp_start = max(0, start - 10)
                exp_end = min(n - 1, end + 10)
                region_oracle = oracle_binary[exp_start:exp_end + 1]
                region_clips = find_runs(region_oracle, min_len=tau)
                for rs, re, rl in region_clips:
                    oracle_expanded_clips.append((exp_start + rs, exp_start + re))

            expanded_frames = sum(min(n - 1, end + 10) - max(0, start - 10) + 1 for start, end in candidates)
            expanded_fraction = expanded_frames / n

            oracle_expanded_metrics = calc_metrics(gt_tuples, oracle_expanded_clips)
            all_results.append({
                'method': 'oracle_in_expanded', 'Kq': Kq, 'tau': tau,
                'candidate_count': len(candidates),
                'candidate_frame_fraction': round(cand_fraction, 4),
                'oracle_scanned_fraction': round(expanded_fraction, 4),
                'oracle_refined_count': len(oracle_expanded_clips),
                **oracle_expanded_metrics,
            })

            # ── Hard proxy baseline ──────────────────────────────────
            proxy_binary_hard = (proxy_counts >= Kq).astype(int)
            hard_candidates = gap_stitch(proxy_binary_hard, gap, tau)
            hard_metrics = calc_metrics(gt_tuples, hard_candidates)
            hard_fraction = sum(e - s + 1 for s, e in hard_candidates) / n if hard_candidates else 0.0
            all_results.append({
                'method': 'hard_proxy', 'Kq': Kq, 'tau': tau,
                'candidate_count': len(hard_candidates),
                'candidate_frame_fraction': round(hard_fraction, 4),
                'oracle_scanned_fraction': 0.0,
                **hard_metrics,
            })

            # ── Adaptive without oracle ──────────────────────────────
            adapt_metrics = calc_metrics(gt_tuples, candidates)
            all_results.append({
                'method': 'adaptive_no_oracle', 'Kq': Kq, 'tau': tau,
                'candidate_count': len(candidates),
                'candidate_frame_fraction': round(cand_fraction, 4),
                'oracle_scanned_fraction': 0.0,
                **adapt_metrics,
            })

    # Save results
    df = pd.DataFrame(all_results)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nResults saved to {OUTPUT_CSV}")

    generate_report(df)
    print(f"Report saved to {OUTPUT_REPORT}")


def generate_report(df):
    lines = []
    lines.append("# Adaptive Candidate Upper Bound Analysis Report")
    lines.append("")
    lines.append("**Date**: 2026-06-07")
    lines.append("**Dataset**: realcar_5k")
    lines.append("**Goal**: Determine if adaptive candidates theoretically support strict IoU@0.9")
    lines.append("")

    # Summary table
    for Kq in KQ_VALUES:
        lines.append("---")
        lines.append("")
        lines.append(f"## Kq={Kq}")
        lines.append("")

        for tau in TAU_VALUES:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau)]
            if subset.empty:
                continue

            lines.append(f"### tau={tau}")
            lines.append("")
            lines.append("| Method | Cand Count | Frame Frac | Scan Frac | R@0.9 | R@0.7 | R@0.5 | mIoU | Coverage |")
            lines.append("|--------|------------|------------|-----------|-------|-------|-------|------|----------|")

            for _, row in subset.iterrows():
                lines.append(f"| {row['method']} | {row['candidate_count']} | "
                            f"{row['candidate_frame_fraction']:.3f} | "
                            f"{row['oracle_scanned_fraction']:.3f} | "
                            f"{row['recall_90']:.3f} | {row['recall_70']:.3f} | "
                            f"{row['recall_50']:.3f} | {row['mIoU']:.3f} | "
                            f"{row['gt_coverage']:.3f} |")
            lines.append("")

    # Key questions
    lines.append("---")
    lines.append("")
    lines.append("## Key Questions")
    lines.append("")

    # Q1: Do candidates contain enough info for IoU@0.9?
    lines.append("### Q1: Do adaptive candidates contain enough information for strict IoU@0.9?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            oracle_in = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'oracle_in_candidates')]
            if oracle_in.empty:
                continue
            row = oracle_in.iloc[0]
            lines.append(f"- Kq={Kq}, tau={tau}: oracle-in-candidates R@0.9={row['recall_90']:.3f}, "
                        f"R@0.5={row['recall_50']:.3f}, coverage={row['gt_coverage']:.3f}")
    lines.append("")

    # Q2: If R@0.9=0, is it candidate structure or GT semantics?
    lines.append("### Q2: If R@0.9=0 with full oracle, is it candidate structure or GT semantics?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            oracle_in = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'oracle_in_candidates')]
            full_oracle = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'full_oracle')]
            if oracle_in.empty or full_oracle.empty:
                continue
            r90_in = oracle_in.iloc[0]['recall_90']
            r90_full = full_oracle.iloc[0]['recall_90']
            lines.append(f"- Kq={Kq}, tau={tau}: oracle-in-candidates R@0.9={r90_in:.3f}, "
                        f"full-oracle R@0.9={r90_full:.3f}")
            if r90_in == 0 and r90_full == 0:
                lines.append(f"  → GT semantics issue: even full oracle can't achieve R@0.9")
            elif r90_in == 0 and r90_full > 0:
                lines.append(f"  → Candidate structure issue: candidates miss GT clips")
            elif r90_in > 0:
                lines.append(f"  → Candidates contain enough info, refinement can work")
    lines.append("")

    # Q3: Upper bound vs current refinement
    lines.append("### Q3: Upper bound vs current refinement")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            oracle_in = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'oracle_in_candidates')]
            adapt = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'adaptive_no_oracle')]
            if oracle_in.empty or adapt.empty:
                continue
            lines.append(f"- Kq={Kq}, tau={tau}: "
                        f"adaptive R@0.5={adapt.iloc[0]['recall_50']:.3f}, "
                        f"upper-bound R@0.5={oracle_in.iloc[0]['recall_50']:.3f}")
    lines.append("")

    # Q4: Candidate frame fraction
    lines.append("### Q4: Candidate frame fraction vs full video")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            oracle_in = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'oracle_in_candidates')]
            if oracle_in.empty:
                continue
            row = oracle_in.iloc[0]
            lines.append(f"- Kq={Kq}, tau={tau}: "
                        f"candidate fraction={row['candidate_frame_fraction']:.3f}, "
                        f"oracle scan fraction={row['oracle_scanned_fraction']:.3f}")
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("1. **If upper-bound R@0.9 > 0**: Boundary refinement can potentially achieve it")
    lines.append("2. **If upper-bound R@0.9 = 0**: Need to expand candidates or accept R@0.5 as target")
    lines.append("3. **Candidate fraction**: Adaptive candidates cover significantly less than full video")
    lines.append("4. **Oracle efficiency**: Scanning only candidate regions saves oracle budget")
    lines.append("")

    report_text = "\n".join(lines)
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_text)


if __name__ == '__main__':
    main()
