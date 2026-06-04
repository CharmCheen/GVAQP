"""
Perturbation ablation study: run each perturbation type in isolation
to determine which causes the main failure in clip-level metrics.

Usage:
    cd /qiuyeqing/llama_prl/G-ARC/try_or_no
    conda run -n garc python outputs/audit/agent_d/run_ablation.py
"""

import csv
import json
import pathlib
import sys

import numpy as np

# Add project root to path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.data_interface import load_or_generate_dataset
from pipeline.clip_gt import build_ground_truth_clips
from pipeline.perturbation import PerturbationConfig, perturb_video
from pipeline.baselines import (
    full_oracle_baseline,
    fixed_rate_sampling_baseline,
    uniform_random_sampling_baseline,
    proxy_threshold_baseline,
    arc_temporal_clustering_baseline,
)
from pipeline.metrics import compute_experiment_metrics, ExperimentMetrics

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
NUM_VIDEOS = 50
NUM_FRAMES = 300
K = 3
TAU = 30
BUDGET = 0.1
OUTPUT_DIR = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Ablation configs: each isolates a single perturbation type
# ---------------------------------------------------------------------------
ABLATION_CONFIGS = {
    "clean": PerturbationConfig(
        proxy_noise_std=0.0,
        gap_probability=0.0,
        gap_max_length=5,
        boundary_jitter_std=0.0,
        visibility_drop_prob=0.0,
        visibility_drop_length=10,
        visibility_drop_scale=0.3,
    ),
    "proxy_noise_only": PerturbationConfig(
        proxy_noise_std=1.5,
        gap_probability=0.0,
        gap_max_length=5,
        boundary_jitter_std=0.0,
        visibility_drop_prob=0.0,
        visibility_drop_length=10,
        visibility_drop_scale=0.3,
    ),
    "short_positive_gaps_only": PerturbationConfig(
        proxy_noise_std=0.0,
        gap_probability=0.05,
        gap_max_length=5,
        boundary_jitter_std=0.0,
        visibility_drop_prob=0.0,
        visibility_drop_length=10,
        visibility_drop_scale=0.3,
    ),
    "boundary_jitter_only": PerturbationConfig(
        proxy_noise_std=0.0,
        gap_probability=0.0,
        gap_max_length=5,
        boundary_jitter_std=3.0,
        visibility_drop_prob=0.0,
        visibility_drop_length=10,
        visibility_drop_scale=0.3,
    ),
    "visibility_drop_only": PerturbationConfig(
        proxy_noise_std=0.0,
        gap_probability=0.0,
        gap_max_length=5,
        boundary_jitter_std=0.0,
        visibility_drop_prob=0.02,
        visibility_drop_length=10,
        visibility_drop_scale=0.3,
    ),
    "all_perturbations": PerturbationConfig(),  # all defaults
}

METHODS = [
    "full_oracle",
    "fixed_rate",
    "uniform_random",
    "proxy_threshold",
    "arc_clustering",
]


def run_baseline(method_name, perturbed, K, tau, budget, rng):
    """Dispatch to the appropriate baseline method."""
    if method_name == "full_oracle":
        return full_oracle_baseline(perturbed, K=K, tau=tau)
    elif method_name == "fixed_rate":
        return fixed_rate_sampling_baseline(
            perturbed, K=K, tau=tau, sample_rate=budget, rng=rng
        )
    elif method_name == "uniform_random":
        return uniform_random_sampling_baseline(
            perturbed, K=K, tau=tau, budget=budget, rng=rng
        )
    elif method_name == "proxy_threshold":
        return proxy_threshold_baseline(
            perturbed, K=K, tau=tau, budget=budget, rng=rng
        )
    elif method_name == "arc_clustering":
        return arc_temporal_clustering_baseline(
            perturbed, K=K, tau=tau, budget=budget, rng=rng
        )
    else:
        raise ValueError(f"Unknown method: {method_name}")


