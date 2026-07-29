from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimePublicState:
    total_budget_sec: float
    remaining_budget_sec: float
    remaining_budget_fraction: float
    scan_cost_estimate: float
    scan_cost_upper: float
    verify_cost_estimate: float
    verify_cost_upper: float
    estimated_remaining_scan_slots: int
    estimated_remaining_verify_slots: int
    scan_then_verify_slack: float
    coverage_fraction: float
    largest_unscanned_gap: float
    number_of_unscanned_regions: int
    recent_scan_region_yield: float
    estimated_unexplored_event_mass: float
    frontier_size: int
    top_proxy_scores: tuple[float, ...] = field(default_factory=tuple)
    top_calibrated_relevance_probabilities: tuple[float, ...] = field(default_factory=tuple)
    top_candidate_uncertainties: tuple[float, ...] = field(default_factory=tuple)
    top_candidate_ages: tuple[float, ...] = field(default_factory=tuple)
    top_candidate_novelties: tuple[float, ...] = field(default_factory=tuple)
    top_candidate_duplicate_risks: tuple[float, ...] = field(default_factory=tuple)
    frontier_entropy: float = 0.0
    frontier_near_threshold_mass: float = 0.0
    number_of_event_hypotheses: int = 0
    number_of_verified_events: int = 0
    number_of_probable_events: int = 0
    top_event_scores: tuple[float, ...] = field(default_factory=tuple)
    top_event_uncertainties: tuple[float, ...] = field(default_factory=tuple)
    top_event_novelties: tuple[float, ...] = field(default_factory=tuple)
    top_event_duplicate_risks: tuple[float, ...] = field(default_factory=tuple)
    event_boundary_stability: float = 0.0
    event_fragmentation_indicator: float = 0.0
    event_merge_ambiguity: float = 0.0
    expected_new_event_value: float = 0.0
    estimated_event_precision: float = 0.0
    event_precision_lower_bound: float = 0.0
    current_return_threshold: float = 0.8
    number_of_probable_events_at_risk: int = 0
    number_of_events_removed_after_verify: int = 0
    number_of_events_promoted_after_verify: int = 0
    recent_scan_candidate_yield: float = 0.0
    recent_scan_new_event_yield: float = 0.0
    recent_scan_boundary_extension_yield: float = 0.0
    recent_verify_positive_rate: float = 0.0
    recent_verify_new_event_rate: float = 0.0
    recent_verify_precision_protection_value: float = 0.0
    recent_verify_set_expansion: float = 0.0
    recent_verify_set_contraction: float = 0.0
    recent_action_cost_residual: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PUBLIC_STATE_FIELDS = frozenset(RuntimePublicState.__dataclass_fields__)
FORBIDDEN_CONTROLLER_FIELDS = frozenset({
    "unverified_32b_labels",
    "unscanned_candidates",
    "future_action_costs",
    "reference_events",
    "future_k3_results",
    "final_recall",
    "final_precision",
    "video_id",
})


def validate_public_state(value: dict[str, Any]) -> None:
    supplied = set(value)
    forbidden = supplied & FORBIDDEN_CONTROLLER_FIELDS
    extra = supplied - PUBLIC_STATE_FIELDS
    missing = PUBLIC_STATE_FIELDS - supplied
    if forbidden or extra or missing:
        raise ValueError(
            f"public state boundary violation: forbidden={sorted(forbidden)}, "
            f"extra={sorted(extra)}, missing={sorted(missing)}"
        )
