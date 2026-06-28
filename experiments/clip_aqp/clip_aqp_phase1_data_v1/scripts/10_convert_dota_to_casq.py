#!/usr/bin/env python3
"""Conservative DoTA-to-CASQ conversion scaffold.

DoTA metadata uses temporal anomaly boundaries. This script only writes CASQ
events when local metadata is present and a frame-rate conversion is explicit.
It never fabricates second-based boundaries from frame indices.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from phase1_data_common import DATASET_ROOT, EVENT_FIELDS, OUT, append_progress, read_json, status_row, write_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fps", type=float, default=None, help="Explicit fps for converting DoTA frame indices to seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = DATASET_ROOT / "dota"
    candidates = [base / "annotations" / "metadata_train.json", base / "annotations" / "metadata_val.json"]
    present = [path for path in candidates if path.exists()]
    status_path = OUT / "tables" / "dota_conversion_status.csv"

    if not present:
        write_csv(
            status_path,
            [status_row("dota", "MISSING_INPUT", "No local DoTA metadata_train.json or metadata_val.json found under datasets/casq_external/dota/annotations.")],
            ["dataset", "status", "message", "source_path", "generated_at"],
        )
        append_progress("convert_dota_to_casq", "python scripts/10_convert_dota_to_casq.py", "missing local DoTA annotations; no conversion", "obtain small approved DoTA metadata/video subset")
        print("DoTA conversion skipped: missing local annotations. No event boundaries invented.")
        return 0

    if args.fps is None or args.fps <= 0:
        write_csv(
            status_path,
            [
                status_row(
                    "dota",
                    "MISSING_EXPLICIT_FPS",
                    "DoTA metadata exists, but event_start/event_end in CASQ seconds require an explicit --fps; no conversion performed.",
                    ";".join(str(p) for p in present),
                )
            ],
            ["dataset", "status", "message", "source_path", "generated_at"],
        )
        append_progress("convert_dota_to_casq", "python scripts/10_convert_dota_to_casq.py", "metadata present but fps absent; no conversion", "rerun with explicit fps after verifying metadata units")
        print("DoTA conversion skipped: explicit --fps required. No event boundaries invented.")
        return 0

    rows = []
    for path in present:
        data = read_json(path)
        for video_id, meta in data.items():
            if "anomaly_start" not in meta or "anomaly_end" not in meta:
                continue
            start = float(meta["anomaly_start"]) / args.fps
            end = float(meta["anomaly_end"]) / args.fps
            rows.append(
                {
                    "dataset": "dota",
                    "video_id": video_id,
                    "event_id": f"dota_{video_id}",
                    "event_type": str(meta.get("anomaly_class", "traffic_anomaly")),
                    "event_start": start,
                    "event_end": end,
                    "event_midpoint": (start + end) / 2.0,
                    "event_duration": end - start,
                    "involved_object": "unknown",
                    "ego_relevant": "unknown",
                    "boundary_source": "official_DoTA_anomaly_frame_indices_converted_with_explicit_fps",
                    "boundary_confidence": "medium",
                    "label_source": "DoTA metadata",
                    "human_adjudicated": "unknown",
                    "original_label": str(meta.get("anomaly_class", "")),
                    "source_annotation_path": str(path),
                }
            )
    write_csv(OUT / "tables" / "dota_casq_events_preview.csv", rows, EVENT_FIELDS)
    write_csv(
        status_path,
        [status_row("dota", "CONVERTED_PREVIEW", f"Converted {len(rows)} events with explicit fps={args.fps}.", ";".join(str(p) for p in present))],
        ["dataset", "status", "message", "source_path", "generated_at"],
    )
    append_progress("convert_dota_to_casq", f"python scripts/10_convert_dota_to_casq.py --fps {args.fps}", f"converted {len(rows)} DoTA event previews", "validate converted preview before using for CASQ")
    print(f"DoTA conversion preview rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

