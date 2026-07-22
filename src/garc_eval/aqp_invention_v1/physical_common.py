"""Shared immutable paths, hashing, and atomic I/O for the physical pilot."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "AQP_Algorithm_Invention_Sprint_v1"
PHYSICAL = PACKAGE / "physical"
STRICT = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
VIDEO = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
IMPLEMENTATION = ROOT / "src/garc_eval/aqp_invention_v1"


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def atomic_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_freeze() -> dict[str, Any]:
    config_path = PHYSICAL / "FROZEN_PHYSICAL_CONFIG.json"
    lock_path = PHYSICAL / ".physical_freeze.lock"
    if not config_path.exists() or not lock_path.exists():
        raise RuntimeError("physical pilot has not been frozen")
    config = load_json(config_path)
    lock = load_json(lock_path)
    if sha256_file(config_path) != lock.get("frozen_config_sha256"):
        raise RuntimeError("frozen physical config hash mismatch")
    for relative, expected in config["frozen_artifact_hashes"].items():
        path = ROOT / relative
        if not path.exists() or sha256_file(path) != expected:
            raise RuntimeError(f"frozen artifact mismatch: {relative}")
    for relative, expected in config["frozen_source_hashes"].items():
        path = ROOT / relative
        if not path.exists() or sha256_file(path) != expected:
            raise RuntimeError(f"frozen source mismatch: {relative}")
    if sha256_file(VIDEO) != config["video"]["sha256"]:
        raise RuntimeError("video hash mismatch")
    return config
