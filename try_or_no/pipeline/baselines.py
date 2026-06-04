"""Baseline methods for clip-level query under perturbation."""

from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np

from pipeline.clip_gt import Clip
from pipeline.perturbation import PerturbedSequence


@dataclass
class BaselineResult:
    method: str
    predicted_clips: List[Tuple[int, int]]  # (start, end) inclusive
    oracle_calls: int
    frame_labels: np.ndarray  # predicted frame-level labels


def full_oracle_baseline(
    perturbed: PerturbedSequence,
    K: int,
    tau: int,
) -> BaselineResult:
    """Full oracle: query every frame (ground truth known).

    This is the upper bound - perfect knowledge of true labels.
    """
    true_labels = perturbed.original_labels
    clips = _labels_to_clips(true_labels, tau)
    return BaselineResult(
        method="full_oracle",
        predicted_clips=clips,
        oracle_calls=len(true_labels),
        frame_labels=true_labels.copy(),
    )


def fixed_rate_sampling_baseline(
    perturbed: PerturbedSequence,
    K: int,
    tau: int,
    sample_rate: float = 0.1,
    rng: Optional[np.random.Generator] = None,
) -> BaselineResult:
    """Fixed-rate sampling: query every Nth frame, fill gaps by propagation.

    Budget expressed as fraction of total frames.
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(perturbed.original_labels)
    stride = max(1, int(1.0 / sample_rate))

    # Sample frames at fixed intervals
    sampled_indices = list(range(0, n, stride))
    oracle_calls = len(sampled_indices)

    # Build frame labels by nearest-neighbor interpolation
    frame_labels = np.zeros(n, dtype=bool)
    for idx in sampled_indices:
        frame_labels[idx] = perturbed.original_labels[idx]

    # Forward-fill between samples
    for i in range(n):
        if i not in sampled_indices:
            # Find nearest sampled frame before
            nearest_before = (i // stride) * stride
            frame_labels[i] = frame_labels[nearest_before]

    clips = _labels_to_clips(frame_labels, tau)
    return BaselineResult(
        method="fixed_rate",
        predicted_clips=clips,
        oracle_calls=oracle_calls,
        frame_labels=frame_labels,
    )


def uniform_random_sampling_baseline(
    perturbed: PerturbedSequence,
    K: int,
    tau: int,
    budget: float = 0.1,
    rng: Optional[np.random.Generator] = None,
) -> BaselineResult:
    """Uniform random sampling: randomly select budget fraction of frames.

    Then propagate labels via nearest-neighbor.
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(perturbed.original_labels)
    num_samples = max(1, int(n * budget))

    sampled_indices = sorted(rng.choice(n, size=num_samples, replace=False))
    oracle_calls = len(sampled_indices)

    # Query sampled frames (oracle)
    frame_labels = np.zeros(n, dtype=bool)
    for idx in sampled_indices:
        frame_labels[idx] = perturbed.original_labels[idx]

    # Nearest-neighbor fill
    all_indices = np.arange(n)
    for i in range(n):
        if i not in sampled_indices:
            distances = np.abs(np.array(sampled_indices) - i)
            nearest = sampled_indices[np.argmin(distances)]
            frame_labels[i] = frame_labels[nearest]

    clips = _labels_to_clips(frame_labels, tau)
    return BaselineResult(
        method="uniform_random",
        predicted_clips=clips,
        oracle_calls=oracle_calls,
        frame_labels=frame_labels,
    )


