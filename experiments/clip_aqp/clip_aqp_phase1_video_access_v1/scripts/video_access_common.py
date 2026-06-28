#!/usr/bin/env python3
"""Shared utilities for Nexar video access audit.

This stage resolves video access only. It does not run VLMs, GPU inference,
training, or candidate generation.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_video_access_v1"
DATASET_ROOT = ROOT / "datasets/casq_external/nexar"
VIDEOS_SMOKE = DATASET_ROOT / "videos_smoke"
MANIFEST_PATH = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/manifests/nexar_200_manifest.csv"
PHASE14_REPORT = ROOT / "test_vlm/outputs/clip_aqp_phase1_candidate_v1/reports/CANDIDATE_FEASIBILITY_REPORT.md"
HF_REPO_ID = "nexar-ai/nexar_collision_prediction"

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
PLAN_COLUMNS = [
    "video_id",
    "filename",
    "label",
    "needed_for_smoke_subset",
    "expected_remote_source",
    "local_target_path",
    "access_status",
    "required_action",
    "notes",
]


def ensure_dirs() -> None:
    for rel in ["scripts", "reports", "logs", "manifests", "config", "data_manifest", "tables"]:
        (OUT / rel).mkdir(parents=True, exist_ok=True)
    VIDEOS_SMOKE.mkdir(parents=True, exist_ok=True)


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


def markdown_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows)
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in view.columns) + " |")
    return "\n".join(lines)


def run_cmd(args: list[str], timeout: int = 30) -> dict:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "command": " ".join(args),
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except FileNotFoundError as exc:
        return {"command": " ".join(args), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {"command": " ".join(args), "returncode": 124, "stdout": (exc.stdout or "").strip(), "stderr": "timeout"}


def load_manifest() -> pd.DataFrame:
    return pd.read_csv(MANIFEST_PATH)


def smoke_subset(manifest: pd.DataFrame) -> pd.DataFrame:
    pos = manifest[manifest["is_positive"].astype(bool)].head(50)
    neg = manifest[manifest["is_normal"].astype(bool)].head(50)
    return pd.concat([pos, neg], ignore_index=True)


def ten_video_subset(manifest: pd.DataFrame) -> pd.DataFrame:
    pos = manifest[manifest["is_positive"].astype(bool)].head(5)
    neg = manifest[manifest["is_normal"].astype(bool)].head(5)
    return pd.concat([pos, neg], ignore_index=True)


def local_target_for(label: str, filename: str) -> Path:
    return VIDEOS_SMOKE / str(label) / filename


def verify_video(path: Path) -> dict:
    size = path.stat().st_size if path.exists() else 0
    duration = ""
    readable = False
    ffprobe = run_cmd(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=20,
    )
    if ffprobe["returncode"] == 0 and ffprobe["stdout"]:
        duration = ffprobe["stdout"].splitlines()[0]
        readable = True
    else:
        try:
            import cv2

            cap = cv2.VideoCapture(str(path))
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
                if fps > 0 and frames > 0:
                    duration = f"{frames / fps:.6f}"
                    readable = True
            cap.release()
        except Exception:
            readable = False
    return {"file_exists": path.exists(), "file_size": size, "duration": duration, "readable": readable}

