"""Frozen non-learned policies. No policy receives an Episode or environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .schema import Action, VisibleState


def _fifo_confirms(state: VisibleState, safe_actions: tuple[Action, ...]) -> list[Action]:
    safe = {a.identifier: a for a in safe_actions}
    ordered = []
    for witness in sorted(state.frontier, key=lambda w: (w.creation_order, w.hypothesis_id, w.witness_id)):
        action = Action.confirm(witness.hypothesis_id, witness.witness_id)
        if action.identifier in safe:
            ordered.append(action)
    return ordered


def shielded_pi0_action(state: VisibleState, safe_actions: tuple[Action, ...]) -> Action:
    confirms = _fifo_confirms(state, safe_actions)
    if confirms:
        return confirms[0]
    scan = next((a for a in safe_actions if a.kind == "SCAN" and a.region_id == state.next_region_id), None)
    return scan or Action.stop()


class ShieldedPi0:
    policy_id = "B1_SHIELDED_PI0"
    def choose(self, state: VisibleState, safe_actions: tuple[Action, ...]) -> Action:
        return shielded_pi0_action(state, safe_actions)


class ScanThenConfirm:
    policy_id = "B0_SCAN_THEN_CONFIRM"
    def choose(self, state, safe_actions):
        scan = next((a for a in safe_actions if a.kind == "SCAN"), None)
        return scan or (_fifo_confirms(state, safe_actions)[0] if _fifo_confirms(state, safe_actions) else Action.stop())


class FixedPeriodic:
    def __init__(self, period: int):
        if period not in {1, 2, 4, 8}:
            raise ValueError("frozen periods are 1,2,4,8")
        self.period = period
        self.scans_since_confirm = 0
        self.policy_id = f"B2_FIXED_PERIODIC_K{period}"

    def choose(self, state, safe_actions):
        confirms = _fifo_confirms(state, safe_actions)
        scan = next((a for a in safe_actions if a.kind == "SCAN"), None)
        if confirms and (self.scans_since_confirm >= self.period or scan is None):
            self.scans_since_confirm = 0
            return confirms[0]
        if scan:
            self.scans_since_confirm += 1
            return scan
        return confirms[0] if confirms else Action.stop()


class CapacityMatching:
    policy_id = "B3_CAPACITY_MATCHING"
    def choose(self, state, safe_actions):
        confirms = _fifo_confirms(state, safe_actions)
        scan = next((a for a in safe_actions if a.kind == "SCAN"), None)
        capacity = int(state.remaining // state.confirm_reserve)
        hypothesis_count = len({w.hypothesis_id for w in state.frontier})
        if scan and hypothesis_count < capacity:
            return scan
        return confirms[0] if confirms else (scan or Action.stop())


class RatioPSVR:
    policy_id = "B4_RATIO_PSVR"
    def choose(self, state, safe_actions):
        pi0 = shielded_pi0_action(state, safe_actions)
        scored = []
        remaining_regions = max(1, state.unscanned_region_count)
        for action in safe_actions:
            if action.kind == "CONFIRM":
                witness = next(w for w in state.frontier if w.witness_id == action.witness_id and w.hypothesis_id == action.hypothesis_id)
                score = witness.raw_score / witness.confirm_support_upper
            elif action.kind == "SCAN":
                # Frozen population-prior one-step opportunity index; no latent state.
                score = 0.5 / (remaining_regions * state.scan_bound)
            else:
                score = 0.0
            scored.append((score, action.identifier == pi0.identifier, action.identifier, action))
        return max(scored, key=lambda row: (row[0], row[1], tuple(-ord(c) for c in row[2])))[3]


class FrontierPi0(ShieldedPi0):
    policy_id = "M0_EVENT_HYPOTHESIS_FRONTIER_PI0"


@dataclass
class IdealSymmetricRollout:
    evaluator: Callable[[Action, VisibleState], float]
    policy_id: str = "M1_IDEAL_SYMMETRIC_ROLLOUT_PSVR"
    last_evaluation: dict | None = None

    def choose(self, state: VisibleState, safe_actions: tuple[Action, ...]) -> Action:
        base = shielded_pi0_action(state, safe_actions)
        values = {action.identifier: self.evaluator(action, state) for action in safe_actions}
        self.last_evaluation = {"continuation_policy": "B1_SHIELDED_PI0", "full_horizon_for_all_actions": True, "candidate_action_ids": sorted(values), "values": values}
        return max(safe_actions, key=lambda action: (values[action.identifier], action.identifier == base.identifier, tuple(-ord(c) for c in action.identifier)))


def make_policy(policy_id: str, rollout_evaluator=None):
    if policy_id == "B0_SCAN_THEN_CONFIRM": return ScanThenConfirm()
    if policy_id == "B1_SHIELDED_PI0": return ShieldedPi0()
    if policy_id.startswith("B2_FIXED_PERIODIC_K"): return FixedPeriodic(int(policy_id.rsplit("K", 1)[1]))
    if policy_id == "B3_CAPACITY_MATCHING": return CapacityMatching()
    if policy_id == "B4_RATIO_PSVR": return RatioPSVR()
    if policy_id == "M0_EVENT_HYPOTHESIS_FRONTIER_PI0": return FrontierPi0()
    if policy_id == "M1_IDEAL_SYMMETRIC_ROLLOUT_PSVR":
        if rollout_evaluator is None: raise ValueError("M1 requires exact rollout evaluator")
        return IdealSymmetricRollout(rollout_evaluator)
    raise KeyError(policy_id)
