"""Clean control experiment: run all baselines on unperturbed synthetic sequences.

Generates 20 synthetic videos with seed=42, applies identity perturbation (zero noise),
and runs all 5 baselines to verify they behave correctly before perturbation is applied.
"""

import json
import sys
import os
import numpy as np

# Ensure the project root is on the path
sys.path.insert(0, "/qiuyeqing/llama_prl/G-ARC/try_or_no")

from pipeline.data_interface import load_or_generate_dataset
from pipeline.perturbation import PerturbedSequence, PerturbationConfig, perturb_video
from pipeline.baselines import (
    full_oracle_baseline,
    fixed_rate_sampling_baseline,
    uniform_random_sampling_baseline,
    proxy_threshold_baseline,
    arc_temporal_clustering_baseline,
)
from pipeline.metrics import compute_experiment_metrics
from pipeline.report import write_metrics_csv

# ── Configuration ──────────────────────────────────────────────────────────
SEED = 42
NUM_VIDEOS = 20
NUM_FRAMES = 300
K = 3          # minimum vehicle count for positive frame
TAU = 30       # minimum consecutive frames for a clip
BUDGET = 0.1   # oracle budget fraction for non-oracle baselines

OUTPUT_DIR = "/qiuyeqing/llama_prl/G-ARC/try_or_no/outputs/audit/agent_b"
METRICS_CSV = os.path.join(OUTPUT_DIR, "clean_control_metrics.csv")
RESULTS_JSONL = os.path.join(OUTPUT_DIR, "clean_control.jsonl")

# ── Step 1: Generate synthetic dataset ─────────────────────────────────────
print("=" * 70)
print("CLEAN CONTROL EXPERIMENT")
print("=" * 70)
print(f"\nGenerating {NUM_VIDEOS} synthetic videos (seed={SEED}, num_frames={NUM_FRAMES})...")

videos = load_or_generate_dataset(
    annotation_dir=None,
    sample_size=NUM_VIDEOS,
    num_frames=NUM_FRAMES,
    seed=SEED,
)
print(f"Generated {len(videos)} videos.")

# ── Step 2: Create clean perturbed sequences ──────────────────────────────
print("\nCreating clean (identity) perturbed sequences...")

clean_config = PerturbationConfig(
    proxy_noise_std=0.0,
    gap_probability=0.0,
    boundary_jitter_std=0.0,
    visibility_drop_prob=0.0,
)

all_metrics = []
jsonl_records = []
verification_issues = []

for vi, video in enumerate(videos):
    rng = np.random.default_rng(SEED + vi)  # deterministic per video

    # Apply identity perturbation
    perturbed = perturb_video(
        video=video,
        K=K,
        config=clean_config,
        rng=rng,
        boundary_clips=None,  # no boundary clips -> no jitter
    )

    # Verify clean perturbation: original_labels should equal perturbed_labels
    if not np.array_equal(perturbed.original_labels, perturbed.perturbed_labels):
        verification_issues.append(
            f"Video {video.video_id}: perturbed_labels != original_labels "
            f"(mismatches: {np.sum(perturbed.original_labels != perturbed.perturbed_labels)})"
        )
    if not np.array_equal(perturbed.original_counts, perturbed.perturbed_counts):
        verification_issues.append(
            f"Video {video.video_id}: perturbed_counts != original_counts"
        )
    if perturbed.num_oracle_calls != 0:
        verification_issues.append(
            f"Video {video.video_id}: num_oracle_calls={perturbed.num_oracle_calls}, expected 0"
        )

    # Build ground truth clips from original labels
    from pipeline.clip_gt import build_ground_truth_clips
    gt_clips_raw = build_ground_truth_clips(video, K=K, tau=TAU)
    gt_clips = [(c.start_frame, c.end_frame) for c in gt_clips_raw]

    # ── Step 3: Run all 5 baselines ────────────────────────────────────────
    baseline_rng = np.random.default_rng(SEED + 1000 + vi)

    baselines = [
        ("full_oracle", lambda: full_oracle_baseline(perturbed, K, TAU)),
        ("fixed_rate", lambda: fixed_rate_sampling_baseline(
            perturbed, K, TAU, sample_rate=BUDGET, rng=np.random.default_rng(SEED + 2000 + vi)
        )),
        ("uniform_random", lambda: uniform_random_sampling_baseline(
            perturbed, K, TAU, budget=BUDGET, rng=np.random.default_rng(SEED + 3000 + vi)
        )),
        ("proxy_threshold", lambda: proxy_threshold_baseline(
            perturbed, K, TAU, budget=BUDGET, rng=np.random.default_rng(SEED + 4000 + vi)
        )),
        ("arc_clustering", lambda: arc_temporal_clustering_baseline(
            perturbed, K, TAU, budget=BUDGET, rng=np.random.default_rng(SEED + 5000 + vi)
        )),
    ]

    video_record = {"video_id": video.video_id, "baselines": {}}

    for method_name, run_baseline in baselines:
        result = run_baseline()

        # Compute metrics
        metrics = compute_experiment_metrics(
            video_id=video.video_id,
            method=method_name,
            gt_frame_labels=perturbed.original_labels,
            pred_frame_labels=result.frame_labels,
            gt_clips=gt_clips,
            pred_clips=result.predicted_clips,
            oracle_calls=result.oracle_calls,
            total_frames=NUM_FRAMES,
        )
        all_metrics.append(metrics)
        video_record["baselines"][method_name] = metrics.to_dict()

    jsonl_records.append(video_record)

    if (vi + 1) % 5 == 0:
        print(f"  Processed {vi + 1}/{len(videos)} videos...")

# ── Step 4: Save results ──────────────────────────────────────────────────
print(f"\nSaving metrics to {METRICS_CSV}")
write_metrics_csv(all_metrics, METRICS_CSV)

