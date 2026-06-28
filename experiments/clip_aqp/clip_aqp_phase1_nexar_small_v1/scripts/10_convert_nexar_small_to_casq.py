#!/usr/bin/env python3
"""Convert Nexar small-subset manifest rows into CASQ event and unit schemas."""

from __future__ import annotations

from pathlib import Path

from nexar_small_common import (
    EVENT_FIELDS,
    MANIFEST_FIELDS,
    OUT,
    UNIT_FIELDS,
    append_progress,
    ensure_dirs,
    read_csv,
    to_float,
    write_csv,
)


def derive_boundary(row: dict) -> tuple[str, float | None, float | None, str, str, str]:
    original_start = to_float(row.get("original_event_start"))
    original_end = to_float(row.get("original_event_end"))
    event_moment = to_float(row.get("event_moment"))
    alert_time = to_float(row.get("alert_time"))
    if original_start is not None and original_end is not None and original_start < original_end:
        return "converted", original_start, original_end, "original_annotation", "high", ""
    if alert_time is not None and event_moment is not None and alert_time < event_moment:
        return "converted", alert_time, event_moment, "derived_from_alert_time_to_event_moment", "medium", "derived precursor interval; not original human interval"
    if event_moment is not None:
        start = max(0.0, event_moment - 2.5)
        end = event_moment + 2.5
        return "converted", start, end, "derived_from_event_moment", "low", "derived +/-2.5s interval; not original human interval"
    if alert_time is not None:
        return "converted", alert_time, alert_time + 5.0, "derived_from_alert_time", "low", "derived 5s alert interval; not original human interval"
    return "missing_boundary", None, None, "", "", "missing boundary: no original interval, event moment, or alert time"


def overlaps(a0: float, a1: float, b0: float, b1: float) -> bool:
    return max(a0, b0) < min(a1, b1)


def video_duration(row: dict, event_end: float | None) -> float:
    if event_end is not None:
        return max(30.0, event_end + 10.0)
    return 30.0


def build_units(row: dict, events_for_video: list[dict], unit_seconds: int) -> list[dict]:
    duration = video_duration(row, max((to_float(ev.get("event_end")) or 0.0 for ev in events_for_video), default=None))
    units = []
    t = 0.0
    while t + unit_seconds <= duration + 1e-9:
        end = t + unit_seconds
        matched = []
        for ev in events_for_video:
            ev_start = to_float(ev["event_start"])
            ev_end = to_float(ev["event_end"])
            if ev_start is not None and ev_end is not None and overlaps(t, end, ev_start, ev_end):
                matched.append(ev["event_id"])
        units.append(
            {
                "dataset": "nexar",
                "video_id": row["video_id"],
                "unit_id": f"{row['video_id']}_u{unit_seconds}_{int(t):06d}_{int(end):06d}",
                "start_time": t,
                "end_time": end,
                "duration": end - t,
                "split": row.get("split", "train") or "train",
                "has_event_overlap": bool(matched),
                "matched_event_ids": ";".join(matched),
                "source_video_path": row.get("local_video_path", ""),
                "source_annotation_path": row.get("local_metadata_path", ""),
            }
        )
        t = end
    return units


def main() -> int:
    ensure_dirs()
    manifest_path = OUT / "download_manifest" / "nexar_small_manifest.csv"
    if not manifest_path.exists():
        write_csv(OUT / "converted" / "casq_events_nexar_small.csv", [], EVENT_FIELDS)
        write_csv(OUT / "converted" / "casq_units_nexar_small.csv", [], UNIT_FIELDS)
        write_csv(
            OUT / "tables" / "nexar_small_conversion_status.csv",
            [{"status": "missing_manifest", "message": f"Missing manifest: {manifest_path}"}],
            ["status", "message"],
        )
        append_progress("convert_nexar_small_to_casq", "python scripts/10_convert_nexar_small_to_casq.py", "missing manifest; wrote empty outputs", "run prepare script first", failure="missing manifest")
        return 0

    manifest = read_csv(manifest_path)
    events = []
    conversion_rows = []
    for row in manifest:
        if row.get("download_status") == "NEED_MANUAL_DATASET_ACCESS" or not row.get("video_id"):
            conversion_rows.append({"video_id": row.get("video_id", ""), "conversion_status": "missing_metadata", "notes": row.get("notes", "")})
            continue
        is_positive = str(row.get("is_positive", "")).lower() == "true"
        if not is_positive:
            conversion_rows.append({"video_id": row["video_id"], "conversion_status": "normal_no_event", "notes": "normal/background manifest row"})
            continue
        status, start, end, source, confidence, notes = derive_boundary(row)
        conversion_rows.append({"video_id": row["video_id"], "conversion_status": status, "notes": notes})
        if status != "converted" or start is None or end is None:
            continue
        events.append(
            {
                "dataset": "nexar",
                "video_id": row["video_id"],
                "event_id": f"nexar_{row['video_id']}_event_0001",
                "event_type": "collision_or_near_collision_precursor",
                "event_start": start,
                "event_end": end,
                "event_midpoint": (start + end) / 2.0,
                "event_duration": end - start,
                "involved_object": "unknown",
                "ego_relevant": True,
                "boundary_source": source,
                "boundary_confidence": confidence,
                "label_source": "Nexar metadata",
                "human_adjudicated": "unknown",
                "original_label": row.get("label", ""),
                "source_annotation_path": row.get("local_metadata_path", ""),
            }
        )

    events_by_video: dict[str, list[dict]] = {}
    for ev in events:
        events_by_video.setdefault(ev["video_id"], []).append(ev)

    units = []
    for row in manifest:
        if not row.get("video_id") or row.get("download_status") == "NEED_MANUAL_DATASET_ACCESS":
            continue
        for unit_seconds in (5, 10, 15):
            units.extend(build_units(row, events_by_video.get(row["video_id"], []), unit_seconds))

    write_csv(OUT / "converted" / "casq_events_nexar_small.csv", events, EVENT_FIELDS)
    write_csv(OUT / "converted" / "casq_units_nexar_small.csv", units, UNIT_FIELDS)
    write_csv(OUT / "tables" / "nexar_small_conversion_status.csv", conversion_rows, ["video_id", "conversion_status", "notes"])
    append_progress(
        "convert_nexar_small_to_casq",
        "python scripts/10_convert_nexar_small_to_casq.py",
        f"converted events={len(events)} units={len(units)}",
        "validate CASQ conversion",
    )
    print(f"Converted Nexar small subset: events={len(events)}, units={len(units)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
