from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

from .artifacts import canonical_hash
from .config import ROOT, V1_DERIVED, V1_IMMUTABLE


SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
v1_common = importlib.import_module("partial_scan_pilot_common")
v1_runner = importlib.import_module("run_partial_scan_pilot")


def load_videos() -> pd.DataFrame:
    return pd.read_csv(V1_IMMUTABLE / "videos.csv")


def load_video(video_id: str) -> dict[str, Any]:
    videos = load_videos()
    selected = videos[videos.video_id.eq(video_id)]
    if len(selected) != 1:
        raise KeyError(video_id)
    return selected.iloc[0].to_dict()


def load_units(video_id: str) -> list[dict[str, Any]]:
    timeline = pd.read_csv(V1_IMMUTABLE / "timeline_units.csv")
    selected = timeline[timeline.video_id.eq(video_id)].sort_values("unit_index")
    if selected.empty:
        raise KeyError(video_id)
    return selected.to_dict("records")


def load_references(video_id: str) -> pd.DataFrame:
    frame = pd.read_csv(V1_IMMUTABLE / "reference_events.csv")
    return frame[frame.video_id.eq(video_id)].copy()


def warm_source_bytes(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    byte_count = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(16 * 1024 * 1024):
            byte_count += len(chunk)
            digest.update(chunk)
    return {
        "protocol": "CONTROLLED_WARM",
        "operation": (
            "sequential read of all source bytes immediately before "
            "decoder/model setup"
        ),
        "bytes_read": byte_count,
        "elapsed_sec": time.perf_counter() - started,
        "content_sha256": digest.hexdigest(),
    }


def transition(
    previous: dict[str, Any] | None, selected: dict[str, Any]
) -> dict[str, Any]:
    return v1_common.transition(previous, selected)


def replay_frozen_visible(
    video_id: str, visible_unit_ids: set[str]
) -> tuple[pd.DataFrame, set[str]]:
    candidates = v1_common.visible_candidates(video_id, visible_unit_ids)
    references = load_references(video_id)
    mapping = v1_runner.candidate_reference_map(candidates, references)
    return candidates, set(mapping.reference_event_id.astype(str))


def visible_candidates_from_raw(
    raw_by_unit: dict[str, list[dict[str, Any]]],
    visible_unit_ids: set[str],
) -> pd.DataFrame:
    raw: list[dict[str, Any]] = []
    for unit_id in sorted(visible_unit_ids):
        raw.extend(raw_by_unit.get(unit_id, []))
    if not raw:
        return pd.DataFrame(
            columns=[
                "candidate_id",
                "video_id",
                "source_unit_ids",
                "candidate_start_sec",
                "candidate_end_sec",
                "generation_state_hash",
                "admission_version",
                "candidate_score",
            ]
        )
    frame = pd.DataFrame(raw)
    normalized = []
    for feature in v1_common.BASE_FEATURES:
        values = pd.to_numeric(frame[feature], errors="coerce").fillna(0.0)
        ranks = pd.Series(0.0, index=frame.index)
        positive = values > 0
        if positive.any():
            ranks.loc[positive] = values.loc[positive].rank(
                method="average", pct=True
            )
        normalized.append(ranks)
    frame["candidate_score"] = pd.concat(normalized, axis=1).mean(axis=1)
    ordered = frame.sort_values(
        ["candidate_score", "candidate_id"], ascending=[False, True]
    )
    admitted: list[dict[str, Any]] = []
    for row in ordered.to_dict("records"):
        if any(
            v1_common.temporal_iou(row, prior)
            >= v1_common.TEMPORAL_NMS_IOU
            for prior in admitted
        ):
            continue
        admitted.append(row)
    state_hash = canonical_hash(sorted(visible_unit_ids))
    for row in admitted:
        row["generation_state_hash"] = state_hash
        row["admission_version"] = "visible_percentile_temporal_nms_v1"
    return pd.DataFrame(admitted)


def replay_physical_visible(
    video_id: str,
    raw_by_unit: dict[str, list[dict[str, Any]]],
    visible_unit_ids: set[str],
) -> tuple[pd.DataFrame, set[str]]:
    candidates = visible_candidates_from_raw(raw_by_unit, visible_unit_ids)
    references = load_references(video_id)
    mapping = v1_runner.candidate_reference_map(candidates, references)
    return candidates, set(mapping.reference_event_id.astype(str))


def raw_candidate_hash(rows: list[dict[str, Any]]) -> str:
    normalized = json.loads(
        json.dumps(rows, sort_keys=True, ensure_ascii=False, allow_nan=False)
    )
    return canonical_hash(normalized)


def new_scan_engine(video: dict[str, Any]):
    return v1_common.ScanEngine(video)
