from __future__ import annotations

from copy import deepcopy
from typing import Any

from .action import Action


def legal_actions(env) -> list[Action]:
    state = env.public_state(); result = []
    if state["estimated_scan_cost_sec"] <= state["remaining_budget_sec"]: result.append(Action.SCAN)
    if state["frontier_size"] and state["estimated_confirm_cost_sec"] <= state["remaining_budget_sec"]: result.append(Action.CONFIRM)
    return result


def one_step_action_oracle(env) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    while True:
        options = []
        for action in legal_actions(env):
            trial = deepcopy(env); before = len(trial.confirmed_events); result = trial.step(action)
            gain = len(trial.confirmed_events) - before
            options.append((gain / max(result.actual_cost_sec, 1e-12), gain, action is Action.CONFIRM, action))
        if not options: break
        # Frozen tie-break is SCAN, hence CONFIRM boolean is sorted ascending.
        action = sorted(options, key=lambda x: (-x[0], -x[1], x[2]))[0][-1]
        env.step(action)
    return env.summary("OFFLINE_ONE_STEP_ORACLE", 0), env.ledger


def multi_step_trace_oracle(env, beam_width: int = 128) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    beam = [env]
    expanded = 0; exact = True
    while True:
        children = []; any_legal = False
        for state in beam:
            actions = legal_actions(state)
            if not actions:
                children.append(state); continue
            any_legal = True
            for action in actions:
                child = deepcopy(state); child.step(action); children.append(child); expanded += 1
        if not any_legal: break
        children.sort(key=lambda s: (len(s.confirmed_events), -s.elapsed, len(s.frontier.rows())), reverse=True)
        if len(children) > beam_width: exact = False
        beam = children[:beam_width]
    best = max(beam, key=lambda s: (len(s.confirmed_events), -s.elapsed))
    return best.summary("OFFLINE_MULTI_STEP_ORACLE", 0), best.ledger, {
        "exact": exact, "algorithm": "DETERMINISTIC_BEAM_SEARCH", "beam_width": beam_width,
        "expanded_states": expanded,
    }

