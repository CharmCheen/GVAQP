"""Canonical temporal transport contract for EVENT_ENUMERATE v2.

The processor receives an already selected RGB frame tensor together with
explicit metadata describing the *source-frame* offsets of those frames.  It
is forbidden to resample that tensor.  Qwen3-VL then exposes one timestamp per
two-frame temporal patch; timestamps are averages of the two source-frame
times and are rendered to one decimal place by the installed processor.

Nothing in this module reads event references or VERA outputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import numpy as np


CONTRACT_VERSION = "event_enumerate_v2_metadata_exact_v1"
PARSER_VERSION = "event_enumerate_v2_strict_parser_v1"
RECONCILER_VERSION = "event_enumerate_v2_midpoint_owner_exact_dedup_v1"
TARGET_SAMPLE_FPS = 2.0
MAX_INTERVAL_SECONDS = 60.0
MAX_DECODED_FRAMES = 121
TEMPORAL_PATCH_SIZE = 2
TIMESTAMP_DISPLAY_DECIMALS = 1
TIMESTAMP_DISPLAY_TOLERANCE_SECONDS = 0.050001


class ContractError(ValueError):
    """An input or response violates the frozen operator contract."""


@dataclass(frozen=True)
class VideoInfo:
    path: str
    fps: float
    total_frames: int
    duration_seconds: float
    width: int
    height: int

    @classmethod
    def probe(cls, path: str | Path) -> "VideoInfo":
        resolved = Path(path).resolve()
        cap = cv2.VideoCapture(str(resolved))
        if not cap.isOpened():
            raise ContractError(f"video cannot be opened: {resolved}")
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if fps <= 0 or total_frames <= 0 or width <= 0 or height <= 0:
            raise ContractError(f"invalid video metadata: {resolved}")
        return cls(
            path=str(resolved),
            fps=fps,
            total_frames=total_frames,
            duration_seconds=total_frames / fps,
            width=width,
            height=height,
        )


@dataclass(frozen=True)
class IntervalRequest:
    interval_id: str
    input_start: float
    input_end: float
    core_start: float
    core_end: float

    def validate(self, video: VideoInfo) -> None:
        values = [self.input_start, self.input_end, self.core_start, self.core_end]
        if not all(math.isfinite(x) for x in values):
            raise ContractError("interval contains a non-finite boundary")
        if not (0.0 <= self.input_start < self.input_end <= video.duration_seconds + 1e-6):
            raise ContractError("input interval lies outside the video")
        if not (self.input_start <= self.core_start < self.core_end <= self.input_end):
            raise ContractError("core is not contained by the input interval")
        if self.input_end - self.input_start > MAX_INTERVAL_SECONDS + 1e-6:
            raise ContractError("input interval exceeds the frozen 60-second maximum")


@dataclass(frozen=True)
class FrameSelection:
    interval_id: str
    video_path: str
    source_fps: float
    source_total_frames: int
    requested_input_start: float
    requested_input_end: float
    core_start: float
    core_end: float
    frame_indices: tuple[int, ...]
    frame_timestamps: tuple[float, ...]
    relative_source_indices: tuple[int, ...]
    relative_timestamps: tuple[float, ...]
    timestamp_anchor_seconds: float
    stride_source_frames: int
    target_sample_fps: float

    @property
    def decoded_frame_count(self) -> int:
        return len(self.frame_indices)

    @property
    def actual_start(self) -> float:
        return self.frame_timestamps[0]

    @property
    def actual_end(self) -> float:
        return self.frame_timestamps[-1]

    @property
    def actual_span_seconds(self) -> float:
        return self.actual_end - self.actual_start

    @property
    def prompt_duration_seconds(self) -> float:
        return self.relative_timestamps[-1]

    @property
    def prompt_duration_text(self) -> str:
        return f"{self.prompt_duration_seconds:.1f}"

    def processor_metadata_dict(self) -> dict[str, Any]:
        """Return metadata expected by ``transformers.VideoMetadata``.

        ``total_num_frames`` describes the source-frame span, not the number of
        selected frames.  ``frames_indices`` are offsets in that source span.
        With ``do_sample_frames=False`` this preserves irregular selections and
        the actual decoded temporal scale without a second sampling operation.
        """

        span_frames = self.relative_source_indices[-1] + 1
        return {
            "total_num_frames": span_frames,
            "fps": self.source_fps,
            "width": None,
            "height": None,
            "duration": span_frames / self.source_fps,
            "video_backend": "opencv_fixed_stride_predecoded",
            "frames_indices": list(self.relative_source_indices),
        }

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.update(
            {
                "decoded_frame_count": self.decoded_frame_count,
                "actual_start": self.actual_start,
                "actual_end": self.actual_end,
                "actual_span_seconds": self.actual_span_seconds,
                "prompt_duration_seconds": self.prompt_duration_seconds,
                "processor_metadata": self.processor_metadata_dict(),
                "processor_patch_timestamps": processor_patch_timestamps(
                    self.relative_source_indices, self.source_fps
                ),
            }
        )
        return value


@dataclass(frozen=True)
class DecodedVideo:
    frames_rgb: np.ndarray
    identities: tuple[dict[str, Any], ...]


def build_frame_selection(
    video: VideoInfo,
    request: IntervalRequest,
    target_sample_fps: float = TARGET_SAMPLE_FPS,
) -> FrameSelection:
    """Apply the one frozen fixed-stride rule used by the original pilot.

    This is a single canonical strategy, not a candidate grid.  The difference
    from v1 is downstream: exact source metadata is transported and processor
    resampling is disabled.
    """

    request.validate(video)
    if not math.isfinite(target_sample_fps) or target_sample_fps <= 0:
        raise ContractError("target_sample_fps must be positive and finite")
    start_frame = max(0, int(request.input_start * video.fps))
    end_frame = min(video.total_frames - 1, int(request.input_end * video.fps))
    stride = max(1, int(video.fps / target_sample_fps))
    indices = tuple(range(start_frame, end_frame + 1, stride))
    if not indices:
        raise ContractError("frame selection is empty")
    if len(indices) > MAX_DECODED_FRAMES:
        raise ContractError(
            f"selection has {len(indices)} frames; frozen maximum is {MAX_DECODED_FRAMES}"
        )
    timestamps = tuple(index / video.fps for index in indices)
    relative_indices = tuple(index - indices[0] for index in indices)
    relative_timestamps = tuple(index / video.fps for index in relative_indices)
    return FrameSelection(
        interval_id=request.interval_id,
        video_path=video.path,
        source_fps=video.fps,
        source_total_frames=video.total_frames,
        requested_input_start=request.input_start,
        requested_input_end=request.input_end,
        core_start=request.core_start,
        core_end=request.core_end,
        frame_indices=indices,
        frame_timestamps=timestamps,
        relative_source_indices=relative_indices,
        relative_timestamps=relative_timestamps,
        timestamp_anchor_seconds=timestamps[0],
        stride_source_frames=stride,
        target_sample_fps=target_sample_fps,
    )


def _rgb_digest(rgb: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str(tuple(rgb.shape)).encode("ascii"))
    digest.update(rgb.tobytes(order="C"))
    return digest.hexdigest()


def decode_frame_selection(selection: FrameSelection) -> DecodedVideo:
    """Decode the exact scheduled frames sequentially, matching the old path."""

    wanted = set(selection.frame_indices)
    cap = cv2.VideoCapture(selection.video_path)
    if not cap.isOpened():
        raise ContractError(f"video cannot be opened: {selection.video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, selection.frame_indices[0])
    frames: list[np.ndarray] = []
    identities: list[dict[str, Any]] = []
    for frame_index in range(selection.frame_indices[0], selection.frame_indices[-1] + 1):
        ok, bgr = cap.read()
        if not ok:
            break
        if frame_index not in wanted:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        frames.append(rgb)
        identities.append(
            {
                "frame_index": frame_index,
                "timestamp_seconds": frame_index / selection.source_fps,
                "relative_timestamp_seconds":
                    (frame_index - selection.frame_indices[0]) / selection.source_fps,
                "shape": list(rgb.shape),
                "rgb_sha256": _rgb_digest(rgb),
            }
        )
    cap.release()
    actual = tuple(row["frame_index"] for row in identities)
    if actual != selection.frame_indices:
        raise ContractError(
            f"decoded frame identities differ from schedule for {selection.interval_id}"
        )
    return DecodedVideo(np.stack(frames, axis=0), tuple(identities))


def processor_patch_timestamps(
    relative_source_indices: Sequence[int],
    source_fps: float,
    temporal_patch_size: int = TEMPORAL_PATCH_SIZE,
) -> list[float]:
    """Mirror Qwen3-VL's installed timestamp calculation exactly."""

    if not relative_source_indices or source_fps <= 0 or temporal_patch_size <= 0:
        raise ContractError("invalid processor timestamp inputs")
    indices = [int(x) for x in relative_source_indices]
    if any(b <= a for a, b in zip(indices, indices[1:])):
        raise ContractError("source-frame offsets must be strictly increasing")
    if indices[0] != 0:
        raise ContractError("relative source-frame offsets must start at zero")
    remainder = len(indices) % temporal_patch_size
    if remainder:
        indices.extend([indices[-1]] * (temporal_patch_size - remainder))
    timestamps = [index / source_fps for index in indices]
    return [
        (timestamps[i] + timestamps[i + temporal_patch_size - 1]) / 2.0
        for i in range(0, len(timestamps), temporal_patch_size)
    ]


