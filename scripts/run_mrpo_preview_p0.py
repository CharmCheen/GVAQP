#!/usr/bin/env python3
"""Generate legal MRPO P0 previews directly from source-video keyframes.

No full-SCAN output, candidate map, reference event, or label is read here.
Operator selection is based only on measured cost, determinism, and support.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import resource
import subprocess
import time

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IMM = ROOT / "benchmarks/partial_scan_pilot_v1/immutable"
OUT = ROOT / "outputs/macro_region_proxy_optimization_v1"
WIDTH, HEIGHT = 160, 90
REGION_LENGTH = 40
CONFIGS = (
    {"operator_id": "P0_KEYFRAME_10S_160X90", "period_sec": 10.0},
    {"operator_id": "P0_KEYFRAME_5S_160X90", "period_sec": 5.0},
)


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def frame_features(frame: np.ndarray, previous_gray: np.ndarray | None,
                   previous_hist: np.ndarray | None) -> tuple[dict, np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
    hist = cv2.calcHist([gray], [0], None, [32], [0, 256]).reshape(-1)
    hist /= max(float(hist.sum()), 1.0)
    entropy = float(-(hist[hist > 0] * np.log2(hist[hist > 0])).sum())
    edges = cv2.Canny(gray, 60, 120)
    h0, h1 = HEIGHT // 4, 3 * HEIGHT // 4
    w0, w1 = WIDTH // 4, 3 * WIDTH // 4
    center = gray[h0:h1, w0:w1]
    center_mean = float(center.mean())
    whole_mean = float(gray.mean())
    values = {
        "luma_mean": whole_mean,
        "luma_std": float(gray.std()),
        "entropy": entropy,
        "edge_density": float(np.mean(edges > 0)),
        "saturation_mean": float(hsv[:, :, 1].mean()),
        "center_border_contrast": center_mean - float((gray.sum() - center.sum()) / (gray.size - center.size)),
        "frame_diff_mean": 0.0 if previous_gray is None else float(cv2.absdiff(gray, previous_gray).mean()),
        "histogram_l1_change": 0.0 if previous_hist is None else float(np.abs(hist - previous_hist).sum()),
    }
    return values, gray, hist


def aggregate(frames: pd.DataFrame, video_id: str, duration: float,
              operator_id: str, period: float) -> pd.DataFrame:
    rows = []
    count = int(math.ceil(duration / REGION_LENGTH))
    value_columns = [c for c in frames.columns if c not in {"sample_index", "timestamp_sec", "region_index"}]
    for index in range(count):
        start, end = index * REGION_LENGTH, min((index + 1) * REGION_LENGTH, duration)
        group = frames[frames.region_index.eq(index)]
        row = {
            "operator_id": operator_id,
            "video_id": video_id,
            "region_id": f"{video_id}_L{REGION_LENGTH:03d}_R{index:04d}",
            "region_index": index,
            "start_sec": start,
            "end_sec": end,
            "actual_duration_sec": end - start,
            "preview_sample_count": int(len(group)),
            "preview_expected_sample_count": int(math.ceil((end - start) / period)),
        }
        row["preview_support_fraction"] = min(1.0, row["preview_sample_count"] / max(row["preview_expected_sample_count"], 1))
        for column in value_columns:
            values = group[column].to_numpy(dtype=float)
            row[f"{column}__mean"] = float(values.mean()) if len(values) else 0.0
            row[f"{column}__std"] = float(values.std()) if len(values) else 0.0
            row[f"{column}__max"] = float(values.max()) if len(values) else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def extract(video: pd.Series, config: dict, run_index: int) -> tuple[pd.DataFrame, dict]:
    source = Path(str(video.video_path))
    period = float(config["period_sec"])
    fps_expression = f"fps=1/{period:g},scale={WIDTH}:{HEIGHT}"
    command = [
        "ffmpeg", "-v", "error", "-skip_frame", "nokey", "-i", str(source),
        "-vf", fps_expression, "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    frame_bytes = WIDTH * HEIGHT * 3
    wall_start = time.perf_counter()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    feature_time = 0.0
    read_time = 0.0
    rows = []
    previous_gray = previous_hist = None
    index = 0
    assert process.stdout is not None
    while True:
        start = time.perf_counter()
        payload = process.stdout.read(frame_bytes)
        read_time += time.perf_counter() - start
        if not payload:
            break
        if len(payload) != frame_bytes:
            process.kill()
            raise RuntimeError(f"partial frame: {len(payload)}/{frame_bytes}")
        start = time.perf_counter()
        frame = np.frombuffer(payload, dtype=np.uint8).reshape(HEIGHT, WIDTH, 3)
        values, previous_gray, previous_hist = frame_features(frame, previous_gray, previous_hist)
        feature_time += time.perf_counter() - start
        timestamp = index * period
        rows.append({
            "sample_index": index,
            "timestamp_sec": timestamp,
            "region_index": min(int(timestamp // REGION_LENGTH), int(math.ceil(float(video.duration_sec) / REGION_LENGTH)) - 1),
            **values,
        })
        index += 1
    stderr = process.stderr.read().decode() if process.stderr is not None else ""
    return_code = process.wait()
    if return_code:
        raise RuntimeError(f"ffmpeg failed ({return_code}): {stderr}")
    elapsed = time.perf_counter() - wall_start
    frame_table = pd.DataFrame(rows)
    region_table = aggregate(frame_table, str(video.video_id), float(video.duration_sec), config["operator_id"], period)
    runtime = {
        "operator_id": config["operator_id"], "video_id": str(video.video_id), "run_index": run_index,
        "source_sha256": file_sha(source), "sample_period_sec": period,
        "sample_count": len(frame_table), "wallclock_sec": elapsed,
        "decode_and_pipe_wait_sec": read_time, "feature_compute_sec": feature_time,
        "model_inference_sec": 0.0, "video_duration_sec": float(video.duration_sec),
        "seconds_per_video_hour": elapsed / float(video.duration_sec) * 3600.0,
        "max_rss_kib_process_lifetime": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "ffmpeg_command": command,
    }
    return region_table, runtime


def canonical_feature_hash(table: pd.DataFrame) -> str:
    value = table.sort_values(["video_id", "region_index"]).to_csv(index=False, float_format="%.10g").encode()
    return hashlib.sha256(value).hexdigest()


def main() -> None:
    videos = pd.read_csv(IMM / "videos.csv")
    phase0 = json.loads((OUT / "audits/asset_audit.json").read_text())
    full_cost = sum(float(row["measured_full_scan_cost_sec"]) for row in phase0["per_video"])
    first_pass: dict[str, tuple[pd.DataFrame, list[dict]]] = {}
    for config in CONFIGS:
        tables, runtimes = [], []
        for video in videos.itertuples(index=False):
            table, runtime = extract(pd.Series(video._asdict()), config, 1)
            tables.append(table); runtimes.append(runtime)
            dump_json(OUT / f"preview/runtime_samples/{config['operator_id']}__{video.video_id}__run1.json", runtime)
        first_pass[config["operator_id"]] = (pd.concat(tables, ignore_index=True), runtimes)

    # Label-free rule: choose the highest temporal support operator whose deployed
    # cost is at most 10% of measured full scan; tie-break by lower cost.
    eligible = []
    for config in CONFIGS:
        table, runtimes = first_pass[config["operator_id"]]
        total = sum(r["wallclock_sec"] for r in runtimes)
        ratio = total / full_cost
        support = float(table.preview_sample_count.sum())
        if ratio <= 0.10:
            eligible.append((support, -total, config))
    if not eligible:
        raise RuntimeError("No P0 operator meets frozen 10% preview-cost ceiling")
    chosen = max(eligible, key=lambda item: (item[0], item[1]))[2]

    repeat_tables, repeat_runtimes = [], []
    for video in videos.itertuples(index=False):
        table, runtime = extract(pd.Series(video._asdict()), chosen, 2)
        repeat_tables.append(table); repeat_runtimes.append(runtime)
        dump_json(OUT / f"preview/runtime_samples/{chosen['operator_id']}__{video.video_id}__run2.json", runtime)
    chosen_table, chosen_run1 = first_pass[chosen["operator_id"]]
    repeat_table = pd.concat(repeat_tables, ignore_index=True)
    deterministic = canonical_feature_hash(chosen_table) == canonical_feature_hash(repeat_table)

    for operator_id, (table, _) in first_pass.items():
        table.to_parquet(OUT / f"preview/region_features/{operator_id}.parquet", index=False)
    chosen_table.to_parquet(OUT / "preview/region_features/SELECTED.parquet", index=False)

    candidates = []
    for config in CONFIGS:
        table, runtimes = first_pass[config["operator_id"]]
        total = sum(r["wallclock_sec"] for r in runtimes)
        candidates.append({
            **config, "family": "P0_METADATA_FRAMESTAT", "total_wallclock_sec": total,
            "preview_to_full_scan_cost_ratio": total / full_cost,
            "sample_count": int(table.preview_sample_count.sum()),
            "mean_region_support_fraction": float(table.preview_support_fraction.mean()),
            "eligible_under_cost_ceiling": total / full_cost <= 0.10,
        })
    manifest = {
        "selected_operator_id": chosen["operator_id"],
        "selection_uses_event_labels": False,
        "selection_rule": "MAX_TEMPORAL_SAMPLE_SUPPORT_SUBJECT_TO_DEPLOYED_COST_RATIO_LE_0.10",
        "full_scan_cache_or_label_inputs": [],
        "source_inputs": list(videos.video_path.astype(str)),
        "macro_region_length_sec": REGION_LENGTH,
        "feature_families": [
            "brightness_contrast", "entropy_texture", "edge_structure", "color_saturation",
            "frame_difference", "histogram_change", "spatial_center_border", "sampling_support",
        ],
        "candidate_operators": candidates,
        "determinism_repeat_hash_match": deterministic,
        "chosen_run1_hash": canonical_feature_hash(chosen_table),
        "chosen_run2_hash": canonical_feature_hash(repeat_table),
        "chosen_repeat_runtime_sec": sum(r["wallclock_sec"] for r in repeat_runtimes),
    }
    dump_json(OUT / "preview/operator_manifests/P0_SELECTION.json", manifest)
    deployed_total = next(x["total_wallclock_sec"] for x in candidates if x["operator_id"] == chosen["operator_id"])
    dump_json(OUT / "audits/preview_cost_audit.json", {
        "status": "PASS" if deployed_total / full_cost <= 0.10 and deterministic else "FAIL",
        "selected_operator_id": chosen["operator_id"],
        "deployed_preview_wallclock_sec": deployed_total,
        "measured_full_scan_wallclock_sec": full_cost,
        "preview_to_full_scan_cost_ratio": deployed_total / full_cost,
        "exploration_wallclock_sec": sum(x["total_wallclock_sec"] for x in candidates),
        "determinism_repeat_cost_sec": sum(r["wallclock_sec"] for r in repeat_runtimes),
        "determinism_repeat_hash_match": deterministic,
        "per_operator": candidates,
        "memory_metric_note": "ru_maxrss is process-lifetime high-water mark, not isolated operator peak",
    })
    if not deterministic:
        raise RuntimeError("Chosen P0 feature output is not deterministic")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
