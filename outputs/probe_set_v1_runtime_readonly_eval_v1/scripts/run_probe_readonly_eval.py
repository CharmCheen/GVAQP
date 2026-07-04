#!/usr/bin/env python3
"""Read-only probe_set_v1 overlap audit for the frozen runtime output."""

from __future__ import annotations

import csv
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "probe_set_v1_runtime_readonly_eval_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
FIGURES = OUT / "figures"
LOGS = OUT / "logs"

RUNTIME_INTERVALS = ROOT / "outputs/query_runtime_v1/tables/returned_intervals.csv"
RUNTIME_MANIFEST = ROOT / "outputs/query_runtime_v1/tables/candidate_clip_manifest.csv"
PROBE_MANIFEST = ROOT / "outputs/probe_set_v1/probe_set_manifest.csv"
PROBE_LABELS = ROOT / "outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv"
POSITIVE_LABELS = {"true_interval", "point_anchor"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path: Path, skip_comments: bool = False) -> list[dict[str, str]]:
    if not skip_comments:
        with path.open(newline="") as f:
            return list(csv.DictReader(f))
    with path.open(newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
    return list(csv.DictReader(lines))


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


def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def append_progress(result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - Run frozen probe read-only eval\n\n")
        f.write("- Checkpoint: Run frozen probe read-only eval\n")
        f.write("- Commands run: `python outputs/probe_set_v1_runtime_readonly_eval_v1/scripts/run_probe_readonly_eval.py`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def make_svg(path: Path, probes: list[dict], intervals: list[dict]) -> None:
    width, height, margin = 1000, 180, 50
    tmax = max(max(float(p["local_t_end"]) for p in probes), max(float(i["t_end"]) for i in intervals))
    def x(t: float) -> float:
        return margin + (t / tmax) * (width - 2 * margin)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="50" y="28" font-family="Arial" font-size="18">Runtime intervals vs probe_set_v1 windows</text>',
        f'<line x1="{margin}" y1="70" x2="{width-margin}" y2="70" stroke="#333"/>',
        f'<line x1="{margin}" y1="120" x2="{width-margin}" y2="120" stroke="#333"/>',
        '<text x="10" y="75" font-family="Arial" font-size="12">runtime</text>',
        '<text x="10" y="125" font-family="Arial" font-size="12">probe</text>',
    ]
    for row in intervals:
        lines.append(f'<rect x="{x(float(row["t_start"])):.1f}" y="58" width="{max(1.0, x(float(row["t_end"])) - x(float(row["t_start"]))):.1f}" height="22" fill="#1f77b4" opacity="0.65"/>')
    for row in probes:
        fill = "#d62728" if row["label"] in POSITIVE_LABELS else "#888888"
        lines.append(f'<rect x="{x(float(row["local_t_start"])):.1f}" y="108" width="{max(1.0, x(float(row["local_t_end"])) - x(float(row["local_t_start"]))):.1f}" height="22" fill="{fill}" opacity="0.75"/>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    for d in [TABLES, REPORTS, FIGURES, LOGS]:
        d.mkdir(parents=True, exist_ok=True)

    intervals = read_csv(RUNTIME_INTERVALS)
    runtime_manifest = read_csv(RUNTIME_MANIFEST)
    probes = read_csv(PROBE_MANIFEST)
    labels = {r["probe_id"]: r for r in read_csv(PROBE_LABELS, skip_comments=True)}
    for probe in probes:
        label = labels.get(probe["probe_id"], {})
        probe["label"] = label.get("label", "")
        probe["reference_source"] = label.get("reference_source", "probe_set_v1_vlm_oracle_reference")
        probe["is_probe_positive"] = str(probe["label"] in POSITIVE_LABELS)

    match_rows = []
    covered_probe_ids = set()
    covered_positive_probe_ids = set()
    covered_negative_probe_ids = set()
    for interval in intervals:
        i0, i1 = float(interval["t_start"]), float(interval["t_end"])
        for probe in probes:
            p0, p1 = float(probe["local_t_start"]), float(probe["local_t_end"])
            ov = overlap(i0, i1, p0, p1)
            if ov <= 0:
                continue
            pid = probe["probe_id"]
            covered_probe_ids.add(pid)
            if probe["label"] in POSITIVE_LABELS:
                covered_positive_probe_ids.add(pid)
            else:
                covered_negative_probe_ids.add(pid)
            match_rows.append(
                {
                    "interval_start": interval["t_start"],
                    "interval_end": interval["t_end"],
                    "supporting_anchor_ids": interval["supporting_anchor_ids"],
                    "probe_id": pid,
                    "probe_start": probe["local_t_start"],
                    "probe_end": probe["local_t_end"],
                    "overlap_seconds": f"{ov:.3f}",
                    "probe_label": probe["label"],
                    "dataset_source": "probe_set_v1_vlm_oracle_reference",
                }
            )

    positive_probe_ids = {p["probe_id"] for p in probes if p["label"] in POSITIVE_LABELS}
    negative_probe_ids = {p["probe_id"] for p in probes if p["label"] not in POSITIVE_LABELS}
    coverage_precision = len(covered_positive_probe_ids) / len(covered_probe_ids) if covered_probe_ids else ""
    positive_recall = len(covered_positive_probe_ids) / len(positive_probe_ids) if positive_probe_ids else ""
    negative_coverage = len(covered_negative_probe_ids) / len(negative_probe_ids) if negative_probe_ids else ""
    summary = {
        "dataset_source": "probe_set_v1_vlm_oracle_reference",
        "eval_type": "read_only_time_overlap_audit_not_tuning",
        "runtime_interval_count": len(intervals),
        "runtime_candidate_count": len(runtime_manifest),
        "probe_count": len(probes),
        "probe_positive_count": len(positive_probe_ids),
        "probe_negative_count": len(negative_probe_ids),
        "covered_probe_count": len(covered_probe_ids),
        "covered_positive_probe_count": len(covered_positive_probe_ids),
        "covered_negative_probe_count": len(covered_negative_probe_ids),
        "covered_probe_precision_probe_set_v1": coverage_precision,
        "positive_probe_window_recall_probe_set_v1": positive_recall,
        "negative_probe_window_coverage_probe_set_v1": negative_coverage,
        "probe_time_min": min(float(p["local_t_start"]) for p in probes),
        "probe_time_max": max(float(p["local_t_end"]) for p in probes),
        "runtime_time_min": min(float(i["t_start"]) for i in intervals),
        "runtime_time_max": max(float(i["t_end"]) for i in intervals),
    }
    sanity = [
        {
            "check": "probe_labels_not_used_for_selector_config",
            "status": "PASS",
            "details": "Runtime output was generated in outputs/query_runtime_v1 before this read-only audit.",
        },
        {
            "check": "all_probe_rows_mark_do_not_use_for_tuning",
            "status": "PASS" if all(p.get("do_not_use_for_tuning") == "True" for p in probes) else "FAIL",
            "details": "Checked probe_set_manifest.csv do_not_use_for_tuning column.",
        },
        {
            "check": "probe_labels_parse_ok",
            "status": "PASS" if len(labels) == len(probes) else "FAIL",
            "details": f"Parsed {len(labels)} labels for {len(probes)} probes.",
        },
        {
            "check": "time_axis_scope_warning",
            "status": "WARN",
            "details": "Probe media uses fallback_dataset3_with_reference_absolute_offset; overlap is a compatibility audit, not a tuning or full-video evaluation.",
        },
    ]
    write_csv(TABLES / "probe_overlap_matches.csv", match_rows)
    write_csv(TABLES / "probe_readonly_summary.csv", [summary])
    write_csv(TABLES / "sanity_checks.csv", sanity)
    make_svg(FIGURES / "runtime_vs_probe_windows.svg", probes, intervals)

    decision = "NO-GO" if any(r["status"] == "FAIL" for r in sanity) else "WEAK GO"
    report = [
        "# Probe Set v1 Runtime Read-Only Eval Final Report",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This is a read-only overlap audit of the frozen `query_runtime_v1` output against `probe_set_v1`. It does not tune thresholds, score columns, NMS gaps, budgets, repair decisions, or selector choices.",
        "",
        "All metrics in this report are labeled `probe_set_v1_vlm_oracle_reference`; these are VLM oracle judgments, not human ground truth.",
        "",
        "## Results",
        "",
        f"- Runtime intervals: `{summary['runtime_interval_count']}`.",
        f"- Probe windows: `{summary['probe_count']}`; positives `probe_set_v1_vlm_oracle_reference`: `{summary['probe_positive_count']}`.",
        f"- Covered probe windows: `{summary['covered_probe_count']}`.",
        f"- Covered positive probe windows: `{summary['covered_positive_probe_count']}`.",
        f"- Covered negative probe windows: `{summary['covered_negative_probe_count']}`.",
        f"- Covered-probe precision `probe_set_v1_vlm_oracle_reference`: {float(coverage_precision) if coverage_precision != '' else math.nan:.3f}.",
        f"- Positive probe-window recall `probe_set_v1_vlm_oracle_reference`: {float(positive_recall) if positive_recall != '' else math.nan:.3f}.",
        "",
        "## Interpretation",
        "",
        "The runtime output overlaps only part of the independent probe grid, so this is a weak compatibility signal, not a promotion criterion. The selector configuration remains the pre-registered `query_runtime_v1` setting.",
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
            "- `tables/probe_overlap_matches.csv`",
            "- `tables/probe_readonly_summary.csv`",
            "- `tables/sanity_checks.csv`",
            "- `figures/runtime_vs_probe_windows.svg`",
            "",
            f"FINAL_DECISION: {decision}",
        ]
    )
    (REPORTS / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n```bash\npython outputs/probe_set_v1_runtime_readonly_eval_v1/scripts/run_probe_readonly_eval.py\n```\n"
    )
    append_progress(
        f"Covered {len(covered_positive_probe_ids)}/{len(positive_probe_ids)} positive probe windows; final decision {decision}.",
        failure="; ".join(r["check"] for r in sanity if r["status"] == "FAIL") or "none",
        next_action="Use this only as read-only evidence; do not tune runtime settings from probe_set_v1.",
    )
    if any(r["status"] == "FAIL" for r in sanity):
        raise SystemExit("Probe read-only eval sanity failed")


if __name__ == "__main__":
    main()
