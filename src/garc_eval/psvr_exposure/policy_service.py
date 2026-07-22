"""Deterministic, capability-isolated candidate-frontier policies.

The service never receives a reference table, future proxy values, video
bytes, or an oracle accessor.  It sees only candidates whose physical proxy
processing has completed and oracle observations already returned to the
trusted runtime.
"""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing as mp
import os
import tempfile
from collections import Counter
from typing import Any

from garc_eval.psvr_runtime.sandbox import (
    _enter_empty_unprivileged_jail,
    _recv_with_timeout,
)


METHODS = frozenset(
    {
        "fifo",
        "score_only",
        "cell_diverse_conservative",
        "exposure_aware",
        "exposure_minus_age",
        "exposure_minus_novelty",
        "exposure_minus_suppression",
        "exposure_temporal_nms",
        "exposure_minus_age_novelty",
        "exposure_minus_age_suppression",
        "exposure_minus_novelty_suppression",
        "exposure_temporal_nms_minus_age",
        "exposure_temporal_nms_minus_novelty",
        "exposure_temporal_nms_minus_suppression",
    }
)


def _average_percentile(values: dict[str, float]) -> dict[str, float]:
    """Average-rank percentile with larger values receiving larger ranks."""

    if not values:
        return {}
    groups: dict[float, list[str]] = {}
    for key, value in values.items():
        groups.setdefault(float(value), []).append(key)
    result: dict[str, float] = {}
    position = 1
    total = len(values)
    for value in sorted(groups):
        keys = sorted(groups[value])
        average_rank = (position + position + len(keys) - 1) / 2
        percentile = average_rank / total
        for key in keys:
            result[key] = percentile
        position += len(keys)
    return result


def _overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        float(left["start_time"]) < float(right["end_time"])
        and float(right["start_time"]) < float(left["end_time"])
    )


def _temporal_distance(
    candidate: dict[str, Any],
    regions: list[dict[str, Any]],
    video_duration: float,
) -> float:
    if not regions:
        return 1.0
    center = 0.5 * (
        float(candidate["start_time"]) + float(candidate["end_time"])
    )
    distances = []
    for region in regions:
        if _overlaps(candidate, region):
            distances.append(0.0)
            continue
        region_center = 0.5 * (
            float(region["start_time"]) + float(region["end_time"])
        )
        distances.append(abs(center - region_center))
    return min(1.0, min(distances) / max(video_duration, 1e-9))


def _entropy(unit_ids: list[int]) -> float:
    if not unit_ids:
        return 0.0
    counts = Counter(unit_ids)
    total = len(unit_ids)
    value = -sum(
        (count / total) * math.log(count / total) for count in counts.values()
    )
    return value / math.log(total) if total > 1 else 0.0


def _candidate_key(row: dict[str, Any]) -> str:
    return str(row["candidate_id"])