def processor_timestamp_texts(selection: FrameSelection) -> list[str]:
    return [
        f"{timestamp:.{TIMESTAMP_DISPLAY_DECIMALS}f}"
        for timestamp in processor_patch_timestamps(
            selection.relative_source_indices, selection.source_fps
        )
    ]


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
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{name} is not finite")
    return result


def parse_event_enumeration(text: str, clip_duration: float) -> dict[str, Any]:
    """Strict deterministic parser; never repair, clamp, or use references."""

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
        "ok",
        "truncated_start",
        "truncated_end",
        "truncated_both",
        "uncertain",
    }
    confidence_domain = {"high", "medium", "low"}
    parsed_events: list[dict[str, Any]] = []
    previous_start = -math.inf
    tolerance = TIMESTAMP_DISPLAY_TOLERANCE_SECONDS + 1e-12
    for index, raw in enumerate(events):
        if not isinstance(raw, dict):
            raise ContractError(f"events[{index}] is not an object")
        start = _finite_number(raw.get("event_start"), f"events[{index}].event_start")
        end = _finite_number(raw.get("event_end"), f"events[{index}].event_end")
        if not (0.0 <= start < end <= clip_duration + tolerance):
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
            raise ContractError(f"events[{index}].complete_event_visible is not bool")
        confidence = raw.get("confidence")
        if confidence not in confidence_domain:
            raise ContractError(f"events[{index}] confidence is invalid")
        identity, evidence = raw.get("object_identity"), raw.get("evidence")
        if not isinstance(identity, str) or not identity.strip():
            raise ContractError(f"events[{index}].object_identity is empty")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ContractError(f"events[{index}].evidence is empty")
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


