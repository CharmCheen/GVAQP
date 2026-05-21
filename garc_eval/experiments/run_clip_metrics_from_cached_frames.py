"""Evaluate clip-level metrics from cached frame-level selection outputs.

Reads frame-level selection results (selected frame ids from SUPG/baseline
methods) and computes clip-level recall, precision, mean IoU, and GVR.

Usage:
    python -m garc_eval.experiments.run_clip_metrics_from_cached_frames \\
        --frames-csv path/to/frames.csv \\
        --selected-ids-csv path/to/selected_ids.csv \\
        --min-duration-sec 1.0 \\
        --gap-tolerance-sec 0.5 \\
        --iou-threshold 0.5 \\
        --fps 30 \\
        --outdir path/to/output
"""

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from garc_eval.metrics.clip_metrics import (
    frame_labels_to_clips,
    compute_clip_metrics,
    gvr,
)


def load_frames(frames_path: str) -> pd.DataFrame:
    """Load frame data from CSV or Parquet.

    Expected columns: id, label (0/1). Optional: timestamp, frame_idx.
    """
    p = pathlib.Path(frames_path)
    if p.suffix == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p)

    required = {"id", "label"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"Frame data must have columns {required}, got {set(df.columns)}")
    return df


def load_selected_ids(selected_ids_path: str) -> np.ndarray:
    """Load selected frame ids from CSV.

    Expected column: id (or first column used as id).
    """
    df = pd.read_csv(selected_ids_path)
    if "id" in df.columns:
        return df["id"].values
    return df.iloc[:, 0].values


def frame_labels_to_clips_with_time(
    labels: np.ndarray,
    timestamps: np.ndarray | None,
    fps: float,
    min_duration_sec: float,
    gap_tolerance_sec: float,
) -> list[tuple[int, int]]:
    """Convert labels to clips using time-based parameters."""
    min_duration_frames = max(1, int(min_duration_sec * fps))
    gap_tolerance_frames = max(0, int(gap_tolerance_sec * fps))
    return frame_labels_to_clips(
        labels,
        timestamps=timestamps,
        min_duration_frames=min_duration_frames,
        gap_tolerance_frames=gap_tolerance_frames,
    )


def run_clip_evaluation(
    frames_df: pd.DataFrame,
    selected_ids: np.ndarray,
    fps: float,
    min_duration_sec: float,
    gap_tolerance_sec: float,
    iou_threshold: float,
) -> dict:
    """Run clip-level evaluation for a single method/trial.

    Parameters
    ----------
    frames_df : DataFrame with id, label columns.
    selected_ids : array of frame ids selected by the method.
    fps : frames per second.
    min_duration_sec : minimum clip duration in seconds.
    gap_tolerance_sec : maximum gap to merge in seconds.
    iou_threshold : IoU threshold for matching.

    Returns
    -------
    Dict with clip metrics plus frame-level counts.
    """
    # Build gt clips from all frame labels
    labels = frames_df["label"].values
    gt_clips = frame_labels_to_clips_with_time(
        labels, None, fps, min_duration_sec, gap_tolerance_sec
    )

    # Build pred clips from selected frame ids
    id_set = set(selected_ids.astype(int))
    pred_labels = np.array([1 if int(fid) in id_set else 0 for fid in frames_df["id"].values])
    pred_clips = frame_labels_to_clips_with_time(
        pred_labels, None, fps, min_duration_sec, gap_tolerance_sec
    )

    # Compute clip metrics
    metrics = compute_clip_metrics(pred_clips, gt_clips, iou_threshold)

    # Add frame-level context
    total_positives = int(np.sum(labels))
    selected_n = len(selected_ids)
    total_n = len(labels)
    true_positives = int(np.sum(labels[np.isin(frames_df["id"].values, selected_ids)]))

    metrics["frame_recall"] = true_positives / total_positives if total_positives > 0 else 0.0
    metrics["frame_precision"] = true_positives / selected_n if selected_n > 0 else 0.0
    metrics["selected_n"] = selected_n
    metrics["total_n"] = total_n
    metrics["selected_n_ratio"] = selected_n / total_n if total_n > 0 else 0.0
    metrics["total_positive_frames"] = total_positives
    metrics["true_positive_frames"] = true_positives

    return metrics


