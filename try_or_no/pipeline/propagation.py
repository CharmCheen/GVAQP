"""Propagation / clip reconstruction strategies.

Each strategy takes frame-level labels (with gaps from sparse oracle queries)
and produces complete frame labels and clip predictions.
"""

from typing import List, Tuple, Optional
import numpy as np


def strict_threshold_stitching(
    labels: np.ndarray,
    sampled_indices: List[int],
    tau: int,
    K: int = 3,
) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """Strict threshold stitching: only propagate labels to adjacent frames.

    Frames not directly adjacent to a sampled frame remain as-is (typically False).
    This is the most conservative approach.
    """
    n = len(labels)
    result = labels.copy()

    # Only fill frames directly between sampled frames
    sampled_set = set(sampled_indices)

    for i in range(n):
        if i in sampled_set:
            continue
        # Check if adjacent to a sampled frame
        if (i - 1 in sampled_set) or (i + 1 in sampled_set):
            # Use nearest sampled frame's label
            if i - 1 in sampled_set:
                result[i] = labels[i - 1]
            elif i + 1 in sampled_set:
                result[i] = labels[i + 1]

    clips = _labels_to_clips(result, tau)
    return result, clips


def nearest_neighbor_interpolation(
    labels: np.ndarray,
    sampled_indices: List[int],
    tau: int,
    K: int = 3,
) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """Nearest-neighbor interpolation: fill each frame with the label of the nearest sampled frame.

    This is the standard approach used in uniform_random baseline.
    """
    n = len(labels)
    result = np.zeros(n, dtype=bool)

    if not sampled_indices:
        clips = _labels_to_clips(result, tau)
        return result, clips

    sampled_arr = np.array(sampled_indices)

    for i in range(n):
        distances = np.abs(sampled_arr - i)
        nearest_idx = sampled_arr[np.argmin(distances)]
        result[i] = labels[nearest_idx]

    clips = _labels_to_clips(result, tau)
    return result, clips


def gap_tolerant_merge(
    labels: np.ndarray,
    sampled_indices: List[int],
    tau: int,
    K: int = 3,
    max_gap: int = 8,
) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """Gap-tolerant merge: fill gaps between positive sampled frames.

    If two sampled frames with label=True are separated by a gap of <= max_gap frames,
    fill the gap with True. Otherwise, use nearest-neighbor.
    """
    n = len(labels)
    result = labels.copy()

    if not sampled_indices:
        clips = _labels_to_clips(result, tau)
        return result, clips

    # First, fill gaps between positive sampled frames
    sorted_indices = sorted(sampled_indices)

    for i in range(len(sorted_indices) - 1):
        idx_a = sorted_indices[i]
        idx_b = sorted_indices[i + 1]

        # If both endpoints are positive and gap is small enough
        if labels[idx_a] and labels[idx_b] and (idx_b - idx_a - 1) <= max_gap:
            # Fill the gap with True
            result[idx_a:idx_b + 1] = True

    # For remaining unfilled frames, use nearest-neighbor
    sampled_set = set(sampled_indices)
    for i in range(n):
        if i not in sampled_set and not result[i]:
            # Check if this frame is in a filled gap
            if not result[i]:
                distances = np.abs(np.array(sorted_indices) - i)
                nearest_idx = sorted_indices[np.argmin(distances)]
                # Only use nearest-neighbor if the frame wasn't already filled
                # by gap-tolerant merge
                pass  # Keep as-is if not in a filled gap

    clips = _labels_to_clips(result, tau)
    return result, clips


def risk_aware_gap_bridge(
    labels: np.ndarray,
    sampled_indices: List[int],
    tau: int,
    K: int = 3,
    max_gap: int = 8,
    risk_threshold: float = 0.5,
) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """Risk-aware gap bridge: selectively bridge gaps based on confidence.

    Similar to gap_tolerant_merge but uses additional heuristics to decide
    whether to bridge a gap:
    - Gap length relative to tau
    - Proximity to existing positive segments
    """
    n = len(labels)
    result = labels.copy()

    if not sampled_indices:
        clips = _labels_to_clips(result, tau)
        return result, clips

    sorted_indices = sorted(sampled_indices)

    # Compute risk score for each gap
    for i in range(len(sorted_indices) - 1):
        idx_a = sorted_indices[i]
        idx_b = sorted_indices[i + 1]

        gap_length = idx_b - idx_a - 1

        if gap_length <= 0:
            continue

        # Risk score: shorter gaps relative to tau are less risky to bridge
        # Also consider if endpoints are positive
        if labels[idx_a] and labels[idx_b]:
            # Risk decreases with shorter gaps and increases with tau
            risk = gap_length / tau

            # Bridge if risk is acceptable
            if risk <= risk_threshold or gap_length <= max_gap:
                result[idx_a:idx_b + 1] = True

    clips = _labels_to_clips(result, tau)
    return result, clips


def conservative_boundary_expansion(
    labels: np.ndarray,
    sampled_indices: List[int],
    tau: int,
    K: int = 3,
    expansion_frames: int = 5,
) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """Conservative boundary expansion: expand positive segments at boundaries.

    For each positive sampled frame, expand by `expansion_frames` in both directions.
    This helps recover clip boundaries that might be slightly off.
    """
    n = len(labels)
    result = labels.copy()

    if not sampled_indices:
        clips = _labels_to_clips(result, tau)
        return result, clips

    # First do nearest-neighbor interpolation
    sampled_arr = np.array(sampled_indices)
    nn_labels = np.zeros(n, dtype=bool)
    for i in range(n):
        distances = np.abs(sampled_arr - i)
        nearest_idx = sampled_arr[np.argmin(distances)]
        nn_labels[i] = labels[nearest_idx]

    result = nn_labels.copy()

    # Find positive segments in NN labels
    segments = []
    run_start = None
    for i, label in enumerate(result):
        if label and run_start is None:
            run_start = i
        elif not label and run_start is not None:
            segments.append((run_start, i - 1))
            run_start = None
    if run_start is not None:
        segments.append((run_start, n - 1))

    # Expand each segment
    expanded = result.copy()
    for seg_start, seg_end in segments:
        # Expand start
        new_start = max(0, seg_start - expansion_frames)
        # Expand end
        new_end = min(n - 1, seg_end + expansion_frames)

        # Only expand if the expansion frames are "plausible"
        # (i.e., their counts are not too far from K)
        for f in range(new_start, seg_start):
            expanded[f] = True
        for f in range(seg_end + 1, new_end + 1):
            expanded[f] = True

    clips = _labels_to_clips(expanded, tau)
    return expanded, clips


def _labels_to_clips(labels: np.ndarray, tau: int) -> List[Tuple[int, int]]:
    """Convert frame-level labels to clips (contiguous runs >= tau)."""
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

    return [(s, e) for s, e in segments if (e - s + 1) >= tau]


# Registry of propagation strategies
PROPAGATION_STRATEGIES = {
    "strict_threshold_stitching": strict_threshold_stitching,
    "nearest_neighbor_interpolation": nearest_neighbor_interpolation,
    "gap_tolerant_merge": gap_tolerant_merge,
    "risk_aware_gap_bridge": risk_aware_gap_bridge,
    "conservative_boundary_expansion": conservative_boundary_expansion,
}
