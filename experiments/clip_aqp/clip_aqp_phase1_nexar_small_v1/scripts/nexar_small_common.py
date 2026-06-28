"""Shared helpers for the Nexar CASQ small-subset smoke ingestion."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
PHASE1_DATA = ROOT / "test_vlm" / "outputs" / "clip_aqp_phase1_data_v1"
OUT = ROOT / "test_vlm" / "outputs" / "clip_aqp_phase1_nexar_small_v1"
DATASET_ROOT = ROOT / "datasets" / "casq_external" / "nexar"
README = DATASET_ROOT / "README_CASQ_MAPPING.md"

SUBDIRS = ["scripts", "reports", "tables", "logs", "figures", "download_manifest", "converted", "config"]

MANIFEST_FIELDS = [
    "dataset",
    "video_id",
    "split",
    "label",
    "is_positive",
    "is_normal",
    "event_moment",
    "alert_time",
    "original_event_start",
    "original_event_end",
    "local_video_path",
    "local_metadata_path",
    "download_status",
    "notes",
]

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


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for name in SUBDIRS:
        (OUT / name).mkdir(parents=True, exist_ok=True)
    (DATASET_ROOT / "metadata").mkdir(parents=True, exist_ok=True)
    (DATASET_ROOT / "raw").mkdir(parents=True, exist_ok=True)


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


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def read_jsonish(path: Path):
    with path.open("r", encoding="utf-8") as f:
        if path.suffix.lower() == ".jsonl":
            return [json.loads(line) for line in f if line.strip()]
        return json.load(f)


def to_float(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None
    return float(text)


def truthy(value) -> bool:
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "positive", "collision", "near_collision", "event"}


def git_status(paths: list[str]) -> str:
    proc = subprocess.run(
        ["git", "status", "--short", "--", *paths],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.stdout.strip()


def file_exists_if_nonempty(path_text: str) -> bool:
    if not path_text:
        return False
    return Path(path_text).exists()

