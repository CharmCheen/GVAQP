#!/usr/bin/env python3
"""Prepare a Nexar small-subset manifest without full dataset download."""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from nexar_small_common import (
    DATASET_ROOT,
    MANIFEST_FIELDS,
    OUT,
    README,
    append_progress,
    ensure_dirs,
    read_jsonish,
    to_float,
    truthy,
    write_csv,
    write_json,
)


METADATA_CANDIDATES = [
    DATASET_ROOT / "metadata" / "train_metadata.csv",
    DATASET_ROOT / "metadata" / "train_metadata.json",
    DATASET_ROOT / "metadata" / "metadata.csv",
    DATASET_ROOT / "metadata" / "metadata.json",
    DATASET_ROOT / "metadata" / "metadata.jsonl",
    DATASET_ROOT / "metadata" / "hf" / "train" / "positive" / "metadata.csv",
    DATASET_ROOT / "metadata" / "hf" / "train" / "negative" / "metadata.csv",
    DATASET_ROOT / "hf_metadata_probe" / "train" / "positive" / "metadata.csv",
    DATASET_ROOT / "hf_metadata_probe" / "train" / "negative" / "metadata.csv",
]
HF_METADATA_FILES = ["train/positive/metadata.csv", "train/negative/metadata.csv"]


def read_local_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    payload = read_jsonish(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = []
        for key, row in payload.items():
            if isinstance(row, dict):
                row = dict(row)
                row.setdefault("video_id", key)
                rows.append(row)
        return rows
    return []


def get_first(row: dict, names: list[str]):
    for name in names:
        if name in row and str(row[name]).strip() != "":
            return row[name]
    return ""


def infer_source_label(source: Path) -> str:
    parts = {part.lower() for part in source.parts}
    if "positive" in parts:
        return "positive"
    if "negative" in parts:
        return "normal"
    return ""


def infer_source_split(source: Path) -> str:
    for part in source.parts:
        if part.lower() in {"train", "test-public", "test-private", "validation", "val"}:
            return part
    return "train"


def normalize_row(row: dict, source: Path) -> dict:
    video_id = str(get_first(row, ["video_id", "id", "video", "filename", "file_name"])).strip()
    source_label = infer_source_label(source)
    label_raw = str(get_first(row, ["label", "target", "event_type", "type", "class"])).strip() or source_label
    event_moment = get_first(row, ["event_moment", "time_of_event", "event_time", "collision_time"])
    alert_time = get_first(row, ["alert_time", "time_of_alert", "toa", "warning_time"])
    original_start = get_first(row, ["event_start", "original_event_start", "start_time"])
    original_end = get_first(row, ["event_end", "original_event_end", "end_time"])
    split = str(get_first(row, ["split", "subset"])).strip() or infer_source_split(source)
    is_positive = truthy(label_raw) or to_float(event_moment) is not None or to_float(alert_time) is not None
    is_normal = not is_positive or label_raw.lower() in {"normal", "negative", "0", "false"}
    local_video_path = str(get_first(row, ["local_video_path", "video_path", "path"])).strip()
    if local_video_path and not Path(local_video_path).is_absolute():
        local_video_path = str(DATASET_ROOT / local_video_path)
    if not local_video_path and video_id:
        video_group = "positive" if is_positive else "negative"
        local_video_path = str(DATASET_ROOT / "raw" / split / video_group / video_id)
    return {
        "dataset": "nexar",
        "video_id": video_id,
        "split": split,
        "label": label_raw or ("positive" if is_positive else "normal"),
        "is_positive": is_positive,
        "is_normal": is_normal,
        "event_moment": event_moment,
        "alert_time": alert_time,
        "original_event_start": original_start,
        "original_event_end": original_end,
        "local_video_path": local_video_path,
        "local_metadata_path": str(source),
        "download_status": "metadata_available_video_not_downloaded",
        "notes": "selected from local/public metadata; expected video path recorded but video download not attempted",
    }


def select_small_subset(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        video_id = str(row.get("video_id", "")).strip()
        if not video_id:
            continue
        normalized.append(row)
    positives = [row for row in normalized if str(row.get("is_positive")).lower() == "true"][:25]
    normals = [row for row in normalized if str(row.get("is_normal")).lower() == "true"][:25]
    seen = set()
    selected = []
    for row in positives + normals:
        key = row["video_id"]
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected


def parse_readme_summary() -> dict:
    text = README.read_text(encoding="utf-8") if README.exists() else ""
    return {
        "readme_path": str(README),
        "readme_exists": README.exists(),
        "expected_metadata_files": [
            "metadata/train_metadata.csv",
            "metadata/train_metadata.json",
            "metadata/metadata.csv",
            "metadata/metadata.jsonl",
        ],
        "expected_annotation_fields": ["time_of_event", "time_of_alert", "label"],
        "original_event_start_end_exists_in_scaffold": bool(re.search(r"original event_start|event_start/event_end", text, re.I)),
        "event_moment_alert_time_expected": "time_of_event" in text and "time_of_alert" in text,
        "positive_identification": "positive collision/near-collision cases with event/alert time",
        "normal_identification": "normal-driving videos from metadata label when available",
    }


def probe_hf_access() -> dict:
    url = "https://huggingface.co/api/datasets/nexar-ai/nexar_collision_prediction"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "G-ARC-CASQ-small-subset-smoke"})
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
        siblings = data.get("siblings", [])
        return {
            "status": "reachable",
            "gated": data.get("gated", "unknown"),
            "private": data.get("private", "unknown"),
            "num_siblings": len(siblings),
            "small_metadata_candidates": [
                s.get("rfilename", "") for s in siblings if "metadata" in s.get("rfilename", "").lower()
            ][:25],
            "error": "",
        }
    except urllib.error.HTTPError as exc:
        return {"status": "http_error", "gated": "unknown", "private": "unknown", "num_siblings": 0, "small_metadata_candidates": [], "error": f"HTTP {exc.code}: {exc.reason}"}
    except Exception as exc:
        return {"status": "access_failed", "gated": "unknown", "private": "unknown", "num_siblings": 0, "small_metadata_candidates": [], "error": f"{type(exc).__name__}: {exc}"}


