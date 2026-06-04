"""Synthetic label-level perturbation for simulating moving-camera degradation."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from pipeline.data_interface import FrameAnnotation, VideoAnnotation


@dataclass
class PerturbationConfig:
    proxy_noise_std: float = 1.5       # std of motion-conditioned proxy noise
    gap_probability: float = 0.05      # probability of a short positive gap per frame
    gap_max_length: int = 5            # max frames in a gap
    boundary_jitter_std: float = 3.0   # std of boundary jitter in frames
    visibility_drop_prob: float = 0.02 # probability of starting a visibility drop segment
    visibility_drop_length: int = 10   # frames of visibility drop
    visibility_drop_scale: float = 0.3 # scale factor during drop (multiply counts)


def apply_motion_conditioned_proxy_noise(
    counts: np.ndarray,
    rng: np.random.Generator,
    std: float = 1.5,
) -> np.ndarray:
    """Apply noise that scales with local motion (temporal derivative magnitude).

    Frames with larger changes get more noise (simulating proxy unreliability
    during camera motion).
    """
    if len(counts) < 2:
        noisy = counts + rng.normal(0, std, len(counts))
        return np.clip(noisy, 0, None)

    # Compute temporal derivative as motion proxy
    deriv = np.abs(np.diff(counts.astype(float)))
    # Pad to same length
    motion = np.concatenate([[deriv[0]], deriv])

    # Scale noise by motion magnitude
    motion_normalized = motion / (motion.mean() + 1e-6)
    noise = rng.normal(0, std, len(counts)) * (1.0 + 0.5 * motion_normalized)

    noisy = counts + noise
    return np.clip(np.round(noisy), 0, None).astype(int)


def apply_short_positive_gaps(
    labels: np.ndarray,
    rng: np.random.Generator,
    gap_prob: float = 0.05,
    max_gap_len: int = 5,
) -> np.ndarray:
    """Insert short gaps (False) inside positive runs.

    Simulates brief detection failures during motion.
    """
    result = labels.copy()
    i = 0
    while i < len(result):
        if result[i]:
            if rng.random() < gap_prob:
                gap_len = rng.integers(1, max_gap_len + 1)
                end = min(i + gap_len, len(result))
                result[i:end] = False
                i = end
                continue
        i += 1
    return result


def apply_boundary_jitter(
    clips: List[Tuple[int, int]],
    rng: np.random.Generator,
    jitter_std: float = 3.0,
    num_frames: int = 300,
) -> List[Tuple[int, int]]:
    """Jitter start and end boundaries of clips independently.

    Simulates imprecise temporal localization under camera motion.
    """
    jittered = []
    for start, end in clips:
        new_start = start + int(rng.normal(0, jitter_std))
        new_end = end + int(rng.normal(0, jitter_std))
        new_start = max(0, min(new_start, num_frames - 1))
        new_end = max(0, min(new_end, num_frames - 1))
        if new_end < new_start:
            new_start, new_end = new_end, new_start
        jittered.append((new_start, new_end))
    return jittered


def apply_visibility_drop_segments(
    counts: np.ndarray,
    rng: np.random.Generator,
    drop_prob: float = 0.02,
    drop_length: int = 10,
    drop_scale: float = 0.3,
) -> np.ndarray:
    """Simulate visibility drops (e.g., occlusion, blur during fast pan).

    Reduces vehicle counts in random segments.
    """
    result = counts.astype(float).copy()
    i = 0
    while i < len(result):
        if rng.random() < drop_prob:
            end = min(i + drop_length, len(result))
            # Apply a smooth drop
            t = np.linspace(0, 1, end - i)
            envelope = np.where(
                t < 0.3, t / 0.3,
                np.where(t > 0.7, (1 - t) / 0.3, 1.0)
            )
            result[i:end] *= (1.0 - (1.0 - drop_scale) * envelope)
            i = end
            continue
        i += 1
    return np.clip(np.round(result), 0, None).astype(int)


@dataclass
class PerturbedSequence:
    """Result of applying perturbations to a video annotation."""
    video_id: str
    original_counts: np.ndarray
    perturbed_counts: np.ndarray
    original_labels: np.ndarray  # frame-level Boolean: count >= K
    perturbed_labels: np.ndarray
    perturbed_frame_annotations: List[FrameAnnotation]
    num_oracle_calls: int  # how many frames needed oracle correction


def perturb_video(
    video: VideoAnnotation,
    K: int,
    config: PerturbationConfig,
    rng: np.random.Generator,
    boundary_clips: Optional[List[Tuple[int, int]]] = None,
) -> PerturbedSequence:
    """Apply all perturbation types to a video annotation.

    Returns perturbed counts, labels, and metadata about oracle calls needed.
    """
    original_counts = video.frame_counts()
    original_labels = (original_counts >= K).astype(bool)

    # 1. Motion-conditioned proxy noise on counts
    perturbed_counts = apply_motion_conditioned_proxy_noise(
        original_counts, rng, std=config.proxy_noise_std
    )

    # 2. Visibility drop segments
    perturbed_counts = apply_visibility_drop_segments(
        perturbed_counts, rng,
        drop_prob=config.visibility_drop_prob,
        drop_length=config.visibility_drop_length,
        drop_scale=config.visibility_drop_scale,
    )

    # Derive labels from perturbed counts
    perturbed_labels = (perturbed_counts >= K).astype(bool)

    # 3. Short positive gaps in label space
    perturbed_labels = apply_short_positive_gaps(
        perturbed_labels, rng,
        gap_prob=config.gap_probability,
        max_gap_len=config.gap_max_length,
    )

    # 4. Boundary jitter (applied to clip boundaries, affects label edges)
    if boundary_clips is not None:
        jittered = apply_boundary_jitter(
            boundary_clips, rng,
            jitter_std=config.boundary_jitter_std,
            num_frames=len(original_counts),
        )
        # Apply jitter: flip labels near jittered boundaries
        for (js, je), (os, oe) in zip(jittered, boundary_clips):
            # Frames between original and jittered start become unreliable
            for f in range(min(os, js), max(os, js)):
                if 0 <= f < len(perturbed_labels):
                    perturbed_labels[f] = not perturbed_labels[f]
            for f in range(min(oe, je), max(oe, je)):
                if 0 <= f < len(perturbed_labels):
                    perturbed_labels[f] = not perturbed_labels[f]

    # Count oracle calls: frames where perturbed != original
    num_oracle_calls = int(np.sum(perturbed_labels != original_labels))

    perturbed_frame_annotations = [
        FrameAnnotation(frame_idx=i, vehicle_count=int(perturbed_counts[i]))
        for i in range(len(perturbed_counts))
    ]

    return PerturbedSequence(
        video_id=video.video_id,
        original_counts=original_counts,
        perturbed_counts=perturbed_counts,
        original_labels=original_labels,
        perturbed_labels=perturbed_labels,
        perturbed_frame_annotations=perturbed_frame_annotations,
        num_oracle_calls=num_oracle_calls,
    )
