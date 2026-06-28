#!/usr/bin/env python3
"""Shared utilities for the kinematic proxy MVP."""

import csv
import math
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.yaml"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def load_config(config_path: Path) -> dict:
    if not config_path.is_file():
        fail(f"config not found: {config_path}")
    try:
        import yaml
    except ImportError:
        fail("missing dependency PyYAML. Install with: pip install pyyaml")
    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def path_from_cfg(cfg: dict, key: str, must_exist: bool = False, is_dir: bool | None = None) -> Path:
    value = cfg.get(key)
    if not value:
        fail(f"missing required config key: {key}")
    path = Path(value)
    if not path.is_absolute():
        fail(f"config key {key} must be an absolute path: {value}")
    if must_exist:
        if is_dir is True and not path.is_dir():
            fail(f"required directory not found for {key}: {path}")
        if is_dir is False and not path.is_file():
            fail(f"required file not found for {key}: {path}")
        if is_dir is None and not path.exists():
            fail(f"required path not found for {key}: {path}")
    return path


def validate_base_paths(cfg: dict, need_video: bool = False, need_model: bool = False) -> None:
    path_from_cfg(cfg, "project_root", must_exist=True, is_dir=True)
    path_from_cfg(cfg, "workspace", must_exist=True, is_dir=True)
    if need_video:
        path_from_cfg(cfg, "input_video", must_exist=True, is_dir=False)
    if need_model:
        path_from_cfg(cfg, "yolo_model", must_exist=True, is_dir=False)
    output_dir = path_from_cfg(cfg, "output_dir", must_exist=False)
    expected = Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy")
    if output_dir != expected:
        fail(f"output_dir must be exactly {expected}, got: {output_dir}")


def ensure_output_dir(cfg: dict) -> Path:
    output_dir = path_from_cfg(cfg, "output_dir", must_exist=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"required input CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def format_float(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"
