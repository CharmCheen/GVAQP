from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Iterable

import numpy as np

from .action import Action
from .common_utility import FixedUpperCostEstimator, SafeTraceReplayEnvironment
from .runner import TraceReplayEnvironment
from .smdp_return import SMDPReturn

DEFAULT_BEAM_WIDTHS = (128, 512, 2048)
DEFAULT_ANYTIME_TOLERANCE = 1e-6


def validate_causal_cost_boundary(env: Any) -> None:
    """Fail closed when a trace environment exposes evaluated-task future costs."""
    if isinstance(env, TraceReplayEnvironment) and not getattr(env, "cost_calibration_tasks", None):
        raise ValueError(
            "conditioned SMDP values require externally calibrated public cost bounds; "
            "plain TraceReplayEnvironment uses evaluated-task future costs"
        )


def _verify_action(value: Action | str) -> Action:
    if isinstance(value, Action):
        return value
    normalized = str(value).upper()
    if normalized in {"VERIFY", "VERIFY_TOP1"}:
        return Action.CONFIRM
    return Action(normalized)


def _finite_positive(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def verify_cost_upper(env: Any, state: dict[str, Any] | None = None) -> float:
    """Return the causal admission bound even when the Frontier is empty."""
    state = env.public_state() if state is None else state
    visible = state.get("estimated_confirm_cost_sec", float("inf"))
    if _finite_positive(visible):
        return float(visible)
    estimator = getattr(env, "confirm_estimator", None)
    if estimator is not None:
        estimate = estimator.estimate()
        if _finite_positive(estimate):
            return float(estimate)
    return float("inf")


def legal_binary_actions(env: Any, *, reserve_verify_after_scan: bool = True) -> list[Action]:
    """Legal learned actions under conservative complete-action admission."""
    state = env.public_state()
    remaining = float(state["remaining_budget_sec"])
    scan_cost = float(state.get("estimated_scan_cost_sec", float("inf")))
    verify_cost = verify_cost_upper(env, state)
    scan_available = getattr(env, "scan_cursor", 0) < len(getattr(env, "order", [0]))
    scan_legal = scan_available and _finite_positive(scan_cost) and scan_cost <= remaining
    if reserve_verify_after_scan:
        scan_legal = scan_legal and _finite_positive(verify_cost) and scan_cost + verify_cost <= remaining
    verify_legal = (
        int(state.get("frontier_size", 0)) > 0
        and _finite_positive(verify_cost)
        and verify_cost <= remaining
    )
    return ([Action.SCAN] if scan_legal else []) + ([Action.CONFIRM] if verify_legal else [])


class ExternalCalibrationSafeTraceReplayEnvironment(SafeTraceReplayEnvironment):
    """Safe replay whose public bounds exclude the evaluated video's future costs.

    Realized per-action costs remain evaluator transition data. Bounds are pooled
    from the other frozen video by default. This can expose safety failures under
    shift; it does not manufacture an evaluated-task maximum.
    """

    FROZEN_TASKS = ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")

    def __init__(
        self,
        task_id: str,
        budget_sec: float,
        *,
        calibration_tasks: Iterable[str] | None = None,
    ) -> None:
        super().__init__(task_id, budget_sec)
        if calibration_tasks is None:
            calibration_tasks = [t for t in self.FROZEN_TASKS if not t.startswith(self.video_id + "_")]
        calibration_tasks = tuple(calibration_tasks)
        if not calibration_tasks:
            raise ValueError("external cost calibration requires at least one task")
        same_video = [task for task in calibration_tasks if task.startswith(self.video_id + "_")]
        if same_video:
            raise ValueError(f"cost calibration leaks evaluated video {self.video_id}: {same_video}")
        scan_samples: list[float] = []
        verify_samples: list[float] = []
        for other_task in calibration_tasks:
            other = TraceReplayEnvironment(other_task, budget_sec)
            scan_samples.extend(other.scan_costs.values())
            verify_samples.extend(other.confirm_costs.values())
        self.scan_estimator = FixedUpperCostEstimator(scan_samples)
        self.confirm_estimator = FixedUpperCostEstimator(verify_samples)
        self.cost_calibration_tasks = calibration_tasks


def _round_float(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)):
            return "NaN"
        if math.isinf(float(value)):
            return "Infinity" if float(value) > 0 else "-Infinity"
        return round(float(value), 12)
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(v) for v in value), key=lambda x: json.dumps(x, sort_keys=True))
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return _canonical(vars(value))
    return _round_float(value)


