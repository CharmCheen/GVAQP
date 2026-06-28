#!/usr/bin/env python3
from __future__ import annotations

import importlib.util

import pandas as pd

from candidate_common import CANDIDATE_COLUMNS, OUT, append_progress, empty_csv


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    frame_index = pd.read_csv(OUT / "tables/frame_index.csv")
    has_frames = not frame_index.empty
    generators = [
        ("fixed_sliding_window", "available_metadata_only_but_not_run_without_video_access"),
        ("motion_energy", "available" if module_available("cv2") else "missing_dependency_cv2"),
        ("yolo_count_proxy", "available" if module_available("ultralytics") else "missing_dependency_ultralytics"),
        ("clip_or_siglip_text_score", "available" if module_available("transformers") or module_available("open_clip") else "missing_dependency_clip_or_siglip"),
        ("optional_small_vlm_score", "missing_dependency_or_not_configured"),
    ]
    status_rows = []
    for name, dep_status in generators:
        empty_csv(OUT / "candidates" / f"{name}.csv", CANDIDATE_COLUMNS)
        if not has_frames:
            status = "skipped_no_video_access"
        elif dep_status.startswith("missing"):
            status = dep_status
        else:
            status = "not_run_in_access_blocked_path"
        status_rows.append(
            {
                "candidate_name": name,
                "status": status,
                "dependency_status": dep_status,
                "uses_oracle_annotation": False,
                "uses_video_content": name != "fixed_sliding_window",
                "notes": "No candidate windows generated because no Nexar video files were accessible." if not has_frames else "",
            }
        )
    pd.DataFrame(status_rows).to_csv(OUT / "tables/candidate_generation_status.csv", index=False)
    append_progress("generate_candidates", "python scripts/20_generate_candidates.py", "skipped_no_video_access" if not has_frames else "completed", failure="no frames available" if not has_frames else "", next_action="candidate evaluation")
    print("Candidate generation status written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

