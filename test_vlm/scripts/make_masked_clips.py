#!/usr/bin/env python3
"""Mask top subtitle and bottom watermark regions of video clips.

Example:
    python test_vlm/scripts/make_masked_clips.py \
        --in_dir test_vlm/clips/round2_5k_stride3_raw \
        --out_dir test_vlm/clips/round2_5k_stride3_masked \
        --top_pct 0.15 --bottom_pct 0.10
"""

import argparse
import subprocess
import sys
from pathlib import Path


def mask_clip(in_path: Path, out_path: Path, top_pct: float, bottom_pct: float) -> bool:
    """Apply black bars to top and bottom of video."""
    # Get video dimensions
    cmd_probe = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        str(in_path),
    ]
    r = subprocess.run(cmd_probe, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [WARN] ffprobe failed for {in_path.name}: {r.stderr.strip()}", file=sys.stderr)
        return False
    w, h = map(int, r.stdout.strip().split(","))

    top_h = int(h * top_pct)
    bot_h = int(h * bottom_pct)

    # Use drawbox to black out top and bottom regions
    filter_str = (
        f"drawbox=x=0:y=0:w={w}:h={top_h}:color=black:t=fill,"
        f"drawbox=x=0:y={h - bot_h}:w={w}:h={bot_h}:color=black:t=fill"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(in_path),
        "-vf", filter_str,
        "-c:v", "libopenh264",
        "-an",
        "-loglevel", "error",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [WARN] ffmpeg failed for {out_path.name}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Mask subtitle/watermark regions of clips.")
    parser.add_argument("--in_dir", type=Path, required=True, help="Input clips directory.")
    parser.add_argument("--out_dir", type=Path, required=True, help="Output masked clips directory.")
    parser.add_argument("--top_pct", type=float, default=0.15, help="Fraction of height to black out at top.")
    parser.add_argument("--bottom_pct", type=float, default=0.10, help="Fraction of height to black out at bottom.")
    args = parser.parse_args()

    if not args.in_dir.is_dir():
        print(f"ERROR: input dir not found: {args.in_dir}", file=sys.stderr)
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    clips = sorted(args.in_dir.glob("*.mp4"))
    print(f"Found {len(clips)} clips in {args.in_dir}")

    ok_count = 0
    for clip in clips:
        out_path = args.out_dir / clip.name
        print(f"Masking {clip.name} ...", end=" ", flush=True)
        if mask_clip(clip, out_path, args.top_pct, args.bottom_pct):
            ok_count += 1
            print("OK")
        else:
            print("FAILED")

    print(f"\nDone. {ok_count}/{len(clips)} masked clips written to {args.out_dir}")


if __name__ == "__main__":
    main()
