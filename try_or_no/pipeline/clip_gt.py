"""Clip ground truth construction from frame-level annotations."""

import json
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from pipeline.data_interface import VideoAnnotation


@dataclass
class Clip:
    video_id: str
    start_frame: int
    end_frame: int  # inclusive
    label: bool  # True = relevant, False = not relevant (for false-positive tracking)
    clip_id: str = ""

    @property
    def length(self) -> int:
        return self.end_frame - self.start_frame + 1

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "length": self.length,
            "label": self.label,
            "clip_id": self.clip_id,
        }


def build_ground_truth_clips(
    video: VideoAnnotation,
    K: int = 3,
    tau: int = 30,
    query_type: str = "count_gte",
) -> List[Clip]:
    """Convert frame-level Boolean labels into ground-truth clips.

    Query: count(vehicle) >= K for at least tau consecutive frames.

    Returns list of Clip objects for segments satisfying the query.
    """
    counts = video.frame_counts()

    if query_type == "count_gte":
        frame_labels = counts >= K
    else:
        raise ValueError(f"Unknown query type: {query_type}")

    # Find contiguous runs of True
    clips = []
    run_start = None
    for i, label in enumerate(frame_labels):
        if label and run_start is None:
            run_start = i
        elif not label and run_start is not None:
            run_length = i - run_start
            if run_length >= tau:
                clips.append(Clip(
                    video_id=video.video_id,
                    start_frame=run_start,
                    end_frame=i - 1,
                    label=True,
                    clip_id=f"{video.video_id}_{run_start}_{i-1}",
                ))
            run_start = None

    # Handle case where sequence ends in a True run
    if run_start is not None:
        run_length = len(frame_labels) - run_start
        if run_length >= tau:
            clips.append(Clip(
                video_id=video.video_id,
                start_frame=run_start,
                end_frame=len(frame_labels) - 1,
                label=True,
                clip_id=f"{video.video_id}_{run_start}_{len(frame_labels)-1}",
            ))

    return clips


def save_clips_jsonl(clips: List[Clip], output_path: str) -> None:
    """Save clips to JSONL format."""
    with open(output_path, "w") as f:
        for clip in clips:
            f.write(json.dumps(clip.to_dict()) + "\n")


def load_clips_jsonl(path: str) -> List[Clip]:
    """Load clips from JSONL format."""
    clips = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            clips.append(Clip(
                video_id=d["video_id"],
                start_frame=d["start_frame"],
                end_frame=d["end_frame"],
                label=d.get("label", True),
                clip_id=d.get("clip_id", ""),
            ))
    return clips
