"""ARC-CACHED-REPLAY-v1 selector and causal frozen-oracle boundary.

This module adapts the historical ARC control loop to a one-query-at-a-time
interface.  The historical helper implementation remains unmodified and is
reused for candidate construction, uncertainty updates, and label
propagation.  Propagated labels affect only ARC scheduling state; callers must
build comparable predictions from the explicit query trace.
"""

from __future__ import annotations

import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from scipy.spatial.distance import jensenshannon


REPO_ROOT = Path(__file__).resolve().parents[3]
HISTORICAL_ARC_ROOT = REPO_ROOT / "try_or_no" / "arc_source" / "arc"
if str(HISTORICAL_ARC_ROOT) not in sys.path:
    sys.path.insert(0, str(HISTORICAL_ARC_ROOT))

# These are the surviving historical ARC helpers.  Their hashes are audited by
# the experiment runner; importing them avoids an unnecessary rewrite.
from pruning_phase import init_cluster_uncertainties, init_probabilities  # noqa: E402
from refinement_phase import (  # noqa: E402
    label_propagation,
    update_uncertainties,
)
from score_tools import entropy  # noqa: E402
from tools import calculate_end, calculate_start, findCandClips  # noqa: E402
from refinement_phase import (  # noqa: E402
    calculate_boundaries,
    calculate_indices,
    calculate_j_indices,
)


DETERMINATE_OUTCOMES = frozenset({"positive", "negative"})
INDETERMINATE_OUTCOMES = frozenset(
    {"unknown", "timeout", "parse_failure", "ambiguous", "abstain", "unusable"}
)
VALID_OUTCOMES = DETERMINATE_OUTCOMES | INDETERMINATE_OUTCOMES


@dataclass(frozen=True)
class ARCConfig:
    """Previously frozen ARC adaptation parameters."""

    proxy_threshold: float = 0.4
    cluster_threshold: float = 0.001
    tau_units: int = 1
    confidence: float = 0.9
    iou_threshold: float = 0.5
    startup_sampling_rate: float = 0.002
    tc_enabled: bool = True
    ps_enabled: bool = True
    lp_enabled: bool = True
    exact_fill: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Selection:
    """A single logical query authorized by the selector."""

    call_idx: int
    unit_id: int
    reason: str = "arc_progressive_sampling_label_propagation"


class OracleAccessError(RuntimeError):
    """Raised when frozen labels are accessed outside the selection boundary."""


class FrozenOracle:
    """Reveal one frozen outcome only for an explicit, unique selection."""

    def __init__(self, labels: Mapping[int, str]):
        normalized: dict[int, str] = {}
        for raw_unit, raw_label in labels.items():
            unit_id = int(raw_unit)
            label = normalize_outcome(raw_label)
            normalized[unit_id] = label
        self.__labels = normalized
        self.__seen: set[int] = set()
        self.__access_log: list[int] = []

    @property
    def access_log(self) -> tuple[int, ...]:
        return tuple(self.__access_log)

    def reveal(self, selection: Selection) -> str:
        if not isinstance(selection, Selection):
            raise OracleAccessError("a Selection returned by ARC is required")
        unit_id = int(selection.unit_id)
        if unit_id in self.__seen:
            raise OracleAccessError(f"duplicate logical oracle query for unit {unit_id}")
        if unit_id not in self.__labels:
            raise OracleAccessError(f"no frozen oracle outcome for selected unit {unit_id}")
        self.__seen.add(unit_id)
        self.__access_log.append(unit_id)
        return self.__labels[unit_id]


def normalize_outcome(value: object) -> str:
    label = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if label not in VALID_OUTCOMES:
        raise ValueError(f"unsupported oracle outcome: {value!r}")
    return label


