"""Metrics for evaluating clip-level query under perturbation."""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any

import numpy as np


@dataclass
class ExperimentMetrics:
    """All metrics for a single video experiment."""
    video_id: str
    method: str

    # Frame-level
    frame_recall: float = 0.0
    frame_precision: float = 0.0

    # Clip-level
    clip_recall: float = 0.0
    clip_precision: float = 0.0

    # Boundary errors (in frames)
    mean_start_error: float = 0.0
    mean_end_error: float = 0.0

    # IoU
    mean_iou: float = 0.0

    # Fragmentation
    fragmentation_rate: float = 0.0

    # Budget
    oracle_calls: int = 0
    total_frames: int = 0
    oracle_fraction: float = 0.0

    # Clip counts
    num_gt_clips: int = 0
    num_pred_clips: int = 0
    num_matched_clips: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "method": self.method,
            "frame_recall": self.frame_recall,
            "frame_precision": self.frame_precision,
            "clip_recall": self.clip_recall,
            "clip_precision": self.clip_precision,
            "mean_start_error": self.mean_start_error,
            "mean_end_error": self.mean_end_error,
            "mean_iou": self.mean_iou,
            "fragmentation_rate": self.fragmentation_rate,
            "oracle_calls": self.oracle_calls,
            "total_frames": self.total_frames,
            "oracle_fraction": self.oracle_fraction,
            "num_gt_clips": self.num_gt_clips,
            "num_pred_clips": self.num_pred_clips,
            "num_matched_clips": self.num_matched_clips,
        }


def compute_frame_metrics(
    gt_labels: np.ndarray,
    pred_labels: np.ndarray,
) -> Tuple[float, float]:
    """Compute frame-level recall and precision."""
    gt_pos = gt_labels.astype(bool)
    pred_pos = pred_labels.astype(bool)

    tp = np.sum(gt_pos & pred_pos)
    fn = np.sum(gt_pos & ~pred_pos)
    fp = np.sum(~gt_pos & pred_pos)

    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    return float(recall), float(precision)


def compute_clip_metrics(
    gt_clips: List[Tuple[int, int]],
    pred_clips: List[Tuple[int, int]],
    iou_threshold: float = 0.5,
) -> Dict[str, float]:
    """Compute clip-level recall, precision, mean IoU, boundary errors, fragmentation."""
    if not gt_clips and not pred_clips:
        return {
            "clip_recall": 1.0,
            "clip_precision": 1.0,
            "mean_iou": 1.0,
            "mean_start_error": 0.0,
            "mean_end_error": 0.0,
            "fragmentation_rate": 0.0,
            "num_matched": 0,
        }

    if not gt_clips:
        return {
            "clip_recall": 1.0,
            "clip_precision": 0.0 if pred_clips else 1.0,
            "mean_iou": 0.0,
            "mean_start_error": 0.0,
            "mean_end_error": 0.0,
            "fragmentation_rate": len(pred_clips),
            "num_matched": 0,
        }

    if not pred_clips:
        return {
            "clip_recall": 0.0,
            "clip_precision": 1.0,
            "mean_iou": 0.0,
            "mean_start_error": float('inf'),
            "mean_end_error": float('inf'),
            "fragmentation_rate": 0.0,
            "num_matched": 0,
        }

    # Match predicted clips to GT clips using IoU
    matched_gt = set()
    matched_pred = set()
    ious = []
    start_errors = []
    end_errors = []

    # For each GT clip, find best matching predicted clip
    for gi, (gs, ge) in enumerate(gt_clips):
        best_iou = 0.0
        best_pi = -1
        for pi, (ps, pe) in enumerate(pred_clips):
            iou = _compute_iou((gs, ge), (ps, pe))
            if iou > best_iou:
                best_iou = iou
                best_pi = pi

        if best_iou >= iou_threshold and best_pi not in matched_pred:
            matched_gt.add(gi)
            matched_pred.add(best_pi)
            ious.append(best_iou)
            ps, pe = pred_clips[best_pi]
            start_errors.append(abs(gs - ps))
            end_errors.append(abs(ge - pe))

    clip_recall = len(matched_gt) / len(gt_clips) if gt_clips else 1.0
    clip_precision = len(matched_pred) / len(pred_clips) if pred_clips else 1.0
    mean_iou = float(np.mean(ious)) if ious else 0.0
    mean_start_error = float(np.mean(start_errors)) if start_errors else float('inf')
    mean_end_error = float(np.mean(end_errors)) if end_errors else float('inf')

    # Fragmentation: how many predicted clips per GT clip (ideal = 1)
    # For unmatched GT clips, fragmentation contribution = 0 (missed, not fragmented)
    # For matched GT clips, check if multiple pred clips overlap the same GT clip
    fragmentation_count = 0
    for gi, (gs, ge) in enumerate(gt_clips):
        overlapping = 0
        for pi, (ps, pe) in enumerate(pred_clips):
            if _compute_iou((gs, ge), (ps, pe)) > 0:
                overlapping += 1
        if overlapping > 1:
            fragmentation_count += overlapping - 1

    fragmentation_rate = fragmentation_count / len(gt_clips) if gt_clips else 0.0

    return {
        "clip_recall": clip_recall,
        "clip_precision": clip_precision,
        "mean_iou": mean_iou,
        "mean_start_error": mean_start_error,
        "mean_end_error": mean_end_error,
        "fragmentation_rate": fragmentation_rate,
        "num_matched": len(matched_gt),
    }


