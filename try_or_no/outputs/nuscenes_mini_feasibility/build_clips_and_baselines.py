"""
Build ground-truth clips and run baseline smoke test.
"""

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLE_PATH = os.path.join(OUTPUT_DIR, "real_3d_query_table.csv")


def load_query_table():
    """Load the query table."""
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
            row["obj_distance_to_ego"] = float(row["obj_distance_to_ego"])
            row["obj_rel_x_ego"] = float(row["obj_rel_x_ego"])
            row["obj_rel_y_ego"] = float(row["obj_rel_y_ego"])
            row["projected_depth"] = float(row["projected_depth"])
            rows.append(row)
    return rows


def build_clips(rows, queries, tau_values):
    """Build ground-truth clips per instance and query."""
    # Group by instance
    instance_rows = defaultdict(list)
    for row in rows:
        instance_rows[row["instance_token"]].append(row)

    clips = []
    clip_id = 0

    for instance_token, irows in instance_rows.items():
        # Sort by timestamp
        irows.sort(key=lambda r: r["timestamp"])
        scene_name = irows[0]["scene_name"]

        for query_name, label_key in queries:
            for tau in tau_values:
                # Find runs of positive labels
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
                            clips.append({
                                "clip_id": clip_id,
                                "instance_token": instance_token,
                                "scene_name": scene_name,
                                "query": query_name,
                                "tau": tau,
                                "start_idx": irows[run_start]["id"],
                                "end_idx": irows[run_start + run_length - 1]["id"],
                                "start_timestamp": irows[run_start]["timestamp"],
                                "end_timestamp": irows[run_start + run_length - 1]["timestamp"],
                                "length_samples": run_length,
                            })
                            clip_id += 1
                        run_start = None
                        run_length = 0

                # Handle run at end
                if run_start is not None and run_length >= tau:
                    clips.append({
                        "clip_id": clip_id,
                        "instance_token": instance_token,
                        "scene_name": scene_name,
                        "query": query_name,
                        "tau": tau,
                        "start_idx": irows[run_start]["id"],
                        "end_idx": irows[run_start + run_length - 1]["id"],
                        "start_timestamp": irows[run_start]["timestamp"],
                        "end_timestamp": irows[run_start + run_length - 1]["timestamp"],
                        "length_samples": run_length,
                    })
                    clip_id += 1

    return clips


def compute_query_stats(rows, clips, queries, tau_values):
    """Compute query statistics."""
    stats = []
    for query_name, label_key in queries:
        n_positive = sum(1 for r in rows if r[label_key] == 1)
        pos_rate = n_positive / len(rows) if rows else 0
        n_instances = len(set(r["instance_token"] for r in rows if r[label_key] == 1))
        n_scenes = len(set(r["scene_name"] for r in rows if r[label_key] == 1))

        for tau in tau_values:
            tau_clips = [c for c in clips if c["query"] == query_name and c["tau"] == tau]
            lengths = [c["length_samples"] for c in tau_clips]
            avg_len = np.mean(lengths) if lengths else 0
            med_len = np.median(lengths) if lengths else 0

            stats.append({
                "query_name": query_name,
                "tau": tau,
                "num_positive_records": n_positive,
                "positive_rate": round(pos_rate, 4),
                "num_clips": len(tau_clips),
                "avg_clip_length_samples": round(avg_len, 2),
                "median_clip_length_samples": round(med_len, 2),
                "num_instances": n_instances,
                "num_scenes": n_scenes,
            })
    return stats


