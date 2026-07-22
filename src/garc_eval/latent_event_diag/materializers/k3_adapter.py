from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Sequence

import pandas as pd

from ..models import ActionType, AtomicUnit, MaterializedEvent, ObservationOutcome, OracleObservation
from .base import MaterializerConfig


@dataclass(frozen=True)
class _Run:
    selector: str = "latent_event_diag"
    method: str = "K3Adapter"
    budget: int = 0
    seed: int = 0


class K3AdapterMaterializer:
    """Adapter around the repository's actual Stage 0.7 K3 function.

    Relation observations are not consumed because the historical K3 accepts only
    binary per-unit oracle labels. This limitation is surfaced through
    ``ignored_relation_observation_count`` rather than emulated with GT.
    """

    name = "K3_adapter"

    def __init__(self) -> None:
        self._module: ModuleType | None = None
        self.ignored_relation_observation_count = 0

    @property
    def implementation_path(self) -> Path:
        return Path(__file__).resolve().parents[4] / "scripts/stage0_7_minimal_operator_compression.py"

    def _load(self) -> ModuleType:
        if self._module is None:
            spec = importlib.util.spec_from_file_location("latent_event_diag_stage07", self.implementation_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot import real K3 implementation: {self.implementation_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            self._module = module
        return self._module

    def materialize(
        self,
        units: Sequence[AtomicUnit],
        observations: Sequence[OracleObservation],
        config: MaterializerConfig,
    ) -> list[MaterializedEvent]:
        module = self._load()
        if config.core_duration_max != module.PARAMS.d_core_max or config.segment_duration_max != module.PARAMS.d_seg_max:
            raise ValueError(
                "K3 adapter is frozen to repository parameters "
                f"D_core={module.PARAMS.d_core_max}, D_seg={module.PARAMS.d_seg_max}"
            )
        index_to_id = {index: unit.unit_id for index, unit in enumerate(units)}
        id_to_index = {value: key for key, value in index_to_id.items()}
        unit_rows = []
        for index, unit in enumerate(units):
            unit_rows.append(
                {
                    "video_id": "synthetic",
                    "frame_idx": index,
                    "timestamp": unit.start_time,
                    "proxy_score": unit.cheap_score,
                    "start_frame": index,
                    "end_frame": index,
                    "start_time": unit.start_time,
                    "end_time": unit.end_time,
                }
            )
        oracle_rows = []
        self.ignored_relation_observation_count = 0
        for obs in observations:
            if obs.action_type == ActionType.PROBE_RELATION:
                self.ignored_relation_observation_count += 1
                continue
            if obs.action_type not in {ActionType.PROBE_CORE, ActionType.EXPLORE_CELL, ActionType.HARD_NEGATIVE_GAP}:
                continue
            if len(obs.target_ids) != 1 or obs.target_ids[0] not in id_to_index:
                continue
            if obs.outcome not in {ObservationOutcome.POSITIVE, ObservationOutcome.NEGATIVE}:
                continue
            oracle_rows.append(
                {
                    "call_idx": len(oracle_rows),
                    "unit_id": id_to_index[obs.target_ids[0]],
                    "oracle_label": int(obs.outcome == ObservationOutcome.POSITIVE),
                }
            )
        oracle = pd.DataFrame(oracle_rows, columns=["call_idx", "unit_id", "oracle_label"])
        original = pd.DataFrame(columns=["source_frame_ids"])
        run = _Run(budget=len(oracle_rows))
        segments = module.construct_k_segments(
            pd.DataFrame(unit_rows), oracle, original, run, "K3_gap_duration_negative_barrier"
        )
        positive_evidence = {
            obs.target_ids[0]: obs.action_id
            for obs in observations
            if len(obs.target_ids) == 1 and obs.outcome == ObservationOutcome.POSITIVE
        }
        events = []
        for _, row in segments.iterrows():
            indices = module.parse_source_ids(row["source_frame_ids"])
            anchor_ids = tuple(index_to_id[i] for i in indices if index_to_id[i] in positive_evidence)
            events.append(
                MaterializedEvent(
                    event_id=f"k3_event_{len(events)}",
                    start_time=float(row["start_time"]),
                    end_time=float(row["end_time"]),
                    anchor_ids=anchor_ids,
                    evidence_ids=tuple(positive_evidence[x] for x in anchor_ids),
                    confidence=min(0.99, 0.65 + 0.08 * len(anchor_ids)),
                )
            )
        return events
