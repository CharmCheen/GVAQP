"""Fail-closed V1 primitive evidence boundary.

This module deliberately knows no production result fields.  Its role is to
reject an evidence package before any reference transition can be attempted
unless the non-derived causes of every replay are explicitly present.
"""
from __future__ import annotations

from typing import Any


class PrimitiveEvidenceError(ValueError):
    pass


REQUIRED_TRACE_PRIMITIVES = frozenset((
    "identity", "deterministic_replay_key", "primitive_visible_history",
    "primitive_history_completion_ticks", "primitive_universe_manifest_hash",
))
REQUIRED_SAMPLE_PRIMITIVES = frozenset((
    "posterior_root_index", "posterior_world_id", "trajectory_index",
    "primitive_pre_action_visible_state", "primitive_first_action",
    "primitive_base_action", "primitive_posterior_selection_key",
))


def require_primitive_evidence(trace: dict[str, Any]) -> None:
    """Validate only causes/replay coordinates; reject conclusions as inputs."""
    missing = sorted(REQUIRED_TRACE_PRIMITIVES - trace.keys())
    if missing:
        raise PrimitiveEvidenceError("missing-trace-primitives:" + ",".join(missing))
    if not isinstance(trace["primitive_visible_history"], dict):
        raise PrimitiveEvidenceError("invalid-primitive-visible-history")
    for decision_index, decision in enumerate(trace.get("decisions", ())):
        pairs = decision.get("planner", {}).get("a4_lossless_evidence", {}).get("pairs", ())
        for pair_index, pair in enumerate(pairs):
            for sample_index, sample in enumerate(pair.get("samples", ())):
                missing = sorted(REQUIRED_SAMPLE_PRIMITIVES - sample.keys())
                if missing:
                    raise PrimitiveEvidenceError(
                        f"missing-sample-primitives:{decision_index}:{pair_index}:{sample_index}:" + ",".join(missing))
