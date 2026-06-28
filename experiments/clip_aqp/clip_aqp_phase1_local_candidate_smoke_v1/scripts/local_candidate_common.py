#!/usr/bin/env python3
"""Shared utilities for local-video candidate generator smoke test."""

from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_local_candidate_smoke_v1"
YOLO_N = ROOT / "models/yolo/yolov8n.pt"
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}

KIN_CLIPS = ROOT / "test_vlm/outputs/kinematic_proxy/clips.csv"
KIN_PROXY = ROOT / "test_vlm/outputs/kinematic_proxy/proxy_scores.csv"
KIN_LABELS = ROOT / "test_vlm/outputs/kinematic_proxy/vlm_labels_conservative_exact_102.csv"
KIN_HUMAN = ROOT / "test_vlm/outputs/kinematic_proxy/human_audit_conservative_vlm_68clips/audit_manifest.csv"

CANDIDATE_COLUMNS = [
    "candidate_name",
    "video_id",
    "returned_clip_id",
    "start_time",
    "end_time",
    "score",
    "rank",
    "generation_rule",
    "uses_oracle_annotation",
    "uses_video_content",
    "model_name",
    "runtime_seconds",
    "notes",
]


def ensure_dirs() -> None:
    for rel in ["scripts", "reports", "tables", "figures", "logs", "frames", "features", "candidates", "config", "data_manifest"]:
        (OUT / rel).mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_progress(checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    with (OUT / "logs/progress.md").open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {utc_now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{command}`",
                    f"- result: {result}",
                    f"- failure if any: {failure or 'none'}",
                    f"- fix applied: {fix or 'none'}",
                    f"- next action: {next_action or 'none'}",
                    "",
                ]
            )
        )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_cmd(args: list[str], timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def video_meta(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    readable = bool(cap.isOpened())
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    num_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = float(num_frames / fps) if fps > 0 and num_frames > 0 else 0.0
    if readable:
        ok, _ = cap.read()
        readable = bool(ok)
    cap.release()
    return {
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "duration_seconds": duration,
        "readable": readable,
        "width": width,
        "height": height,
        "fps": fps,
        "num_frames": num_frames,
    }


def source_category(path: Path) -> str:
    text = str(path)
    if "roadclip_budget_v2" in text:
        return "roadclip_budget_v2_clip"
    if "kinematic_proxy" in text:
        return "kinematic_proxy_clip"
    if "focused_validation_outputs" in text:
        return "focused_validation_clip"
    if "try_or_no/videos" in text:
        return "full_local_video"
    if "clips/" in text:
        return "local_clip"
    if "nexar/videos_smoke" in text:
        return "nexar_smoke_video"
    return "other_video"


def parse_clip_times_from_name(path: str) -> tuple[float | None, float | None]:
    match = re.search(r"_s(\d{6,})(?:ms)?_e(\d{6,})(?:ms)?", path)
    if not match:
        return None, None
    s = match.group(1)
    e = match.group(2)
    scale = 1000.0 if len(s) > 6 or "ms" in path else 1.0
    return float(int(s)) / scale, float(int(e)) / scale


def markdown_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows)
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in view.columns:
            value = row[col]
            if isinstance(value, float):
                vals.append(f"{value:.4g}" if math.isfinite(value) else "")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def load_smoke_units() -> pd.DataFrame:
    return pd.read_csv(OUT / "tables/local_smoke_units.csv")


def label_col(df: pd.DataFrame) -> str:
    if "human_label" in df.columns and df["human_label"].notna().any():
        return "human_label"
    return "oracle_label"


def positive_series(df: pd.DataFrame) -> pd.Series:
    col = label_col(df)
    return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)


def candidate_df(name: str, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if not df.empty:
        df = df.sort_values(["score", "video_id", "start_time"], ascending=[False, True, True]).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
    return df

