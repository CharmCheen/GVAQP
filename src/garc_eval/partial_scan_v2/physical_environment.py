from __future__ import annotations

from typing import Any

from .hidden_evaluator import (
    new_scan_engine,
    raw_candidate_hash,
    replay_physical_visible,
)


class PhysicalEnvironment:
    def __init__(self, video: dict[str, Any]):
        self.video = video
        self.engine = new_scan_engine(video)
        self.raw_by_unit: dict[str, list[dict[str, Any]]] = {}

    @property
    def model_instance_identity(self) -> int:
        return id(self.engine.detector)

    @property
    def decoder_instance_identity(self) -> int:
        return id(self.engine.capture)

    def execute(self, unit: dict[str, Any]) -> dict[str, Any]:
        result = self.engine.scan(unit)
        unit_id = str(unit["unit_id"])
        self.raw_by_unit[unit_id] = result["raw_candidates"]
        return {
            "runtime": result["runtime"],
            "raw_candidate_count": len(result["raw_candidates"]),
            "raw_candidate_hash": raw_candidate_hash(
                result["raw_candidates"]
            ),
        }

    def visible_subset(
        self, video_id: str, visible_unit_ids: set[str]
    ):
        return replay_physical_visible(
            video_id, self.raw_by_unit, visible_unit_ids
        )

    def close(self) -> None:
        self.engine.close()
