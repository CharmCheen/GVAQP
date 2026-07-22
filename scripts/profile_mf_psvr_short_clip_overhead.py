#!/usr/bin/env python3
"""CPU-only profile of per-video open/close and per-unit tracker-reset overhead."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
POOL = CYCLE / "TRAINING_POOL_MANIFEST.csv"
UNIT_MANIFEST = CYCLE / "candidates/UNIT_MANIFEST.csv"
PROXY_SOURCE = ROOT / "scripts/run_psvr_two_video_proxy.py"
OUT = CYCLE / "SHORT_CLIP_OVERHEAD_PROFILE.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def summary(values: list[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=float)
    return {
        "count": len(values),
        "sum_seconds": float(array.sum()),
        "mean_seconds": float(array.mean()),
        "p50_seconds": float(np.quantile(array, 0.50)),
        "p95_seconds": float(np.quantile(array, 0.95)),
        "maximum_seconds": float(array.max()),
    }


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_proxy_module():
    spec = importlib.util.spec_from_file_location("mf_overhead_proxy", PROXY_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen proxy implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    pool = pd.read_csv(POOL, keep_default_na=False)
    pool = pool[
        (pool["source_dataset"] == "nexar_collision_prediction")
        & (pool["pool_status"] == "ELIGIBLE_PENDING_CANDIDATE_EXTRACTION")
    ].sort_values("session_id")
    units = pd.read_csv(UNIT_MANIFEST, keep_default_na=False)
    if len(pool) != 603 or len(units) != 2654:
        raise RuntimeError("Short-clip profile input count mismatch")

    open_seconds = []
    for row in pool.to_dict("records"):
        started = time.perf_counter_ns()
        capture = cv2.VideoCapture(str(ROOT / row["local_locator"]))
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open {row['session_id']}")
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        capture.release()
        open_seconds.append((time.perf_counter_ns() - started) / 1e9)
        if frame_count != int(row["frame_or_image_count"]) or abs(fps - float(row["fps"])) > 1e-6:
            raise RuntimeError(f"Media metadata changed during overhead profile: {row['session_id']}")

    proxy = load_proxy_module()
    tracker_seconds = []
    for _ in range(len(units)):
        started = time.perf_counter_ns()
        proxy.make_tracker()
        tracker_seconds.append((time.perf_counter_ns() - started) / 1e9)

    value = {
        "profile_id": "MF_PSVR_SHORT_CLIP_CPU_OVERHEAD_V1",
        "profiled_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "CPU-only VideoCapture open/metadata/close and fresh ByteTrack construction",
        "semantic_frames_inspected": 0,
        "detector_loaded": False,
        "gpu_inference": False,
        "pool_manifest_sha256": sha256_file(POOL),
        "unit_manifest_sha256": sha256_file(UNIT_MANIFEST),
        "proxy_source_sha256": sha256_file(PROXY_SOURCE),
        "video_open_close": summary(open_seconds),
        "tracker_reset": summary(tracker_seconds),
        "p95_product_envelope_seconds": (
            len(open_seconds) * float(np.quantile(open_seconds, 0.95))
            + len(tracker_seconds) * float(np.quantile(tracker_seconds, 0.95))
        ),
        "observed_sum_seconds": sum(open_seconds) + sum(tracker_seconds),
        "residual_limitation": (
            "This isolates structural CPU overhead; concurrent detector/decode interactions are "
            "measured only by the authorized full extraction."
        ),
        "heldout_opened": False,
    }
    atomic_json(OUT, value)
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
