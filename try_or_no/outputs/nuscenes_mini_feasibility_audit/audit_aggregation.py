"""
Audit: Check if the issue is in evaluate_instance or aggregate_metrics.

Key hypothesis: instances with 0 GT clips get clip_f1=0 in evaluate_instance,
which drags down the mean in aggregate_metrics.
"""

import csv
import json
import os
from collections import defaultdict

import numpy as np

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
FEAS_DIR = os.path.join(os.path.dirname(AUDIT_DIR), "nuscenes_mini_feasibility")
TABLE_PATH = os.path.join(FEAS_DIR, "real_3d_query_table.csv")
CLIPS_PATH = os.path.join(FEAS_DIR, "ground_truth_clips.jsonl")


def load_query_table():
    rows = []
    with open(TABLE_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["id"] = int(row["id"])
            row["timestamp"] = int(row["timestamp"])
            row["in_fov_label"] = int(row["in_fov_label"])
            row["within_30m_label"] = int(row["within_30m_label"])
            row["ego_front_label"] = int(row["ego_front_label"])
            row["is_valid"] = int(row["is_valid"])
            rows.append(row)
    return rows


def build_instance_sequences(rows):
    instance_rows = defaultdict(list)
    for row in rows:
        instance_rows[row["instance_token"]].append(row)
    sequences = {}
    for instance_token, irows in instance_rows.items():
        irows.sort(key=lambda r: r["timestamp"])
        sequences[instance_token] = irows
    return sequences


def build_clips_for_sequence(irows, label_key, tau):
    clips = []
    run_start = None
    run_length = 0
    for i, row in enumerate(irows):
        if row[label_key] == 1:
            if run_start is None:
                run_start = i
                run_length = 1
            else:
                run_length += 1
        else:
            if run_start is not None and run_length >= tau:
                clips.append((run_start, run_start + run_length - 1, run_length))
            run_start = None
            run_length = 0
    if run_start is not None and run_length >= tau:
        clips.append((run_start, run_start + run_length - 1, run_length))
    return clips


def evaluate_instance_v1(predicted, labels, gt_clips, tau):
    """Original evaluate_instance from v2 code."""
    n = len(labels)

    tp_f = sum(1 for p, l in zip(predicted, labels) if p == 1 and l == 1)
    fp_f = sum(1 for p, l in zip(predicted, labels) if p == 1 and l == 0)
    fn_f = sum(1 for p, l in zip(predicted, labels) if p == 0 and l == 1)

    frame_prec = tp_f / (tp_f + fp_f) if (tp_f + fp_f) > 0 else 0
    frame_rec = tp_f / (tp_f + fn_f) if (tp_f + fn_f) > 0 else 0

    # Build predicted clips
    pred_clips = []
    run_start = None
    run_len = 0
    for i, p in enumerate(predicted):
        if p == 1:
            if run_start is None:
                run_start = i
                run_len = 1
            else:
                run_len += 1
        else:
            if run_start is not None and run_len >= tau:
                pred_clips.append((run_start, run_start + run_len - 1, run_len))
            run_start = None
            run_len = 0
    if run_start is not None and run_len >= tau:
        pred_clips.append((run_start, run_start + run_len - 1, run_len))

    gt_intervals = [(c[0], c[1]) for c in gt_clips]
    tp_c = 0
    ious = []
    boundary_errors = []

    for ps, pe, _ in pred_clips:
        best_iou = 0
        best_gt = None
        for gs, ge in gt_intervals:
            inter = max(0, min(pe, ge) - max(ps, gs) + 1)
            union = max(pe, ge) - min(ps, gs) + 1
            iou = inter / union if union > 0 else 0
            if iou > best_iou:
                best_iou = iou
                best_gt = (gs, ge)
        if best_iou > 0.3:
            tp_c += 1
            ious.append(best_iou)
            if best_gt:
                boundary_errors.append(abs(ps - best_gt[0]))
                boundary_errors.append(abs(pe - best_gt[1]))

    fp_c = len(pred_clips) - tp_c
    fn_c = len(gt_intervals) - tp_c

    clip_prec = tp_c / len(pred_clips) if pred_clips else 0
    clip_rec = tp_c / len(gt_intervals) if gt_intervals else 0
    clip_f1 = 2 * clip_prec * clip_rec / (clip_prec + clip_rec) if (clip_prec + clip_rec) > 0 else 0

    return {
        "clip_recall": clip_rec,
        "clip_precision": clip_prec,
        "clip_f1": clip_f1,
        "mean_iou": np.mean(ious) if ious else 0,
        "n_pred_clips": len(pred_clips),
        "n_gt_clips": len(gt_intervals),
        "n_matched": tp_c,
    }


def main():
    print("=" * 60)
    print("AUDIT: Aggregation Analysis")
    print("=" * 60)

    rows = load_query_table()
    sequences = build_instance_sequences(rows)

    query_name, label_key = "within_30m", "within_30m_label"
    tau = 3

    # Count instances with/without clips
    n_with_clips = 0
    n_without_clips = 0
    n_skipped = 0
    instance_metrics_with = []
    instance_metrics_without = []

    for instance_token, irows in sequences.items():
        n = len(irows)
        if n < tau:
            n_skipped += 1
            continue

        labels = [r[label_key] for r in irows]
        gt_clips = build_clips_for_sequence(irows, label_key, tau)
        predicted = labels[:]  # naive_oracle

        metrics = evaluate_instance_v1(predicted, labels, gt_clips, tau)

        if len(gt_clips) > 0:
            n_with_clips += 1
            instance_metrics_with.append(metrics)
        else:
            n_without_clips += 1
            instance_metrics_without.append(metrics)

    print(f"Instances with clips: {n_with_clips}")
    print(f"Instances without clips: {n_without_clips}")
    print(f"Instances skipped (n < tau): {n_skipped}")

    # Metrics for instances WITH clips
    if instance_metrics_with:
        avg_f1_with = np.mean([m["clip_f1"] for m in instance_metrics_with])
        avg_rec_with = np.mean([m["clip_recall"] for m in instance_metrics_with])
        print(f"\nInstances WITH clips:")
        print(f"  avg clip_f1: {avg_f1_with:.4f}")
        print(f"  avg clip_recall: {avg_rec_with:.4f}")

    # Metrics for instances WITHOUT clips
    if instance_metrics_without:
        avg_f1_without = np.mean([m["clip_f1"] for m in instance_metrics_without])
        avg_rec_without = np.mean([m["clip_recall"] for m in instance_metrics_without])
        print(f"\nInstances WITHOUT clips:")
        print(f"  avg clip_f1: {avg_f1_without:.4f}")
        print(f"  avg clip_recall: {avg_rec_without:.4f}")
        # Check: what does evaluate_instance return when there are no GT clips and no pred clips?
        print(f"  Sample metrics (first 5):")
        for m in instance_metrics_without[:5]:
            print(f"    {m}")

    # Overall average (this is what the code does)
    all_metrics = instance_metrics_with + instance_metrics_without
    avg_f1_all = np.mean([m["clip_f1"] for m in all_metrics])
    avg_rec_all = np.mean([m["clip_recall"] for m in all_metrics])
    print(f"\nAll instances (what code computes):")
    print(f"  avg clip_f1: {avg_f1_all:.4f}")
    print(f"  avg clip_recall: {avg_rec_all:.4f}")

    # What it SHOULD be (only instances with clips)
    print(f"\nIf we only average over instances WITH clips:")
    print(f"  avg clip_f1: {avg_f1_with:.4f}")
    print(f"  avg clip_recall: {avg_rec_with:.4f}")

    # Verify: for instances with clips, naive_oracle should give f1=1.0
    print(f"\nVerification: instances with clips should have f1=1.0")
    f1_values = [m["clip_f1"] for m in instance_metrics_with]
    print(f"  min f1: {min(f1_values):.4f}")
    print(f"  max f1: {max(f1_values):.4f}")
    print(f"  all == 1.0: {all(abs(f - 1.0) < 0.001 for f in f1_values)}")


if __name__ == "__main__":
    main()
