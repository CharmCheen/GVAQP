#!/usr/bin/env python3
"""Create a masked manifest from a raw manifest, replacing video_path with masked clips.

Example:
    python test_vlm/scripts/make_masked_manifest.py \
        --raw_manifest test_vlm/manifests/round2_5k_stride3_raw_manifest.csv \
        --masked_dir test_vlm/clips/round2_5k_stride3_masked \
        --out test_vlm/manifests/round2_5k_stride3_masked_manifest.csv
"""

import argparse
import csv
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_manifest", type=Path, required=True)
    parser.add_argument("--masked_dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.raw_manifest.is_file():
        print(f"ERROR: {args.raw_manifest}", file=sys.stderr)
        sys.exit(1)

    with open(args.raw_manifest, newline="") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys()) if rows else []
    for row in rows:
        clip_file = Path(row["video_path"]).name
        masked_path = args.masked_dir / clip_file
        row["video_path"] = str(masked_path)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Masked manifest written: {args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