print(f"Saving per-video results to {RESULTS_JSONL}")
with open(RESULTS_JSONL, "w") as f:
    for rec in jsonl_records:
        f.write(json.dumps(rec) + "\n")

# ── Step 5: Verify expected behavior ──────────────────────────────────────
print("\n" + "=" * 70)
print("VERIFICATION RESULTS")
print("=" * 70)

# Group metrics by method
from collections import defaultdict
method_metrics = defaultdict(list)
for m in all_metrics:
    method_metrics[m.method].append(m)

print("\nPer-method summary (mean across videos):")
print(f"{'Method':<20} {'FrameRec':>10} {'FramePrec':>10} {'ClipRec':>10} {'ClipPrec':>10} {'IoU':>8} {'FragRate':>8} {'OracleFrac':>10}")
print("-" * 90)

method_stats = {}
for method in ["full_oracle", "fixed_rate", "uniform_random", "proxy_threshold", "arc_clustering"]:
    metrics_list = method_metrics[method]
    n = len(metrics_list)
    stats = {
        "frame_recall": sum(m.frame_recall for m in metrics_list) / n,
        "frame_precision": sum(m.frame_precision for m in metrics_list) / n,
        "clip_recall": sum(m.clip_recall for m in metrics_list) / n,
        "clip_precision": sum(m.clip_precision for m in metrics_list) / n,
        "mean_iou": sum(m.mean_iou for m in metrics_list) / n,
        "fragmentation_rate": sum(m.fragmentation_rate for m in metrics_list) / n,
        "oracle_fraction": sum(m.oracle_fraction for m in metrics_list) / n,
    }
    method_stats[method] = stats
    print(
        f"{method:<20} {stats['frame_recall']:>10.4f} {stats['frame_precision']:>10.4f} "
        f"{stats['clip_recall']:>10.4f} {stats['clip_precision']:>10.4f} "
        f"{stats['mean_iou']:>8.4f} {stats['fragmentation_rate']:>8.4f} "
        f"{stats['oracle_fraction']:>10.4f}"
    )

# Check expected behaviors
print("\n" + "-" * 70)
print("BEHAVIORAL CHECKS")
print("-" * 70)

# Check 1: full_oracle should have frame_recall ~ 1.0 and clip_recall ~ 1.0
oracle_stats = method_stats["full_oracle"]
if oracle_stats["frame_recall"] >= 0.999 and oracle_stats["clip_recall"] >= 0.999:
    print("[PASS] full_oracle: frame_recall={:.4f}, clip_recall={:.4f} (expected ~1.0)".format(
        oracle_stats["frame_recall"], oracle_stats["clip_recall"]))
else:
    msg = "[FAIL] full_oracle: frame_recall={:.4f}, clip_recall={:.4f} (expected ~1.0)".format(
        oracle_stats["frame_recall"], oracle_stats["clip_recall"])
    print(msg)
    verification_issues.append(msg)

# Check 2: fixed_rate should have high frame_recall
fr_stats = method_stats["fixed_rate"]
if fr_stats["frame_recall"] >= 0.80:
    print("[PASS] fixed_rate: frame_recall={:.4f} (expected high on clean data)".format(
        fr_stats["frame_recall"]))
else:
    msg = "[WARN] fixed_rate: frame_recall={:.4f} (lower than expected)".format(
        fr_stats["frame_recall"])
    print(msg)
    verification_issues.append(msg)

# Check 3: uniform_random should have reasonable performance
ur_stats = method_stats["uniform_random"]
if ur_stats["frame_recall"] >= 0.50:
    print("[PASS] uniform_random: frame_recall={:.4f} (expected reasonable)".format(
        ur_stats["frame_recall"]))
else:
    msg = "[WARN] uniform_random: frame_recall={:.4f} (lower than expected)".format(
        ur_stats["frame_recall"])
    print(msg)
    verification_issues.append(msg)

# Check 4: proxy_threshold should be near-perfect on clean data
pt_stats = method_stats["proxy_threshold"]
if pt_stats["frame_recall"] >= 0.95 and pt_stats["clip_recall"] >= 0.90:
    print("[PASS] proxy_threshold: frame_recall={:.4f}, clip_recall={:.4f} (expected near-perfect)".format(
        pt_stats["frame_recall"], pt_stats["clip_recall"]))
else:
    msg = "[WARN] proxy_threshold: frame_recall={:.4f}, clip_recall={:.4f} (lower than expected near-perfect)".format(
        pt_stats["frame_recall"], pt_stats["clip_recall"])
    print(msg)
    verification_issues.append(msg)

# Check 5: arc_clustering should be near-perfect on clean data
ac_stats = method_stats["arc_clustering"]
if ac_stats["frame_recall"] >= 0.95 and ac_stats["clip_recall"] >= 0.90:
    print("[PASS] arc_clustering: frame_recall={:.4f}, clip_recall={:.4f} (expected near-perfect)".format(
        ac_stats["frame_recall"], ac_stats["clip_recall"]))
else:
    msg = "[WARN] arc_clustering: frame_recall={:.4f}, clip_recall={:.4f} (lower than expected near-perfect)".format(
        ac_stats["frame_recall"], ac_stats["clip_recall"])
    print(msg)
    verification_issues.append(msg)

# Perturbation identity check
if verification_issues:
    print("\n[ISSUES FOUND]")
    for issue in verification_issues:
        print(f"  - {issue}")
else:
    print("\n[ALL CHECKS PASSED] No anomalies detected.")

print("\n" + "=" * 70)
print("EXPERIMENT COMPLETE")
print(f"Results saved to: {OUTPUT_DIR}")
print("=" * 70)
