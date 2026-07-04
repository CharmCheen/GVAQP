#!/usr/bin/env python3
"""Audit generated cheap-score quality and archive runtime output as A0.

This script reads only generated cheap feature tables and the A0 runtime
manifest. It does not read oracle labels or probe_set_v1.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "video_signal_quality_audit_v1"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"

COARSE_GRID = ROOT / "outputs" / "video_feature_precompute_v1" / "tables" / "coarse_5s_clip_grid.csv"
ANCHOR_GRID = ROOT / "outputs" / "video_feature_precompute_v1" / "tables" / "center10_anchor_grid.csv"
PROXY = ROOT / "outputs" / "video_feature_precompute_v1" / "tables" / "center10_proxy_features.csv"
CANDIDATES = ROOT / "outputs" / "video_feature_precompute_runtime_v1" / "tables" / "candidate_clip_manifest.csv"

SCORE_COLUMNS = [
    "yolo_vehicle_max",
    "motion_energy_max",
    "score_fusion_yolo_motion",
    "bbox_area_sum_max",
    "center_roi_vehicle_count_mean",
]


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
        f.write(f"\n## {utc_now()} - Run signal quality audit\n\n")
        f.write("- Checkpoint: Run signal quality audit\n")
        f.write("- Commands run: `python outputs/video_signal_quality_audit_v1/scripts/run_signal_quality_audit.py`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def values(rows: list[dict[str, str]], column: str) -> np.ndarray:
    return np.array([float(row[column]) for row in rows], dtype=float)


def score_stats(rows: list[dict[str, str]]) -> list[dict]:
    out = []
    n = len(rows)
    for col in SCORE_COLUMNS:
        arr = values(rows, col)
        rounded = [round(float(v), 6) for v in arr]
        counts = Counter(rounded)
        top_value, top_count = counts.most_common(1)[0]
        unique_count = len(counts)
        top_tie_fraction = top_count / n if n else 0.0
        zero_fraction = float(np.mean(arr == 0.0)) if n else 0.0
        nondegenerate = unique_count >= max(5, math.ceil(0.03 * n)) and top_tie_fraction <= 0.60
        out.append(
            {
                "score_column": col,
                "row_count": n,
                "min": f"{float(np.min(arr)):.6f}",
                "p25": f"{float(np.quantile(arr, 0.25)):.6f}",
                "median": f"{float(np.median(arr)):.6f}",
                "p75": f"{float(np.quantile(arr, 0.75)):.6f}",
                "max": f"{float(np.max(arr)):.6f}",
                "mean": f"{float(np.mean(arr)):.6f}",
                "std": f"{float(np.std(arr)):.6f}",
                "unique_value_count": unique_count,
                "top_tie_value": f"{top_value:.6f}",
                "top_tie_count": top_count,
                "top_tie_fraction": f"{top_tie_fraction:.6f}",
                "zero_fraction": f"{zero_fraction:.6f}",
                "prior_signal_non_degenerate": "PASS" if nondegenerate else "WARN",
            }
        )
    return out


def histograms(rows: list[dict[str, str]], bins: int = 20) -> list[dict]:
    out = []
    for col in SCORE_COLUMNS:
        arr = values(rows, col)
        if float(np.min(arr)) == float(np.max(arr)):
            edges = np.linspace(float(np.min(arr)), float(np.max(arr)) + 1.0, bins + 1)
        else:
            edges = np.linspace(float(np.min(arr)), float(np.max(arr)), bins + 1)
        counts, edges = np.histogram(arr, bins=edges)
        for i, count in enumerate(counts):
            out.append(
                {
                    "score_column": col,
                    "bin_index": i,
                    "bin_start": f"{float(edges[i]):.6f}",
                    "bin_end": f"{float(edges[i + 1]):.6f}",
                    "count": int(count),
                }
            )
    return out


def coverage(rows: list[dict[str, str]], start_key: str, end_key: str, expected_step: float) -> dict:
    intervals = sorted((float(row[start_key]), float(row[end_key])) for row in rows)
    gaps = []
    overlaps = []
    for prev, cur in zip(intervals, intervals[1:]):
        gap = cur[0] - prev[1]
        if gap > 1e-6:
            gaps.append(gap)
        if gap < -1e-6:
            overlaps.append(-gap)
    starts = [s for s, _ in intervals]
    step_deltas = [b - a for a, b in zip(starts, starts[1:])]
    return {
        "row_count": len(rows),
        "start_min": f"{intervals[0][0]:.3f}",
        "end_max": f"{intervals[-1][1]:.3f}",
        "gap_count": len(gaps),
        "max_gap_seconds": f"{max(gaps) if gaps else 0.0:.6f}",
        "overlap_count": len(overlaps),
        "max_overlap_seconds": f"{max(overlaps) if overlaps else 0.0:.6f}",
        "median_start_step_seconds": f"{float(np.median(step_deltas)) if step_deltas else 0.0:.6f}",
        "expected_step_seconds": f"{expected_step:.6f}",
        "coverage_status": "PASS" if not gaps else "FAIL",
    }


def candidate_distribution(rows: list[dict[str, str]], bucket_seconds: float = 600.0) -> list[dict]:
    starts = [float(row["t_start"]) for row in rows]
    duration_end = max(float(row["t_end"]) for row in rows) if rows else 0.0
    bucket_count = int(math.ceil(duration_end / bucket_seconds)) or 1
    counts = [0 for _ in range(bucket_count)]
    for start in starts:
        idx = min(bucket_count - 1, int(start // bucket_seconds))
        counts[idx] += 1
    out = []
    for idx, count in enumerate(counts):
        out.append(
            {
                "bucket_index": idx,
                "bucket_start_seconds": f"{idx * bucket_seconds:.3f}",
                "bucket_end_seconds": f"{(idx + 1) * bucket_seconds:.3f}",
                "candidate_count": count,
                "candidate_fraction": f"{count / len(rows) if rows else 0.0:.6f}",
            }
        )
    return out


def write_hist_svg(path: Path, hist_rows: list[dict], score_column: str) -> None:
    rows = [r for r in hist_rows if r["score_column"] == score_column]
    width, height = 820, 250
    left, top, bottom, right = 42, 30, 36, 18
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_count = max(int(r["count"]) for r in rows) if rows else 1
    bar_w = plot_w / max(1, len(rows))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="20" font-family="Arial" font-size="15" fill="#111827">{score_column} histogram</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#6b7280"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#6b7280"/>',
    ]
    for i, row in enumerate(rows):
        count = int(row["count"])
        h = (count / max_count) * plot_h if max_count else 0
        x = left + i * bar_w
        y = top + plot_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(1.0, bar_w - 2):.1f}" height="{h:.1f}" fill="#2563eb" opacity="0.82"/>')
    parts.append(f'<text x="{left}" y="{height - 10}" font-family="Arial" font-size="11" fill="#374151">20 equal-width bins; max bin count={max_count}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def write_candidate_svg(path: Path, rows: list[dict[str, str]], buckets: list[dict]) -> None:
    width, height = 960, 260
    left, top, right, bottom = 54, 38, 24, 42
    plot_w = width - left - right
    plot_h = height - top - bottom
    tmax = max(float(row["t_end"]) for row in rows) if rows else 1.0
    max_bucket = max(int(row["candidate_count"]) for row in buckets) if buckets else 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="23" font-family="Arial" font-size="15" fill="#111827">A0 selected candidate distribution over source video time</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#6b7280"/>',
    ]
    for bucket in buckets:
        start = float(bucket["bucket_start_seconds"])
        end = float(bucket["bucket_end_seconds"])
        count = int(bucket["candidate_count"])
        x = left + (start / tmax) * plot_w
        w = max(1.0, ((end - start) / tmax) * plot_w - 2)
        h = (count / max_bucket) * (plot_h * 0.55) if max_bucket else 0
        y = top + plot_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#94a3b8" opacity="0.65"/>')
    for row in rows:
        start = float(row["t_start"])
        rank = int(row["rank"])
        x = left + (start / tmax) * plot_w
        opacity = max(0.35, 1.0 - (rank - 1) / max(1, len(rows)) * 0.60)
        parts.append(f'<line x1="{x:.1f}" y1="{top + 8}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#dc2626" stroke-width="2" opacity="{opacity:.2f}"/>')
    for tick in range(0, int(math.ceil(tmax / 600.0)) + 1):
        t = tick * 600.0
        x = left + (t / tmax) * plot_w
        parts.append(f'<line x1="{x:.1f}" y1="{top + plot_h}" x2="{x:.1f}" y2="{top + plot_h + 5}" stroke="#374151"/>')
        parts.append(f'<text x="{x - 12:.1f}" y="{height - 12}" font-family="Arial" font-size="11" fill="#374151">{int(t/60)}m</text>')
    parts.append('<text x="650" y="23" font-family="Arial" font-size="11" fill="#374151">red=ranks; gray=10min bucket counts</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def append_section(path: Path, marker: str, section: str) -> None:
    text = path.read_text()
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n\n"
    path.write_text(text.rstrip() + "\n\n" + section.strip() + "\n")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    coarse = read_csv(COARSE_GRID)
    anchors = read_csv(ANCHOR_GRID)
    proxy = read_csv(PROXY)
    candidates = read_csv(CANDIDATES)

    stats = score_stats(proxy)
    hist = histograms(proxy)
    coarse_cov = coverage(coarse, "start_time", "end_time", 5.0)
    anchor_cov = coverage(anchors, "start_time", "end_time", 10.0)
    buckets = candidate_distribution(candidates)
    top_bucket_fraction = max(float(row["candidate_fraction"]) for row in buckets) if buckets else 0.0
    selected_starts = sorted(float(row["t_start"]) for row in candidates)
    candidate_gap_seconds = [b - a for a, b in zip(selected_starts, selected_starts[1:])]
    candidate_stats = {
        "candidate_count": len(candidates),
        "selected_time_min_seconds": f"{min(selected_starts) if selected_starts else 0.0:.3f}",
        "selected_time_max_seconds": f"{max(selected_starts) if selected_starts else 0.0:.3f}",
        "median_gap_between_selected_starts_seconds": f"{float(np.median(candidate_gap_seconds)) if candidate_gap_seconds else 0.0:.3f}",
        "min_gap_between_selected_starts_seconds": f"{min(candidate_gap_seconds) if candidate_gap_seconds else 0.0:.3f}",
        "top_10min_bucket_fraction": f"{top_bucket_fraction:.6f}",
        "distribution_status": "WARN" if top_bucket_fraction > 0.50 else "PASS",
    }

    write_csv(TABLES / "score_quality_summary.csv", stats)
    write_csv(TABLES / "score_histograms.csv", hist)
    write_csv(TABLES / "time_axis_coverage.csv", [{"grid": "coarse_5s", **coarse_cov}, {"grid": "center10", **anchor_cov}])
    write_csv(TABLES / "a0_candidate_time_buckets.csv", buckets)
    write_csv(TABLES / "a0_candidate_distribution_summary.csv", [candidate_stats])

    for col in SCORE_COLUMNS:
        write_hist_svg(FIGURES / f"{col}_histogram.svg", hist, col)
    write_candidate_svg(FIGURES / "a0_candidate_time_distribution.svg", candidates, buckets)

    nondegenerate_status = "GO" if all(row["prior_signal_non_degenerate"] == "PASS" for row in stats) else "WEAK GO"
    coverage_status = "GO" if coarse_cov["coverage_status"] == "PASS" and anchor_cov["coverage_status"] == "PASS" else "NO-GO"
    pipeline_execution = "GO"
    final_decision = "GO" if nondegenerate_status == "GO" and coverage_status == "GO" else "WEAK GO"

    report = [
        "# Video Signal Quality Audit v1 Final Report",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This audit reads generated cheap-score tables and A0 runtime candidates only. It runs no VLM and reads no oracle/probe labels.",
        "",
        "## Split Conclusions",
        "",
        f"- Pipeline execution success: `{pipeline_execution}`.",
        f"- Prior signal non-degenerate: `{nondegenerate_status}`.",
        f"- Time-axis coverage: `{coverage_status}`.",
        "",
        "## A0 Baseline Archive",
        "",
        "- A0 baseline: `score_topk + temporal NMS + duration cap`, no CILS, no oracle confirmation.",
        "- Budget: `40` candidate clips.",
        "- NMS gap: `20.0` seconds.",
        "- Budget/gap source: carried over from `default_selector_score_sweep_v1` / `query_runtime_v1` dev operating point; not a fairness-tuned CILS comparison setting.",
        "",
        "## Score Quality",
        "",
        "| Score | Unique Values | Top Tie Fraction | Zero Fraction | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in stats:
        report.append(
            f"| `{row['score_column']}` | {row['unique_value_count']} | {float(row['top_tie_fraction']):.3f} | {float(row['zero_fraction']):.3f} | {row['prior_signal_non_degenerate']} |"
        )
    report.extend(
        [
            "",
            "## Time-Axis Coverage",
            "",
            f"- Coarse 5s grid: `{coarse_cov['row_count']}` rows, gap_count `{coarse_cov['gap_count']}`, max_gap_seconds `{coarse_cov['max_gap_seconds']}`.",
            f"- Center10 grid: `{anchor_cov['row_count']}` rows, gap_count `{anchor_cov['gap_count']}`, max_gap_seconds `{anchor_cov['max_gap_seconds']}`.",
            "",
            "## A0 Candidate Time Distribution",
            "",
            f"- Candidate count: `{candidate_stats['candidate_count']}`.",
            f"- Selected time span: `{candidate_stats['selected_time_min_seconds']}` to `{candidate_stats['selected_time_max_seconds']}` seconds.",
            f"- Top 10min bucket fraction: `{candidate_stats['top_10min_bucket_fraction']}`.",
            f"- Distribution status: `{candidate_stats['distribution_status']}`.",
            "",
            "## Figures",
            "",
            "- `figures/yolo_vehicle_max_histogram.svg`",
            "- `figures/motion_energy_max_histogram.svg`",
            "- `figures/score_fusion_yolo_motion_histogram.svg`",
            "- `figures/a0_candidate_time_distribution.svg`",
            "",
            "## Files",
            "",
            "- `tables/score_quality_summary.csv`",
            "- `tables/score_histograms.csv`",
            "- `tables/time_axis_coverage.csv`",
            "- `tables/a0_candidate_time_buckets.csv`",
            "- `tables/a0_candidate_distribution_summary.csv`",
            "",
            f"FINAL_DECISION: {final_decision}",
        ]
    )
    report_text = "\n".join(report) + "\n"
    (REPORTS / "FINAL_REPORT.md").write_text(report_text)
    (OUT / "FINAL_REPORT.md").write_text(report_text)
    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n```bash\npython outputs/video_signal_quality_audit_v1/scripts/run_signal_quality_audit.py\n```\n"
    )

    precompute_section = "\n".join(
        [
            "<!-- SIGNAL_QUALITY_AUDIT_V1 -->",
            "## Signal Quality Audit v1 Addendum",
            "",
            f"- Pipeline execution success: `{pipeline_execution}`.",
            f"- Prior signal non-degenerate: `{nondegenerate_status}`.",
            f"- Time-axis coverage: `{coverage_status}`.",
            f"- Score quality report: `outputs/video_signal_quality_audit_v1/FINAL_REPORT.md`.",
            f"- `yolo_vehicle_max` top tie fraction: `{next(r for r in stats if r['score_column'] == 'yolo_vehicle_max')['top_tie_fraction']}`.",
            f"- Coarse 5s gap count: `{coarse_cov['gap_count']}`; center10 gap count: `{anchor_cov['gap_count']}`.",
        ]
    )
    runtime_section = "\n".join(
        [
            "<!-- A0_BASELINE_ARCHIVE_V1 -->",
            "## A0 Baseline Archive Addendum",
            "",
            "- A0 baseline: `score_topk + temporal NMS + duration cap`, no CILS, no oracle confirmation.",
            "- Budget: `40` candidate clips.",
            "- NMS gap: `20.0` seconds.",
            "- Budget/gap source: carried over from `default_selector_score_sweep_v1` / `query_runtime_v1` dev operating point; not a fairness-tuned CILS comparison setting.",
            f"- A0 candidate time distribution status: `{candidate_stats['distribution_status']}`; top 10min bucket fraction `{candidate_stats['top_10min_bucket_fraction']}`.",
            "- Candidate distribution figure: `outputs/video_signal_quality_audit_v1/figures/a0_candidate_time_distribution.svg`.",
        ]
    )
    append_section(ROOT / "outputs" / "video_feature_precompute_v1" / "FINAL_REPORT.md", "<!-- SIGNAL_QUALITY_AUDIT_V1 -->", precompute_section)
    append_section(ROOT / "outputs" / "video_feature_precompute_v1" / "reports" / "FINAL_REPORT.md", "<!-- SIGNAL_QUALITY_AUDIT_V1 -->", precompute_section)
    append_section(ROOT / "outputs" / "video_feature_precompute_runtime_v1" / "FINAL_REPORT.md", "<!-- A0_BASELINE_ARCHIVE_V1 -->", runtime_section)
    append_section(ROOT / "outputs" / "video_feature_precompute_runtime_v1" / "reports" / "FINAL_REPORT.md", "<!-- A0_BASELINE_ARCHIVE_V1 -->", runtime_section)

    write_csv(
        TABLES / "sanity_checks.csv",
        [
            {"check": "no_oracle_or_probe_inputs", "status": "PASS", "details": "Only generated feature/runtime CSVs are read."},
            {"check": "coarse_time_axis_no_gaps", "status": coarse_cov["coverage_status"], "details": f"gap_count={coarse_cov['gap_count']}"},
            {"check": "center10_time_axis_no_gaps", "status": anchor_cov["coverage_status"], "details": f"gap_count={anchor_cov['gap_count']}"},
            {"check": "prior_signal_non_degenerate", "status": "PASS" if nondegenerate_status == "GO" else "WARN", "details": nondegenerate_status},
            {"check": "a0_candidate_distribution_not_single_bucket", "status": candidate_stats["distribution_status"], "details": f"top_10min_bucket_fraction={candidate_stats['top_10min_bucket_fraction']}"},
        ],
    )
    append_progress(
        f"pipeline={pipeline_execution}, prior_signal={nondegenerate_status}, coverage={coverage_status}, final_decision={final_decision}.",
        next_action="Pause real-video feature expansion and run toy simulation gate.",
    )


if __name__ == "__main__":
    main()
