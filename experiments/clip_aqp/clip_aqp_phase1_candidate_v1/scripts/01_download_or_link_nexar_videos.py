#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

from candidate_common import DATASET_ROOT, OUT, append_progress, gpu_info, write_json


def main() -> int:
    subset = pd.read_csv(OUT / "data_manifest/candidate_subset_smoke.csv")
    rows = []
    for row in subset.itertuples(index=False):
        local_path = Path(str(row.local_video_path))
        exists = local_path.exists()
        rows.append(
            {
                "video_id": row.video_id,
                "label": row.label,
                "local_video_path": str(local_path),
                "download_status": "linked_existing" if exists else "missing_no_download_url",
                "file_size": local_path.stat().st_size if exists else 0,
                "duration": "",
                "access_detail": "local path exists" if exists else "manifest points to missing local file and metadata has no remote URL",
            }
        )
    access = pd.DataFrame(rows)
    access.to_csv(OUT / "data_manifest/video_download_manifest.csv", index=False)
    access.to_csv(OUT / "tables/video_access_manifest.csv", index=False)

    summary = {
        "dataset_root": str(DATASET_ROOT),
        "subset_rows": len(access),
        "accessible_videos": int((access["download_status"] == "linked_existing").sum()),
        "missing_videos": int((access["download_status"] != "linked_existing").sum()),
        "manual_access_or_license_required": int((access["download_status"] != "linked_existing").sum()) > 0,
    }
    write_json(OUT / "data_manifest/video_access_summary.json", summary)
    write_json(OUT / "logs/gpu_hardware.json", gpu_info())
    append_progress("download_or_link", "python scripts/01_download_or_link_nexar_videos.py", f"accessible={summary['accessible_videos']}/{summary['subset_rows']}", failure="video access blocked" if summary["accessible_videos"] == 0 else "", next_action="frame extraction or blocked report")
    print(f"Accessible videos: {summary['accessible_videos']}/{summary['subset_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

