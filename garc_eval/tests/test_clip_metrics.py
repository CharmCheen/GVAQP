"""Tests for clip-level metrics.

Tests:
1. Contiguous positives merge into one clip.
2. Gap tolerance merges nearby positive runs.
3. Minimum duration filters short clips.
4. IoU exact cases (identical, disjoint, partial overlap).
5. Clip recall and precision.
6. GVR calculation.
"""

import sys
import pathlib
import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from garc_eval.metrics.clip_metrics import (
    frame_labels_to_clips,
    clip_iou,
    clip_recall,
    clip_precision,
    mean_iou,
    gvr,
    compute_clip_metrics,
)


# --- frame_labels_to_clips ---


def test_contiguous_positives_one_clip():
    """Contiguous positive frames should produce a single clip."""
    labels = [0, 0, 1, 1, 1, 0, 0]
    clips = frame_labels_to_clips(labels)
    assert len(clips) == 1
    assert clips[0] == (2, 4)


def test_two_separate_runs_two_clips():
    """Two separated positive runs should produce two clips."""
    labels = [0, 1, 1, 0, 0, 0, 1, 1, 0]
    clips = frame_labels_to_clips(labels)
    assert len(clips) == 2
    assert clips[0] == (1, 2)
    assert clips[1] == (6, 7)


def test_gap_tolerance_merges():
    """Gap tolerance should merge nearby positive runs."""
    # Positive at 1,2 and 5,6 with gap of 2 frames (3,4)
    labels = [0, 1, 1, 0, 0, 1, 1, 0]
    clips_no_merge = frame_labels_to_clips(labels, gap_tolerance_frames=0)
    assert len(clips_no_merge) == 2

    clips_merged = frame_labels_to_clips(labels, gap_tolerance_frames=2)
    assert len(clips_merged) == 1
    assert clips_merged[0] == (1, 6)


def test_gap_tolerance_exact_boundary():
    """Gap tolerance should merge exactly at the boundary."""
    # Gap of 1 frame between positives at 0 and 2
    labels = [1, 0, 1]
    clips = frame_labels_to_clips(labels, gap_tolerance_frames=1)
    assert len(clips) == 1
    assert clips[0] == (0, 2)


def test_gap_tolerance_exceeded():
    """Gap larger than tolerance should not merge."""
    labels = [1, 0, 0, 1]
    clips = frame_labels_to_clips(labels, gap_tolerance_frames=1)
    assert len(clips) == 2


def test_min_duration_filters_short_clips():
    """Clips shorter than min_duration_frames should be dropped."""
    labels = [1, 0, 0, 1, 1, 1, 0]
    clips = frame_labels_to_clips(labels, min_duration_frames=2)
    assert len(clips) == 1
    assert clips[0] == (3, 5)


def test_min_duration_keeps_long_clips():
    """Clips meeting min_duration should be kept."""
    labels = [1, 1, 1, 0, 1, 0]
    clips = frame_labels_to_clips(labels, min_duration_frames=2)
    assert len(clips) == 1
    assert clips[0] == (0, 2)


def test_all_negative():
    """All negative labels should produce no clips."""
    labels = [0, 0, 0, 0]
    clips = frame_labels_to_clips(labels)
    assert len(clips) == 0


def test_all_positive():
    """All positive labels should produce one clip covering everything."""
    labels = [1, 1, 1, 1, 1]
    clips = frame_labels_to_clips(labels)
    assert len(clips) == 1
    assert clips[0] == (0, 4)


def test_empty_labels():
    """Empty labels should produce no clips."""
    clips = frame_labels_to_clips([])
    assert len(clips) == 0


def test_single_positive():
    """Single positive frame should produce a clip of length 1."""
    labels = [0, 0, 1, 0, 0]
    clips = frame_labels_to_clips(labels)
    assert len(clips) == 1
    assert clips[0] == (2, 2)


# --- clip_iou ---


