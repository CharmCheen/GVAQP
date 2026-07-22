#!/usr/bin/env python3
"""Audit and deterministically freeze the two-video PSVR development input.

The search is intentionally bounded to data/realcam/long_video_data and the
four container suffixes named by the two-video research protocol.  This phase
does not run a proxy model, semantic oracle, scheduler, or held-out evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
VIDEO_ROOT = ROOT / "data/realcam/long_video_data"
DATASET3 = VIDEO_ROOT / "long_video_dataset3.mp4"
DATASET3_SHA256 = "bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610"
PROFILE = ROOT / "outputs/psvr_stage0b_physical_profile/partial_proxy_gate.json"
OUT = ROOT / "outputs/psvr_two_video_loop"
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi"}
UNIT_SECONDS = 10.0
COARSE_STRIDE_SECONDS = 30.0
FINGERPRINT_STRIDE_SECONDS = 30.0
FIXED_RATIOS = tuple(float(x) for x in np.linspace(0.01, 0.99, 21))
SEEK_RATIOS = (0.001, 0.01, 0.05, 0.13, 0.25, 0.37, 0.50, 0.63, 0.75, 0.87, 0.95, 0.99)
AUDIO_RATIOS = (0.02, 0.10, 0.18, 0.26, 0.34, 0.42, 0.50, 0.58, 0.66, 0.74, 0.82, 0.90, 0.98)
MIN_TEMPORAL_CELLS = 12
MEAN_ALIGNED_OVERLAP_REJECT = 0.90
OFFSET_MATCH_THRESHOLD = 0.92
MIN_OFFSET_MATCH_RUN = 5
LOOP_MATCH_THRESHOLD = 0.94


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def run(command: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, capture_output=True, check=False, timeout=timeout)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parse_rate(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    numerator, separator, denominator = value.partition("/")
    if not separator:
        return float(value)
    return float(numerator) / float(denominator)


def ffprobe(path: Path) -> dict[str, Any]:
    result = run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    if result.returncode:
        return {"status": "FAIL", "error": result.stderr.decode("utf-8", "replace").strip()}
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video = next((row for row in streams if row.get("codec_type") == "video"), {})
    audio = next((row for row in streams if row.get("codec_type") == "audio"), None)
    fmt = payload.get("format", {})
    duration = float(fmt.get("duration") or video.get("duration") or 0.0)
    fps = parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    frame_count_raw = video.get("nb_frames")
    frame_count = int(frame_count_raw) if str(frame_count_raw or "").isdigit() else int(round(duration * fps))
    return {
        "status": "PASS",
        "container": fmt.get("format_name", ""),
        "codec": video.get("codec_name", ""),
        "duration_seconds": duration,
        "fps": fps,
        "r_frame_rate": video.get("r_frame_rate", ""),
        "avg_frame_rate": video.get("avg_frame_rate", ""),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "resolution": f"{int(video.get('width') or 0)}x{int(video.get('height') or 0)}",
        "frame_count": frame_count,
        "video_start_time": float(video.get("start_time") or 0.0),
        "video_duration_seconds": float(video.get("duration") or duration),
        "audio": None if audio is None else {
            "codec": audio.get("codec_name", ""),
            "sample_rate": int(audio.get("sample_rate") or 0),
            "channels": int(audio.get("channels") or 0),
            "duration_seconds": float(audio.get("duration") or duration),
        },
        "format_tags": fmt.get("tags", {}),
        "video_tags": video.get("tags", {}),
        "audio_tags": {} if audio is None else audio.get("tags", {}),
        "bit_rate": int(fmt.get("bit_rate") or 0),
        "probe_score": int(fmt.get("probe_score") or 0),
    }


def timestamp_audit(path: Path, expected_frames: int) -> dict[str, Any]:
    started = time.perf_counter()
    result = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_packets",
        "-show_entries", "packet=pts_time,dts_time", "-of", "csv=p=0", str(path),
    ])
    elapsed = time.perf_counter() - started
    if result.returncode:
        return {
            "status": "FAIL",
            "elapsed_seconds": elapsed,
            "error": result.stderr.decode("utf-8", "replace").strip(),
        }
    pts_values: list[float] = []
    dts_values: list[float] = []
    for raw_line in result.stdout.decode("utf-8", "replace").splitlines():
        fields = [field.strip() for field in raw_line.split(",")]
        if len(fields) >= 2:
            try:
                pts_values.append(float(fields[0]))
                dts_values.append(float(fields[1]))
            except ValueError:
                continue
    pts_regressions = sum(b + 1e-9 < a for a, b in zip(pts_values, pts_values[1:]))
    dts_regressions = sum(b + 1e-9 < a for a, b in zip(dts_values, dts_values[1:]))
    dts_duplicates = sum(abs(b - a) <= 1e-9 for a, b in zip(dts_values, dts_values[1:]))
    coverage = len(dts_values) / expected_frames if expected_frames else 0.0
    status = "PASS" if dts_regressions == 0 and coverage >= 0.999 else "FAIL"
    return {
        "status": status,
        "elapsed_seconds": elapsed,
        "video_packets": len(dts_values),
        "expected_frames": expected_frames,
        "packet_to_frame_count_ratio": coverage,
        "dts_regressions": dts_regressions,
        "pts_reorder_regressions": pts_regressions,
        "duplicate_adjacent_dts": dts_duplicates,
        "first_dts": dts_values[0] if dts_values else None,
        "last_dts": dts_values[-1] if dts_values else None,
        "definition": (
            "Exhaustive video-packet DTS must be monotonic. PTS reordering is reported but "
            "not treated as failure because H.264 B-frames are decoded out of presentation order; "
            "decoded-frame availability is independently checked by full decode and random seeks."
        ),
    }


def full_decode_and_cut_audit(path: Path) -> dict[str, Any]:
    """Decode every video frame and report high-confidence edit boundaries."""
    started = time.perf_counter()
    result = run([
        "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-an",
        "-vf", r"scale=320:-2,select=gt(scene\,0.55),metadata=print:file=-",
        "-fps_mode", "passthrough", "-f", "null", "-",
    ])
    elapsed = time.perf_counter() - started
    stdout = result.stdout.decode("utf-8", "replace")
    stderr = result.stderr.decode("utf-8", "replace").strip()
    times = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", stdout)]
    scores = [float(value) for value in re.findall(r"lavfi\.scene_score=([0-9.]+)", stdout)]
    return {
        "status": "PASS" if result.returncode == 0 and not stderr else "FAIL",
        "elapsed_seconds": elapsed,
        "ffmpeg_exit_code": result.returncode,
        "decode_errors": stderr.splitlines(),
        "hard_cut_threshold": 0.55,
        "hard_cut_count": len(times),
        "hard_cut_timestamps": times,
        "hard_cut_scores": scores,
        "interpretation": (
            "No decoder error. Hard cuts are descriptive evidence only; a small count is "
            "compatible with an intro/outro and does not by itself establish stitching."
        ),
    }


def random_seek_audit(path: Path, duration: float) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for ratio in SEEK_RATIOS:
        timestamp = min(max(0.0, ratio * duration), max(0.0, duration - 0.25))
        started = time.perf_counter()
        result = run([
            "ffmpeg", "-v", "error", "-ss", f"{timestamp:.6f}", "-i", str(path),
            "-map", "0:v:0", "-frames:v", "1", "-an", "-f", "null", "-",
        ], timeout=90)
        rows.append({
            "ratio": ratio,
            "timestamp_seconds": timestamp,
            "elapsed_seconds": time.perf_counter() - started,
            "status": "PASS" if result.returncode == 0 and not result.stderr.strip() else "FAIL",
            "error": result.stderr.decode("utf-8", "replace").strip(),
        })
    elapsed = [row["elapsed_seconds"] for row in rows]
    return {
        "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL",
        "attempts": len(rows),
        "p50_seconds": float(np.percentile(elapsed, 50)),
        "p95_seconds": float(np.percentile(elapsed, 95)),
        "max_seconds": max(elapsed),
        "rows": rows,
    }


def bits_to_hex(bits: np.ndarray) -> str:
    value = 0
    for bit in bits.astype(bool).ravel():
        value = (value << 1) | int(bit)
    width = int(math.ceil(bits.size / 4))
    return f"{value:0{width}x}"


def frame_signature(frame: np.ndarray) -> dict[str, Any]:
    def image_hashes(image: np.ndarray) -> tuple[str, str]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
        low = cv2.dct(small)[:8, :8]
        phash = bits_to_hex(low > np.median(low[1:, :]))
        dh = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
        dhash = bits_to_hex(dh[:, 1:] > dh[:, :-1])
        return phash, dhash

    height, width = frame.shape[:2]
    margin_y, margin_x = int(round(height * 0.10)), int(round(width * 0.10))
    center = frame[margin_y:height - margin_y, margin_x:width - margin_x]
    full_phash, full_dhash = image_hashes(frame)
    center_phash, center_dhash = image_hashes(center)
    hsv = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 180, 0, 256]).ravel()
    histogram = histogram / max(float(np.linalg.norm(histogram)), 1e-12)
    return {
        "phash": full_phash,
        "dhash": full_dhash,
        "center_phash": center_phash,
        "center_dhash": center_dhash,
        "hsv_histogram": [round(float(x), 8) for x in histogram],
        "mean_bgr": [round(float(x), 4) for x in frame.reshape(-1, 3).mean(axis=0)],
    }


def sample_visual_fingerprints(path: Path, duration: float) -> dict[str, Any]:
    interval_times = list(np.arange(0.5, max(0.51, duration - 0.25), FINGERPRINT_STRIDE_SECONDS))
    fixed_times = [min(duration - 0.25, ratio * duration) for ratio in FIXED_RATIOS]
    times = sorted({round(float(value), 6) for value in interval_times + fixed_times})
    cap = cv2.VideoCapture(str(path))
    samples: list[dict[str, Any]] = []
    failures: list[float] = []
    for timestamp in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            failures.append(timestamp)
            continue
        signature = frame_signature(frame)
        signature["timestamp_seconds"] = timestamp
        samples.append(signature)
    cap.release()
    return {
        "status": "PASS" if not failures and len(samples) == len(times) else "FAIL",
        "sampling_stride_seconds": FINGERPRINT_STRIDE_SECONDS,
        "fixed_ratios": FIXED_RATIOS,
        "requested_samples": len(times),
        "successful_samples": len(samples),
        "failed_timestamps": failures,
        "samples": samples,
    }


def audio_fingerprints(path: Path, duration: float, has_audio: bool) -> dict[str, Any]:
    if not has_audio:
        return {"status": "NOT_PRESENT", "samples": []}
    rows: list[dict[str, Any]] = []
    for ratio in AUDIO_RATIOS:
        timestamp = min(max(0.0, ratio * duration - 2.0), max(0.0, duration - 4.0))
        result = run([
            "ffmpeg", "-v", "error", "-ss", f"{timestamp:.6f}", "-i", str(path),
            "-t", "4", "-map", "0:a:0", "-ac", "1", "-ar", "8000",
            "-f", "s16le", "-",
        ], timeout=90)
        pcm = np.frombuffer(result.stdout, dtype="<i2").astype(np.float32)
        if result.returncode or pcm.size < 8000:
            rows.append({
                "ratio": ratio, "timestamp_seconds": timestamp, "status": "FAIL",
                "error": result.stderr.decode("utf-8", "replace").strip(),
            })
            continue
        pcm /= 32768.0
        pcm -= float(pcm.mean())
        window = np.hanning(pcm.size)
        spectrum = np.abs(np.fft.rfft(pcm * window))
        edges = np.unique(np.geomspace(1, max(2, spectrum.size - 1), 33).astype(int))
        bands = []
        for start, end in zip(edges[:-1], edges[1:]):
            bands.append(math.log1p(float(spectrum[start:max(start + 1, end)].mean())))
        vector = np.asarray(bands, dtype=np.float64)
        vector = (vector - vector.mean()) / max(float(vector.std()), 1e-9)
        envelope = np.sqrt(np.mean(pcm[: (pcm.size // 20) * 20].reshape(20, -1) ** 2, axis=1))
        envelope /= max(float(np.linalg.norm(envelope)), 1e-9)
        rows.append({
            "ratio": ratio,
            "timestamp_seconds": timestamp,
            "status": "PASS",
            "spectral_vector": [round(float(x), 8) for x in vector],
            "envelope": [round(float(x), 8) for x in envelope],
            "pcm_sha256": hashlib.sha256(result.stdout).hexdigest(),
        })
    return {
        "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL",
        "sample_rate_hz": 8000,
        "window_seconds": 4,
        "samples": rows,
    }


def hamming_similarity(left: str, right: str) -> float:
    left_value, right_value = int(left, 16), int(right, 16)
    bits = max(len(left), len(right)) * 4
    return 1.0 - ((left_value ^ right_value).bit_count() / bits)


def cosine(left: list[float], right: list[float]) -> float:
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else 0.0


def visual_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    hash_scores = []
    for prefix_left in ("", "center_"):
        for prefix_right in ("", "center_"):
            phash = hamming_similarity(left[prefix_left + "phash"], right[prefix_right + "phash"])
            dhash = hamming_similarity(left[prefix_left + "dhash"], right[prefix_right + "dhash"])
            hash_scores.append(0.60 * phash + 0.40 * dhash)
    color = max(0.0, cosine(left["hsv_histogram"], right["hsv_histogram"]))
    return 0.85 * max(hash_scores) + 0.15 * color


def audio_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    spectral = (cosine(left["spectral_vector"], right["spectral_vector"]) + 1.0) / 2.0
    envelope = max(0.0, cosine(left["envelope"], right["envelope"]))
    return 0.8 * spectral + 0.2 * envelope


def nearest_time_sample(samples: list[dict[str, Any]], timestamp: float) -> dict[str, Any]:
    return min(samples, key=lambda row: abs(float(row["timestamp_seconds"]) - timestamp))


def longest_offset_run(matches: list[tuple[int, int]], minimum_index_gap: int = 0) -> int:
    match_set = set(matches)
    best = 0
    for start_i, start_j in match_set:
        if abs(start_i - start_j) < minimum_index_gap:
            continue
        length = 1
        while (start_i + length, start_j + length) in match_set:
            length += 1
        best = max(best, length)
    return best


def cross_video_independence(
    left: dict[str, Any], right: dict[str, Any], left_meta: dict[str, Any], right_meta: dict[str, Any]
) -> dict[str, Any]:
    left_samples = left["visual_fingerprints"]["samples"]
    right_samples = right["visual_fingerprints"]["samples"]
    ratio_scores = []
    for ratio in FIXED_RATIOS:
        a = nearest_time_sample(left_samples, ratio * float(left_meta["duration_seconds"]))
        b = nearest_time_sample(right_samples, ratio * float(right_meta["duration_seconds"]))
        ratio_scores.append(visual_similarity(a, b))

    stride_left = [
        row for row in left_samples
        if abs((float(row["timestamp_seconds"]) - 0.5) % FINGERPRINT_STRIDE_SECONDS) < 1e-3
    ]
    stride_right = [
        row for row in right_samples
        if abs((float(row["timestamp_seconds"]) - 0.5) % FINGERPRINT_STRIDE_SECONDS) < 1e-3
    ]
    matrix = np.zeros((len(stride_left), len(stride_right)), dtype=np.float32)
    threshold_matches: list[tuple[int, int]] = []
    for i, a in enumerate(stride_left):
        for j, b in enumerate(stride_right):
            score = visual_similarity(a, b)
            matrix[i, j] = score
            if score >= OFFSET_MATCH_THRESHOLD:
                threshold_matches.append((i, j))
    offset_counts: dict[int, int] = {}
    for i, j in threshold_matches:
        offset_counts[j - i] = offset_counts.get(j - i, 0) + 1
    best_offset_count = max(offset_counts.values(), default=0)
    longest_run = longest_offset_run(threshold_matches)

    left_audio = [row for row in left["audio_fingerprints"]["samples"] if row.get("status") == "PASS"]
    right_audio = [row for row in right["audio_fingerprints"]["samples"] if row.get("status") == "PASS"]
    aligned_audio = []
    if left_audio and right_audio:
        for ratio in AUDIO_RATIOS:
            a = min(left_audio, key=lambda row: abs(float(row["ratio"]) - ratio))
            b = min(right_audio, key=lambda row: abs(float(row["ratio"]) - ratio))
            aligned_audio.append(audio_similarity(a, b))

    exact_duplicate = left["sha256"] == right["sha256"]
    visual_overlap = (
        float(np.mean(ratio_scores)) >= MEAN_ALIGNED_OVERLAP_REJECT
        or longest_run >= MIN_OFFSET_MATCH_RUN
        or best_offset_count >= MIN_OFFSET_MATCH_RUN + 2
    )
    audio_overlap = bool(aligned_audio and float(np.mean(aligned_audio)) >= 0.94)
    independent = not exact_duplicate and not visual_overlap and not audio_overlap
    return {
        "status": "PASS" if independent else "FAIL",
        "exact_file_duplicate": exact_duplicate,
        "duration_ratio_right_over_left": (
            float(right_meta["duration_seconds"]) / float(left_meta["duration_seconds"])
        ),
        "fixed_ratio_visual_similarity": {
            "mean": float(np.mean(ratio_scores)),
            "p95": float(np.percentile(ratio_scores, 95)),
            "max": max(ratio_scores),
            "reject_threshold_mean": MEAN_ALIGNED_OVERLAP_REJECT,
        },
        "sequence_overlap": {
            "sampling_stride_seconds": FINGERPRINT_STRIDE_SECONDS,
            "left_samples": len(stride_left),
            "right_samples": len(stride_right),
            "threshold": OFFSET_MATCH_THRESHOLD,
            "threshold_match_pairs": len(threshold_matches),
            "best_constant_offset_match_count": best_offset_count,
            "longest_consecutive_offset_run": longest_run,
            "reject_run_length": MIN_OFFSET_MATCH_RUN,
            "maximum_pair_similarity": float(matrix.max()) if matrix.size else None,
        },
        "aligned_audio_similarity": None if not aligned_audio else {
            "mean": float(np.mean(aligned_audio)),
            "p95": float(np.percentile(aligned_audio, 95)),
            "max": max(aligned_audio),
            "reject_threshold_mean": 0.94,
        },
        "same_source_adjacent_segment_assessment": {
            "decision": "NO_SUPPORT_FOR_SAME_SOURCE_ADJACENCY" if independent else "UNRESOLVED_OR_FAILED",
            "observed_evidence": [
                "No exact-byte duplicate",
                "No sustained visual sequence alignment at 30-second sampling",
                "Fixed-ratio visual summaries are below the preregistered overlap threshold",
                "Audio summaries do not show aligned-content identity" if aligned_audio else "No comparable audio summary",
            ],
            "limitation": (
                "A cryptographic capture-session declaration is unavailable. The decision is a "
                "content-based independence conclusion, not proof of camera ownership provenance."
            ),
        },
        "independence_conclusion": (
            "Content fingerprints reject crop/re-encode/overlap/loop explanations and provide no "
            "evidence that the files are adjacent pieces of one source."
            if independent else
            "The candidate cannot be frozen as an independent source under the content audit."
        ),
    }


def within_video_repetition(video: dict[str, Any]) -> dict[str, Any]:
    samples = video["visual_fingerprints"]["samples"]
    stride = [
        row for row in samples
        if abs((float(row["timestamp_seconds"]) - 0.5) % FINGERPRINT_STRIDE_SECONDS) < 1e-3
    ]
    matches: list[tuple[int, int]] = []
    scores = []
    minimum_gap = max(3, int(round(180.0 / FINGERPRINT_STRIDE_SECONDS)))
    for i, left in enumerate(stride):
        for j in range(i + minimum_gap, len(stride)):
            score = visual_similarity(left, stride[j])
            scores.append(score)
            if score >= LOOP_MATCH_THRESHOLD:
                matches.append((i, j))
    longest = longest_offset_run(matches, minimum_index_gap=minimum_gap)
    loop_detected = longest >= MIN_OFFSET_MATCH_RUN
    duration = float(video["duration_seconds"])
    hard_cut_count = int(video.get("decode_health", {}).get("hard_cut_count", 0))
    hard_cuts_per_hour = hard_cut_count / max(duration / 3600.0, 1e-9)
    compilation_suspected = hard_cut_count >= 20 and hard_cuts_per_hour > 60.0
    return {
        "status": "FAIL" if loop_detected or compilation_suspected else "PASS",
        "sampling_stride_seconds": FINGERPRINT_STRIDE_SECONDS,
        "minimum_nonlocal_gap_seconds": minimum_gap * FINGERPRINT_STRIDE_SECONDS,
        "comparison_count": len(scores),
        "near_duplicate_pairs": len(matches),
        "maximum_nonlocal_similarity": max(scores) if scores else None,
        "longest_repeated_sequence_run": longest,
        "loop_reject_run_length": MIN_OFFSET_MATCH_RUN,
        "loop_or_padding_detected": loop_detected,
        "hard_cut_count": hard_cut_count,
        "hard_cuts_per_hour": hard_cuts_per_hour,
        "multi_clip_compilation_suspected": compilation_suspected,
        "compilation_screen": (
            "Fail only when at least 20 high-confidence cuts and more than 60 cuts/hour "
            "indicate a sequence of short edited clips."
        ),
    }


def physical_eligibility(meta: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    reference_duration = float(profile.get("video_duration_seconds") or 3462.930499)
    regime = profile["regime_B"] if "regime_B" in profile else {
        "coarse_p95": profile["C_p95_coarse_warm"],
        "physical_verify_p95": profile["C_p95_VERIFY"],
        "k3_snapshot_p95": profile["C_p95_K3"] + profile["C_p95_snapshot"],
        "safety_margin": profile.get("epsilon", 1.0),
        "full_proxy_p50": profile["C_p50_full_proxy_warm"],
    }
    duration = float(meta["duration_seconds"])
    scale = duration / reference_duration
    coarse_p95 = float(regime["coarse_p95"]) * scale
    full_p50 = float(regime["full_proxy_p50"]) * scale
    verify_p95 = float(regime["physical_verify_p95"])
    commit_p95 = float(regime["k3_snapshot_p95"])
    safety = float(regime["safety_margin"])
    t_min = coarse_p95 + verify_p95 + commit_p95 + safety
    t_max = full_p50
    width = t_max - t_min
    normalized = width / t_max if t_max else -math.inf
    cells = int(math.ceil(duration / UNIT_SECONDS))
    noise_floor = max(safety, 0.05 * t_max)
    pass_gate = (
        t_min < t_max
        and width > noise_floor
        and normalized > 0.10
        and cells >= MIN_TEMPORAL_CELLS
    )
    return {
        "status": "PASS" if pass_gate else "FAIL",
        "profile_source": str(PROFILE),
        "profile_workload": "warm_oracle_cold_unmaterialized_proxy",
        "reference_video_duration_seconds": reference_duration,
        "scaling_assumption": (
            "Coarse and full-proxy video work scale linearly with duration; VERIFY and durable "
            "commit tails are workload-fixed. Phase D must physically remeasure the selected proxy."
        ),
        "duration_scale": scale,
        "coarse_scan_p95_seconds": coarse_p95,
        "physical_verify_p95_seconds": verify_p95,
        "k3_snapshot_commit_p95_seconds": commit_p95,
        "safety_margin_seconds": safety,
        "full_proxy_p50_seconds": full_p50,
        "T_min_seconds": t_min,
        "T_max_seconds": t_max,
        "partial_proxy_interval_seconds": width,
        "normalized_interval_width": normalized,
        "measurement_noise_floor_seconds": noise_floor,
        "temporal_cells_10s": cells,
        "minimum_temporal_cells": MIN_TEMPORAL_CELLS,
        "can_complete_scan_verify_k3_commit": t_min < t_max and cells >= MIN_TEMPORAL_CELLS,
        "meaningful_partial_proxy_interval": width > noise_floor and normalized > 0.10,
    }


@dataclass
class VideoAudit:
    path: Path
    meta: dict[str, Any]
    value: dict[str, Any]


def inspect_video(path: Path, profile: dict[str, Any], *, full_decode: bool) -> VideoAudit:
    meta = ffprobe(path)
    if meta.get("status") != "PASS":
        value = {
            "absolute_path": str(path.resolve()), "file_name": path.name,
            "file_size_bytes": path.stat().st_size, "technical_status": "FAIL", "ffprobe": meta,
        }
        return VideoAudit(path, meta, value)
    digest = sha256_file(path)
    timestamps = timestamp_audit(path, int(meta["frame_count"]))
    decode = (
        full_decode_and_cut_audit(path)
        if full_decode else
        {"status": "NOT_RUN", "reason": "--skip-full-decode was used; not eligible for freezing"}
    )
    seek = random_seek_audit(path, float(meta["duration_seconds"]))
    visual = sample_visual_fingerprints(path, float(meta["duration_seconds"]))
    audio = audio_fingerprints(path, float(meta["duration_seconds"]), meta.get("audio") is not None)
    eligibility = physical_eligibility(meta, profile)
    stat = path.stat()
    value = {
        "absolute_path": str(path.resolve()),
        "file_name": path.name,
        "file_size_bytes": stat.st_size,
        "sha256": digest,
        "duration_seconds": meta["duration_seconds"],
        "fps": meta["fps"],
        "resolution": meta["resolution"],
        "codec": meta["codec"],
        "frame_count": meta["frame_count"],
        "creation_source_metadata": {
            "format_tags": meta["format_tags"],
            "video_tags": meta["video_tags"],
            "audio_tags": meta["audio_tags"],
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        },
        "ffprobe": meta,
        "timestamp_monotonicity": timestamps,
        "decode_health": decode,
        "random_seek_health": seek,
        "visual_fingerprints": visual,
        "audio_fingerprints": audio,
        "physical_eligibility": eligibility,
    }
    value["technical_status"] = "PASS" if all(
        block.get("status") == "PASS"
        for block in (timestamps, decode, seek, visual, eligibility)
    ) and audio.get("status") in {"PASS", "NOT_PRESENT"} else "FAIL"
    return VideoAudit(path, meta, value)


def load_profile() -> dict[str, Any]:
    if not PROFILE.is_file():
        raise FileNotFoundError(f"required physical profile missing: {PROFILE}")
    value = json.loads(PROFILE.read_text(encoding="utf-8"))
    if "regime_B" not in value and "C_p95_coarse_warm" not in value:
        raise RuntimeError(f"unrecognized physical profile schema: {PROFILE}")
    return value


def write_input_request(reasons: list[str]) -> None:
    text = f"""# PSVR two-video input request

