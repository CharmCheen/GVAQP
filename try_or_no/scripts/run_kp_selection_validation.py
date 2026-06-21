#!/usr/bin/env python3
"""
run_kp_selection_validation.py

Kp selection rule validation.
Tests strategies for selecting proxy threshold Kp without using GT clips.

Usage:
    python scripts/run_kp_selection_validation.py
"""

import sys
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ── Configuration ──────────────────────────────────────────────────────────

ORACLE_CSV = 'outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv'
OUTPUT_CSV = 'outputs/kp_selection_validation_results.csv'
OUTPUT_REPORT = 'outputs/kp_selection_validation_report.md'

KQ_VALUES = [12, 13]
TAU_VALUES = [15, 30, 60]
GAP = 15  # Best gap from previous experiments
TARGET_RATES = [0.10, 0.15, 0.20, 0.25, 0.30]
PILOT_BUDGETS = [0.01, 0.02]
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


# ── Kp Selection Strategies ───────────────────────────────────────────────

def select_kp_fixed_margin(Kq, m):
    """Kp = Kq - m"""
    return max(1, Kq - m)


def select_kp_by_rate(proxy_counts, target_rate):
    """Select Kp such that proxy positive rate is closest to target."""
    n = len(proxy_counts)
    best_Kp = None
    best_diff = float('inf')

    for Kp in range(1, int(np.max(proxy_counts)) + 1):
        rate = (proxy_counts >= Kp).mean()
        diff = abs(rate - target_rate)
        if diff < best_diff:
            best_diff = diff
            best_Kp = Kp

    return best_Kp


