#!/usr/bin/env python3
"""Filter source videos into coarse valid road-driving segments using Qwen3-VL."""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

from common import DEFAULT_CONFIG, append_csv, cut_clip, encoder_candidates, ensure_output_dir, fail, fmt_ms, load_config, read_csv, validate_base_paths, write_blocked, write_csv
from vlm_utils import SCENE_FILTER_PROMPT, load_qwen3_vl, parse_json_object, run_video_prompt


WINDOW_FIELDS = [
    "video_id",
    "video_path",
    "window_id",
    "start_time",
    "end_time",
    "window_path",
    "valid_road_driving",
    "scene_type",
    "confidence",
    "reason",
    "raw_response",
    "runtime_sec",
    "status",
    "error_message",
]
SEGMENT_FIELDS = ["video_id", "video_path", "segment_id", "start_time", "end_time", "window_count", "uncertain_count", "reason"]


def norm_choice(value: str, allowed: set[str], default: str) -> str:
    value = str(value or "").strip().lower()
    return value if value in allowed else default


def make_windows(inventory: list[dict], window_len: float, stride: float) -> list[dict]:
    windows = []
    for video in inventory:
        duration = float(video["duration_sec"])
        start = 0.0
        idx = 0
        while start + window_len <= duration + 1e-6:
            end = start + window_len
            window_id = f"{video['video_id']}_win{idx:05d}_s{fmt_ms(start)}_e{fmt_ms(end)}"
            windows.append(
                {
                    "video_id": video["video_id"],
                    "video_path": video["video_path"],
                    "window_id": window_id,
                    "start_time": f"{start:.3f}",
                    "end_time": f"{end:.3f}",
                }
            )
            idx += 1
            start += stride
    return windows


def normalize_result(window: dict, window_path: Path, raw: str, parse_error: str, parsed: dict | None, runtime_sec: float, status: str, error: str = "") -> dict:
    parsed = parsed or {}
    valid = norm_choice(parsed.get("valid_road_driving"), {"yes", "no", "uncertain"}, "uncertain")
    scene_type = norm_choice(
        parsed.get("scene_type"),
        {"road_driving", "pre_road", "closed_area", "parking_low_speed", "title_or_black", "static_or_parked", "unusable", "other"},
        "other",
    )
    confidence = norm_choice(parsed.get("confidence"), {"low", "medium", "high"}, "low")
    if parse_error:
        valid, scene_type, confidence = "uncertain", "other", "low"
        error = parse_error
        status = "parse_failed"
    return {
        **window,
        "window_path": str(window_path),
        "valid_road_driving": valid,
        "scene_type": scene_type,
        "confidence": confidence,
        "reason": str(parsed.get("reason", ""))[:1000],
        "raw_response": raw,
        "runtime_sec": f"{runtime_sec:.3f}",
        "status": status,
        "error_message": error,
    }


def merge_segments(rows: list[dict], stride: float) -> list[dict]:
    rows = sorted(rows, key=lambda r: (r["video_id"], float(r["start_time"])))
    segments = []
    current = None
    for row in rows:
        keep = row["valid_road_driving"] == "yes"
        if row["valid_road_driving"] == "uncertain" and current is not None and current["uncertain_count"] == 0:
            keep = True
        if not keep:
            if current is not None:
                segments.append(current)
                current = None
            continue
        if current is None or current["video_id"] != row["video_id"] or float(row["start_time"]) - current["last_start"] > stride + 1e-6:
            if current is not None:
                segments.append(current)
            current = {
                "video_id": row["video_id"],
                "video_path": row["video_path"],
                "start_time": float(row["start_time"]),
                "end_time": float(row["end_time"]),
                "last_start": float(row["start_time"]),
                "window_count": 1,
                "uncertain_count": 1 if row["valid_road_driving"] == "uncertain" else 0,
            }
        else:
            current["end_time"] = float(row["end_time"])
            current["last_start"] = float(row["start_time"])
            current["window_count"] += 1
            if row["valid_road_driving"] == "uncertain":
                current["uncertain_count"] += 1
    if current is not None:
        segments.append(current)
    out = []
    counters = Counter()
    for seg in segments:
        counters[seg["video_id"]] += 1
        segment_id = f"{seg['video_id']}_seg{counters[seg['video_id']]:03d}"
        out.append(
            {
                "video_id": seg["video_id"],
                "video_path": seg["video_path"],
                "segment_id": segment_id,
                "start_time": f"{seg['start_time']:.3f}",
                "end_time": f"{seg['end_time']:.3f}",
                "window_count": seg["window_count"],
                "uncertain_count": seg["uncertain_count"],
                "reason": "merged consecutive valid windows; one uncertain gap allowed",
            }
        )
    return out


