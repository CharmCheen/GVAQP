"""Extract specific UA-DETRAC sequences from the training set zip.

This script extracts only 2-3 sequences from the large zip file
without extracting the entire archive.

Usage:
    python -m garc_eval.datasets.extract_uadetrac_from_zip \\
        --zip-path /path/to/ua_detrac_training_set.zip \\
        --sequences MVI_20011 MVI_20033 MVI_20051 \\
        --outdir /path/to/frames/uadetrac \\
        --frame-table /path/to/frame_metadata.parquet
"""

import argparse
import pathlib
import zipfile

import pandas as pd


DETRAC_FPS = 25.0


def extract_sequences_from_zip(
    zip_path: str,
    sequences: list[str],
    outdir: pathlib.Path,
    max_frames: int | None = None,
) -> pd.DataFrame:
    """Extract specific sequences from the UA-DETRAC training zip.

    The zip contains directories like:
    - Ins/detrac_1_MVI_20011/image000001.jpg

    Returns DataFrame with frame metadata.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    global_id = 0

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # List all files in the zip
        all_files = zf.namelist()
        print(f"Total files in zip: {len(all_files)}")

        for seq_name in sequences:
            print(f"\n=== Extracting {seq_name} ===")

            # Find files matching this sequence
            # Pattern: .../detrac_N_MVI_XXXXX/imageNNNNNN.jpg
            seq_files = [f for f in all_files if seq_name in f and f.endswith('.jpg')]
            seq_files.sort()

            if not seq_files:
                # Try alternative patterns
                seq_files = [f for f in all_files
                            if seq_name.replace("MVI_", "MVI_") in f
                            and f.lower().endswith(('.jpg', '.png'))]
                seq_files.sort()

            if not seq_files:
                print(f"  WARNING: No files found for {seq_name}")
                print(f"  Available patterns (first 5): {all_files[:5]}")
                continue

            if max_frames is not None:
                seq_files = seq_files[:max_frames]

            print(f"  Found {len(seq_files)} frames")

            # Create output directory
            video_id = seq_name.lower().replace(" ", "_")
            seq_outdir = outdir / video_id
            seq_outdir.mkdir(parents=True, exist_ok=True)

            # Extract frames
            for i, fname in enumerate(seq_files):
                # Extract frame index from filename
                basename = pathlib.Path(fname).stem
                try:
                    frame_idx = int(basename.replace("image", "").replace("frame", ""))
                except ValueError:
                    frame_idx = i + 1

                # Extract file
                out_name = f"{video_id}_{frame_idx:06d}.jpg"
                out_path = seq_outdir / out_name

                if not out_path.exists():
                    with zf.open(fname) as src:
                        with open(out_path, 'wb') as dst:
                            dst.write(src.read())

                timestamp = frame_idx / DETRAC_FPS

                all_rows.append({
                    "id": global_id,
                    "video_id": video_id,
                    "frame_idx": frame_idx,
                    "timestamp": round(timestamp, 4),
                    "image_path": str(out_path),
                })
                global_id += 1

            print(f"  Extracted to {seq_outdir}")

    return pd.DataFrame(all_rows)


def main():
    parser = argparse.ArgumentParser(description="Extract UA-DETRAC sequences from zip")
    parser.add_argument("--zip-path", required=True, help="Path to ua_detrac_training_set.zip")
    parser.add_argument("--sequences", nargs="+", required=True,
                        help="Sequence names (e.g., MVI_20011 MVI_20033)")
    parser.add_argument("--outdir", required=True, help="Output directory for frames")
    parser.add_argument("--frame-table", required=True, help="Output parquet path")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames per sequence")
    args = parser.parse_args()

    outdir = pathlib.Path(args.outdir)
    df = extract_sequences_from_zip(
        args.zip_path, args.sequences, outdir, args.max_frames
    )

    if len(df) == 0:
        print("ERROR: No frames extracted")
        return

    # Save frame table
    table_path = pathlib.Path(args.frame_table)
    table_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(table_path, index=False)

    print(f"\n=== Summary ===")
    print(f"Total frames: {len(df)}")
    print(f"Sequences: {df['video_id'].nunique()}")
    print(f"Frame table: {table_path}")

    for vid, group in df.groupby("video_id"):
        duration = group["timestamp"].max() - group["timestamp"].min()
        print(f"  {vid}: {len(group)} frames, {duration:.1f}s")


if __name__ == "__main__":
    main()
