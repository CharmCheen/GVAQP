#!/usr/bin/env python3
"""Cut fixed-length clips from filtered road-driving segments."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from common import DEFAULT_CONFIG, cut_clip, encoder_candidates, ensure_output_dir, fail, fmt_ms, load_config, read_csv, validate_base_paths, write_csv


FIELDS = ["clip_id", "video_id", "segment_id", "start_time", "end_time", "clip_path"]


def planned_clips(segments: list[dict], clip_len: float, stride: float) -> list[dict]:
    plans = []
    for seg in segments:
        start = float(seg["start_time"])
        end = float(seg["end_time"])
        t = start
        idx = 0
        while t + clip_len <= end + 1e-6:
            plans.append(
                {
                    "video_id": seg["video_id"],
                    "segment_id": seg["segment_id"],
                    "video_path": seg["video_path"],
                    "start_time": t,
                    "end_time": t + clip_len,
                    "segment_local_index": idx,
                }
            )
            t += stride
            idx += 1
    return plans


def uniform_downsample(items: list[dict], target: int) -> list[dict]:
    if len(items) <= target:
        return items
    if target <= 1:
        return items[:target]
    selected = []
    for i in range(target):
        idx = int(round(i * (len(items) - 1) / (target - 1)))
        selected.append(items[idx])
    seen = set()
    dedup = []
    for item in selected:
        key = (item["video_id"], item["segment_id"], item["start_time"])
        if key not in seen:
            dedup.append(item)
            seen.add(key)
    return dedup


def main() -> None:
    parser = argparse.ArgumentParser(description="Make fixed-length clips from road segments.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    clip_cfg = cfg.get("clips") or {}
    clip_len = float(clip_cfg.get("clip_len_sec", 5))
    stride = float(clip_cfg.get("stride_sec", 2))
    target_max = int(clip_cfg.get("target_max_clips", 500))
    target_min = int(clip_cfg.get("target_min_clips", 200))
    if clip_len <= 0 or stride <= 0:
        fail("clip_len_sec and stride_sec must be positive")

    segments = read_csv(output_dir / "road_segments.csv")
    valid_segments = [s for s in segments if float(s.get("end_time", 0)) - float(s.get("start_time", 0)) >= clip_len]
    plans = planned_clips(valid_segments, clip_len, stride)
    plans = uniform_downsample(plans, target_max)
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    encoders = encoder_candidates()

    rows = []
    failed = []
    for i, plan in enumerate(plans):
        start = float(plan["start_time"])
        end = float(plan["end_time"])
        clip_id = f"{plan['video_id']}_{plan['segment_id']}_clip{i:05d}_s{fmt_ms(start)}_e{fmt_ms(end)}"
        out_path = clips_dir / f"{clip_id}.mp4"
        try:
            cut_clip(Path(plan["video_path"]), start, clip_len, out_path, encoders)
            rows.append(
                {
                    "clip_id": clip_id,
                    "video_id": plan["video_id"],
                    "segment_id": plan["segment_id"],
                    "start_time": f"{start:.3f}",
                    "end_time": f"{end:.3f}",
                    "clip_path": str(out_path),
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            failed.append({"clip_id": clip_id, "error": str(exc)})
        print(f"[{i + 1}/{len(plans)}] {clip_id}", flush=True)

    write_csv(output_dir / "clips.csv", rows, FIELDS)
    if failed:
        write_csv(output_dir / "clip_failures.csv", failed, ["clip_id", "error"])
    report = [
        "# Road Clip Pool Report",
        "",
        f"- valid segments used: {len(valid_segments)}",
        f"- candidate clips planned after target_max sampling: {len(plans)}",
        f"- clips written: {len(rows)}",
        f"- failed clips: {len(failed)}",
        f"- target_min_clips: {target_min}",
        f"- target_max_clips: {target_max}",
    ]
    if len(rows) < target_min:
        report.append(f"- WARNING: clip count {len(rows)} is below target_min_clips {target_min}.")
    (output_dir / "clip_pool_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"clips_csv={output_dir / 'clips.csv'}")
    print(f"clip_count={len(rows)}")


if __name__ == "__main__":
    main()
