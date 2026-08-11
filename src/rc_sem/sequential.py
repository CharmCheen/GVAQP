"""Label-isolated sequential SCAN/VERIFY environment for cached replay.

The environment deliberately separates public state from evaluator-only data.
Policies can inspect only :class:`PublicSequentialState`.  Frozen oracle labels
are held privately and are revealed one at a time by a legal VERIFY action.
Reference events are never stored in the environment or passed to a policy.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class SequentialActionType(str, Enum):
    SCAN = "SCAN"
    VERIFY = "VERIFY"
    STOP = "STOP"


@dataclass(frozen=True)
class SequentialAction:
    action_type: SequentialActionType
    target_id: int | None
    reason: str

    def __post_init__(self) -> None:
        if self.action_type is SequentialActionType.STOP:
            if self.target_id is not None:
                raise ValueError("STOP cannot have a target")
        elif self.target_id is None or int(self.target_id) < 0:
            raise ValueError("SCAN and VERIFY require a nonnegative target")


@dataclass(frozen=True)
class ScanCell:
    cell_id: int
    unit_ids: tuple[int, ...]
    start_time: float
    end_time: float


@dataclass(frozen=True)
class SequentialCostConfig:
    """Abstract mechanism costs, not measured wall-clock seconds."""

    scan_cost: float = 0.1
    verify_cost: float = 1.0
    scan_cell_units: int = 10
    scan_requires_verify_reserve: bool = True

    def __post_init__(self) -> None:
        if self.scan_cost <= 0 or self.verify_cost <= 0:
            raise ValueError("action costs must be positive")
        if self.scan_cell_units <= 0:
            raise ValueError("scan_cell_units must be positive")


@dataclass(frozen=True)
class PublicSequentialState:
    """All and only information available to the runtime scheduler."""

    budget: float
    spent: float
    cells: tuple[ScanCell, ...]
    unit_windows: Mapping[int, tuple[float, float]]
    scanned_cell_ids: frozenset[int] = field(default_factory=frozenset)
    proxy_scores: Mapping[int, float] = field(default_factory=dict)
    verified_labels: Mapping[int, str] = field(default_factory=dict)
    event_groups: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    action_count: int = 0
    scan_count: int = 0
    verify_count: int = 0

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget - self.spent)

    @property
    def scanned_fraction(self) -> float:
        return len(self.scanned_cell_ids) / len(self.cells) if self.cells else 1.0

    @property
    def unscanned_cell_ids(self) -> tuple[int, ...]:
        return tuple(
            cell.cell_id for cell in self.cells if cell.cell_id not in self.scanned_cell_ids
        )

    @property
    def verifiable_unit_ids(self) -> tuple[int, ...]:
        return tuple(
            sorted(set(self.proxy_scores).difference(self.verified_labels))
        )

    @property
    def positive_unit_ids(self) -> frozenset[int]:
        return frozenset(
            int(unit_id)
            for unit_id, label in self.verified_labels.items()
            if str(label).lower() == "positive"
        )

    @property
    def determinate_verify_count(self) -> int:
        return sum(
            str(label).lower() in {"positive", "negative"}
            for label in self.verified_labels.values()
        )

    def canonical_hash(self) -> str:
        payload = {
            "budget": self.budget,
            "spent": self.spent,
            "scanned_cell_ids": sorted(self.scanned_cell_ids),
            "proxy_scores": sorted((int(k), float(v)) for k, v in self.proxy_scores.items()),
            "verified_labels": sorted((int(k), str(v)) for k, v in self.verified_labels.items()),
            "event_groups": [list(group) for group in self.event_groups],
            "action_count": self.action_count,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SequentialObservation:
    action: SequentialAction
    action_cost: float
    revealed_proxy_scores: Mapping[int, float] = field(default_factory=dict)
    revealed_label: str | None = None


def build_scan_cells(
    unit_windows: Mapping[int, tuple[float, float]],
    units_per_cell: int,
) -> tuple[ScanCell, ...]:
    ids = sorted(map(int, unit_windows))
    if ids != list(range(len(ids))):
        raise ValueError("sequential environment requires canonical contiguous unit IDs")
    cells = []
    for cell_id, offset in enumerate(range(0, len(ids), units_per_cell)):
        members = tuple(ids[offset : offset + units_per_cell])
        cells.append(
            ScanCell(
                cell_id=cell_id,
                unit_ids=members,
                start_time=float(unit_windows[members[0]][0]),
                end_time=float(unit_windows[members[-1]][1]),
            )
        )
    return tuple(cells)


def strict_k3_groups(
    verified_labels: Mapping[int, str],
    unit_windows: Mapping[int, tuple[float, float]],
    *,
    duration_cap: float = 40.0,
) -> tuple[tuple[int, ...], ...]:
    """Shared bridge-safe K3 grouping from explicit positive units only."""

    positives = sorted(
        int(unit_id)
        for unit_id, label in verified_labels.items()
        if str(label).lower() == "positive"
    )
    if not positives:
        return ()
    groups: list[list[int]] = []
    current = [positives[0]]
    for unit_id in positives[1:]:
        start = float(unit_windows[current[0]][0])
        proposed_end = float(unit_windows[unit_id][1])
        if unit_id == current[-1] + 1 and proposed_end - start <= duration_cap + 1e-9:
            current.append(unit_id)
        else:
            groups.append(current)
            current = [unit_id]
    groups.append(current)
    return tuple(tuple(group) for group in groups)


class LabelIsolatedSequentialEnv:
    """State machine that reveals proxy or oracle data only through actions."""

    VALID_LABELS = frozenset(
        {
            "positive",
            "negative",
            "unknown",
            "parse_failure",
            "timeout",
            "ambiguous",
            "abstain",
            "unusable",
        }
    )

    def __init__(
        self,
        *,
        unit_windows: Mapping[int, tuple[float, float]],
        proxy_scores: Mapping[int, float],
        oracle_labels: Mapping[int, str],
        budget: float,
        costs: SequentialCostConfig | None = None,
    ) -> None:
        self.costs = costs or SequentialCostConfig()
        self.__unit_windows = {int(k): (float(v[0]), float(v[1])) for k, v in unit_windows.items()}
        self.__proxy_scores = {int(k): float(v) for k, v in proxy_scores.items()}
        self.__oracle_labels = {int(k): str(v).lower() for k, v in oracle_labels.items()}
        if set(self.__unit_windows) != set(self.__proxy_scores) or set(self.__unit_windows) != set(self.__oracle_labels):
            raise ValueError("unit, proxy and oracle universes must match")
        if any(not 0.0 <= value <= 1.0 or not math.isfinite(value) for value in self.__proxy_scores.values()):
            raise ValueError("proxy scores must be probabilities")
        if not set(self.__oracle_labels.values()) <= self.VALID_LABELS:
            raise ValueError("unsupported oracle label")
        if budget <= 0:
            raise ValueError("budget must be positive")
        self.__cells = build_scan_cells(self.__unit_windows, self.costs.scan_cell_units)
        self.__budget = float(budget)
        self.__spent = 0.0
        self.__scanned: set[int] = set()
        self.__public_proxy: dict[int, float] = {}
        self.__revealed_labels: dict[int, str] = {}
        self.__action_count = 0
        self.__scan_count = 0
        self.__verify_count = 0
        self.__stopped = False
        self.__attempted_actions: set[tuple[str, int | None]] = set()

    @property
    def state(self) -> PublicSequentialState:
        return PublicSequentialState(
            budget=self.__budget,
            spent=self.__spent,
            cells=self.__cells,
            unit_windows=dict(self.__unit_windows),
            scanned_cell_ids=frozenset(self.__scanned),
            proxy_scores=dict(self.__public_proxy),
            verified_labels=dict(self.__revealed_labels),
            event_groups=strict_k3_groups(self.__revealed_labels, self.__unit_windows),
            action_count=self.__action_count,
            scan_count=self.__scan_count,
            verify_count=self.__verify_count,
        )

    def action_cost(self, action: SequentialAction) -> float:
        if action.action_type is SequentialActionType.SCAN:
            return self.costs.scan_cost
        if action.action_type is SequentialActionType.VERIFY:
            return self.costs.verify_cost
        return 0.0

    def step(self, action: SequentialAction) -> SequentialObservation:
        if self.__stopped:
            raise RuntimeError("environment already stopped")
        if action.action_type is SequentialActionType.STOP:
            self.__stopped = True
            return SequentialObservation(action=action, action_cost=0.0)
        target = int(action.target_id)  # guarded by SequentialAction
        key = (action.action_type.value, target)
        if key in self.__attempted_actions:
            raise RuntimeError("duplicate action attempt")
        cost = self.action_cost(action)
        if self.__spent + cost > self.__budget + 1e-12:
            raise RuntimeError("action exceeds budget")

        if action.action_type is SequentialActionType.SCAN:
            if target not in {cell.cell_id for cell in self.__cells}:
                raise RuntimeError("unknown scan cell")
            if target in self.__scanned:
                raise RuntimeError("duplicate scan")
            cell = self.__cells[target]
            revealed = {unit_id: self.__proxy_scores[unit_id] for unit_id in cell.unit_ids}
            self.__scanned.add(target)
            self.__public_proxy.update(revealed)
            self.__scan_count += 1
            observation = SequentialObservation(
                action=action,
                action_cost=cost,
                revealed_proxy_scores=revealed,
            )
        else:
            if target not in self.__public_proxy:
                raise RuntimeError("VERIFY target has not been scanned")
            if target in self.__revealed_labels:
                raise RuntimeError("duplicate VERIFY")
            label = self.__oracle_labels[target]
            self.__revealed_labels[target] = label
            self.__verify_count += 1
            observation = SequentialObservation(
                action=action,
                action_cost=cost,
                revealed_label=label,
            )

        self.__attempted_actions.add(key)
        self.__spent = round(self.__spent + cost, 12)
        self.__action_count += 1
        return observation


def validate_public_state_no_evaluator_leakage(state: PublicSequentialState) -> None:
    """Fail closed if evaluator-only vocabulary appears in the public schema."""

    forbidden = {"reference_events", "full_grid_labels", "oracle_labels", "future_labels"}
    if forbidden.intersection(state.__dict__):
        raise ValueError("evaluator-only field leaked into public sequential state")

