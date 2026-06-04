"""Diagnostic script for synthetic clip degradation metrics audit.

Generates 20 synthetic videos (seed=42, num_frames=300), runs all baselines
with K=3, tau=30, budget=0.1, and reports detailed statistics.
"""

import json
import sys
import pathlib

import numpy as np

# Add project root to path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# outputs/audit/agent_a -> outputs/audit -> outputs -> project root
# But that's only 3 levels which gives us 'outputs/'. We need 4 levels for project root:
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
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
from pipeline.metrics import compute_clip_metrics, compute_frame_metrics


def main():
    seed = 42
    num_frames = 300
    K = 3
    tau = 30
    budget = 0.1
    iou_threshold = 0.5
    sample_size = 20

    # Generate videos
    videos = load_or_generate_dataset(
        annotation_dir=None,
        sample_size=sample_size,
        num_frames=num_frames,
        seed=seed,
    )

    perturb_config = PerturbationConfig()
    all_diagnostics = []

    for i, video in enumerate(videos):
        video_rng = np.random.default_rng(seed + i)

        # Ground truth
        gt_clips = build_ground_truth_clips(video, K=K, tau=tau)
        gt_clip_ranges = [(c.start_frame, c.end_frame) for c in gt_clips]
        gt_frame_labels = (video.frame_counts() >= K).astype(bool)

        # Perturbation
        perturbed = perturb_video(
            video, K=K, config=perturb_config, rng=video_rng,
            boundary_clips=gt_clip_ranges,
        )

        # GT clip statistics
        gt_clip_lengths = [e - s + 1 for s, e in gt_clip_ranges]
        num_gt_positive_frames = int(np.sum(gt_frame_labels))
        num_perturbed_diff = int(np.sum(perturbed.perturbed_labels != perturbed.original_labels))

        video_diag = {
            "video_id": video.video_id,
            "num_frames": num_frames,
            "num_gt_clips": len(gt_clips),
            "gt_clip_lengths": gt_clip_lengths,
            "avg_gt_clip_length": float(np.mean(gt_clip_lengths)) if gt_clip_lengths else 0.0,
            "num_gt_positive_frames": num_gt_positive_frames,
            "perturbed_label_diffs": num_perturbed_diff,
            "perturbation_oracle_calls": perturbed.num_oracle_calls,
            "baselines": {},
        }

        # Run each baseline
        baselines = {
            "full_oracle": lambda: full_oracle_baseline(perturbed, K=K, tau=tau),
            "fixed_rate": lambda: fixed_rate_sampling_baseline(
                perturbed, K=K, tau=tau, sample_rate=budget, rng=np.random.default_rng(seed + i)
            ),
            "uniform_random": lambda: uniform_random_sampling_baseline(
                perturbed, K=K, tau=tau, budget=budget, rng=np.random.default_rng(seed + i)
            ),
            "proxy_threshold": lambda: proxy_threshold_baseline(
                perturbed, K=K, tau=tau, budget=budget, rng=np.random.default_rng(seed + i)
            ),
            "arc_clustering": lambda: arc_temporal_clustering_baseline(
                perturbed, K=K, tau=tau, budget=budget, rng=np.random.default_rng(seed + i)
            ),
        }

        for method_name, baseline_fn in baselines.items():
            result = baseline_fn()
            pred_clips = result.predicted_clips
            pred_clip_lengths = [e - s + 1 for s, e in pred_clips]

            clip_metrics = compute_clip_metrics(gt_clip_ranges, pred_clips, iou_threshold=iou_threshold)
            frame_recall, frame_precision = compute_frame_metrics(gt_frame_labels, result.frame_labels)

            expected_budget = max(1, int(num_frames * budget))
            actual_budget_used = result.oracle_calls

            video_diag["baselines"][method_name] = {
                "num_predicted_clips": len(pred_clips),
                "pred_clip_lengths": pred_clip_lengths,
                "avg_pred_clip_length": float(np.mean(pred_clip_lengths)) if pred_clip_lengths else 0.0,
                "num_matched_clips": clip_metrics["num_matched"],
                "iou_threshold_used": iou_threshold,
                "oracle_calls": result.oracle_calls,
                "expected_budget": expected_budget if method_name != "full_oracle" else num_frames,
                "budget_used_fraction": actual_budget_used / num_frames,
                "clip_recall": clip_metrics["clip_recall"],
                "clip_precision": clip_metrics["clip_precision"],
                "mean_iou": clip_metrics["mean_iou"],
                "mean_start_error": clip_metrics["mean_start_error"],
                "mean_end_error": clip_metrics["mean_end_error"],
                "fragmentation_rate": clip_metrics["fragmentation_rate"],
                "frame_recall": frame_recall,
                "frame_precision": frame_precision,
            }

        all_diagnostics.append(video_diag)

    # Summary statistics across all videos
    summary = {
        "config": {
            "seed": seed,
            "num_frames": num_frames,
            "K": K,
            "tau": tau,
            "budget": budget,
            "iou_threshold": iou_threshold,
            "sample_size": sample_size,
        },
        "per_video": all_diagnostics,
        "aggregate": {},
    }

    # Aggregate stats
    method_names = ["full_oracle", "fixed_rate", "uniform_random", "proxy_threshold", "arc_clustering"]
    for method in method_names:
        oracle_calls_list = [v["baselines"][method]["oracle_calls"] for v in all_diagnostics]
        matched_list = [v["baselines"][method]["num_matched_clips"] for v in all_diagnostics]
        pred_clips_list = [v["baselines"][method]["num_predicted_clips"] for v in all_diagnostics]
        clip_recall_list = [v["baselines"][method]["clip_recall"] for v in all_diagnostics]
        clip_prec_list = [v["baselines"][method]["clip_precision"] for v in all_diagnostics]
        mean_iou_list = [v["baselines"][method]["mean_iou"] for v in all_diagnostics]
        frag_list = [v["baselines"][method]["fragmentation_rate"] for v in all_diagnostics]
        frame_recall_list = [v["baselines"][method]["frame_recall"] for v in all_diagnostics]
        frame_prec_list = [v["baselines"][method]["frame_precision"] for v in all_diagnostics]

        summary["aggregate"][method] = {
            "avg_oracle_calls": float(np.mean(oracle_calls_list)),
            "total_oracle_calls": int(np.sum(oracle_calls_list)),
            "avg_matched_clips": float(np.mean(matched_list)),
            "avg_predicted_clips": float(np.mean(pred_clips_list)),
            "avg_clip_recall": float(np.mean(clip_recall_list)),
            "avg_clip_precision": float(np.mean(clip_prec_list)),
            "avg_mean_iou": float(np.mean(mean_iou_list)),
            "avg_fragmentation_rate": float(np.mean(frag_list)),
            "avg_frame_recall": float(np.mean(frame_recall_list)),
            "avg_frame_precision": float(np.mean(frame_prec_list)),
        }

    # GT aggregate stats
    gt_clip_counts = [v["num_gt_clips"] for v in all_diagnostics]
    gt_avg_lengths = [v["avg_gt_clip_length"] for v in all_diagnostics if v["avg_gt_clip_length"] > 0]
    perturbed_diffs = [v["perturbed_label_diffs"] for v in all_diagnostics]

    summary["gt_aggregate"] = {
        "avg_num_gt_clips": float(np.mean(gt_clip_counts)),
        "total_gt_clips": int(np.sum(gt_clip_counts)),
        "avg_gt_clip_length_overall": float(np.mean(gt_avg_lengths)) if gt_avg_lengths else 0.0,
        "avg_perturbed_label_diffs": float(np.mean(perturbed_diffs)),
        "total_perturbed_label_diffs": int(np.sum(perturbed_diffs)),
    }

    # Save
    output_path = pathlib.Path(__file__).parent / "diagnostics.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"Diagnostics saved to {output_path}")

    # Print summary
    print(f"\n=== DIAGNOSTIC SUMMARY ===")
    print(f"Videos: {sample_size}, Frames: {num_frames}, K={K}, tau={tau}, budget={budget}")
    print(f"\nGT Stats:")
    print(f"  Avg GT clips per video: {summary['gt_aggregate']['avg_num_gt_clips']:.1f}")
    print(f"  Total GT clips: {summary['gt_aggregate']['total_gt_clips']}")
    print(f"  Avg GT clip length: {summary['gt_aggregate']['avg_gt_clip_length_overall']:.1f}")
    print(f"  Avg perturbed label diffs: {summary['gt_aggregate']['avg_perturbed_label_diffs']:.1f}")
    print(f"\nMethod Comparison:")
    print(f"  {'Method':<20} {'Oracle':>8} {'PredClips':>10} {'Matched':>8} {'ClipRec':>8} {'ClipPrec':>8} {'IoU':>6} {'Frag':>6} {'FrmRec':>8}")
    for method in method_names:
        a = summary["aggregate"][method]
        print(f"  {method:<20} {a['avg_oracle_calls']:>8.1f} {a['avg_predicted_clips']:>10.1f} "
              f"{a['avg_matched_clips']:>8.1f} {a['avg_clip_recall']:>8.3f} {a['avg_clip_precision']:>8.3f} "
              f"{a['avg_mean_iou']:>6.3f} {a['avg_fragmentation_rate']:>6.3f} {a['avg_frame_recall']:>8.3f}")


if __name__ == "__main__":
    main()
