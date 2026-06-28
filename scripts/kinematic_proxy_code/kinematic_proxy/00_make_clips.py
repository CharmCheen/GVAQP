#!/usr/bin/env python3
"""Cut fixed-length clips from the configured dashcam video."""

import argparse
import subprocess
import sys
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, validate_base_paths, write_csv


def ffprobe_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"ffprobe failed for {video_path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def encoder_candidates() -> list[str]:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    if result.returncode != 0:
        fail("ffmpeg is required but failed to list encoders")
    encoders = result.stdout + result.stderr
    candidates = []
    for encoder in ["libx264", "libopenh264", "mpeg4"]:
        if encoder in encoders:
            candidates.append(encoder)
    if not candidates:
        fail("no usable MP4 video encoder found. Need one of: libx264, libopenh264, mpeg4")
    return candidates


def cut_clip(video_path: Path, start_sec: float, duration_sec: float, out_path: Path, encoders: list[str]) -> str:
    last_error = ""
    for encoder in encoders:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{duration_sec:.3f}",
            "-c:v",
            encoder,
            "-an",
            "-loglevel",
            "error",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and out_path.is_file():
            return encoder
        last_error = result.stderr.strip()
        if out_path.exists():
            out_path.unlink()
    fail(f"ffmpeg failed to cut {out_path}: {last_error}")


def fmt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    return f"{ms:09d}ms"


def main() -> None:
    parser = argparse.ArgumentParser(description="Make fixed-length clips for kinematic proxy scoring.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-duration-sec", type=float, default=None, help="Optional smoke-test cap from video start.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg, need_video=True, need_model=False)
    output_dir = ensure_output_dir(cfg)
    input_video = Path(cfg["input_video"])
    clip_len = float(cfg["clip_len_sec"])
    stride = float(cfg["stride_sec"])
    if clip_len <= 0 or stride <= 0:
        fail("clip_len_sec and stride_sec must be positive")

    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips_csv = output_dir / "clips.csv"

    video_duration = ffprobe_duration(input_video)
    usable_duration = min(video_duration, args.max_duration_sec) if args.max_duration_sec else video_duration
    if usable_duration < clip_len:
        fail(f"usable duration {usable_duration:.3f}s is shorter than clip_len_sec {clip_len:.3f}s")

    encoders = encoder_candidates()
    rows = []
    start = 0.0
    video_id = input_video.stem
    clip_idx = 0
    while start + clip_len <= usable_duration + 1e-6:
        end = start + clip_len
        clip_id = f"{video_id}_clip{clip_idx:05d}_s{fmt_time(start)}_e{fmt_time(end)}"
        out_path = clips_dir / f"{clip_id}.mp4"
        encoder = cut_clip(input_video, start, clip_len, out_path, encoders)
        rows.append(
            {
                "clip_id": clip_id,
                "video_id": video_id,
                "start_time": f"{start:.3f}",
                "end_time": f"{end:.3f}",
                "clip_path": str(out_path),
            }
        )
        print(f"wrote {out_path} using {encoder}", file=sys.stderr)
        clip_idx += 1
        start += stride

    write_csv(clips_csv, rows, ["clip_id", "video_id", "start_time", "end_time", "clip_path"])
    print(f"clips_csv={clips_csv}")
    print(f"clip_count={len(rows)}")


if __name__ == "__main__":
    main()
