"""Build frame metadata table from BDD100K image directory.

BDD100K validation set contains ~10,000 JPEG images (1280x720).
Each image is from a distinct dashcam clip.

Usage:
    python -m garc_eval.datasets.build_bdd100k_frame_table \
        --images-dir /path/to/bdd100k/images/val \
        --output-frame-table /path/to/output/frame_metadata.parquet \
        --max-frames 10000
"""

from __future__ import annotations

import argparse
import pathlib

import pandas as pd


def build_bdd100k_frame_table(
    *,
    images_dir: str,
    output_frame_table: str,
    max_frames: int | None = None,
) -> pd.DataFrame:
    root = pathlib.Path(images_dir)
    if not root.exists():
        raise FileNotFoundError(f"Images directory does not exist: {root}")

    # BDD100K images are JPEG files named like: 0000f77c-6257be58.jpg
    images = sorted(root.glob("*.jpg"))
    if not images:
        # Try .png as fallback
        images = sorted(root.glob("*.png"))
    if not images:
        raise RuntimeError(f"No image files (.jpg/.png) found in {root}")

    if max_frames is not None and max_frames > 0:
        images = images[:max_frames]

    rows = []
    for idx, src in enumerate(images):
        rows.append(
            {
                "video_id": src.stem,  # each image is its own "video"
                "frame_idx": 0,
                "timestamp": 0.0,
                "image_path": str(src),
            }
        )

    df = pd.DataFrame(rows)
    df.insert(0, "id", range(len(df)))

    if df["id"].duplicated().any():
        raise ValueError("Generated duplicate ids")

    missing_paths = [p for p in df["image_path"] if not pathlib.Path(p).exists()]
    if missing_paths:
        raise FileNotFoundError(
            f"{len(missing_paths)} image_path values do not exist; first: {missing_paths[0]}"
        )

    out = pathlib.Path(output_frame_table)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".parquet":
        df.to_parquet(out, index=False)
    else:
        df.to_csv(out, index=False)

    print(f"Saved BDD100K frame table: {out}")
    print(f"Total frames: {len(df)}")
    print(f"Source directory: {root}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build BDD100K frame metadata table"
    )
    parser.add_argument(
        "--images-dir",
        required=True,
        help="Directory containing BDD100K JPEG images",
    )
    parser.add_argument(
        "--output-frame-table",
        required=True,
        help="Output path for frame metadata parquet/csv",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum number of frames to include (default: all)",
    )
    args = parser.parse_args()

    build_bdd100k_frame_table(
        images_dir=args.images_dir,
        output_frame_table=args.output_frame_table,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
