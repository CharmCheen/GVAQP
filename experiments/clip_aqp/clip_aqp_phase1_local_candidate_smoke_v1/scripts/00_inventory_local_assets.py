#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from local_candidate_common import OUT, ROOT, append_progress, ensure_dirs, source_category, video_meta, write_json


KEY_COLUMNS = {
    "clip_id",
    "start_time",
    "end_time",
    "source_clip_path",
    "archive_clip_path",
    "conservative_positive",
    "label_conservative_positive",
    "old_vlm_relevant",
    "human_label",
    "human_label_conservative_positive",
    "proxy_score",
    "score_count",
    "score_kinematic",
    "score_naive",
}


def main() -> int:
    ensure_dirs()
    video_rows = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".mp4", ".mov", ".avi", ".mkv"}:
            continue
        meta = video_meta(path)
        video_rows.append(
            {
                "video_path": str(path),
                "filename": path.name,
                **meta,
                "source_category": source_category(path),
                "notes": "local media inventory; metadata read via OpenCV",
            }
        )
    pd.DataFrame(video_rows).to_csv(OUT / "tables/local_video_inventory.csv", index=False)

    label_rows = []
    for path in sorted((ROOT / "test_vlm/outputs").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".json", ".md"}:
            continue
        cols: list[str] = []
        row_count = ""
        notes = ""
        try:
            if path.suffix.lower() == ".csv":
                df = pd.read_csv(path, nrows=5000)
                cols = list(df.columns)
                row_count = len(pd.read_csv(path, usecols=[cols[0]])) if cols else len(df)
            elif path.suffix.lower() == ".json":
                payload = json.loads(path.read_text(errors="ignore"))
                if isinstance(payload, dict):
                    cols = list(payload.keys())
                    row_count = 1
                elif isinstance(payload, list):
                    row_count = len(payload)
                    cols = sorted({k for row in payload[:20] if isinstance(row, dict) for k in row})
            else:
                text = path.read_text(errors="ignore")
                cols = [col for col in KEY_COLUMNS if col in text]
                row_count = ""
                notes = "markdown scanned for key strings"
        except Exception as exc:
            notes = f"read_error: {type(exc).__name__}: {exc}"
        lower_cols = {c.lower() for c in cols}
        has_key = bool(lower_cols & {c.lower() for c in KEY_COLUMNS})
        if has_key or notes:
            label_rows.append(
                {
                    "file_path": str(path),
                    "row_count": row_count,
                    "columns": ";".join(cols),
                    "has_clip_id": "clip_id" in lower_cols,
                    "has_start_end": "start_time" in lower_cols and "end_time" in lower_cols,
                    "has_video_path": bool(lower_cols & {"source_clip_path", "archive_clip_path", "clip_path", "video_path"}),
                    "has_oracle_label": bool(lower_cols & {"conservative_positive", "label_conservative_positive", "old_vlm_relevant"}),
                    "has_human_label": bool(lower_cols & {"human_label", "human_label_conservative_positive"}),
                    "has_proxy_score": bool(lower_cols & {"proxy_score", "score_count", "score_kinematic", "score_naive"}),
                    "notes": notes or "schema/key inventory",
                }
            )
    pd.DataFrame(label_rows).to_csv(OUT / "tables/local_label_inventory.csv", index=False)
    write_json(
        OUT / "config/experiment_config.json",
        {
            "experiment": "clip_aqp_phase1_local_candidate_smoke_v1",
            "created_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
            "no_external_model_hub": True,
            "no_download": True,
            "no_vlm": True,
            "no_training": True,
            "debugging_only": True,
        },
    )
    append_progress("inventory", "python scripts/00_inventory_local_assets.py", f"videos={len(video_rows)}, label_files={len(label_rows)}", next_action="build smoke dataset")
    print(f"videos={len(video_rows)} label_files={len(label_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