def evaluator_state_payload(env: Any) -> dict[str, Any]:
    """Complete evaluator-only state used for branch identity and deduplication."""
    custom = getattr(env, "smdp_state_payload", None)
    if custom is not None:
        return _canonical(custom())
    frontier = getattr(env, "frontier", None)
    frontier_rows = []
    if frontier is not None:
        frontier_rows = [vars(row) for row in frontier.rows()]
    estimator_payload = {}
    for name in ("scan_estimator", "confirm_estimator"):
        estimator = getattr(env, name, None)
        if estimator is not None:
            estimator_payload[name] = {
                "class": type(estimator).__name__,
                "state": vars(estimator),
                "estimate": estimator.estimate(),
            }
    return _canonical({
        "task_id": getattr(env, "task_id", None),
        "budget_sec": getattr(env, "budget_sec", None),
        "elapsed": getattr(env, "elapsed", None),
        "public_state": env.public_state(),
        "scan_cursor": getattr(env, "scan_cursor", None),
        "order": getattr(env, "order", None),
        "observed": getattr(env, "observed", None),
        "frontier_rows": frontier_rows,
        "frontier_capacity": getattr(frontier, "capacity", None),
        "frontier_discarded": getattr(frontier, "discarded", None),
        "frontier_queried": getattr(frontier, "queried", None),
        "confirmed_events": getattr(env, "confirmed_events", None),
        "bound_tracks": getattr(env, "bound_tracks", None),
        "candidate_created_elapsed": getattr(env, "candidate_created_elapsed", None),
        "ever_admitted": getattr(env, "ever_admitted", None),
        "cost_estimators": estimator_payload,
        "transition_asset_hash": getattr(env, "transition_asset_hash", None),
        "reference_count": getattr(env, "reference_count", None),
        "ledger": getattr(env, "ledger", None),
    })


