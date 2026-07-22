from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

import numpy as np

from .models import AtomicUnit, GroundTruthEvent


class Regime(str, Enum):
    R1_ISOLATED_EVENTS = "R1_ISOLATED_EVENTS"
    R2_ADJACENT_DISTINCT = "R2_ADJACENT_DISTINCT"
    R3_INTERNAL_WEAK_GAP = "R3_INTERNAL_WEAK_GAP"
    R4_PROXY_INVISIBLE = "R4_PROXY_INVISIBLE"
    R5_NO_CLEAR_SEPARATOR = "R5_NO_CLEAR_SEPARATOR"
    R6_MODEL_MISSPECIFICATION = "R6_MODEL_MISSPECIFICATION"


@dataclass(frozen=True)
class SyntheticConfig:
    timeline_length: float = 60.0
    event_count: int = 3
    duration_distribution: tuple[float, float] = (7.0, 2.0)
    inter_event_gap: float = 7.0
    adjacent_event_probability: float = 0.35
    internal_weak_gap_probability: float = 0.30
    proxy_quality: float = 0.85
    proxy_zero_probability: float = 0.0
    oracle_false_positive: float = 0.0
    oracle_false_negative: float = 0.0
    oracle_abstain: float = 0.0
    positive_evidence_density: float = 0.75
    unit_size: float = 1.0
    unit_multiplicity: int = 2
    action_specific_cost: dict[str, float] = field(
        default_factory=lambda: {
            "PROBE_CORE": 1.0,
            "PROBE_RELATION": 1.0,
            "EXPLORE_CELL": 1.0,
            "HARD_NEGATIVE_GAP": 1.0,
        }
    )
    random_seed: int = 0


@dataclass(frozen=True)
class SyntheticTimeline:
    regime: Regime
    config: SyntheticConfig
    units: tuple[AtomicUnit, ...]
    ground_truth_events: tuple[GroundTruthEvent, ...]
    latent_unit_event_ids: dict[str, tuple[str, ...]]
    positive_evidence_unit_ids: tuple[str, ...]
    weak_gap_unit_ids: tuple[str, ...]

    def public_units(self) -> tuple[AtomicUnit, ...]:
        return self.units


