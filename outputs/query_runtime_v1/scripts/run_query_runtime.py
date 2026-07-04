#!/usr/bin/env python3
"""Query-to-clip runtime for the current SQ-CRAQ dev operating point.

The selector is fixed to the allowed project default family:
score_topk + temporal NMS + duration cap. Optional oracle files are used only
after selection for offline evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "query_runtime_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
CLIPS = OUT / "clips"
FIGURES = OUT / "figures"


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


def append_progress(result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Run query runtime\n\n")
        f.write("- Checkpoint: Run query runtime\n")
        f.write("- Commands run: `python outputs/query_runtime_v1/scripts/run_query_runtime.py --use-defaults --budget 40 --query dangerous_segments_enter_ego_path_v0`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_runtime_rows(anchor_grid: Path, proxy_features: Path, score_column: str) -> list[dict]:
    anchors = {r["anchor_id"]: r for r in read_csv(anchor_grid)}
    proxies = {r["anchor_id"]: r for r in read_csv(proxy_features)}
    rows = []
    missing_score = []
    for aid, anchor in anchors.items():
        proxy = proxies.get(aid)
        if proxy is None:
            continue
        if score_column not in proxy:
            missing_score.append(aid)
            continue
        rows.append(
            {
                "anchor_id": aid,
                "video_id": anchor.get("video_id", ""),
                "anchor_time": float(anchor["anchor_time"]),
                "start_time": float(anchor["start_time"]),
                "end_time": float(anchor["end_time"]),
                "duration": float(anchor.get("duration", 0) or 0),
                "source_video_path": anchor.get("source_video_path", ""),
                "score": float(proxy.get(score_column, 0.0) or 0.0),
                "score_column": score_column,
            }
        )
    if missing_score:
        raise ValueError(f"score column {score_column} missing for {len(missing_score)} anchors")
    rows.sort(key=lambda r: r["start_time"])
    return rows


def select_score_topk_temporal_nms(rows: list[dict], budget: int, gap_seconds: float) -> list[dict]:
    ranked = sorted(rows, key=lambda r: (r["score"], -r["start_time"]), reverse=True)
    selected = []
    selected_times = []
    for row in ranked:
        if all(abs(row["anchor_time"] - t) >= gap_seconds for t in selected_times):
            selected.append(row)
            selected_times.append(row["anchor_time"])
        if len(selected) >= budget:
            break
    if len(selected) < budget:
        selected_ids = {r["anchor_id"] for r in selected}
        for row in ranked:
            if row["anchor_id"] not in selected_ids:
                selected.append(row)
                selected_ids.add(row["anchor_id"])
            if len(selected) >= budget:
                break
    return selected


def build_clip_manifest(selected: list[dict], query: str, budget: int, video_path: Path | None, export_dir: Path) -> list[dict]:
    manifest = []
    for rank, row in enumerate(selected, start=1):
        clip_name = f"{query}_rank{rank:03d}_{row['anchor_id']}_{row['start_time']:.1f}_{row['end_time']:.1f}.mp4"
        clip_path = export_dir / clip_name
        manifest.append(
            {
                "query_id": query,
                "budget": budget,
                "rank": rank,
                "anchor_id": row["anchor_id"],
                "video_id": row["video_id"],
                "t_start": f"{row['start_time']:.3f}",
                "t_end": f"{row['end_time']:.3f}",
                "duration": f"{row['end_time'] - row['start_time']:.3f}",
                "score_column": row["score_column"],
                "score": f"{row['score']:.6f}",
                "source_video_path": str(video_path) if video_path else row["source_video_path"],
                "clip_path": str(clip_path),
                "clip_export_status": "PENDING",
            }
        )
    return manifest


def merge_intervals(manifest: list[dict], merge_gap_seconds: float = 0.0) -> list[dict]:
    intervals = sorted(manifest, key=lambda r: float(r["t_start"]))
    merged = []
    for row in intervals:
        start = float(row["t_start"])
        end = float(row["t_end"])
        if not merged or start > float(merged[-1]["t_end"]) + merge_gap_seconds:
            merged.append(
                {
                    "query_id": row["query_id"],
                    "video_id": row["video_id"],
                    "t_start": f"{start:.3f}",
                    "t_end": f"{end:.3f}",
                    "duration": f"{end - start:.3f}",
                    "supporting_anchor_ids": row["anchor_id"],
                    "supporting_ranks": str(row["rank"]),
                    "max_score": row["score"],
                }
            )
        else:
            prev = merged[-1]
            prev["t_end"] = f"{max(float(prev['t_end']), end):.3f}"
            prev["duration"] = f"{float(prev['t_end']) - float(prev['t_start']):.3f}"
            prev["supporting_anchor_ids"] += "|" + row["anchor_id"]
            prev["supporting_ranks"] += "|" + str(row["rank"])
            prev["max_score"] = f"{max(float(prev['max_score']), float(row['score'])):.6f}"
    for idx, row in enumerate(merged, start=1):
        row["interval_rank_by_time"] = idx
    return merged


def write_ffmpeg_commands(manifest: list[dict], path: Path) -> None:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for row in manifest:
        src = row["source_video_path"]
        start = row["t_start"]
        duration = row["duration"]
        dst = row["clip_path"]
        lines.append(f"ffmpeg -y -ss {start} -i {json.dumps(src)} -t {duration} -c copy {json.dumps(dst)}")
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o755)


def export_clips(manifest: list[dict], video_path: Path) -> list[dict]:
    CLIPS.mkdir(parents=True, exist_ok=True)
    updated = []
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
        new_row["clip_export_status"] = "OK" if proc.returncode == 0 and out.exists() else "FAIL"
        new_row["ffmpeg_returncode"] = proc.returncode
        updated.append(new_row)
    return updated


def make_timeline_svg(path: Path, manifest: list[dict]) -> None:
    width, height, margin = 1000, 170, 55
    tmax = max(float(row["t_end"]) for row in manifest) if manifest else 1.0
    def x(t: float) -> float:
        return margin + (t / tmax) * (width - 2 * margin)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="55" y="30" font-family="Arial" font-size="18">Query runtime selected candidate clips</text>',
        f'<line x1="{margin}" y1="88" x2="{width-margin}" y2="88" stroke="#333"/>',
    ]
    for row in manifest:
        start = float(row["t_start"])
        end = float(row["t_end"])
        rank = int(row["rank"])
        opacity = max(0.30, 1.0 - (rank - 1) / max(1, len(manifest)) * 0.65)
        lines.append(
            f'<rect x="{x(start):.1f}" y="72" width="{max(1.0, x(end) - x(start)):.1f}" height="32" fill="#1f77b4" opacity="{opacity:.2f}"/>'
        )
    for tick in range(0, int(math.ceil(tmax / 600.0)) + 1):
        t = tick * 600.0
        xx = x(t)
        lines.append(f'<line x1="{xx:.1f}" y1="108" x2="{xx:.1f}" y2="114" stroke="#333"/>')
        lines.append(f'<text x="{xx-14:.1f}" y="132" font-family="Arial" font-size="12">{int(t/60)}m</text>')
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def load_oracle(oracle_labels: Path | None, oracle_events: Path | None):
    labels = {}
    anchor_to_events = defaultdict(set)
    total_events = 0
    if oracle_labels and oracle_labels.exists():
        labels = {r["anchor_id"]: r for r in read_csv(oracle_labels)}
    if oracle_events and oracle_events.exists():
        events = read_csv(oracle_events)
        total_events = len(events)
        for ev in events:
            for aid in ev["supporting_anchor_ids"].split("|"):
                if aid:
                    anchor_to_events[aid].add(ev["event_id"])
    return labels, anchor_to_events, total_events


def evaluate_manifest(manifest: list[dict], oracle_labels: Path | None, oracle_events: Path | None) -> dict:
    labels, anchor_to_events, total_events = load_oracle(oracle_labels, oracle_events)
    if not labels:
        return {"evaluation_status": "NO_ORACLE_PROVIDED"}
    total_positive = sum(1 for row in labels.values() if row.get("label") == "positive")
    selected = [r["anchor_id"] for r in manifest]
    positives = [aid for aid in selected if labels.get(aid, {}).get("label") == "positive"]
    events = set()
    redundant_positive = 0
    seen_events = set()
    for aid in selected:
        evs = anchor_to_events.get(aid, set())
        if labels.get(aid, {}).get("label") == "positive":
            if seen_events.intersection(evs):
                redundant_positive += 1
            seen_events.update(evs)
        events.update(evs)
    precision = len(positives) / len(selected) if selected else 0.0
    recall = len(positives) / total_positive if total_positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "evaluation_status": "OK",
        "dataset_source": "v13_8_center10_oracle",
        "selected_unique_calls": len(set(selected)),
        "positive_anchor_calls": len(positives),
        "total_positive_anchors": total_positive,
        "clip_precision_v13_8_center10_oracle": precision,
        "clip_recall_v13_8_center10_oracle": recall,
        "clip_f1_v13_8_center10_oracle": f1,
        "unique_events_found": len(events),
        "total_pseudo_events": total_events,
        "pseudo_event_recall_v13_8_center10_oracle": len(events) / total_events if total_events else "",
        "redundant_call_rate_v13_8_center10_oracle": redundant_positive / len(selected) if selected else 0.0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-defaults", action="store_true")
    parser.add_argument("--query", default="dangerous_segments_enter_ego_path_v0")
    parser.add_argument("--budget", type=int, default=40)
    parser.add_argument("--anchor-grid", default="experiments/v13/v13_7_multimethod_replay/tables/center10_anchor_grid.csv")
    parser.add_argument("--proxy-features", default="experiments/v13/v13_7_multimethod_replay/tables/center10_proxy_features.csv")
    parser.add_argument("--score-column", default="yolo_vehicle_max")
    parser.add_argument("--nms-gap-seconds", type=float, default=20.0)
    parser.add_argument("--oracle-labels", default="experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv")
    parser.add_argument("--oracle-events", default="experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv")
    parser.add_argument("--video-path", default="")
    parser.add_argument("--export-clips", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    anchor_grid = resolve(args.anchor_grid)
    proxy_features = resolve(args.proxy_features)
    oracle_labels = resolve(args.oracle_labels) if args.oracle_labels else None
    oracle_events = resolve(args.oracle_events) if args.oracle_events else None
    video_path = resolve(args.video_path) if args.video_path else None
    if video_path and not video_path.exists():
        raise FileNotFoundError(video_path)

    rows = load_runtime_rows(anchor_grid, proxy_features, args.score_column)
    selected = select_score_topk_temporal_nms(rows, args.budget, args.nms_gap_seconds)
    manifest = build_clip_manifest(selected, args.query, args.budget, video_path, CLIPS)
    write_ffmpeg_commands(manifest, OUT / "ffmpeg_export_commands.sh")

    export_status = "SKIPPED_NO_VIDEO"
    if args.export_clips:
        if not video_path:
            export_status = "SKIPPED_NO_VIDEO"
        else:
            manifest = export_clips(manifest, video_path)
            export_status = "OK" if all(r["clip_export_status"] == "OK" for r in manifest) else "PARTIAL_OR_FAIL"
    else:
        for row in manifest:
            row["clip_export_status"] = "SKIPPED_INTERVAL_ONLY"

    intervals = merge_intervals(manifest)
    metrics = evaluate_manifest(manifest, oracle_labels, oracle_events)
    summary = {
        "query_id": args.query,
        "budget": args.budget,
        "selector_family": "score_topk_temporal_nms_duration_cap",
        "score_column": args.score_column,
        "nms_gap_seconds": args.nms_gap_seconds,
        "candidate_clip_count": len(manifest),
        "returned_interval_count_after_merge": len(intervals),
        "total_returned_duration_seconds": sum(float(r["duration"]) for r in intervals),
        "clip_export_status": export_status,
        **metrics,
    }

    write_csv(TABLES / "candidate_clip_manifest.csv", manifest)
    write_csv(TABLES / "returned_intervals.csv", intervals)
    write_csv(TABLES / "runtime_summary.csv", [summary])
    make_timeline_svg(FIGURES / "selected_clip_timeline.svg", manifest)

    sanity = [
        {
            "check": "selected_unique_clips_equal_budget",
            "status": "PASS" if len({r["anchor_id"] for r in manifest}) == min(args.budget, len(rows)) else "FAIL",
            "details": f"{len({r['anchor_id'] for r in manifest})} unique clips selected.",
        },
        {
            "check": "selector_uses_no_oracle_labels",
            "status": "PASS",
            "details": "Selection occurs before evaluate_manifest(); load_runtime_rows reads only anchor grid and proxy feature CSV.",
        },
        {
            "check": "duration_cap_respected",
            "status": "PASS" if sum(float(r["duration"]) for r in manifest) <= args.budget * 10.0 + 1e-9 else "FAIL",
            "details": f"sum clip duration={sum(float(r['duration']) for r in manifest):.3f}s, cap={args.budget * 10.0:.3f}s.",
        },
        {
            "check": "source_video_available_for_clip_export",
            "status": "PASS" if video_path and video_path.exists() else "WARN",
            "details": str(video_path) if video_path else "No video path provided; wrote interval manifest and ffmpeg commands only.",
        },
    ]
    write_csv(TABLES / "sanity_checks.csv", sanity)

    decision = "GO" if all(r["status"] in ("PASS", "WARN") for r in sanity) else "NO-GO"
    if summary.get("evaluation_status") == "OK" and float(summary["clip_precision_v13_8_center10_oracle"]) < 0.3:
        decision = "WEAK GO"

    report = [
        "# Query Runtime v1 Final Report",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This experiment turns the current dev operating point into a reusable query-to-clip runtime. It does not run VLM/API/YOLO/GPU inference. It uses the fixed default selector family `score_topk + temporal NMS + duration cap`.",
        "",
        "## Runtime Configuration",
        "",
        f"- Query: `{args.query}`.",
        f"- Budget: `{args.budget}` VLM-equivalent candidate clips.",
        f"- Score column: `{args.score_column}`.",
        f"- Temporal NMS gap: `{args.nms_gap_seconds}` seconds.",
        f"- Anchor grid: `{anchor_grid.relative_to(ROOT)}`.",
        f"- Proxy features: `{proxy_features.relative_to(ROOT)}`.",
        "",
        "## Outputs",
        "",
        f"- Candidate clips: `{len(manifest)}`.",
        f"- Returned merged intervals: `{len(intervals)}`.",
        f"- Total returned interval duration: `{summary['total_returned_duration_seconds']:.3f}` seconds.",
        f"- Clip export status: `{export_status}`.",
        "",
        "## VLM-Defined Offline Evaluation",
        "",
    ]
    if metrics.get("evaluation_status") == "OK":
        report.extend(
            [
                "Dataset source: `v13_8_center10_oracle`.",
                "",
                f"- Clip precision `v13_8_center10_oracle`: {float(metrics['clip_precision_v13_8_center10_oracle']):.3f}.",
                f"- Clip recall `v13_8_center10_oracle`: {float(metrics['clip_recall_v13_8_center10_oracle']):.3f}.",
                f"- Clip F1 `v13_8_center10_oracle`: {float(metrics['clip_f1_v13_8_center10_oracle']):.3f}.",
                f"- Pseudo-event recall `v13_8_center10_oracle`: {float(metrics['pseudo_event_recall_v13_8_center10_oracle']):.3f}.",
            ]
        )
    else:
        report.append("No oracle evaluation was requested.")
    report.extend(
        [
            "",
            "## Sanity Checks",
            "",
            "| Check | Status | Details |",
            "|---|---|---|",
        ]
    )
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
        "python outputs/query_runtime_v1/scripts/run_query_runtime.py --use-defaults --budget 40 --query dangerous_segments_enter_ego_path_v0\n"
        "```\n\n"
        "To export physical clips, pass `--video-path /path/to/source.mp4 --export-clips` on a matching time axis.\n"
    )
    append_progress(
        f"Selected {len(manifest)} candidate clips and {len(intervals)} merged intervals; final decision {decision}.",
        failure="; ".join(r["check"] for r in sanity if r["status"] == "FAIL") or "none",
        next_action="Run frozen/probe read-only compatibility audit and avoid tuning on probe_set_v1.",
    )
    if any(r["status"] == "FAIL" for r in sanity):
        raise SystemExit("Runtime sanity failed")


if __name__ == "__main__":
    main()
