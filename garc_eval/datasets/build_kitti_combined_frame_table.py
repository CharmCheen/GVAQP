"""Build one frame metadata table from multiple KITTI Raw image sequences."""

from __future__ import annotations

import argparse
import pathlib

import pandas as pd


def _find_sequence_dir(root: pathlib.Path, sequence: str) -> pathlib.Path:
    direct = root / sequence
    if direct.exists():
        return direct
    matches = [p for p in root.rglob(sequence) if p.is_dir()]
    if matches:
        return sorted(matches, key=lambda p: str(p))[0]
    raise FileNotFoundError(f"Could not find extracted sequence directory for {sequence} under {root}")


def _find_images(sequence_dir: pathlib.Path, sequence: str, camera: str) -> list[pathlib.Path]:
    date = sequence.split("_drive_")[0]
    preferred = sequence_dir / date / sequence / camera / "data"
    if preferred.exists():
        images = sorted(preferred.glob("*.png"))
        if images:
            return images
    candidates = []
    for data_dir in sequence_dir.rglob("data"):
        if data_dir.parent.name == camera:
            candidates.extend(data_dir.glob("*.png"))
    return sorted(candidates, key=lambda p: str(p).lower())


def build_combined_frame_table(
    *,
    kitti_root: str,
    sequences: list[str],
    camera: str,
    output_frame_table: str,
) -> pd.DataFrame:
    root = pathlib.Path(kitti_root)
    rows = []
    per_sequence = {}

    for sequence in sequences:
        sequence_dir = _find_sequence_dir(root, sequence)
        images = _find_images(sequence_dir, sequence, camera)
        if not images:
            raise RuntimeError(f"No frames found for {sequence} camera {camera} under {sequence_dir}")
        per_sequence[sequence] = len(images)
        for src in images:
            rows.append(
                {
                    "video_id": sequence,
                    "frame_idx": int(src.stem),
                    "timestamp": round(int(src.stem) / 10.0, 4),
                    "image_path": str(src),
                }
            )

    df = pd.DataFrame(rows)
    df.insert(0, "id", range(len(df)))
    if df["id"].duplicated().any():
        raise ValueError("Generated duplicate ids")
    missing_paths = [p for p in df["image_path"] if not pathlib.Path(p).exists()]
    if missing_paths:
        raise FileNotFoundError(f"{len(missing_paths)} image_path values do not exist; first: {missing_paths[0]}")

    out = pathlib.Path(output_frame_table)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".parquet":
        df.to_parquet(out, index=False)
    else:
        df.to_csv(out, index=False)

    print(f"Saved combined frame table: {out}")
    print(f"Total frames: {len(df)}")
    for sequence, count in per_sequence.items():
        print(f"{sequence}: {count}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build combined KITTI Raw frame metadata")
    parser.add_argument("--kitti-root", required=True, help="Root containing extracted KITTI Raw sync directories")
    parser.add_argument("--sequences", nargs="+", required=True, help="KITTI sync sequence names")
    parser.add_argument("--camera", default="image_02")
    parser.add_argument("--output-frame-table", required=True)
    args = parser.parse_args()

    build_combined_frame_table(
        kitti_root=args.kitti_root,
        sequences=args.sequences,
        camera=args.camera,
        output_frame_table=args.output_frame_table,
    )


if __name__ == "__main__":
    main()
