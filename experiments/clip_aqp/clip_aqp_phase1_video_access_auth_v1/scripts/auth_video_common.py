#!/usr/bin/env python3
"""Shared helpers for authenticated Nexar video access smoke test."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1"
DATASET_ROOT = ROOT / "datasets/casq_external/nexar"
PREV_ACCESS_OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_video_access_v1"
PREV_PLAN = PREV_ACCESS_OUT / "manifests/nexar_video_access_plan.csv"
PREV_DOWNLOADS = PREV_ACCESS_OUT / "manifests/downloaded_smoke_videos.csv"
NEXAR_MANIFEST = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/manifests/nexar_200_manifest.csv"
PHASE14_REPORT = ROOT / "test_vlm/outputs/clip_aqp_phase1_candidate_v1/reports/CANDIDATE_FEASIBILITY_REPORT.md"
PREV_REPORT = PREV_ACCESS_OUT / "reports/NEXAR_VIDEO_ACCESS_REPORT.md"
HF_REPO_ID = "nexar-ai/nexar_collision_prediction"

SMOKE_COLUMNS = [
    "video_id",
    "filename",
    "label",
    "is_positive",
    "is_normal",
    "hf_path",
    "local_target_path",
    "previous_status",
    "auth_download_status",
    "file_size_bytes",
    "duration_seconds",
    "readable",
    "notes",
]


def ensure_dirs() -> None:
    for rel in ["scripts", "reports", "logs", "manifests", "downloaded", "checks", "config", "data_manifest"]:
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


def redact(text: str) -> str:
    return re.sub(r"(hf_[A-Za-z0-9_\-]+|token\s*[:=]\s*\S+|api[_-]?key\s*[:=]\s*\S+)", "[REDACTED]", text, flags=re.IGNORECASE)


def run_cmd(args: list[str], timeout: int = 30) -> dict:
    env = os.environ.copy()
    for key in list(env):
        if "TOKEN" in key.upper() or "HF_" in key.upper() and "HOME" not in key.upper():
            env[key] = "[REDACTED]"
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "command": " ".join(args),
            "returncode": proc.returncode,
            "stdout": redact(proc.stdout.strip()),
            "stderr": redact(proc.stderr.strip()),
        }
    except FileNotFoundError as exc:
        return {"command": " ".join(args), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired:
        return {"command": " ".join(args), "returncode": 124, "stdout": "", "stderr": "timeout"}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows)
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in view.columns) + " |")
    return "\n".join(lines)


def verify_video(path: Path) -> dict:
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    duration = ""
    readable = False
    frame_read_ok = False
    if exists and size > 0:
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
        try:
            import cv2

            cap = cv2.VideoCapture(str(path))
            ok, _frame = cap.read()
            if ok:
                frame_read_ok = True
                readable = True
                if not duration:
                    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
                    if fps > 0 and frames > 0:
                        duration = f"{frames / fps:.6f}"
            cap.release()
        except Exception:
            pass
    return {
        "file_exists": exists,
        "file_size_bytes": size,
        "duration_seconds": duration,
        "readable": readable,
        "frame_read_ok": frame_read_ok,
    }


def auth_status() -> dict:
    hf_cli = run_cmd(["bash", "-lc", "command -v hf"], timeout=10)
    old_cli = run_cmd(["bash", "-lc", "command -v huggingface-cli"], timeout=10)
    if not hf_cli["stdout"] and not old_cli["stdout"]:
        return {
            "auth_status": "cli_missing",
            "hf_cli_available": False,
            "huggingface_cli_available": False,
            "whoami_returncode": "",
            "whoami_user": "",
            "whoami_message": "HF CLI missing",
        }
    who = run_cmd(["hf", "auth", "whoami"], timeout=20) if hf_cli["stdout"] else run_cmd(["huggingface-cli", "whoami"], timeout=20)
    out = "\n".join(x for x in [who["stdout"], who["stderr"]] if x)
    if who["returncode"] == 0 and "not logged in" not in out.lower():
        user = out.splitlines()[0] if out.splitlines() else "authenticated"
        status = "authenticated"
    elif "not logged in" in out.lower() or who["returncode"] != 0:
        user = ""
        status = "not_authenticated"
    else:
        user = ""
        status = "unknown"
    return {
        "auth_status": status,
        "hf_cli_available": bool(hf_cli["stdout"]),
        "huggingface_cli_available": bool(old_cli["stdout"]),
        "whoami_returncode": who["returncode"],
        "whoami_user": user,
        "whoami_message": out,
    }