def proxy_threshold_baseline(
    perturbed: PerturbedSequence,
    K: int,
    tau: int,
    budget: float = 0.1,
    rng: Optional[np.random.Generator] = None,
) -> BaselineResult:
    """Proxy-threshold baseline: use perturbed counts with adjusted threshold.

    Query frames where proxy (perturbed count) is close to threshold K,
    using oracle budget for uncertain frames.
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(perturbed.perturbed_counts)
    num_oracle_budget = max(1, int(n * budget))

    # Proxy decision: perturbed count vs adjusted threshold
    # Use a slightly lower threshold to increase recall
    proxy_labels = perturbed.perturbed_counts >= max(0, K - 1)

    # Identify uncertain frames (close to threshold)
    uncertainty = np.abs(perturbed.perturbed_counts.astype(float) - K)
    uncertain_indices = np.argsort(uncertainty)[:num_oracle_budget]

    # Query oracle for uncertain frames
    frame_labels = proxy_labels.copy()
    oracle_calls = 0
    for idx in uncertain_indices:
        frame_labels[idx] = perturbed.original_labels[idx]
        oracle_calls += 1

    clips = _labels_to_clips(frame_labels, tau)
    return BaselineResult(
        method="proxy_threshold",
        predicted_clips=clips,
        oracle_calls=oracle_calls,
        frame_labels=frame_labels,
    )


def arc_temporal_clustering_baseline(
    perturbed: PerturbedSequence,
    K: int,
    tau: int,
    budget: float = 0.1,
    cluster_merge_gap: int = 10,
    refinement_fraction: float = 0.5,
    rng: Optional[np.random.Generator] = None,
) -> BaselineResult:
    """ARC-style simplified temporal clustering + refinement baseline.

    1. Use proxy to identify candidate positive segments.
    2. Merge nearby segments (within cluster_merge_gap frames).
    3. Use oracle budget to refine boundaries of top segments.
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(perturbed.perturbed_counts)
    num_oracle_budget = max(1, int(n * budget))

    # Step 1: Proxy-based candidate segments
    proxy_positive = perturbed.perturbed_counts >= K
    candidate_segments = _labels_to_segment_list(proxy_positive)

    # Step 2: Merge nearby segments
    if len(candidate_segments) > 1:
        merged = [candidate_segments[0]]
        for start, end in candidate_segments[1:]:
            prev_start, prev_end = merged[-1]
            if start - prev_end <= cluster_merge_gap:
                merged[-1] = (prev_start, end)
            else:
                merged.append((start, end))
        candidate_segments = merged

    # Step 3: Refine boundaries using oracle budget
    frame_labels = proxy_positive.copy()
    oracle_calls = 0
    refine_budget = int(num_oracle_budget * refinement_fraction)
    per_segment_budget = max(2, refine_budget // max(1, len(candidate_segments)))

    for seg_start, seg_end in candidate_segments:
        if oracle_calls >= refine_budget:
            break
        # Query boundary frames
        boundary_frames = []
        for offset in range(min(5, per_segment_budget // 2)):
            f_start = seg_start + offset
            f_end = seg_end - offset
            if f_start <= seg_end and oracle_calls < refine_budget:
                boundary_frames.append(f_start)
            if f_end >= seg_start and oracle_calls < refine_budget:
                boundary_frames.append(f_end)

        for f in boundary_frames:
            if 0 <= f < n:
                frame_labels[f] = perturbed.original_labels[f]
                oracle_calls += 1

    # Use remaining budget for random refinement
    remaining_budget = num_oracle_budget - oracle_calls
    if remaining_budget > 0:
        # Focus on frames near segment boundaries
        all_boundary_frames = set()
        for seg_start, seg_end in candidate_segments:
            for offset in range(10):
                all_boundary_frames.add(max(0, seg_start - offset))
                all_boundary_frames.add(min(n - 1, seg_end + offset))

        boundary_list = sorted(all_boundary_frames)
        if boundary_list:
            num_refine = min(remaining_budget, len(boundary_list))
            refine_indices = rng.choice(
                boundary_list, size=num_refine, replace=False
            )
            for idx in refine_indices:
                frame_labels[idx] = perturbed.original_labels[idx]
                oracle_calls += 1

    clips = _labels_to_clips(frame_labels, tau)
    return BaselineResult(
        method="arc_clustering",
        predicted_clips=clips,
        oracle_calls=oracle_calls,
        frame_labels=frame_labels,
    )


def _labels_to_clips(labels: np.ndarray, tau: int) -> List[Tuple[int, int]]:
    """Convert frame-level labels to clips (contiguous runs >= tau)."""
    segments = _labels_to_segment_list(labels)
    return [(s, e) for s, e in segments if (e - s + 1) >= tau]


def _labels_to_segment_list(labels: np.ndarray) -> List[Tuple[int, int]]:
    """Convert Boolean labels to list of (start, end) inclusive segments."""
    segments = []
    run_start = None
    for i, label in enumerate(labels):
        if label and run_start is None:
            run_start = i
        elif not label and run_start is not None:
            segments.append((run_start, i - 1))
            run_start = None
    if run_start is not None:
        segments.append((run_start, len(labels) - 1))
    return segments
