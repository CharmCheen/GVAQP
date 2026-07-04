#!/usr/bin/env python3
"""Export physical clips for the frozen query runtime output where fallback media covers the time axis."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "query_runtime_fallback_clip_export_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
FIGURES = OUT / "figures"
LOGS = OUT / "logs"
CLIPS = OUT / "clips"

RUNTIME_MANIFEST = ROOT / "outputs/query_runtime_v1/tables/candidate_clip_manifest.csv"
RUNTIME_INTERVALS = ROOT / "outputs/query_runtime_v1/tables/returned_intervals.csv"
FALLBACK_VIDEO = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
OFFSET_SECONDS = 2000.0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ffprobe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return float(proc.stdout.strip())


def ffprobe_duration_or_blank(path: Path) -> str:
    if not path.exists():
        return ""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return ""
    return f"{float(proc.stdout.strip()):.6f}"


def append_progress(result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Export fallback clips\n\n")
        f.write("- Checkpoint: Export fallback clips\n")
        f.write("- Commands run: `python outputs/query_runtime_fallback_clip_export_v1/scripts/export_fallback_clips.py`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def make_timeline(path: Path, rows: list[dict], video_duration: float) -> None:
    width, height, margin = 1000, 190, 55
    def x(t: float) -> float:
        return margin + (t / video_duration) * (width - 2 * margin)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="55" y="30" font-family="Arial" font-size="18">Fallback physical clip export coverage</text>',
        f'<line x1="{margin}" y1="95" x2="{width-margin}" y2="95" stroke="#333"/>',
    ]
    for row in rows:
        if row["eligible_for_export"] != "True":
            continue
        start = float(row["media_t_start"])
        end = float(row["media_t_end"])
        fill = "#2ca02c" if row["clip_export_status"] == "OK" else "#d62728"
        lines.append(f'<rect x="{x(start):.1f}" y="76" width="{max(1.0, x(end)-x(start)):.1f}" height="34" fill="{fill}" opacity="0.7"/>')
    for tick in range(0, int(video_duration // 600) + 2):
        t = min(video_duration, tick * 600.0)
        xx = x(t)
        lines.append(f'<line x1="{xx:.1f}" y1="116" x2="{xx:.1f}" y2="122" stroke="#333"/>')
        lines.append(f'<text x="{xx-14:.1f}" y="140" font-family="Arial" font-size="12">{int(t/60)}m</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    for d in [TABLES, REPORTS, FIGURES, LOGS, CLIPS]:
        d.mkdir(parents=True, exist_ok=True)
    runtime_rows = read_csv(RUNTIME_MANIFEST)
    _ = read_csv(RUNTIME_INTERVALS)
    duration = ffprobe_duration(FALLBACK_VIDEO)

    rows = []
    commands = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for row in runtime_rows:
        local_start = float(row["t_start"])
        local_end = float(row["t_end"])
        media_start = local_start + OFFSET_SECONDS
        media_end = local_end + OFFSET_SECONDS
        eligible = media_start >= 0 and media_end <= duration
        out_name = f"rank{int(row['rank']):03d}_{row['anchor_id']}_media{media_start:.1f}_{media_end:.1f}.mp4"
        out_path = CLIPS / out_name
        export_status = "SKIPPED_OUT_OF_FALLBACK_RANGE"
        returncode = ""
        if eligible:
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{media_start:.3f}",
                "-i",
                str(FALLBACK_VIDEO),
                "-t",
                f"{media_end - media_start:.3f}",
                "-c",
                "copy",
                str(out_path),
            ]
            commands.append(" ".join(json.dumps(part) for part in cmd))
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            returncode = str(proc.returncode)
            export_status = "OK" if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0 else "FAIL"
        rows.append(
            {
                "rank": row["rank"],
                "anchor_id": row["anchor_id"],
                "query_id": row["query_id"],
                "local_t_start": row["t_start"],
                "local_t_end": row["t_end"],
                "media_t_start": f"{media_start:.3f}",
                "media_t_end": f"{media_end:.3f}",
                "duration": row["duration"],
                "score_column": row["score_column"],
                "score": row["score"],
                "eligible_for_export": str(eligible),
                "clip_export_status": export_status,
                "ffmpeg_returncode": returncode,
                "fallback_video_path": str(FALLBACK_VIDEO),
                "exported_clip_path": str(out_path) if eligible else "",
            }
        )
    validation_rows = []
    for row in rows:
        if row["clip_export_status"] != "OK":
            continue
        path = Path(row["exported_clip_path"])
        probed_duration = ffprobe_duration_or_blank(path)
        validation_rows.append(
            {
                "rank": row["rank"],
                "anchor_id": row["anchor_id"],
                "exported_clip_path": row["exported_clip_path"],
                "expected_duration_seconds": row["duration"],
                "ffprobe_duration_seconds": probed_duration,
                "file_size_bytes": path.stat().st_size if path.exists() else 0,
                "duration_positive": str(bool(probed_duration and float(probed_duration) > 0.0)),
            }
        )
    (OUT / "ffmpeg_commands_executed.sh").write_text("\n".join(commands) + "\n")
    (OUT / "ffmpeg_commands_executed.sh").chmod(0o755)
    write_csv(TABLES / "fallback_clip_export_manifest.csv", rows)
    write_csv(TABLES / "exported_clip_validation.csv", validation_rows)

    ok = [r for r in rows if r["clip_export_status"] == "OK"]
    eligible_rows = [r for r in rows if r["eligible_for_export"] == "True"]
    skipped = [r for r in rows if r["clip_export_status"] == "SKIPPED_OUT_OF_FALLBACK_RANGE"]
    failed = [r for r in rows if r["clip_export_status"] == "FAIL"]
    summary = {
        "runtime_candidate_count": len(rows),
        "fallback_video_path": str(FALLBACK_VIDEO),
        "fallback_video_duration_seconds": duration,
        "local_to_media_offset_seconds": OFFSET_SECONDS,
        "eligible_for_export_count": len(eligible_rows),
        "exported_ok_count": len(ok),
        "skipped_out_of_fallback_range_count": len(skipped),
        "failed_export_count": len(failed),
        "exported_total_duration_seconds": sum(float(r["duration"]) for r in ok),
        "ffprobe_min_duration_seconds": min((float(r["ffprobe_duration_seconds"]) for r in validation_rows), default=0.0),
        "ffprobe_max_duration_seconds": max((float(r["ffprobe_duration_seconds"]) for r in validation_rows), default=0.0),
    }
    write_csv(TABLES / "fallback_clip_export_summary.csv", [summary])
    sanity = [
        {
            "check": "selector_output_not_modified",
            "status": "PASS",
            "details": "Exporter reads outputs/query_runtime_v1/tables/candidate_clip_manifest.csv and does not change selector settings.",
        },
        {
            "check": "fallback_video_exists",
            "status": "PASS" if FALLBACK_VIDEO.exists() else "FAIL",
            "details": str(FALLBACK_VIDEO),
        },
        {
            "check": "all_eligible_clips_exported",
            "status": "PASS" if len(failed) == 0 and len(ok) == len(eligible_rows) else "FAIL",
            "details": f"ok={len(ok)}, eligible={len(eligible_rows)}, failed={len(failed)}.",
        },
        {
            "check": "partial_export_scope_declared",
            "status": "PASS" if len(skipped) > 0 else "WARN",
            "details": f"skipped_out_of_fallback_range={len(skipped)}.",
        },
        {
            "check": "exported_clips_are_ffprobe_readable",
            "status": "PASS" if validation_rows and all(r["duration_positive"] == "True" for r in validation_rows) else "FAIL",
            "details": f"validated={len(validation_rows)} exported clips.",
        },
    ]
    write_csv(TABLES / "sanity_checks.csv", sanity)
    make_timeline(FIGURES / "fallback_export_timeline.svg", rows, duration)

    decision = "NO-GO" if any(r["status"] == "FAIL" for r in sanity) else "WEAK GO"
    report = [
        "# Query Runtime Fallback Clip Export v1 Final Report",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This export materializes physical MP4 clips for the subset of frozen `query_runtime_v1` selections whose local times fit the available fallback video with `local_to_media_offset_seconds = 2000.0`. It does not rerank, retune, run VLM, run YOLO, or change the selector.",
        "",
        "This is a partial physical preview export, not a full V13 source-video export, because `try_or_no/videos/realcartest.mp4` is absent in this workspace.",
        "",
        "## Results",
        "",
        f"- Runtime candidate clips: `{len(rows)}`.",
        f"- Eligible for fallback export: `{len(eligible_rows)}`.",
        f"- Exported OK: `{len(ok)}`.",
        f"- Skipped out of fallback range: `{len(skipped)}`.",
        f"- Exported total duration: `{summary['exported_total_duration_seconds']:.3f}` seconds.",
        f"- ffprobe exported duration range: `{summary['ffprobe_min_duration_seconds']:.3f}` to `{summary['ffprobe_max_duration_seconds']:.3f}` seconds.",
        f"- Fallback video duration: `{duration:.6f}` seconds.",
        "",
        "## Sanity Checks",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for row in sanity:
        report.append(f"| {row['check']} | {row['status']} | {row['details']} |")
    report.extend(
        [
            "",
            "## Files",
            "",
            "- `tables/fallback_clip_export_manifest.csv`",
            "- `tables/fallback_clip_export_summary.csv`",
            "- `tables/exported_clip_validation.csv`",
            "- `tables/sanity_checks.csv`",
            "- `figures/fallback_export_timeline.svg`",
            "- `clips/`",
            "- `ffmpeg_commands_executed.sh`",
            "",
            f"FINAL_DECISION: {decision}",
        ]
    )
    (REPORTS / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n```bash\npython outputs/query_runtime_fallback_clip_export_v1/scripts/export_fallback_clips.py\n```\n"
    )
    append_progress(
        f"Exported {len(ok)}/{len(eligible_rows)} eligible fallback clips; final decision {decision}.",
        failure="; ".join(r["check"] for r in sanity if r["status"] == "FAIL") or "none",
        next_action="Use exported clips as physical preview only; restore original realcartest.mp4 for full export.",
    )
    if any(r["status"] == "FAIL" for r in sanity):
        raise SystemExit("Fallback export sanity failed")


if __name__ == "__main__":
    main()
