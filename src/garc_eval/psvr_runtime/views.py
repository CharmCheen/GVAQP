"""Immutable selector-visible state and queried-evidence ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping


def _freeze_rows(rows: Iterable[Mapping]) -> tuple[Mapping, ...]:
    return tuple(MappingProxyType(dict(row)) for row in rows)


@dataclass(frozen=True)
class RuntimeConfig:
    benchmark_id: str
    video_id: str
    query_id: str
    proxy_name: str

    def __post_init__(self) -> None:
        names = tuple(self.__dataclass_fields__)
        if any(token in name.lower() for name in names for token in ("reference", "oracle_path", "cache_path", "label_path")):
            raise ValueError("runtime config must not carry evaluator reference or full-cache paths")


@dataclass(frozen=True)
class SelectorView:
    public_units: tuple[Mapping, ...]
    scanned_proxy_observations: tuple[Mapping, ...]
    queried_oracle_observations: tuple[Mapping, ...]

    @classmethod
    def build(cls, public_units: Iterable[Mapping], scanned_proxy: Iterable[Mapping], queried: Iterable[Mapping]):
        return cls(_freeze_rows(public_units), _freeze_rows(scanned_proxy), _freeze_rows(queried))

    def visible_label_count(self) -> int:
        return sum("parsed_label" in row for row in self.queried_oracle_observations)


@dataclass
class EvidenceLedger:
    """Runtime-owned append-only evidence; no cache/reference dependency."""

    _by_unit: dict[int, dict] = field(default_factory=dict)

    def append_query_result(self, observation: Mapping) -> None:
        unit_id = int(observation["unit_id"])
        if unit_id in self._by_unit:
            raise RuntimeError(f"duplicate evidence: {unit_id}")
        self._by_unit[unit_id] = dict(observation)

    def queried_observations(self) -> tuple[Mapping, ...]:
        return _freeze_rows(self._by_unit[key] for key in sorted(self._by_unit))

    def selector_view(self, public_units: Iterable[Mapping], scanned_proxy: Iterable[Mapping]) -> SelectorView:
        return SelectorView.build(public_units, scanned_proxy, self._by_unit.values())

    def materializer_trace_rows(self) -> list[dict]:
        return [
            {"unit_id": unit_id, "oracle_label_after_query": row["parsed_label"]}
            for unit_id, row in sorted(self._by_unit.items())
        ]
