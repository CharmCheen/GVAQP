"""Frozen physical contracts for the VERA event-enumeration pilot.

This module intentionally contains no evaluator/reference access.  It defines
the sample plan, strict parsers, and deterministic single-owner relation
composition used at inference time.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable


ENUMERATOR_VERSION = "vera_event_enumerate_contract_v1"
PRESENCE_PARSER_VERSION = "strict_presence_compatible_parser_v1"
RECONCILER_VERSION = "midpoint_single_owner_no_cross_window_merge_v1"


@dataclass(frozen=True)
class Window:
    window_id: str
    core_start: float
    core_end: float
    input_start: float
    input_end: float

    @property
    def is_last(self) -> bool:
        return self.window_id.endswith("0069")


class ContractError(ValueError):
    """A model response violated the frozen physical contract."""


def canonical_json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_windows(
    duration: float,
    core_seconds: float = 50.0,
    margin_seconds: float = 5.0,
) -> list[Window]:
    if duration <= 0 or core_seconds <= 0 or margin_seconds < 0:
        raise ValueError("invalid timeline configuration")
    windows: list[Window] = []
    start = 0.0
    index = 0
    while start < duration - 1e-9:
        end = min(duration, start + core_seconds)
        windows.append(
            Window(
                window_id=f"vera_enum_{index:04d}",
                core_start=start,
                core_end=end,
                input_start=max(0.0, start - margin_seconds),
                input_end=min(duration, end + margin_seconds),
            )
        )
        start = end
        index += 1
    return windows


def sample_frame_indices(
    start_time: float,
    end_time: float,
    video_fps: float,
    total_frames: int,
    sample_fps: float = 2.0,
) -> list[int]:
    """Match the strict benchmark's inclusive, fixed-stride OpenCV sampler."""
    if not (0 <= start_time < end_time) or video_fps <= 0 or sample_fps <= 0 or total_frames <= 0:
        raise ValueError("invalid sampling arguments")
    start_frame = max(0, int(start_time * video_fps))
    end_frame = min(total_frames - 1, int(end_time * video_fps))
    stride = max(1, int(video_fps / sample_fps))
    return list(range(start_frame, end_frame + 1, stride))


def perceived_clip_duration(frame_count: int, message_fps: float = 2.0) -> float:
    if frame_count < 1 or message_fps <= 0:
        raise ValueError("invalid perceived-duration arguments")
    return (frame_count - 1) / message_fps


def _json_object(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise ContractError("response is not text")
    left, right = text.find("{"), text.rfind("}")
    if left < 0 or right < left:
        raise ContractError("no JSON object")
    try:
        value = json.loads(text[left : right + 1])
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ContractError("top level is not an object")
    return value


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} is not numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ContractError(f"{name} is not finite")
    return out