def write_report(output_dir: Path, inventory: list[dict], windows: list[dict], rows: list[dict], segments: list[dict]) -> None:
    scene_counts = Counter(r["scene_type"] for r in rows if r["valid_road_driving"] != "yes")
    valid = [r for r in rows if r["valid_road_driving"] == "yes"]
    invalid = [r for r in rows if r["valid_road_driving"] == "no"]
    uncertain = [r for r in rows if r["valid_road_driving"] == "uncertain"]
    valid_duration = sum(float(s["end_time"]) - float(s["start_time"]) for s in segments)
    lines = [
        "# Road Segment Filter Report",
        "",
        f"- source videos: {len(inventory)}",
        f"- total source duration sec: {sum(float(v['duration_sec']) for v in inventory):.3f}",
        f"- candidate windows: {len(windows)}",
        f"- completed window labels: {len(rows)}",
        f"- valid windows: {len(valid)}",
        f"- invalid windows: {len(invalid)}",
        f"- uncertain windows: {len(uncertain)}",
        f"- valid road-driving duration sec: {valid_duration:.3f}",
        f"- final road segments: {len(segments)}",
        "",
        "## Invalid Scene Type Distribution",
        "",
        "| scene_type | count |",
        "|---|---:|",
    ]
    for k, v in scene_counts.most_common():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Road Segments", "", "| segment_id | video_id | start | end | duration_sec | windows | uncertain |", "|---|---|---:|---:|---:|---:|---:|"]
    for s in segments:
        dur = float(s["end_time"]) - float(s["start_time"])
        lines.append(f"| {s['segment_id']} | {s['video_id']} | {float(s['start_time']):.1f} | {float(s['end_time']):.1f} | {dur:.1f} | {s['window_count']} | {s['uncertain_count']} |")
    if valid_duration < 120:
        lines += ["", "WARNING: valid road-driving duration is below 120 seconds; dataset may be insufficient."]
    (output_dir / "road_segment_filter_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter road-driving segments with VLM scene prompt.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    model_path = Path(cfg["vlm_model_path"])
    if not model_path.is_dir():
        path = write_blocked(output_dir, "BLOCKED_scene_filter_vlm.md", "BLOCKED: Scene Filter VLM", [f"missing model path `{model_path}`"])
        print(f"blocked_report={path}")
        return

    inv_path = output_dir / "video_inventory.csv"
    if not inv_path.is_file():
        path = write_blocked(output_dir, "BLOCKED_missing_video_inventory.md", "BLOCKED: Missing Video Inventory", ["Run `00_inventory_videos.py` first."])
        print(f"blocked_report={path}")
        return
    inventory = read_csv(inv_path)
    scene_cfg = cfg.get("scene_filter") or {}
    window_len = float(scene_cfg.get("window_len_sec", 10))
    stride = float(scene_cfg.get("stride_sec", 10))
    fps = float(scene_cfg.get("fps", 1.0))
    retries = int(scene_cfg.get("retries", 1))
    windows = make_windows(inventory, window_len, stride)
    if args.limit:
        windows = windows[: args.limit]

    labels_path = output_dir / "road_window_labels.csv"
    existing = {}
    if labels_path.is_file() and not args.overwrite:
        existing = {r["window_id"]: r for r in read_csv(labels_path) if r.get("status") in {"ok", "parse_failed", "runtime_failed"}}
    pending = [w for w in windows if args.overwrite or w["window_id"] not in existing]
    print(f"windows={len(windows)} existing={len(existing)} pending={len(pending)}")

    encoders = encoder_candidates()
    window_dir = output_dir / "scene_windows"
    if pending:
        print(f"Loading Qwen3-VL-32B from {model_path}", flush=True)
        torch, process_vision_info, model, processor = load_qwen3_vl(model_path)
        for i, win in enumerate(pending, 1):
            window_path = window_dir / f"{win['window_id']}.mp4"
            cut_clip(Path(win["video_path"]), float(win["start_time"]), window_len, window_path, encoders)
            last_error = ""
            row = None
            for attempt in range(1, max(1, retries) + 1):
                start = time.time()
                try:
                    raw = run_video_prompt(torch, process_vision_info, model, processor, str(window_path), SCENE_FILTER_PROMPT, fps)
                    parsed, parse_error = parse_json_object(raw)
                    row = normalize_result(win, window_path, raw, parse_error, parsed, time.time() - start, "ok")
                    break
                except Exception as exc:
                    last_error = str(exc)
            if row is None:
                row = normalize_result(win, window_path, "", "", None, 0.0, "runtime_failed", last_error)
            existing[win["window_id"]] = row
            ordered = [existing[w["window_id"]] for w in windows if w["window_id"] in existing]
            write_csv(labels_path, ordered, WINDOW_FIELDS)
            print(f"[{i}/{len(pending)}] {win['window_id']} {row['valid_road_driving']} {row['scene_type']}", flush=True)

    rows = [existing[w["window_id"]] for w in windows if w["window_id"] in existing]
    write_csv(labels_path, rows, WINDOW_FIELDS)
    segments = merge_segments(rows, stride)
    write_csv(output_dir / "road_segments.csv", segments, SEGMENT_FIELDS)
    write_report(output_dir, inventory, windows, rows, segments)
    print(f"road_segments={output_dir / 'road_segments.csv'}")
    print(f"segment_count={len(segments)}")
    if args.smoke_only:
        print("smoke_only=true")


if __name__ == "__main__":
    main()
