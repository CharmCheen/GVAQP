from __future__ import annotations

from collections import Counter

import pytest

from garc_eval.mf_psvr.stage_a import STRATA, select_stage_a_units, selection_spec


def synthetic_pool(include_collision: bool = True) -> list[dict[str, object]]:
    rows = []
    split_sizes = {"model_train": 60, "model_calibration": 20, "pool_audit": 20}
    ordinal = 0
    for split, videos in split_sizes.items():
        for video_index in range(videos):
            collision = include_collision and video_index < videos // 2
            for unit_id in range(3):
                ordinal += 1
                rows.append({
                    "source_dataset": "synthetic",
                    "session_id": f"{split}:{video_index:03d}",
                    "unit_id": unit_id,
                    "model_split_role": split,
                    "sampling_tag_only": (
                        "collision_or_near_collision" if collision else "normal_driving"
                    ),
                    "sampling_anchor_seconds": 15.0 if collision else None,
                    "anchor_time": 5.0 + 10.0 * unit_id,
                    "q1_score": ((ordinal * 37) % 101) / 100.0,
                    "q2_score": ((ordinal * 61) % 101) / 100.0,
                    "q1_witness_track_id": unit_id,
                    "q2_witness_track_id": unit_id + 10,
                })
    return rows


def test_stage_a_selection_is_exact_reproducible_and_group_capped() -> None:
    rows = synthetic_pool()
    first = select_stage_a_units(rows)
    second = select_stage_a_units(reversed(rows))
    assert first == second
    assert len(first) == 96
    assert Counter(row["model_split_role"] for row in first) == {
        "model_train": 64,
        "model_calibration": 16,
        "pool_audit": 16,
    }
    assert Counter(row["sampling_stratum"] for row in first) == {
        stratum["name"]: sum(stratum["split_quotas"].values()) for stratum in STRATA
    }
    per_video = Counter((row["source_dataset"], row["session_id"]) for row in first)
    assert max(per_video.values()) <= 2
    assert len(per_video) >= 48
    assert len({row["physical_call_id"] for row in first}) == 96


def test_stage_a_spec_has_no_label_inputs_and_fails_closed() -> None:
    spec = selection_spec()
    assert spec["input_labels_permitted"] is False
    assert not any("label" in field for field in spec["input_fields"])
    assert "FAIL_CLOSED" in spec["fallback"]
    with pytest.raises(ValueError, match="FAIL_CLOSED"):
        select_stage_a_units(synthetic_pool(include_collision=False))