def run_baselines(rows, clips, queries, tau_values, seeds=[42, 123, 456, 789, 101112]):
    """Run minimal baselines."""
    # Group rows by instance
    instance_rows = defaultdict(list)
    for row in rows:
        instance_rows[row["instance_token"]].append(row)

    results = []

    for query_name, label_key in queries:
        for tau in tau_values:
            tau_clips = [c for c in clips if c["query"] == query_name and c["tau"] == tau]

            for seed in seeds:
                rng = np.random.RandomState(seed)

                # B0: naive_oracle - use every sample
                all_labels = []
                all_predicted = []
                for instance_token, irows in instance_rows.items():
                    irows_sorted = sorted(irows, key=lambda r: r["timestamp"])
                    labels = [r[label_key] for r in irows_sorted]
                    all_labels.extend(labels)
                    all_predicted.extend(labels)  # perfect oracle

                naive_metrics = evaluate(all_predicted, all_labels, tau_clips, len(rows))
                results.append({
                    "method": "naive_oracle", "query": query_name, "tau": tau, "seed": seed,
                    "oracle_calls": len(rows), "oracle_call_ratio": 1.0,
                    **naive_metrics,
                })

                # B1: fixed_rate_k
                for k in [2, 3, 5]:
                    predicted = []
                    oracle_calls = 0
                    for instance_token, irows in instance_rows.items():
                        irows_sorted = sorted(irows, key=lambda r: r["timestamp"])
                        last_label = 0
                        for i, row in enumerate(irows_sorted):
                            if i % k == 0:
                                last_label = row[label_key]
                                oracle_calls += 1
                            predicted.append(last_label)

                    metrics = evaluate(predicted, [r[label_key] for r in rows], tau_clips, len(rows))
                    results.append({
                        "method": f"fixed_rate_k{k}", "query": query_name, "tau": tau, "seed": seed,
                        "oracle_calls": oracle_calls, "oracle_call_ratio": oracle_calls / len(rows),
                        **metrics,
                    })

                # B2: linear_interpolation (between keyframes)
                predicted = []
                oracle_calls = 0
                for instance_token, irows in instance_rows.items():
                    irows_sorted = sorted(irows, key=lambda r: r["timestamp"])
                    n = len(irows_sorted)
                    if n == 0:
                        continue
                    if n == 1:
                        predicted.append(irows_sorted[0][label_key])
                        oracle_calls += 1
                        continue

                    # Observe at start and end, interpolate position
                    # For discrete labels, we just hold the nearest observed value
                    k = max(2, n // 3)  # observe ~1/3 of samples
                    observed_indices = set(range(0, n, k))
                    if n - 1 not in observed_indices:
                        observed_indices.add(n - 1)

                    for i in range(n):
                        if i in observed_indices:
                            predicted.append(irows_sorted[i][label_key])
                            oracle_calls += 1
                        else:
                            # Find nearest observed
                            nearest = min(observed_indices, key=lambda x: abs(x - i))
                            predicted.append(irows_sorted[nearest][label_key])

                metrics = evaluate(predicted, [r[label_key] for r in rows], tau_clips, len(rows))
                results.append({
                    "method": "linear_interp", "query": query_name, "tau": tau, "seed": seed,
                    "oracle_calls": oracle_calls, "oracle_call_ratio": oracle_calls / len(rows),
                    **metrics,
                })

                # B3: constant_velocity (hold last value + position extrapolation)
                predicted = []
                oracle_calls = 0
                for instance_token, irows in instance_rows.items():
                    irows_sorted = sorted(irows, key=lambda r: r["timestamp"])
                    n = len(irows_sorted)
                    if n == 0:
                        continue

                    k = 5  # observe every 5 samples
                    last_label = irows_sorted[0][label_key]
                    oracle_calls += 1
                    predicted.append(last_label)

                    for i in range(1, n):
                        if i % k == 0:
                            last_label = irows_sorted[i][label_key]
                            oracle_calls += 1
                        predicted.append(last_label)

                metrics = evaluate(predicted, [r[label_key] for r in rows], tau_clips, len(rows))
                results.append({
                    "method": "const_vel_k5", "query": query_name, "tau": tau, "seed": seed,
                    "oracle_calls": oracle_calls, "oracle_call_ratio": oracle_calls / len(rows),
                    **metrics,
                })

    return results


def evaluate(predicted, labels, gt_clips, n_total):
    """Evaluate clip-level and frame-level metrics."""
    # Frame-level
    tp_f = sum(1 for p, l in zip(predicted, labels) if p == 1 and l == 1)
    fp_f = sum(1 for p, l in zip(predicted, labels) if p == 1 and l == 0)
    fn_f = sum(1 for p, l in zip(predicted, labels) if p == 0 and l == 1)
    tn_f = sum(1 for p, l in zip(predicted, labels) if p == 0 and l == 0)

    frame_prec = tp_f / (tp_f + fp_f) if (tp_f + fp_f) > 0 else 0
    frame_rec = tp_f / (tp_f + fn_f) if (tp_f + fn_f) > 0 else 0

    # Build predicted clips
    tau = gt_clips[0]["tau"] if gt_clips else 5
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

    # Match predicted clips to GT clips
    gt_intervals = [(c["start_idx"], c["end_idx"]) for c in gt_clips]
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
        "clip_recall": round(clip_rec, 4),
        "clip_precision": round(clip_prec, 4),
        "clip_f1": round(clip_f1, 4),
        "mean_iou": round(np.mean(ious), 4) if ious else 0,
        "boundary_error_samples": round(np.mean(boundary_errors), 2) if boundary_errors else 0,
        "frame_recall": round(frame_rec, 4),
        "frame_precision": round(frame_prec, 4),
    }