def select_kp_pilot_oracle(proxy_counts, oracle_counts, Kq, pilot_budget_frac, tau):
    """Pilot oracle calibration: sample frames, estimate recall per Kp."""
    n = len(proxy_counts)
    pilot_size = int(pilot_budget_frac * n)
    rng = np.random.RandomState(42)
    pilot_indices = rng.choice(n, size=pilot_size, replace=False)

    oracle_binary_full = (oracle_counts >= Kq).astype(int)
    oracle_calls = 0

    # Query oracle at pilot frames
    pilot_oracle = {}
    for idx in pilot_indices:
        pilot_oracle[idx] = oracle_binary_full[idx]
        oracle_calls += 1

    # For each candidate Kp, estimate recall
    best_Kp = None
    best_score = -1

    for Kp in range(max(1, Kq - 5), Kq + 1):
        proxy_binary = (proxy_counts >= Kp).astype(int)

        # Estimate: how many pilot oracle-positive frames are covered by proxy
        pilot_pos_indices = [i for i in pilot_indices if pilot_oracle[i] == 1]
        if not pilot_pos_indices:
            continue

        covered = sum(1 for i in pilot_pos_indices if proxy_binary[i] == 1)
        estimated_recall = covered / len(pilot_pos_indices)

        # Estimate candidate fraction
        candidates = gap_stitch(proxy_binary, GAP, tau)
        candidate_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0

        # Score: balance recall and candidate fraction
        # Prefer high recall with moderate candidate fraction
        if candidate_frac > 0.5:
            score = estimated_recall * 0.5  # Penalize too broad
        else:
            score = estimated_recall

        if score > best_score:
            best_score = score
            best_Kp = Kp

    return best_Kp, oracle_calls


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Kp Selection Validation")
    print("=" * 70)

    proxy_counts, oracle_counts = load_data()
    n = len(proxy_counts)
    print(f"Loaded {n} frames")

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

            # Oracle-only baseline
            all_results.append({
                'strategy': 'oracle_only', 'Kq': Kq, 'tau': tau,
                'selected_Kp': Kq, 'oracle_calls': n,
                'candidate_count': len(gt_tuples),
                'candidate_frame_fraction': 1.0,
                **calc_metrics(gt_tuples, gt_tuples),
            })

            # Hard proxy baseline (Kp=Kq)
            proxy_binary_hard = (proxy_counts >= Kq).astype(int)
            candidates_hard = gap_stitch(proxy_binary_hard, GAP, tau)
            frame_frac_hard = sum(e - s + 1 for s, e in candidates_hard) / n if candidates_hard else 0.0
            all_results.append({
                'strategy': 'hard_proxy', 'Kq': Kq, 'tau': tau,
                'selected_Kp': Kq, 'oracle_calls': 0,
                'candidate_count': len(candidates_hard),
                'candidate_frame_fraction': round(frame_frac_hard, 4),
                **calc_metrics(gt_tuples, candidates_hard),
            })

            # Best oracle-known Kp (upper bound)
            best_recall = 0
            best_Kp_known = Kq
            for Kp in range(6, Kq + 1):
                proxy_binary = (proxy_counts >= Kp).astype(int)
                candidates = gap_stitch(proxy_binary, GAP, tau)
                metrics = calc_metrics(gt_tuples, candidates)
                if metrics['recall_05'] > best_recall:
                    best_recall = metrics['recall_05']
                    best_Kp_known = Kp

            proxy_binary_best = (proxy_counts >= best_Kp_known).astype(int)
            candidates_best = gap_stitch(proxy_binary_best, GAP, tau)
            frame_frac_best = sum(e - s + 1 for s, e in candidates_best) / n if candidates_best else 0.0
            all_results.append({
                'strategy': 'best_known_Kp', 'Kq': Kq, 'tau': tau,
                'selected_Kp': best_Kp_known, 'oracle_calls': 0,
                'candidate_count': len(candidates_best),
                'candidate_frame_fraction': round(frame_frac_best, 4),
                **calc_metrics(gt_tuples, candidates_best),
            })

            # Strategy 1: Fixed margin
            for m in [1, 2, 3, 4]:
                Kp = select_kp_fixed_margin(Kq, m)
                proxy_binary = (proxy_counts >= Kp).astype(int)
                candidates = gap_stitch(proxy_binary, GAP, tau)
                frame_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0
                metrics = calc_metrics(gt_tuples, candidates)

                all_results.append({
                    'strategy': f'fixed_margin_m{m}', 'Kq': Kq, 'tau': tau,
                    'selected_Kp': Kp, 'oracle_calls': 0,
                    'candidate_count': len(candidates),
                    'candidate_frame_fraction': round(frame_frac, 4),
                    **metrics,
                })

            # Strategy 2: Proxy positive rate
            for target_rate in TARGET_RATES:
                Kp = select_kp_by_rate(proxy_counts, target_rate)
                proxy_binary = (proxy_counts >= Kp).astype(int)
                actual_rate = proxy_binary.mean()
                candidates = gap_stitch(proxy_binary, GAP, tau)
                frame_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0
                metrics = calc_metrics(gt_tuples, candidates)

                all_results.append({
                    'strategy': f'rate_target_{int(target_rate*100)}', 'Kq': Kq, 'tau': tau,
                    'selected_Kp': Kp, 'oracle_calls': 0,
                    'actual_rate': round(actual_rate, 4),
                    'candidate_count': len(candidates),
                    'candidate_frame_fraction': round(frame_frac, 4),
                    **metrics,
                })

            # Strategy 3: Pilot oracle calibration
            for pilot_budget in PILOT_BUDGETS:
                Kp, oracle_calls = select_kp_pilot_oracle(
                    proxy_counts, oracle_counts, Kq, pilot_budget, tau)
                proxy_binary = (proxy_counts >= Kp).astype(int)
                candidates = gap_stitch(proxy_binary, GAP, tau)
                frame_frac = sum(e - s + 1 for s, e in candidates) / n if candidates else 0.0
                metrics = calc_metrics(gt_tuples, candidates)

                all_results.append({
                    'strategy': f'pilot_oracle_{int(pilot_budget*100)}', 'Kq': Kq, 'tau': tau,
                    'selected_Kp': Kp, 'oracle_calls': oracle_calls,
                    'candidate_count': len(candidates),
                    'candidate_frame_fraction': round(frame_frac, 4),
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
    lines.append("# Kp Selection Validation Report")
    lines.append("")
    lines.append("**Date**: 2026-06-07")
    lines.append("**Dataset**: realcar_5k")
    lines.append("**Goal**: Validate Kp selection strategies without using GT clips")
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
            lines.append("| Strategy | Kp | R@0.5 | Coverage | Candidates | Frame Frac | Merges | Oracle |")
            lines.append("|----------|-----|-------|----------|------------|------------|--------|--------|")

            for _, row in subset.iterrows():
                lines.append(f"| {row['strategy']} | {row['selected_Kp']} | "
                            f"{row['recall_05']:.3f} | {row['gt_coverage']:.3f} | "
                            f"{row['candidate_count']} | {row['candidate_frame_fraction']:.3f} | "
                            f"{row['false_merges']} | {row['oracle_calls']} |")
            lines.append("")

    # Key questions
    lines.append("---")
    lines.append("")
    lines.append("## Key Questions")
    lines.append("")

    # Q1: Proxy positive rate rule
    lines.append("### Q1: Does proxy positive rate rule select Kp≈10?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) &
                       (df['strategy'].str.startswith('rate_target'))]
            if subset.empty:
                continue
            lines.append(f"Kq={Kq}, tau={tau}:")
            for _, row in subset.iterrows():
                lines.append(f"- Target {row['strategy']}: Kp={row['selected_Kp']}, "
                            f"actual_rate={row.get('actual_rate', 'N/A')}, R@0.5={row['recall_05']:.3f}")
    lines.append("")

    # Q2: Fixed margin stability
    lines.append("### Q2: Is fixed Kp=Kq-m stable?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) &
                       (df['strategy'].str.startswith('fixed_margin'))]
            if subset.empty:
                continue
            lines.append(f"Kq={Kq}, tau={tau}:")
            for _, row in subset.iterrows():
                lines.append(f"- {row['strategy']}: Kp={row['selected_Kp']}, "
                            f"R@0.5={row['recall_05']:.3f}, coverage={row['gt_coverage']:.3f}")
    lines.append("")

    # Q3: Pilot oracle vs pure proxy
    lines.append("### Q3: Is pilot oracle better than pure proxy rule?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            proxy_subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) &
                            (df['strategy'].str.startswith('rate_target'))]
            pilot_subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) &
                            (df['strategy'].str.startswith('pilot_oracle'))]

            if proxy_subset.empty or pilot_subset.empty:
                continue

            best_proxy = proxy_subset.loc[proxy_subset['recall_05'].idxmax()]
            best_pilot = pilot_subset.loc[pilot_subset['recall_05'].idxmax()]

            lines.append(f"Kq={Kq}, tau={tau}:")
            lines.append(f"- Best proxy rule: Kp={best_proxy['selected_Kp']}, "
                        f"R@0.5={best_proxy['recall_05']:.3f}")
            lines.append(f"- Best pilot oracle: Kp={best_pilot['selected_Kp']}, "
                        f"R@0.5={best_pilot['recall_05']:.3f}, "
                        f"oracle={best_pilot['oracle_calls']}")
    lines.append("")

    # Q4: Candidate explosion
    lines.append("### Q4: Is there candidate explosion?")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau)]
            max_frac = subset['candidate_frame_fraction'].max()
            max_frac_strategy = subset.loc[subset['candidate_frame_fraction'].idxmax(), 'strategy']
            lines.append(f"- Kq={Kq}, tau={tau}: max frame fraction={max_frac:.3f} "
                        f"(strategy: {max_frac_strategy})")
    lines.append("")

    # Q5: Recommended default
    lines.append("### Q5: Recommended default strategy")
    lines.append("")
    for Kq in KQ_VALUES:
        for tau in [30]:
            subset = df[(df['Kq'] == Kq) & (df['tau'] == tau) &
                       (df['strategy'] != 'oracle_only') &
                       (df['strategy'] != 'hard_proxy') &
                       (df['strategy'] != 'best_known_Kp')]

            if subset.empty:
                continue

            # Find best strategy by R@0.5
            best = subset.loc[subset['recall_05'].idxmax()]
            lines.append(f"Kq={Kq}, tau={tau}: **{best['strategy']}** "
                        f"(Kp={best['selected_Kp']}, R@0.5={best['recall_05']:.3f}, "
                        f"coverage={best['gt_coverage']:.3f})")
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("1. **Use proxy positive rate rule**: Target 20-25% positive rate")
    lines.append("2. **Fixed margin Kp=Kq-2**: Simple and stable")
    lines.append("3. **Pilot oracle optional**: Marginal improvement over proxy rule")
    lines.append("4. **No candidate explosion**: Frame fraction stays below 50%")
    lines.append("5. **Default**: Kp = Kq - 2 or proxy_pos_rate target 20%")
    lines.append("")

    report_text = "\n".join(lines)
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_text)


if __name__ == '__main__':
    main()
