"""Tests for frame-to-clip bridge module."""

import numpy as np
import pandas as pd
import pytest

from garc_eval.metrics.frame_to_clip import (
    build_gt_clips,
    build_candidate_clips,
    temporal_iou,
    compute_frame_level_metrics,
    compute_clip_level_metrics,
    analyze_temporal_misses,
)


def make_frames(video_id, n_frames, positive_ranges, fps=25.0):
    """Helper: create a frame DataFrame with known positive ranges.

    positive_ranges: list of (start_idx, end_idx) inclusive
    """
    rows = []
    fid = 0
    for i in range(n_frames):
        label = 0
        for s, e in positive_ranges:
            if s <= i <= e:
                label = 1
                break
        rows.append({
            "id": fid,
            "video_id": video_id,
            "frame_idx": i,
            "timestamp": i / fps,
            "label": label,
        })
        fid += 1
    return pd.DataFrame(rows)


class TestTemporalIoU:
    def test_perfect_overlap(self):
        assert temporal_iou(0, 10, 0, 10) == 1.0

    def test_no_overlap(self):
        assert temporal_iou(0, 5, 6, 10) == 0.0

    def test_partial_overlap(self):
        iou = temporal_iou(0, 10, 5, 15)
        # intersection = 5, union = 15
        assert abs(iou - 5 / 15) < 1e-6

    def test_contained(self):
        iou = temporal_iou(2, 8, 0, 10)
        # intersection = 6, union = 10
        assert abs(iou - 6 / 10) < 1e-6


class TestBuildGtClips:
    def test_single_clip(self):
        df = make_frames("v1", 10, [(2, 7)])
        clips = build_gt_clips(df, min_clip_frames=1, gap_tolerance=0)
        assert len(clips) == 1
        assert clips.iloc[0]["start_frame"] == 2
        assert clips.iloc[0]["end_frame"] == 7
        assert clips.iloc[0]["video_id"] == "v1"

    def test_two_clips(self):
        df = make_frames("v1", 20, [(2, 5), (12, 17)])
        clips = build_gt_clips(df, min_clip_frames=1, gap_tolerance=0)
        assert len(clips) == 2

    def test_gap_tolerance_merges(self):
        df = make_frames("v1", 20, [(2, 5), (7, 10)])
        clips = build_gt_clips(df, min_clip_frames=1, gap_tolerance=2)
        assert len(clips) == 1  # merged

    def test_min_clip_frames_filters(self):
        df = make_frames("v1", 20, [(2, 3), (10, 17)])
        clips = build_gt_clips(df, min_clip_frames=5, gap_tolerance=0)
        assert len(clips) == 1  # (2,3) filtered out

    def test_no_positives(self):
        df = make_frames("v1", 10, [])
        clips = build_gt_clips(df)
        assert len(clips) == 0

    def test_multi_video(self):
        df1 = make_frames("v1", 10, [(2, 5)])
        df2 = make_frames("v2", 10, [(3, 8)])
        df = pd.concat([df1, df2], ignore_index=True)
        clips = build_gt_clips(df)
        assert len(clips) == 2
        assert set(clips["video_id"]) == {"v1", "v2"}


class TestBuildCandidateClips:
    def test_basic(self):
        df = make_frames("v1", 10, [])
        selected_ids = np.array([2, 3, 4, 5])
        clips = build_candidate_clips(df, selected_ids, min_clip_frames=1)
        assert len(clips) == 1
        assert clips.iloc[0]["start_frame"] == 2
        assert clips.iloc[0]["end_frame"] == 5

    def test_sparse_selection(self):
        df = make_frames("v1", 10, [])
        selected_ids = np.array([1, 3, 5, 7])
        clips = build_candidate_clips(df, selected_ids, min_clip_frames=1, gap_tolerance=0)
        assert len(clips) == 4  # each frame is its own clip

    def test_gap_tolerance(self):
        df = make_frames("v1", 10, [])
        selected_ids = np.array([1, 2, 5, 6])
        clips = build_candidate_clips(df, selected_ids, min_clip_frames=1, gap_tolerance=3)
        assert len(clips) == 1  # merged


