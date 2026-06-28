#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import cv2
import pandas as pd

from auth_video_common import OUT, append_progress


def main() -> int:
    checks = pd.read_csv(OUT / "checks/video_readability_checks.csv")
    readable = checks[checks["readable"].astype(bool)].head(5)
    rows = []
    if len(readable) < 5:
        pd.DataFrame(columns=["video_id", "frame_id", "timestamp", "frame_path", "source_video_path"]).to_csv(OUT / "checks/frame_smoke_index.csv", index=False)
        pd.DataFrame([{"status": "skipped_fewer_than_5_readable", "readable_videos": len(readable), "frames": 0}]).to_csv(OUT / "checks/frame_smoke_status.csv", index=False)
        append_progress("frame_smoke", "python scripts/20_frame_smoke.py", "skipped_fewer_than_5_readable", next_action="report")
        print("Frame smoke skipped: fewer than 5 readable videos")
        return 0
    for video in readable.itertuples(index=False):
        cap = cv2.VideoCapture(str(video.local_target_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(fps))
        frame_idx = 0
        saved_idx = 0
        out_dir = OUT / "checks" / "frames_smoke" / str(video.video_id).replace(".mp4", "")
        out_dir.mkdir(parents=True, exist_ok=True)
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % step == 0:
                timestamp = frame_idx / fps
                frame_path = out_dir / f"frame_{saved_idx:06d}.jpg"
                cv2.imwrite(str(frame_path), frame)
                rows.append({"video_id": video.video_id, "frame_id": f"{video.video_id}_f{saved_idx:06d}", "timestamp": timestamp, "frame_path": str(frame_path), "source_video_path": video.local_target_path})
                saved_idx += 1
            frame_idx += 1
        cap.release()
    pd.DataFrame(rows).to_csv(OUT / "checks/frame_smoke_index.csv", index=False)
    pd.DataFrame([{"status": "completed", "readable_videos": len(readable), "frames": len(rows)}]).to_csv(OUT / "checks/frame_smoke_status.csv", index=False)
    append_progress("frame_smoke", "python scripts/20_frame_smoke.py", f"frames={len(rows)}", next_action="report")
    print(f"Frame smoke frames={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

