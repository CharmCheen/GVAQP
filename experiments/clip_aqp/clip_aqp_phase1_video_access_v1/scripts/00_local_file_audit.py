#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

from video_access_common import DATASET_ROOT, MANIFEST_PATH, OUT, ROOT, VIDEO_EXTENSIONS, append_progress, ensure_dirs, load_manifest, smoke_subset, write_json


def iter_video_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)


def main() -> int:
    ensure_dirs()
    manifest = load_manifest()
    smoke = smoke_subset(manifest)
    manifest_names = set(manifest["video_id"].astype(str))

    nexar_files = iter_video_files(DATASET_ROOT)
    dataset_files = iter_video_files(ROOT / "datasets")
    rows = []
    for scope, files in [("nexar_root", nexar_files), ("datasets_root", dataset_files)]:
        for path in files:
            rows.append(
                {
                    "search_scope": scope,
                    "path": str(path),
                    "filename": path.name,
                    "matches_manifest": path.name in manifest_names,
                    "file_size": path.stat().st_size,
                }
            )
    local_df = pd.DataFrame(rows, columns=["search_scope", "path", "filename", "matches_manifest", "file_size"])
    local_df.to_csv(OUT / "manifests/local_video_file_search.csv", index=False)

    match_rows = []
    by_name = {row["filename"]: row for _, row in local_df[local_df["matches_manifest"]].iterrows()}
    for row in manifest.itertuples(index=False):
        match = by_name.get(str(row.video_id))
        match_rows.append(
            {
                "video_id": row.video_id,
                "label": row.label,
                "manifest_local_video_path": row.local_video_path,
                "matched_existing_path": "" if match is None else match["path"],
                "local_exists": bool(Path(str(row.local_video_path)).exists()) or match is not None,
                "needed_for_smoke_subset": row.video_id in set(smoke["video_id"].astype(str)),
            }
        )
    pd.DataFrame(match_rows).to_csv(OUT / "manifests/local_manifest_match.csv", index=False)

    write_json(
        OUT / "config/experiment_config.json",
        {
            "experiment": "clip_aqp_phase1_video_access_v1",
            "created_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
            "manifest_path": str(MANIFEST_PATH),
            "dataset_target_root": str(DATASET_ROOT),
            "search_roots": [str(DATASET_ROOT), str(ROOT / "datasets")],
            "download_cap": {"positive": 5, "normal": 5},
            "forbidden_actions": ["VLM", "GPU inference", "training", "full dataset download", "overwrite previous artifacts"],
        },
    )
    pd.DataFrame(
        [
            {"input_name": "nexar_200_manifest", "path": str(MANIFEST_PATH), "exists": MANIFEST_PATH.exists(), "rows": len(manifest), "columns": ";".join(manifest.columns)},
            {"input_name": "phase1_4_candidate_report", "path": str(ROOT / "test_vlm/outputs/clip_aqp_phase1_candidate_v1/reports/CANDIDATE_FEASIBILITY_REPORT.md"), "exists": (ROOT / "test_vlm/outputs/clip_aqp_phase1_candidate_v1/reports/CANDIDATE_FEASIBILITY_REPORT.md").exists(), "rows": "", "columns": ""},
        ]
    ).to_csv(OUT / "data_manifest/input_manifest.csv", index=False)

    append_progress("local_file_audit", "python scripts/00_local_file_audit.py", f"video_files_found={len(local_df)}, manifest_matches={int(local_df['matches_manifest'].sum()) if not local_df.empty else 0}", next_action="HF and Kaggle access audit")
    print(f"Local video files found: {len(local_df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

