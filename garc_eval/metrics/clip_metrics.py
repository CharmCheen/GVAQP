"""Metrics for clip-level evaluation of frame-level selection.

Converts frame-level labels (0/1 per frame) into temporal clips (contiguous
positive runs), then computes clip-level IoU, recall, precision, mean IoU,
and Guaranteed Video Rate (GVR).
"""

import numpy as np


def frame_labels_to_clips(
    labels: np.ndarray,
    timestamps: np.ndarray | None = None,
    min_duration_frames: int = 1,
    gap_tolerance_frames: int = 0,
) -> list[tuple[int, int]]:
    """Convert binary frame labels into temporal clips.

    A clip is a contiguous run of positive frames, with gaps up to
    ``gap_tolerance_frames`` merged. Clips shorter than ``min_duration_frames``
    are dropped.

    Parameters
    ----------
    labels : array of 0/1 per frame.
    timestamps : optional array of frame timestamps (indices used if None).
    min_duration_frames : minimum clip length in frames.
    gap_tolerance_frames : maximum gap (consecutive negative frames) to merge
        across. 0 means no merging.

    Returns
    -------
    List of (start_idx, end_idx) tuples, inclusive on both ends.
    """
    labels = np.asarray(labels).astype(int)
    n = len(labels)
    if n == 0:
        return []

    positive_indices = np.where(labels == 1)[0]
    if len(positive_indices) == 0:
        return []

    # Build raw clips from positive runs with gap tolerance
    clips = []
    start = int(positive_indices[0])
    end = int(positive_indices[0])

    for i in range(1, len(positive_indices)):
        idx = int(positive_indices[i])
        if idx - end - 1 <= gap_tolerance_frames:
            # Merge across gap
            end = idx
        else:
            # Flush current clip
            clips.append((start, end))
            start = idx
            end = idx
    clips.append((start, end))

    # Filter by minimum duration
    clips = [
        (s, e) for s, e in clips
        if (e - s + 1) >= min_duration_frames
    ]

    return clips


def clip_iou(
    pred_clip: tuple[int, int],
    gt_clip: tuple[int, int],
) -> float:
    """Compute IoU between two clips.

    Clips are (start, end) inclusive.
    """
    inter_start = max(pred_clip[0], gt_clip[0])
    inter_end = min(pred_clip[1], gt_clip[1])
    intersection = max(0, inter_end - inter_start + 1)

    union = (pred_clip[1] - pred_clip[0] + 1) + (gt_clip[1] - gt_clip[0] + 1) - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def clip_recall(
    pred_clips: list[tuple[int, int]],
    gt_clips: list[tuple[int, int]],
    iou_threshold: float = 0.5,
) -> float:
    """Fraction of ground-truth clips matched by at least one prediction.

    A gt clip is matched if any pred clip has IoU >= iou_threshold.
    """
    if len(gt_clips) == 0:
        return 1.0

    matched = 0
    for gt in gt_clips:
        for pred in pred_clips:
            if clip_iou(pred, gt) >= iou_threshold:
                matched += 1
                break
    return matched / len(gt_clips)


def clip_precision(
    pred_clips: list[tuple[int, int]],
    gt_clips: list[tuple[int, int]],
    iou_threshold: float = 0.5,
) -> float:
    """Fraction of predicted clips matched by at least one ground-truth clip.

    A pred clip is matched if any gt clip has IoU >= iou_threshold.
    """
    if len(pred_clips) == 0:
        return 1.0 if len(gt_clips) == 0 else 0.0

    matched = 0
    for pred in pred_clips:
        for gt in gt_clips:
            if clip_iou(pred, gt) >= iou_threshold:
                matched += 1
                break
    return matched / len(pred_clips)


def mean_iou(
    pred_clips: list[tuple[int, int]],
    gt_clips: list[tuple[int, int]],
) -> float:
    """Mean best-IoU across all ground-truth clips.

    For each gt clip, finds the best IoU with any pred clip, then averages.
    """
    if len(gt_clips) == 0:
        return 1.0

    ious = []
    for gt in gt_clips:
        best = max((clip_iou(pred, gt) for pred in pred_clips), default=0.0)
        ious.append(best)
    return float(np.mean(ious))


def gvr(
    trial_results: list[dict],
    iou_threshold: float = 0.5,
) -> float:
    """Guaranteed Video Rate: fraction of trials where clip_recall >= iou_threshold.

    Parameters
    ----------
    trial_results : list of dicts, each with 'clip_recall' key.

    Returns
    -------
    Fraction of trials meeting the clip recall threshold.
    """
    if len(trial_results) == 0:
        return 0.0
    met = sum(1 for r in trial_results if r.get("clip_recall", 0.0) >= iou_threshold)
    return met / len(trial_results)


def compute_clip_metrics(
    pred_clips: list[tuple[int, int]],
    gt_clips: list[tuple[int, int]],
    iou_threshold: float = 0.5,
) -> dict:
    """Compute all clip-level metrics for a single trial.

    Returns dict with: clip_recall, clip_precision, mean_iou, n_pred_clips, n_gt_clips.
    """
    return {
        "clip_recall": clip_recall(pred_clips, gt_clips, iou_threshold),
        "clip_precision": clip_precision(pred_clips, gt_clips, iou_threshold),
        "mean_iou": mean_iou(pred_clips, gt_clips),
        "n_pred_clips": len(pred_clips),
        "n_gt_clips": len(gt_clips),
    }
