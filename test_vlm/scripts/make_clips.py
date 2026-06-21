#!/usr/bin/env python3
"""Cut short clips from a long driving video and generate a manifest CSV.

Example:
    python test_vlm/scripts/make_clips.py \
        --video /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest_5k.mp4 \
        --out_dir test_vlm/clips/smoke \
        --manifest test_vlm/manifests/smoke_manifest.csv \
        --clip_len 6 \
        --start 0 \
        --num_clips 10 \
        --stride 30
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {video_path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def format_time(seconds: float) -> str:
    """Format seconds to HH_MM_SS string for clip_id."""
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h:02d}{m:02d}{s:02d}"


def cut_clip(
    video_path: Path,
    start_sec: float,
    duration: float,
    out_path: Path,
) -> bool:
    """Cut a single clip using ffmpeg. Returns True on success."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_sec),
        "-i", str(video_path),
        "-t", str(duration),
        "-c:v", "libopenh264",
        "-an",  # drop audio for faster processing and VLM compatibility
        "-loglevel", "error",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [WARN] ffmpeg failed for {out_path.name}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Cut short clips from a long video.")
    parser.add_argument("--video", type=Path, required=True, help="Source video path.")
    parser.add_argument("--out_dir", type=Path, required=True, help="Output directory for clips.")
    parser.add_argument("--manifest", type=Path, required=True, help="Output manifest CSV path.")
    parser.add_argument("--clip_len", type=float, default=6.0, help="Clip duration in seconds.")
    parser.add_argument("--start", type=float, default=0.0, help="Start time (seconds) in source video.")
    parser.add_argument("--num_clips", type=int, default=10, help="Number of clips to cut.")
    parser.add_argument("--stride", type=float, default=30.0, help="Seconds between clip start times.")
    parser.add_argument("--query_type", type=str, default="general_risk", help="Default query_type for manifest.")
    args = parser.parse_args()

    if not args.video.is_file():
        print(f"ERROR: video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    # Source video stem for clip_id prefix
    src_stem = args.video.stem  # e.g. "realcartest_5k"

    duration = get_video_duration(args.video)
    print(f"Source video: {args.video}")
    print(f"Duration: {duration:.1f}s")

    rows = []
    for i in range(args.num_clips):
        clip_start = args.start + i * args.stride
        clip_end = clip_start + args.clip_len
        if clip_start >= duration:
            print(f"Clip {i}: start {clip_start:.1f}s >= video duration {duration:.1f}s, stopping early.")
            break

        # Clamp end to video duration
        actual_end = min(clip_end, duration)
        actual_len = actual_end - clip_start

        clip_id = f"{src_stem}_s{format_time(clip_start)}_e{format_time(actual_end)}"
        out_path = args.out_dir / f"{clip_id}.mp4"

        print(f"Cutting clip {i}: {clip_start:.1f}s - {actual_end:.1f}s -> {out_path.name}")
        ok = cut_clip(args.video, clip_start, actual_len, out_path)
        if not ok:
            continue

        rows.append({
            "clip_id": clip_id,
            "video_path": str(out_path),
            "source_video": str(args.video),
            "start_sec": round(clip_start, 3),
            "end_sec": round(actual_end, 3),
            "query_type": args.query_type,
            "human_label": "unknown",
            "note": "auto_generated",
        })

    # Write manifest
    fieldnames = ["clip_id", "video_path", "source_video", "start_sec", "end_sec",
                  "query_type", "human_label", "note"]
    with open(args.manifest, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} clips written to {args.out_dir}")
    print(f"Manifest: {args.manifest}")


if __name__ == "__main__":
    main()
