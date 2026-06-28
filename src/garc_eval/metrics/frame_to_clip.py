"""Frame-to-clip bridge: convert frame-level selections/labels into temporal clips.

This module provides the core bridge between frame-level evaluation
and clip-level evaluation for temporal video data.

Key distinction:
- Frame recall: fraction of positive FRAMES selected
- Clip recall: fraction of positive CLIPS (temporal events) hit by candidate clips

A high frame recall does NOT guarantee high clip recall because:
1. Sparse positive frames across different clips won't form complete candidate clips
2. Missing boundary frames can reduce IoU below threshold
3. Short clips are harder to hit than long clips
"""

import numpy as np
import pandas as pd


def build_gt_clips(
    df: pd.DataFrame,
    min_clip_frames: int = 1,
    gap_tolerance: int = 0,
) -> pd.DataFrame:
    """Build ground-truth clips from oracle-positive frames.

    A GT clip is a contiguous run of positive frames (label=1),
    allowing gaps up to gap_tolerance frames.

    Parameters
    ----------
    df : DataFrame with columns: video_id, frame_idx, label, timestamp
    min_clip_frames : minimum clip length in frames
    gap_tolerance : max consecutive negative frames to merge across

    Returns
    -------
    DataFrame with columns: video_id, gt_clip_id, start_frame, end_frame,
                            start_time, end_time, duration_frames, duration_sec
    """
    clips = []
    clip_id = 0

    for vid, group in df.groupby("video_id"):
        group = group.sort_values("frame_idx").reset_index(drop=True)
        labels = group["label"].values
        frame_idxs = group["frame_idx"].values
        timestamps = group["timestamp"].values

        # Find contiguous positive runs
        positive_indices = np.where(labels == 1)[0]
        if len(positive_indices) == 0:
            continue

        # Build runs with gap tolerance
        start = positive_indices[0]
        end = positive_indices[0]

        for i in range(1, len(positive_indices)):
            idx = positive_indices[i]
            # Check if gap is within tolerance
            gap = idx - end - 1
            if gap <= gap_tolerance:
                end = idx
            else:
                # Flush current clip
                clip_len = end - start + 1
                if clip_len >= min_clip_frames:
                    clips.append({
                        "video_id": vid,
                        "gt_clip_id": clip_id,
                        "start_frame": int(frame_idxs[start]),
                        "end_frame": int(frame_idxs[end]),
                        "start_time": float(timestamps[start]),
                        "end_time": float(timestamps[end]),
                        "duration_frames": clip_len,
                        "duration_sec": float(timestamps[end] - timestamps[start]),
                    })
                    clip_id += 1
                start = idx
                end = idx

        # Flush last clip
        clip_len = end - start + 1
        if clip_len >= min_clip_frames:
            clips.append({
                "video_id": vid,
                "gt_clip_id": clip_id,
                "start_frame": int(frame_idxs[start]),
                "end_frame": int(frame_idxs[end]),
                "start_time": float(timestamps[start]),
                "end_time": float(timestamps[end]),
                "duration_frames": clip_len,
                "duration_sec": float(timestamps[end] - timestamps[start]),
            })
            clip_id += 1

    return pd.DataFrame(clips)


def build_candidate_clips(
    df: pd.DataFrame,
    selected_ids: np.ndarray,
    min_clip_frames: int = 1,
    gap_tolerance: int = 0,
) -> pd.DataFrame:
    """Build candidate clips from selected frame ids.

    A candidate clip is a contiguous run of selected frames,
    allowing gaps up to gap_tolerance frames.

    Parameters
    ----------
    df : DataFrame with columns: video_id, frame_idx, timestamp
    selected_ids : array of frame ids selected by the method
    min_clip_frames : minimum clip length in frames
    gap_tolerance : max consecutive non-selected frames to merge across

    Returns
    -------
    DataFrame with columns: video_id, pred_clip_id, start_frame, end_frame,
                            start_time, end_time, duration_frames, duration_sec
    """
    selected_set = set(int(sid) for sid in selected_ids)
    df_sel = df.copy()
    df_sel["selected"] = df_sel["id"].isin(selected_set).astype(int)

    clips = []
    clip_id = 0

    for vid, group in df_sel.groupby("video_id"):
        group = group.sort_values("frame_idx").reset_index(drop=True)
        selected = group["selected"].values
        frame_idxs = group["frame_idx"].values
        timestamps = group["timestamp"].values

        selected_indices = np.where(selected == 1)[0]
        if len(selected_indices) == 0:
            continue

        # Build runs with gap tolerance
        start = selected_indices[0]
        end = selected_indices[0]

        for i in range(1, len(selected_indices)):
            idx = selected_indices[i]
            gap = idx - end - 1
            if gap <= gap_tolerance:
                end = idx
            else:
                clip_len = end - start + 1
                if clip_len >= min_clip_frames:
                    clips.append({
                        "video_id": vid,
                        "pred_clip_id": clip_id,
                        "start_frame": int(frame_idxs[start]),
                        "end_frame": int(frame_idxs[end]),
                        "start_time": float(timestamps[start]),
                        "end_time": float(timestamps[end]),
                        "duration_frames": clip_len,
                        "duration_sec": float(timestamps[end] - timestamps[start]),
                    })
                    clip_id += 1
                start = idx
                end = idx

        clip_len = end - start + 1
        if clip_len >= min_clip_frames:
            clips.append({
                "video_id": vid,
                "pred_clip_id": clip_id,
                "start_frame": int(frame_idxs[start]),
                "end_frame": int(frame_idxs[end]),
                "start_time": float(timestamps[start]),
                "end_time": float(timestamps[end]),
                "duration_frames": clip_len,
                "duration_sec": float(timestamps[end] - timestamps[start]),
            })
            clip_id += 1

    return pd.DataFrame(clips)


