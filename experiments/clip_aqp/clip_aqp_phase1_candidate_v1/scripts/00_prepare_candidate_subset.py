#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from candidate_common import (
    FORBIDDEN_GENERATION_FIELDS,
    MANIFEST_PATH,
    OUT,
    append_progress,
    ensure_dirs,
    write_experiment_config,
    write_input_manifest,
    write_schema_mapping,
)


def main() -> int:
    ensure_dirs()
    write_experiment_config()
    write_schema_mapping()
    write_input_manifest()

    manifest = pd.read_csv(MANIFEST_PATH)
    positive = manifest[manifest["is_positive"].astype(bool)].head(50).copy()
    normal = manifest[manifest["is_normal"].astype(bool)].head(50).copy()
    subset = pd.concat([positive, normal], ignore_index=True)

    generation_safe_cols = [
        "dataset",
        "video_id",
        "split",
        "label",
        "is_positive",
        "is_normal",
        "local_video_path",
        "local_metadata_path",
        "notes",
    ]
    subset[generation_safe_cols].to_csv(OUT / "data_manifest/candidate_subset_smoke.csv", index=False)

    leakage_checks = []
    used_for_selection = {"is_positive", "is_normal", "label", "video_id"}
    leakage_checks.append(
        {
            "check": "forbidden_time_fields_not_used_for_candidate_generation",
            "passed": not bool(used_for_selection & FORBIDDEN_GENERATION_FIELDS),
            "detail": "subset selection used label balance only; event timing fields excluded from generation-safe subset",
        }
    )
    leakage_checks.append({"check": "smoke_subset_50_positive_50_normal", "passed": len(positive) == 50 and len(normal) == 50, "detail": f"positive={len(positive)}, normal={len(normal)}"})
    leakage_checks.append({"check": "manifest_has_200_positive_200_normal", "passed": int(manifest["is_positive"].astype(bool).sum()) == 200 and int(manifest["is_normal"].astype(bool).sum()) == 200, "detail": f"rows={len(manifest)}"})
    pd.DataFrame(leakage_checks).to_csv(OUT / "tables/leakage_and_subset_checks.csv", index=False)

    append_progress("prepare_subset", "python scripts/00_prepare_candidate_subset.py", f"smoke_subset_rows={len(subset)}", next_action="download/link video files")
    print(f"Wrote smoke subset rows={len(subset)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

