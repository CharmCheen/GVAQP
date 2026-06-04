"""
Build ground-truth clips and run baseline smoke test (v2).
Fixed: per-instance evaluation to avoid cross-instance index mismatch.
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
            rows.append(row)
    return rows


def build_instance_sequences(rows):
    """Group rows by instance, sorted by timestamp."""
    instance_rows = defaultdict(list)
    for row in rows:
        instance_rows[row["instance_token"]].append(row)

    sequences = {}
    for instance_token, irows in instance_rows.items():
        irows.sort(key=lambda r: r["timestamp"])
        sequences[instance_token] = irows
    return sequences


def build_clips_for_sequence(irows, label_key, tau):
    """Build clips for a single instance sequence."""
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
                clips.append({
                    "start_local": run_start,
                    "end_local": run_start + run_length - 1,
                    "length": run_length,
                    "start_id": irows[run_start]["id"],
                    "end_id": irows[run_start + run_length - 1]["id"],
                })
            run_start = None
            run_length = 0

    if run_start is not None and run_length >= tau:
        clips.append({
            "start_local": run_start,
            "end_local": run_start + run_length - 1,
            "length": run_length,
            "start_id": irows[run_start]["id"],
            "end_id": irows[run_start + run_length - 1]["id"],
        })

    return clips


def build_predicted_clips(predicted_labels, tau):
    """Build predicted clips from a binary label sequence."""
    clips = []
    run_start = None
    run_len = 0

    for i, p in enumerate(predicted_labels):
        if p == 1:
            if run_start is None:
                run_start = i
                run_len = 1
            else:
                run_len += 1
        else:
            if run_start is not None and run_len >= tau:
                clips.append((run_start, run_start + run_len - 1, run_len))
            run_start = None
            run_len = 0

    if run_start is not None and run_len >= tau:
        clips.append((run_start, run_start + run_len - 1, run_len))

    return clips


def evaluate_instance(predicted, labels, gt_clips, tau):
    """Evaluate clip-level metrics for a single instance."""
    n = len(labels)

    # Frame-level
    tp_f = sum(1 for p, l in zip(predicted, labels) if p == 1 and l == 1)
    fp_f = sum(1 for p, l in zip(predicted, labels) if p == 1 and l == 0)
    fn_f = sum(1 for p, l in zip(predicted, labels) if p == 0 and l == 1)
    tn_f = sum(1 for p, l in zip(predicted, labels) if p == 0 and l == 0)

    frame_prec = tp_f / (tp_f + fp_f) if (tp_f + fp_f) > 0 else 0
    frame_rec = tp_f / (tp_f + fn_f) if (tp_f + fn_f) > 0 else 0

    # Build predicted clips
    pred_clips = build_predicted_clips(predicted, tau)

    # Match predicted clips to GT clips
    gt_intervals = [(c["start_local"], c["end_local"]) for c in gt_clips]
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
        "boundary_error_samples": np.mean(boundary_errors) if boundary_errors else 0,
        "frame_recall": frame_rec,
        "frame_precision": frame_prec,
        "n_pred_clips": len(pred_clips),
        "n_gt_clips": len(gt_intervals),
        "n_matched": tp_c,
    }


def aggregate_metrics(instance_metrics):
    """Aggregate per-instance metrics."""
    n = len(instance_metrics)
    if n == 0:
        return {k: 0 for k in ["clip_recall", "clip_precision", "clip_f1", "mean_iou",
                                 "boundary_error_samples", "frame_recall", "frame_precision"]}

    result = {}
    for key in ["clip_recall", "clip_precision", "clip_f1", "mean_iou",
                 "boundary_error_samples", "frame_recall", "frame_precision"]:
        vals = [m[key] for m in instance_metrics]
        result[key] = round(np.mean(vals), 4)
    return result


def main():
    print("Loading query table...")
    rows = load_query_table()
    print(f"Loaded {len(rows)} rows")

    sequences = build_instance_sequences(rows)
    print(f"Instances: {len(sequences)}")

    queries = [
        ("in_fov", "in_fov_label"),
        ("within_30m", "within_30m_label"),
        ("ego_front", "ego_front_label"),
    ]
    tau_values = [2, 3, 5]
    seeds = [42, 123, 456, 789, 101112]

    # Build all GT clips
    all_clips = []
    clip_id = 0
    for instance_token, irows in sequences.items():
        scene_name = irows[0]["scene_name"]
        for query_name, label_key in queries:
            for tau in tau_values:
                clips = build_clips_for_sequence(irows, label_key, tau)
                for c in clips:
                    c["clip_id"] = clip_id
                    c["instance_token"] = instance_token
                    c["scene_name"] = scene_name
                    c["query"] = query_name
                    c["tau"] = tau
                    all_clips.append(c)
                    clip_id += 1

    # Write clips
    clips_path = os.path.join(OUTPUT_DIR, "ground_truth_clips.jsonl")
    with open(clips_path, "w") as f:
        for clip in all_clips:
            f.write(json.dumps(clip) + "\n")
    print(f"Wrote {len(all_clips)} clips to {clips_path}")

    # Compute query stats
    stats = []
    for query_name, label_key in queries:
        n_positive = sum(1 for r in rows if r[label_key] == 1)
        pos_rate = n_positive / len(rows) if rows else 0
        n_instances = len(set(r["instance_token"] for r in rows if r[label_key] == 1))
        n_scenes = len(set(r["scene_name"] for r in rows if r[label_key] == 1))

        for tau in tau_values:
            tau_clips = [c for c in all_clips if c["query"] == query_name and c["tau"] == tau]
            lengths = [c["length"] for c in tau_clips]
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
    results = []

    for query_name, label_key in queries:
        for tau in tau_values:
            for seed in seeds:
                rng = np.random.RandomState(seed)

                # Collect per-instance metrics for each method
                method_results = {
                    "naive_oracle": [],
                    "fixed_rate_k2": [],
                    "fixed_rate_k3": [],
                    "fixed_rate_k5": [],
                    "linear_interp": [],
                    "const_vel_k5": [],
                }

                for instance_token, irows in sequences.items():
                    n = len(irows)
                    if n < tau:
                        continue

                    labels = [r[label_key] for r in irows]
                    gt_clips = build_clips_for_sequence(irows, label_key, tau)

                    # B0: naive_oracle
                    predicted = labels[:]
                    method_results["naive_oracle"].append(
                        evaluate_instance(predicted, labels, gt_clips, tau))

                    # B1: fixed_rate_k
                    for k in [2, 3, 5]:
                        predicted = []
                        oracle_calls = 0
                        last_label = 0
                        for i in range(n):
                            if i % k == 0:
                                last_label = labels[i]
                                oracle_calls += 1
                            predicted.append(last_label)
                        method_results[f"fixed_rate_k{k}"].append(
                            evaluate_instance(predicted, labels, gt_clips, tau))

                    # B2: linear interpolation
                    k_lin = max(2, n // 3)
                    observed = set(range(0, n, k_lin))
                    if n - 1 not in observed:
                        observed.add(n - 1)
                    predicted = []
                    oracle_calls = 0
                    for i in range(n):
                        if i in observed:
                            predicted.append(labels[i])
                            oracle_calls += 1
                        else:
                            nearest = min(observed, key=lambda x: abs(x - i))
                            predicted.append(labels[nearest])
                    method_results["linear_interp"].append(
                        evaluate_instance(predicted, labels, gt_clips, tau))

                    # B3: constant velocity
                    k_cv = 5
                    predicted = []
                    oracle_calls = 0
                    last_label = labels[0]
                    oracle_calls += 1
                    predicted.append(last_label)
                    for i in range(1, n):
                        if i % k_cv == 0:
                            last_label = labels[i]
                            oracle_calls += 1
                        predicted.append(last_label)
                    method_results["const_vel_k5"].append(
                        evaluate_instance(predicted, labels, gt_clips, tau))

                # Aggregate and record results
                total_rows = sum(len(sequences[it]) for it in sequences)
                for method_name, instance_metrics in method_results.items():
                    agg = aggregate_metrics(instance_metrics)

                    # Compute total oracle calls
                    if method_name == "naive_oracle":
                        oracle_calls = total_rows
                    elif method_name == "fixed_rate_k2":
                        oracle_calls = sum(1 for it in sequences for i in range(len(sequences[it])) if i % 2 == 0)
                    elif method_name == "fixed_rate_k3":
                        oracle_calls = sum(1 for it in sequences for i in range(len(sequences[it])) if i % 3 == 0)
                    elif method_name == "fixed_rate_k5":
                        oracle_calls = sum(1 for it in sequences for i in range(len(sequences[it])) if i % 5 == 0)
                    elif method_name == "linear_interp":
                        oracle_calls = sum(max(2, len(sequences[it]) // 3) for it in sequences)
                    elif method_name == "const_vel_k5":
                        oracle_calls = sum(1 + len(sequences[it]) // 5 for it in sequences)
                    else:
                        oracle_calls = total_rows

                    results.append({
                        "method": method_name,
                        "query": query_name,
                        "tau": tau,
                        "seed": seed,
                        "oracle_calls": oracle_calls,
                        "oracle_call_ratio": round(oracle_calls / total_rows, 4),
                        **agg,
                    })

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
    print(f"\nWrote {len(results)} results to {results_path}")

    # Print summary
    print("\n=== Baseline Summary (averaged over seeds) ===")
    for query_name, _ in queries:
        for tau in tau_values:
            print(f"\n{query_name}, tau={tau}:")
            print(f"  {'Method':<20} {'ClipF1':>8} {'ClipRec':>8} {'ClipPre':>8} {'FrRec':>8} {'Oracle%':>8}")
            query_results = [r for r in results if r["query"] == query_name and r["tau"] == tau]
            methods = list(dict.fromkeys(r["method"] for r in query_results))
            for method in methods:
                mrs = [r for r in query_results if r["method"] == method]
                avg_f1 = np.mean([r["clip_f1"] for r in mrs])
                avg_rec = np.mean([r["clip_recall"] for r in mrs])
                avg_prec = np.mean([r["clip_precision"] for r in mrs])
                avg_fr = np.mean([r["frame_recall"] for r in mrs])
                avg_or = np.mean([r["oracle_call_ratio"] for r in mrs])
                print(f"  {method:<20} {avg_f1:>8.4f} {avg_rec:>8.4f} {avg_prec:>8.4f} {avg_fr:>8.4f} {avg_or:>8.2%}")


if __name__ == "__main__":
    main()