def _compute_iou(clip_a: Tuple[int, int], clip_b: Tuple[int, int]) -> float:
    """Compute IoU between two clips (start, end inclusive)."""
    a_start, a_end = clip_a
    b_start, b_end = clip_b

    intersection_start = max(a_start, b_start)
    intersection_end = min(a_end, b_end)
    intersection = max(0, intersection_end - intersection_start + 1)

    union = (a_end - a_start + 1) + (b_end - b_start + 1) - intersection
    return intersection / union if union > 0 else 0.0


def compute_experiment_metrics(
    video_id: str,
    method: str,
    gt_frame_labels: np.ndarray,
    pred_frame_labels: np.ndarray,
    gt_clips: List[Tuple[int, int]],
    pred_clips: List[Tuple[int, int]],
    oracle_calls: int,
    total_frames: int,
) -> ExperimentMetrics:
    """Compute all metrics for a single video/method combination."""
    frame_recall, frame_precision = compute_frame_metrics(gt_frame_labels, pred_frame_labels)
    clip_metrics = compute_clip_metrics(gt_clips, pred_clips)

    return ExperimentMetrics(
        video_id=video_id,
        method=method,
        frame_recall=frame_recall,
        frame_precision=frame_precision,
        clip_recall=clip_metrics["clip_recall"],
        clip_precision=clip_metrics["clip_precision"],
        mean_start_error=clip_metrics["mean_start_error"],
        mean_end_error=clip_metrics["mean_end_error"],
        mean_iou=clip_metrics["mean_iou"],
        fragmentation_rate=clip_metrics["fragmentation_rate"],
        oracle_calls=oracle_calls,
        total_frames=total_frames,
        oracle_fraction=oracle_calls / total_frames if total_frames > 0 else 0.0,
        num_gt_clips=len(gt_clips),
        num_pred_clips=len(pred_clips),
        num_matched_clips=clip_metrics["num_matched"],
    )


@dataclass
class HardExperimentMetrics:
    """Extended metrics for hard synthetic experiments."""
    video_id: str
    method: str
    regime: str
    tau: int
    budget: float
    seed: int

    # Standard metrics
    frame_recall: float = 0.0
    frame_precision: float = 0.0
    clip_recall: float = 0.0
    clip_precision: float = 0.0
    mean_iou: float = 0.0
    mean_start_error: float = 0.0
    mean_end_error: float = 0.0
    fragmentation_rate: float = 0.0

    # Precision-sensitive metrics
    false_merge_count: int = 0    # predicted clips that overlap multiple GT clips
    false_split_count: int = 0    # GT clips that overlap multiple predicted clips
    over_extension_length: float = 0.0   # avg frames predicted extends beyond GT
    under_coverage_length: float = 0.0   # avg frames GT extends beyond predicted

    # Budget
    oracle_calls: int = 0
    total_frames: int = 0
    oracle_fraction: float = 0.0

    # Clip counts
    num_gt_clips: int = 0
    num_pred_clips: int = 0
    num_matched_clips: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "method": self.method,
            "regime": self.regime,
            "tau": self.tau,
            "budget": self.budget,
            "seed": self.seed,
            "frame_recall": self.frame_recall,
            "frame_precision": self.frame_precision,
            "clip_recall": self.clip_recall,
            "clip_precision": self.clip_precision,
            "mean_iou": self.mean_iou,
            "mean_start_error": self.mean_start_error,
            "mean_end_error": self.mean_end_error,
            "fragmentation_rate": self.fragmentation_rate,
            "false_merge_count": self.false_merge_count,
            "false_split_count": self.false_split_count,
            "over_extension_length": self.over_extension_length,
            "under_coverage_length": self.under_coverage_length,
            "oracle_calls": self.oracle_calls,
            "total_frames": self.total_frames,
            "oracle_fraction": self.oracle_fraction,
            "num_gt_clips": self.num_gt_clips,
            "num_pred_clips": self.num_pred_clips,
            "num_matched_clips": self.num_matched_clips,
        }


