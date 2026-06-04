"""Oracle allocation strategies for deciding which frames to query.

Each allocation strategy takes a perturbed sequence and returns:
- sampled_indices: list of frame indices to query with oracle
- allocation_labels: initial frame labels (before propagation)
"""

from typing import List, Tuple, Optional
import numpy as np

from pipeline.perturbation import PerturbedSequence


def uniform_allocation(
    perturbed: PerturbedSequence,
    budget: float,
    rng: np.random.Generator,
) -> Tuple[List[int], np.ndarray]:
    """Uniform random allocation: randomly select budget fraction of frames."""
    n = len(perturbed.original_labels)
    num_samples = max(1, int(n * budget))
    sampled_indices = sorted(rng.choice(n, size=num_samples, replace=False).tolist())

    # Query oracle at sampled frames
    labels = np.zeros(n, dtype=bool)
    for idx in sampled_indices:
        labels[idx] = perturbed.original_labels[idx]

    return sampled_indices, labels


def fixed_rate_allocation(
    perturbed: PerturbedSequence,
    budget: float,
    rng: np.random.Generator,
) -> Tuple[List[int], np.ndarray]:
    """Fixed-rate allocation: sample every Nth frame."""
    n = len(perturbed.original_labels)
    stride = max(1, int(1.0 / budget))
    sampled_indices = list(range(0, n, stride))

    labels = np.zeros(n, dtype=bool)
    for idx in sampled_indices:
        labels[idx] = perturbed.original_labels[idx]

    return sampled_indices, labels


def proxy_threshold_allocation(
    perturbed: PerturbedSequence,
    budget: float,
    rng: np.random.Generator,
) -> Tuple[List[int], np.ndarray]:
    """Proxy-threshold allocation: query frames where proxy is uncertain (near threshold K)."""
    n = len(perturbed.original_labels)
    num_samples = max(1, int(n * budget))

    # Uncertainty: distance from threshold (assume K is around the median of counts)
    # Use perturbed counts as proxy
    counts = perturbed.perturbed_counts.astype(float)
    # Estimate K as the approximate threshold where labels flip
    K_est = np.median(counts[counts > 0]) if np.any(counts > 0) else 3.0
    uncertainty = np.abs(counts - K_est)

    # Select most uncertain frames
    sampled_indices = sorted(np.argsort(uncertainty)[:num_samples].tolist())

    labels = perturbed.perturbed_labels.copy()
    for idx in sampled_indices:
        labels[idx] = perturbed.original_labels[idx]

    return sampled_indices, labels


def proxy_uncertainty_allocation(
    perturbed: PerturbedSequence,
    budget: float,
    rng: np.random.Generator,
) -> Tuple[List[int], np.ndarray]:
    """Proxy-uncertainty allocation: query frames with highest temporal instability.

    Uses the magnitude of temporal changes in perturbed counts as uncertainty proxy.
    Frames with large changes are more likely to be misclassified.
    """
    n = len(perturbed.original_labels)
    num_samples = max(1, int(n * budget))

    counts = perturbed.perturbed_counts.astype(float)

    # Compute temporal instability (absolute second derivative)
    if n < 3:
        instability = np.zeros(n)
    else:
        first_deriv = np.abs(np.diff(counts))
        second_deriv = np.abs(np.diff(first_deriv))
        # Pad to length n
        instability = np.zeros(n)
        instability[1:-1] = second_deriv
        instability[0] = instability[1] if n > 1 else 0
        instability[-1] = instability[-2] if n > 1 else 0

    # Add noise to break ties
    instability += rng.uniform(0, 0.01, n)

    sampled_indices = sorted(np.argsort(instability)[-num_samples:].tolist())

    labels = perturbed.perturbed_labels.copy()
    for idx in sampled_indices:
        labels[idx] = perturbed.original_labels[idx]

    return sampled_indices, labels


def hidden_risk_allocation(
    perturbed: PerturbedSequence,
    budget: float,
    rng: np.random.Generator,
    K: int = 3,
) -> Tuple[List[int], np.ndarray]:
    """Hidden-risk allocation: prioritize frames near clip boundaries and gap regions.

    Frames at the edges of positive segments are more critical for clip reconstruction.
    Misclassifying a boundary frame can cause a whole clip to be missed or fragmented.
    """
    n = len(perturbed.original_labels)
    num_samples = max(1, int(n * budget))

    labels = perturbed.perturbed_labels.copy()

    # Identify candidate boundary regions
    # Find transitions in perturbed labels
    risk_scores = np.zeros(n)

    for i in range(1, n - 1):
        # Higher risk near label transitions
        if labels[i - 1] != labels[i]:
            risk_scores[i] += 2.0
            risk_scores[i - 1] += 1.0
            risk_scores[i + 1] += 1.0
        if labels[i] != labels[i + 1]:
            risk_scores[i] += 2.0
            risk_scores[i - 1] += 1.0
            risk_scores[i + 1] += 1.0

    # Also consider frames near the K threshold
    counts = perturbed.perturbed_counts.astype(float)
    near_threshold = np.abs(counts - K) <= 1
    risk_scores[near_threshold] += 1.5

    # Add noise for exploration
    risk_scores += rng.uniform(0, 0.1, n)

    sampled_indices = sorted(np.argsort(risk_scores)[-num_samples:].tolist())

    for idx in sampled_indices:
        labels[idx] = perturbed.original_labels[idx]

    return sampled_indices, labels


def boundary_focused_allocation(
    perturbed: PerturbedSequence,
    budget: float,
    rng: np.random.Generator,
    boundary_window: int = 10,
) -> Tuple[List[int], np.ndarray]:
    """Boundary-focused allocation: concentrate oracle budget around segment boundaries.

    Allocates more samples near the start and end of positive segments,
    where errors are most costly for clip reconstruction.
    """
    n = len(perturbed.original_labels)
    num_samples = max(1, int(n * budget))

    labels = perturbed.perturbed_labels.copy()

    # Find segment boundaries from perturbed labels
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

    # Collect boundary frames
    boundary_frames = set()
    for seg_start, seg_end in segments:
        for offset in range(boundary_window):
            f_start = seg_start + offset
            f_end = seg_end - offset
            if 0 <= f_start < n:
                boundary_frames.add(f_start)
            if 0 <= f_end < n:
                boundary_frames.add(f_end)

    boundary_list = sorted(boundary_frames)

    if len(boundary_list) >= num_samples:
        # Sample from boundary frames
        indices = rng.choice(boundary_list, size=num_samples, replace=False)
        sampled_indices = sorted(indices.tolist())
    else:
        # Use all boundary frames, fill rest randomly
        sampled_indices = list(boundary_list)
        remaining = num_samples - len(boundary_list)
        non_boundary = [i for i in range(n) if i not in boundary_frames]
        if remaining > 0 and non_boundary:
            extra = rng.choice(non_boundary, size=min(remaining, len(non_boundary)), replace=False)
            sampled_indices.extend(extra.tolist())
        sampled_indices = sorted(set(sampled_indices))

    for idx in sampled_indices:
        labels[idx] = perturbed.original_labels[idx]

    return sampled_indices, labels


# Registry of allocation strategies
ALLOCATION_STRATEGIES = {
    "uniform": uniform_allocation,
    "fixed_rate": fixed_rate_allocation,
    "proxy_threshold": proxy_threshold_allocation,
    "proxy_uncertainty": proxy_uncertainty_allocation,
    "hidden_risk": hidden_risk_allocation,
    "boundary_focused": boundary_focused_allocation,
}
