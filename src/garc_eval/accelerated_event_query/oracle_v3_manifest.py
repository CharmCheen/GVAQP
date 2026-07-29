"""Hashing, write-once, and manifest validation primitives for AEQ V3."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .oracle_v3_parser import loads_unique


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return loads_unique(path.read_text(encoding="utf-8"))


def atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def write_json_once(path: Path, value: Any) -> None:
    payload = json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite nonmatching frozen artifact: {path}")
        return
    atomic_text(path, payload)


def validate_payload_hash(value: dict, field: str) -> None:
    claimed = value.get(field)
    unsigned = {key: item for key, item in value.items() if key != field}
    if claimed != canonical_hash(unsigned):
        raise RuntimeError(f"invalid {field}")


def validate_frame_set(frame_set: dict) -> None:
    required = {
        "candidate_id", "video_id", "start_time", "end_time", "sampling_fps",
        "sampling_semantics", "source_video_sha256", "frame_count",
        "frame_set_sha256", "frames",
    }
    if set(frame_set) != required:
        raise RuntimeError("frame-set schema mismatch")
    if frame_set["frame_count"] != len(frame_set["frames"]):
        raise RuntimeError("frame-set count mismatch")
    if frame_set["frame_set_sha256"] != canonical_hash(frame_set["frames"]):
        raise RuntimeError("frame-set payload hash mismatch")
    if not frame_set["frames"]:
        raise RuntimeError("empty frame set")
    expected_ordinals = list(range(len(frame_set["frames"])))
    if [row["ordinal"] for row in frame_set["frames"]] != expected_ordinals:
        raise RuntimeError("noncanonical frame ordinals")


def validate_call_manifest(manifest: dict, expected_count: int) -> None:
    if manifest.get("authorized_call_count") != expected_count:
        raise RuntimeError("authorized call count mismatch")
    calls = manifest.get("calls")
    if not isinstance(calls, list) or len(calls) != expected_count:
        raise RuntimeError("authorized calls missing")
    if [row.get("ordinal") for row in calls] != list(range(expected_count)):
        raise RuntimeError("authorized call ordinals are not canonical")
    if len({row.get("artifact_path") for row in calls}) != expected_count:
        raise RuntimeError("authorized artifact paths are not unique")
    for row in calls:
        claimed = row.get("call_spec_sha256")
        unsigned = {key: value for key, value in row.items() if key != "call_spec_sha256"}
        if claimed != canonical_hash(unsigned):
            raise RuntimeError(f"call self-hash mismatch: {row.get('artifact_name')}")