def generate_timeline(regime: Regime | str, config: SyntheticConfig | None = None) -> SyntheticTimeline:
    regime = Regime(regime)
    config = config or SyntheticConfig()
    rng = np.random.default_rng(config.random_seed)
    intervals = _regime_intervals(regime, config, rng)
    events = tuple(
        GroundTruthEvent(
            event_id=f"gt_{index}",
            start_time=float(start),
            end_time=float(end),
            canonical_anchor_time=float((start + end) / 2.0),
            actor_id=f"actor_{index}",
            schema="synthetic_latent_event_v1",
        )
        for index, (start, end) in enumerate(intervals)
    )
    unit_count = int(np.ceil(config.timeline_length / config.unit_size))
    latent: dict[str, tuple[str, ...]] = {}
    scores = []
    structural = []
    weak_gap_ids: list[str] = []
    for index in range(unit_count):
        start = index * config.unit_size
        end = min(config.timeline_length, start + config.unit_size)
        unit_id = f"u{index:04d}"
        overlaps = tuple(event.event_id for event in events if min(end, event.end_time) > max(start, event.start_time))
        latent[unit_id] = overlaps
        center = (start + end) / 2.0
        if overlaps:
            event = next(event for event in events if event.event_id == overlaps[0])
            dist = abs(center - event.canonical_anchor_time) / max(config.unit_size, event.end_time - event.start_time)
            signal = max(0.0, 1.0 - 2.0 * dist)
        else:
            signal = 0.0
        noise = float(rng.uniform(0.0, 0.20))
        score = config.proxy_quality * signal + (1.0 - config.proxy_quality) * noise
        if regime == Regime.R4_PROXY_INVISIBLE and overlaps and "gt_1" in overlaps:
            score = 0.0
        elif overlaps and rng.random() < config.proxy_zero_probability:
            score = 0.0
        weak_gap_enabled = regime == Regime.R3_INTERNAL_WEAK_GAP or (
            regime == Regime.R6_MODEL_MISSPECIFICATION and config.internal_weak_gap_probability > 0.0
        )
        if weak_gap_enabled and overlaps:
            event = next(event for event in events if event.event_id == overlaps[0])
            weak_width = 0.55 if regime == Regime.R3_INTERNAL_WEAK_GAP else 0.55 * min(
                1.0, config.internal_weak_gap_probability / 0.30
            )
            if abs(center - event.canonical_anchor_time) < config.unit_size * weak_width:
                score = 0.0
                weak_gap_ids.append(unit_id)
        scores.append(float(np.clip(score, 0.0, 1.0)))
        structural.append(float(1.0 / (1.0 + min(abs(center - e.canonical_anchor_time) for e in events))))
    coverage = _coverage_priors(unit_count)
    units = tuple(
        AtomicUnit(
            unit_id=f"u{index:04d}",
            start_time=index * config.unit_size,
            end_time=min(config.timeline_length, (index + 1) * config.unit_size),
            cheap_score=scores[index],
            structural_score=structural[index],
            coverage_prior=coverage[index],
        )
        for index in range(unit_count)
    )
    positives: list[str] = []
    for event in events:
        candidates = [u for u in units if event.event_id in latent[u.unit_id]]
        candidates.sort(key=lambda u: (abs((u.start_time + u.end_time) / 2 - event.canonical_anchor_time), u.unit_id))
        n = max(2 if regime == Regime.R3_INTERNAL_WEAK_GAP else 1, int(round(len(candidates) * config.positive_evidence_density)))
        chosen = candidates[: max(1, min(n, len(candidates)))]
        if regime == Regime.R3_INTERNAL_WEAK_GAP and len(candidates) >= 4:
            chosen = [candidates[len(candidates) // 4], candidates[(3 * len(candidates)) // 4]]
        positives.extend(u.unit_id for u in chosen if u.unit_id not in weak_gap_ids)
    if regime == Regime.R3_INTERNAL_WEAK_GAP:
        positive_set = set(positives)
        units = tuple(
            replace(unit, cheap_score=max(0.95, unit.cheap_score)) if unit.unit_id in positive_set else unit
            for unit in units
        )
    return SyntheticTimeline(
        regime=regime,
        config=config,
        units=units,
        ground_truth_events=events,
        latent_unit_event_ids=latent,
        positive_evidence_unit_ids=tuple(sorted(set(positives))),
        weak_gap_unit_ids=tuple(sorted(set(weak_gap_ids))),
    )


def _regime_intervals(regime: Regime, config: SyntheticConfig, rng: np.random.Generator) -> list[tuple[float, float]]:
    if regime == Regime.R1_ISOLATED_EVENTS:
        return [(5.0, 11.0), (25.0, 32.0), (46.0, 53.0)]
    if regime in {Regime.R2_ADJACENT_DISTINCT, Regime.R5_NO_CLEAR_SEPARATOR}:
        boundary = 17.6 if config.unit_multiplicity >= 2 else 18.0
        return [(8.0, boundary), (boundary, 26.2), (43.0, 50.0)]
    if regime == Regime.R3_INTERNAL_WEAK_GAP:
        return [(10.0, 27.0), (43.0, 51.0)]
    if regime == Regime.R4_PROXY_INVISIBLE:
        return [(7.0, 14.0), (29.0, 37.0), (47.0, 53.0)]
    durations = np.clip(rng.normal(config.duration_distribution[0], config.duration_distribution[1], config.event_count), 2.0, 14.0)
    starts = [3.0]
    for duration in durations[:-1]:
        gap = 0.0 if rng.random() < config.adjacent_event_probability else config.inter_event_gap
        starts.append(starts[-1] + float(duration) + gap)
    intervals = [(start, min(config.timeline_length, start + float(duration))) for start, duration in zip(starts, durations)]
    return [(start, end) for start, end in intervals if end > start]


def _coverage_priors(n: int) -> list[float]:
    order = []
    queue = [(0, n)]
    while queue:
        lo, hi = queue.pop(0)
        if lo >= hi:
            continue
        mid = (lo + hi) // 2
        order.append(mid)
        queue.extend([(lo, mid), (mid + 1, hi)])
    rank = {idx: pos for pos, idx in enumerate(order)}
    return [1.0 - rank[i] / max(1, n) for i in range(n)]
