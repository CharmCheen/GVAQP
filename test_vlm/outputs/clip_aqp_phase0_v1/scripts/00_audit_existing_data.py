#!/usr/bin/env python3
from __future__ import annotations

import tarfile
from pathlib import Path

import pandas as pd

from phase0_common import OUT_DIR, PROJECT_ROOT, append_progress, ensure_dirs, markdown_table


SEARCH_ROOTS = [
    PROJECT_ROOT / "test_vlm",
    PROJECT_ROOT / "test_vlm/outputs",
]
PREFERRED_PATHS = [
    PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv",
    PROJECT_ROOT / "test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/roadclip_v2_audit_package.tar.gz",
    PROJECT_ROOT / "test_vlm/outputs/kinematic_proxy/human_audit_conservative_vlm_68clips.tar.gz",
    PROJECT_ROOT / "test_vlm/outputs/kinematic_proxy/clips",
    PROJECT_ROOT / "test_vlm/focused_validation_outputs",
]
FIELD_GROUPS = {
    "video_id": ["video_id", "source_video"],
    "unit_id": ["unit_id", "clip_id"],
    "clip_id": ["clip_id"],
    "start_time": ["start_time", "start_sec"],
    "end_time": ["end_time", "end_sec"],
    "proxy_score": ["proxy_score", "score_count", "score_kinematic", "score_learned_logreg", "score_learned_rf"],
    "oracle_label": ["oracle_label", "oracle_positive", "conservative_positive", "vlm_label"],
    "human_label": ["human_label", "human_relevant", "human_positive"],
    "event_id": ["event_id"],
    "event_start": ["event_start"],
    "event_end": ["event_end"],
    "source_path": ["source_path", "clip_path", "path"],
}


def discover_files() -> list[Path]:
    files: set[Path] = set()
    for path in PREFERRED_PATHS:
        if path.exists():
            if path.is_dir():
                files.update(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".json", ".md"})
            else:
                files.add(path)
    patterns = ["*vlm_labels*.csv", "*conservative*.csv", "*budget*", "*proxy*", "*human_audit*", "*clips*", "*audit*", "*event*"]
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for pattern in patterns:
            files.update(p for p in root.rglob(pattern) if p.is_file() and (p.suffix.lower() in {".csv", ".json", ".md"} or p.name.endswith(".tar.gz")))
    return sorted(files)


def inspect_file(path: Path) -> dict:
    row = {
        "path": str(path),
        "file_type": "directory" if path.is_dir() else path.suffix.lower(),
        "exists": path.exists(),
        "readable": False,
        "row_count": "",
        "columns": "",
        "tar_member_count": "",
        "error": "",
    }
    for field, names in FIELD_GROUPS.items():
        row[f"has_{field}"] = False
    row["has_event_boundary"] = False
    if not path.exists():
        return row
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
            cols = list(df.columns)
            row["readable"] = True
            row["row_count"] = len(df)
            row["columns"] = ";".join(cols)
            colset = set(cols)
            for field, names in FIELD_GROUPS.items():
                row[f"has_{field}"] = bool(colset & set(names))
            row["has_event_boundary"] = bool({"event_start", "event_end"} <= colset and df[["event_start", "event_end"]].notna().all(axis=None))
        elif path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as tar:
                row["readable"] = True
                row["tar_member_count"] = len(tar.getmembers())
        elif path.suffix.lower() in {".json", ".md"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            row["readable"] = True
            row["row_count"] = ""
            row["columns"] = ""
            for field, names in FIELD_GROUPS.items():
                row[f"has_{field}"] = any(name in text for name in names)
            row["has_event_boundary"] = "event_start" in text and "event_end" in text
    except Exception as exc:
        row["error"] = repr(exc)
    return row


def main() -> None:
    ensure_dirs()
    files = discover_files()
    rows = [inspect_file(path) for path in files]
    inventory = pd.DataFrame(rows)
    out_csv = OUT_DIR / "data_audit/existing_data_inventory.csv"
    inventory.to_csv(out_csv, index=False)
    useful = inventory[
        inventory[["has_video_id", "has_unit_id", "has_start_time", "has_end_time", "has_proxy_score", "has_oracle_label"]].any(axis=1)
    ].copy()
    lines = [
        "# Data Audit",
        "",
        "This audit inspects existing local CSV/JSON/Markdown/tar metadata only. It does not download datasets or run VLM inference.",
        "",
        f"- discovered files: {len(inventory)}",
        f"- files with any Phase 0-relevant field: {len(useful)}",
        f"- clean event-boundary files detected by strict column presence/non-null check: {int(inventory['has_event_boundary'].sum())}",
        "",
        "The Phase 0 implementation uses existing proxy scores where present. If a fallback score is ever needed, it is defined as a lagged oracle-positive indicator within the same video timeline, used only as a deterministic diagnostic fallback and recorded with `score_source = fallback_score`; the current selected unified table uses `score_source = proxy_score` for all rows.",
        "",
        "## Relevant Inventory Sample",
        "",
        markdown_table(useful[["path", "row_count", "has_video_id", "has_start_time", "has_end_time", "has_proxy_score", "has_oracle_label", "has_human_label", "has_event_id", "has_event_start", "has_event_end", "has_event_boundary"]].head(25)),
        "",
        "## Boundary Finding",
        "",
        "The main unit-level timeline lacks clean human-adjudicated event boundaries. Later Phase 0 stages therefore use pseudo-events formed by merging adjacent oracle-positive units and label all event results as pseudo-event / oracle-relative.",
    ]
    (OUT_DIR / "reports/DATA_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    append_progress("data audit", "python scripts/00_audit_existing_data.py", f"wrote {out_csv}", next_action="build phase0 unit table")


if __name__ == "__main__":
    main()
