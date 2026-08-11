from __future__ import annotations
from dataclasses import dataclass

ALLOWED_COVERAGE_POLICIES = (
    "SEQUENTIAL", "UNIFORM_PREFIX", "ANYTIME_LARGEST_GAP", "MACRO_REGION_LARGEST_GAP",
)

@dataclass(frozen=True)
class SafeCoverageConfig:
    """Configuration for the evidence-supported fallback policy."""
    policy_id: str = "ANYTIME_LARGEST_GAP"
    macro_region_size_units: int = 3

    def __post_init__(self) -> None:
        if self.policy_id not in ALLOWED_COVERAGE_POLICIES:
            raise ValueError(f"unsupported safe coverage policy: {self.policy_id}")
        if self.macro_region_size_units < 2:
            raise ValueError("macro_region_size_units must be >=2")
