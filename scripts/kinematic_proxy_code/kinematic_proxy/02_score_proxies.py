#!/usr/bin/env python3
"""Compute count, naive, and kinematic proxy scores for each clip."""

import argparse
import math
from collections import defaultdict
from pathlib import Path

from common import (
    DEFAULT_CONFIG,
    clamp01,
    ensure_output_dir,
    format_float,
    load_config,
    read_csv,
    to_float,
    validate_base_paths,
    write_csv,
)


def group_tracks(track_rows: list[dict]) -> dict[str, dict[str, list[dict]]]:
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in track_rows:
        grouped[row["clip_id"]][str(row["track_id"])].append(row)
    for tracks in grouped.values():
        for rows in tracks.values():
            rows.sort(key=lambda r: int(float(r["frame_idx"])))
    return grouped


def roi_overlap_ratio(row: dict, cfg: dict) -> float:
    fw = to_float(row["frame_w"])
    fh = to_float(row["frame_h"])
    if fw <= 0 or fh <= 0:
        return 0.0
    rx1 = float(cfg["roi_x1"]) * fw
    rx2 = float(cfg["roi_x2"]) * fw
    ry1 = float(cfg["roi_y1"]) * fh
    ry2 = float(cfg["roi_y2"]) * fh
    x1, y1 = to_float(row["x1"]), to_float(row["y1"])
    x2, y2 = to_float(row["x2"]), to_float(row["y2"])
    ix1, iy1 = max(x1, rx1), max(y1, ry1)
    ix2, iy2 = min(x2, rx2), min(y2, ry2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return inter / area if area > 0 else 0.0


def predicted_entry(row: dict, vx: float, vy: float, horizon: float, cfg: dict) -> float:
    fw = to_float(row["frame_w"])
    fh = to_float(row["frame_h"])
    if fw <= 0 or fh <= 0:
        return 0.0
    pred_x = to_float(row["cx"]) + vx * horizon
    pred_y = to_float(row["cy"]) + vy * horizon
    rx1 = float(cfg["roi_x1"]) * fw
    rx2 = float(cfg["roi_x2"]) * fw
    ry1 = float(cfg["roi_y1"]) * fh
    ry2 = float(cfg["roi_y2"]) * fh
    if rx1 <= pred_x <= rx2 and ry1 <= pred_y <= ry2:
        return 1.0
    roi_cx = (rx1 + rx2) / 2.0
    roi_cy = (ry1 + ry2) / 2.0
    dist = math.hypot((pred_x - roi_cx) / fw, (pred_y - roi_cy) / fh)
    return clamp01(1.0 - dist / 0.5)


def lateral_toward(row: dict, vx: float, cfg: dict) -> float:
    fw = to_float(row["frame_w"])
    if fw <= 0:
        return 0.0
    roi_center_x = ((float(cfg["roi_x1"]) + float(cfg["roi_x2"])) / 2.0) * fw
    cx = to_float(row["cx"])
    direction_to_roi = math.copysign(1.0, roi_center_x - cx) if roi_center_x != cx else 0.0
    toward_speed = max(0.0, vx * direction_to_roi)
    return clamp01(toward_speed / (0.20 * fw))


def track_features(rows: list[dict], clip_len: float, cfg: dict) -> dict:
    first, last = rows[0], rows[-1]
    fw = max(to_float(last["frame_w"]), 1.0)
    fh = max(to_float(last["frame_h"]), 1.0)
    times = [to_float(r["time_sec"]) for r in rows]
    duration = max(times) - min(times) if len(times) > 1 else 0.0
    persistence = clamp01(duration / max(clip_len, 1e-6))

    first_area = max(to_float(first["area"]), 1.0)
    last_area = max(to_float(last["area"]), 1.0)
    area_growth = clamp01(max(0.0, last_area / first_area - 1.0) / 2.0)
    center_motion = clamp01(math.hypot(to_float(last["cx"]) - to_float(first["cx"]), to_float(last["cy"]) - to_float(first["cy"])) / math.hypot(fw, fh))
    max_overlap = max(roi_overlap_ratio(r, cfg) for r in rows)

    recent = rows[-min(6, len(rows)) :]
    if len(recent) >= 2:
        dt = max(to_float(recent[-1]["time_sec"]) - to_float(recent[0]["time_sec"]), 1e-6)
        vx = (to_float(recent[-1]["cx"]) - to_float(recent[0]["cx"])) / dt
        vy = (to_float(recent[-1]["cy"]) - to_float(recent[0]["cy"])) / dt
    else:
        vx = vy = 0.0
    horizon = float(cfg["prediction_horizon_sec"])
    pred_entry = predicted_entry(last, vx, vy, horizon, cfg)
    lateral = lateral_toward(last, vx, cfg)

    frame_indices = [int(float(r["frame_idx"])) for r in rows]
    expected = frame_indices[-1] - frame_indices[0] + 1 if frame_indices else 1
    continuity = len(set(frame_indices)) / max(expected, 1)
    instability_penalty = clamp01(1.0 - continuity)

    risk = (
        0.30 * pred_entry
        + 0.20 * lateral
        + 0.20 * area_growth
        + 0.20 * persistence
        + 0.10 * max_overlap
        - 0.20 * instability_penalty
    )
    return {
        "area_growth": area_growth,
        "center_motion": center_motion,
        "overlap": max_overlap,
        "pred_entry": pred_entry,
        "lateral": lateral,
        "persistence": persistence,
        "instability_penalty": instability_penalty,
        "risk": clamp01(risk),
        "duration": duration,
    }


def score_clip(clip: dict, tracks: dict[str, list[dict]], cfg: dict) -> dict:
    clip_len = to_float(clip["end_time"]) - to_float(clip["start_time"])
    frame_counts = defaultdict(int)
    for rows in tracks.values():
        for row in rows:
            frame_counts[row["frame_idx"]] += 1
    mean_count = sum(frame_counts.values()) / len(frame_counts) if frame_counts else 0.0
    max_count = max(frame_counts.values()) if frame_counts else 0
    count_score = clamp01(0.6 * (mean_count / 8.0) + 0.4 * (max_count / 12.0))

    feats = [track_features(rows, clip_len, cfg) for rows in tracks.values() if rows]
    stable = [f for f in feats if f["persistence"] >= 0.30]
    max_area_growth = max((f["area_growth"] for f in feats), default=0.0)
    max_center_motion = max((f["center_motion"] for f in feats), default=0.0)
    max_overlap = max((f["overlap"] for f in feats), default=0.0)
    max_pred_entry = max((f["pred_entry"] for f in feats), default=0.0)
    max_lateral = max((f["lateral"] for f in feats), default=0.0)
    max_persistence = max((f["persistence"] for f in feats), default=0.0)

    naive = clamp01(
        0.25 * max_area_growth
        + 0.20 * max_center_motion
        + 0.25 * max_overlap
        + 0.15 * clamp01(len(stable) / 5.0)
        + 0.15 * max_persistence
    )
    kinematic = max((f["risk"] for f in feats), default=0.0)

    return {
        "clip_id": clip["clip_id"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"],
        "clip_path": clip["clip_path"],
        "score_count": format_float(count_score),
        "score_naive": format_float(naive),
        "score_kinematic": format_float(kinematic),
        "mean_vehicle_count": format_float(mean_count),
        "max_vehicle_count": max_count,
        "max_area_growth": format_float(max_area_growth),
        "max_center_motion": format_float(max_center_motion),
        "max_ego_path_overlap": format_float(max_overlap),
        "max_predicted_entry": format_float(max_pred_entry),
        "max_lateral_toward_ego_path": format_float(max_lateral),
        "max_temporal_persistence": format_float(max_persistence),
        "track_count": len(tracks),
        "stable_track_count": len(stable),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score clips using vehicle count, naive, and kinematic proxies.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    clips = read_csv(output_dir / "clips.csv")
    track_rows = read_csv(output_dir / "tracks.csv")
    grouped = group_tracks(track_rows)
    rows = [score_clip(clip, grouped.get(clip["clip_id"], {}), cfg) for clip in clips]

    fieldnames = [
        "clip_id",
        "start_time",
        "end_time",
        "clip_path",
        "score_count",
        "score_naive",
        "score_kinematic",
        "mean_vehicle_count",
        "max_vehicle_count",
        "max_area_growth",
        "max_center_motion",
        "max_ego_path_overlap",
        "max_predicted_entry",
        "max_lateral_toward_ego_path",
        "max_temporal_persistence",
        "track_count",
        "stable_track_count",
    ]
    out_path = output_dir / "proxy_scores.csv"
    write_csv(out_path, rows, fieldnames)
    print(f"proxy_scores_csv={out_path}")
    print(f"clip_count={len(rows)}")


if __name__ == "__main__":
    main()
