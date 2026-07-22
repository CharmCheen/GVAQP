"""Exact finite-support D2-T bounds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToyBounds:
    # Supremum from the frozen universe: ratio<=5, activity<=2, v<=.8.
    scan_core_upper: float = 56.25
    confirm_core_upper: float = 13.5
    mode_switch_upper: float = 0.25

    @property
    def scan(self) -> float:
        return self.scan_core_upper + self.mode_switch_upper

    @property
    def confirm(self) -> float:
        return self.confirm_core_upper + self.mode_switch_upper

    @property
    def standard_confirm_reserve(self) -> float:
        return self.confirm

    def bound_for(self, kind: str) -> float:
        if kind == "SCAN":
            return self.scan
        if kind == "CONFIRM":
            return self.confirm
        if kind == "STOP":
            return 0.0
        raise ValueError(kind)