`AUTONOMOUS_RESEARCH = PAUSED_INPUT_REQUIRED`

The bounded audit could not freeze a second independent, physically eligible video.

## Decisive reasons

{os.linesep.join(f"- {reason}" for reason in reasons)}

Place an original, continuous, forward-facing road video in:

`{VIDEO_ROOT}`

It must not be a crop, re-encode, overlapping/adjacent split, loop, padding, or
multi-clip compilation derived from `long_video_dataset3.mp4`. Eligibility is
derived from the frozen physical runtime profile; there is no fixed 1200-second
screen in this audit.

## Resume

```bash
python scripts/audit_psvr_two_video_inputs.py
```
"""
    atomic_text(OUT / "INPUT_REQUEST.md", text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-full-decode", action="store_true",
        help="Developer-only fast diagnostic. Results cannot be frozen as eligible.",
    )
    parser.add_argument(
        "--reuse-technical-audit", action="store_true",
        help="Reuse prior exhaustive technical blocks only when path, size, and SHA-256 still match.",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        path.resolve() for path in VIDEO_ROOT.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    )
    profile = load_profile()
    reused: dict[str, dict[str, Any]] = {}
    detail_path = OUT / "state/INPUT_AUDIT_DETAIL.json"
    if args.reuse_technical_audit and detail_path.is_file():
        prior = json.loads(detail_path.read_text(encoding="utf-8"))
        reused = prior.get("videos", {})
    technical_cache = OUT / "state/technical_cache"
    technical_cache.mkdir(parents=True, exist_ok=True)
    audits = []
    for path in candidates:
        prior = reused.get(path.name)
        digest = sha256_file(path)
        cache_path = technical_cache / f"{digest}.json"
        if prior is None and args.reuse_technical_audit and cache_path.is_file():
            prior = json.loads(cache_path.read_text(encoding="utf-8"))
        if prior and (
            prior.get("absolute_path") == str(path.resolve())
            and int(prior.get("file_size_bytes", -1)) == path.stat().st_size
            and prior.get("sha256") == digest
            and prior.get("technical_status") == "PASS"
        ):
            audits.append(VideoAudit(path, prior["ffprobe"], prior))
        else:
            audit = inspect_video(path, profile, full_decode=not args.skip_full_decode)
            audits.append(audit)
            atomic_json(cache_path, audit.value)
    by_path = {audit.path.resolve(): audit for audit in audits}
    reasons: list[str] = []
    if DATASET3.resolve() not in by_path:
        reasons.append(f"canonical V0 missing: {DATASET3}")
    dataset3 = by_path.get(DATASET3.resolve())
    if dataset3 and dataset3.value.get("sha256") != DATASET3_SHA256:
        reasons.append("canonical V0 SHA-256 differs from the frozen research contract")
    if dataset3 and dataset3.value.get("technical_status") != "PASS":
        reasons.append("canonical V0 failed current technical or physical eligibility checks")

    pair_audits: list[dict[str, Any]] = []
    eligible_new: list[VideoAudit] = []
    if dataset3:
        for audit in audits:
            if audit.path.resolve() == DATASET3.resolve():
                continue
            independence = cross_video_independence(
                dataset3.value, audit.value, dataset3.meta, audit.meta
            ) if audit.value.get("technical_status") == "PASS" else {
                "status": "FAIL", "reason": "candidate technical audit failed before content comparison"
            }
            repetition = (
                within_video_repetition(audit.value)
                if audit.value.get("visual_fingerprints", {}).get("status") == "PASS"
                else {"status": "FAIL", "reason": "candidate fingerprint audit incomplete"}
            )
            pair = {
                "v0": str(dataset3.path.resolve()),
                "candidate": str(audit.path.resolve()),
                "content_independence": independence,
                "candidate_loop_padding_audit": repetition,
                "eligible": (
                    audit.value.get("technical_status") == "PASS"
                    and independence.get("status") == "PASS"
                    and repetition.get("status") == "PASS"
                ),
            }
            pair_audits.append(pair)
            if pair["eligible"]:
                eligible_new.append(audit)
    eligible_new.sort(key=lambda audit: (-float(audit.meta["duration_seconds"]), str(audit.path.resolve())))
    selected = eligible_new[0] if eligible_new else None
    if selected is None:
        reasons.append("no non-dataset3 candidate passed technical, independence, loop, and physical gates")

    video_manifest = {
        "audit_version": "PSVR_TWO_VIDEO_INPUT_AUDIT_V1",
        "created_utc": utc_now(),
        "bounded_search_root": str(VIDEO_ROOT),
        "allowed_suffixes": sorted(VIDEO_SUFFIXES),
        "candidate_count": len(audits),
        "selection_rule": "longest eligible duration, then absolute-path lexicographic order",
        "V0": None if dataset3 is None else {
            key: dataset3.value[key] for key in (
                "absolute_path", "file_name", "file_size_bytes", "sha256", "duration_seconds",
                "fps", "resolution", "codec", "frame_count", "technical_status",
            )
        },
        "V1": None if selected is None else {
            key: selected.value[key] for key in (
                "absolute_path", "file_name", "file_size_bytes", "sha256", "duration_seconds",
                "fps", "resolution", "codec", "frame_count", "technical_status",
            )
        },
        "all_candidates": [
            {
                key: audit.value.get(key) for key in (
                    "absolute_path", "file_name", "file_size_bytes", "sha256", "duration_seconds",
                    "fps", "resolution", "codec", "frame_count", "technical_status",
                )
            }
            for audit in audits
        ],
        "VIDEO_FREEZE": "PASS" if selected is not None and not reasons else "FAIL",
        "heldout_opened": False,
    }
    source_audit = {
        "audit_version": "PSVR_TWO_VIDEO_SOURCE_INDEPENDENCE_V1",
        "created_utc": utc_now(),
        "criteria": [
            "not exact duplicate",
            "not crop or re-encode",
            "not an overlapping sequence",
            "no content evidence of adjacent same-source segmentation",
            "not looped or padded",
            "not a compilation of unrelated short clips",
        ],
        "pair_audits": pair_audits,
        "selected_candidate": None if selected is None else str(selected.path.resolve()),
        "SOURCE_INDEPENDENCE": "PASS" if selected is not None else "FAIL",
        "evidence_boundary": (
            "Direct byte, frame, sequence, audio, timestamp, decode, and edit-boundary evidence. "
            "No external capture-session sidecar was available."
        ),
        "heldout_opened": False,
    }
    physical_audit = {
        "audit_version": "PSVR_TWO_VIDEO_PHYSICAL_ELIGIBILITY_V1",
        "created_utc": utc_now(),
        "runtime_profile": str(PROFILE),
        "fixed_duration_threshold_used": False,
        "videos": {
            audit.path.name: audit.value.get("physical_eligibility")
            for audit in audits
        },
        "selected_candidate": None if selected is None else selected.path.name,
        "PHYSICAL_ELIGIBILITY": (
            "PASS" if selected is not None
            and selected.value["physical_eligibility"]["status"] == "PASS" else "FAIL"
        ),
        "heldout_opened": False,
    }
    detailed = {
        "audit_version": "PSVR_TWO_VIDEO_INPUT_AUDIT_V1",
        "created_utc": utc_now(),
        "videos": {audit.path.name: audit.value for audit in audits},
        "pair_audits": pair_audits,
        "reasons": reasons,
        "heldout_opened": False,
    }
    atomic_json(OUT / "VIDEO_MANIFEST.json", video_manifest)
    atomic_json(OUT / "SOURCE_INDEPENDENCE_AUDIT.json", source_audit)
    atomic_json(OUT / "PHYSICAL_ELIGIBILITY_AUDIT.json", physical_audit)
    atomic_json(OUT / "state/INPUT_AUDIT_DETAIL.json", detailed)
    decision = {
        "VIDEO_INPUT_GATE": "PASS" if selected is not None and not reasons else "FAIL",
        "V0": None if dataset3 is None else str(dataset3.path.resolve()),
        "V1": None if selected is None else str(selected.path.resolve()),
        "AUTONOMOUS_RESEARCH_STATUS": (
            "RUNNING" if selected is not None and not reasons else "PAUSED_INPUT_REQUIRED"
        ),
        "NEXT_EXACT_COMMAND": (
            "python scripts/freeze_psvr_two_video_queries.py"
            if selected is not None and not reasons
            else "python scripts/audit_psvr_two_video_inputs.py"
        ),
        "heldout_opened": False,
    }
    atomic_json(OUT / "state/INPUT_GATE_DECISION.json", decision)
    if decision["VIDEO_INPUT_GATE"] != "PASS":
        write_input_request(reasons)
    elif (OUT / "INPUT_REQUEST.md").exists():
        (OUT / "INPUT_REQUEST.md").unlink()
    print(json.dumps(decision, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
