"""Pure, non-runtime helpers for the PSVR preimplementation freeze.

This module deliberately performs no simulation, inference, media access, or
policy comparison.  It exists only to make the frozen base-policy decision
rule and static validation independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence


FORBIDDEN_POLICY_FIELDS = frozenset(
    {
        "future_proxy",
        "unscanned_content",
        "reference_labels",
        "future_oracle_outcome",
        "evaluator_bottleneck_label",
        "rollout_result",
        "m0_prediction",
        "latent_event_id",
        "latent_events",
        "future_cost_draws",
        "future_oracle_draws",
        "clairvoyant_value",
    }
)


@dataclass(frozen=True)
class Witness:
    hypothesis_created_at: float
    hypothesis_id: str
    witness_created_at: float
    witness_id: str
    confirm_bound_seconds: float
    verified: bool = False
    pending: bool = False


def shielded_base_action(
    *,
    remaining_seconds: float,
    witnesses: Iterable[Witness],
    next_region_id: str | None,
    scan_bound_seconds: float | None,
    standard_confirm_reserve_seconds: float | None,
    visible_state: Mapping[str, object] | None = None,
) -> tuple[str, str | None, str | None]:
    """Return the D2 action without reading or evaluating future fields.

    A missing numeric SCAN binding makes SCAN inadmissible (fail closed).  This
    behavior makes the logical policy total while preserving the documented
    distinction between a logical freeze and a physically executable binding.
    """

    def keys_in(value: object) -> set[str]:
        if isinstance(value, Mapping):
            return set(value) | set().union(*(keys_in(v) for v in value.values()))
        if isinstance(value, (list, tuple)):
            return set().union(*(keys_in(v) for v in value)) if value else set()
        return set()

    if not math.isfinite(remaining_seconds) or remaining_seconds < 0:
        raise ValueError("remaining_seconds must be finite and nonnegative")
    if visible_state is not None and FORBIDDEN_POLICY_FIELDS & keys_in(visible_state):
        raise ValueError("policy input contains forbidden future/evaluator field")
    ordered: Sequence[Witness] = sorted(
        witnesses,
        key=lambda w: (
            w.hypothesis_created_at,
            w.hypothesis_id,
            w.witness_created_at,
            w.witness_id,
        ),
    )
    for witness in ordered:
        if not math.isfinite(witness.confirm_bound_seconds) or witness.confirm_bound_seconds < 0:
            raise ValueError("confirm bound must be finite and nonnegative")
        if (
            not witness.verified
            and not witness.pending
            and witness.confirm_bound_seconds <= remaining_seconds
        ):
            return "CONFIRM", witness.hypothesis_id, witness.witness_id
    for name, value in (("scan", scan_bound_seconds), ("reserve", standard_confirm_reserve_seconds)):
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError(f"{name} bound must be finite and nonnegative")
    if (
        next_region_id is not None
        and scan_bound_seconds is not None
        and standard_confirm_reserve_seconds is not None
        and scan_bound_seconds + standard_confirm_reserve_seconds
        <= remaining_seconds
    ):
        return "SCAN", next_region_id, None
    return "STOP", None, None
