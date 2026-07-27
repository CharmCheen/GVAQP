from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    unit_id: int
    track_id: int
    score: float
    created_elapsed_sec: float
    creation_scan_index: int


class FrozenFrontier:
    def __init__(self, capacity: int = 10):
        self.capacity = int(capacity)
        self._rows: dict[int, Candidate] = {}
        self.discarded: set[int] = set()
        self.queried: set[int] = set()

    def update(self, candidates: list[Candidate]) -> tuple[int, list[int]]:
        prior = set(self._rows)
        for row in candidates:
            if row.unit_id not in self.queried and row.unit_id not in self.discarded:
                self._rows[row.unit_id] = row
        ordered = sorted(
            self._rows.values(),
            key=lambda r: (-r.score, r.unit_id, r.track_id, r.candidate_id),
        )
        dropped = [r.unit_id for r in ordered[self.capacity :]]
        for unit_id in dropped:
            self._rows.pop(unit_id, None)
            self.discarded.add(unit_id)
        return len(set(self._rows) - prior), dropped

    def best(self) -> Candidate | None:
        if not self._rows:
            return None
        return sorted(
            self._rows.values(),
            key=lambda r: (-r.score, r.unit_id, r.track_id, r.candidate_id),
        )[0]

    def terminalize(self, unit_id: int) -> None:
        self._rows.pop(int(unit_id), None)
        self.queried.add(int(unit_id))

    def rows(self) -> list[Candidate]:
        return list(self._rows.values())

    def __len__(self) -> int:
        return len(self._rows)

