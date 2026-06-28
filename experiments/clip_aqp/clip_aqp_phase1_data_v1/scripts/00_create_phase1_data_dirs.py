#!/usr/bin/env python3
"""Create CASQ Phase 1 output and external dataset directories."""

from pathlib import Path

from phase1_data_common import DATASET_DIRS, DATASET_ROOT, OUT, SUBDIRS, append_progress, ensure_dirs, write_csv


def main() -> int:
    ensure_dirs()
    rows = []
    for name in SUBDIRS:
        path = OUT / name
        rows.append({"kind": "output_subdir", "name": name, "path": str(path), "exists": path.exists()})
    for name in DATASET_DIRS:
        path = DATASET_ROOT / name
        rows.append({"kind": "dataset_subdir", "name": name, "path": str(path), "exists": path.exists()})
    write_csv(OUT / "data_manifest" / "phase1_directories.csv", rows, ["kind", "name", "path", "exists"])
    append_progress(
        "create_phase1_data_dirs",
        "python scripts/00_create_phase1_data_dirs.py",
        "created or verified Phase 1 output and dataset directories",
        "validate schemas and source availability",
    )
    print(f"Created/verified Phase 1 directories under {OUT} and {DATASET_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

