#!/usr/bin/env python3
"""Verify the V1 three-video freeze and materialize its deterministic unit grid."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
VIDEO_MANIFEST = OUT / "video_manifests/frozen_videos_v1.json"
CONFIG = OUT / "configs/stage1_freeze_v1.json"
GRID = OUT / "video_manifests/frozen_unit_grid_v1.csv"
AUDIT = OUT / "video_manifests/freeze_audit_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def ffprobe(path: Path) -> dict:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of", "json", str(path),
    ], text=True)
    return json.loads(raw)


def write_or_verify(path: Path, payload: str) -> str:
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite nonmatching frozen artifact: {path}")
        return "VERIFIED_EXISTING"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(payload)
    return "CREATED"


def main() -> None:
    manifest = json.loads(VIDEO_MANIFEST.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    window = float(config["unit_grid"]["window_seconds"])
    stride = float(config["unit_grid"]["stride_seconds"])
    if window != stride or window <= 0:
        raise RuntimeError("V1 requires a positive non-overlapping grid")

    rows = []
    checks = []
    for video in manifest["videos"]:
        path = ROOT / video["path"]
        observed_hash = sha256_file(path)
        probe = ffprobe(path)
        duration = float(probe["format"]["duration"])
        size = int(probe["format"]["size"])
        units = int(math.ceil(duration / stride))
        passed = (
            observed_hash == video["sha256"]
            and size == int(video["size_bytes"])
            and abs(duration - float(video["duration_seconds"])) <= 1e-6
            and units == int(video["expected_units"])
        )
        checks.append({
            "video_id": video["video_id"],
            "path": video["path"],
            "sha256": observed_hash,
            "duration_seconds": duration,
            "size_bytes": size,
            "unit_count": units,
            "status": "PASS" if passed else "FAIL",
        })
        if not passed:
            raise RuntimeError(f"video freeze mismatch: {video['video_id']}")
        for unit_id in range(units):
            start = unit_id * stride
            end = min(duration, start + window)
            rows.append({
                "video_id": video["video_id"],
                "unit_id": unit_id,
                "candidate_id": f"{video['video_id']}_u{unit_id:04d}",
                "start_time": f"{start:.6f}",
                "end_time": f"{end:.6f}",
                "duration_seconds": f"{end - start:.6f}",
            })

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=[
        "video_id", "unit_id", "candidate_id", "start_time", "end_time", "duration_seconds",
    ], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    grid_payload = stream.getvalue()
    write_or_verify(GRID, grid_payload)

    audit = {
        "status": "PASS",
        "video_checks": checks,
        "total_units": len(rows),
        "expected_total_units": manifest["total_expected_units"],
        "grid_sha256": hashlib.sha256(grid_payload.encode()).hexdigest(),
        "config_sha256": sha256_file(CONFIG),
        "prompt_sha256": sha256_file(ROOT / config["query"]["prompt_path"]),
        "video_manifest_sha256": sha256_file(VIDEO_MANIFEST),
        "freeze_script_sha256": sha256_file(Path(__file__)),
        "content_identity_sha256": canonical_hash({
            "checks": checks,
            "config_sha256": sha256_file(CONFIG),
            "grid_sha256": hashlib.sha256(grid_payload.encode()).hexdigest(),
        }),
    }
    if len(rows) != int(manifest["total_expected_units"]):
        raise RuntimeError("total unit count mismatch")
    audit_payload = json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    write_or_verify(AUDIT, audit_payload)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
