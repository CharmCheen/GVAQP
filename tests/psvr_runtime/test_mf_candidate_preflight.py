from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_mf_psvr_training_pool_candidates.py"
SPEC = importlib.util.spec_from_file_location("mf_candidate_preflight_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_pool_frame_windows_match_frozen_centered_tail() -> None:
    units = MODULE.make_units({
        "source_dataset": "source",
        "session_id": "video",
        "content_sha256": "a" * 64,
        "model_split_role": "model_train",
        "sampling_tag_only": "background",
        "sampling_anchor_seconds": "",
        "duration_seconds": 20.25,
        "fps": 30.0,
        "frame_or_image_count": 608,
        "local_locator": "unused.mp4",
    })
    assert units[
        ["unit_id", "anchor_time", "start_time", "end_time", "start_frame", "end_frame"]
    ].to_dict("records") == [
        {
            "unit_id": 0,
            "anchor_time": 5.0,
            "start_time": 0.0,
            "end_time": 10.0,
            "start_frame": 0,
            "end_frame": 299,
        },
        {
            "unit_id": 1,
            "anchor_time": 15.0,
            "start_time": 10.0,
            "end_time": 20.0,
            "start_frame": 300,
            "end_frame": 599,
        },
        {
            "unit_id": 2,
            "anchor_time": 20.25,
            "start_time": 15.25,
            "end_time": 20.25,
            "start_frame": 457,
            "end_frame": 607,
        },
    ]


def test_empty_track_candidates_preserve_identity_schema() -> None:
    empty = pd.DataFrame(columns=["query_id", "unit_id", "track_id"])
    identified = MODULE.add_identities(
        empty,
        {
            "source_dataset": "source",
            "session_id": "video",
            "content_sha256": "b" * 64,
            "model_split_role": "model_train",
        },
        "UNIT_OUTCOME_WITH_TRACK_WITNESS",
    )
    assert identified.empty
    assert {"verification_key", "opportunity_id", "witness_track_id"}.issubset(
        identified.columns
    )


def test_resume_marker_requires_complete_full_video_scope(tmp_path: Path) -> None:
    for filename in ("TRACK_CANDIDATES.csv", "UNIT_SCORES.csv", "UNIT_PROCESSING.json"):
        (tmp_path / filename).write_text(filename, encoding="utf-8")
    marker = {
        "status": "COMPLETE",
        "unit_scope": "SMOKE_FIRST_UNIT_ONLY",
        "unit_scope_complete": False,
        "units": 1,
        "expected_units": 3,
        "unit_score_rows": 2,
        "source_sha256": "c" * 64,
        "proxy_config_hash": "config",
        "track_candidates_sha256": MODULE.sha256_file(tmp_path / "TRACK_CANDIDATES.csv"),
        "unit_scores_sha256": MODULE.sha256_file(tmp_path / "UNIT_SCORES.csv"),
        "unit_processing_sha256": MODULE.sha256_file(tmp_path / "UNIT_PROCESSING.json"),
    }
    (tmp_path / "EXTRACTION_COMPLETE.json").write_text(
        json.dumps(marker), encoding="utf-8"
    )
    assert not MODULE.marker_valid(tmp_path, "c" * 64, "config", 3)

    marker.update({
        "unit_scope": "FULL_PROVIDER_VIDEO",
        "unit_scope_complete": True,
        "units": 3,
        "unit_score_rows": 6,
    })
    (tmp_path / "EXTRACTION_COMPLETE.json").write_text(
        json.dumps(marker), encoding="utf-8"
    )
    assert MODULE.marker_valid(tmp_path, "c" * 64, "config", 3)
    assert not MODULE.marker_valid(tmp_path, "c" * 64, "config", 4)