class TestFrameLevelMetrics:
    def test_perfect(self):
        df = make_frames("v1", 10, [(0, 9)])
        selected_ids = np.arange(10)
        m = compute_frame_level_metrics(df, selected_ids)
        assert m["frame_recall"] == 1.0
        assert m["frame_precision"] == 1.0

    def test_half(self):
        df = make_frames("v1", 10, [(0, 9)])
        selected_ids = np.arange(0, 10, 2)
        m = compute_frame_level_metrics(df, selected_ids)
        assert abs(m["frame_recall"] - 0.5) < 1e-6

    def test_empty_selection(self):
        df = make_frames("v1", 10, [(0, 5)])
        m = compute_frame_level_metrics(df, np.array([]))
        assert m["frame_recall"] == 0.0
        assert m["selected_n"] == 0


class TestClipLevelMetrics:
    def test_perfect_match(self):
        df = make_frames("v1", 20, [(0, 10)])
        gt = build_gt_clips(df)
        selected_ids = np.arange(0, 11)
        m = compute_clip_level_metrics(gt, df, selected_ids, iou_threshold=0.5)
        assert m["clip_recall_coverage"] == 1.0
        assert m["clip_recall_iou"] == 1.0
        assert m["clip_precision"] == 1.0
        assert m["mIoU"] == 1.0

    def test_no_match(self):
        df = make_frames("v1", 40, [(0, 10)])
        gt = build_gt_clips(df)
        selected_ids = np.arange(20, 31)
        m = compute_clip_level_metrics(gt, df, selected_ids, iou_threshold=0.5)
        assert m["clip_recall_coverage"] == 0.0
        assert m["clip_recall_iou"] == 0.0

    def test_partial_match(self):
        df = make_frames("v1", 20, [(0, 10)])
        gt = build_gt_clips(df)
        selected_ids = np.arange(0, 6)
        m = compute_clip_level_metrics(gt, df, selected_ids, iou_threshold=0.3)
        assert m["clip_recall_coverage"] == 1.0
        assert m["clip_recall_iou"] == 1.0
        assert abs(m["mIoU"] - 0.5) < 1e-6

    def test_empty_predictions(self):
        df = make_frames("v1", 20, [(0, 10)])
        gt = build_gt_clips(df)
        m = compute_clip_level_metrics(gt, df, np.array([]), iou_threshold=0.5)
        assert m["clip_recall_coverage"] == 0.0
        assert m["clip_recall_iou"] == 0.0
        assert m["clip_precision"] == 0.0


class TestAnalyzeMisses:
    def test_fully_hit(self):
        df = make_frames("v1", 10, [(2, 7)])
        gt_clips = build_gt_clips(df)
        selected_ids = np.array([2, 3, 4, 5, 6, 7])
        analysis = analyze_temporal_misses(df, selected_ids, gt_clips)
        assert analysis["n_fully_hit"] == 1
        assert analysis["n_fully_missed"] == 0

    def test_fully_missed(self):
        df = make_frames("v1", 10, [(2, 7)])
        gt_clips = build_gt_clips(df)
        selected_ids = np.array([0, 1, 8, 9])
        analysis = analyze_temporal_misses(df, selected_ids, gt_clips)
        assert analysis["n_fully_hit"] == 0
        assert analysis["n_fully_missed"] == 1

    def test_sparse_miss(self):
        df = make_frames("v1", 10, [(2, 7)])
        gt_clips = build_gt_clips(df)
        selected_ids = np.array([2, 3, 5, 6, 7])  # missing frame 4
        analysis = analyze_temporal_misses(df, selected_ids, gt_clips)
        assert analysis["n_sparse_miss"] == 1

    def test_consecutive_miss(self):
        df = make_frames("v1", 10, [(2, 7)])
        gt_clips = build_gt_clips(df)
        selected_ids = np.array([2, 7])  # missing frames 3,4,5,6
        analysis = analyze_temporal_misses(df, selected_ids, gt_clips)
        assert analysis["n_consecutive_miss"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
