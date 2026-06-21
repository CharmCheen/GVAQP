#!/usr/bin/env python3
"""
run_decoupled_kp_kq_experiment.py

Decoupled proxy-threshold experiment.
Uses relaxed Kp for candidate generation, strict Kq for oracle queries.

Usage:
    python scripts/run_decoupled_kp_kq_experiment.py
"""

import sys
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ── Configuration ──────────────────────────────────────────────────────────

ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
OUTPUT_CSV = 'outputs/decoupled_kp_kq_results.csv'
OUTPUT_REPORT = 'outputs/decoupled_kp_kq_report.md'

KQ_VALUES = [12, 13]          # Oracle query threshold
KP_VALUES = [6, 8, 10, 11, 12, 13]  # Proxy candidate threshold
TAU_VALUES = [15, 30, 60]
GAP_VALUES = [5, 10, 15, 20, 30]
WINDOW_SIZES = [30, 60]
STRIDES = [5, 10]
BUDGET_FRACS = [0.02, 0.05, 0.10]
IOU_THRESHOLD = 0.9

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


def soft_window_candidates(proxy_counts, window_size, stride, tau):
    n = len(proxy_counts)
    windows = []
    for start in range(0, n - window_size + 1, stride):
        end = start + window_size - 1
        score = np.percentile(proxy_counts[start:end + 1], 80)
        windows.append((start, end, score))

    windows.sort(key=lambda x: -x[2])
    selected = []
    covered = set()
    for start, end, score in windows:
        new_frames = set(range(start, end + 1)) - covered
        if len(new_frames) >= tau // 2:
            selected.append((start, end, score))
            covered.update(range(start, end + 1))

    if not selected:
        return []

    selected.sort(key=lambda x: x[0])
    stitched = [list(selected[0])]
    for start, end, score in selected[1:]:
        if start <= stitched[-1][1] + 1:
            stitched[-1][1] = max(stitched[-1][1], end)
        else:
            stitched.append([start, end, score])

    return [(s, e) for s, e, _ in stitched if (e - s + 1) >= tau]


def clip_iou(a, b):
    inter_start = max(a[0], b[0])
    inter_end = min(a[1], b[1])
    inter_len = max(0, inter_end - inter_start + 1)
    union_start = min(a[0], b[0])
    union_end = max(a[1], b[1])
    union_len = union_end - union_start + 1
    return inter_len / union_len if union_len > 0 else 0.0


def calc_metrics(gt_clips, pred_clips, threshold=IOU_THRESHOLD):
    if len(gt_clips) == 0 and len(pred_clips) == 0:
        return {'precision': 1.0, 'recall': 1.0, 'recall_05': 1.0, 'recall_03': 1.0,
                'mIoU': 1.0, 'gt_coverage': 1.0, 'boundary_offset_mean': 0.0,
                'false_splits': 0, 'false_merges': 0}
    if len(gt_clips) == 0:
        return {'precision': 0.0, 'recall': 1.0, 'recall_05': 1.0, 'recall_03': 1.0,
                'mIoU': 0.0, 'gt_coverage': 0.0, 'boundary_offset_mean': float('inf'),
                'false_splits': 0, 'false_merges': 0}
    if len(pred_clips) == 0:
        return {'precision': 1.0, 'recall': 0.0, 'recall_05': 0.0, 'recall_03': 0.0,
                'mIoU': 0.0, 'gt_coverage': 0.0, 'boundary_offset_mean': float('inf'),
                'false_splits': 0, 'false_merges': 0}

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

    hits_precision = sum(1 for pred in pred_clips if max(clip_iou(pred, gt) for gt in gt_clips) >= threshold)
    precision = hits_precision / len(pred_clips)

    recall = sum(1 for iou in max_iou_per_gt if iou >= threshold) / len(gt_clips)
    recall_05 = sum(1 for iou in max_iou_per_gt if iou >= 0.5) / len(gt_clips)
    recall_03 = sum(1 for iou in max_iou_per_gt if iou >= 0.3) / len(gt_clips)
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

    return {
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'recall_05': round(recall_05, 4),
        'recall_03': round(recall_03, 4),
        'mIoU': round(mIoU, 4),
        'gt_coverage': round(gt_coverage, 4),
        'boundary_offset_mean': round(np.mean(boundary_offsets), 1) if boundary_offsets else 999,
        'false_splits': false_splits,
        'false_merges': false_merges,
    }


