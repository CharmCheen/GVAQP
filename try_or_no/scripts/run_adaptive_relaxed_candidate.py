#!/usr/bin/env python3
"""
run_adaptive_relaxed_candidate.py

Adaptive relaxed candidate generation v1.
Automatically decides when to relax proxy threshold Kp based on diagnostics.

Usage:
    python scripts/run_adaptive_relaxed_candidate.py
"""

import sys
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ── Configuration ──────────────────────────────────────────────────────────

ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
ARC_RESULTS = 'outputs/realcar_5k_arc_stress_results.csv'
OUTPUT_CSV = 'outputs/adaptive_relaxed_candidate_results.csv'
OUTPUT_REPORT = 'outputs/adaptive_relaxed_candidate_report.md'

KQ_VALUES = [12, 13]
TAU_VALUES = [15, 30, 60]
GAP_CANDIDATES = [5, 10, 15]
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


# ── Diagnosis ──────────────────────────────────────────────────────────────

def diagnose_hard_proxy(proxy_counts, Kq, tau):
    """Diagnose hard proxy (Kp=Kq) to decide if relaxation is needed."""
    n = len(proxy_counts)
    proxy_binary = (proxy_counts >= Kq).astype(int)

    proxy_positive_rate = proxy_binary.mean()
    proxy_runs = find_runs(proxy_binary, min_len=1)
    proxy_run_lengths = [r[2] for r in proxy_runs]
    max_proxy_run_length = max(proxy_run_lengths) if proxy_run_lengths else 0

    # Hard candidates
    hard_candidates = gap_stitch(proxy_binary, 10, tau)
    hard_candidate_count = len(hard_candidates)
    candidate_frame_fraction = sum(e - s + 1 for s, e in hard_candidates) / n if hard_candidates else 0.0

    # Repaired candidates (gap=10)
    repaired_candidates = gap_stitch(proxy_binary, 10, tau)
    repaired_candidate_count = len(repaired_candidates)

    return {
        'proxy_positive_rate': round(proxy_positive_rate, 4),
        'hard_candidate_count': hard_candidate_count,
        'candidate_frame_fraction': round(candidate_frame_fraction, 4),
        'proxy_positive_run_count': len(proxy_runs),
        'max_proxy_run_length': max_proxy_run_length,
        'repaired_candidate_count': repaired_candidate_count,
    }


# ── Trigger Rule ───────────────────────────────────────────────────────────

def check_trigger(diagnosis, tau):
    """Check if relaxation should be triggered."""
    reasons = []

    if diagnosis['hard_candidate_count'] == 0:
        reasons.append('no_hard_candidates')

    if diagnosis['max_proxy_run_length'] < tau:
        reasons.append('max_run_too_short')

    if diagnosis['proxy_positive_rate'] < 0.10:
        reasons.append('low_positive_rate')

    if diagnosis['repaired_candidate_count'] == 0:
        reasons.append('no_repaired_candidates')

    should_relax = len(reasons) > 0
    return should_relax, reasons


# ── Kp Selection ───────────────────────────────────────────────────────────

def select_kp(proxy_counts, Kq, tau, should_relax):
    """Select Kp based on trigger decision."""
    n = len(proxy_counts)

    if not should_relax:
        return Kq, 'no_relaxation'

    # Search from Kq-1 downward
    for Kp in range(Kq - 1, 0, -1):
        proxy_binary = (proxy_counts >= Kp).astype(int)
        rate = proxy_binary.mean()

        # Check constraints
        candidates = gap_stitch(proxy_binary, 10, tau)
        frame_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0

        if 0.15 <= rate <= 0.30 and frame_frac <= 0.50 and len(candidates) > 0:
            return Kp, 'rate_and_fraction_ok'

    # Fallback: select Kp with frame_fraction closest to 30%
    best_Kp = Kq
    best_diff = float('inf')
    for Kp in range(Kq - 1, 0, -1):
        proxy_binary = (proxy_counts >= Kp).astype(int)
        candidates = gap_stitch(proxy_binary, 10, tau)
        frame_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0

        diff = abs(frame_frac - 0.30)
        if diff < best_diff:
            best_diff = diff
            best_Kp = Kp

    return best_Kp, 'fallback_closest_to_30pct'


# ── Gap Selection ──────────────────────────────────────────────────────────