def generate_report(
    all_results: dict[str, dict],
    outdir: pathlib.Path,
    fps: float,
    min_duration_sec: float,
    gap_tolerance_sec: float,
    iou_threshold: float,
) -> None:
    """Generate clip metrics summary report."""
    lines = [
        "# Clip-Level Metrics Report\n",
        "\n## Parameters\n",
        f"- fps: {fps}",
        f"- min_duration_sec: {min_duration_sec}",
        f"- gap_tolerance_sec: {gap_tolerance_sec}",
        f"- iou_threshold: {iou_threshold}\n",
        "\n## Results by Method\n",
        "| Method | Clip Recall | Clip Precision | Mean IoU | GVR | "
        "Frame Recall | Frame Precision | Selected N/N | N Clips (pred/gt) |",
        "|--------|-------------|----------------|----------|-----|"
        "--------------|-----------------|--------------|-------------------|",
    ]

    for method, m in all_results.items():
        lines.append(
            f"| {method} "
            f"| {m['clip_recall']:.3f} "
            f"| {m['clip_precision']:.3f} "
            f"| {m['mean_iou']:.3f} "
            f"| {m.get('gvr', 'N/A')} "
            f"| {m['frame_recall']:.3f} "
            f"| {m['frame_precision']:.3f} "
            f"| {m['selected_n_ratio']:.3f} "
            f"| {m['n_pred_clips']}/{m['n_gt_clips']} |"
        )

    lines.append("\n## Frame vs Clip Gap Analysis\n")
    for method, m in all_results.items():
        frame_recall = m["frame_recall"]
        clip_recall = m["clip_recall"]
        gap = frame_recall - clip_recall
        lines.append(f"- **{method}**: frame_recall={frame_recall:.3f}, "
                     f"clip_recall={clip_recall:.3f}, gap={gap:+.3f}")
        if gap > 0.1:
            lines.append(f"  - **WARNING**: Frame recall exceeds clip recall by {gap:.1%}. "
                         f"Frame-level guarantee does NOT transfer to clip level.")

    lines.append(f"\n---\nGenerated: {pd.Timestamp.now().isoformat()}\n")
    (outdir / "clip_metrics_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Clip-level metrics from cached frames")
    parser.add_argument("--frames-csv", required=True,
                        help="Path to frames CSV/Parquet with id, label columns")
    parser.add_argument("--selected-ids-csv", required=True,
                        help="Path to selected frame ids CSV")
    parser.add_argument("--method-name", default="SUPG-RT",
                        help="Method name for reporting")
    parser.add_argument("--fps", type=float, default=30.0,
                        help="Frames per second")
    parser.add_argument("--min-duration-sec", type=float, default=1.0,
                        help="Minimum clip duration in seconds")
    parser.add_argument("--gap-tolerance-sec", type=float, default=0.5,
                        help="Maximum gap to merge in seconds")
    parser.add_argument("--iou-threshold", type=float, default=0.5,
                        help="IoU threshold for clip matching")
    parser.add_argument("--outdir", type=str, default="garc_eval/outputs/clip_metrics")
    args = parser.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load data
    frames_df = load_frames(args.frames_csv)
    selected_ids = load_selected_ids(args.selected_ids_csv)

    print(f"Loaded {len(frames_df)} frames, {len(selected_ids)} selected ids")
    print(f"Positive rate: {frames_df['label'].mean():.4f}")

    # Run evaluation
    metrics = run_clip_evaluation(
        frames_df, selected_ids,
        fps=args.fps,
        min_duration_sec=args.min_duration_sec,
        gap_tolerance_sec=args.gap_tolerance_sec,
        iou_threshold=args.iou_threshold,
    )

    all_results = {args.method_name: metrics}

    # Save results
    with open(outdir / "clip_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Generate report
    generate_report(
        all_results, outdir,
        fps=args.fps,
        min_duration_sec=args.min_duration_sec,
        gap_tolerance_sec=args.gap_tolerance_sec,
        iou_threshold=args.iou_threshold,
    )

    print(f"\nResults:")
    print(f"  Clip recall: {metrics['clip_recall']:.3f}")
    print(f"  Clip precision: {metrics['clip_precision']:.3f}")
    print(f"  Mean IoU: {metrics['mean_iou']:.3f}")
    print(f"  Frame recall: {metrics['frame_recall']:.3f}")
    print(f"\nSaved to {outdir}")


if __name__ == "__main__":
    main()
