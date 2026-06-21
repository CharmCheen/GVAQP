#!/usr/bin/env python3
"""Build the Nexar-200 derived-boundary manifest from local metadata only."""

from __future__ import annotations

import pandas as pd

from nexar_200_common import (
    DATASET_ROOT,
    MANIFEST_FIELDS,
    NEG_META,
    OUT,
    POS_META,
    append_progress,
    ensure_dirs,
    to_float,
    write_csv,
    write_json,
)


def build_positive_rows(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    rows = []
    skipped = []
    for _, row in df.iterrows():
        event_moment = to_float(row.get("time_of_event"))
        alert_time = to_float(row.get("time_of_alert"))
        video_id = str(row.get("file_name", "")).strip()
        if not video_id or event_moment is None or alert_time is None:
            skipped.append({"video_id": video_id, "reason": "missing event_moment or alert_time"})
            continue
        if alert_time >= event_moment:
            skipped.append({"video_id": video_id, "reason": "alert_time >= event_moment"})
            continue
        rows.append(
            {
                "dataset": "nexar",
                "video_id": video_id,
                "split": "train",
                "label": "positive",
                "is_positive": True,
                "is_normal": False,
                "event_moment": event_moment,
                "alert_time": alert_time,
                "original_event_start": "",
                "original_event_end": "",
                "derived_event_start": alert_time,
                "derived_event_end": event_moment,
                "boundary_source": "derived_from_alert_time_to_event_moment",
                "boundary_confidence": "medium",
                "local_video_path": str(DATASET_ROOT / "raw" / "train" / "positive" / video_id),
                "local_metadata_path": str(POS_META),
                "notes": "metadata-only row; derived interval is not original human event_start/event_end",
            }
        )
        if len(rows) >= 200:
            break
    return rows, skipped


def build_normal_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        video_id = str(row.get("file_name", "")).strip()
        if not video_id:
            continue
        rows.append(
            {
                "dataset": "nexar",
                "video_id": video_id,
                "split": "train",
                "label": "normal",
                "is_positive": False,
                "is_normal": True,
                "event_moment": "",
                "alert_time": "",
                "original_event_start": "",
                "original_event_end": "",
                "derived_event_start": "",
                "derived_event_end": "",
                "boundary_source": "",
                "boundary_confidence": "",
                "local_video_path": str(DATASET_ROOT / "raw" / "train" / "negative" / video_id),
                "local_metadata_path": str(NEG_META),
                "notes": "metadata-only normal row; video not downloaded",
            }
        )
        if len(rows) >= 200:
            break
    return rows


def main() -> int:
    ensure_dirs()
    if not POS_META.exists() or not NEG_META.exists():
        write_csv(OUT / "manifests" / "nexar_200_manifest.csv", [], MANIFEST_FIELDS)
        write_json(
            OUT / "tables" / "nexar_200_metadata_status.json",
            {
                "decision": "NEED_METADATA_ACCESS",
                "positive_metadata_exists": POS_META.exists(),
                "negative_metadata_exists": NEG_META.exists(),
            },
        )
        append_progress("build_manifest", "python scripts/00_build_nexar_200_manifest.py", "metadata access missing", "obtain local Nexar metadata", failure="metadata missing")
        print("NEXAR_200_DECISION: NEED_METADATA_ACCESS")
        return 0

    pos_df = pd.read_csv(POS_META)
    neg_df = pd.read_csv(NEG_META)
    positives, skipped = build_positive_rows(pos_df)
    normals = build_normal_rows(neg_df)
    rows = positives + normals
    write_csv(OUT / "manifests" / "nexar_200_manifest.csv", rows, MANIFEST_FIELDS)
    write_csv(OUT / "tables" / "nexar_200_manifest_skipped_positive_rows.csv", skipped, ["video_id", "reason"])
    status = {
        "decision": "LOCAL_METADATA_READY" if len(positives) >= 200 and len(normals) >= 200 else "NEED_METADATA_ACCESS",
        "positive_metadata_rows": int(len(pos_df)),
        "negative_metadata_rows": int(len(neg_df)),
        "selected_positive_rows": len(positives),
        "selected_normal_rows": len(normals),
        "positive_metadata_path": str(POS_META),
        "negative_metadata_path": str(NEG_META),
        "videos_downloaded": False,
    }
    write_json(OUT / "tables" / "nexar_200_metadata_status.json", status)
    append_progress("build_manifest", "python scripts/00_build_nexar_200_manifest.py", f"selected positives={len(positives)} normals={len(normals)}", "convert manifest to CASQ")
    print(f"Built manifest rows={len(rows)} positives={len(positives)} normals={len(normals)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

