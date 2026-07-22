"""Evaluator-only exact legal-partition ceiling.

This is the only BCEM implementation module that accepts reference rows.
Nothing from this module is imported by the public additive optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd

from .core import Group, Partition


@dataclass(frozen=True)
class CeilingResult:
    partition: Partition
    event_f1: float
    matched_count: int
    predicted_count: int
    total_iou: float
    returned_seconds: float
    matching: tuple[tuple[int, int], ...]
    states_visited: int


@dataclass(frozen=True)
class _Value:
    total_iou: float
    returned_seconds: float
    groups: tuple[Group, ...]
    matching: tuple[tuple[int, int], ...]

    def preference(self) -> tuple:
        return (-self.total_iou, self.returned_seconds, tuple(g.anchors for g in self.groups), self.matching)


def _read_ids(value: object) -> set[int]:
    text = str(value).strip()
    for delimiter in ("|", ",", ";"):
        text = text.replace(delimiter, " ")
    out = set()
    for token in text.split():
        try:
            out.add(int(float(token)))
        except ValueError:
            pass
    return out


def _overlap_iou(group: Group, ref: object, require_anchor_support: bool = False) -> tuple[bool, float]:
    rs, re = float(getattr(ref, "start_time")), float(getattr(ref, "end_time"))
    inter = max(0.0, min(group.end_time, re) - max(group.start_time, rs))
    union = max(group.end_time, re) - min(group.start_time, rs)
    eligible = inter > 0.0
    if require_anchor_support:
        eligible = eligible and bool(set(group.anchors) & _read_ids(getattr(ref, "source_unit_ids", "")))
    return eligible, inter / union if union > 0 else 0.0


def score_partition_ordered(
    partition: Partition, reference: pd.DataFrame, *, require_anchor_support: bool = False,
) -> tuple[int, float, tuple[tuple[int, int], ...]]:
    """Exact ordered interval matching for a fixed legal partition."""
    refs = list(reference.sort_values(["start_time", "end_time"]).itertuples(index=False))
    # DP over groups/reference prefixes: maximize count then IoU, deterministic ties.
    states: dict[int, tuple[int, float, tuple[tuple[int, int], ...]]] = {-1: (0, 0.0, ())}
    for gi, group in enumerate(partition.groups):
        nxt = dict(states)  # current group unmatched
        for last_ref, (count, iou, pairs) in states.items():
            for ri in range(last_ref + 1, len(refs)):
                overlap, value = _overlap_iou(group, refs[ri], require_anchor_support)
                if not overlap:
                    continue
                candidate = (count + 1, iou + value, pairs + ((gi, ri),))
                current = nxt.get(ri)
                if current is None or (-candidate[0], -candidate[1], candidate[2]) < (-current[0], -current[1], current[2]):
                    nxt[ri] = candidate
        states = nxt
    return min(states.values(), key=lambda x: (-x[0], -x[1], x[2]))


def exact_ceiling_partition(
    edges: Mapping[int, Sequence[Group]], anchor_count: int, reference: pd.DataFrame,
    *, require_anchor_support: bool = False,
) -> CeilingResult:
    """Joint exact DP over legal partitions and ordered reference matching."""
    refs = list(reference.sort_values(["start_time", "end_time"]).itertuples(index=False))
    # Per anchor-prefix states: (last_ref, predicted_count, matched_count) -> best value.
    layers: list[dict[tuple[int, int, int], _Value]] = [dict() for _ in range(anchor_count + 1)]
    layers[0][(-1, 0, 0)] = _Value(0.0, 0.0, (), ())
    states_visited = 1
    for i in range(anchor_count):
        for (last_ref, pred_count, matched_count), value in list(layers[i].items()):
            for group in edges.get(i, ()):
                t = group.end_anchor_index + 1
                base_groups = value.groups + (group,)
                base_returned = value.returned_seconds + group.span_seconds
                # Leave the new group unmatched.
                key = (last_ref, pred_count + 1, matched_count)
                candidate = _Value(value.total_iou, base_returned, base_groups, value.matching)
                current = layers[t].get(key)
                if current is None or candidate.preference() < current.preference():
                    layers[t][key] = candidate
                for ri in range(last_ref + 1, len(refs)):
                    overlap, iou = _overlap_iou(group, refs[ri], require_anchor_support)
                    if not overlap:
                        continue
                    key = (ri, pred_count + 1, matched_count + 1)
                    matched = _Value(value.total_iou + iou, base_returned, base_groups,
                                     value.matching + ((pred_count, ri),))
                    current = layers[t].get(key)
                    if current is None or matched.preference() < current.preference():
                        layers[t][key] = matched
        states_visited += len(layers[i + 1])
    if anchor_count == 0:
        return CeilingResult(Partition(()), 0.0, 0, 0, 0.0, 0.0, (), states_visited)
    candidates = []
    rcount = len(refs)
    for (_, pred_count, matched_count), value in layers[anchor_count].items():
        f1 = 2.0 * matched_count / (pred_count + rcount) if pred_count + rcount else 0.0
        key = (-f1, -value.total_iou, value.returned_seconds,
               tuple(g.anchors for g in value.groups), value.matching)
        candidates.append((key, f1, pred_count, matched_count, value))
    if not candidates:
        raise RuntimeError("legal partition DAG has no source-to-sink path")
    _, f1, pred_count, matched_count, value = min(candidates, key=lambda x: x[0])
    return CeilingResult(Partition(value.groups), float(f1), int(matched_count), int(pred_count),
                         float(value.total_iou), float(value.returned_seconds), value.matching, states_visited)
