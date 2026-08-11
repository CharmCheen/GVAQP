#!/usr/bin/env python3
"""Build deterministic, pre-outcome 2 fps contact sheets for blinded review."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V1_PREREGISTRATION.json"
VIDEOS = OUT / "video_manifests/frozen_videos_v1.json"
SHEETS = OUT / "operational_oracle/preflight_v1/contact_sheets"
MANIFEST = OUT / "operational_oracle/preflight_v1/CONTACT_SHEET_MANIFEST.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_once(path: Path, value: dict) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite nonmatching contact-sheet manifest: {path}")
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    videos = {
        row["video_id"]: row
        for row in json.loads(VIDEOS.read_text(encoding="utf-8"))["videos"]
    }
    SHEETS.mkdir(parents=True, exist_ok=True)
    rows = []
    for clip in prereg["clips"]:
        video = videos[clip["video_id"]]
        source = ROOT / video["path"]
        destination = SHEETS / f"{clip['candidate_id']}.jpg"
        if not destination.exists():
            subprocess.run([
                "ffmpeg", "-v", "error", "-n",
                "-ss", f"{float(clip['start_time']):.6f}",
                "-t", f"{float(clip['end_time']) - float(clip['start_time']):.6f}",
                "-i", str(source),
                "-vf", (
                    "setpts=PTS-STARTPTS,fps=2,scale=320:-1,"
                    "drawtext=text='%{pts\\:hms}':x=5:y=5:fontsize=16:"
                    "fontcolor=white:box=1:boxcolor=black@0.55,"
                    "tile=7x3:padding=2:margin=2"
                ),
                "-frames:v", "1", "-q:v", "2", str(destination),
            ], check=True)
        rows.append({
            "candidate_id": clip["candidate_id"],
            "video_id": clip["video_id"],
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
            "stratum": clip["stratum"],
            "source_video_sha256": video["sha256"],
            "contact_sheet_path": str(destination.relative_to(ROOT)),
            "contact_sheet_sha256": sha256_file(destination),
            "frame_sampling_fps": 2.0,
            "layout": "7x3_chronological_relative_timestamp",
        })
    manifest = {
        "status": "PASS",
        "review_blinding": "generated before any new-query 32B output exists",
        "expected_sheet_count": len(prereg["clips"]),
        "observed_sheet_count": len(rows),
        "sheets": rows,
    }
    write_once(MANIFEST, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