def parse_event_enumeration(text: str, clip_duration: float) -> dict[str, Any]:
    """Validate without repairing, clamping, or reference-dependent filtering."""
    obj = _json_object(text)
    status = obj.get("clip_status")
    if status not in {"ok", "abstain"}:
        raise ContractError("clip_status outside frozen domain")
    events = obj.get("events")
    if not isinstance(events, list):
        raise ContractError("events is not a list")
    if len(events) > 50:
        raise ContractError("events exceeds frozen safety bound")
    if status == "abstain" and events:
        raise ContractError("abstain response contains events")

    object_domain = {"vehicle", "pedestrian", "cyclist", "other", "unknown"}
    boundary_domain = {
        "ok", "truncated_start", "truncated_end", "truncated_both", "uncertain"
    }
    confidence_domain = {"high", "medium", "low"}
    parsed_events: list[dict[str, Any]] = []
    previous_start = -math.inf
    for index, raw in enumerate(events):
        if not isinstance(raw, dict):
            raise ContractError(f"events[{index}] is not an object")
        start = _finite_number(raw.get("event_start"), f"events[{index}].event_start")
        end = _finite_number(raw.get("event_end"), f"events[{index}].event_end")
        if not (0.0 <= start < end <= clip_duration + 1e-6):
            raise ContractError(f"events[{index}] boundary outside clip")
        if start + 1e-12 < previous_start:
            raise ContractError("events are not chronological")
        previous_start = start
        if raw.get("event_type") != "enter_ego_path":
            raise ContractError(f"events[{index}] event_type is invalid")
        involved = raw.get("involved_object")
        if involved not in object_domain:
            raise ContractError(f"events[{index}] involved_object is invalid")
        if raw.get("ego_relevant") is not True:
            raise ContractError(f"events[{index}] ego_relevant is not true")
        boundary = raw.get("boundary_status")
        if boundary not in boundary_domain:
            raise ContractError(f"events[{index}] boundary_status is invalid")
        complete = raw.get("complete_event_visible")
        if not isinstance(complete, bool):
            raise ContractError(f"events[{index}] complete_event_visible is not bool")
        confidence = raw.get("confidence")
        if confidence not in confidence_domain:
            raise ContractError(f"events[{index}] confidence is invalid")
        identity = raw.get("object_identity")
        evidence = raw.get("evidence")
        if not isinstance(identity, str) or not identity.strip():
            raise ContractError(f"events[{index}] object_identity is empty")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ContractError(f"events[{index}] evidence is empty")
        parsed_events.append(
            {
                "event_start": start,
                "event_end": end,
                "event_type": "enter_ego_path",
                "involved_object": involved,
                "object_identity": identity.strip()[:200],
                "ego_relevant": True,
                "boundary_status": boundary,
                "complete_event_visible": complete,
                "confidence": confidence,
                "evidence": evidence.strip()[:500],
            }
        )
    reason = obj.get("abstain_reason")
    if reason is not None and not isinstance(reason, str):
        raise ContractError("abstain_reason is not null/string")
    return {"clip_status": status, "events": parsed_events, "abstain_reason": reason}


def parse_dense_presence(text: str, clip_duration: float) -> dict[str, Any]:
    obj = _json_object(text)
    label = obj.get("label")
    confidence = obj.get("confidence")
    if label not in {"positive", "negative", "abstain"}:
        raise ContractError("dense label outside frozen domain")
    if confidence not in {"high", "medium", "low"}:
        raise ContractError("dense confidence outside frozen domain")
    event_start = obj.get("event_start")
    event_end = obj.get("event_end")
    if label == "positive" and event_start is not None and event_end is not None:
        event_start = _finite_number(event_start, "event_start")
        event_end = _finite_number(event_end, "event_end")
        if not (0 <= event_start <= event_end <= clip_duration + 1e-6):
            raise ContractError("dense boundary outside clip")
    else:
        event_start = event_end = None
    return {
        "label": label,
        "confidence": confidence,
        "event_start": event_start,
        "event_end": event_end,
        "event_type": obj.get("event_type"),
        "involved_object": obj.get("involved_object"),
    }


def owner_accepts(
    absolute_start: float,
    absolute_end: float,
    core_start: float,
    core_end: float,
    timeline_end: float,
) -> bool:
    """Use midpoint ownership; the final core alone is closed on the right."""
    if absolute_end <= absolute_start:
        return False
    midpoint = (absolute_start + absolute_end) / 2.0
    if math.isclose(core_end, timeline_end, abs_tol=1e-6):
        return core_start <= midpoint <= core_end
    return core_start <= midpoint < core_end


def reconcile_owned_fragments(fragments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Canonicalize exact duplicate rows only; do not heuristically merge events.

    Ownership filtering happens before this function.  Keeping overlapping but
    non-identical rows makes oversplitting an observable failure rather than a
    post-hoc tuning opportunity.
    """
    chosen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in fragments:
        key = (
            round(float(row["start_time"]), 6),
            round(float(row["end_time"]), 6),
            str(row["involved_object"]),
            str(row["object_identity"]).strip().lower(),
        )
        incumbent = chosen.get(key)
        if incumbent is None or str(row["source_window_id"]) < str(incumbent["source_window_id"]):
            chosen[key] = dict(row)
    return sorted(
        chosen.values(),
        key=lambda r: (float(r["start_time"]), float(r["end_time"]), str(r["source_window_id"])),
    )
