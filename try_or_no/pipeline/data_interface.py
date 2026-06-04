"""Dataset abstraction for frame-level annotations."""

import json
import pathlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import numpy as np


@dataclass
class FrameAnnotation:
    frame_idx: int
    vehicle_count: int
    boxes: List[Dict[str, float]] = field(default_factory=list)  # optional bbox info


@dataclass
class VideoAnnotation:
    video_id: str
    frames: List[FrameAnnotation]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_frames(self) -> int:
        return len(self.frames)

    def frame_counts(self) -> np.ndarray:
        return np.array([f.vehicle_count for f in self.frames])


def generate_synthetic_sequence(
    video_id: str,
    num_frames: int = 300,
    rng: Optional[np.random.Generator] = None,
    base_count_mean: float = 5.0,
    activity_density: float = 0.03,
) -> VideoAnnotation:
    """Generate a synthetic annotation sequence with realistic temporal structure.

    Creates a background of base_count_mean vehicles, then inserts activity
    bursts where count >= K for contiguous stretches.
    """
    if rng is None:
        rng = np.random.default_rng()

    # Background count (slowly varying)
    noise = rng.normal(0, 1.5, num_frames)
    background = base_count_mean + np.cumsum(noise) * 0.05
    background = np.clip(background, 0, 20)

    # Activity bursts: randomly place segments where extra vehicles appear
    counts = background.copy()
    # Place ~3-8 burst segments per sequence
    num_bursts = rng.integers(3, 9)
    for _ in range(num_bursts):
        start = rng.integers(0, num_frames - 40)
        length = rng.integers(20, 80)
        extra = rng.uniform(2, 8)
        end = min(start + length, num_frames)
        # Ramp up and ramp down
        ramp = np.concatenate([
            np.linspace(0, 1, min(5, (end - start) // 3)),
            np.ones(max(0, end - start - 2 * 5)),
            np.linspace(1, 0, min(5, (end - start) // 3)),
        ])
        if len(ramp) < end - start:
            ramp = np.pad(ramp, (0, end - start - len(ramp)), mode='edge')
        ramp = ramp[:end - start]
        counts[start:end] += extra * ramp

    counts = np.round(np.clip(counts, 0, 30)).astype(int)

    frames = [
        FrameAnnotation(frame_idx=i, vehicle_count=int(counts[i]))
        for i in range(num_frames)
    ]
    return VideoAnnotation(video_id=video_id, frames=frames)


def load_ua_detrac_sample(
    annotation_dir: str,
    max_videos: int = 20,
) -> List[VideoAnnotation]:
    """Attempt to load UA-DETRAC-style annotations from a directory.

    Expects XML files with frame-level vehicle counts.
    Falls back to synthetic if directory doesn't exist or is empty.
    """
    ann_path = pathlib.Path(annotation_dir)
    if not ann_path.exists():
        return []

    xml_files = sorted(ann_path.glob("*.xml"))[:max_videos]
    if not xml_files:
        return []

    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        return []

    videos = []
    for xf in xml_files:
        tree = ET.parse(xf)
        root = tree.getroot()
        vid_id = xf.stem
        frames = []
        for frame_elem in root.iter("frame"):
            fidx = int(frame_elem.get("num", 0))
            vehicle_count = 0
            for target in frame_elem.iter("target"):
                vehicle_count += 1
            frames.append(FrameAnnotation(frame_idx=fidx, vehicle_count=vehicle_count))
        if frames:
            videos.append(VideoAnnotation(video_id=vid_id, frames=frames))
    return videos


def load_or_generate_dataset(
    annotation_dir: Optional[str] = None,
    sample_size: int = 20,
    num_frames: int = 300,
    seed: int = 42,
) -> List[VideoAnnotation]:
    """Load real annotations or fall back to synthetic generation."""
    if annotation_dir:
        videos = load_ua_detrac_sample(annotation_dir, max_videos=sample_size)
        if videos:
            return videos[:sample_size]

    rng = np.random.default_rng(seed)
    videos = []
    for i in range(sample_size):
        vid = generate_synthetic_sequence(
            video_id=f"synthetic_{i:03d}",
            num_frames=num_frames,
            rng=rng,
        )
        videos.append(vid)
    return videos
