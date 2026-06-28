#!/usr/bin/env python3
"""Validate Nexar-200 CASQ events and units."""

from __future__ import annotations

from pathlib import Path

from nexar_200_common import EVENT_FIELDS, MANIFEST_FIELDS, OUT, UNIT_FIELDS, append_progress, read_csv, to_float, write_csv


def main() -> int:
    manifest = read_csv(OUT / "manifests" / "nexar_200_manifest.csv")
    events = read_csv(OUT / "converted" / "casq_events_nexar_200.csv")
    units = read_csv(OUT / "converted" / "casq_units_nexar_200.csv")
    checks = []

    checks.append({"check": "manifest_required_columns", "passed": list(manifest[0].keys()) == MANIFEST_FIELDS if manifest else False, "detail": ""})
    checks.append({"check": "event_required_columns", "passed": list(events[0].keys()) == EVENT_FIELDS if events else False, "detail": ""})
    checks.append({"check": "unit_required_columns", "passed": list(units[0].keys()) == UNIT_FIELDS if units else False, "detail": ""})

    bad_intervals = []
    bad_midpoints = []
    bad_durations = []
    unmarked_derived = []
    bad_human = []
    fabricated = []
    original_sources = []
    for event in events:
        start = to_float(event.get("event_start"))
        end = to_float(event.get("event_end"))
        midpoint = to_float(event.get("event_midpoint"))
        duration = to_float(event.get("event_duration"))
        if start is None or end is None or not start < end:
            bad_intervals.append(event.get("event_id", ""))
        if midpoint is None or start is None or end is None or not (start <= midpoint <= end):
            bad_midpoints.append(event.get("event_id", ""))
        if duration is None or duration <= 0:
            bad_durations.append(event.get("event_id", ""))
        source = event.get("boundary_source", "")
        if source.startswith("derived_") and source == "original_annotation":
            unmarked_derived.append(event.get("event_id", ""))
        if source == "original_annotation":
            original_sources.append(event.get("event_id", ""))
        if str(event.get("human_adjudicated", "")).lower() not in {"false", "0"}:
            bad_human.append(event.get("event_id", ""))
        if source in {"", "fabricated"}:
            fabricated.append(event.get("event_id", ""))

    checks.append({"check": "event_start_lt_event_end", "passed": not bad_intervals, "detail": ";".join(bad_intervals)})
    checks.append({"check": "event_duration_positive", "passed": not bad_durations, "detail": ";".join(bad_durations)})
    checks.append({"check": "event_midpoint_inside_interval", "passed": not bad_midpoints, "detail": ";".join(bad_midpoints)})
    checks.append({"check": "derived_boundaries_not_original_annotation", "passed": not original_sources, "detail": ";".join(original_sources)})
    checks.append({"check": "derived_boundaries_explicitly_marked", "passed": not unmarked_derived, "detail": ";".join(unmarked_derived)})
    checks.append({"check": "human_adjudicated_false", "passed": not bad_human, "detail": ";".join(bad_human)})
    checks.append({"check": "no_fabricated_boundaries", "passed": not fabricated, "detail": ";".join(fabricated)})

    event_ids = {event["event_id"] for event in events}
    normal_videos = {row["video_id"] for row in manifest if str(row.get("is_normal", "")).lower() == "true"}
    missing_matches = []
    normal_overlap = []
    for unit in units:
        matched = [x for x in unit.get("matched_event_ids", "").split(";") if x]
        for event_id in matched:
            if event_id not in event_ids:
                missing_matches.append(event_id)
        if unit.get("video_id") in normal_videos and matched:
            normal_overlap.append(unit.get("unit_id", ""))
    checks.append({"check": "all_matched_event_ids_exist", "passed": not missing_matches, "detail": ";".join(sorted(set(missing_matches)))})
    checks.append({"check": "normal_videos_have_no_casq_events", "passed": not normal_overlap, "detail": ";".join(normal_overlap[:20])})

    positive_videos = {row["video_id"] for row in manifest if str(row.get("is_positive", "")).lower() == "true"}
    event_overlap_units = [row for row in units if str(row.get("has_event_overlap", "")).lower() == "true"]
    background_units = [row for row in units if str(row.get("has_event_overlap", "")).lower() != "true"]
    durations = [to_float(event.get("event_duration")) for event in events]
    durations = [value for value in durations if value is not None]
    boundary_source_counts = {}
    boundary_conf_counts = {}
    duration_bins = {"<=0.5s": 0, "0.5-1s": 0, "1-2s": 0, "2-5s": 0, ">5s": 0}
    for event in events:
        boundary_source_counts[event.get("boundary_source", "")] = boundary_source_counts.get(event.get("boundary_source", ""), 0) + 1
        boundary_conf_counts[event.get("boundary_confidence", "")] = boundary_conf_counts.get(event.get("boundary_confidence", ""), 0) + 1
        duration = to_float(event.get("event_duration"))
        if duration is None:
            continue
        if duration <= 0.5:
            duration_bins["<=0.5s"] += 1
        elif duration <= 1.0:
            duration_bins["0.5-1s"] += 1
        elif duration <= 2.0:
            duration_bins["1-2s"] += 1
        elif duration <= 5.0:
            duration_bins["2-5s"] += 1
        else:
            duration_bins[">5s"] += 1
    write_csv(
        OUT / "tables" / "nexar_200_event_stats.csv",
        [
            {"metric": "num_videos", "value": len({row["video_id"] for row in manifest})},
            {"metric": "num_positive_videos", "value": len(positive_videos)},
            {"metric": "num_normal_videos", "value": len(normal_videos)},
            {"metric": "usable_casq_events", "value": len(events)},
            {"metric": "event_duration_min", "value": min(durations) if durations else ""},
            {"metric": "event_duration_median", "value": sorted(durations)[len(durations) // 2] if durations else ""},
            {"metric": "event_duration_mean", "value": sum(durations) / len(durations) if durations else ""},
            {"metric": "event_duration_max", "value": max(durations) if durations else ""},
            {"metric": "event_duration_distribution", "value": duration_bins},
            {"metric": "boundary_source_distribution", "value": boundary_source_counts},
            {"metric": "boundary_confidence_distribution", "value": boundary_conf_counts},
        ],
        ["metric", "value"],
    )
    write_csv(
        OUT / "tables" / "nexar_200_unit_stats.csv",
        [
            {"metric": "num_units", "value": len(units)},
            {"metric": "event_overlap_units", "value": len(event_overlap_units)},
            {"metric": "background_units", "value": len(background_units)},
            {"metric": "unit_durations", "value": sorted({float(row["duration"]) for row in units})},
        ],
        ["metric", "value"],
    )

    all_passed = all(row["passed"] for row in checks)
    write_csv(OUT / "tables" / "nexar_200_schema_validation.csv", checks, ["check", "passed", "detail"])
    append_progress(
        "validate_schema",
        "python scripts/20_validate_nexar_200_casq.py",
        f"validation passed={all_passed}",
        "run phase0-style simulations",
        failure="" if all_passed else "validation failed",
    )
    print(f"Nexar-200 schema validation passed={all_passed}")
    return 0 if all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
