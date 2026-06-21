#!/usr/bin/env python3
"""Shared utilities for roadclip_budget_v2."""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.yaml"
EXPECTED_OUTPUT_DIR = Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def load_config(path: Path) -> dict:
    if not path.is_file():
        fail(f"config not found: {path}")
    try:
        import yaml
    except ImportError:
        fail("missing dependency PyYAML")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def require_abs_path(cfg: dict, key: str, must_exist: bool = False, is_dir: bool | None = None) -> Path:
    value = cfg.get(key)
    if not value:
        fail(f"missing config key: {key}")
    path = Path(value)
    if not path.is_absolute():
        fail(f"config key {key} must be absolute: {value}")
    if must_exist:
        if is_dir is True and not path.is_dir():
            fail(f"required directory not found for {key}: {path}")
        if is_dir is False and not path.is_file():
            fail(f"required file not found for {key}: {path}")
        if is_dir is None and not path.exists():
            fail(f"required path not found for {key}: {path}")
    return path


def validate_base_paths(cfg: dict) -> None:
    require_abs_path(cfg, "project_root", True, True)
    require_abs_path(cfg, "workspace", True, True)
    require_abs_path(cfg, "video_dir", True, True)
    output_dir = require_abs_path(cfg, "output_dir", False, None)
    if output_dir != EXPECTED_OUTPUT_DIR and EXPECTED_OUTPUT_DIR not in output_dir.parents:
        fail(f"output_dir must be {EXPECTED_OUTPUT_DIR} or a subdirectory of it, got {output_dir}")


def ensure_output_dir(cfg: dict) -> Path:
    output_dir = require_abs_path(cfg, "output_dir", False, None)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path: Path, row: dict, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.is_file()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp01(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return max(0.0, min(1.0, value))


def fmt_float(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"


def fmt_ms(seconds: float) -> str:
    return f"{int(round(seconds * 1000)):09d}ms"


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ffprobe_json(path: Path) -> dict:
    result = run_cmd(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        fail(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def parse_rate(rate: str) -> float:
    if not rate or rate == "0/0":
        return 0.0
    if "/" in rate:
        num, den = rate.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    return float(rate)


def encoder_candidates() -> list[str]:
    result = run_cmd(["ffmpeg", "-hide_banner", "-encoders"])
    if result.returncode != 0:
        fail("ffmpeg is required but failed to list encoders")
    text = result.stdout + result.stderr
    encoders = [e for e in ["libx264", "libopenh264", "mpeg4"] if e in text]
    if not encoders:
        fail("no usable ffmpeg MP4 encoder found")
    return encoders


def cut_clip(video_path: Path, start_sec: float, duration_sec: float, out_path: Path, encoders: list[str]) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.is_file() and out_path.stat().st_size > 0:
        return "existing"
    last_error = ""
    for encoder in encoders:
        result = run_cmd(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start_sec:.3f}",
                "-i",
                str(video_path),
                "-t",
                f"{duration_sec:.3f}",
                "-c:v",
                encoder,
                "-an",
                "-loglevel",
                "error",
                str(out_path),
            ]
        )
        if result.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
            return encoder
        last_error = result.stderr.strip()
        if out_path.exists():
            out_path.unlink()
    fail(f"ffmpeg failed to cut {out_path}: {last_error}")


def write_blocked(output_dir: Path, name: str, title: str, lines: list[str]) -> Path:
    path = output_dir / name
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path
