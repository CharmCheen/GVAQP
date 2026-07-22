"""Frozen under-/over-merge construction."""

from __future__ import annotations

from collections import defaultdict

from .rng import SplitMix64


def assign_hypotheses(rows: list[dict], under_rate: float, over_rate: float, rng: SplitMix64) -> None:
    by_event: dict[str, list[dict]] = defaultdict(list)
    groups: list[list[dict]] = []
    for row in rows:
        event_id = row["latent_event_id"]
        if event_id is None:
            groups.append([row])
        else:
            by_event[event_id].append(row)
    for event_id in sorted(by_event):
        members = sorted(by_event[event_id], key=lambda r: r["witness_id"])
        current = [members[0]]
        groups.append(current)
        for member in members[1:]:
            if rng.bernoulli(under_rate):
                current = [member]
                groups.append(current)
            else:
                current.append(member)
    groups.sort(key=lambda g: min(row["witness_id"] for row in g))
    merged: list[list[dict]] = []
    i = 0
    while i < len(groups):
        if i + 1 < len(groups) and rng.bernoulli(over_rate):
            merged.append(groups[i] + groups[i + 1])
            i += 2
        else:
            merged.append(groups[i])
            i += 1
    for group in merged:
        hypothesis_id = "h_" + min(row["witness_id"] for row in group)
        for row in group:
            row["hypothesis_id"] = hypothesis_id