def _validate(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[int, dict]]:
    expected = {
        "method",
        "public_units",
        "candidate_rows",
        "queried_rows",
        "pending_unit_ids",
        "candidate_capacity",
        "current_scan_index",
        "parameters",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("candidate-frontier payload schema mismatch")
    method = str(payload["method"])
    if method not in METHODS:
        raise ValueError("unknown candidate-frontier method")
    public_units = list(payload["public_units"])
    for row in public_units:
        if set(row) != {"unit_id", "start_time", "end_time", "duration_seconds"}:
            raise ValueError("public unit schema contains a forbidden field")
    units = {
        int(row["unit_id"]): {
            "unit_id": int(row["unit_id"]),
            "start_time": float(row["start_time"]),
            "end_time": float(row["end_time"]),
        }
        for row in public_units
    }
    if sorted(units) != list(range(len(units))):
        raise ValueError("public units must have contiguous identifiers")
    capacity = int(payload["candidate_capacity"])
    if capacity <= 0:
        raise ValueError("candidate capacity must be positive")
    candidates = []
    seen = set()
    for row in payload["queried_rows"]:
        if set(row) != {"unit_id", "parsed_label"}:
            raise ValueError("queried observation schema contains a forbidden field")
    queried_ids = {int(row["unit_id"]) for row in payload["queried_rows"]}
    if not queried_ids.issubset(units):
        raise ValueError("queried observation has unknown unit")
    if set(payload["parameters"]) - {"temporal_nms_window_seconds"}:
        raise ValueError("unknown candidate-frontier parameter")
    for raw in payload["candidate_rows"]:
        required = {
            "candidate_id",
            "unit_id",
            "track_id",
            "proxy_score",
            "creation_scan_index",
            "score_availability_seconds",
        }
        if set(raw) != required:
            raise ValueError("candidate row schema mismatch")
        candidate_id = str(raw["candidate_id"])
        unit_id = int(raw["unit_id"])
        if candidate_id in seen or unit_id not in units or unit_id in queried_ids:
            raise ValueError("duplicate, unknown, or already-queried candidate")
        score = float(raw["proxy_score"])
        availability = float(raw["score_availability_seconds"])
        if not math.isfinite(score) or not math.isfinite(availability):
            raise ValueError("non-finite public candidate observation")
        creation = int(raw["creation_scan_index"])
        if creation < 0 or creation > int(payload["current_scan_index"]):
            raise ValueError("candidate creation uses a future scan")
        seen.add(candidate_id)
        candidates.append(
            {
                **raw,
                "candidate_id": candidate_id,
                "unit_id": unit_id,
                "track_id": int(raw["track_id"]),
                "proxy_score": score,
                "creation_scan_index": creation,
                "score_availability_seconds": availability,
                "start_time": units[unit_id]["start_time"],
                "end_time": units[unit_id]["end_time"],
            }
        )
    return candidates, units


def _fixed_order(
    method: str, candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if method == "fifo":
        ordered = sorted(
            candidates,
            key=lambda row: (
                int(row["creation_scan_index"]),
                float(row["score_availability_seconds"]),
                int(row["unit_id"]),
                int(row["track_id"]),
                str(row["candidate_id"]),
            ),
        )
        details = [
            {
                "candidate_id": row["candidate_id"],
                "priority": -float(row["creation_scan_index"]),
                "rule": "oldest_creation_first",
            }
            for row in ordered
        ]
        return ordered, details
    ordered = sorted(
        candidates,
        key=lambda row: (
            -float(row["proxy_score"]),
            int(row["unit_id"]),
            int(row["track_id"]),
            str(row["candidate_id"]),
        ),
    )
    details = [
        {
            "candidate_id": row["candidate_id"],
            "priority": float(row["proxy_score"]),
            "rule": "proxy_score_descending",
        }
        for row in ordered
    ]
    return ordered, details


def _cell_diverse_conservative_order(
    candidates: list[dict[str, Any]],
    payload: dict[str, Any],
    units: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One candidate per frozen unit-cell, then cell FIFO.

    The confirmed-cell exclusion is derived from the median frozen unit duration,
    which is also the unchanged K3 return window for this benchmark. There is no
    outcome-tuned parameter.
    """

    pending = {int(unit_id) for unit_id in payload["pending_unit_ids"]}
    durations = [
        float(row["end_time"]) - float(row["start_time"])
        for row in units.values()
    ]
    exclusion = sorted(durations)[len(durations) // 2]
    confirmed_centers = [
        0.5 * (
            float(units[int(row["unit_id"])]["start_time"])
            + float(units[int(row["unit_id"])]["end_time"])
        )
        for row in payload["queried_rows"]
        if str(row.get("parsed_label", "")).lower() == "positive"
    ]
    by_cell: dict[int, list[dict[str, Any]]] = {}
    for row in candidates:
        by_cell.setdefault(int(row["unit_id"]), []).append(row)
    representatives = [
        sorted(
            rows,
            key=lambda row: (
                -float(row["proxy_score"]),
                int(row["track_id"]),
                str(row["candidate_id"]),
            ),
        )[0]
        for _, rows in sorted(by_cell.items())
    ]

    def suppressed(row: dict[str, Any]) -> bool:
        unit_id = int(row["unit_id"])
        if unit_id in pending:
            return True
        center = 0.5 * (
            float(units[unit_id]["start_time"])
            + float(units[unit_id]["end_time"])
        )
        return any(abs(center - confirmed) <= exclusion for confirmed in confirmed_centers)

    eligible = [row for row in representatives if not suppressed(row)]
    fallback = False
    if not eligible:
        eligible = [row for row in representatives if int(row["unit_id"]) not in pending]
        fallback = True
    ordered = sorted(
        eligible,
        key=lambda row: (
            int(row["creation_scan_index"]),
            float(row["score_availability_seconds"]),
            int(row["unit_id"]),
            int(row["track_id"]),
            str(row["candidate_id"]),
        ),
    )
    details = [
        {
            "candidate_id": row["candidate_id"],
            "priority": -float(row["creation_scan_index"]),
            "rule": "cell_diverse_conservative_fifo",
            "cell_id": int(row["unit_id"]),
            "cell_proxy_score": float(row["proxy_score"]),
            "confirmed_exclusion_window_seconds": exclusion,
            "fallback_global_fifo": fallback,
        }
        for row in ordered
    ]
    return ordered, details


def _exposure_order(
    method: str,
    candidates: list[dict[str, Any]],
    payload: dict[str, Any],
    units: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_scan = int(payload["current_scan_index"])
    proxy_rank = _average_percentile(
        {_candidate_key(row): float(row["proxy_score"]) for row in candidates}
    )
    age_rank = _average_percentile(
        {
            _candidate_key(row): float(
                current_scan - int(row["creation_scan_index"])
            )
            for row in candidates
        }
    )
    queried_regions = [
        units[int(row["unit_id"])]
        for row in payload["queried_rows"]
        if int(row["unit_id"]) in units
    ]
    confirmed_regions = [
        units[int(row["unit_id"])]
        for row in payload["queried_rows"]
        if str(row.get("parsed_label", "")).lower() == "positive"
        and int(row["unit_id"]) in units
    ]
    explicit_pending = [
        units[int(unit_id)]
        for unit_id in payload["pending_unit_ids"]
        if int(unit_id) in units
    ]
    duration = max(
        float(row["end_time"]) for row in units.values()
    ) - min(float(row["start_time"]) for row in units.values())
    remaining = {_candidate_key(row): row for row in candidates}
    selected: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    use_age = "minus_age" not in method
    use_novelty = "minus_novelty" not in method
    use_suppression = "minus_suppression" not in method
    temporal_nms = method.startswith("exposure_temporal_nms")
    nms_window = float(payload["parameters"].get("temporal_nms_window_seconds", 10.0))
    while remaining:
        ranked = []
        retained_regions = [
            {
                "start_time": row["start_time"],
                "end_time": row["end_time"],
            }
            for row in selected
        ]
        pending_regions = explicit_pending + retained_regions
        for candidate_id, row in remaining.items():
            novelty = _temporal_distance(
                row, queried_regions + pending_regions, duration
            )
            pending_overlap = float(
                any(_overlaps(row, region) for region in pending_regions)
            )
            confirmed_overlap = float(
                any(_overlaps(row, region) for region in confirmed_regions)
            )
            if temporal_nms:
                center = 0.5 * (row["start_time"] + row["end_time"])
                near = False
                for region in pending_regions + confirmed_regions:
                    region_center = 0.5 * (
                        float(region["start_time"]) + float(region["end_time"])
                    )
                    near |= abs(center - region_center) <= nms_window
                pending_overlap = float(near)
                confirmed_overlap = 0.0
            priority = proxy_rank[candidate_id]
            if use_age:
                priority += age_rank[candidate_id]
            if use_novelty:
                priority += novelty
            if use_suppression:
                priority -= pending_overlap + confirmed_overlap
            detail = {
                "candidate_id": candidate_id,
                "proxy_rank": proxy_rank[candidate_id],
                "age_rank": age_rank[candidate_id] if use_age else 0.0,
                "temporal_novelty": novelty if use_novelty else 0.0,
                "pending_overlap": pending_overlap if use_suppression else 0.0,
                "confirmed_overlap": (
                    confirmed_overlap if use_suppression else 0.0
                ),
                "priority": priority,
                "rule": method,
            }
            ranked.append(
                (
                    priority,
                    proxy_rank[candidate_id],
                    age_rank[candidate_id],
                    novelty,
                    -int(row["creation_scan_index"]),
                    -int(row["unit_id"]),
                    -int(row["track_id"]),
                    candidate_id,
                    detail,
                )
            )
        *_, candidate_id, detail = max(ranked)
        selected.append(remaining.pop(candidate_id))
        details.append(detail)
    return selected, details


def decide_frontier(payload: dict[str, Any]) -> dict[str, Any]:
    candidates, units = _validate(payload)
    method = str(payload["method"])
    if method in {"fifo", "score_only"}:
        ordered, details = _fixed_order(method, candidates)
    elif method == "cell_diverse_conservative":
        ordered, details = _cell_diverse_conservative_order(
            candidates, payload, units
        )
    else:
        ordered, details = _exposure_order(method, candidates, payload, units)
    capacity = int(payload["candidate_capacity"])
    retained = ordered[:capacity]
    retained_ids = {row["candidate_id"] for row in retained}
    discarded = [
        row["candidate_id"] for row in candidates
        if row["candidate_id"] not in retained_ids
    ]
    priority_by_id = {row["candidate_id"]: row for row in details}
    response = {
        "selected_candidate_id": (
            None if not retained else str(retained[0]["candidate_id"])
        ),
        "selected_unit_id": (
            None if not retained else int(retained[0]["unit_id"])
        ),
        "selected_track_id": (
            None if not retained else int(retained[0]["track_id"])
        ),
        "retained_candidate_ids": [
            str(row["candidate_id"]) for row in retained
        ],
        "discarded_candidate_ids": sorted(map(str, discarded)),
        "priority_rows": [
            priority_by_id[str(row["candidate_id"])] for row in retained
        ],
        "frontier_candidates": len(retained),
        "frontier_unique_temporal_cells": len(
            {int(row["unit_id"]) for row in retained}
        ),
        "frontier_temporal_entropy": _entropy(
            [int(row["unit_id"]) for row in retained]
        ),
        "worker_uid": os.geteuid(),
        "worker_root": os.getcwd(),
        "visible_candidates": len(candidates),
        "visible_queried_units": len(payload["queried_rows"]),
    }
    response["decision_sha256"] = hashlib.sha256(
        json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return response


def _worker(connection, jail: str) -> None:
    try:
        _enter_empty_unprivileged_jail(jail)
        connection.send(
            ("ready", {"worker_uid": os.geteuid(), "worker_root": os.getcwd()})
        )
        while True:
            operation, *rest = connection.recv()
            if operation == "shutdown":
                connection.send(("ok", None))
                break
            if operation != "decide":
                connection.send(("error", "operation not allowed"))
                continue
            try:
                connection.send(("ok", decide_frontier(rest[0])))
            except Exception as exc:
                connection.send(("error", f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        try:
            connection.send(("startup_error", f"{type(exc).__name__}: {exc}"))
        except Exception:
            pass
    finally:
        connection.close()


class ExposurePolicyService:
    def __init__(self, connection, process, jail, initialization: dict[str, Any]):
        self._connection = connection
        self._process = process
        self._jail = jail
        self.initialization = dict(initialization)

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._connection.send(("decide", payload))
        status, response = _recv_with_timeout(
            self._connection, 10.0, "exposure policy decision"
        )
        if status != "ok":
            raise RuntimeError(str(response))
        return dict(response)

    def close(self) -> None:
        try:
            if self._process.is_alive():
                self._connection.send(("shutdown",))
                status, _ = _recv_with_timeout(
                    self._connection, 10.0, "exposure policy shutdown"
                )
                if status != "ok":
                    raise RuntimeError("exposure policy rejected shutdown")
                self._process.join(timeout=10)
        finally:
            self._connection.close()
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=5)
            self._jail.cleanup()


def start_exposure_policy_service() -> ExposurePolicyService:
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=True)
    jail = tempfile.TemporaryDirectory(prefix="psvr_exposure_policy_jail_")
    process = context.Process(target=_worker, args=(sender, jail.name))
    process.start()
    sender.close()
    try:
        status, payload = _recv_with_timeout(
            receiver, 20.0, "exposure policy startup"
        )
        if status != "ready":
            raise RuntimeError(f"exposure policy startup failed: {payload}")
        return ExposurePolicyService(receiver, process, jail, payload)
    except Exception:
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        jail.cleanup()
        raise
