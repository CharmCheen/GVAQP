"""Generate the label-independent burned-timestamp processor test corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT
    / "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/tests/metadata_videos"
)
WIDTH, HEIGHT = 256, 144
BARCODE_BITS = 16
BARCODE_X, BARCODE_Y, BARCODE_STEP, BARCODE_SIZE = 8, 8, 14, 11


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _frame(frame_index: int, fps: float, total_frames: int) -> np.ndarray:
    timestamp = frame_index / fps
    value = int((frame_index * 17) % 90) + 40
    image = np.full((HEIGHT, WIDTH, 3), (value, value // 2, 120), dtype=np.uint8)
    # A robust binary frame-index barcode lets tests verify identity without
    # relying on OCR.  Human-readable absolute time/index are burned below it.
    for bit in range(BARCODE_BITS):
        white = (frame_index >> bit) & 1
        color = (245, 245, 245) if white else (5, 5, 5)
        x0 = BARCODE_X + bit * BARCODE_STEP
        cv2.rectangle(
            image,
            (x0, BARCODE_Y),
            (x0 + BARCODE_SIZE - 1, BARCODE_Y + BARCODE_SIZE - 1),
            color,
            thickness=-1,
        )
    cv2.putText(
        image,
        f"ABS={timestamp:06.2f}s FRAME={frame_index:04d} FPS={fps:g}",
        (8, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    marker = None
    if frame_index == 0:
        marker = ("BEGIN", (20, 20, 230))
    elif frame_index == (total_frames - 1) // 2:
        marker = ("MIDDLE", (20, 220, 20))
    elif frame_index == total_frames - 1:
        marker = ("END", (230, 80, 20))
    if marker:
        label, color = marker
        cv2.rectangle(image, (20, 78), (236, 132), color, thickness=-1)
        cv2.putText(
            image,
            label,
            (62, 116),
            cv2.FONT_HERSHEY_DUPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return image


def write_video(path: Path, fps: float, total_frames: int) -> None:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (WIDTH, HEIGHT)
    )
    if not writer.isOpened():
        raise RuntimeError(f"cannot create metadata video: {path}")
    for frame_index in range(total_frames):
        writer.write(_frame(frame_index, fps, total_frames))
    writer.release()


def generate() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = [
        {
            "file": "timeline_60s_10fps.mp4",
            "fps": 10.0,
            "total_frames": 601,
            "intervals": [
                {"id": "len_10", "start": 0.0, "end": 10.0},
                {"id": "len_50", "start": 5.0, "end": 55.0},
                {"id": "len_55", "start": 0.0, "end": 55.0},
                {"id": "len_60", "start": 0.0, "end": 60.0},
                {"id": "nonzero_10", "start": 12.3, "end": 22.3},
            ],
        },
        {
            "file": "timeline_73p4s_10fps.mp4",
            "fps": 10.0,
            "total_frames": 734,
            "intervals": [
                {"id": "nonzero_60", "start": 10.0, "end": 70.0},
                {"id": "final_partial", "start": 70.0, "end": 73.4},
                {"id": "odd_count", "start": 1.0, "end": 4.0},
            ],
        },
        {
            "file": "timeline_10s_12fps.mp4",
            "fps": 12.0,
            "total_frames": 121,
            "intervals": [
                {"id": "alternate_fps", "start": 0.0, "end": 10.0},
            ],
        },
    ]
    manifest_videos = []
    for spec in specs:
        path = OUTPUT / spec["file"]
        write_video(path, spec["fps"], spec["total_frames"])
        cap = cv2.VideoCapture(str(path))
        observed = {
            "fps": float(cap.get(cv2.CAP_PROP_FPS)),
            "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
        cap.release()
        if observed["total_frames"] != spec["total_frames"]:
            raise RuntimeError(f"encoded frame count changed for {path}")
        if abs(observed["fps"] - spec["fps"]) > 1e-9:
            raise RuntimeError(f"encoded FPS changed for {path}")
        manifest_videos.append(
            {
                **spec,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "container_duration_seconds": observed["total_frames"]
                / observed["fps"],
                "last_frame_timestamp_seconds": (observed["total_frames"] - 1)
                / observed["fps"],
                "width": observed["width"],
                "height": observed["height"],
                "marker_frame_indices": {
                    "begin": 0,
                    "middle": (observed["total_frames"] - 1) // 2,
                    "end": observed["total_frames"] - 1,
                },
            }
        )
    manifest = {
        "corpus_version": "event_enumerate_v2_metadata_corpus_v1",
        "semantic_event_labels_present": False,
        "purpose": "temporal transport, frame identity, marker, and boundary tests only",
        "barcode": {
            "encoding": "little-endian binary frame index",
            "bits": BARCODE_BITS,
            "x": BARCODE_X,
            "y": BARCODE_Y,
            "step": BARCODE_STEP,
            "square_size": BARCODE_SIZE,
            "decode_threshold": 128,
        },
        "videos": manifest_videos,
    }
    (OUTPUT / "CORPUS_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    generate()


if __name__ == "__main__":
    main()