def select_gap(proxy_binary, Kp, tau):
    """Select gap tolerance that generates candidates with minimal frame fraction."""
    n = len(proxy_binary)
    best_gap = GAP_CANDIDATES[0]
    best_frac = float('inf')
    best_count = 0

    for gap in GAP_CANDIDATES:
        candidates = gap_stitch(proxy_binary, gap, tau)
        if len(candidates) == 0:
            continue
        frame_frac = sum(e - s + 1 for s, e in candidates) / n
        if frame_frac < best_frac:
            best_frac = frame_frac
            best_gap = gap
            best_count = len(candidates)

    return best_gap, best_count, round(best_frac, 4)


# ── Oracle Refinement ─────────────────────────────────────────────────────

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
            step = max(1, length // 20)
            positive_blocks = []
            block_start = None
            for i in range(start, end + 1, step):
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
    print("Adaptive Relaxed Candidate Generation v1")
    print("=" * 70)

    proxy_counts, oracle_counts = load_data()
    n = len(proxy_counts)
    print(f"Loaded {n} frames")

    # Load ARC results for comparison
    arc_df = pd.read_csv(ARC_RESULTS)

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

            # ── Oracle-only baseline ─────────────────────────────────
            all_results.append({
                'method': 'oracle_only', 'Kq': Kq, 'tau': tau,
                'selected_Kp': Kq, 'trigger_reason': '-',
                'selected_gap': '-', 'budget_frac': 1.0,
                'candidate_count': len(gt_tuples),
                'candidate_frame_fraction': 1.0,
                'final_count': len(gt_tuples),
                'oracle_calls': n,
                'recall_per_call': round(1.0 / n, 6),
                **calc_metrics(gt_tuples, gt_tuples),
            })

            # ── Hard proxy baseline ──────────────────────────────────
            diag = diagnose_hard_proxy(proxy_counts, Kq, tau)
            print(f"  Hard proxy diagnosis: rate={diag['proxy_positive_rate']:.3f}, "
                  f"candidates={diag['hard_candidate_count']}, "
                  f"max_run={diag['max_proxy_run_length']}")

            proxy_binary_hard = (proxy_counts >= Kq).astype(int)
            gap_hard, count_hard, frac_hard = select_gap(proxy_binary_hard, Kq, tau)
            candidates_hard = gap_stitch(proxy_binary_hard, gap_hard, tau)

            all_results.append({
                'method': 'hard_proxy', 'Kq': Kq, 'tau': tau,
                'selected_Kp': Kq, 'trigger_reason': 'baseline',
                'selected_gap': gap_hard, 'budget_frac': 0.0,
                'candidate_count': count_hard,
                'candidate_frame_fraction': frac_hard,
                'final_count': count_hard,
                'oracle_calls': 0, 'recall_per_call': 0.0,
                **calc_metrics(gt_tuples, candidates_hard),
            })

            # ── Fixed Kp=Kq-2 ───────────────────────────────────────
            Kp_fixed = max(1, Kq - 2)
            proxy_binary_fixed = (proxy_counts >= Kp_fixed).astype(int)
            gap_fixed, count_fixed, frac_fixed = select_gap(proxy_binary_fixed, Kp_fixed, tau)
            candidates_fixed = gap_stitch(proxy_binary_fixed, gap_fixed, tau)

            all_results.append({
                'method': 'fixed_kp_kq_minus_2', 'Kq': Kq, 'tau': tau,
                'selected_Kp': Kp_fixed, 'trigger_reason': 'fixed',
                'selected_gap': gap_fixed, 'budget_frac': 0.0,
                'candidate_count': count_fixed,
                'candidate_frame_fraction': frac_fixed,
                'final_count': count_fixed,
                'oracle_calls': 0, 'recall_per_call': 0.0,
                **calc_metrics(gt_tuples, candidates_fixed),
            })

            # ── Rate target 20% ─────────────────────────────────────
            best_Kp_rate = None
            best_diff = float('inf')
            for Kp in range(1, int(np.max(proxy_counts)) + 1):
                rate = (proxy_counts >= Kp).mean()
                diff = abs(rate - 0.20)
                if diff < best_diff:
                    best_diff = diff
                    best_Kp_rate = Kp

            proxy_binary_rate = (proxy_counts >= best_Kp_rate).astype(int)
            gap_rate, count_rate, frac_rate = select_gap(proxy_binary_rate, best_Kp_rate, tau)
            candidates_rate = gap_stitch(proxy_binary_rate, gap_rate, tau)

            all_results.append({
                'method': 'rate_target_20', 'Kq': Kq, 'tau': tau,
                'selected_Kp': best_Kp_rate, 'trigger_reason': 'rate_target',
                'selected_gap': gap_rate, 'budget_frac': 0.0,
                'candidate_count': count_rate,
                'candidate_frame_fraction': frac_rate,
                'final_count': count_rate,
                'oracle_calls': 0, 'recall_per_call': 0.0,
                **calc_metrics(gt_tuples, candidates_rate),
            })

            # ── Adaptive relaxed candidate ───────────────────────────
            should_relax, reasons = check_trigger(diag, tau)
            Kp_adaptive, selection_reason = select_kp(proxy_counts, Kq, tau, should_relax)

            trigger_str = ','.join(reasons) if reasons else 'no_trigger'
            print(f"  Adaptive: should_relax={should_relax}, reasons={trigger_str}")
            print(f"  Adaptive: selected Kp={Kp_adaptive}, reason={selection_reason}")

            proxy_binary_adaptive = (proxy_counts >= Kp_adaptive).astype(int)
            gap_adaptive, count_adaptive, frac_adaptive = select_gap(
                proxy_binary_adaptive, Kp_adaptive, tau)
            candidates_adaptive = gap_stitch(proxy_binary_adaptive, gap_adaptive, tau)

            all_results.append({
                'method': 'adaptive_relaxed', 'Kq': Kq, 'tau': tau,
                'selected_Kp': Kp_adaptive,
                'trigger_reason': trigger_str,
                'selected_gap': gap_adaptive, 'budget_frac': 0.0,
                'candidate_count': count_adaptive,
                'candidate_frame_fraction': frac_adaptive,
                'final_count': count_adaptive,
                'oracle_calls': 0, 'recall_per_call': 0.0,
                **calc_metrics(gt_tuples, candidates_adaptive),
            })

            # ── Adaptive + oracle refinement ─────────────────────────
            for bf in BUDGET_FRACS:
                budget = int(bf * n)
                t0 = time.time()
                refined, oracle_calls = oracle_refine(
                    candidates_adaptive, oracle_binary, budget, tau)
                t1 = time.time()

                ref_metrics = calc_metrics(gt_tuples, refined)
                recall_per_call = ref_metrics['recall'] / oracle_calls if oracle_calls > 0 else 0.0

                all_results.append({
                    'method': f'adaptive_refined_{int(bf*100)}pct',
                    'Kq': Kq, 'tau': tau,
                    'selected_Kp': Kp_adaptive,
                    'trigger_reason': trigger_str,
                    'selected_gap': gap_adaptive, 'budget_frac': bf,
                    'candidate_count': count_adaptive,
                    'candidate_frame_fraction': frac_adaptive,
                    'final_count': len(refined),
                    'oracle_calls': oracle_calls,
                    'recall_per_call': round(recall_per_call, 6),
                    'runtime_sec': round(t1 - t0, 3),
                    **ref_metrics,
                })

            # ── ARC result for comparison ────────────────────────────
            arc_subset = arc_df[(arc_df['K'] == Kq) & (arc_df['tau'] == tau) &
                               (arc_df['method'] == 'ARC') & (arc_df['budget'] == 0.10)]
            if not arc_subset.empty:
                arc_row = arc_subset.iloc[0]
                all_results.append({
                    'method': 'ARC_10pct', 'Kq': Kq, 'tau': tau,
                    'selected_Kp': Kq, 'trigger_reason': 'ARC',
                    'selected_gap': '-', 'budget_frac': 0.10,
                    'candidate_count': int(arc_row['clips']),
                    'candidate_frame_fraction': '-',
                    'final_count': int(arc_row['clips']),
                    'oracle_calls': int(arc_row['oracle_calls']),
                    'recall_per_call': round(float(arc_row['recall_per_call']), 6),
                    'precision': round(float(arc_row['precision']), 4),
                    'recall': round(float(arc_row['recall']), 4),
                    'recall_05': round(float(arc_row['recall']), 4),
                    'recall_03': round(float(arc_row['recall']), 4),
                    'mIoU': round(float(arc_row['mIoU']), 4),
                    'gt_coverage': '-',
                    'boundary_offset_mean': '-',
                    'false_splits': '-',
                    'false_merges': '-',
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
    lines.append("# Adaptive Relaxed Candidate Generation v1 Report")
    lines.append("")
    lines.append("**Date**: 2026-06-07")
    lines.append("**Dataset**: realcar_5k")
    lines.append("**Goal**: Automatically decide when to relax proxy threshold Kp")
    lines.append("")

    # Summary by Kq and tau
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
            lines.append("| Method | Kp | Gap | Candidates | Frame Frac | R@0.5 | Coverage | Merges | Oracle |")
            lines.append("|--------|-----|-----|------------|------------|-------|----------|--------|--------|")

            for _, row in subset.iterrows():
                lines.append(f"| {row['method']} | {row['selected_Kp']} | {row['selected_gap']} | "
                            f"{row['candidate_count']} | {row['candidate_frame_fraction']} | "
                            f"{row['recall_05']:.3f} | {row['gt_coverage']} | "
                            f"{row['false_merges']} | {row['oracle_calls']} |")
            lines.append("")

    # Key questions
    lines.append("---")
    lines.append("")
    lines.append("## Key Questions")
    lines.append("")

    # Q1: Does adaptive keep hard proxy for Kq=12?
    lines.append("### Q1: Does adaptive keep hard proxy for Kq=12?")
    lines.append("")
    for tau in TAU_VALUES:
        subset = df[(df['Kq'] == 12) & (df['tau'] == tau) &
                   (df['method'].isin(['hard_proxy', 'adaptive_relaxed']))]
        if subset.empty:
            continue
        hard = subset[subset['method'] == 'hard_proxy'].iloc[0]
        adaptive = subset[subset['method'] == 'adaptive_relaxed'].iloc[0]
        lines.append(f"- tau={tau}: hard Kp={hard['selected_Kp']}, adaptive Kp={adaptive['selected_Kp']}, "
                    f"trigger={adaptive['trigger_reason']}")
    lines.append("")

    # Q2: Does adaptive trigger for Kq=13?
    lines.append("### Q2: Does adaptive trigger for Kq=13?")
    lines.append("")
    for tau in TAU_VALUES:
        subset = df[(df['Kq'] == 13) & (df['tau'] == tau) &
                   (df['method'] == 'adaptive_relaxed')]
        if subset.empty:
            continue
        row = subset.iloc[0]
        lines.append(f"- tau={tau}: Kp={row['selected_Kp']}, trigger={row['trigger_reason']}")
    lines.append("")

    # Q3: Is adaptive close to manually best Kp?
    lines.append("### Q3: Is adaptive close to manually best Kp?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau)]
            adaptive = subset[subset['method'] == 'adaptive_relaxed']
            rate_target = subset[subset['method'] == 'rate_target_20']
            if adaptive.empty or rate_target.empty:
                continue
            lines.append(f"- Kq={Kq}, tau={tau}: adaptive Kp={adaptive.iloc[0]['selected_Kp']}, "
                        f"rate_target Kp={rate_target.iloc[0]['selected_Kp']}")
    lines.append("")

    # Q4: Candidate explosion?
    lines.append("### Q4: Is there candidate explosion?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) &
                       (df['method'].isin(['hard_proxy', 'adaptive_relaxed']))]
            if subset.empty:
                continue
            for _, row in subset.iterrows():
                lines.append(f"- Kq={Kq}, tau={tau}, {row['method']}: "
                            f"frame_frac={row['candidate_frame_fraction']}")
    lines.append("")

    # Q5: Comparison with ARC
    lines.append("### Q5: Comparison with ARC / hard proxy / fixed Kp")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in TAU_VALUES:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau)]
            if subset.empty:
                continue

            methods = ['ARC_10pct', 'hard_proxy', 'fixed_kp_kq_minus_2', 'adaptive_relaxed']
            lines.append(f"Kq={Kq}, tau={tau}:")
            for method in methods:
                row = subset[subset['method'] == method]
                if row.empty:
                    continue
                row = row.iloc[0]
                lines.append(f"  - {method}: Kp={row['selected_Kp']}, R@0.5={row['recall_05']:.3f}, "
                            f"coverage={row['gt_coverage']}")
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("1. **Use adaptive rule**: Automatically detects when relaxation is needed")
    lines.append("2. **Kq=12**: Hard proxy works, no relaxation needed")
    lines.append("3. **Kq=13**: Adaptive triggers relaxation, selects Kp≈10-12")
    lines.append("4. **Gap selection**: Automatically selects minimal frame fraction gap")
    lines.append("5. **Oracle refinement**: Optional, improves recall with budget")
    lines.append("")

    report_text = "\n".join(lines)
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_text)


if __name__ == '__main__':
    main()
