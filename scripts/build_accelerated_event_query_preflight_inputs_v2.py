#!/usr/bin/env python3
"""Freeze exact oracle-input identities and matching pre-outcome contact sheets."""

from __future__ import annotations

import json
import os
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw

from garc_eval.accelerated_event_query.oracle_protocol import (
    canonical_hash,
    extract_exact_frames,
    public_frame_record,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
V1_PREREG = OUT / "operational_oracle/PREFLIGHT_V1_PREREGISTRATION.json"
CONFIG = OUT / "configs/stage1_freeze_v2.json"
VIDEOS = OUT / "video_manifests/frozen_videos_v1.json"
PROTOCOL = ROOT / "src/garc_eval/accelerated_event_query/oracle_protocol.py"
DESTINATION = OUT / "operational_oracle/preflight_v2"
SHEETS = DESTINATION / "contact_sheets"
FRAME_MANIFEST = DESTINATION / "ORACLE_INPUT_FRAME_MANIFEST_V2.json"
SHEET_MANIFEST = DESTINATION / "CONTACT_SHEET_MANIFEST_V2.json"


def write_once(path: Path, value: dict) -> None:
    payload = json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite nonmatching frozen artifact: {path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def contact_sheet(frames: list[dict], destination: Path) -> None:
    cell_width, cell_height = 320, 180
    columns = 7
    rows = (len(frames) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * cell_width, rows * cell_height), "black")
    draw = ImageDraw.Draw(canvas)
    for index, frame in enumerate(frames):
        image = Image.fromarray(frame["rgb"]).resize(
            (cell_width, cell_height), Image.Resampling.BILINEAR
        )
        x = index % columns * cell_width
        y = index // columns * cell_height
        canvas.paste(image, (x, y))
        label = f"{frame['target_relative_seconds']:06.3f}s"
        draw.rectangle((x + 3, y + 3, x + 75, y + 17), fill=(0, 0, 0))
        draw.text((x + 5, y + 4), label, fill=(255, 255, 255))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    canvas.save(destination, format="PNG", optimize=False)


def main() -> None:
    prereg = json.loads(V1_PREREG.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    videos = {
        row["video_id"]: row
        for row in json.loads(VIDEOS.read_text(encoding="utf-8"))["videos"]
    }
    sensitivity_ids = set(
        prereg["frame_sampling_sensitivity"]["single_sensitivity_call_candidate_ids"]
    )
    protocol_hash = sha256_file(PROTOCOL)
    frame_sets = []
    sheets = []
    for clip in prereg["clips"]:
        video = videos[clip["video_id"]]
        video_path = ROOT / video["path"]
        rates = [2.0] + ([4.0] if clip["candidate_id"] in sensitivity_ids else [])
        for sampling_fps in rates:
            frames = extract_exact_frames(
                video_path,
                float(clip["start_time"]),
                float(clip["end_time"]),
                float(Fraction(video["nominal_fps"])),
                sampling_fps,
            )
            public_frames = [public_frame_record(frame) for frame in frames]
            frame_sets.append({
                "candidate_id": clip["candidate_id"],
                "video_id": clip["video_id"],
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "sampling_fps": sampling_fps,
                "sampling_semantics": config["oracle"]["sampling_semantics"],
                "source_video_sha256": video["sha256"],
                "frame_count": len(frames),
                "frame_set_sha256": canonical_hash(public_frames),
                "frames": public_frames,
            })
            if sampling_fps == 2.0:
                destination = SHEETS / f"{clip['candidate_id']}.png"
                contact_sheet(frames, destination)
                sheets.append({
                    "candidate_id": clip["candidate_id"],
                    "video_id": clip["video_id"],
                    "contact_sheet_path": str(destination.relative_to(ROOT)),
                    "contact_sheet_sha256": sha256_file(destination),
                    "source_frame_set_sha256": canonical_hash(public_frames),
                    "frame_count": len(frames),
                    "first_relative_seconds": public_frames[0]["target_relative_seconds"],
                    "last_relative_seconds": public_frames[-1]["target_relative_seconds"],
                    "layout": "7x3_exact_oracle_frames_with_relative_target_timestamp",
                })
    frame_manifest = {
        "status": "FROZEN_BEFORE_NEW_QUERY_ORACLE_EXECUTION",
        "protocol_source_path": str(PROTOCOL.relative_to(ROOT)),
        "protocol_source_sha256": protocol_hash,
        "config_path": str(CONFIG.relative_to(ROOT)),
        "config_sha256": sha256_file(CONFIG),
        "source_selection": str(V1_PREREG.relative_to(ROOT)),
        "source_selection_sha256": sha256_file(V1_PREREG),
        "frame_set_count": len(frame_sets),
        "frame_sets": frame_sets,
    }
    write_once(FRAME_MANIFEST, frame_manifest)
    sheet_manifest = {
        "status": "FROZEN_BEFORE_NEW_QUERY_ORACLE_EXECUTION",
        "review_information_boundary": "generated before any new-query 32B output exists",
        "exact_oracle_frame_manifest_path": str(FRAME_MANIFEST.relative_to(ROOT)),
        "exact_oracle_frame_manifest_sha256": sha256_file(FRAME_MANIFEST),
        "sheet_count": len(sheets),
        "sheets": sheets,
    }
    write_once(SHEET_MANIFEST, sheet_manifest)
    print(json.dumps({
        "frame_manifest": str(FRAME_MANIFEST.relative_to(ROOT)),
        "frame_set_count": len(frame_sets),
        "sheet_manifest": str(SHEET_MANIFEST.relative_to(ROOT)),
        "sheet_count": len(sheets),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
