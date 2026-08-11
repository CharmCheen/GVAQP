from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .types import (
    EventHypothesis,
    EventStatus,
    PublicationSnapshot,
    PublishedEvent,
)


@dataclass(frozen=True)
class MaterializationConfig:
    probable_threshold: float = 0.80
    precision_floor: float = 0.80
    uncertainty_beta: float = 1.0
    false_positive_penalty: float = 1.0

    def __post_init__(self) -> None:
        for name, value in (
            ("probable_threshold", self.probable_threshold),
            ("precision_floor", self.precision_floor),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if not math.isfinite(self.uncertainty_beta) or self.uncertainty_beta < 0:
            raise ValueError("uncertainty_beta must be finite and nonnegative")
        if not math.isfinite(self.false_positive_penalty) or self.false_positive_penalty < 0:
            raise ValueError("false_positive_penalty must be finite and nonnegative")

    @property
    def individual_lcb_floor(self) -> float:
        return max(self.probable_threshold, self.precision_floor)


class RiskControlledMaterializer:
    """Deterministically publish verified and risk-admissible probable events."""

    def __init__(self, config: MaterializationConfig | None = None) -> None:
        self.config = config or MaterializationConfig()

    def probability_lower_bound(self, hypothesis: EventHypothesis) -> float:
        return max(
            0.0,
            min(
                1.0,
                hypothesis.probability_mean
                - self.config.uncertainty_beta * hypothesis.probability_uncertainty,
            ),
        )

    def materialize(
        self,
        hypotheses: Iterable[EventHypothesis],
        *,
        elapsed_sec: float,
    ) -> PublicationSnapshot:
        if not math.isfinite(elapsed_sec) or elapsed_sec < 0:
            raise ValueError("elapsed_sec must be finite and nonnegative")

        unique: dict[str, EventHypothesis] = {}
        for row in hypotheses:
            prior = unique.get(row.event_id)
            if prior is not None and prior != row:
                raise ValueError(f"conflicting duplicate event hypothesis: {row.event_id}")
            unique[row.event_id] = row

        verified: list[PublishedEvent] = []
        probable_candidates: list[tuple[float, EventHypothesis]] = []
        withheld = 0

        for row in unique.values():
            lcb = self.probability_lower_bound(row)
            if row.authoritative_positive_support > 0:
                verified.append(self._publish(row, EventStatus.VERIFIED, 1.0, elapsed_sec))
            elif lcb >= self.config.individual_lcb_floor:
                probable_candidates.append((lcb, row))
            else:
                withheld += 1

        probable_candidates.sort(
            key=lambda item: (-item[0], -item[1].probability_mean, item[1].event_id)
        )
        probable: list[PublishedEvent] = []
        lcb_sum = 0.0
        for lcb, row in probable_candidates:
            prospective_count = len(probable) + 1
            prospective_average = (lcb_sum + lcb) / prospective_count
            if prospective_average + 1e-15 < self.config.precision_floor:
                withheld += 1
                continue
            probable.append(self._publish(row, EventStatus.PROBABLE, lcb, elapsed_sec))
            lcb_sum += lcb

        events = tuple(
            sorted(
                (*verified, *probable),
                key=lambda row: (row.start_time, row.end_time, row.event_id, row.status.value),
            )
        )
        probable_precision_lcb = lcb_sum / len(probable) if probable else 1.0
        utility = float(len(verified)) + sum(
            row.probability_lower_bound
            - self.config.false_positive_penalty * (1.0 - row.probability_lower_bound)
            for row in probable
        )
        return PublicationSnapshot(
            events=events,
            verified_count=len(verified),
            probable_count=len(probable),
            hypothesis_count=withheld,
            probable_precision_lower_bound=probable_precision_lcb,
            risk_adjusted_utility=utility,
        )

    @staticmethod
    def _publish(
        row: EventHypothesis,
        status: EventStatus,
        probability_lower_bound: float,
        elapsed_sec: float,
    ) -> PublishedEvent:
        return PublishedEvent(
            event_id=row.event_id,
            start_time=row.start_time,
            end_time=row.end_time,
            status=status,
            probability_mean=row.probability_mean,
            probability_lower_bound=probability_lower_bound,
            probability_uncertainty=row.probability_uncertainty,
            boundary_uncertainty_sec=row.boundary_uncertainty_sec,
            source_candidate_ids=tuple(sorted(row.source_candidate_ids)),
            authoritative_positive_support=row.authoritative_positive_support,
            materialized_at_sec=elapsed_sec,
            provenance=dict(row.provenance),
        )
