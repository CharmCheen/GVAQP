from __future__ import annotations

from copy import deepcopy

from garc_eval.scan_confirm_controller.action import Action, ActionResult
from garc_eval.scan_confirm_controller.smdp_oracle import (
    conditioned_action_value,
    conditioned_action_values,
    evaluator_state_hash,
)


class _Estimator:
    def estimate(self) -> float:
        return 1.0

    def observe(self, value: float) -> None:
        return None


class ToyEnvironment:
    """Small deterministic SMDP with an existing A and one scanned B event."""

    def __init__(self) -> None:
        self.task_id = "toy"
        self.budget_sec = 4.0
        self.elapsed = 0.0
        self.scan_cursor = 0
        self.order = [0, 1]
        self.frontier = ["A"]
        self.confirmed_events: set[str] = set()
        self.reference_count = 2
        self.ledger: list[dict] = []
        self.scan_estimator = _Estimator()
        self.confirm_estimator = _Estimator()

    def public_state(self) -> dict:
        return {
            "remaining_budget_sec": self.budget_sec - self.elapsed,
            "estimated_scan_cost_sec": 1.0 if self.scan_cursor < len(self.order) else float("inf"),
            "estimated_confirm_cost_sec": 1.0 if self.frontier else float("inf"),
            "frontier_size": len(self.frontier),
        }

    def smdp_state_payload(self) -> dict:
        return {
            "elapsed": self.elapsed,
            "scan_cursor": self.scan_cursor,
            "frontier": self.frontier,
            "confirmed": self.confirmed_events,
            "ledger": self.ledger,
        }

    def step(self, action: Action) -> ActionResult:
        if action is Action.SCAN:
            self.scan_cursor += 1
            if self.scan_cursor == 1:
                self.frontier.append("B")
            cost = 1.0
            gain = 0
        elif action is Action.CONFIRM and self.frontier:
            event = self.frontier.pop(0)
            gain = int(event not in self.confirmed_events)
            self.confirmed_events.add(event)
            cost = 1.0
        else:
            return ActionResult(action, 1.0, 0.0, False)
        self.elapsed += cost
        self.ledger.append({
            "action_index": len(self.ledger),
            "action": action.value,
            "actual_action_cost_sec": cost,
            "cumulative_wallclock": self.elapsed,
            "deadline_overrun": self.elapsed > self.budget_sec,
            "new_distinct_utility": gain,
            "utility": len(self.confirmed_events),
        })
        return ActionResult(action, 1.0, cost, True, new_distinct_utility=gain)


def test_forced_first_action_is_executed_and_source_is_unchanged():
    env = ToyEnvironment()
    original = evaluator_state_hash(env)
    scan = conditioned_action_value(env, Action.SCAN, beam_width=32)
    verify = conditioned_action_value(env, "VERIFY_TOP1", beam_width=32)
    assert scan.trajectory[0]["action"] == "SCAN"
    assert verify.trajectory[0]["action"] == "CONFIRM"
    assert evaluator_state_hash(env) == original


def test_conditioned_branches_start_identically_and_deepcopy_isolated():
    env = ToyEnvironment()
    left = deepcopy(env)
    right = deepcopy(env)
    assert evaluator_state_hash(left) == evaluator_state_hash(right)
    left.step(Action.SCAN)
    assert evaluator_state_hash(left) != evaluator_state_hash(right)
    assert right.frontier == ["A"]


def test_lexicographic_value_uses_anytime_on_terminal_tie():
    values = conditioned_action_values(ToyEnvironment(), beam_widths=(8, 32))
    assert values.scan.final_distinct_events == values.verify.final_distinct_events == 2
    assert values.verify.anytime_auc > values.scan.anytime_auc
    assert values.label_class == "VERIFY_BETTER"
    assert values.oracle_action == "VERIFY"
    assert values.label_stable
    assert values.oracle_exact


def test_single_beam_width_is_not_claimed_stable():
    values = conditioned_action_values(ToyEnvironment(), beam_widths=(32,))
    assert not values.label_stable
    assert not values.scan.stable
    assert not values.verify.stable
