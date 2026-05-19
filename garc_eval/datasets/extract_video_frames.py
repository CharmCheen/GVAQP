"""Extract frames from a video file and write metadata.

Usage:
    python -m garc_eval.datasets.extract_video_frames --video path/to/video.mp4 --video-id sample --outdir path/to/frames --sample-fps 1.0
"""

import argparse
import pathlib


def extract_frames(
    video_path: str,
    video_id: str,
    outdir: str,
    frame_table_path: str,
    sample_fps: float = 1.0,
    max_frames: int | None = None,
) -> None:
    try:
        import cv2
    except ImportError:
        raise ImportError(
            "opencv-python is not installed. "
            "Install it on the server with: pip install opencv-python"
        )

    import pandas as pd

    video_path = str(pathlib.Path(video_path).expanduser())
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, int(round(video_fps / sample_fps)))

    frames_dir = pathlib.Path(outdir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    frame_idx = 0
    saved = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            timestamp = frame_idx / video_fps
            image_name = f"{video_id}_{frame_idx:08d}.jpg"
            image_path = str(frames_dir / image_name)
            cv2.imwrite(image_path, frame)

            rows.append({
                "id": saved,
                "video_id": video_id,
                "frame_idx": frame_idx,
                "timestamp": round(timestamp, 4),
                "image_path": image_path,
            })
            saved += 1

            if max_frames is not None and saved >= max_frames:
                break

        frame_idx += 1

    cap.release()

    df = pd.DataFrame(rows)
    table_path = pathlib.Path(frame_table_path)
    table_path.parent.mkdir(parents=True, exist_ok=True)

    if table_path.suffix == ".parquet":
        df.to_parquet(table_path, index=False)
    else:
        df.to_csv(table_path, index=False)

    print(f"Extracted {saved} frames from {video_path}")
    print(f"Saved frame table to {table_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract video frames and write metadata")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--video-id", required=True, help="Video identifier")
    parser.add_argument("--outdir", required=True, help="Directory to save extracted frames")
    parser.add_argument("--frame-table", required=True, help="Output path for frame metadata (.parquet or .csv)")
    parser.add_argument("--sample-fps", type=float, default=1.0, help="Frames per second to sample")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum number of frames to extract")
    parser.add_argument("--dry-run", action="store_true", help="Check parameters without extracting")
    args = parser.parse_args()

    if args.dry_run:
        print("[dry-run] Would extract frames:")
        print(f"  video:      {args.video}")
        print(f"  video_id:   {args.video_id}")
        print(f"  outdir:     {args.outdir}")
        print(f"  frame_table:{args.frame_table}")
        print(f"  sample_fps: {args.sample_fps}")
        print(f"  max_frames: {args.max_frames}")
        vp = pathlib.Path(args.video)
        print(f"  video exists: {vp.exists()}")
        return

    extract_frames(args.video, args.video_id, args.outdir, args.frame_table, args.sample_fps, args.max_frames)


if __name__ == "__main__":
    main()
