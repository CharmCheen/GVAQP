#!/usr/bin/env python3
"""Convert Nexar-200 manifest rows to CASQ events and fixed units."""

from __future__ import annotations

from nexar_200_common import (
    EVENT_FIELDS,
    OUT,
    UNIT_FIELDS,
    UNIT_SECONDS,
    append_progress,
    read_csv,
    to_float,
    write_csv,
)


def video_duration(event_end) -> float:
    if event_end is None:
        return 30.0
    return max(30.0, float(event_end) + 10.0)


def overlaps(a0: float, a1: float, b0: float, b1: float) -> bool:
    return max(a0, b0) < min(a1, b1)


def main() -> int:
    manifest_path = OUT / "manifests" / "nexar_200_manifest.csv"
    manifest = read_csv(manifest_path) if manifest_path.exists() else []
    events = []
    conversion = []
    for row in manifest:
        if str(row.get("is_positive", "")).lower() != "true":
            conversion.append({"video_id": row.get("video_id", ""), "conversion_status": "normal_no_event", "reason": ""})
            continue
        original_start = to_float(row.get("original_event_start"))
        original_end = to_float(row.get("original_event_end"))
        alert_time = to_float(row.get("alert_time"))
        event_moment = to_float(row.get("event_moment"))
        if original_start is not None and original_end is not None:
            start, end = original_start, original_end
            source, confidence = "original_annotation", "high"
        elif alert_time is not None and event_moment is not None:
            start, end = alert_time, event_moment
            source, confidence = "derived_from_alert_time_to_event_moment", "medium"
        else:
            conversion.append({"video_id": row.get("video_id", ""), "conversion_status": "missing_boundary", "reason": "missing event_moment or alert_time"})
            continue
        if start >= end:
            conversion.append({"video_id": row.get("video_id", ""), "conversion_status": "invalid_boundary", "reason": "event_start >= event_end"})
            continue
        event = {
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
            "human_adjudicated": False,
            "original_label": row.get("label", ""),
            "source_annotation_path": row.get("local_metadata_path", ""),
        }
        events.append(event)
        conversion.append({"video_id": row.get("video_id", ""), "conversion_status": "converted", "reason": "derived precursor interval; not original human interval"})

    events_by_video = {ev["video_id"]: ev for ev in events}
    units = []
    for row in manifest:
        event = events_by_video.get(row["video_id"])
        end_time = video_duration(float(event["event_end"]) if event else None)
        for unit_seconds in UNIT_SECONDS:
            t = 0.0
            while t + unit_seconds <= end_time + 1e-9:
                end = t + unit_seconds
                matched = []
                if event and overlaps(t, end, float(event["event_start"]), float(event["event_end"])):
                    matched.append(event["event_id"])
                units.append(
                    {
                        "dataset": "nexar",
                        "video_id": row["video_id"],
                        "unit_id": f"{row['video_id']}_u{unit_seconds}_{int(t):06d}_{int(end):06d}",
                        "start_time": t,
                        "end_time": end,
                        "duration": unit_seconds,
                        "split": row.get("split", "train"),
                        "has_event_overlap": bool(matched),
                        "matched_event_ids": ";".join(matched),
                        "source_video_path": row.get("local_video_path", ""),
                        "source_annotation_path": row.get("local_metadata_path", ""),
                    }
                )
                t = end

    write_csv(OUT / "converted" / "casq_events_nexar_200.csv", events, EVENT_FIELDS)
    write_csv(OUT / "converted" / "casq_units_nexar_200.csv", units, UNIT_FIELDS)
    write_csv(OUT / "tables" / "nexar_200_conversion_status.csv", conversion, ["video_id", "conversion_status", "reason"])
    append_progress("convert_to_casq", "python scripts/10_convert_nexar_200_to_casq.py", f"events={len(events)} units={len(units)}", "validate schema")
    print(f"Converted Nexar-200 events={len(events)} units={len(units)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

