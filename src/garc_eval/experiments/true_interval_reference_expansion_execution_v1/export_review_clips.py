#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pandas as pd

from common_review import MEDIA_DIR, OUT, append_progress, ffprobe_duration, video_source, write_df, write_text


def fmt_time(x: float) -> str:
    return f"{x:.1f}".replace(".", "p")


def run(cmd: list[str]) -> tuple[bool, str]:
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode == 0, p.stdout[-800:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=OUT / "true_interval_review_queue.csv")
    parser.add_argument("--max-items", type=int, default=None, help="Optional smoke limit. Default exports all queue rows.")
    args = parser.parse_args()

    queue = pd.read_csv(args.queue)
    if args.max_items:
        queue = queue.head(args.max_items)
    video, status, offset = video_source()
    video_duration = ffprobe_duration(video)
    rows = []
    if video is None:
        write_text(OUT / "media_export_missing.md", "# Media Export Missing\n\nNo requested or corresponding full video file was found. Review CSV/workbook/protocol were still generated.")
        for r in queue.itertuples(index=False):
            rows.append({"review_id": r.review_id, "candidate_id": r.candidate_id, "video_source_status": status, "clip_path": "", "center_frame_path": "", "sheet_path": "", "clip_export_status": "VIDEO_MISSING", "center_export_status": "VIDEO_MISSING", "sheet_export_status": "PENDING_CONTACT_SHEET_SCRIPT", "media_t_start": "", "media_t_end": "", "notes": "CSV review can proceed; media unavailable."})
        manifest = pd.DataFrame(rows)
        write_df(manifest, OUT / "media_manifest.csv")
        write_text(OUT / "media_export_report.md", "# Media Export Report\n\nVideo missing; no clips or center frames exported.")
        append_progress("export_review_clips", "video_missing")
        return

    for r in queue.itertuples(index=False):
        local_start = max(0.0, float(r.context_start))
        local_end = max(local_start + 0.5, float(r.context_end))
        media_start = local_start + offset
        media_end = local_end + offset
        if video_duration is not None:
            media_start = max(0.0, min(media_start, max(0.0, video_duration - 0.2)))
            media_end = max(media_start + 0.5, min(media_end, video_duration))
        duration = max(0.5, media_end - media_start)
        clip_name = f"review_{r.review_id}_{fmt_time(float(r.t_start))}_{fmt_time(float(r.t_end))}.mp4"
        center_name = f"review_{r.review_id}_center.jpg"
        clip_path = MEDIA_DIR / "clips" / clip_name
        center_path = MEDIA_DIR / "centers" / center_name
        if clip_path.exists() and clip_path.stat().st_size > 0:
            clip_ok, clip_msg = True, "SKIPPED_EXISTING"
        else:
            clip_ok, clip_msg = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{media_start:.3f}", "-t", f"{duration:.3f}", "-i", str(video), "-c", "copy", str(clip_path)])
            if not clip_ok:
                clip_ok, clip_msg = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{media_start:.3f}", "-t", f"{duration:.3f}", "-i", str(video), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", str(clip_path)])
        center_t = media_start + duration / 2.0
        if center_path.exists() and center_path.stat().st_size > 0:
            center_ok, center_msg = True, "SKIPPED_EXISTING"
        else:
            center_ok, center_msg = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{center_t:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(center_path)])
        rows.append({
            "review_id": r.review_id,
            "candidate_id": r.candidate_id,
            "video_source_status": status,
            "video_path": str(video),
            "local_to_media_offset_seconds": offset,
            "media_t_start": media_start,
            "media_t_end": media_end,
            "clip_path": str(clip_path),
            "center_frame_path": str(center_path),
            "sheet_path": str(MEDIA_DIR / "sheets" / f"review_{r.review_id}_sheet.jpg"),
            "clip_export_status": "OK" if clip_ok else "FAILED",
            "center_export_status": "OK" if center_ok else "FAILED",
            "sheet_export_status": "PENDING_CONTACT_SHEET_SCRIPT",
            "notes": "" if clip_ok and center_ok else f"clip_msg={clip_msg}; center_msg={center_msg}",
        })
    manifest = pd.DataFrame(rows)
    write_df(manifest, OUT / "media_manifest.csv")
    ok = int((manifest["clip_export_status"] == "OK").sum())
    write_text(
        OUT / "media_export_report.md",
        f"""# Media Export Report

- Video source status: `{status}`
- Video path: `{video}`
- Local-to-media offset seconds: `{offset}`
- Queue rows attempted: `{len(manifest)}`
- Clips exported OK: `{ok}`
- Center frames exported OK: `{int((manifest['center_export_status'] == 'OK').sum())}`
- Contact sheets are generated by `build_contact_sheets.py`.

Only video clipping/frame extraction was performed; no visual model was run.
""",
    )
    append_progress("export_review_clips", f"clips_ok={ok}/{len(manifest)}")


if __name__ == "__main__":
    main()