def temporal_iou(
    start_a: float, end_a: float,
    start_b: float, end_b: float,
) -> float:
    """Compute temporal IoU between two intervals."""
    inter_start = max(start_a, start_b)
    inter_end = min(end_a, end_b)
    intersection = max(0.0, inter_end - inter_start)
    union = (end_a - start_a) + (end_b - start_b) - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def compute_clip_level_metrics(
    gt_clips: pd.DataFrame,
    df: pd.DataFrame,
    selected_ids: np.ndarray,
    coverage_threshold: float = 0.5,
    iou_threshold: float = 0.5,
) -> dict:
    """Compute clip-level retrieval metrics using frame coverage.

    Two metrics:
    1. Coverage-based clip recall: fraction of GT clips where at least
       coverage_threshold of positive frames are selected.
    2. IoU-based clip recall: fraction of GT clips with temporal IoU >= iou_threshold
       against candidate clips built from selected positive frames.

    Parameters
    ----------
    gt_clips : DataFrame of ground-truth clips
    df : DataFrame with video_id, frame_idx, timestamp, label, id
    selected_ids : array of selected frame ids
    coverage_threshold : min fraction of positive frames in GT clip that must be selected
    iou_threshold : min temporal IoU for IoU-based matching
    """
    if len(gt_clips) == 0:
        return {
            "clip_recall_coverage": 1.0,
            "clip_recall_iou": 1.0,
            "clip_precision": 1.0,
            "mIoU": 1.0,
            "mean_coverage": 1.0,
            "n_gt_clips": 0,
            "n_gt_hit_coverage": 0,
            "n_gt_hit_iou": 0,
            "gt_clip_details": [],
        }

    selected_set = set(int(sid) for sid in selected_ids)

    gt_details = []
    for _, gt in gt_clips.iterrows():
        vid = gt["video_id"]
        # Get all positive frames in this GT clip
        gt_frames = df[
            (df["video_id"] == vid) &
            (df["frame_idx"] >= gt["start_frame"]) &
            (df["frame_idx"] <= gt["end_frame"]) &
            (df["label"] == 1)
        ]

        n_positive = len(gt_frames)
        if n_positive == 0:
            coverage = 0.0
        else:
            n_selected = sum(1 for fid in gt_frames["id"] if int(fid) in selected_set)
            coverage = n_selected / n_positive

        gt_details.append({
            "gt_clip_id": gt["gt_clip_id"],
            "video_id": vid,
            "duration_frames": gt["duration_frames"],
            "duration_sec": gt["duration_sec"],
            "n_positive_frames": n_positive,
            "n_selected_positive": int(coverage * n_positive),
            "coverage": coverage,
            "hit_coverage": coverage >= coverage_threshold,
        })

    n_gt = len(gt_clips)
    gt_hit_coverage = sum(1 for d in gt_details if d["hit_coverage"])
    mean_coverage = np.mean([d["coverage"] for d in gt_details])

    clip_recall_coverage = gt_hit_coverage / n_gt if n_gt > 0 else 1.0

    # IoU-based: build candidate clips from selected positive frames only
    pos_selected_ids = np.array([
        int(fid) for fid in selected_ids
        if int(fid) in set(df[df["label"] == 1]["id"].values)
    ])
    pred_clips = build_candidate_clips(df, pos_selected_ids, min_clip_frames=1, gap_tolerance=0)

    # IoU matching
    gt_hit_iou = 0
    ious = []
    for _, gt in gt_clips.iterrows():
        best_iou = 0.0
        for _, pred in pred_clips.iterrows():
            if pred["video_id"] != gt["video_id"]:
                continue
            iou = temporal_iou(
                gt["start_time"], gt["end_time"],
                pred["start_time"], pred["end_time"],
            )
            best_iou = max(best_iou, iou)
        ious.append(best_iou)
        if best_iou >= iou_threshold:
            gt_hit_iou += 1

    clip_recall_iou = gt_hit_iou / n_gt if n_gt > 0 else 1.0
    mIoU = np.mean(ious) if ious else 0.0

    # Clip precision: fraction of pred clips that contain at least one positive frame
    n_pred_hit = 0
    for _, pred in pred_clips.iterrows():
        pred_frames = df[
            (df["video_id"] == pred["video_id"]) &
            (df["frame_idx"] >= pred["start_frame"]) &
            (df["frame_idx"] <= pred["end_frame"])
        ]
        if (pred_frames["label"] == 1).any():
            n_pred_hit += 1

    clip_precision = n_pred_hit / len(pred_clips) if len(pred_clips) > 0 else 0.0

    return {
        "clip_recall_coverage": clip_recall_coverage,
        "clip_recall_iou": clip_recall_iou,
        "clip_precision": clip_precision,
        "mIoU": mIoU,
        "mean_coverage": mean_coverage,
        "n_gt_clips": n_gt,
        "n_gt_hit_coverage": gt_hit_coverage,
        "n_gt_hit_iou": gt_hit_iou,
        "n_pred_clips": len(pred_clips),
        "gt_clip_details": gt_details,
    }


