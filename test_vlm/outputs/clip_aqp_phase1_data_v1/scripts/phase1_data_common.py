"""Shared helpers for CASQ Phase 1 data ingestion scaffolding."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm" / "outputs" / "clip_aqp_phase1_data_v1"
DATASET_ROOT = ROOT / "datasets" / "casq_external"

SUBDIRS = ["config", "data_manifest", "scripts", "logs", "tables", "figures", "reports", "schema"]
DATASET_DIRS = ["dota", "dada2000", "nexar", "micro_casq_v0"]

EVENT_FIELDS = [
    "dataset",
    "video_id",
    "event_id",
    "event_type",
    "event_start",
    "event_end",
    "event_midpoint",
    "event_duration",
    "involved_object",
    "ego_relevant",
    "boundary_source",
    "boundary_confidence",
    "label_source",
    "human_adjudicated",
    "original_label",
    "source_annotation_path",
]

UNIT_FIELDS = [
    "dataset",
    "video_id",
    "unit_id",
    "start_time",
    "end_time",
    "duration",
    "split",
    "has_event_overlap",
    "matched_event_ids",
    "source_video_path",
    "source_annotation_path",
]

MICRO_TEMPLATE_FIELDS = [
    "dataset",
    "video_id",
    "event_id",
    "event_type",
    "event_start",
    "event_end",
    "involved_object",
    "ego_relevant",
    "boundary_confidence",
    "label_source",
    "human_adjudicated",
    "positive_reason",
    "negative_near_miss_reason",
    "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for name in SUBDIRS:
        (OUT / name).mkdir(parents=True, exist_ok=True)
    for name in DATASET_DIRS:
        (DATASET_ROOT / name).mkdir(parents=True, exist_ok=True)


def append_progress(checkpoint: str, command: str, result: str, next_action: str, failure: str = "", fix: str = "") -> None:
    ensure_dirs()
    path = OUT / "logs" / "progress.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(
            f"- time: {utc_now()}\n"
            f"  checkpoint: {checkpoint}\n"
            f"  command: `{command}`\n"
            f"  result: {result}\n"
            f"  failure: {failure or 'none'}\n"
            f"  fix_applied: {fix or 'none'}\n"
            f"  next_action: {next_action}\n"
        )


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def file_info(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else "",
    }


def git_status_subset(paths: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", "status", "--short", "--", *paths],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return proc.stdout.strip()
    except Exception as exc:  # pragma: no cover - diagnostic only
        return f"git status failed: {exc}"


def status_row(dataset: str, status: str, message: str, source_path: str = "") -> dict:
    return {
        "dataset": dataset,
        "status": status,
        "message": message,
        "source_path": source_path,
        "generated_at": utc_now(),
    }