def test_iou_identical_clips():
    """Identical clips should have IoU = 1.0."""
    assert clip_iou((0, 10), (0, 10)) == 1.0


def test_iou_disjoint_clips():
    """Disjoint clips should have IoU = 0.0."""
    assert clip_iou((0, 4), (5, 10)) == 0.0


def test_iou_partial_overlap():
    """Partial overlap should have IoU between 0 and 1."""
    # (0,4) = 5 frames, (3,7) = 5 frames, intersection = [3,4] = 2, union = 5+5-2 = 8
    iou = clip_iou((0, 4), (3, 7))
    assert abs(iou - 2.0 / 8.0) < 1e-10


def test_iou_contained():
    """One clip fully contained in another should have IoU < 1."""
    # (2,3) = 2 frames, (0,5) = 6 frames, intersection = 2, union = 6
    iou = clip_iou((2, 3), (0, 5))
    assert abs(iou - 2.0 / 6.0) < 1e-10


def test_iou_single_frame_overlap():
    """Single-frame overlap."""
    # (0,0) and (0,0): intersection = 1, union = 1
    assert clip_iou((0, 0), (0, 0)) == 1.0


# --- clip_recall ---


def test_recall_perfect_match():
    """All gt clips matched should give recall = 1.0."""
    pred = [(0, 10)]
    gt = [(0, 10)]
    assert clip_recall(pred, gt, iou_threshold=0.5) == 1.0


def test_recall_no_match():
    """Disjoint pred/gt should give recall = 0.0."""
    pred = [(0, 4)]
    gt = [(10, 20)]
    assert clip_recall(pred, gt, iou_threshold=0.5) == 0.0


def test_recall_partial():
    """One of two gt clips matched should give recall = 0.5."""
    pred = [(0, 10)]
    gt = [(0, 10), (20, 30)]
    assert clip_recall(pred, gt, iou_threshold=0.5) == 0.5


def test_recall_empty_gt():
    """Empty gt should give recall = 1.0 (vacuous)."""
    assert clip_recall([(0, 10)], [], iou_threshold=0.5) == 1.0


# --- clip_precision ---


def test_precision_perfect_match():
    """All pred clips matched should give precision = 1.0."""
    pred = [(0, 10)]
    gt = [(0, 10)]
    assert clip_precision(pred, gt, iou_threshold=0.5) == 1.0


def test_precision_no_match():
    """Disjoint pred/gt should give precision = 0.0."""
    pred = [(0, 4)]
    gt = [(10, 20)]
    assert clip_precision(pred, gt, iou_threshold=0.5) == 0.0


def test_precision_empty_pred():
    """Empty pred with empty gt should give precision = 1.0."""
    assert clip_precision([], [], iou_threshold=0.5) == 1.0


def test_precision_empty_pred_nonempty_gt():
    """Empty pred with non-empty gt should give precision = 0.0."""
    assert clip_precision([], [(0, 10)], iou_threshold=0.5) == 0.0


# --- mean_iou ---


def test_mean_iou_perfect():
    """Perfect match should give mean_iou = 1.0."""
    pred = [(0, 10)]
    gt = [(0, 10)]
    assert mean_iou(pred, gt) == 1.0


def test_mean_iou_no_overlap():
    """No overlap should give mean_iou = 0.0."""
    pred = [(0, 4)]
    gt = [(10, 20)]
    assert mean_iou(pred, gt) == 0.0


def test_mean_iou_two_gt_clips():
    """Mean IoU across two gt clips."""
    pred = [(0, 10)]
    gt = [(0, 10), (20, 30)]
    # gt[0]: IoU = 1.0, gt[1]: IoU = 0.0
    assert abs(mean_iou(pred, gt) - 0.5) < 1e-10


def test_mean_iou_empty_gt():
    """Empty gt should give mean_iou = 1.0 (vacuous)."""
    assert mean_iou([(0, 10)], []) == 1.0


# --- gvr ---


