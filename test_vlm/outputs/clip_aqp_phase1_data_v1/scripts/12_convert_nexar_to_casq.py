#!/usr/bin/env python3
"""Conservative Nexar collision prediction conversion scaffold."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from phase1_data_common import DATASET_ROOT, EVENT_FIELDS, OUT, append_progress, status_row, write_csv


def iter_rows(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)
    elif path.suffix.lower() in {".json", ".jsonl"}:
        with path.open("r", encoding="utf-8") as f:
            if path.suffix.lower() == ".jsonl":
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
            else:
                data = json.load(f)
                if isinstance(data, list):
                    for row in data:
                        if isinstance(row, dict):
                            yield row
                elif isinstance(data, dict):
                    for key, row in data.items():
                        if isinstance(row, dict):
                            row = dict(row)
                            row.setdefault("video_id", key)
                            yield row


def main() -> int:
    base = DATASET_ROOT / "nexar"
    candidates = [
        base / "metadata" / "train_metadata.csv",
        base / "metadata" / "train_metadata.json",
        base / "metadata" / "metadata.csv",
        base / "metadata" / "metadata.jsonl",
    ]
    present = [path for path in candidates if path.exists()]
    status_path = OUT / "tables" / "nexar_conversion_status.csv"
    if not present:
        write_csv(
            status_path,
            [
                status_row(
                    "nexar",
                    "MISSING_INPUT",
                    "No local Nexar metadata file found under datasets/casq_external/nexar/metadata. Expected time_of_event and time_of_alert columns for positive cases.",
                )
            ],
            ["dataset", "status", "message", "source_path", "generated_at"],
        )
        append_progress("convert_nexar_to_casq", "python scripts/12_convert_nexar_to_casq.py", "missing local Nexar metadata; no conversion", "obtain approved small subset or metadata sample")
        print("Nexar conversion skipped: missing local metadata. No event boundaries invented.")
        return 0

    rows = []
    for path in present:
        for src in iter_rows(path):
            label = str(src.get("label", src.get("event_type", ""))).lower()
            time_event = src.get("time_of_event")
            time_alert = src.get("time_of_alert")
            if str(label) in {"0", "normal", "negative"} or time_event in ("", None) or time_alert in ("", None):
                continue
            start = float(time_alert)
            end = float(time_event)
            if end < start:
                continue
            video_id = src.get("video_id", src.get("id", src.get("video", "")))
            rows.append(
                {
                    "dataset": "nexar",
                    "video_id": video_id,
                    "event_id": src.get("event_id", f"nexar_{video_id}"),
                    "event_type": src.get("event_type", "collision_or_near_collision_precursor"),
                    "event_start": start,
                    "event_end": end,
                    "event_midpoint": (start + end) / 2.0,
                    "event_duration": end - start,
                    "involved_object": src.get("involved_object", "unknown"),
                    "ego_relevant": True,
                    "boundary_source": "official_time_of_alert_to_time_of_event_interval",
                    "boundary_confidence": "medium",
                    "label_source": src.get("label_source", "Nexar collision prediction metadata"),
                    "human_adjudicated": "unknown",
                    "original_label": src.get("event_type", src.get("label", "")),
                    "source_annotation_path": str(path),
                }
            )
    write_csv(OUT / "tables" / "nexar_casq_events_preview.csv", rows, EVENT_FIELDS)
    write_csv(
        status_path,
        [status_row("nexar", "CONVERTED_PREVIEW", f"Converted {len(rows)} precursor intervals from local metadata.", ";".join(str(p) for p in present))],
        ["dataset", "status", "message", "source_path", "generated_at"],
    )
    append_progress("convert_nexar_to_casq", "python scripts/12_convert_nexar_to_casq.py", f"converted {len(rows)} Nexar event previews", "validate converted preview before CASQ use")
    print(f"Nexar conversion preview rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