def sequential_js_clusters(scores: Sequence[float], threshold: float) -> np.ndarray:
    """Historical sequential Jensen-Shannon change-point clustering.

    ARC's historical function is named ``js_divergence`` but uses SciPy's
    Jensen-Shannon *distance*.  This function intentionally preserves that
    behavior and compares each posterior with the most recent change point.
    """

    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("scores must be a non-empty one-dimensional sequence")
    if np.any(~np.isfinite(values)) or np.any((values < 0.0) | (values > 1.0)):
        raise ValueError("proxy scores must be finite probabilities in [0, 1]")
    if threshold < 0:
        raise ValueError("cluster threshold must be non-negative")
    distributions = np.column_stack((1.0 - values, values))
    labels = np.zeros(len(values), dtype=int)
    current_label = 0
    previous = distributions[0]
    for index in range(1, len(distributions)):
        candidate = distributions[index]
        if float(jensenshannon(previous, candidate)) > threshold:
            previous = candidate
            current_label += 1
        labels[index] = current_label
    return labels


def safe_confidence(
    clips: np.ndarray,
    iou_threshold: float,
    probabilities: np.ndarray,
    clusters: np.ndarray,
    boundaries: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Historical confidence with defined, finite empty-candidate semantics."""

    clips = np.asarray(clips, dtype=int).reshape(-1, 2)
    if len(clips) == 0:
        return np.asarray([], dtype=float), 0.0
    # Historical ARC constructs j_left/j_right as (n, 1) arrays and passed the
    # one-element arrays into np.arange.  NumPy <2 implicitly converted those
    # arrays to scalars; NumPy 2 rejects that conversion.  Explicit .item()
    # preserves the old numerical operation.
    results: list[float] = []
    total_boundaries = len(boundaries)
    for clip in clips:
        start, end = calculate_boundaries(clip, iou_threshold, total_boundaries)
        i_values, cluster_range = calculate_indices(start, end, boundaries, clusters)
        j_left, j_right = calculate_j_indices(
            i_values, int(clip[0]), int(clip[1]), iou_threshold, total_boundaries
        )
        combined_probability = 0.0
        for index, cluster_value in enumerate(cluster_range):
            left_index = int(np.asarray(j_left[index]).item())
            right_index = int(np.asarray(j_right[index]).item())
            cluster_j_range = np.arange(
                int(clusters[left_index]) + 1, int(clusters[right_index])
            )
            if cluster_j_range.size == 0:
                continue
            cluster_value = int(cluster_value)
            probability_matrix = probabilities[
                cluster_value : int(cluster_j_range[-1]) + 1
            ]
            products = np.cumprod(probability_matrix, axis=0)[
                cluster_j_range - cluster_value
            ]
            left_probability = 1.0 - probabilities[cluster_value - 1]
            right_probability = 1.0 - probabilities[
                np.clip(cluster_j_range + 1, 0, len(probabilities) - 1)
            ]
            combined_probability += float(
                np.sum(products * left_probability * right_probability)
            )
        results.append(combined_probability)
    values = np.asarray(results, dtype=float)
    mean_value = float(np.mean(values))
    if np.any(~np.isfinite(values)) or not math.isfinite(float(mean_value)):
        raise RuntimeError("ARC confidence became non-finite for a non-empty candidate set")
    return values, float(mean_value)


class ARCSelector:
    """Causal, deterministic cached-replay state machine for historical ARC."""

    def __init__(
        self,
        proxy_scores: Sequence[float],
        clusters: Sequence[int],
        *,
        budget: int,
        seed: int,
        config: ARCConfig | None = None,
    ):
        self.config = config or ARCConfig()
        self.public_scores = np.asarray(proxy_scores, dtype=float)
        if self.public_scores.ndim != 1 or len(self.public_scores) == 0:
            raise ValueError("proxy_scores must be a non-empty one-dimensional sequence")
        if np.any(~np.isfinite(self.public_scores)) or np.any(
            (self.public_scores < 0.0) | (self.public_scores > 1.0)
        ):
            raise ValueError("proxy scores must be finite probabilities in [0, 1]")
        if int(budget) < 0:
            raise ValueError("budget must be non-negative")
        self.budget = int(budget)
        self.seed = int(seed)
        self.rng = np.random.RandomState(self.seed)
        self.n = len(self.public_scores)

        self.clusters = np.asarray(clusters, dtype=int)
        if self.clusters.shape != (self.n,):
            raise ValueError("clusters must align exactly with proxy_scores")
        unique = np.unique(self.clusters)
        if len(unique) == 0 or not np.array_equal(unique, np.arange(len(unique))):
            raise ValueError("cluster labels must be contiguous and start at zero")
        if np.any(np.diff(self.clusters) < 0):
            raise ValueError("cluster labels must be temporally nondecreasing")

        self.proxy = np.column_stack((1.0 - self.public_scores, self.public_scores))
        self.PD = self.proxy.copy()
        self.score = (self.public_scores >= self.config.proxy_threshold).astype(int)
        init_probabilities(self.PD, 0, [0.9999, 0.0001])
        init_probabilities(self.PD, 1, [0.0001, 0.9999])
        self.entropy_array = np.apply_along_axis(entropy, 1, self.proxy)
        (
            self.cluster_boundaries,
            self.uncertainties,
            self.probabilities,
        ) = init_cluster_uncertainties(self.clusters, self.entropy_array, self.proxy)

        self.reliability = 0.5
        self.startup_matches = 0
        self.frame_reward = np.zeros(self.n, dtype=int)
        self.sampled = np.zeros(self.n, dtype=bool)
        self.attempted = np.zeros(self.n, dtype=bool)
        self.sampled_boundaries = np.full((self.n, 2), [-self.n, 2 * self.n], dtype=int)
        self.scheduling_labels = np.full(self.n, -1, dtype=int)
        self.explicit_labels = np.full(self.n, -1, dtype=int)
        self.trace: list[dict[str, object]] = []
        self.propagation_log: list[dict[str, object]] = []
        self._pending: Selection | None = None
        self.stop_reason: str | None = None

        tau_rel = self._candidate_clips(self.config.tau_units * (1.0 - self.reliability))
        _, self.tau_rel_confidence = safe_confidence(
            tau_rel,
            self.config.iou_threshold,
            self.probabilities,
            self.clusters,
            self.cluster_boundaries,
        )
        tau = self._candidate_clips(self.config.tau_units)
        _, self.tau_confidence = safe_confidence(
            tau,
            self.config.iou_threshold,
            self.probabilities,
            self.clusters,
            self.cluster_boundaries,
        )
        self.interval_o = max(
            int((self.config.confidence - self.tau_rel_confidence) * len(tau_rel)),
            int((self.config.confidence - self.tau_confidence) * len(tau)),
            1,
        )
        if len(tau) == 0:
            self.stop_reason = "empty_initial_candidate_set"
        elif self.budget == 0:
            self.stop_reason = "budget_exhausted"

    def _candidate_clips(self, tau: float) -> np.ndarray:
        return np.asarray(findCandClips(self.score, ">", 0, tau), dtype=int).reshape(-1, 2)

    def _compute_ucb(
        self, starts: np.ndarray, ends: np.ndarray, available: np.ndarray, call_number: int
    ) -> int | None:
        active: list[tuple[float, int, int]] = []
        for start, end in zip(starts, ends):
            start_i, end_i = int(start), int(end)
            if not np.any(available[start_i : end_i + 1]):
                continue
            rewards = self.frame_reward[start_i : end_i + 1]
            non_zero = rewards[rewards != 0]
            count = len(non_zero)
            reward = (
                float(np.mean(non_zero))
                if count
                else float(np.max(self.uncertainties[start_i : end_i + 1]))
            )
            ucb = reward + 2.0 * math.sqrt(2.0 * math.log(call_number + 1) / count) if count else 0.0
            active.append((ucb, start_i, end_i))
        if not active:
            return None
        _, best_start, best_end = max(active)
        values = self.uncertainties[best_start : best_end + 1].copy()
        allowed = available[best_start : best_end + 1]
        values[~allowed] = -np.inf
        if not np.any(np.isfinite(values)):
            return None
        return int(np.argmax(values) + best_start)

    def _importance_choice(self, indices: np.ndarray) -> int | None:
        if len(indices) == 0:
            return None
        weights = self.entropy_array[indices].astype(float)
        total = float(weights.sum())
        if total <= 0.0:
            return None
        probabilities = weights / total
        return int(self.rng.choice(indices, 1, replace=False, p=probabilities)[0])

    def select_next(self) -> Selection | None:
        """Return one query authorization without accessing an oracle label."""

        if self._pending is not None:
            raise RuntimeError("observe the pending selection before requesting another")
        if self.stop_reason is not None:
            return None
        if len(self.trace) >= self.budget:
            self.stop_reason = "budget_exhausted"
            return None

        call_number = len(self.trace) + 1  # historical o_b, starting at one
        tau_rel = self._candidate_clips(self.config.tau_units * (1.0 - self.reliability))
        if call_number % self.interval_o == 0:
            tau = self._candidate_clips(self.config.tau_units)
            _, self.tau_confidence = safe_confidence(
                tau,
                self.config.iou_threshold,
                self.probabilities,
                self.clusters,
                self.cluster_boundaries,
            )
            if self.tau_confidence >= self.config.confidence:
                _, self.tau_rel_confidence = safe_confidence(
                    tau_rel,
                    self.config.iou_threshold,
                    self.probabilities,
                    self.clusters,
                    self.cluster_boundaries,
                )
                if self.tau_rel_confidence >= self.config.confidence:
                    self.stop_reason = "confidence_reached"
                    return None
            self.interval_o = max(
                int((self.config.confidence - self.tau_rel_confidence) * len(tau_rel)),
                int((self.config.confidence - self.tau_confidence) * len(tau)),
                1,
            )

        starts = np.asarray(
            [
                calculate_start(a, b, self.config.iou_threshold, self.config.tau_units)
                for a, b in tau_rel
            ],
            dtype=int,
        )
        ends = np.asarray(
            [
                calculate_end(a, b, self.config.iou_threshold, self.config.tau_units, self.n)
                for a, b in tau_rel
            ],
            dtype=int,
        )
        available = ~(self.sampled | self.attempted)
        if not np.any(available):
            self.stop_reason = "candidate_universe_exhausted"
            return None

        if self.config.ps_enabled:
            candidate_mask = np.zeros(self.n, dtype=bool)
            for start, end in zip(starts, ends):
                candidate_mask[int(start) : int(end) + 1] = True
            candidate_mask &= available
            non_candidate = available & ~candidate_mask
            startup_limit = self.config.startup_sampling_rate * (self.budget + 1)
            if call_number < startup_limit:
                selected = int(self.rng.choice(np.flatnonzero(available), 1, replace=False)[0])
            elif float(self.rng.rand()) < self.reliability:
                selected = self._compute_ucb(starts, ends, available, call_number)
            else:
                selected = self._importance_choice(np.flatnonzero(non_candidate))
        else:
            selected = int(self.rng.choice(np.flatnonzero(available)))

        if selected is None:
            self.stop_reason = "no_selectable_uncertainty"
            return None
        if self.attempted[selected]:
            raise RuntimeError("internal duplicate-selection error")
        self.attempted[selected] = True
        self._pending = Selection(call_idx=len(self.trace), unit_id=selected)
        return self._pending

    def observe(self, selection: Selection, outcome: object) -> None:
        """Apply only the outcome of the currently authorized logical query."""

        if self._pending is None or selection != self._pending:
            raise RuntimeError("observation does not match the pending ARC selection")
        label = normalize_outcome(outcome)
        unit_id = int(selection.unit_id)
        propagated_ids: list[int] = []

        if label in DETERMINATE_OUTCOMES:
            binary = 1 if label == "positive" else 0
            self.explicit_labels[unit_id] = binary
            call_number = selection.call_idx + 1
            startup_limit = self.config.startup_sampling_rate * (self.budget + 1)
            if call_number < startup_limit:
                if int(self.score[unit_id]) == binary:
                    self.startup_matches += 1
                self.reliability = self.startup_matches / float(call_number + 1)

            before = self.sampled.copy()
            oracle = np.full((self.n, 2), np.nan, dtype=float)
            oracle[unit_id] = [1 - binary, binary]
            _, left, right, left_t, right_t = label_propagation(
                self.PD,
                self.score,
                self.sampled,
                self.cluster_boundaries,
                self.sampled_boundaries,
                unit_id,
                self.config.tau_units,
                oracle,
                self.probabilities,
                self.clusters,
                self.frame_reward,
                self.uncertainties,
                self.config.lp_enabled,
            )
            newly_sampled = np.flatnonzero(self.sampled & ~before)
            self.scheduling_labels[newly_sampled] = binary
            propagated_ids = [int(value) for value in newly_sampled if int(value) != unit_id]
            self.propagation_log.append(
                {
                    "call_idx": selection.call_idx,
                    "queried_unit_id": unit_id,
                    "queried_outcome": label,
                    "scheduling_left": int(left),
                    "scheduling_right": int(right),
                    "propagated_unit_ids": propagated_ids,
                }
            )
            if self.config.ps_enabled and self.config.lp_enabled and int(self.score[unit_id]) == 0:
                left_t = max(0, int(left_t), int(left) - self.config.tau_units)
                right_t = min(int(right_t), self.n - 1, int(right) + self.config.tau_units)
                update_uncertainties(
                    left_t + 1,
                    int(left),
                    self.uncertainties,
                    self.clusters,
                    self.probabilities,
                    self.config.tau_units,
                    self.score,
                    self.cluster_boundaries,
                    left_t,
                    int(left),
                    self.entropy_array,
                )
                update_uncertainties(
                    int(right) + 1,
                    right_t - 1,
                    self.uncertainties,
                    self.clusters,
                    self.probabilities,
                    self.config.tau_units,
                    self.score,
                    self.cluster_boundaries,
                    int(right),
                    right_t,
                    self.entropy_array,
                )

        self.trace.append(
            {
                "call_idx": selection.call_idx,
                "unit_id": unit_id,
                "oracle_label_after_query": label,
                "outcome_is_determinate": label in DETERMINATE_OUTCOMES,
                "verified_positive": label == "positive",
                "propagated_unit_count": len(propagated_ids),
                "selection_reason": selection.reason,
            }
        )
        self._pending = None
        if len(self.trace) >= self.budget:
            self.stop_reason = "budget_exhausted"

    def diagnostics(self) -> dict[str, object]:
        clips = self._candidate_clips(self.config.tau_units)
        confidences, mean_confidence = safe_confidence(
            clips,
            self.config.iou_threshold,
            self.probabilities,
            self.clusters,
            self.cluster_boundaries,
        )
        return {
            "candidate_clips": clips.tolist(),
            "candidate_clip_confidences": confidences.tolist(),
            "tau_confidence": mean_confidence,
            "logical_oracle_calls": len(self.trace),
            "stop_reason": self.stop_reason or "running",
            "cluster_count": int(len(np.unique(self.clusters))),
            "explicit_positive_unit_ids": np.flatnonzero(self.explicit_labels == 1).astype(int).tolist(),
            "explicit_negative_unit_ids": np.flatnonzero(self.explicit_labels == 0).astype(int).tolist(),
            "propagated_positive_unit_ids": np.flatnonzero(
                (self.scheduling_labels == 1) & (self.explicit_labels != 1)
            ).astype(int).tolist(),
            "propagated_negative_unit_ids": np.flatnonzero(
                (self.scheduling_labels == 0) & (self.explicit_labels != 0)
            ).astype(int).tolist(),
            "native_candidate_output_is_comparable_event_relation": False,
        }

    def run(self, oracle: FrozenOracle) -> list[dict[str, object]]:
        """Convenience cached replay; the selector never receives label storage."""

        while True:
            selection = self.select_next()
            if selection is None:
                break
            self.observe(selection, oracle.reveal(selection))
        return list(self.trace)