def download_public_hf_metadata(hf_status: dict) -> list[Path]:
    if hf_status.get("status") != "reachable" or hf_status.get("private") is True or hf_status.get("gated") is True:
        return []
    try:
        from huggingface_hub import hf_hub_download
    except Exception:
        return []
    downloaded = []
    for filename in HF_METADATA_FILES:
        if filename not in set(hf_status.get("small_metadata_candidates", [])):
            continue
        path = hf_hub_download(
            repo_id="nexar-ai/nexar_collision_prediction",
            repo_type="dataset",
            filename=filename,
            local_dir=str(DATASET_ROOT / "metadata" / "hf"),
        )
        downloaded.append(Path(path))
    return downloaded


def main() -> int:
    ensure_dirs()
    readme_summary = parse_readme_summary()
    local_sources = [path for path in METADATA_CANDIDATES if path.exists()]
    manifest_path = OUT / "download_manifest" / "nexar_small_manifest.csv"
    hf_status = None
    downloaded_sources = []
    if not local_sources:
        hf_status = probe_hf_access()
        downloaded_sources = download_public_hf_metadata(hf_status)
        local_sources = [path for path in downloaded_sources if path.exists()]

    if local_sources:
        rows = []
        for path in local_sources:
            rows.extend(normalize_row(row, path) for row in read_local_rows(path))
        selected = select_small_subset(rows)
        write_csv(manifest_path, selected, MANIFEST_FIELDS)
        status = {
            "decision": "LOCAL_METADATA_READY",
            "message": f"Prepared manifest from {len(local_sources)} metadata file(s); no videos downloaded.",
            "local_sources": [str(p) for p in local_sources],
            "downloaded_metadata_sources": [str(p) for p in downloaded_sources],
            "selected_rows": len(selected),
            "readme_summary": readme_summary,
            "hf_access_probe": hf_status,
        }
        write_json(OUT / "tables" / "nexar_small_access_status.json", status)
        append_progress("prepare_nexar_small_subset", "python scripts/00_prepare_nexar_small_subset.py", status["message"], "convert manifest to CASQ")
        print(status["message"])
        return 0

    placeholder = [
        {
            "dataset": "nexar",
            "video_id": "",
            "split": "",
            "label": "",
            "is_positive": "",
            "is_normal": "",
            "event_moment": "",
            "alert_time": "",
            "original_event_start": "",
            "original_event_end": "",
            "local_video_path": "",
            "local_metadata_path": "",
            "download_status": "NEED_MANUAL_DATASET_ACCESS",
            "notes": "No local metadata found. Full dataset download was not attempted. Hugging Face/API access status: "
            + hf_status["status"]
            + ("; " + hf_status["error"] if hf_status.get("error") else ""),
        }
    ]
    write_csv(manifest_path, placeholder, MANIFEST_FIELDS)
    status = {
        "decision": "NEED_MANUAL_DATASET_ACCESS",
        "message": "No local Nexar metadata found; access/download requires manual dataset access or a metadata file placed under datasets/casq_external/nexar/metadata.",
        "local_sources": [],
        "selected_rows": 0,
        "readme_summary": readme_summary,
        "hf_access_probe": hf_status,
        "hf_token_present": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")),
    }
    write_json(OUT / "tables" / "nexar_small_access_status.json", status)
    append_progress(
        "prepare_nexar_small_subset",
        "python scripts/00_prepare_nexar_small_subset.py",
        "manual dataset access needed; wrote placeholder manifest",
        "obtain approved Nexar metadata subset before conversion",
        failure=hf_status.get("error", "no local metadata"),
    )
    print(status["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
