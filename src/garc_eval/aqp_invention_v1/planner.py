"""Risk-discretized temporal relation-cover optimizer for VERA."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from typing import Iterable


@dataclass(frozen=True, order=True)
class PlanEdge:
    start: int
    end: int
    operator: str
    predicted_cost: float
    predicted_risk: float
    input_start: int
    input_end: int
    logical_calls: int = 1

    def validate(self, n: int) -> None:
        if not (0 <= self.input_start <= self.start < self.end <= self.input_end <= n):
            raise ValueError(f"invalid edge bounds: {self}")
        if self.predicted_cost < 0 or self.predicted_risk < 0:
            raise ValueError(f"negative edge cost/risk: {self}")


@dataclass(frozen=True)
class Plan:
    edges: tuple[PlanEdge, ...]
    predicted_cost: float
    rounded_risk: float
    logical_calls: int


def make_cover_edges(
    n: int,
    core_lengths: Iterable[int],
    margin: int,
    enumerate_cost: dict[int, float],
    enumerate_risk_per_unit: dict[int, float],
    dense_cost: float = 1.0,
) -> list[PlanEdge]:
    """Generate all legal temporal edges, including a zero-risk dense path."""
    lengths = sorted(set(int(x) for x in core_lengths if int(x) > 0))
    edges: list[PlanEdge] = []
    for start in range(n):
        edges.append(PlanEdge(start, start + 1, "DENSE_UNIT", dense_cost, 0.0, start, start + 1))
        for length in lengths:
            end = min(n, start + length)
            if end <= start:
                continue
            edges.append(
                PlanEdge(
                    start=start,
                    end=end,
                    operator=f"EVENT_ENUMERATE_L{length}",
                    predicted_cost=float(enumerate_cost[length]),
                    predicted_risk=float(enumerate_risk_per_unit[length]) * (end - start),
                    input_start=max(0, start - margin),
                    input_end=min(n, end + margin),
                )
            )
    for edge in edges:
        edge.validate(n)
    return edges


def optimize_cover(
    n: int,
    edges: Iterable[PlanEdge],
    max_risk: float,
    risk_quantum: float,
) -> Plan:
    """Exact DP for the upward-discretized resource-constrained DAG.

    Each edge risk is rounded upward, so a returned plan never exceeds the
    supplied risk budget in the original (unrounded) model.
    """
    if n < 0 or max_risk < 0 or risk_quantum <= 0:
        raise ValueError("invalid optimizer arguments")
    kmax = int(floor(max_risk / risk_quantum + 1e-12))
    by_start: dict[int, list[PlanEdge]] = {i: [] for i in range(n)}
    for edge in edges:
        edge.validate(n)
        by_start[edge.start].append(edge)
    # value: (cost, calls, max_input_span, lexical_edge_keys, path)
    states: list[dict[int, tuple[float, int, int, tuple, tuple[PlanEdge, ...]]]] = [dict() for _ in range(n + 1)]
    states[0][0] = (0.0, 0, 0, tuple(), tuple())
    for pos in range(n):
        for used, state in list(states[pos].items()):
            for edge in by_start.get(pos, []):
                krisk = int(ceil(edge.predicted_risk / risk_quantum - 1e-15))
                new_used = used + krisk
                if new_used > kmax:
                    continue
                key = (edge.operator, edge.start, edge.end, edge.input_start, edge.input_end)
                candidate = (
                    state[0] + edge.predicted_cost,
                    state[1] + edge.logical_calls,
                    max(state[2], edge.input_end - edge.input_start),
                    state[3] + (key,),
                    state[4] + (edge,),
                )
                old = states[edge.end].get(new_used)
                if old is None or candidate[:4] < old[:4]:
                    states[edge.end][new_used] = candidate
    if not states[n]:
        raise RuntimeError("no feasible cover, including dense fallback")
    used, best = min(states[n].items(), key=lambda item: (item[1][:4], item[0]))
    return Plan(best[4], best[0], used * risk_quantum, best[1])


def assign_owner(position: float, edges: Iterable[PlanEdge]) -> PlanEdge:
    """Return the unique ownership-core edge for a timeline position."""
    owners = [e for e in edges if e.start <= position < e.end]
    if len(owners) != 1:
        raise ValueError(f"expected one owner for {position}, got {len(owners)}")
    return owners[0]