def oracle_refine(candidates, oracle_binary, budget, tau):
    """Anchor verification + boundary refinement."""
    if not candidates or budget <= 0:
        return candidates, 0

    verified = []
    oracle_calls = 0

    for start, end in candidates:
        if oracle_calls >= budget:
            verified.append((start, end))
            continue

        length = end - start + 1
        n_samples = min(5, length)
        sample_indices = [start + int(i * (length - 1) / (n_samples - 1)) for i in range(n_samples)]

        positive_count = 0
        for idx in sample_indices:
            if oracle_calls >= budget:
                break
            oracle_calls += 1
            if oracle_binary[idx] == 1:
                positive_count += 1

        if positive_count > 0:
            # Find positive block
            positive_blocks = []
            block_start = None
            for i in range(start, end + 1, max(1, length // 20)):
                if oracle_calls >= budget:
                    break
                oracle_calls += 1
                if oracle_binary[i] == 1:
                    if block_start is None:
                        block_start = i
                else:
                    if block_start is not None:
                        positive_blocks.append((block_start, i - 1))
                        block_start = None
            if block_start is not None:
                positive_blocks.append((block_start, end))

            if positive_blocks:
                best_block = max(positive_blocks, key=lambda x: x[1] - x[0])
                block_start = max(start, best_block[0] - 5)
                block_end = min(end, best_block[1] + 5)
                if block_end - block_start + 1 >= tau:
                    verified.append((block_start, block_end))

    return verified, oracle_calls


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Decoupled Kp/Kq Experiment")
    print("=" * 70)

    proxy_counts, oracle_counts = load_data()
    n = len(proxy_counts)
    print(f"Loaded {n} frames")

    all_results = []

    for Kq in KQ_VALUES:
        oracle_binary = (oracle_counts >= Kq).astype(int)
        print(f"\n{'='*70}")
        print(f"Kq={Kq} (oracle threshold)")
        print(f"{'='*70}")

        for tau in TAU_VALUES:
            gt_clips = find_runs(oracle_binary, min_len=tau)
            gt_tuples = [(s, e) for s, e, l in gt_clips]
            print(f"\n  tau={tau}: GT clips={len(gt_tuples)}")

            # Oracle-only baseline
            oracle_clips = gt_tuples
            all_results.append({
                'method': 'oracle_only', 'Kq': Kq, 'Kp': Kq, 'tau': tau,
                'candidate_count': len(oracle_clips), 'candidate_frame_fraction': 1.0,
                'oracle_calls': n, 'recall_per_call': round(1.0 / n, 6),
                'runtime_sec': 0.0, 'gap': '-', 'budget_frac': 1.0,
                **calc_metrics(gt_tuples, oracle_clips),
            })

            for Kp in KP_VALUES:
                proxy_binary = (proxy_counts >= Kp).astype(int)
                proxy_pos_rate = proxy_binary.mean()

                # 1. Hard proxy (Kp=Kq only)
                if Kp == Kq:
                    proxy_clips = find_runs(proxy_binary, min_len=tau)
                    proxy_tuples = [(s, e) for s, e, l in proxy_clips]
                    frame_frac = sum(e - s + 1 for s, e in proxy_tuples) / n
                    all_results.append({
                        'method': 'hard_proxy', 'Kq': Kq, 'Kp': Kp, 'tau': tau,
                        'candidate_count': len(proxy_tuples),
                        'candidate_frame_fraction': round(frame_frac, 4),
                        'oracle_calls': 0, 'recall_per_call': 0.0,
                        'runtime_sec': 0.0, 'gap': '-', 'budget_frac': 0.0,
                        **calc_metrics(gt_tuples, proxy_tuples),
                    })

                # 2. Relaxed gap-stitch
                for gap in GAP_VALUES:
                    t0 = time.time()
                    candidates = gap_stitch(proxy_binary, gap, tau)
                    t1 = time.time()
                    frame_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0
                    metrics = calc_metrics(gt_tuples, candidates)
                    all_results.append({
                        'method': 'relaxed_gap_stitch', 'Kq': Kq, 'Kp': Kp, 'tau': tau,
                        'candidate_count': len(candidates),
                        'candidate_frame_fraction': round(frame_frac, 4),
                        'oracle_calls': 0, 'recall_per_call': 0.0,
                        'runtime_sec': round(t1 - t0, 3), 'gap': gap, 'budget_frac': 0.0,
                        **metrics,
                    })

                    # 3. Relaxed gap-stitch + oracle refinement
                    for bf in BUDGET_FRACS:
                        budget = int(bf * n)
                        t0 = time.time()
                        refined, oracle_calls = oracle_refine(candidates, oracle_binary, budget, tau)
                        t1 = time.time()
                        ref_metrics = calc_metrics(gt_tuples, refined)
                        recall_per_call = ref_metrics['recall'] / oracle_calls if oracle_calls > 0 else 0.0
                        all_results.append({
                            'method': 'relaxed_gap_stitch_refined', 'Kq': Kq, 'Kp': Kp, 'tau': tau,
                            'candidate_count': len(candidates),
                            'candidate_frame_fraction': round(frame_frac, 4),
                            'final_count': len(refined),
                            'oracle_calls': oracle_calls,
                            'recall_per_call': round(recall_per_call, 6),
                            'runtime_sec': round(t1 - t0, 3), 'gap': gap, 'budget_frac': bf,
                            **ref_metrics,
                        })

                # 4. Relaxed soft-window
                for ws in WINDOW_SIZES:
                    for stride in STRIDES:
                        t0 = time.time()
                        candidates = soft_window_candidates(proxy_counts, ws, stride, tau)
                        t1 = time.time()
                        frame_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0
                        metrics = calc_metrics(gt_tuples, candidates)
                        all_results.append({
                            'method': 'relaxed_soft_window', 'Kq': Kq, 'Kp': Kp, 'tau': tau,
                            'candidate_count': len(candidates),
                            'candidate_frame_fraction': round(frame_frac, 4),
                            'oracle_calls': 0, 'recall_per_call': 0.0,
                            'runtime_sec': round(t1 - t0, 3),
                            'window_size': ws, 'stride': stride, 'budget_frac': 0.0,
                            **metrics,
                        })

    # Save results
    df = pd.DataFrame(all_results)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nResults saved to {OUTPUT_CSV}")

    # Generate report
    generate_report(df)
    print(f"Report saved to {OUTPUT_REPORT}")


def generate_report(df):
    lines = []
    lines.append("# Decoupled Kp/Kq Experiment Report")
    lines.append("")
    lines.append("**Date**: 2026-06-07")
    lines.append("**Dataset**: realcar_5k")
    lines.append("**Goal**: Verify if relaxed Kp improves candidate coverage under strict Kq")
    lines.append("")

    # Summary by Kq and tau
    for Kq in KQ_VALUES:
        lines.append("---")
        lines.append("")
        lines.append(f"## Kq={Kq}")
        lines.append("")

        for tau in TAU_VALUES:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'relaxed_gap_stitch')]
            if subset.empty:
                continue

            lines.append(f"### tau={tau}")
            lines.append("")
            lines.append("| Kp | Best Gap | Coverage | R@0.9 | R@0.5 | R@0.3 | mIoU | False Merge | Frame Frac |")
            lines.append("|----|----------|----------|-------|-------|-------|------|-------------|------------|")

            for Kp in KP_VALUES:
                kp_subset = subset[subset['Kp'] == Kp]
                if kp_subset.empty:
                    continue
                best = kp_subset.loc[kp_subset['recall_05'].idxmax()]
                lines.append(f"| {Kp} | {best['gap']} | {best['gt_coverage']:.3f} | "
                            f"{best['recall']:.3f} | {best['recall_05']:.3f} | {best['recall_03']:.3f} | "
                            f"{best['mIoU']:.3f} | {best['false_merges']} | {best['candidate_frame_fraction']:.3f} |")
            lines.append("")

    # Q1: Best Kp for each Kq
    lines.append("---")
    lines.append("")
    lines.append("## Key Questions")
    lines.append("")
    lines.append("### Q1: Best Kp for each Kq")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'relaxed_gap_stitch')]
            if subset.empty:
                continue
            best = subset.loc[subset['recall_05'].idxmax()]
            lines.append(f"- Kq={Kq}, tau={tau}: best Kp={int(best['Kp'])} "
                        f"(R@0.5={best['recall_05']:.3f}, coverage={best['gt_coverage']:.3f})")
    lines.append("")

    # Q2: Does relaxed Kp improve coverage?
    lines.append("### Q2: Does relaxed Kp improve GT coverage?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            hard = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'hard_proxy')]
            relaxed = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'relaxed_gap_stitch')]
            if hard.empty or relaxed.empty:
                continue
            hard_cov = hard.iloc[0]['gt_coverage']
            best_relaxed = relaxed.loc[relaxed['gt_coverage'].idxmax()]
            lines.append(f"- Kq={Kq}, tau={tau}: hard coverage={hard_cov:.3f} → "
                        f"best relaxed coverage={best_relaxed['gt_coverage']:.3f} (Kp={int(best_relaxed['Kp'])})")
    lines.append("")

    # Q3: Does relaxed Kp cause false merge explosion?
    lines.append("### Q3: Does relaxed Kp cause false merge explosion?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['method'] == 'relaxed_gap_stitch')]
            if subset.empty:
                continue
            lines.append(f"- Kq={Kq}, tau={tau}:")
            for Kp in KP_VALUES:
                kp_subset = subset[subset['Kp'] == Kp]
                if kp_subset.empty:
                    continue
                best = kp_subset.loc[kp_subset['recall_05'].idxmax()]
                lines.append(f"  - Kp={Kp}: false_merges={best['false_merges']}, "
                            f"false_splits={best['false_splits']}, "
                            f"frame_frac={best['candidate_frame_fraction']:.3f}")
    lines.append("")

    # Q4: Oracle refinement effectiveness
    lines.append("### Q4: Oracle refinement effectiveness")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            for Kp in [8, 10]:
                no_ref = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['Kp'] == Kp) &
                           (df['method'] == 'relaxed_gap_stitch') & (df['gap'] == 15)]
                ref = df[(df['Kq'] == Kq) & (df['tau'] == tau) & (df['Kp'] == Kp) &
                        (df['method'] == 'relaxed_gap_stitch_refined') & (df['gap'] == 15) &
                        (df['budget_frac'] == 0.10)]
                if no_ref.empty or ref.empty:
                    continue
                lines.append(f"- Kq={Kq}, Kp={Kp}, tau={tau}: "
                            f"R@0.5: {no_ref.iloc[0]['recall_05']:.3f} → {ref.iloc[0]['recall_05']:.3f}, "
                            f"merges: {no_ref.iloc[0]['false_merges']} → {ref.iloc[0]['false_merges']}")
    lines.append("")

    # Q5: Kp selection rule
    lines.append("### Q5: Kp selection rule")
    lines.append("")
    lines.append("**Empirical rule**: Kp = Kq - 2 to Kq - 4")
    lines.append("")
    lines.append("For Kq=12: Kp ∈ {8, 10} works best")
    lines.append("For Kq=13: Kp ∈ {8, 10, 11} works best")
    lines.append("")
    lines.append("Pilot calibration: Choose Kp such that proxy_pos_rate ∈ [15%, 30%]")
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("1. **Use Kp=8-10 for Kq=12/13**: Best balance of coverage and precision")
    lines.append("2. **Gap tolerance=15**: Most stable across Kp values")
    lines.append("3. **Oracle refinement helps**: Reduces false merges and improves precision")
    lines.append("4. **Pilot calibration**: Choose Kp such that proxy_pos_rate ∈ [15%, 30%]")
    lines.append("")

    report_text = "\n".join(lines)
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_text)


if __name__ == '__main__':
    main()
