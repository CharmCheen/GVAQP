from __future__ import annotations

from typing import Any, Sequence


STAGE_B_VISIBLE_FIELDS = {
    "proposal_id",
    "start_frame_index",
    "peak_frame_index",
    "end_frame_index",
}


def render_stage_a(template: str, frame_count: int) -> str:
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    rendered = template.replace("__LAST_FRAME_INDEX__", f"{frame_count - 1:03d}")
    if "__LAST_FRAME_INDEX__" in rendered:
        raise ValueError("unresolved Stage A placeholder")
    return rendered


def stage_b_payload(proposal: dict[str, Any]) -> dict[str, Any]:
    """Project Stage A output onto the frozen anti-confirmation-bias allowlist."""
    missing = STAGE_B_VISIBLE_FIELDS - set(proposal)
    if missing:
        raise ValueError(f"proposal is missing Stage B fields: {sorted(missing)}")
    return {field: proposal[field] for field in sorted(STAGE_B_VISIBLE_FIELDS)}


def render_stage_b(template: str, proposal: dict[str, Any]) -> str:
    visible = stage_b_payload(proposal)
    replacements = {
        "__PROPOSAL_ID__": str(visible["proposal_id"]),
        "__START_FRAME_INDEX__": f"{visible['start_frame_index']:03d}",
        "__PEAK_FRAME_INDEX__": f"{visible['peak_frame_index']:03d}",
        "__END_FRAME_INDEX__": f"{visible['end_frame_index']:03d}",
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    if any(placeholder in rendered for placeholder in replacements):
        raise ValueError("unresolved Stage B placeholder")
    return rendered


def source_timestamp(frame_index: int, decoded_timestamps_sec: Sequence[float]) -> float:
    if isinstance(frame_index, bool) or not isinstance(frame_index, int):
        raise TypeError("frame_index must be an integer")
    if frame_index < 0 or frame_index >= len(decoded_timestamps_sec):
        raise IndexError(frame_index)
    return float(decoded_timestamps_sec[frame_index])
