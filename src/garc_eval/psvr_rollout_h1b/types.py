"""Visible-only values accepted by approximate H1B components."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, order=True)
class ActionView:
    identifier: str
    kind: str
    score_bin: int | None = None
    hypothesis_id: str | None = None
    witness_id: str | None = None
    region_id: str | None = None
    minimum_remaining_ticks: int = 0

@dataclass(frozen=True)
class VisibleDecisionState:
    history_hash: str
    decision_index: int
    remaining_ticks: int
    legal_actions: tuple[ActionView, ...]
    frontier: tuple[ActionView, ...] = ()

    def ordered_actions(self) -> tuple[ActionView, ...]:
        return tuple(sorted(self.legal_actions, key=lambda a: a.identifier))

    def with_remaining(self, remaining_ticks: int) -> "VisibleDecisionState":
        legal = tuple(action for action in self.legal_actions if action.kind == "STOP" or action.minimum_remaining_ticks <= remaining_ticks)
        return VisibleDecisionState(self.history_hash, self.decision_index, remaining_ticks, legal, self.frontier)
