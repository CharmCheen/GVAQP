"""Label-blind plan construction for one-step Guangzhou counterfactual probes."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass

from .exploratory_gate_o import temporal_bisection_order
from .exploratory_h0 import RuntimeAction, RuntimeState, legal_actions

DEADLINE_SECONDS = 300.0
ADMISSION_MODE = "exploratory_start_before_deadline"
STATE_SCHEMA_VERSION = "GUANGZHOU_B_LOGICAL_STATE_V1"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class LogicalSnapshot:
    state_id: str
    elapsed_seconds: float
    scan_order: tuple[int, ...]
    next_scan_index: int
    scanned_cells: tuple[int, ...]
    exposed_candidates: tuple[dict, ...]
    attempted_verify_units: tuple[int, ...]
    confirmed_positive_units: tuple[int, ...]
    rejected_units: tuple[int, ...]
    parent_action: RuntimeAction
    prior_cost_seconds: tuple[float, ...]

    def runtime_state(self) -> RuntimeState:
        return RuntimeState(
            elapsed_seconds=self.elapsed_seconds,
            deadline_seconds=DEADLINE_SECONDS,
            scan_order=self.scan_order,
            next_scan_index=self.next_scan_index,
            scanned_cells=frozenset(self.scanned_cells),
            exposed_units=frozenset(item["unit_id"] for item in self.exposed_candidates),
            attempted_verify_units=frozenset(self.attempted_verify_units),
        )

    def canonical(self) -> dict:
        value = asdict(self)
        value["parent_action"] = asdict(self.parent_action)
        return value

    def sha256(self) -> str:
        return canonical_sha256(self.canonical())


def reconstruct_b_snapshots(trace: Iterable[Mapping[str, object]], *, cell_count: int = 43) -> tuple[LogicalSnapshot, ...]:
    """Reconstruct each B pre-decision public state from its immutable trace."""
    order = temporal_bisection_order(cell_count)
    scanned: set[int] = set(); exposed: dict[int, dict] = {}; attempted: set[int] = set()
    positive: set[int] = set(); rejected: set[int] = set(); costs: list[float] = []
    result: list[LogicalSnapshot] = []
    for index, raw in enumerate(trace):
        action = RuntimeAction(str(raw["action_type"]), int(raw["target"]))
        snapshot = LogicalSnapshot(
            state_id=f"B_DECISION_{index:03d}",
            elapsed_seconds=float(raw["timestamp_seconds"]),
            scan_order=order,
            next_scan_index=len(scanned),
            scanned_cells=tuple(sorted(scanned)),
            exposed_candidates=tuple(exposed[unit] for unit in sorted(exposed)),
            attempted_verify_units=tuple(sorted(attempted)),
            confirmed_positive_units=tuple(sorted(positive)),
            rejected_units=tuple(sorted(rejected)),
            parent_action=action,
            prior_cost_seconds=tuple(costs),
        )
        result.append(snapshot)
        if action.kind == "SCAN":
            scanned.add(action.target)  # type: ignore[arg-type]
            for item in raw["outcome"]["exposed"]:  # type: ignore[index]
                exposed[int(item["unit_id"])] = dict(item)
        elif action.kind == "VERIFY":
            attempted.add(action.target)  # type: ignore[arg-type]
            label = str(raw["outcome"]["label"])  # type: ignore[index]
            (positive if label == "positive" else rejected).add(action.target)  # type: ignore[arg-type]
        costs.append(float(raw["physical_cost_seconds"]))
    return tuple(result)


def public_actions(snapshot: LogicalSnapshot) -> tuple[RuntimeAction, ...]:
    return legal_actions(
        snapshot.runtime_state(),
        scan_estimated_cost_seconds=None,
        verify_estimated_cost_seconds=None,
        admission_mode=ADMISSION_MODE,
    )


def _stratum(elapsed: float) -> str:
    return "early" if elapsed < 100.0 else "middle" if elapsed < 200.0 else "late"


def _proxy_spread(snapshot: LogicalSnapshot) -> float:
    scores = [float(item["score"]) for item in snapshot.exposed_candidates if item["unit_id"] not in snapshot.attempted_verify_units]
    return max(scores, default=0.0) - min(scores, default=0.0)


def _ranked_verify(snapshot: LogicalSnapshot) -> list[int]:
    attempted = set(snapshot.attempted_verify_units)
    return [
        int(item["unit_id"])
        for item in sorted(snapshot.exposed_candidates, key=lambda item: (-float(item["score"]), int(item["unit_id"])))
        if int(item["unit_id"]) not in attempted
    ]


def select_snapshots(snapshots: Iterable[LogicalSnapshot], *, target: int = 12) -> tuple[LogicalSnapshot, ...]:
    """Choose up to two SCAN and two VERIFY decisions per equal time stratum.

    Ranking uses only already exposed queue structure, proxy spread, elapsed time,
    and a stable trace index; evaluator truth is not an input.
    """
    if not 10 <= target <= 20:
        raise ValueError("target must be in [10, 20]")
    per_bucket = target // 6
    remainder = target % 6
    selected: list[LogicalSnapshot] = []
    for stratum in ("early", "middle", "late"):
        for kind in ("SCAN", "VERIFY"):
            candidates = [
                item for item in snapshots
                if _stratum(item.elapsed_seconds) == stratum
                and item.parent_action.kind == kind
                and any(action.kind == "SCAN" for action in public_actions(item))
                and any(action.kind == "VERIFY" for action in public_actions(item))
            ]
            candidates.sort(key=lambda item: (
                -len(_ranked_verify(item)), -_proxy_spread(item), -item.elapsed_seconds, item.state_id
            ))
            take = per_bucket + (1 if remainder > 0 else 0)
            remainder -= int(remainder > 0)
            selected.extend(candidates[:take])
    return tuple(sorted(selected, key=lambda item: item.state_id))


def alternatives(snapshot: LogicalSnapshot, *, maximum: int = 2) -> tuple[RuntimeAction, ...]:
    actions = public_actions(snapshot)
    ranked_verify = _ranked_verify(snapshot)
    result: list[RuntimeAction] = []
    if snapshot.parent_action.kind == "SCAN":
        result.extend(RuntimeAction("VERIFY", unit) for unit in ranked_verify[:1])
    else:
        scan = next((action for action in actions if action.kind == "SCAN"), None)
        if scan is not None:
            result.append(scan)
        result.extend(RuntimeAction("VERIFY", unit) for unit in ranked_verify if unit != snapshot.parent_action.target)
    return tuple(result[:maximum])


def build_plan(trace: Iterable[Mapping[str, object]], *, parent_trace_sha256: str, target: int = 12) -> dict:
    selected = select_snapshots(reconstruct_b_snapshots(trace), target=target)
    states = []
    by_state = {snapshot.state_id: raw for snapshot, raw in zip(reconstruct_b_snapshots(trace), trace)}
    for snapshot in selected:
        parent = by_state[snapshot.state_id]
        legal = public_actions(snapshot)
        chosen = alternatives(snapshot)
        states.append({
            "state_id": snapshot.state_id,
            "state_snapshot": snapshot.canonical(),
            "state_snapshot_sha256": snapshot.sha256(),
            "elapsed_seconds": snapshot.elapsed_seconds,
            "stratum": _stratum(snapshot.elapsed_seconds),
            "legal_actions": [asdict(item) for item in legal],
            "parent_b_action": asdict(snapshot.parent_action),
            "parent_b_transition": {
                "physical_cost_seconds": float(parent["physical_cost_seconds"]),
                "completion_seconds": float(parent["timestamp_seconds"]) + float(parent["physical_cost_seconds"]),
                "outcome": parent["outcome"],
                "event_relation_after": parent.get("current_event_relation", []),
            },
            "alternatives": [asdict(item) for item in chosen],
            "selection_reason": "label-blind: stratum x parent action type, then exposed queue size, proxy-score spread, elapsed time, state id",
        })
    plan = {
        "schema_version": "COUNTERFACTUAL_BRANCH_PROBE_PLAN_V1",
        "parent_policy": "B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1",
        "parent_trace_sha256": parent_trace_sha256,
        "selection_algorithm": "two per (early/middle/late) x (parent SCAN/VERIFY), structural ranking only",
        "selection_uses_evaluator_labels": False,
        "maximum_selected_states": target,
        "maximum_alternatives_per_state": 2,
        "admission_mode": ADMISSION_MODE,
        "states": states,
        "planned_branch_count": sum(len(item["alternatives"]) for item in states),
    }
    plan["plan_sha256"] = canonical_sha256(plan)
    return plan