def main():
    print("=" * 70)
    print("PERTURBATION ABLATION STUDY")
    print("=" * 70)
    print(f"  Videos: {NUM_VIDEOS}, Frames: {NUM_FRAMES}, K: {K}, tau: {TAU}")
    print(f"  Budget: {BUDGET}, Seed: {SEED}")
    print(f"  Configs: {list(ABLATION_CONFIGS.keys())}")
    print(f"  Methods: {METHODS}")
    print()

    # 1. Generate dataset (shared across all configs for fair comparison)
    print("[1/4] Generating synthetic dataset...")
    videos = load_or_generate_dataset(
        annotation_dir=None,
        sample_size=NUM_VIDEOS,
        num_frames=NUM_FRAMES,
        seed=SEED,
    )
    print(f"  Generated {len(videos)} videos")

    # 2. Run each ablation config
    print("[2/4] Running ablation experiments...")
    all_metrics = []       # flat list for CSV/JSONL
    per_config_results = {}  # config_name -> list of ExperimentMetrics

    for config_name, config in ABLATION_CONFIGS.items():
        print(f"\n  --- {config_name} ---")
        config_metrics = []

        for i, video in enumerate(videos):
            # Per-video RNG for reproducibility
            video_rng = np.random.default_rng(SEED + i)

            # Build ground truth
            gt_clips = build_ground_truth_clips(video, K=K, tau=TAU)
            gt_clip_ranges = [(c.start_frame, c.end_frame) for c in gt_clips]
            gt_frame_labels = (video.frame_counts() >= K).astype(bool)

            # Apply perturbation
            perturbed = perturb_video(
                video, K=K, config=config, rng=video_rng,
                boundary_clips=gt_clip_ranges,
            )

            # Run each baseline method
            for method_name in METHODS:
                method_rng = np.random.default_rng(SEED + i + hash(method_name) % 10000)
                baseline = run_baseline(
                    method_name, perturbed, K=K, tau=TAU, budget=BUDGET, rng=method_rng
                )

                metrics = compute_experiment_metrics(
                    video_id=video.video_id,
                    method=method_name,
                    gt_frame_labels=gt_frame_labels,
                    pred_frame_labels=baseline.frame_labels,
                    gt_clips=gt_clip_ranges,
                    pred_clips=baseline.predicted_clips,
                    oracle_calls=baseline.oracle_calls,
                    total_frames=len(gt_frame_labels),
                )
                # Tag with ablation config name
                record = metrics.to_dict()
                record["ablation_config"] = config_name
                config_metrics.append(metrics)
                all_metrics.append(record)

            if (i + 1) % 10 == 0:
                print(f"    Processed {i + 1}/{len(videos)} videos")

        per_config_results[config_name] = config_metrics
        print(f"  Completed {config_name}: {len(config_metrics)} metric records")

    # 3. Compute summary statistics per config and method
    print("\n[3/4] Computing summary statistics...")

    def summarize(metrics_list):
        """Compute mean metrics over a list of ExperimentMetrics."""
        n = len(metrics_list)
        if n == 0:
            return {}
        return {
            "frame_recall": np.mean([m.frame_recall for m in metrics_list]),
            "frame_precision": np.mean([m.frame_precision for m in metrics_list]),
            "clip_recall": np.mean([m.clip_recall for m in metrics_list]),
            "clip_precision": np.mean([m.clip_precision for m in metrics_list]),
            "mean_iou": np.mean([m.mean_iou for m in metrics_list]),
            "mean_start_error": np.mean([
                m.mean_start_error for m in metrics_list
                if m.mean_start_error != float('inf')
            ]),
            "mean_end_error": np.mean([
                m.mean_end_error for m in metrics_list
                if m.mean_end_error != float('inf')
            ]),
            "fragmentation_rate": np.mean([m.fragmentation_rate for m in metrics_list]),
            "oracle_calls": np.mean([m.oracle_calls for m in metrics_list]),
        }

    # Group by (config, method)
    summary_table = {}
    for config_name in ABLATION_CONFIGS:
        summary_table[config_name] = {}
        for method in METHODS:
            subset = [m for m in per_config_results[config_name] if m.method == method]
            summary_table[config_name][method] = summarize(subset)

    # Compute deltas relative to clean baseline
    delta_table = {}
    for config_name in ABLATION_CONFIGS:
        if config_name == "clean":
            continue
        delta_table[config_name] = {}
        for method in METHODS:
            clean_stats = summary_table["clean"][method]
            perturbed_stats = summary_table[config_name][method]
            delta = {}
            for metric in ["frame_recall", "clip_recall", "mean_iou",
                           "mean_start_error", "mean_end_error", "fragmentation_rate"]:
                if metric in ["mean_start_error", "mean_end_error"]:
                    delta[f"{metric}_increase"] = (
                        perturbed_stats.get(metric, 0) - clean_stats.get(metric, 0)
                    )
                elif metric == "fragmentation_rate":
                    delta[f"{metric}_increase"] = (
                        perturbed_stats.get(metric, 0) - clean_stats.get(metric, 0)
                    )
                else:
                    delta[f"{metric}_drop"] = (
                        clean_stats.get(metric, 0) - perturbed_stats.get(metric, 0)
                    )
            delta_table[config_name][method] = delta

    # 4. Write outputs
    print("[4/4] Writing outputs...")

    # --- CSV ---
    csv_path = OUTPUT_DIR / "perturbation_ablation.csv"
    if all_metrics:
        fieldnames = list(all_metrics[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_metrics:
                writer.writerow(row)
    print(f"  Wrote {csv_path}")

    # --- JSONL ---
    jsonl_path = OUTPUT_DIR / "perturbation_ablation.jsonl"
    with open(jsonl_path, "w") as f:
        for row in all_metrics:
            # Replace inf with null for JSON compatibility
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, float) and (v == float('inf') or v == float('-inf')):
                    clean_row[k] = None
                else:
                    clean_row[k] = v
            f.write(json.dumps(clean_row) + "\n")
    print(f"  Wrote {jsonl_path}")

    # --- Summary JSON for the report ---
    summary_json_path = OUTPUT_DIR / "ablation_summary.json"
    summary_export = {
        "config": {
            "seed": SEED,
            "num_videos": NUM_VIDEOS,
            "num_frames": NUM_FRAMES,
            "K": K,
            "tau": TAU,
            "budget": BUDGET,
        },
        "summary_table": {
            cfg: {
                method: {k: round(float(v), 6) for k, v in stats.items()}
                for method, stats in methods.items()
            }
            for cfg, methods in summary_table.items()
        },
        "delta_table": {
            cfg: {
                method: {k: round(float(v), 6) for k, v in deltas.items()}
                for method, deltas in methods.items()
            }
            for cfg, methods in delta_table.items()
        },
    }
    with open(summary_json_path, "w") as f:
        json.dump(summary_export, f, indent=2)
    print(f"  Wrote {summary_json_path}")

    # --- Print summary to stdout ---
    print("\n" + "=" * 70)
    print("ABLATION SUMMARY")
    print("=" * 70)

    for method in METHODS:
        print(f"\n--- Method: {method} ---")
        print(f"{'Config':<30} {'FrameRec':>10} {'ClipRec':>10} {'mIoU':>10} {'FragRate':>10}")
        print("-" * 70)
        for config_name in ABLATION_CONFIGS:
            s = summary_table[config_name][method]
            print(f"{config_name:<30} {s['frame_recall']:>10.4f} {s['clip_recall']:>10.4f} "
                  f"{s['mean_iou']:>10.4f} {s['fragmentation_rate']:>10.4f}")

    print("\n--- Deltas relative to CLEAN (clip_recall_drop) ---")
    for method in METHODS:
        if method == "full_oracle":
            continue
        print(f"\n  Method: {method}")
        for config_name in delta_table:
            d = delta_table[config_name][method]
            print(f"    {config_name:<30} clip_recall_drop={d.get('clip_recall_drop', 0):.4f}  "
                  f"frame_recall_drop={d.get('frame_recall_drop', 0):.4f}  "
                  f"frag_increase={d.get('fragmentation_rate_increase', 0):.4f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
