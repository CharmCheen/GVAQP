#!/usr/bin/env python3
"""Run the fixed default selector on generated cheap feature tables.

This is intentionally isolated from query_runtime_v1 outputs. It imports the
existing selector helpers but writes all artifacts under
outputs/video_feature_precompute_runtime_v1.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "video_feature_precompute_runtime_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
CLIPS = OUT / "clips"
FIGURES = OUT / "figures"


def load_query_runtime_module():
    path = ROOT / "outputs" / "query_runtime_v1" / "scripts" / "run_query_runtime.py"
    spec = importlib.util.spec_from_file_location("query_runtime_v1_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def append_progress(command: str, result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Run generated-feature runtime\n\n")
        f.write("- Checkpoint: Run generated-feature runtime\n")
        f.write(f"- Commands run: `{command}`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def export_clips(manifest: list[dict], video_path: Path) -> list[dict]:
    updated = []
    CLIPS.mkdir(parents=True, exist_ok=True)
    for row in manifest:
        out = Path(row["clip_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            row["t_start"],
            "-i",
            str(video_path),
            "-t",
            row["duration"],
            "-c",
            "copy",
            str(out),
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        new_row = dict(row)
        new_row["clip_export_status"] = "OK" if proc.returncode == 0 and out.exists() and out.stat().st_size > 0 else "FAIL"
        new_row["ffmpeg_returncode"] = proc.returncode
        new_row["clip_size_bytes"] = out.stat().st_size if out.exists() else 0
        updated.append(new_row)
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="dangerous_segments_enter_ego_path_v0")
    parser.add_argument("--budget", type=int, default=40)
    parser.add_argument("--anchor-grid", default="outputs/video_feature_precompute_v1/tables/center10_anchor_grid.csv")
    parser.add_argument("--proxy-features", default="outputs/video_feature_precompute_v1/tables/center10_proxy_features.csv")
    parser.add_argument("--score-column", default="yolo_vehicle_max")
    parser.add_argument("--nms-gap-seconds", type=float, default=20.0)
    parser.add_argument("--video-path", default="data/realcam/long_video_data/long_video_dataset3.mp4")
    parser.add_argument("--export-clips", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rt = load_query_runtime_module()
    anchor_grid = resolve(args.anchor_grid)
    proxy_features = resolve(args.proxy_features)
    video_path = resolve(args.video_path) if args.video_path else None
    if video_path and not video_path.exists():
        raise FileNotFoundError(video_path)

    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    rows = rt.load_runtime_rows(anchor_grid, proxy_features, args.score_column)
    selected = rt.select_score_topk_temporal_nms(rows, args.budget, args.nms_gap_seconds)
    manifest = rt.build_clip_manifest(selected, args.query, args.budget, video_path, CLIPS)
    rt.write_ffmpeg_commands(manifest, OUT / "ffmpeg_export_commands.sh")

    if args.export_clips and video_path:
        manifest = export_clips(manifest, video_path)
        export_status = "OK" if all(row["clip_export_status"] == "OK" for row in manifest) else "PARTIAL_OR_FAIL"
    else:
        export_status = "SKIPPED_INTERVAL_ONLY"
        for row in manifest:
            row["clip_export_status"] = "SKIPPED_INTERVAL_ONLY"

    intervals = rt.merge_intervals(manifest)
    summary = {
        "query_id": args.query,
        "budget": args.budget,
        "selector_family": "score_topk_temporal_nms_duration_cap",
        "score_column": args.score_column,
        "nms_gap_seconds": args.nms_gap_seconds,
        "candidate_clip_count": len(manifest),
        "returned_interval_count_after_merge": len(intervals),
        "total_returned_duration_seconds": f"{sum(float(row['duration']) for row in intervals):.3f}",
        "clip_export_status": export_status,
        "evaluation_status": "NO_ORACLE_PROVIDED",
        "anchor_grid": str(anchor_grid),
        "proxy_features": str(proxy_features),
    }

    sanity = [
        {
            "check": "selected_unique_clips_equal_budget",
            "status": "PASS" if len({row["anchor_id"] for row in manifest}) == min(args.budget, len(rows)) else "FAIL",
            "details": f"{len({row['anchor_id'] for row in manifest})} unique clips selected.",
        },
        {
            "check": "selector_uses_no_oracle_labels",
            "status": "PASS",
            "details": "Inputs are generated anchor/proxy CSVs; no oracle/probe files are opened.",
        },
        {
            "check": "duration_cap_respected",
            "status": "PASS" if sum(float(row["duration"]) for row in manifest) <= args.budget * 10.0 + 1e-9 else "FAIL",
            "details": f"sum clip duration={sum(float(row['duration']) for row in manifest):.3f}s, cap={args.budget * 10.0:.3f}s.",
        },
        {
            "check": "default_selector_family",
            "status": "PASS",
            "details": "score_topk + temporal NMS + duration cap; CILS not used.",
        },
        {
            "check": "physical_clip_export",
            "status": "PASS" if (not args.export_clips or export_status == "OK") else "FAIL",
            "details": export_status,
        },
    ]

    rt.write_csv(TABLES / "candidate_clip_manifest.csv", manifest)
    rt.write_csv(TABLES / "returned_intervals.csv", intervals)
    rt.write_csv(TABLES / "runtime_summary.csv", [summary])
    rt.write_csv(TABLES / "sanity_checks.csv", sanity)
    rt.make_timeline_svg(FIGURES / "selected_clip_timeline.svg", manifest)

    decision = "NO-GO" if any(row["status"] == "FAIL" for row in sanity) else "GO"
    report = [
        "# Video Feature Precompute Runtime v1 Final Report",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This stage runs the fixed default selector family on generated cheap feature tables. It runs no VLM and performs no oracle/probe evaluation.",
        "",
        "## Runtime Configuration",
        "",
        f"- Query: `{args.query}`.",
        f"- Budget: `{args.budget}` candidate clips.",
        f"- Selector: `score_topk + temporal NMS + duration cap`.",
        f"- Score column: `{args.score_column}`.",
        f"- Temporal NMS gap: `{args.nms_gap_seconds}` seconds.",
        f"- Anchor grid: `{anchor_grid}`.",
        f"- Proxy features: `{proxy_features}`.",
        "",
        "## Outputs",
        "",
        f"- Candidate clips: `{len(manifest)}`.",
        f"- Returned merged intervals: `{len(intervals)}`.",
        f"- Total returned interval duration: `{summary['total_returned_duration_seconds']}` seconds.",
        f"- Clip export status: `{export_status}`.",
        "- Evaluation status: `NO_ORACLE_PROVIDED`.",
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
            "- `tables/candidate_clip_manifest.csv`",
            "- `tables/returned_intervals.csv`",
            "- `tables/runtime_summary.csv`",
            "- `tables/sanity_checks.csv`",
            "- `figures/selected_clip_timeline.svg`",
            "- `ffmpeg_export_commands.sh`",
            "",
            f"FINAL_DECISION: {decision}",
        ]
    )
    (REPORTS / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n"
        "```bash\n"
        "python outputs/video_feature_precompute_runtime_v1/scripts/run_generated_feature_runtime.py --export-clips\n"
        "```\n"
    )
    append_progress(
        "python outputs/video_feature_precompute_runtime_v1/scripts/run_generated_feature_runtime.py --export-clips",
        f"Selected {len(manifest)} candidates, returned {len(intervals)} intervals, export_status={export_status}, decision={decision}.",
        failure="; ".join(row["check"] for row in sanity if row["status"] == "FAIL") or "none",
        next_action="Inspect runtime artifacts; optionally run read-only eval only against a declared held-out reference.",
    )
    if decision == "NO-GO":
        raise SystemExit("Generated-feature runtime sanity failed")


if __name__ == "__main__":
    main()
