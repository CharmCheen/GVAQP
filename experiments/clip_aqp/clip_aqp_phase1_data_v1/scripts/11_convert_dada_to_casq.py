#!/usr/bin/env python3
"""Conservative DADA-2000/LOTVS-DADA conversion scaffold."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from phase1_data_common import DATASET_ROOT, EVENT_FIELDS, OUT, append_progress, status_row, write_csv


def iter_annotation_rows(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)
    elif path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
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
    base = DATASET_ROOT / "dada2000"
    candidates = [
        base / "annotations" / "casq_event_boundaries.csv",
        base / "annotations" / "accident_intervals.csv",
        base / "annotations" / "accident_intervals.json",
    ]
    present = [path for path in candidates if path.exists()]
    status_path = OUT / "tables" / "dada_conversion_status.csv"
    if not present:
        write_csv(
            status_path,
            [
                status_row(
                    "dada2000",
                    "MISSING_INPUT",
                    "No local DADA-2000 accident interval annotation file found. Public repo split files list sequence IDs but do not expose per-video event_start/event_end locally.",
                )
            ],
            ["dataset", "status", "message", "source_path", "generated_at"],
        )
        append_progress("convert_dada_to_casq", "python scripts/11_convert_dada_to_casq.py", "missing local DADA accident interval annotations; no conversion", "obtain approved small subset with accident windows")
        print("DADA conversion skipped: missing local interval annotations. No event boundaries invented.")
        return 0

    rows = []
    for path in present:
        for src in iter_annotation_rows(path):
            if not {"video_id", "event_start", "event_end"} <= set(src):
                continue
            if src.get("event_start") in ("", None) or src.get("event_end") in ("", None):
                continue
            start = float(src["event_start"])
            end = float(src["event_end"])
            rows.append(
                {
                    "dataset": "dada2000",
                    "video_id": src["video_id"],
                    "event_id": src.get("event_id", f"dada2000_{src['video_id']}"),
                    "event_type": src.get("event_type", src.get("accident_category", "driving_accident")),
                    "event_start": start,
                    "event_end": end,
                    "event_midpoint": (start + end) / 2.0,
                    "event_duration": end - start,
                    "involved_object": src.get("involved_object", "unknown"),
                    "ego_relevant": src.get("ego_relevant", "unknown"),
                    "boundary_source": src.get("boundary_source", "local_DADA_accident_interval_annotation"),
                    "boundary_confidence": src.get("boundary_confidence", "medium"),
                    "label_source": src.get("label_source", "DADA-2000 annotation"),
                    "human_adjudicated": src.get("human_adjudicated", "unknown"),
                    "original_label": src.get("original_label", src.get("accident_category", "")),
                    "source_annotation_path": str(path),
                }
            )
    write_csv(OUT / "tables" / "dada_casq_events_preview.csv", rows, EVENT_FIELDS)
    write_csv(
        status_path,
        [status_row("dada2000", "CONVERTED_PREVIEW", f"Converted {len(rows)} events from local interval annotations.", ";".join(str(p) for p in present))],
        ["dataset", "status", "message", "source_path", "generated_at"],
    )
    append_progress("convert_dada_to_casq", "python scripts/11_convert_dada_to_casq.py", f"converted {len(rows)} DADA event previews", "validate converted preview before CASQ use")
    print(f"DADA conversion preview rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