def test_gvr_all_pass():
    """All trials passing should give GVR = 1.0."""
    trials = [{"clip_recall": 0.9}, {"clip_recall": 1.0}, {"clip_recall": 0.8}]
    assert gvr(trials, iou_threshold=0.5) == 1.0


def test_gvr_none_pass():
    """No trials passing should give GVR = 0.0."""
    trials = [{"clip_recall": 0.1}, {"clip_recall": 0.0}]
    assert gvr(trials, iou_threshold=0.5) == 0.0


def test_gvr_partial():
    """Half passing should give GVR = 0.5."""
    trials = [{"clip_recall": 0.6}, {"clip_recall": 0.3}]
    assert gvr(trials, iou_threshold=0.5) == 0.5


def test_gvr_empty():
    """Empty trials should give GVR = 0.0."""
    assert gvr([], iou_threshold=0.5) == 0.0


def test_gvr_custom_threshold():
    """GVR with custom threshold."""
    trials = [{"clip_recall": 0.8}, {"clip_recall": 0.6}]
    assert gvr(trials, iou_threshold=0.7) == 0.5
    assert gvr(trials, iou_threshold=0.9) == 0.0


# --- compute_clip_metrics ---


def test_compute_clip_metrics_keys():
    """compute_clip_metrics should return expected keys."""
    result = compute_clip_metrics([(0, 10)], [(0, 10)], iou_threshold=0.5)
    expected_keys = {"clip_recall", "clip_precision", "mean_iou", "n_pred_clips", "n_gt_clips"}
    assert set(result.keys()) == expected_keys


def test_compute_clip_metrics_values():
    """compute_clip_metrics should return correct values for perfect match."""
    result = compute_clip_metrics([(0, 10)], [(0, 10)], iou_threshold=0.5)
    assert result["clip_recall"] == 1.0
    assert result["clip_precision"] == 1.0
    assert result["mean_iou"] == 1.0
    assert result["n_pred_clips"] == 1
    assert result["n_gt_clips"] == 1


# --- integration: frame_labels_to_clips + clip_metrics ---


def test_end_to_end_frame_labels_to_metrics():
    """Full pipeline: frame labels -> clips -> metrics."""
    gt_labels =   [0, 1, 1, 1, 0, 0, 0, 1, 1, 0]
    pred_labels = [0, 1, 1, 0, 0, 0, 0, 1, 1, 0]

    gt_clips = frame_labels_to_clips(gt_labels)
    pred_clips = frame_labels_to_clips(pred_labels)

    assert gt_clips == [(1, 3), (7, 8)]
    assert pred_clips == [(1, 2), (7, 8)]

    metrics = compute_clip_metrics(pred_clips, gt_clips, iou_threshold=0.5)
    # gt[0] = (1,3): best pred = (1,2), IoU = 2/3 = 0.667 >= 0.5 -> matched
    # gt[1] = (7,8): best pred = (7,8), IoU = 1.0 -> matched
    assert metrics["clip_recall"] == 1.0
    # pred[0] = (1,2): best gt = (1,3), IoU = 2/3 >= 0.5 -> matched
    # pred[1] = (7,8): best gt = (7,8), IoU = 1.0 -> matched
    assert metrics["clip_precision"] == 1.0


def test_frame_labels_to_clips_with_gap_and_min_duration():
    """Combined gap tolerance and min duration."""
    # Positives at 0,1 and 4,5,6 with gap of 2 frames (2,3)
    labels = [1, 1, 0, 0, 1, 1, 1, 0]
    # Without merge: clips = [(0,1), (4,6)]
    clips = frame_labels_to_clips(labels, gap_tolerance_frames=0, min_duration_frames=2)
    assert len(clips) == 2
    assert clips[0] == (0, 1)
    assert clips[1] == (4, 6)

    # With merge (gap_tolerance=2): clips = [(0,6)], length=7
    clips_merged = frame_labels_to_clips(labels, gap_tolerance_frames=2, min_duration_frames=3)
    assert len(clips_merged) == 1
    assert clips_merged[0] == (0, 6)