def compute_frame_level_metrics(
    df: pd.DataFrame,
    selected_ids: np.ndarray,
) -> dict:
    """Compute frame-level retrieval metrics."""
    selected_set = set(int(sid) for sid in selected_ids)
    labels = df["label"].values
    ids = df["id"].values

    total_positive = int(labels.sum())
    selected_mask = np.array([int(fid) in selected_set for fid in ids])
    true_positive = int(labels[selected_mask].sum())

    frame_recall = true_positive / total_positive if total_positive > 0 else 0.0
    frame_precision = true_positive / len(selected_ids) if len(selected_ids) > 0 else 0.0

    return {
        "frame_recall": frame_recall,
        "frame_precision": frame_precision,
        "selected_n": len(selected_ids),
        "total_positive": total_positive,
        "true_positive": true_positive,
        "total_n": len(df),
    }


def analyze_temporal_misses(
    df: pd.DataFrame,
    selected_ids: np.ndarray,
    gt_clips: pd.DataFrame,
) -> dict:
    """Analyze temporal miss patterns.

    Distinguishes:
    - Sparse misses: isolated positive frames not selected (within otherwise hit clips)
    - Consecutive misses: runs of positive frames not selected (entire clip missed)
    - Boundary misses: positive frames at clip boundaries not selected
    """
    selected_set = set(int(sid) for sid in selected_ids)
    miss_details = []

    for _, gt in gt_clips.iterrows():
        vid = gt["video_id"]
        gt_frames = df[
            (df["video_id"] == vid) &
            (df["frame_idx"] >= gt["start_frame"]) &
            (df["frame_idx"] <= gt["end_frame"]) &
            (df["label"] == 1)
        ]

        if len(gt_frames) == 0:
            continue

        # Classify each frame in the GT clip
        n_frames = len(gt_frames)
        n_selected = sum(1 for fid in gt_frames["id"] if int(fid) in selected_set)
        n_missed = n_frames - n_selected

        # Find runs of missed frames
        missed_runs = []
        run_start = None
        run_len = 0
        for _, row in gt_frames.iterrows():
            if int(row["id"]) not in selected_set:
                if run_start is None:
                    run_start = row["frame_idx"]
                run_len += 1
            else:
                if run_len > 0:
                    missed_runs.append((run_start, run_start + run_len - 1, run_len))
                run_start = None
                run_len = 0
        if run_len > 0:
            missed_runs.append((run_start, run_start + run_len - 1, run_len))

        # Classify miss type
        if n_missed == 0:
            miss_type = "fully_hit"
        elif n_selected == 0:
            miss_type = "fully_missed"
        elif n_missed <= 2:
            miss_type = "sparse_miss"
        elif any(r[2] >= 3 for r in missed_runs):
            miss_type = "consecutive_miss"
        else:
            miss_type = "boundary_miss"

        miss_details.append({
            "gt_clip_id": gt["gt_clip_id"],
            "video_id": vid,
            "duration_frames": gt["duration_frames"],
            "n_positive_frames": n_frames,
            "n_selected": n_selected,
            "n_missed": n_missed,
            "miss_type": miss_type,
            "n_missed_runs": len(missed_runs),
            "longest_miss_run": max((r[2] for r in missed_runs), default=0),
        })

    return {
        "miss_details": miss_details,
        "n_fully_hit": sum(1 for m in miss_details if m["miss_type"] == "fully_hit"),
        "n_fully_missed": sum(1 for m in miss_details if m["miss_type"] == "fully_missed"),
        "n_sparse_miss": sum(1 for m in miss_details if m["miss_type"] == "sparse_miss"),
        "n_consecutive_miss": sum(1 for m in miss_details if m["miss_type"] == "consecutive_miss"),
        "n_boundary_miss": sum(1 for m in miss_details if m["miss_type"] == "boundary_miss"),
    }
