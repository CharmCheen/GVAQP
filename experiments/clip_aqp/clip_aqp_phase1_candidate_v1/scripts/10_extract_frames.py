#!/usr/bin/env python3
from __future__ import annotations

import time
from pathlib import Path

import cv2
import pandas as pd

from candidate_common import OUT, append_progress, empty_csv


FRAME_COLUMNS = ["video_id", "frame_id", "timestamp", "frame_path", "source_video_path"]


def main() -> int:
    access = pd.read_csv(OUT / "tables/video_access_manifest.csv")
    linked = access[access["download_status"] == "linked_existing"]
    if linked.empty:
        empty_csv(OUT / "tables/frame_index.csv", FRAME_COLUMNS)
        pd.DataFrame([{"stage": "frame_extraction", "status": "skipped_no_video_access", "fps": 1, "frames": 0, "runtime_seconds": 0.0}]).to_csv(OUT / "tables/frame_extraction_status.csv", index=False)
        append_progress("extract_frames", "python scripts/10_extract_frames.py", "skipped_no_video_access", failure="no linked videos", next_action="candidate generation status")
        print("Frame extraction skipped: no accessible videos")
        return 0

    rows = []
    t0 = time.time()
    for video in linked.itertuples(index=False):
        cap = cv2.VideoCapture(str(video.local_video_path))
        if not cap.isOpened():
            continue
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(fps / 1.0))
        frame_idx = 0
        saved_idx = 0
        out_dir = OUT / "frames" / str(video.video_id).replace(".mp4", "")
        out_dir.mkdir(parents=True, exist_ok=True)
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % step == 0:
                timestamp = frame_idx / fps
                frame_path = out_dir / f"frame_{saved_idx:06d}.jpg"
                cv2.imwrite(str(frame_path), frame)
                rows.append({"video_id": video.video_id, "frame_id": f"{video.video_id}_f{saved_idx:06d}", "timestamp": timestamp, "frame_path": str(frame_path), "source_video_path": video.local_video_path})
                saved_idx += 1
            frame_idx += 1
        cap.release()
    pd.DataFrame(rows, columns=FRAME_COLUMNS).to_csv(OUT / "tables/frame_index.csv", index=False)
    runtime = time.time() - t0
    pd.DataFrame([{"stage": "frame_extraction", "status": "completed", "fps": 1, "frames": len(rows), "runtime_seconds": runtime}]).to_csv(OUT / "tables/frame_extraction_status.csv", index=False)
    append_progress("extract_frames", "python scripts/10_extract_frames.py", f"frames={len(rows)}", next_action="candidate generation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