def compute_precision_sensitive_metrics(
    gt_clips: List[Tuple[int, int]],
    pred_clips: List[Tuple[int, int]],
    iou_threshold: float = 0.5,
) -> Dict[str, float]:
    """Compute precision-sensitive clip metrics.

    Returns:
        - false_merge_count: predicted clips that overlap multiple GT clips
        - false_split_count: GT clips that overlap multiple predicted clips
        - over_extension_length: avg frames predicted extends beyond GT (for matched clips)
        - under_coverage_length: avg frames GT extends beyond predicted (for matched clips)
    """
    if not gt_clips and not pred_clips:
        return {
            "false_merge_count": 0,
            "false_split_count": 0,
            "over_extension_length": 0.0,
            "under_coverage_length": 0.0,
        }

    if not gt_clips:
        return {
            "false_merge_count": len(pred_clips),
            "false_split_count": 0,
            "over_extension_length": float('inf') if pred_clips else 0.0,
            "under_coverage_length": 0.0,
        }

    if not pred_clips:
        return {
            "false_merge_count": 0,
            "false_split_count": len(gt_clips),
            "over_extension_length": 0.0,
            "under_coverage_length": float('inf') if gt_clips else 0.0,
        }

    # Compute overlap matrix
    # overlap[i][j] = frames of intersection between gt_clips[i] and pred_clips[j]
    n_gt = len(gt_clips)
    n_pred = len(pred_clips)
    overlap = np.zeros((n_gt, n_pred), dtype=int)

    for i, (gs, ge) in enumerate(gt_clips):
        for j, (ps, pe) in enumerate(pred_clips):
            inter_start = max(gs, ps)
            inter_end = min(ge, pe)
            overlap[i, j] = max(0, inter_end - inter_start + 1)

    # False merges: predicted clips that overlap multiple GT clips
    false_merge_count = 0
    for j in range(n_pred):
        overlapping_gt = np.sum(overlap[:, j] > 0)
        if overlapping_gt > 1:
            false_merge_count += overlapping_gt - 1

    # False splits: GT clips that overlap multiple predicted clips
    false_split_count = 0
    for i in range(n_gt):
        overlapping_pred = np.sum(overlap[i, :] > 0)
        if overlapping_pred > 1:
            false_split_count += overlapping_pred - 1

    # Over-extension and under-coverage for matched clips
    over_extensions = []
    under_coverages = []

    # For each GT clip, find best matching predicted clip
    for i, (gs, ge) in enumerate(gt_clips):
        best_j = np.argmax(overlap[i, :])
        if overlap[i, best_j] > 0:
            ps, pe = pred_clips[best_j]
            # Over-extension: how much predicted extends beyond GT
            over_ext = max(0, ps - gs) + max(0, ge - pe)
            over_extensions.append(over_ext)

            # Under-coverage: how much GT extends beyond predicted (missed frames)
            under_cov = max(0, gs - ps) + max(0, pe - ge)
            under_coverages.append(under_cov)

    return {
        "false_merge_count": false_merge_count,
        "false_split_count": false_split_count,
        "over_extension_length": float(np.mean(over_extensions)) if over_extensions else 0.0,
        "under_coverage_length": float(np.mean(under_coverages)) if under_coverages else 0.0,
    }


def compute_hard_experiment_metrics(
    video_id: str,
    method: str,
    regime: str,
    tau: int,
    budget: float,
    seed: int,
    gt_frame_labels: np.ndarray,
    pred_frame_labels: np.ndarray,
    gt_clips: List[Tuple[int, int]],
    pred_clips: List[Tuple[int, int]],
    oracle_calls: int,
    total_frames: int,
) -> HardExperimentMetrics:
    """Compute all metrics including precision-sensitive ones."""
    frame_recall, frame_precision = compute_frame_metrics(gt_frame_labels, pred_frame_labels)
    clip_metrics = compute_clip_metrics(gt_clips, pred_clips)
    precision_metrics = compute_precision_sensitive_metrics(gt_clips, pred_clips)

    return HardExperimentMetrics(
        video_id=video_id,
        method=method,
        regime=regime,
        tau=tau,
        budget=budget,
        seed=seed,
        frame_recall=frame_recall,
        frame_precision=frame_precision,
        clip_recall=clip_metrics["clip_recall"],
        clip_precision=clip_metrics["clip_precision"],
        mean_iou=clip_metrics["mean_iou"],
        mean_start_error=clip_metrics["mean_start_error"],
        mean_end_error=clip_metrics["mean_end_error"],
        fragmentation_rate=clip_metrics["fragmentation_rate"],
        false_merge_count=precision_metrics["false_merge_count"],
        false_split_count=precision_metrics["false_split_count"],
        over_extension_length=precision_metrics["over_extension_length"],
        under_coverage_length=precision_metrics["under_coverage_length"],
        oracle_calls=oracle_calls,
        total_frames=total_frames,
        oracle_fraction=oracle_calls / total_frames if total_frames > 0 else 0.0,
        num_gt_clips=len(gt_clips),
        num_pred_clips=len(pred_clips),
        num_matched_clips=clip_metrics["num_matched"],
    )
