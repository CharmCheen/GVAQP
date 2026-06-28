"""Shared utilities for the Nexar-200 derived-boundary CASQ benchmark."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm" / "outputs" / "clip_aqp_phase1_nexar_200_v1"
DATASET_ROOT = ROOT / "datasets" / "casq_external" / "nexar"
POS_META = DATASET_ROOT / "hf_metadata_probe" / "train" / "positive" / "metadata.csv"
NEG_META = DATASET_ROOT / "hf_metadata_probe" / "train" / "negative" / "metadata.csv"

SUBDIRS = ["scripts", "reports", "tables", "figures", "logs", "converted", "manifests", "config"]
UNIT_SECONDS = [5, 10, 15]
HASH_SEED = "nexar_200_derived_v1"

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
    "derived_event_start",
    "derived_event_end",
    "boundary_source",
    "boundary_confidence",
    "local_video_path",
    "local_metadata_path",
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


def ensure_dirs() -> None:
    for name in SUBDIRS:
        (OUT / name).mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_progress(checkpoint: str, command: str, result: str, next_action: str, failure: str = "", fix: str = "") -> None:
    ensure_dirs()
    with (OUT / "logs" / "progress.md").open("a", encoding="utf-8") as f:
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
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def to_float(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None
    return float(text)


def stable_score(text: str, seed: str = HASH_SEED) -> float:
    digest = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16 - 1)


def interval_iou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return inter / union if union > 0 else 0.0


def overlaps(a0: float, a1: float, b0: float, b1: float) -> bool:
    return max(a0, b0) < min(a1, b1)


def stitch_intervals(rows: list[dict], gap: float = 1e-9) -> list[dict]:
    clips = []
    by_video: dict[str, list[dict]] = {}
    for row in rows:
        by_video.setdefault(row["video_id"], []).append(row)
    for video_id, video_rows in by_video.items():
        cur = None
        for row in sorted(video_rows, key=lambda x: (float(x["start_time"]), float(x["end_time"]))):
            start = float(row["start_time"])
            end = float(row["end_time"])
            if cur is None or start - cur["end_time"] > gap:
                if cur is not None:
                    clips.append(cur)
                cur = {"video_id": video_id, "start_time": start, "end_time": end}
            else:
                cur["end_time"] = max(cur["end_time"], end)
        if cur is not None:
            clips.append(cur)
    return clips


def event_hit(event: dict, clips: list[dict], theta: float) -> bool:
    ev_start = float(event["event_start"])
    ev_end = float(event["event_end"])
    for clip in clips:
        if clip["video_id"] != event["video_id"]:
            continue
        if interval_iou(ev_start, ev_end, float(clip["start_time"]), float(clip["end_time"])) >= theta:
            return True
    return False


def normal_quantile(confidence: float) -> float:
    # Fixed one-sided z values used by the configured deltas.
    if confidence >= 0.95:
        return 1.6448536269514722
    if confidence >= 0.90:
        return 1.2815515655446004
    return 1.2815515655446004


def finite_population_total_bounds(values: list[float], population_n: int, delta: float, lower: bool) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    mean = statistics.fmean(values)
    if n == 1 or population_n <= 1:
        se_mean = 0.0
    else:
        s2 = statistics.variance(values) if n > 1 else 0.0
        fpc = max(0.0, 1.0 - n / population_n)
        se_mean = math.sqrt(fpc * s2 / n)
    z = normal_quantile(1.0 - delta)
    estimate = population_n * mean
    margin = z * population_n * se_mean
    if lower:
        return max(0.0, estimate - margin)
    return max(0.0, estimate + margin)

