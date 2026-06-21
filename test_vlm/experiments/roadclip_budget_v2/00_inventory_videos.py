#!/usr/bin/env python3
"""Inventory local source videos for roadclip_budget_v2."""

from __future__ import annotations

import argparse
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, ffprobe_json, load_config, parse_rate, validate_base_paths, write_blocked, write_csv


VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}
FIELDS = ["video_id", "video_path", "duration_sec", "fps", "width", "height", "frame_count"]


def inspect_video(path: Path) -> dict:
    data = ffprobe_json(path)
    streams = data.get("streams") or []
    stream = streams[0] if streams else {}
    duration = float((data.get("format") or {}).get("duration") or stream.get("duration") or 0.0)
    fps = parse_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/0")
    nb_frames = stream.get("nb_frames")
    frame_count = int(nb_frames) if nb_frames and str(nb_frames).isdigit() else int(round(duration * fps)) if fps else 0
    return {
        "video_id": path.stem,
        "video_path": str(path),
        "duration_sec": f"{duration:.6f}",
        "fps": f"{fps:.6f}",
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "frame_count": frame_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory source videos.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    video_dir = Path(cfg["video_dir"])
    videos = sorted(p for p in video_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        path = write_blocked(
            output_dir,
            "BLOCKED_no_source_videos.md",
            "BLOCKED: No Source Videos",
            [f"No mp4/mov/avi/mkv files found in `{video_dir}`."],
        )
        print(f"blocked_report={path}")
        return
    rows = [inspect_video(p) for p in videos]
    out_path = output_dir / "video_inventory.csv"
    write_csv(out_path, rows, FIELDS)
    print(f"video_inventory={out_path}")
    print(f"video_count={len(rows)}")
    print(f"total_duration_sec={sum(float(r['duration_sec']) for r in rows):.3f}")


if __name__ == "__main__":
    main()
