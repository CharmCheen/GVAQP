"""Shared-runtime policies for the unknown-video sequential environment.

Every policy consumes only public state.  The dynamic variants are successive
objective improvements: proxy exploitation, K3 marginal-event novelty, and
online state adaptation.  None can access frozen labels before VERIFY.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from .sequential import (
    PublicSequentialState,
    SequentialAction,
    SequentialActionType,
    SequentialCostConfig,
    SequentialObservation,
)


class SequentialPolicy(Protocol):
    method_id: str

    def choose(self, state: PublicSequentialState) -> SequentialAction: ...

    def observe(
        self,
        prior_state: PublicSequentialState,
        observation: SequentialObservation,
        next_state: PublicSequentialState,
    ) -> None: ...


@dataclass(frozen=True)
class CrossVideoProfile:
    """Training-video-only calibration used on an unseen video."""

    intercept: float
    proxy_coefficient: float
    positive_prior: float
    cell_max_posteriors: tuple[float, ...]
    prior_strength: float = 20.0

    def posterior(self, proxy_score: float, state: PublicSequentialState | None = None) -> float:
        logit = self.intercept + self.proxy_coefficient * float(proxy_score)
        if state is not None and state.determinate_verify_count:
            positives = len(state.positive_unit_ids)
            count = state.determinate_verify_count
            online_rate = (positives + self.prior_strength * self.positive_prior) / (
                count + self.prior_strength
            )
            base = min(max(self.positive_prior, 1e-6), 1 - 1e-6)
            online = min(max(online_rate, 1e-6), 1 - 1e-6)
            logit += math.log(online / (1 - online)) - math.log(base / (1 - base))
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, logit))))


def space_filling_order(cell_count: int) -> tuple[int, ...]:
    """Label-blind temporal bisection order for early broad coverage."""

    order: list[int] = []
    queue = [(0, cell_count - 1)]
    while queue:
        left, right = queue.pop(0)
        if left > right:
            continue
        middle = (left + right) // 2
        order.append(middle)
        queue.append((left, middle - 1))
        queue.append((middle + 1, right))
    return tuple(order)


def next_scan_target(state: PublicSequentialState, *, chronological: bool = False) -> int | None:
    unscanned = set(state.unscanned_cell_ids)
    if not unscanned:
        return None
    order = range(len(state.cells)) if chronological else space_filling_order(len(state.cells))
    return next(int(cell_id) for cell_id in order if cell_id in unscanned)


def can_scan_with_reserve(state: PublicSequentialState, costs: SequentialCostConfig) -> bool:
    required = costs.scan_cost + (costs.verify_cost if costs.scan_requires_verify_reserve else 0.0)
    return bool(state.unscanned_cell_ids) and required <= state.remaining + 1e-12


def can_verify(state: PublicSequentialState, costs: SequentialCostConfig) -> bool:
    return bool(state.verifiable_unit_ids) and costs.verify_cost <= state.remaining + 1e-12


class BasePolicy:
    method_id = "BASE"

    def observe(self, prior_state, observation, next_state) -> None:
        return None

    @staticmethod
    def stop(reason: str) -> SequentialAction:
        return SequentialAction(SequentialActionType.STOP, None, reason)


class TwoStageRawPolicy(BasePolicy):
    """Current cached baseline: complete chronological SCAN, then raw-proxy VERIFY."""

    method_id = "CURRENT_TWO_STAGE_RAW"

    def __init__(self, costs: SequentialCostConfig) -> None:
        self.costs = costs

    def choose(self, state: PublicSequentialState) -> SequentialAction:
        scan = next_scan_target(state, chronological=True)
        if scan is not None and can_scan_with_reserve(state, self.costs):
            return SequentialAction(SequentialActionType.SCAN, scan, "two_stage_complete_scan")
        if can_verify(state, self.costs):
            unit = max(state.verifiable_unit_ids, key=lambda uid: (state.proxy_scores[uid], -uid))
            return SequentialAction(SequentialActionType.VERIFY, unit, "raw_proxy_descending")
        return self.stop("no_safe_action")


class FixedCyclePolicy(BasePolicy):
    """Label-blind fixed interleaving baseline with broad scan coverage."""

    def __init__(self, costs: SequentialCostConfig, verifies_per_scan: int) -> None:
        if verifies_per_scan <= 0:
            raise ValueError("verifies_per_scan must be positive")
        self.costs = costs
        self.verifies_per_scan = int(verifies_per_scan)
        self.method_id = f"FIXED_SCAN1_VERIFY{verifies_per_scan}"

    def choose(self, state: PublicSequentialState) -> SequentialAction:
        scans_due = state.scan_count == 0 or state.verify_count >= state.scan_count * self.verifies_per_scan
        if scans_due and can_scan_with_reserve(state, self.costs):
            target = next_scan_target(state)
            return SequentialAction(SequentialActionType.SCAN, target, "fixed_cycle_scan")
        if can_verify(state, self.costs):
            unit = max(state.verifiable_unit_ids, key=lambda uid: (state.proxy_scores[uid], -uid))
            return SequentialAction(SequentialActionType.VERIFY, unit, "fixed_cycle_proxy_verify")
        if can_scan_with_reserve(state, self.costs):
            return SequentialAction(
                SequentialActionType.SCAN, next_scan_target(state), "fixed_cycle_frontier_refill"
            )
        return self.stop("no_safe_action")


class DynamicValuePolicy(BasePolicy):
    """Objective-based closed-loop SCAN/VERIFY policy.

    ``mode=proxy`` values a VERIFY by posterior alone. ``mode=k3`` discounts
    units that merely extend an existing event. ``mode=adaptive`` additionally
    updates posterior odds from this video's revealed labels and adds a small,
    decaying information term.  SCAN value is the expected improvement in the
    best available VERIFY option using only training-video cell statistics.
    """

    def __init__(
        self,
        *,
        costs: SequentialCostConfig,
        profile: CrossVideoProfile,
        mode: str,
        boundary_value: float = 0.15,
        information_weight: float = 0.05,
        scan_coverage_bonus: float = 0.03,
    ) -> None:
        if mode not in {"proxy", "k3", "adaptive"}:
            raise ValueError("unsupported dynamic policy mode")
        self.costs = costs
        self.profile = profile
        self.mode = mode
        self.boundary_value = boundary_value
        self.information_weight = information_weight
        self.scan_coverage_bonus = scan_coverage_bonus
        self.method_id = {
            "proxy": "DYNAMIC_PROXY_VALUE_V1",
            "k3": "DYNAMIC_K3_VALUE_V2",
            "adaptive": "DYNAMIC_ADAPTIVE_K3_VALUE_V3",
        }[mode]

    def _posterior(self, state: PublicSequentialState, unit_id: int) -> float:
        adapt = state if self.mode == "adaptive" else None
        return self.profile.posterior(state.proxy_scores[unit_id], adapt)

    def _novelty(self, state: PublicSequentialState, unit_id: int) -> float:
        if self.mode == "proxy":
            return 1.0
        positives = state.positive_unit_ids
        if unit_id - 1 in positives or unit_id + 1 in positives:
            return self.boundary_value
        if unit_id - 2 in positives or unit_id + 2 in positives:
            return 0.65
        return 1.0

    def _verify_value(self, state: PublicSequentialState, unit_id: int) -> float:
        posterior = self._posterior(state, unit_id)
        value = posterior * self._novelty(state, unit_id)
        if self.mode == "adaptive":
            information = 4.0 * posterior * (1.0 - posterior)
            value += self.information_weight * information / math.sqrt(
                1.0 + state.determinate_verify_count
            )
        return value

    def _best_verify(self, state: PublicSequentialState) -> tuple[int | None, float]:
        if not state.verifiable_unit_ids:
            return None, 0.0
        values = [(self._verify_value(state, unit_id), unit_id) for unit_id in state.verifiable_unit_ids]
        value, unit_id = max(values, key=lambda row: (row[0], -row[1]))
        return unit_id, float(value)

    def _scan_value(self, state: PublicSequentialState, current_best: float) -> float:
        if not self.profile.cell_max_posteriors:
            return 0.0
        maxima = np.asarray(self.profile.cell_max_posteriors, dtype=float)
        if self.mode == "adaptive" and state.determinate_verify_count:
            # Apply the same online odds adjustment to training-derived cell
            # maxima without ever observing an unseen cell in this video.
            adjusted = []
            for value in maxima:
                raw_logit = math.log(min(max(value, 1e-6), 1 - 1e-6) / (1 - min(max(value, 1e-6), 1 - 1e-6)))
                base = min(max(self.profile.positive_prior, 1e-6), 1 - 1e-6)
                positives = len(state.positive_unit_ids)
                count = state.determinate_verify_count
                online = (positives + self.profile.prior_strength * base) / (
                    count + self.profile.prior_strength
                )
                shift = math.log(online / (1 - online)) - math.log(base / (1 - base))
                adjusted.append(1.0 / (1.0 + math.exp(-(raw_logit + shift))))
            maxima = np.asarray(adjusted)
        expected_after_scan = float(np.mean(np.maximum(maxima, current_best)))
        option_gain = max(0.0, expected_after_scan - current_best)
        coverage_bonus = (
            self.scan_coverage_bonus * (1.0 - state.scanned_fraction)
            if self.mode == "adaptive"
            else 0.0
        )
        # A scan is useful only because it improves a later VERIFY option.
        return (current_best + option_gain + coverage_bonus) / (
            self.costs.scan_cost + self.costs.verify_cost
        )

    def choose(self, state: PublicSequentialState) -> SequentialAction:
        verify_unit, verify_gain = self._best_verify(state)
        verify_value = verify_gain / self.costs.verify_cost if verify_unit is not None else 0.0
        scan_value = self._scan_value(state, verify_gain)
        scan_safe = can_scan_with_reserve(state, self.costs)
        verify_safe = can_verify(state, self.costs)

        if scan_safe and (not verify_safe or scan_value > verify_value + 1e-12):
            return SequentialAction(
                SequentialActionType.SCAN,
                next_scan_target(state),
                f"{self.method_id.lower()}_scan_value={scan_value:.6f}",
            )
        if verify_safe and verify_unit is not None:
            return SequentialAction(
                SequentialActionType.VERIFY,
                verify_unit,
                f"{self.method_id.lower()}_verify_value={verify_value:.6f}",
            )
        return self.stop("no_safe_productive_action")

