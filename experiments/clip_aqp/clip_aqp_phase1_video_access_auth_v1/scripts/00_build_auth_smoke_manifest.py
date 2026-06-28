#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

from auth_video_common import (
    NEXAR_MANIFEST,
    OUT,
    PHASE14_REPORT,
    PREV_DOWNLOADS,
    PREV_PLAN,
    PREV_REPORT,
    SMOKE_COLUMNS,
    append_progress,
    auth_status,
    ensure_dirs,
    verify_video,
    write_json,
)


def main() -> int:
    ensure_dirs()
    auth = auth_status()
    write_json(OUT / "manifests/hf_auth_status.json", auth)
    write_json(
        OUT / "config/experiment_config.json",
        {
            "experiment": "clip_aqp_phase1_video_access_auth_v1",
            "previous_plan": str(PREV_PLAN),
            "previous_downloads": str(PREV_DOWNLOADS),
            "nexar_manifest": str(NEXAR_MANIFEST),
            "download_cap_total_videos": 10,
            "max_positive": 5,
            "max_normal": 5,
            "forbidden_actions": ["full dataset download", "VLM", "training", "candidate generation", "GPU inference", "token logging"],
        },
    )
    pd.DataFrame(
        [
            {"input_name": "previous_video_access_report", "path": str(PREV_REPORT), "exists": PREV_REPORT.exists()},
            {"input_name": "previous_video_access_plan", "path": str(PREV_PLAN), "exists": PREV_PLAN.exists()},
            {"input_name": "nexar_200_manifest", "path": str(NEXAR_MANIFEST), "exists": NEXAR_MANIFEST.exists()},
            {"input_name": "candidate_feasibility_report", "path": str(PHASE14_REPORT), "exists": PHASE14_REPORT.exists()},
        ]
    ).to_csv(OUT / "data_manifest/input_manifest.csv", index=False)

    prev_plan = pd.read_csv(PREV_PLAN)
    prev_downloads = pd.read_csv(PREV_DOWNLOADS) if PREV_DOWNLOADS.exists() else pd.DataFrame()
    nexar_manifest = pd.read_csv(NEXAR_MANIFEST)
    manifest_by_video = {row.video_id: row for row in nexar_manifest.itertuples(index=False)}
    prev_download_by_video = {row.video_id: row for row in prev_downloads.itertuples(index=False)} if not prev_downloads.empty else {}

    pos = prev_plan[(prev_plan["label"] == "positive") & (prev_plan["expected_remote_source"].astype(str).str.len() > 0)].head(5)
    neg = prev_plan[(prev_plan["label"] == "negative") & (prev_plan["expected_remote_source"].astype(str).str.len() > 0)].head(5)
    selected = pd.concat([pos, neg], ignore_index=True).head(10)

    rows = []
    for row in selected.itertuples(index=False):
        manifest_row = manifest_by_video[str(row.video_id)]
        prev = prev_download_by_video.get(str(row.video_id))
        prev_path = Path(str(getattr(prev, "local_target_path", ""))) if prev is not None else None
        use_existing = False
        local_target = OUT / "downloaded" / str(row.label) / str(row.filename)
        if prev_path is not None and prev_path.exists():
            verified = verify_video(prev_path)
            if verified["readable"]:
                local_target = prev_path
                use_existing = True
        else:
            verified = verify_video(local_target)
        previous_status = getattr(prev, "download_status", row.access_status) if prev is not None else row.access_status
        rows.append(
            {
                "video_id": row.video_id,
                "filename": row.filename,
                "label": row.label,
                "is_positive": bool(manifest_row.is_positive),
                "is_normal": bool(manifest_row.is_normal),
                "hf_path": row.expected_remote_source,
                "local_target_path": str(local_target),
                "previous_status": previous_status,
                "auth_download_status": "already_readable" if use_existing else "pending_auth_download",
                "file_size_bytes": verified["file_size_bytes"],
                "duration_seconds": verified["duration_seconds"],
                "readable": verified["readable"],
                "notes": "included existing readable prior smoke video" if use_existing else "selected from previous HF-mapped smoke plan",
            }
        )
    smoke = pd.DataFrame(rows, columns=SMOKE_COLUMNS)
    smoke.to_csv(OUT / "manifests/nexar_auth_smoke_manifest.csv", index=False)
    append_progress("build_auth_smoke_manifest", "python scripts/00_build_auth_smoke_manifest.py", f"auth_status={auth['auth_status']}, rows={len(smoke)}", next_action="download missing videos only if authenticated")
    print(f"auth_status={auth['auth_status']} smoke_rows={len(smoke)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

