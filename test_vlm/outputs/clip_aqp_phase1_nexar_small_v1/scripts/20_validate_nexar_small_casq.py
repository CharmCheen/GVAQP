#!/usr/bin/env python3
"""Validate converted Nexar small-subset CASQ events and units."""

from __future__ import annotations

from pathlib import Path

from nexar_small_common import OUT, append_progress, file_exists_if_nonempty, read_csv, to_float, write_csv


def main() -> int:
    events_path = OUT / "converted" / "casq_events_nexar_small.csv"
    units_path = OUT / "converted" / "casq_units_nexar_small.csv"
    manifest_path = OUT / "download_manifest" / "nexar_small_manifest.csv"
    events = read_csv(events_path) if events_path.exists() else []
    units = read_csv(units_path) if units_path.exists() else []
    manifest = read_csv(manifest_path) if manifest_path.exists() else []

    checks = []
    event_ids = {row["event_id"] for row in events if row.get("event_id")}

    bad_intervals = []
    bad_midpoints = []
    bad_durations = []
    unmarked_derived = []
    fabricated_like = []
    for row in events:
        start = to_float(row.get("event_start"))
        end = to_float(row.get("event_end"))
        midpoint = to_float(row.get("event_midpoint"))
        duration = to_float(row.get("event_duration"))
        if start is None or end is None or not start < end:
            bad_intervals.append(row.get("event_id", ""))
        if midpoint is None or start is None or end is None or not (start <= midpoint <= end):
            bad_midpoints.append(row.get("event_id", ""))
        if duration is None or duration <= 0:
            bad_durations.append(row.get("event_id", ""))
        source = row.get("boundary_source", "")
        confidence = row.get("boundary_confidence", "")
        if source.startswith("derived_") and confidence not in {"low", "medium"}:
            unmarked_derived.append(row.get("event_id", ""))
        if source == "" or source == "fabricated":
            fabricated_like.append(row.get("event_id", ""))

    checks.append({"check": "event_start_lt_event_end", "passed": not bad_intervals, "detail": ";".join(bad_intervals)})
    checks.append({"check": "event_midpoint_inside_interval", "passed": not bad_midpoints, "detail": ";".join(bad_midpoints)})
    checks.append({"check": "event_duration_positive", "passed": not bad_durations, "detail": ";".join(bad_durations)})
    checks.append({"check": "derived_boundaries_explicitly_marked", "passed": not unmarked_derived, "detail": ";".join(unmarked_derived)})
    checks.append({"check": "no_fabricated_boundaries", "passed": not fabricated_like, "detail": ";".join(fabricated_like)})

    missing_matches = []
    normal_event_violations = []
    manifest_normal = {row["video_id"] for row in manifest if str(row.get("is_normal", "")).lower() == "true" and str(row.get("is_positive", "")).lower() != "true"}
    for unit in units:
        for event_id in [x for x in unit.get("matched_event_ids", "").split(";") if x]:
            if event_id not in event_ids:
                missing_matches.append(event_id)
        if unit.get("video_id") in manifest_normal and str(unit.get("has_event_overlap", "")).lower() == "true":
            normal_event_violations.append(unit.get("unit_id", ""))
    checks.append({"check": "all_matched_event_ids_exist", "passed": not missing_matches, "detail": ";".join(sorted(set(missing_matches)))})
    checks.append({"check": "normal_videos_have_no_positive_event", "passed": not normal_event_violations, "detail": ";".join(normal_event_violations[:20])})

    missing_video_paths = []
    for row in manifest:
        status = row.get("download_status", "")
        video_path = row.get("local_video_path", "")
        if status in {"downloaded", "local_video_present"} and not file_exists_if_nonempty(video_path):
            missing_video_paths.append(row.get("video_id", ""))
    checks.append({"check": "source_paths_exist_if_downloaded", "passed": not missing_video_paths, "detail": ";".join(missing_video_paths)})

    all_passed = all(str(row["passed"]) == "True" or row["passed"] is True for row in checks)
    write_csv(OUT / "tables" / "nexar_small_schema_validation.csv", checks, ["check", "passed", "detail"])

    event_stats = {
        "num_events": len(events),
        "boundary_source_distribution": {},
        "boundary_confidence_distribution": {},
        "usable_event_boundaries": 0,
    }
    for ev in events:
        event_stats["boundary_source_distribution"][ev.get("boundary_source", "")] = event_stats["boundary_source_distribution"].get(ev.get("boundary_source", ""), 0) + 1
        event_stats["boundary_confidence_distribution"][ev.get("boundary_confidence", "")] = event_stats["boundary_confidence_distribution"].get(ev.get("boundary_confidence", ""), 0) + 1
        if to_float(ev.get("event_start")) is not None and to_float(ev.get("event_end")) is not None:
            event_stats["usable_event_boundaries"] += 1

    videos = {row.get("video_id") for row in manifest if row.get("video_id")}
    positive_videos = {row.get("video_id") for row in manifest if str(row.get("is_positive", "")).lower() == "true"}
    normal_videos = {row.get("video_id") for row in manifest if str(row.get("is_normal", "")).lower() == "true"}
    background_units = [row for row in units if str(row.get("has_event_overlap", "")).lower() != "true"]
    event_units = [row for row in units if str(row.get("has_event_overlap", "")).lower() == "true"]

    write_csv(
        OUT / "tables" / "nexar_small_event_stats.csv",
        [
            {"metric": "num_videos", "value": len(videos)},
            {"metric": "num_positive_videos", "value": len(positive_videos)},
            {"metric": "num_normal_videos", "value": len(normal_videos)},
            {"metric": "num_casq_events", "value": event_stats["num_events"]},
            {"metric": "boundary_source_distribution", "value": event_stats["boundary_source_distribution"]},
            {"metric": "boundary_confidence_distribution", "value": event_stats["boundary_confidence_distribution"]},
            {"metric": "usable_event_boundaries", "value": event_stats["usable_event_boundaries"]},
        ],
        ["metric", "value"],
    )
    write_csv(
        OUT / "tables" / "nexar_small_unit_stats.csv",
        [
            {"metric": "num_units", "value": len(units)},
            {"metric": "background_units", "value": len(background_units)},
            {"metric": "event_overlap_units", "value": len(event_units)},
            {"metric": "unit_durations", "value": sorted({row.get("duration") for row in units}) if units else []},
        ],
        ["metric", "value"],
    )
    append_progress(
        "validate_nexar_small_casq",
        "python scripts/20_validate_nexar_small_casq.py",
        f"validation passed={all_passed}",
        "generate ingestion report",
        failure="" if all_passed else "one or more validation checks failed",
    )
    print(f"Nexar small validation passed={all_passed}")
    return 0 if all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

