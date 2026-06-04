"""Harder synthetic perturbation regimes for stress-testing clip reconstruction.

These regimes are designed to break nearest-neighbor interpolation and expose
real failure modes in relevant clip query processing.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import numpy as np

from pipeline.perturbation import PerturbedSequence
from pipeline.data_interface import VideoAnnotation, FrameAnnotation


@dataclass
class HardPerturbationConfig:
    """Configuration for hard perturbation regimes."""
    regime: str = "mixed_hard"  # one of: regime_shift, long_gap, close_merge, boundary_ambig, mixed_hard

    # regime_shift_proxy_noise
    regime_length: int = 50        # frames per regime segment
    fn_rate: float = 0.4           # false negative rate in high-risk segments
    fp_rate: float = 0.2           # false positive rate in high-risk segments
    transition_sharpness: float = 0.8  # 0=gradual, 1=sharp transition

    # long_visibility_gaps
    gap_lengths: List[int] = field(default_factory=lambda: [3, 5, 10, 20, 40])
    gap_positions: List[str] = field(default_factory=lambda: ["interior", "boundary", "tau_critical"])

    # close_clip_merge_cases
    negative_gap_lengths: List[int] = field(default_factory=lambda: [2, 5, 10, 15, 20, 30])

    # boundary_ambiguity
    boundary_noise_width: int = 10   # frames of noise around boundaries
    boundary_score_fluctuation: float = 0.3  # magnitude of score fluctuation

    # general
    base_noise_std: float = 1.0

    # oracle noise: simulates unreliable oracle in difficult conditions
    # This is the key addition: the oracle itself can be wrong
    oracle_noise_rate: float = 0.0   # probability oracle returns wrong label
    oracle_noise_regime_only: bool = True  # only apply oracle noise in high-risk regimes


def apply_regime_shift_proxy_noise(
    labels: np.ndarray,
    rng: np.random.Generator,
    regime_length: int = 50,
    fn_rate: float = 0.4,
    fp_rate: float = 0.2,
    transition_sharpness: float = 0.8,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply piecewise proxy reliability changes across time.

    Creates alternating low-risk (reliable) and high-risk (unreliable) segments.
    In high-risk segments, proxy has systematic false negatives or false positives.

    Returns:
        perturbed_labels: labels after regime-shift noise
        risk_mask: boolean array indicating high-risk frames
    """
    n = len(labels)
    perturbed = labels.copy()
    risk_mask = np.zeros(n, dtype=bool)

    # Create regime boundaries
    num_regimes = max(1, n // regime_length)
    regime_starts = np.linspace(0, n, num_regimes + 1, dtype=int)

    for i in range(len(regime_starts) - 1):
        start, end = regime_starts[i], regime_starts[i + 1]
        segment_len = end - start

        # Alternate: even = low-risk, odd = high-risk
        if i % 2 == 1:
            # High-risk segment
            risk_mask[start:end] = True

            # Apply transition smoothing at boundaries
            if transition_sharpness < 1.0:
                transition_len = int(segment_len * (1 - transition_sharpness) / 2)
                transition_len = max(1, transition_len)
            else:
                transition_len = 0

            for j in range(start, end):
                # Compute local risk weight (higher in middle of segment)
                dist_to_edge = min(j - start, end - j - 1)
                if transition_len > 0 and dist_to_edge < transition_len:
                    risk_weight = dist_to_edge / transition_len
                else:
                    risk_weight = 1.0

                # Apply false negatives (positive -> negative)
                if labels[j] and rng.random() < fn_rate * risk_weight:
                    perturbed[j] = False
                # Apply false negatives (negative -> positive)
                elif not labels[j] and rng.random() < fp_rate * risk_weight:
                    perturbed[j] = True

    return perturbed, risk_mask


def apply_long_visibility_gaps(
    labels: np.ndarray,
    rng: np.random.Generator,
    gap_lengths: List[int] = [3, 5, 10, 20, 40],
    gap_positions: List[str] = ["interior", "boundary", "tau_critical"],
) -> Tuple[np.ndarray, List[Dict]]:
    """Insert long visibility gaps into positive clips.

    Supports gaps at different positions:
    - interior: middle of a positive run
    - boundary: near start/end of a positive run
    - tau_critical: near the tau-threshold (where clip length ≈ tau)

    Returns:
        perturbed_labels: labels with gaps inserted
        gap_info: list of dicts describing each gap
    """
    n = len(labels)
    perturbed = labels.copy()
    gap_info = []

    # Find positive segments
    segments = []
    run_start = None
    for i, label in enumerate(labels):
        if label and run_start is None:
            run_start = i
        elif not label and run_start is not None:
            segments.append((run_start, i - 1))
            run_start = None
    if run_start is not None:
        segments.append((run_start, n - 1))

    for seg_start, seg_end in segments:
        seg_len = seg_end - seg_start + 1

        # Choose a gap length that fits in this segment
        valid_gaps = [g for g in gap_lengths if g < seg_len - 2]
        if not valid_gaps:
            continue

        gap_len = rng.choice(valid_gaps)

        # Choose position
        position = rng.choice(gap_positions)

        if position == "interior":
            # Place gap in the middle third
            mid = (seg_start + seg_end) // 2
            gap_start = mid - gap_len // 2
        elif position == "boundary":
            # Place gap near start or end
            if rng.random() < 0.5:
                gap_start = seg_start + 1
            else:
                gap_start = seg_end - gap_len - 1
        elif position == "tau_critical":
            # Place gap where it might cause clip to drop below tau
            # If segment is just barely above tau, place gap to test boundary
            gap_start = seg_start + max(1, seg_len // 3)
        else:
            gap_start = seg_start + rng.integers(1, max(2, seg_len - gap_len))

        gap_start = max(seg_start + 1, min(gap_start, seg_end - gap_len - 1))
        gap_end = gap_start + gap_len

        # Apply gap
        perturbed[gap_start:gap_end] = False

        gap_info.append({
            "segment": (seg_start, seg_end),
            "gap_start": gap_start,
            "gap_end": gap_end - 1,
            "gap_length": gap_len,
            "position": position,
            "seg_length": seg_len,
        })

    return perturbed, gap_info


def apply_close_clip_merge_cases(
    counts: np.ndarray,
    rng: np.random.Generator,
    K: int,
    negative_gap_lengths: List[int] = [2, 5, 10, 15, 20, 30],
    tau: int = 30,
) -> Tuple[np.ndarray, List[Dict]]:
    """Generate two true clips separated by a short negative gap.

    Creates synthetic scenarios where two positive clips are close together,
    testing whether reconstruction wrongly merges them.

    Returns:
        modified_counts: counts with injected close-clip pairs
        merge_info: list of dicts describing each pair
    """
    n = len(counts)
    modified = counts.copy()
    merge_info = []

    # Find existing positive segments
    labels = (counts >= K)
    segments = []
    run_start = None
    for i, label in enumerate(labels):
        if label and run_start is None:
            run_start = i
        elif not label and run_start is not None:
            segments.append((run_start, i - 1))
            run_start = None
    if run_start is not None:
        segments.append((run_start, n - 1))

    # For each segment, try to create a close-clip pair
    for seg_start, seg_end in segments:
        seg_len = seg_end - seg_start + 1

        # Only process segments that are long enough to split
        if seg_len < tau * 2 + 10:
            continue

        # Choose a gap length
        gap_len = rng.choice(negative_gap_lengths)

        # Split the segment into two clips with a gap
        split_point = seg_start + tau + gap_len // 2 + rng.integers(0, 5)

        # Make the gap region negative (count < K)
        gap_start = split_point - gap_len // 2
        gap_end = gap_start + gap_len

        if gap_end >= seg_end:
            continue

        # Store original counts in gap, then reduce
        original_gap_counts = modified[gap_start:gap_end].copy()
        modified[gap_start:gap_end] = rng.integers(0, max(1, K - 1), size=gap_len)

        merge_info.append({
            "original_segment": (seg_start, seg_end),
            "gap_start": gap_start,
            "gap_end": gap_end - 1,
            "gap_length": gap_len,
            "clip1": (seg_start, gap_start - 1),
            "clip2": (gap_end, seg_end),
            "clip1_len": gap_start - seg_start,
            "clip2_len": seg_end - gap_end + 1,
        })

    return modified, merge_info


def apply_boundary_ambiguity(
    labels: np.ndarray,
    rng: np.random.Generator,
    noise_width: int = 10,
    score_fluctuation: float = 0.3,
) -> Tuple[np.ndarray, np.ndarray]:
    """Add noisy proxy scores around clip start/end boundaries.

    Creates zones of uncertainty around boundaries where labels may flip.

    Returns:
        perturbed_labels: labels with boundary noise
        ambiguity_mask: boolean array indicating ambiguous frames
    """
    n = len(labels)
    perturbed = labels.copy()
    ambiguity_mask = np.zeros(n, dtype=bool)

    # Find segment boundaries
    boundaries = []
    for i in range(1, n):
        if labels[i] != labels[i - 1]:
            boundaries.append(i)

    for boundary in boundaries:
        # Create noise zone around boundary
        zone_start = max(0, boundary - noise_width)
        zone_end = min(n, boundary + noise_width)

        ambiguity_mask[zone_start:zone_end] = True

        for j in range(zone_start, zone_end):
            # Distance from boundary (normalized)
            dist = abs(j - boundary) / noise_width
            # Flip probability decreases with distance from boundary
            flip_prob = score_fluctuation * (1 - dist)

            if rng.random() < flip_prob:
                perturbed[j] = not perturbed[j]

    return perturbed, ambiguity_mask


def apply_mixed_hard(
    labels: np.ndarray,
    counts: np.ndarray,
    rng: np.random.Generator,
    K: int,
    tau: int,
    config: HardPerturbationConfig,
) -> Tuple[np.ndarray, Dict]:
    """Apply a mixture of all hard perturbation modes.

    Returns:
        perturbed_labels: labels after all perturbations
        info: dict with info about each perturbation type applied
    """
    n = len(labels)
    info = {}

    # 1. Start with boundary ambiguity (mild)
    perturbed, ambig_mask = apply_boundary_ambiguity(
        labels, rng,
        noise_width=config.boundary_noise_width,
        score_fluctuation=config.boundary_score_fluctuation * 0.5,
    )
    info["boundary_ambiguity_frames"] = int(np.sum(ambig_mask))

    # 2. Apply regime shift (moderate)
    perturbed, risk_mask = apply_regime_shift_proxy_noise(
        perturbed, rng,
        regime_length=config.regime_length,
        fn_rate=config.fn_rate * 0.7,
        fp_rate=config.fp_rate * 0.7,
        transition_sharpness=config.transition_sharpness,
    )
    info["high_risk_frames"] = int(np.sum(risk_mask))

    # 3. Apply some visibility gaps (selective)
    # Only apply to a subset of segments
    segments = []
    run_start = None
    for i, label in enumerate(perturbed):
        if label and run_start is None:
            run_start = i
        elif not label and run_start is not None:
            segments.append((run_start, i - 1))
            run_start = None
    if run_start is not None:
        segments.append((run_start, n - 1))

    gaps_inserted = 0
    for seg_start, seg_end in segments:
        seg_len = seg_end - seg_start + 1
        if seg_len > tau * 1.5 and rng.random() < 0.3:
            # Insert a moderate gap
            gap_len = rng.choice([3, 5, 10])
            if gap_len < seg_len - 4:
                gap_start = seg_start + rng.integers(2, max(3, seg_len - gap_len - 2))
                perturbed[gap_start:gap_start + gap_len] = False
                gaps_inserted += 1

    info["visibility_gaps_inserted"] = gaps_inserted

    return perturbed, info


def perturb_video_hard(
    video: VideoAnnotation,
    K: int,
    tau: int,
    config: HardPerturbationConfig,
    rng: np.random.Generator,
) -> Dict:
    """Apply hard perturbation to a video.

    Returns dict with:
        - perturbed_labels: frame-level labels after perturbation
        - original_labels: ground truth labels
        - original_counts: ground truth counts
        - perturbed_counts: counts after perturbation (for proxy-based methods)
        - regime: which regime was applied
        - info: regime-specific metadata
    """
    original_counts = video.frame_counts()
    original_labels = (original_counts >= K).astype(bool)
    n = len(original_labels)

    regime = config.regime

    if regime == "regime_shift":
        perturbed_labels, risk_mask = apply_regime_shift_proxy_noise(
            original_labels, rng,
            regime_length=config.regime_length,
            fn_rate=config.fn_rate,
            fp_rate=config.fp_rate,
            transition_sharpness=config.transition_sharpness,
        )
        # Also perturb counts for proxy-based methods
        perturbed_counts = original_counts.copy().astype(float)
        noise = rng.normal(0, config.base_noise_std, n)
        perturbed_counts += noise
        perturbed_counts = np.clip(np.round(perturbed_counts), 0, None).astype(int)
        info = {"risk_mask": risk_mask, "high_risk_frames": int(np.sum(risk_mask))}

    elif regime == "long_gap":
        perturbed_labels, gap_info = apply_long_visibility_gaps(
            original_labels, rng,
            gap_lengths=config.gap_lengths,
            gap_positions=config.gap_positions,
        )
        perturbed_counts = original_counts.copy().astype(float)
        noise = rng.normal(0, config.base_noise_std, n)
        perturbed_counts += noise
        perturbed_counts = np.clip(np.round(perturbed_counts), 0, None).astype(int)
        info = {"gap_info": gap_info, "num_gaps": len(gap_info)}

    elif regime == "close_merge":
        perturbed_counts, merge_info = apply_close_clip_merge_cases(
            original_counts.astype(float), rng, K=K,
            negative_gap_lengths=config.negative_gap_lengths,
            tau=tau,
        )
        perturbed_labels = (perturbed_counts >= K)
        info = {"merge_info": merge_info, "num_merge_cases": len(merge_info)}

    elif regime == "boundary_ambig":
        perturbed_labels, ambig_mask = apply_boundary_ambiguity(
            original_labels, rng,
            noise_width=config.boundary_noise_width,
            score_fluctuation=config.boundary_score_fluctuation,
        )
        perturbed_counts = original_counts.copy().astype(float)
        noise = rng.normal(0, config.base_noise_std, n)
        perturbed_counts += noise
        perturbed_counts = np.clip(np.round(perturbed_counts), 0, None).astype(int)
        info = {"ambiguity_mask": ambig_mask, "ambiguous_frames": int(np.sum(ambig_mask))}

    elif regime == "mixed_hard":
        perturbed_labels, mix_info = apply_mixed_hard(
            original_labels, original_counts, rng, K=K, tau=tau, config=config,
        )
        perturbed_counts = original_counts.copy().astype(float)
        noise = rng.normal(0, config.base_noise_std, n)
        perturbed_counts += noise
        perturbed_counts = np.clip(np.round(perturbed_counts), 0, None).astype(int)
        info = mix_info

    else:
        raise ValueError(f"Unknown regime: {regime}")

    # Build PerturbedSequence-compatible output
    perturbed_frame_annotations = [
        FrameAnnotation(frame_idx=i, vehicle_count=int(perturbed_counts[i]))
        for i in range(n)
    ]

    return {
        "video_id": video.video_id,
        "original_counts": original_counts,
        "perturbed_counts": perturbed_counts,
        "original_labels": original_labels,
        "perturbed_labels": perturbed_labels.astype(bool),
        "perturbed_frame_annotations": perturbed_frame_annotations,
        "regime": regime,
        "info": info,
        "num_oracle_calls": int(np.sum(perturbed_labels != original_labels)),
    }


# Registry of hard perturbation regimes
HARD_REGIMES = [
    "regime_shift",
    "long_gap",
    "close_merge",
    "boundary_ambig",
    "mixed_hard",
]


def apply_oracle_noise(
    gt_labels: np.ndarray,
    sampled_indices: List[int],
    rng: np.random.Generator,
    noise_rate: float = 0.15,
    risk_mask: Optional[np.ndarray] = None,
) -> Tuple[List[int], np.ndarray]:
    """Apply noise to oracle responses at sampled frames.

    Simulates unreliable oracle in difficult conditions (motion blur, occlusion).

    Args:
        gt_labels: ground truth frame labels
        sampled_indices: frames to query oracle
        rng: random generator
        noise_rate: probability oracle returns wrong label
        risk_mask: if provided, only apply noise in high-risk frames.
                   if None and noise_rate > 0, apply noise uniformly.

    Returns:
        sampled_indices: unchanged
        noisy_labels: labels with oracle noise applied at sampled frames
    """
    if noise_rate <= 0:
        # No oracle noise: return ground truth at sampled frames
        noisy_labels = np.zeros(len(gt_labels), dtype=bool)
        for idx in sampled_indices:
            noisy_labels[idx] = gt_labels[idx]
        return sampled_indices, noisy_labels

    noisy_labels = np.zeros(len(gt_labels), dtype=bool)

    for idx in sampled_indices:
        label = gt_labels[idx]

        # Determine if this frame is high-risk
        if risk_mask is not None:
            is_risky = risk_mask[idx]
            # Only apply noise in risky frames
            effective_noise_rate = noise_rate if is_risky else 0.0
        else:
            # Apply noise uniformly
            effective_noise_rate = noise_rate

        if rng.random() < effective_noise_rate:
            # Oracle returns wrong label
            noisy_labels[idx] = not label
        else:
            noisy_labels[idx] = label

    return sampled_indices, noisy_labels
