#!/usr/bin/env python3
"""Generate the Nexar small-subset CASQ ingestion report."""

from __future__ import annotations

import json
from pathlib import Path

from nexar_small_common import OUT, README, append_progress, read_csv, write_csv


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def table_md(rows: list[dict]) -> str:
    if not rows:
        return "_No rows._"
    columns = list(rows[0].keys())
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    return "\n".join(lines)


def metric_value(rows: list[dict], metric: str, default="0"):
    for row in rows:
        if row.get("metric") == metric:
            return row.get("value", default)
    return default


def decide(access: dict, events: list[dict]) -> str:
    access_decision = access.get("decision", "")
    if access_decision == "NEED_MANUAL_DATASET_ACCESS":
        return "NEED_MANUAL_DATASET_ACCESS"
    if not events:
        return "NOT_SUITABLE_FOR_CASQ_BOUNDARIES"
    sources = {row.get("boundary_source", "") for row in events}
    if sources and all(source.startswith("derived_") for source in sources):
        return "BOUNDARIES_ARE_DERIVED_ONLY"
    return "READY_FOR_200_EVENT_SUBSET"


def all_manifest_empty(values: list[str]) -> bool:
    return all(str(value).strip() == "" for value in values)


def main() -> int:
    access = read_json(OUT / "tables" / "nexar_small_access_status.json")
    manifest = read_csv(OUT / "download_manifest" / "nexar_small_manifest.csv") if (OUT / "download_manifest" / "nexar_small_manifest.csv").exists() else []
    events = read_csv(OUT / "converted" / "casq_events_nexar_small.csv") if (OUT / "converted" / "casq_events_nexar_small.csv").exists() else []
    units = read_csv(OUT / "converted" / "casq_units_nexar_small.csv") if (OUT / "converted" / "casq_units_nexar_small.csv").exists() else []
    validation = read_csv(OUT / "tables" / "nexar_small_schema_validation.csv") if (OUT / "tables" / "nexar_small_schema_validation.csv").exists() else []
    event_stats = read_csv(OUT / "tables" / "nexar_small_event_stats.csv") if (OUT / "tables" / "nexar_small_event_stats.csv").exists() else []
    unit_stats = read_csv(OUT / "tables" / "nexar_small_unit_stats.csv") if (OUT / "tables" / "nexar_small_unit_stats.csv").exists() else []
    conversion_status = read_csv(OUT / "tables" / "nexar_small_conversion_status.csv") if (OUT / "tables" / "nexar_small_conversion_status.csv").exists() else []

    readme_summary = access.get("readme_summary", {})
    hf_probe = access.get("hf_access_probe") or {}
    final_decision = decide(access, events)
    write_csv(OUT / "tables" / "nexar_small_final_decision.csv", [{"decision": final_decision}], ["decision"])
    metadata_sources = sorted({row.get("local_metadata_path", "") for row in manifest if row.get("local_metadata_path")})
    original_boundaries_present = not all_manifest_empty([row.get("original_event_start", "") for row in manifest] + [row.get("original_event_end", "") for row in manifest])
    event_moment_present = not all_manifest_empty([row.get("event_moment", "") for row in manifest])
    alert_time_present = not all_manifest_empty([row.get("alert_time", "") for row in manifest])
    videos_downloaded = any(row.get("download_status") in {"downloaded", "local_video_present"} for row in manifest)

    lines = [
        "# Nexar Small-Subset CASQ Ingestion Report",
        "",
        "## 1. Goal",
        "",
        "Run a Phase 1.1 smoke test to determine whether a small Nexar subset can be mapped into CASQ event-boundary and unit/block schemas without downloading the full dataset, running VLMs, training models, or fabricating event boundaries.",
        "",
        "## 2. Data Access Status",
        "",
        f"- Nexar scaffold README: `{README}`",
        f"- README exists: `{readme_summary.get('readme_exists', README.exists())}`",
        f"- Access decision: `{access.get('decision', 'unknown')}`",
        f"- Access message: {access.get('message', 'not recorded')}",
        f"- Hugging Face token present: `{access.get('hf_token_present', False)}`",
        f"- Hugging Face/API probe status: `{hf_probe.get('status', 'not_run')}`",
        f"- Hugging Face/API probe error: {hf_probe.get('error', '') or 'none'}",
        f"- Metadata sources used: `{metadata_sources}`",
        f"- Videos downloaded by this run: `{videos_downloaded}`",
        "",
        "## 3. Download / Manifest Summary",
        "",
        f"- Manifest path: `{OUT / 'download_manifest' / 'nexar_small_manifest.csv'}`",
        f"- Manifest rows: `{len(manifest)}`",
        f"- CASQ events converted: `{len(events)}`",
        f"- CASQ units converted: `{len(units)}`",
        "",
        table_md(manifest[:10]),
        "",
        "## 4. Annotation Fields Found",
        "",
        f"- Expected metadata files: `{readme_summary.get('expected_metadata_files', [])}`",
        f"- Expected annotation fields: `{readme_summary.get('expected_annotation_fields', [])}`",
        f"- Original `event_start` / `event_end` exists in observed metadata: `{original_boundaries_present}`",
        f"- Event moment observed in metadata: `{event_moment_present}`",
        f"- Alert time observed in metadata: `{alert_time_present}`",
        f"- Event moment / alert time expected from scaffold: `{readme_summary.get('event_moment_alert_time_expected', False)}`",
        f"- Positive identification: {readme_summary.get('positive_identification', 'unknown')}",
        f"- Normal identification: {readme_summary.get('normal_identification', 'unknown')}",
        "",
        "The observed public metadata contains `time_of_event` and `time_of_alert`, but not original interval fields named `event_start` / `event_end`.",
        "",
        "## 5. CASQ Boundary Mapping",
        "",
        "- If original `event_start` / `event_end` exist, converters use them directly with `boundary_source=original_annotation`.",
        "- If `alert_time` and `event_moment` exist, converters derive `[alert_time, event_moment]` with `boundary_source=derived_from_alert_time_to_event_moment` and `boundary_confidence=medium`.",
        "- If only `event_moment` exists, converters derive `[max(0, event_moment - 2.5), event_moment + 2.5]` with `boundary_source=derived_from_event_moment` and `boundary_confidence=low`.",
        "- If only `alert_time` exists, converters derive `[alert_time, alert_time + 5.0]` with `boundary_source=derived_from_alert_time` and `boundary_confidence=low`.",
        "- If neither original boundary nor event moment/alert time exists, no event boundary is created.",
        "",
        "Derived boundaries are explicitly marked and must not be treated as original human interval annotations.",
        "",
        "## 6. Converted CASQ Events",
        "",
        table_md(event_stats),
        "",
        "Conversion status:",
        "",
        table_md(conversion_status[:20]),
        "",
        "## 7. Converted CASQ Units",
        "",
        "The converter creates fixed 5s, 10s, and 15s units for manifest rows with metadata video IDs. Tail fragments shorter than the configured unit length are dropped to keep unit durations fixed.",
        "",
        table_md(unit_stats),
        "",
        "## 8. Schema Validation",
        "",
        table_md(validation),
        "",
        "Validation checks cover interval order, midpoint inclusion, positive duration, matched event IDs, normal-video event leakage, fabricated-boundary markings, derived-boundary markings, and downloaded source path existence.",
        "",
        "## 9. Limitations",
        "",
        "- Only metadata CSV files were used; videos were not downloaded.",
        "- No full dataset download was attempted.",
        "- CASQ intervals are derived from `time_of_alert` and `time_of_event`; they are not original human event_start/event_end interval annotations.",
        "- Source video paths are expected paths only until the approved 25 positive / 25 normal videos are downloaded or otherwise placed locally.",
        "- Existing Phase 0 pseudo-events remain debugging-only and were not used as human-truth boundaries.",
        "",
        "## 10. Recommendation",
        "",
        "Use this metadata-only smoke result to request the bounded video subset next: 25 positive videos and 25 normal videos matching the manifest. For a 200-event expansion, treat Nexar boundaries as derived precursor intervals unless a source with original interval annotations is added.",
        "",
        f"NEXAR_SMALL_DECISION: {final_decision}",
    ]
    report_path = OUT / "reports" / "NEXAR_SMALL_INGESTION_REPORT.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    append_progress(
        "generate_nexar_small_report",
        "python scripts/30_generate_nexar_small_report.py",
        f"wrote report with decision {final_decision}",
        "review report and request manual access if needed",
    )
    print(f"Wrote {report_path} with decision {final_decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