def evaluator_state_hash(env: Any) -> str:
    encoded = json.dumps(evaluator_state_payload(env), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def anytime_auc(env: Any) -> float:
    """Compute B^-1 integral N(t)dt from on-time atomic commits."""
    budget = float(env.budget_sec)
    if budget <= 0:
        return 0.0
    rows = sorted(getattr(env, "ledger", ()), key=lambda row: (float(row["cumulative_wallclock"]), int(row.get("action_index", 0))))
    area = 0.0
    prior_time = 0.0
    count = 0
    for row in rows:
        completion = float(row["cumulative_wallclock"])
        clipped = min(max(completion, prior_time), budget)
        area += count * (clipped - prior_time)
        prior_time = clipped
        if completion <= budget and not row.get("deadline_overrun", False):
            count = int(row.get("utility", count + int(row.get("new_distinct_utility", 0))))
        if completion >= budget:
            break
    area += count * max(0.0, budget - prior_time)
    return float(area / budget)


def _return_from_env(env: Any, *, exact: bool, stable: bool = False) -> SMDPReturn:
    on_time = [
        row for row in getattr(env, "ledger", ())
        if float(row.get("cumulative_wallclock", float("inf"))) <= float(env.budget_sec)
        and not row.get("deadline_overrun", False)
    ]
    if on_time:
        final_events = max(int(row.get("utility", 0)) for row in on_time)
    else:
        final_events = len(getattr(env, "confirmed_events", ())) if not getattr(env, "ledger", ()) else 0
    return SMDPReturn(
        final_distinct_events=final_events,
        anytime_auc=anytime_auc(env),
        elapsed_sec=float(getattr(env, "elapsed", 0.0)),
        completed_actions=len(getattr(env, "ledger", ())),
        exact=bool(exact),
        stable=bool(stable),
        trajectory=tuple(deepcopy(getattr(env, "ledger", ()))),
    )


def _partial_rank(env: Any) -> tuple[float, float, float, float, str]:
    state = env.public_state()
    remaining = float(state["remaining_budget_sec"])
    verify_cost = verify_cost_upper(env, state)
    slots = int(remaining // verify_cost) if _finite_positive(verify_cost) else 0
    confirmed = set(getattr(env, "confirmed_events", ()))
    reference_count = int(getattr(env, "reference_count", len(confirmed)))
    event_by_unit = getattr(env, "event_by_unit", {})
    labels = getattr(env, "labels", {})
    potential_per_verify = sorted(
        (
            len(set(events) - confirmed)
            for unit, events in event_by_unit.items()
            if labels.get(int(unit)) == "positive"
        ),
        reverse=True,
    )
    if potential_per_verify:
        optimistic_events = min(reference_count, len(confirmed) + sum(potential_per_verify[:slots]))
    else:
        optimistic_events = reference_count if slots > 0 else len(confirmed)
    return (
        float(optimistic_events),
        float(len(getattr(env, "confirmed_events", ()))),
        anytime_auc(env),
        -float(getattr(env, "elapsed", 0.0)),
        evaluator_state_hash(env),
    )


def _transition(env: Any, action: Action) -> Any | None:
    child = deepcopy(env)
    result = child.step(action)
    if not result.completed:
        return None
    if float(getattr(child, "elapsed", 0.0)) > float(child.budget_sec) + 1e-12:
        return None
    if getattr(child, "ledger", ()) and child.ledger[-1].get("deadline_overrun", False):
        return None
    return child


def _search_continuation(env: Any, beam_width: int) -> SMDPReturn:
    if beam_width <= 0:
        raise ValueError("beam_width must be positive")
    active = [env]
    best_finished: SMDPReturn | None = None
    exact = True
    expanded_states = 0
    pruned_states = 0
    invalid_transitions = 0
    while active:
        children_by_hash: dict[str, Any] = {}
        for state in active:
            actions = legal_binary_actions(state)
            if not actions:
                candidate = _return_from_env(state, exact=True)
                if best_finished is None or candidate.objective_key > best_finished.objective_key:
                    best_finished = candidate
                continue
            produced = False
            for action in actions:
                expanded_states += 1
                child = _transition(state, action)
                if child is None:
                    exact = False
                    invalid_transitions += 1
                    continue
                produced = True
                key = evaluator_state_hash(child)
                incumbent = children_by_hash.get(key)
                if incumbent is None or _partial_rank(child) > _partial_rank(incumbent):
                    children_by_hash[key] = child
            if not produced:
                candidate = _return_from_env(state, exact=False)
                if best_finished is None or candidate.objective_key > best_finished.objective_key:
                    best_finished = candidate
        children = sorted(children_by_hash.values(), key=_partial_rank, reverse=True)
        if len(children) > beam_width:
            exact = False
            pruned_states += len(children) - beam_width
            children = children[:beam_width]
        active = children
    if best_finished is None:
        best_finished = _return_from_env(env, exact=False)
        exact = False
    return replace(
        best_finished,
        exact=bool(exact and best_finished.exact),
        expanded_states=expanded_states,
        pruned_states=pruned_states,
        invalid_transitions=invalid_transitions,
    )


def conditioned_action_value(
    env: Any,
    first_action: Action | str,
    *,
    beam_width: int,
    objective: str = "lexicographic",
) -> SMDPReturn:
    """Best return after forcing one legal first action from an untouched state."""
    validate_causal_cost_boundary(env)
    if objective.lower() not in {"lexicographic", "event_then_anytime"}:
        raise ValueError("only the frozen lexicographic objective is supported")
    action = _verify_action(first_action)
    if action not in {Action.SCAN, Action.CONFIRM}:
        raise ValueError("first_action must be SCAN or VERIFY_TOP1/CONFIRM")
    if action not in legal_binary_actions(env):
        raise ValueError(f"forced first action {action.value} is not legal")
    original_hash = evaluator_state_hash(env)
    trial = _transition(env, action)
    if trial is None:
        raise RuntimeError("a conservatively admitted forced action failed or overran")
    result = _search_continuation(trial, beam_width)
    if evaluator_state_hash(env) != original_hash:
        raise RuntimeError("conditioned search mutated the source environment")
    return result


def optimal_binary_return(
    env: Any,
    *,
    beam_width: int,
    objective: str = "lexicographic",
) -> SMDPReturn:
    """Best binary return from a state without forcing the first action."""
    validate_causal_cost_boundary(env)
    if objective.lower() not in {"lexicographic", "event_then_anytime"}:
        raise ValueError("only the frozen lexicographic objective is supported")
    original_hash = evaluator_state_hash(env)
    result = _search_continuation(deepcopy(env), beam_width)
    if evaluator_state_hash(env) != original_hash:
        raise RuntimeError("oracle search mutated the source environment")
    return result


def label_from_returns(
    scan: SMDPReturn,
    verify: SMDPReturn,
    *,
    anytime_tolerance: float = DEFAULT_ANYTIME_TOLERANCE,
) -> tuple[str, str]:
    event_delta = scan.final_distinct_events - verify.final_distinct_events
    anytime_delta = scan.anytime_auc - verify.anytime_auc
    if event_delta > 0:
        return "SCAN_BETTER", "SCAN"
    if event_delta < 0:
        return "VERIFY_BETTER", "VERIFY"
    if anytime_delta > anytime_tolerance:
        return "SCAN_BETTER", "SCAN"
    if anytime_delta < -anytime_tolerance:
        return "VERIFY_BETTER", "VERIFY"
    return "EFFECTIVELY_TIED", "R4_FALLBACK"


@dataclass(frozen=True)
class ConditionedActionValues:
    scan: SMDPReturn
    verify: SMDPReturn
    delta_final_events: int
    delta_anytime: float
    oracle_action: str
    label_class: str
    label_stable: bool
    oracle_exact: bool
    beam_width: int
    widths_checked: tuple[int, ...]


def conditioned_action_values(
    env: Any,
    *,
    beam_widths: Iterable[int] = DEFAULT_BEAM_WIDTHS,
    objective: str = "lexicographic",
    anytime_tolerance: float = DEFAULT_ANYTIME_TOLERANCE,
) -> ConditionedActionValues:
    widths = tuple(sorted(set(int(width) for width in beam_widths)))
    if not widths:
        raise ValueError("at least one beam width is required")
    per_width: list[tuple[int, SMDPReturn, SMDPReturn, str, str]] = []
    for width in widths:
        scan = conditioned_action_value(env, Action.SCAN, beam_width=width, objective=objective)
        verify = conditioned_action_value(env, Action.CONFIRM, beam_width=width, objective=objective)
        label, oracle_action = label_from_returns(scan, verify, anytime_tolerance=anytime_tolerance)
        per_width.append((width, scan, verify, label, oracle_action))
    width, scan, verify, label, oracle_action = per_width[-1]
    event_signatures = {
        (row[1].final_distinct_events, row[2].final_distinct_events, row[3]) for row in per_width
    }
    scan_auc = [row[1].anytime_auc for row in per_width]
    verify_auc = [row[2].anytime_auc for row in per_width]
    stable = (
        len(widths) >= 2
        and len(event_signatures) == 1
        and max(scan_auc) - min(scan_auc) <= anytime_tolerance
        and max(verify_auc) - min(verify_auc) <= anytime_tolerance
    )
    exact = all(row[1].exact and row[2].exact for row in per_width)
    return ConditionedActionValues(
        scan=replace(scan, stable=stable),
        verify=replace(verify, stable=stable),
        delta_final_events=scan.final_distinct_events - verify.final_distinct_events,
        delta_anytime=scan.anytime_auc - verify.anytime_auc,
        oracle_action=oracle_action,
        label_class=label,
        label_stable=stable,
        oracle_exact=exact,
        beam_width=width,
        widths_checked=widths,
    )
