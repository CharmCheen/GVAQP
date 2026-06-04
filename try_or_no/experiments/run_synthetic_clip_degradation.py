"""
Main experiment runner for synthetic clip degradation analysis.

Usage:
    python -m experiments.run_synthetic_clip_degradation \
        --sample-size 20 \
        --K 3 \
        --tau 30 \
        --budget 0.1 \
        --output-dir outputs/smoke
"""

import argparse
import json
import pathlib
import sys

import numpy as np

# Add parent to path for module imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline.data_interface import load_or_generate_dataset, VideoAnnotation
from pipeline.clip_gt import build_ground_truth_clips, save_clips_jsonl
from pipeline.perturbation import PerturbationConfig, perturb_video
from pipeline.baselines import (
    full_oracle_baseline,
    fixed_rate_sampling_baseline,
    uniform_random_sampling_baseline,
    proxy_threshold_baseline,
    arc_temporal_clustering_baseline,
    BaselineResult,
)
from pipeline.metrics import compute_experiment_metrics, ExperimentMetrics
from pipeline.report import generate_report, write_metrics_csv


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run synthetic clip degradation experiment"
    )
    parser.add_argument("--sample-size", type=int, default=20, help="Number of videos")
    parser.add_argument("--K", type=int, default=3, help="Min vehicle count threshold")
    parser.add_argument("--tau", type=int, default=30, help="Min frames for a clip")
    parser.add_argument("--budget", type=float, default=0.1, help="Oracle budget fraction")
    parser.add_argument("--output-dir", type=str, default="outputs/smoke", help="Output directory")
    parser.add_argument("--num-frames", type=int, default=300, help="Frames per synthetic video")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--annotation-dir", type=str, default=None, help="Path to UA-DETRAC annotations")
    return parser.parse_args()


def run_single_video(
    video: VideoAnnotation,
    K: int,
    tau: int,
    budget: float,
    perturb_config: PerturbationConfig,
    rng: np.random.Generator,
) -> list[ExperimentMetrics]:
    """Run all baselines on a single video and return metrics."""
    # Build ground truth clips
    gt_clips = build_ground_truth_clips(video, K=K, tau=tau)
    gt_clip_ranges = [(c.start_frame, c.end_frame) for c in gt_clips]
    gt_frame_labels = (video.frame_counts() >= K).astype(bool)

    # Apply perturbation
    perturbed = perturb_video(
        video, K=K, config=perturb_config, rng=rng, boundary_clips=gt_clip_ranges
    )

    # Create perturbed VideoAnnotation for baselines that need it
    from pipeline.data_interface import FrameAnnotation
    perturbed_video = VideoAnnotation(
        video_id=video.video_id,
        frames=perturbed.perturbed_frame_annotations,
    )

    # Run baselines
    results = []

    # 1. Full oracle
    oracle_result = full_oracle_baseline(perturbed, K=K, tau=tau)
    results.append(("full_oracle", oracle_result))

    # 2. Fixed-rate sampling
    fixed_result = fixed_rate_sampling_baseline(
        perturbed, K=K, tau=tau, sample_rate=budget, rng=rng
    )
    results.append(("fixed_rate", fixed_result))

    # 3. Uniform random sampling
    random_result = uniform_random_sampling_baseline(
        perturbed, K=K, tau=tau, budget=budget, rng=rng
    )
    results.append(("uniform_random", random_result))

    # 4. Proxy-threshold
    proxy_result = proxy_threshold_baseline(
        perturbed, K=K, tau=tau, budget=budget, rng=rng
    )
    results.append(("proxy_threshold", proxy_result))

    # 5. ARC-style temporal clustering
    arc_result = arc_temporal_clustering_baseline(
        perturbed, K=K, tau=tau, budget=budget, rng=rng
    )
    results.append(("arc_clustering", arc_result))

    # Compute metrics for each baseline
    all_metrics = []
    for method_name, baseline in results:
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
        all_metrics.append(metrics)

    return all_metrics


def main():
    args = parse_args()
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Configuration:")
    print(f"  sample_size={args.sample_size}, K={args.K}, tau={args.tau}, budget={args.budget}")
    print(f"  output_dir={output_dir}")
    print()

    # Load or generate dataset
    print("Loading/generating dataset...")
    videos = load_or_generate_dataset(
        annotation_dir=args.annotation_dir,
        sample_size=args.sample_size,
        num_frames=args.num_frames,
        seed=args.seed,
    )
    print(f"  Loaded {len(videos)} videos")

    # Save ground truth clips
    gt_clips_path = output_dir / "ground_truth_clips.jsonl"
    all_gt_clips = []
    for video in videos:
        clips = build_ground_truth_clips(video, K=args.K, tau=args.tau)
        all_gt_clips.extend(clips)
    save_clips_jsonl(all_gt_clips, str(gt_clips_path))
    print(f"  Saved {len(all_gt_clips)} ground truth clips to {gt_clips_path}")

    # Perturbation config
    perturb_config = PerturbationConfig()

    # Run experiments
    print("\nRunning experiments...")
    all_metrics = []
    per_video_results = []

    rng = np.random.default_rng(args.seed)

    for i, video in enumerate(videos):
        print(f"  [{i+1}/{len(videos)}] {video.video_id}")
        video_rng = np.random.default_rng(args.seed + i)

        video_metrics = run_single_video(
            video=video,
            K=args.K,
            tau=args.tau,
            budget=args.budget,
            perturb_config=perturb_config,
            rng=video_rng,
        )
        all_metrics.extend(video_metrics)

        # Store per-video summary
        per_video_results.append({
            "video_id": video.video_id,
            "num_frames": video.num_frames,
            "gt_clips": len(build_ground_truth_clips(video, K=args.K, tau=args.tau)),
            "metrics": [m.to_dict() for m in video_metrics],
        })

    # Write outputs
    print("\nWriting outputs...")

    # metrics.csv
    metrics_csv_path = output_dir / "metrics.csv"
    write_metrics_csv(all_metrics, str(metrics_csv_path))
    print(f"  {metrics_csv_path}")

    # per_video_results.jsonl
    per_video_path = output_dir / "per_video_results.jsonl"
    with open(per_video_path, "w") as f:
        for result in per_video_results:
            f.write(json.dumps(result) + "\n")
    print(f"  {per_video_path}")

    # Report
    report_path = output_dir / "report.md"
    config = {
        "sample_size": args.sample_size,
        "K": args.K,
        "tau": args.tau,
        "budget": args.budget,
    }
    report = generate_report(all_metrics, str(report_path), config)
    print(f"  {report_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)
    print(report)


if __name__ == "__main__":
    main()
