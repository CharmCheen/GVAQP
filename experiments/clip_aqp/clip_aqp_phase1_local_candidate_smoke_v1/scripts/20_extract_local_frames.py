#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import cv2
import pandas as pd

from local_candidate_common import OUT, append_progress


def save_frame(frame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)


def extract_clip_frames(unit) -> list[dict]:
    cap = cv2.VideoCapture(str(unit.source_clip_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    idxs = sorted(set([0, max(0, total // 2), max(0, total - 1)])) if total else [0]
    rows = []
    for idx in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        timestamp = float(unit.start_time) + idx / fps
        frame_path = OUT / "frames" / "clips" / str(unit.unit_id) / f"frame_{idx:06d}.jpg"
        save_frame(frame, frame_path)
        rows.append(
            {
                "video_id": unit.video_id,
                "unit_id": unit.unit_id,
                "timestamp": timestamp,
                "frame_path": str(frame_path),
                "source_video_path": unit.source_video_path,
                "source_clip_path": unit.source_clip_path,
            }
        )
    cap.release()
    return rows


def extract_full_video_frames(video) -> list[dict]:
    cap = cv2.VideoCapture(str(video.source_video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps))
    rows = []
    frame_idx = 0
    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % step == 0:
            timestamp = frame_idx / fps
            frame_path = OUT / "frames" / "full_videos" / str(video.video_id) / f"frame_{saved:06d}.jpg"
            save_frame(frame, frame_path)
            rows.append(
                {
                    "video_id": video.video_id,
                    "unit_id": "",
                    "timestamp": timestamp,
                    "frame_path": str(frame_path),
                    "source_video_path": video.source_video_path,
                    "source_clip_path": "",
                }
            )
            saved += 1
        frame_idx += 1
    cap.release()
    return rows


def main() -> int:
    units = pd.read_csv(OUT / "tables/local_smoke_units.csv")
    full = pd.read_csv(OUT / "tables/local_full_video_selection.csv")
    rows = []
    for unit in units.itertuples(index=False):
        rows.extend(extract_clip_frames(unit))
    for video in full.itertuples(index=False):
        rows.extend(extract_full_video_frames(video))
    pd.DataFrame(rows, columns=["video_id", "unit_id", "timestamp", "frame_path", "source_video_path", "source_clip_path"]).to_csv(OUT / "tables/local_frame_index.csv", index=False)
    append_progress("extract_frames", "python scripts/20_extract_local_frames.py", f"frames={len(rows)}", next_action="generate candidates")
    print(f"frames={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

