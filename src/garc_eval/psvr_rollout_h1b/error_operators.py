"""A1/A2 planner-only misspecification operators with canonical targets."""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil
from .crn import error_key, sign
from .types import ActionView

ERROR_TARGETS = ("scan_candidate_yield", "confirm_positive_probability", "novelty_duplicate_probability", "grouping_transition", "action_duration", "materialization_success")
ERROR_FORMS = ("independent_variance", "systematic_optimism", "systematic_pessimism", "state_dependent_calibration")

@dataclass(frozen=True)
class ErrorContext:
    h1b_seed: object
    decision_index: int
    target: str
    form: str
    trajectory_index: int
    target_identity: str
    draw_index: int
    target_score_bin: int | None = None
    frontier_max_score_bin: int | None = None

def canonical_candidates(candidates: tuple[ActionView, ...]) -> tuple[ActionView, ...]:
    return tuple(sorted(candidates, key=lambda x: ((x.hypothesis_id or ""), (x.witness_id or ""))))

def canonical_target(mechanism: str, action: ActionView, peer: ActionView | None = None) -> str:
    if mechanism == "grouping_transition":
        if peer is None or action.hypothesis_id != peer.hypothesis_id: raise ValueError("grouping requires same-hypothesis pair")
        lo, hi = sorted((action.witness_id or "", peer.witness_id or ""))
        return f"GROUP|{action.hypothesis_id}|{lo}|{hi}"
    if mechanism not in ERROR_TARGETS: raise ValueError("unknown frozen error target")
    prefix = {"scan_candidate_yield":"SCAN", "confirm_positive_probability":"CONFIRM", "novelty_duplicate_probability":"NOVELTY", "action_duration":"DURATION", "materialization_success":"MATERIALIZE"}[mechanism]
    if mechanism == "scan_candidate_yield":
        if action.region_id is None: raise ValueError("SCAN target requires region_id")
        return f"SCAN|{action.region_id}|{action.hypothesis_id}|{action.witness_id}"
    if mechanism == "action_duration": return f"DURATION|{action.identifier}"
    return f"{prefix}|{action.hypothesis_id}|{action.witness_id}"

def error_sign(context: ErrorContext) -> int:
    if context.target not in ERROR_TARGETS: raise ValueError("unknown frozen error target")
    if context.form == "systematic_optimism": return 1
    if context.form == "systematic_pessimism": return -1
    if context.form == "state_dependent_calibration":
        if context.target_score_bin is None or context.frontier_max_score_bin is None: return -1
        return 1 if context.target_score_bin == context.frontier_max_score_bin else -1
    if context.form != "independent_variance": raise ValueError("unknown frozen error form")
    return sign(*error_key(context.h1b_seed, context.decision_index, context.target, context.form, context.trajectory_index, context.target_identity, context.draw_index))

def perturb_probability(value: float, magnitude: float, context: ErrorContext) -> float:
    if not 0.0 <= value <= 1.0 or not 0.0 <= magnitude <= 0.20: raise ValueError("invalid probability or frozen magnitude")
    return min(.99, max(.01, value + error_sign(context) * magnitude))

def perturb_duration(value: int, magnitude: float, maximum: int, context: ErrorContext) -> int:
    if value < 1 or maximum < value or not 0.0 <= magnitude <= 0.20: raise ValueError("invalid duration support")
    return min(maximum, max(1, ceil(value * (1 + error_sign(context) * magnitude))))