def main():
    print("Loading query table...")
    rows = load_query_table()
    print(f"Loaded {len(rows)} rows")

    queries = [
        ("in_fov", "in_fov_label"),
        ("within_30m", "within_30m_label"),
        ("ego_front", "ego_front_label"),
    ]
    tau_values = [2, 3, 5]

    # Build clips
    print("Building clips...")
    clips = build_clips(rows, queries, tau_values)
    print(f"Built {len(clips)} clips")

    # Write clips
    clips_path = os.path.join(OUTPUT_DIR, "ground_truth_clips.jsonl")
    with open(clips_path, "w") as f:
        for clip in clips:
            f.write(json.dumps(clip) + "\n")
    print(f"Wrote clips to {clips_path}")

    # Compute query stats
    print("Computing query stats...")
    stats = compute_query_stats(rows, clips, queries, tau_values)
    stats_path = os.path.join(OUTPUT_DIR, "query_stats.csv")
    with open(stats_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=stats[0].keys())
        writer.writeheader()
        writer.writerows(stats)
    print(f"Wrote stats to {stats_path}")

    for s in stats:
        print(f"  {s['query_name']}, tau={s['tau']}: "
              f"{s['num_clips']} clips, {s['positive_rate']:.2%} positive, "
              f"avg_len={s['avg_clip_length_samples']:.1f}")

    # Run baselines
    print("\nRunning baselines...")
    results = run_baselines(rows, clips, queries, tau_values)
    print(f"Generated {len(results)} baseline results")

    # Write results
    results_path = os.path.join(OUTPUT_DIR, "baseline_smoke_metrics.csv")
    fieldnames = [
        "method", "query", "tau", "seed", "oracle_calls", "oracle_call_ratio",
        "clip_recall", "clip_precision", "clip_f1", "mean_iou",
        "boundary_error_samples", "frame_recall", "frame_precision",
    ]
    with open(results_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote results to {results_path}")

    # Print summary
    print("\n=== Baseline Summary ===")
    for query_name, _ in queries:
        for tau in tau_values:
            print(f"\n{query_name}, tau={tau}:")
            print(f"  {'Method':<20} {'ClipF1':>8} {'ClipRec':>8} {'Oracle%':>8} {'FrRec':>8}")
            for r in results:
                if r["query"] == query_name and r["tau"] == tau:
                    print(f"  {r['method']:<20} {r['clip_f1']:>8.4f} {r['clip_recall']:>8.4f} "
                          f"{r['oracle_call_ratio']:>8.2%} {r['frame_recall']:>8.4f}")


if __name__ == "__main__":
    main()
