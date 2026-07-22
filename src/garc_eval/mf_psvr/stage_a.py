"""Frozen, label-blind Stage-A support-pilot selection for MF-PSVR."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Iterable


SELECTION_SEED = "MF_PSVR_CYCLE1_STAGE_A_V1_2026-07-18"
SPLIT_ORDER = ("model_calibration", "pool_audit", "model_train")
MAX_UNITS_PER_PROVIDER_VIDEO = 2
MINIMUM_DISTINCT_PROVIDER_VIDEOS = 48

STRATA = (
    {
        "name": "Q2_Y8_HIGH",
        "split_quotas": {"model_train": 16, "model_calibration": 4, "pool_audit": 4},
        "eligibility": "all remaining units",
        "ranking": "q2_score descending, then selection_hash and identity ascending",
        "score_threshold": None,
    },
    {
        "name": "Q1_WEAK_COLLISION_NEAR_ANCHOR",
        "split_quotas": {"model_train": 16, "model_calibration": 4, "pool_audit": 4},
        "eligibility": (
            "sampling_tag_only == collision_or_near_collision and absolute distance between "
            "unit anchor and provider event anchor <= 5.0 seconds"
        ),
        "ranking": (
            "q1_score descending, anchor_distance_seconds ascending, then selection_hash and "
            "identity ascending"
        ),
        "near_anchor_window_seconds_inclusive": 5.0,
        "score_threshold": None,
    },
    {
        "name": "LOW_SCORE_WEAK_COLLISION_NEAR_ANCHOR",
        "split_quotas": {"model_train": 10, "model_calibration": 3, "pool_audit": 3},
        "eligibility": (
            "sampling_tag_only == collision_or_near_collision and absolute distance between "
            "unit anchor and provider event anchor <= 5.0 seconds"
        ),
        "ranking": (
            "max(q1_score,q2_score) ascending, anchor_distance_seconds ascending, then "
            "selection_hash and identity ascending"
        ),
        "near_anchor_window_seconds_inclusive": 5.0,
        "score_threshold": None,
    },
    {
        "name": "HIGH_SCORE_WEAK_NORMAL",
        "split_quotas": {"model_train": 10, "model_calibration": 3, "pool_audit": 3},
        "eligibility": "sampling_tag_only == normal_driving",
        "ranking": (
            "max(q1_score,q2_score) descending, then selection_hash and identity ascending"
        ),
        "score_threshold": None,
    },
    {
        "name": "Q1_Q2_SCORE_DISAGREEMENT",
        "split_quotas": {"model_train": 6, "model_calibration": 1, "pool_audit": 1},
        "eligibility": "all remaining units",
        "ranking": (
            "abs(q1_score-q2_score) descending, then selection_hash and identity ascending"
        ),
        "score_threshold": None,
    },
    {
        "name": "DETERMINISTIC_RANDOM_BACKGROUND",
        "split_quotas": {"model_train": 6, "model_calibration": 1, "pool_audit": 1},
        "eligibility": "sampling_tag_only == normal_driving",
        "ranking": "selection_hash and identity ascending",
        "score_threshold": None,
    },
)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def selection_spec() -> dict[str, Any]:
    spec = {
        "selection_id": "MF_PSVR_CYCLE1_STAGE_A_SELECTION_V1",
        "selection_seed": SELECTION_SEED,
        "selection_unit": "one generic physical oracle call per unique source video x unit",
        "input_labels_permitted": False,
        "input_fields": [
            "source_dataset",
            "session_id",
            "unit_id",
            "model_split_role",
            "sampling_tag_only",
            "sampling_anchor_seconds",
            "anchor_time",
            "q1_score",
            "q2_score",
            "q1_witness_track_id",
            "q2_witness_track_id",
        ],
        "split_order": list(SPLIT_ORDER),
        "split_quotas": {"model_train": 64, "model_calibration": 16, "pool_audit": 16},
        "maximum_units_per_provider_video": MAX_UNITS_PER_PROVIDER_VIDEO,
        "minimum_distinct_provider_videos": MINIMUM_DISTINCT_PROVIDER_VIDEOS,
        "strata_in_priority_order": list(STRATA),
        "mutual_exclusion": (
            "Once a source-video x unit is selected, it is unavailable to every later stratum."
        ),
        "hash_rank": (
            "sha256(selection_seed|stratum_name|source_dataset|session_id|unit_id), "
            "lexicographically ascending"
        ),
        "identity_tie_break": "source_dataset, session_id, unit_id ascending",
        "quota_algorithm": (
            "For each stratum in priority order and each split in fixed split_order, greedily "
            "take the first eligible unselected unit in the stated total order while enforcing "
            "the global two-unit provider-video cap."
        ),
        "fallback": (
            "FAIL_CLOSED before any oracle call if any stratum x split cell cannot be filled; "
            "there is no quota borrowing, threshold relaxation, stratum substitution, or "
            "label-aware replacement."
        ),
        "freeze_rule": "All 96 identities and both query witnesses are durable before call 1.",
    }
    spec["selection_spec_hash"] = canonical_hash(spec)
    return spec


def _identity(row: dict[str, Any]) -> tuple[str, str, int]:
    return str(row["source_dataset"]), str(row["session_id"]), int(row["unit_id"])


def _hash_rank(stratum: str, row: dict[str, Any]) -> str:
    source, session, unit_id = _identity(row)
    return hashlib.sha256(
        f"{SELECTION_SEED}|{stratum}|{source}|{session}|{unit_id}".encode("utf-8")
    ).hexdigest()


def _finite_score(row: dict[str, Any], key: str) -> float:
    value = float(row[key])
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"{key} must be finite and in [0,1]: {_identity(row)}={value}")
    return value


def _anchor_distance(row: dict[str, Any]) -> float:
    value = row.get("sampling_anchor_seconds")
    if value in (None, ""):
        return math.inf
    value = float(value)
    if not math.isfinite(value):
        return math.inf
    return abs(float(row["anchor_time"]) - value)


def _eligible(name: str, row: dict[str, Any]) -> bool:
    if name in {"Q2_Y8_HIGH", "Q1_Q2_SCORE_DISAGREEMENT"}:
        return True
    if name in {
        "Q1_WEAK_COLLISION_NEAR_ANCHOR",
        "LOW_SCORE_WEAK_COLLISION_NEAR_ANCHOR",
    }:
        return (
            row["sampling_tag_only"] == "collision_or_near_collision"
            and _anchor_distance(row) <= 5.0
        )
    if name in {"HIGH_SCORE_WEAK_NORMAL", "DETERMINISTIC_RANDOM_BACKGROUND"}:
        return row["sampling_tag_only"] == "normal_driving"
    raise ValueError(f"Unknown Stage-A stratum: {name}")


def _rank_key(name: str, row: dict[str, Any]) -> tuple[Any, ...]:
    q1 = _finite_score(row, "q1_score")
    q2 = _finite_score(row, "q2_score")
    hash_rank = _hash_rank(name, row)
    identity = _identity(row)
    if name == "Q2_Y8_HIGH":
        primary = (-q2,)
    elif name == "Q1_WEAK_COLLISION_NEAR_ANCHOR":
        primary = (-q1, _anchor_distance(row))
    elif name == "LOW_SCORE_WEAK_COLLISION_NEAR_ANCHOR":
        primary = (max(q1, q2), _anchor_distance(row))
    elif name == "HIGH_SCORE_WEAK_NORMAL":
        primary = (-max(q1, q2),)
    elif name == "Q1_Q2_SCORE_DISAGREEMENT":
        primary = (-abs(q1 - q2),)
    elif name == "DETERMINISTIC_RANDOM_BACKGROUND":
        primary = ()
    else:
        raise ValueError(f"Unknown Stage-A stratum: {name}")
    return (*primary, hash_rank, *identity)


def select_stage_a_units(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select the exactly frozen 96 generic calls without outcome information."""
    materialized = [dict(row) for row in rows]
    identities = [_identity(row) for row in materialized]
    if len(identities) != len(set(identities)):
        raise ValueError("Stage-A input contains duplicate source-video x unit identities")
    allowed_splits = set(SPLIT_ORDER)
    for row in materialized:
        if row["model_split_role"] not in allowed_splits:
            raise ValueError(f"Unknown split role: {row['model_split_role']}")
        _finite_score(row, "q1_score")
        _finite_score(row, "q2_score")

    selected: list[dict[str, Any]] = []
    selected_identities: set[tuple[str, str, int]] = set()
    per_video: Counter[tuple[str, str]] = Counter()
    for stratum_index, stratum in enumerate(STRATA):
        name = str(stratum["name"])
        for split in SPLIT_ORDER:
            quota = int(stratum["split_quotas"][split])
            eligible = [
                row
                for row in materialized
                if row["model_split_role"] == split
                and _identity(row) not in selected_identities
                and _eligible(name, row)
            ]
            eligible.sort(key=lambda row: _rank_key(name, row))
            choices = []
            for row in eligible:
                if per_video[_identity(row)[:2]] >= MAX_UNITS_PER_PROVIDER_VIDEO:
                    continue
                choices.append(row)
                per_video[_identity(row)[:2]] += 1
                if len(choices) == quota:
                    break
            if len(choices) < quota:
                for row in choices:
                    per_video[_identity(row)[:2]] -= 1
                raise ValueError(
                    f"FAIL_CLOSED insufficient {name} x {split}: need {quota}, "
                    f"have {len(choices)} under the provider-video cap"
                )
            for within_cell_rank, row in enumerate(choices, start=1):
                identity = _identity(row)
                selected_identities.add(identity)
                enriched = dict(row)
                enriched.update({
                    "sampling_stratum": name,
                    "stratum_priority": stratum_index + 1,
                    "within_stratum_split_rank": within_cell_rank,
                    "selection_hash": _hash_rank(name, row),
                    "anchor_distance_seconds": (
                        None if math.isinf(_anchor_distance(row)) else _anchor_distance(row)
                    ),
                })
                selected.append(enriched)

    expected = sum(sum(stratum["split_quotas"].values()) for stratum in STRATA)
    if len(selected) != expected or expected != 96:
        raise ValueError(f"Stage-A selection count mismatch: {len(selected)} != 96")
    split_counts = Counter(row["model_split_role"] for row in selected)
    if split_counts != Counter({"model_train": 64, "model_calibration": 16, "pool_audit": 16}):
        raise ValueError(f"Stage-A split quota mismatch: {dict(split_counts)}")
    distinct_videos = len({(row["source_dataset"], row["session_id"]) for row in selected})
    if distinct_videos < MINIMUM_DISTINCT_PROVIDER_VIDEOS:
        raise ValueError(f"Stage-A provider-video coverage is only {distinct_videos}")
    if max(per_video.values(), default=0) > MAX_UNITS_PER_PROVIDER_VIDEO:
        raise ValueError("Stage-A provider-video cap violated")
    for call_index, row in enumerate(selected, start=1):
        row["physical_call_id"] = f"mf_psvr_stage_a_{call_index:03d}"
    return selected
