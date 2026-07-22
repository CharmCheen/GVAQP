"""Metadata-correct EVENT_ENUMERATE operator validation utilities.

This package is intentionally operator-only.  It does not import, execute, or
modify the VERA planner, risk model, or dynamic program.
"""

from .temporal_contract import (
    CONTRACT_VERSION,
    ContractError,
    FrameSelection,
    IntervalRequest,
    VideoInfo,
    build_frame_selection,
    map_event_response,
    parse_event_enumeration,
    processor_patch_timestamps,
)

__all__ = [
    "CONTRACT_VERSION",
    "ContractError",
    "FrameSelection",
    "IntervalRequest",
    "VideoInfo",
    "build_frame_selection",
    "map_event_response",
    "parse_event_enumeration",
    "processor_patch_timestamps",
]