def owner_accepts(
    absolute_start: float,
    absolute_end: float,
    core_start: float,
    core_end: float,
    timeline_end: float,
) -> bool:
    if absolute_end <= absolute_start:
        return False
    midpoint = (absolute_start + absolute_end) / 2.0
    if math.isclose(core_end, timeline_end, abs_tol=1e-6):
        return core_start <= midpoint <= core_end
    return core_start <= midpoint < core_end


def map_event_response(
    parsed: dict[str, Any],
    selection: FrameSelection,
    timeline_end: float,
) -> list[dict[str, Any]]:
    """Map model-relative timestamps using the actual first decoded frame."""

    if parsed.get("clip_status") != "ok":
        return []
    rows = []
    for event_index, event in enumerate(parsed.get("events", [])):
        relative_start = float(event["event_start"])
        relative_end = float(event["event_end"])
        if relative_end > selection.prompt_duration_seconds + TIMESTAMP_DISPLAY_TOLERANCE_SECONDS:
            raise ContractError("generated event extends beyond transported clip duration")
        absolute_start = selection.timestamp_anchor_seconds + relative_start
        absolute_end = selection.timestamp_anchor_seconds + relative_end
        row = {
            "fragment_id": f"{selection.interval_id}_event_{event_index:02d}",
            "source_interval_id": selection.interval_id,
            "generated_relative_start": relative_start,
            "generated_relative_end": relative_end,
            "start_time": absolute_start,
            "end_time": absolute_end,
            "core_start": selection.core_start,
            "core_end": selection.core_end,
            "timestamp_anchor_seconds": selection.timestamp_anchor_seconds,
            "owned": owner_accepts(
                absolute_start,
                absolute_end,
                selection.core_start,
                selection.core_end,
                timeline_end,
            ),
            **event,
        }
        rows.append(row)
    return rows


def reconcile_owned_fragments(fragments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order-invariant exact deduplication; never invent or merge events."""

    chosen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in fragments:
        if not row.get("owned", False):
            continue
        key = (
            round(float(row["start_time"]), 6),
            round(float(row["end_time"]), 6),
            str(row["involved_object"]),
            str(row["object_identity"]).strip().lower(),
        )
        incumbent = chosen.get(key)
        if incumbent is None or str(row["source_interval_id"]) < str(
            incumbent["source_interval_id"]
        ):
            chosen[key] = dict(row)
    return sorted(
        chosen.values(),
        key=lambda row: (
            float(row["start_time"]),
            float(row["end_time"]),
            str(row["source_interval_id"]),
        ),
    )


def canonical_json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
