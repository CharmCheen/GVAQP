#!/usr/bin/env python3
"""Parameterized cheap feature precompute for query_runtime_v1.

No VLM, no oracle labels, no probe labels. The output schema mirrors the V13
center10 proxy features consumed by the runtime selector.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "video_feature_precompute_v1"
LOGS = OUT / "logs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_progress(checkpoint: str, command: str, result: str, failure: str = "none", fix: str = "none", next_action: str = "") -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "progress.md").open("a") as f:
        f.write(f"\n## {utc_now()} - {checkpoint}\n\n")
        f.write(f"- Checkpoint: {checkpoint}\n")
        f.write(f"- Commands run: `{command}`\n")
        f.write(f"- Result: {result}\n")
        f.write(f"- Failure: {failure}\n")
        f.write(f"- Fix applied: {fix}\n")
        if next_action:
            f.write(f"- Next action: {next_action}\n")


def ffprobe_metadata(video_path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,nb_frames:format=duration,bit_rate,format_name",
        "-of",
        "json",
        str(video_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    raw = json.loads(proc.stdout)
    stream = raw["streams"][0]
    fmt = raw["format"]
    fps_text = stream.get("r_frame_rate", "0/1")
    num, den = fps_text.split("/")
    fps = float(num) / max(1.0, float(den))
    return {
        "video_path": str(video_path),
        "format_name": fmt.get("format_name", ""),
        "duration_seconds": float(fmt["duration"]),
        "bit_rate": fmt.get("bit_rate", ""),
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "fps": fps,
        "nb_frames": stream.get("nb_frames", ""),
    }


def build_coarse_grid(video_path: Path, video_id: str, duration: float, clip_duration: float) -> list[dict]:
    rows = []
    n = int(math.ceil(duration / clip_duration))
    for i in range(n):
        start = i * clip_duration
        end = min(duration, start + clip_duration)
        rows.append(
            {
                "clip_id": f"{video_id}_coarse_{i:04d}",
                "video_id": video_id,
                "source_video_path": str(video_path),
                "start_time": f"{start:.3f}",
                "end_time": f"{end:.3f}",
                "duration": f"{end - start:.3f}",
                "split": "coarse_5s",
            }
        )
    return rows


def compute_motion(video_path: Path, clips: list[dict], motion_fps: float, resize_wh: tuple[int, int]) -> dict[str, dict]:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    interval = max(1, int(round(fps / motion_fps))) if fps > 0 else 12
    max_end = max((float(clip["end_time"]) for clip in clips), default=0.0)
    frame_data = []
    prev_gray = None
    frame_idx = 0
    while True:
        if fps > 0 and (frame_idx / fps) > max_end:
            break
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_small = cv2.resize(gray, resize_wh)
            motion = 0.0
            if prev_gray is not None:
                motion = float(np.mean(cv2.absdiff(gray_small, prev_gray)))
            frame_data.append((frame_idx / fps if fps else 0.0, motion))
            prev_gray = gray_small
        frame_idx += 1
    cap.release()

    out = {}
    j = 0
    for clip in clips:
        start = float(clip["start_time"])
        end = float(clip["end_time"])
        vals = [motion for ts, motion in frame_data if start <= ts < end]
        out[clip["clip_id"]] = {
            "motion_energy_mean": float(np.mean(vals)) if vals else 0.0,
            "motion_energy_max": float(np.max(vals)) if vals else 0.0,
            "motion_energy_std": float(np.std(vals)) if vals else 0.0,
            "motion_frames_sampled": len(vals),
        }
        j += 1
    return out


def zero_yolo(status: str) -> dict:
    row = {
        "vehicle_count_mean": 0.0,
        "vehicle_count_max": 0.0,
        "object_count_mean": 0.0,
        "object_count_max": 0.0,
        "bbox_area_sum_mean": 0.0,
        "bbox_area_sum_max": 0.0,
        "max_bbox_area_mean": 0.0,
        "max_bbox_area_max": 0.0,
        "center_roi_vehicle_count_mean": 0.0,
        "bottom_roi_vehicle_count_mean": 0.0,
        "yolo_status": status,
    }
    return row


def compute_yolo(video_path: Path, clips: list[dict], model_path: Path, device: str) -> tuple[dict[str, dict], str]:
    if not model_path.exists():
        return {c["clip_id"]: zero_yolo("model_not_found") for c in clips}, "MODEL_NOT_FOUND"
    try:
        import torch
        from ultralytics import YOLO
    except Exception as exc:
        return {c["clip_id"]: zero_yolo(f"import_error:{str(exc)[:60]}") for c in clips}, f"IMPORT_ERROR:{exc}"

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = YOLO(str(model_path))
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out = {}
    ok = fail = skip = 0
    for clip in clips:
        mid = (float(clip["start_time"]) + float(clip["end_time"])) / 2.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(mid * fps))
        ret, frame = cap.read()
        if not ret:
            out[clip["clip_id"]] = zero_yolo("frame_read_failed")
            skip += 1
            continue
        try:
            results = model(frame, device=device, verbose=False)
            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                out[clip["clip_id"]] = zero_yolo("no_detections")
                ok += 1
                continue
            cls_ids = boxes.cls.cpu().numpy()
            xyxy = boxes.xyxy.cpu().numpy()
            areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
            frame_h, frame_w = frame.shape[:2]
            vehicle_mask = np.isin(cls_ids, [2, 3, 5, 7])
            cx = (xyxy[:, 0] + xyxy[:, 2]) / 2.0
            cy_bottom = xyxy[:, 3]
            center_mask = (cx > frame_w / 3.0) & (cx < 2.0 * frame_w / 3.0) & (cy_bottom > frame_h / 3.0) & (cy_bottom < 2.0 * frame_h / 3.0)
            bottom_mask = cy_bottom > 2.0 * frame_h / 3.0
            vehicle_count = float(vehicle_mask.sum())
            object_count = float(len(cls_ids))
            area_sum = float(areas.sum()) if len(areas) else 0.0
            max_area = float(areas.max()) if len(areas) else 0.0
            out[clip["clip_id"]] = {
                "vehicle_count_mean": vehicle_count,
                "vehicle_count_max": vehicle_count,
                "object_count_mean": object_count,
                "object_count_max": object_count,
                "bbox_area_sum_mean": area_sum,
                "bbox_area_sum_max": area_sum,
                "max_bbox_area_mean": max_area,
                "max_bbox_area_max": max_area,
                "center_roi_vehicle_count_mean": float((vehicle_mask & center_mask).sum()),
                "bottom_roi_vehicle_count_mean": float((vehicle_mask & bottom_mask).sum()),
                "yolo_status": "ok",
            }
            ok += 1
        except Exception as exc:
            out[clip["clip_id"]] = zero_yolo(f"error:{str(exc)[:80]}")
            fail += 1
    cap.release()
    return out, f"COMPLETE_{ok}_ok_{skip}_skip_{fail}_fail_device_{device}"


def merge_5s_features(clips: list[dict], motion: dict[str, dict], yolo: dict[str, dict]) -> list[dict]:
    rows = []
    for clip in clips:
        cid = clip["clip_id"]
        row = {
            "clip_id": cid,
            "video_id": clip["video_id"],
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
        }
        row.update(motion.get(cid, {}))
        row.update(yolo.get(cid, zero_yolo("not_attempted")))
        rows.append(row)
    return rows


def build_center10_grid(video_path: Path, video_id: str, duration: float, interval: float, window: float) -> list[dict]:
    rows = []
    n = int(math.ceil(duration / interval))
    half = window / 2.0
    for i in range(n):
        anchor_time = min(duration, i * interval + interval / 2.0)
        start = max(0.0, anchor_time - half)
        end = min(duration, anchor_time + half)
        rows.append(
            {
                "anchor_id": f"center10_anchor_{i:04d}",
                "video_id": video_id,
                "anchor_time": f"{anchor_time:.3f}",
                "start_time": f"{start:.3f}",
                "end_time": f"{end:.3f}",
                "duration": f"{end - start:.3f}",
                "source_video_path": str(video_path),
                "construction_policy": "center_10s",
            }
        )
    return rows


def aggregate_center10(anchors: list[dict], proxy5: list[dict]) -> list[dict]:
    out = []

    def agg(rows: list[dict], key: str, fn) -> float:
        vals = [float(r[key]) for r in rows if r.get(key, "") != ""]
        return float(fn(vals)) if vals else 0.0

    for anchor in anchors:
        start = float(anchor["start_time"])
        end = float(anchor["end_time"])
        overlaps = [r for r in proxy5 if float(r["end_time"]) > start and float(r["start_time"]) < end]
        if not overlaps:
            overlaps = [proxy5[0]]
        out.append(
            {
                "anchor_id": anchor["anchor_id"],
                "anchor_time": anchor["anchor_time"],
                "num_overlapping_5s_clips": len(overlaps),
                "yolo_vehicle_mean": agg(overlaps, "vehicle_count_mean", np.mean),
                "yolo_vehicle_max": agg(overlaps, "vehicle_count_mean", np.max),
                "yolo_vehicle_sum": agg(overlaps, "vehicle_count_mean", np.sum),
                "object_count_mean": agg(overlaps, "object_count_mean", np.mean),
                "object_count_max": agg(overlaps, "object_count_mean", np.max),
                "bbox_area_sum_mean": agg(overlaps, "bbox_area_sum_mean", np.mean),
                "bbox_area_sum_max": agg(overlaps, "bbox_area_sum_mean", np.max),
                "max_bbox_area_mean": agg(overlaps, "max_bbox_area_mean", np.mean),
                "max_bbox_area_max": agg(overlaps, "max_bbox_area_mean", np.max),
                "center_roi_vehicle_count_mean": agg(overlaps, "center_roi_vehicle_count_mean", np.mean),
                "bottom_roi_vehicle_count_mean": agg(overlaps, "bottom_roi_vehicle_count_mean", np.mean),
                "motion_energy_mean": agg(overlaps, "motion_energy_mean", np.mean),
                "motion_energy_max": agg(overlaps, "motion_energy_mean", np.max),
                "motion_energy_sum": agg(overlaps, "motion_energy_mean", np.sum),
            }
        )
    arrays = {
        "yolo_vehicle_max": np.array([r["yolo_vehicle_max"] for r in out]),
        "bbox_area_sum_max": np.array([r["bbox_area_sum_max"] for r in out]),
        "motion_energy_max": np.array([r["motion_energy_max"] for r in out]),
        "center_roi_vehicle_count_mean": np.array([r["center_roi_vehicle_count_mean"] for r in out]),
    }

    def z(value: float, arr: np.ndarray) -> float:
        return float((value - np.mean(arr)) / (np.std(arr) + 1e-8))

    for row in out:
        row["z_yolo_vehicle_max"] = z(row["yolo_vehicle_max"], arrays["yolo_vehicle_max"])
        row["z_bbox_area_sum_max"] = z(row["bbox_area_sum_max"], arrays["bbox_area_sum_max"])
        row["z_motion_energy_max"] = z(row["motion_energy_max"], arrays["motion_energy_max"])
        row["z_center_roi_count_mean"] = z(row["center_roi_vehicle_count_mean"], arrays["center_roi_vehicle_count_mean"])
        row["score_yolo_count"] = row["z_yolo_vehicle_max"]
        row["score_yolo_geometry"] = row["z_bbox_area_sum_max"]
        row["score_motion"] = row["z_motion_energy_max"]
        row["score_fusion_yolo_motion"] = row["z_yolo_vehicle_max"] + row["z_motion_energy_max"]
        row["score_fusion_geometry_motion"] = row["z_bbox_area_sum_max"] + row["z_motion_energy_max"]
    return out


def write_score_timeline(path: Path, center_proxy: list[dict], title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not center_proxy:
        path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"960\" height=\"260\"></svg>\n")
        return

    width = 960
    height = 260
    left = 54
    right = 18
    top = 32
    bottom = 34
    plot_w = width - left - right
    plot_h = height - top - bottom
    times = np.array([float(row["anchor_time"]) for row in center_proxy], dtype=float)
    yolo = np.array([float(row["yolo_vehicle_max"]) for row in center_proxy], dtype=float)
    motion = np.array([float(row["motion_energy_max"]) for row in center_proxy], dtype=float)
    t_min = float(times.min())
    t_max = float(times.max())

    def normalize(values: np.ndarray) -> np.ndarray:
        v_min = float(values.min())
        v_max = float(values.max())
        if abs(v_max - v_min) < 1e-8:
            return np.zeros_like(values)
        return (values - v_min) / (v_max - v_min)

    def points(values: np.ndarray) -> str:
        norm = normalize(values)
        coords = []
        for t, v in zip(times, norm):
            x = left + ((float(t) - t_min) / max(1e-8, t_max - t_min)) * plot_w
            y = top + (1.0 - float(v)) * plot_h
            coords.append(f"{x:.1f},{y:.1f}")
        return " ".join(coords)

    yolo_points = points(yolo)
    motion_points = points(motion)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="#ffffff"/>
  <text x="{left}" y="21" font-family="Arial, sans-serif" font-size="15" fill="#111827">{title}</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#9ca3af" stroke-width="1"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#9ca3af" stroke-width="1"/>
  <polyline points="{yolo_points}" fill="none" stroke="#2563eb" stroke-width="2"/>
  <polyline points="{motion_points}" fill="none" stroke="#dc2626" stroke-width="2" opacity="0.85"/>
  <text x="{left}" y="{height - 10}" font-family="Arial, sans-serif" font-size="11" fill="#374151">anchor_time_seconds: {t_min:.1f} to {t_max:.1f}</text>
  <rect x="{width - 255}" y="13" width="12" height="12" fill="#2563eb"/>
  <text x="{width - 238}" y="23" font-family="Arial, sans-serif" font-size="11" fill="#374151">yolo_vehicle_max normalized</text>
  <rect x="{width - 255}" y="31" width="12" height="12" fill="#dc2626"/>
  <text x="{width - 238}" y="41" font-family="Arial, sans-serif" font-size="11" fill="#374151">motion_energy_max normalized</text>
</svg>
"""
    path.write_text(svg)


def write_report(report_path: Path, title: str, summary: dict, sanity: list[dict], decision: str) -> None:
    lines = [
        f"# {title}",
        "",
        "Date: 2026-07-03",
        "",
        "## Scope",
        "",
        "This stage converts an input video into the cheap feature CSVs consumed by `query_runtime_v1`. It runs no VLM, reads no oracle labels, and reads no probe labels.",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- `{key}`: `{value}`.")
    lines.extend(["", "## Sanity Checks", "", "| Check | Status | Details |", "|---|---|---|"])
    for row in sanity:
        lines.append(f"| {row['check']} | {row['status']} | {row['details']} |")
    if "score_timeline_figure" in summary:
        lines.extend(["", "## Figure", "", f"- Score timeline: `{summary['score_timeline_figure']}`."])
    lines.extend(["", f"FINAL_DECISION: {decision}"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="data/realcam/long_video_data/long_video_dataset3.mp4")
    parser.add_argument("--video-id", default="long_video_dataset3")
    parser.add_argument("--run-name", default="tables")
    parser.add_argument("--max-duration", type=float, default=0.0)
    parser.add_argument("--clip-duration", type=float, default=5.0)
    parser.add_argument("--anchor-interval", type=float, default=10.0)
    parser.add_argument("--anchor-window", type=float, default=10.0)
    parser.add_argument("--motion-fps", type=float, default=2.0)
    parser.add_argument("--yolo-model", default="models/yolo/yolov8n.pt")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--skip-yolo", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video_path = resolve(args.video)
    model_path = resolve(args.yolo_model)
    table_dir = OUT / args.run_name
    report_dir = OUT / "reports"
    table_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    metadata = ffprobe_metadata(video_path)
    effective_duration = min(metadata["duration_seconds"], args.max_duration) if args.max_duration > 0 else metadata["duration_seconds"]
    metadata["effective_duration_seconds"] = effective_duration
    (table_dir / "video_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    coarse = build_coarse_grid(video_path, args.video_id, effective_duration, args.clip_duration)
    motion = compute_motion(video_path, coarse, args.motion_fps, (320, 180))
    if args.skip_yolo:
        yolo = {c["clip_id"]: zero_yolo("skipped_by_user") for c in coarse}
        yolo_status = "SKIPPED_BY_USER"
    else:
        yolo, yolo_status = compute_yolo(video_path, coarse, model_path, args.device)
    proxy5 = merge_5s_features(coarse, motion, yolo)
    anchors = build_center10_grid(video_path, args.video_id, effective_duration, args.anchor_interval, args.anchor_window)
    center_proxy = aggregate_center10(anchors, proxy5)

    write_csv(table_dir / "coarse_5s_clip_grid.csv", coarse)
    write_csv(table_dir / "proxy_features_5s.csv", proxy5)
    write_csv(table_dir / "center10_anchor_grid.csv", anchors)
    write_csv(table_dir / "center10_proxy_features.csv", center_proxy)
    figure_path = OUT / "figures" / f"{args.run_name}_score_timeline.svg"
    write_score_timeline(figure_path, center_proxy, f"{args.video_id} cheap proxy timeline ({args.run_name})")

    forbidden = ["vlm", "oracle", "label", "event_start", "event_end", "positive", "negative"]
    forbidden_fields = [field for field in center_proxy[0] if any(tok in field.lower() for tok in forbidden)]
    yolo_ok = sum(1 for row in proxy5 if row.get("yolo_status") == "ok")
    sanity = [
        {"check": "video_readable", "status": "PASS" if metadata["duration_seconds"] > 0 else "FAIL", "details": f"duration={metadata['duration_seconds']:.3f}s"},
        {"check": "coarse_grid_nonempty", "status": "PASS" if coarse else "FAIL", "details": f"rows={len(coarse)}"},
        {"check": "center10_grid_nonempty", "status": "PASS" if anchors else "FAIL", "details": f"rows={len(anchors)}"},
        {"check": "required_runtime_score_column_present", "status": "PASS" if center_proxy and "yolo_vehicle_max" in center_proxy[0] else "FAIL", "details": "score column yolo_vehicle_max"},
        {"check": "proxy_table_has_no_oracle_fields", "status": "PASS" if not forbidden_fields else "FAIL", "details": ",".join(forbidden_fields) if forbidden_fields else "none"},
        {"check": "yolo_completed_or_explicitly_skipped", "status": "PASS" if args.skip_yolo or yolo_ok > 0 else "FAIL", "details": yolo_status},
    ]
    write_csv(table_dir / "sanity_checks.csv", sanity)
    summary = {
        "video_path": str(video_path),
        "video_id": args.video_id,
        "source_duration_seconds": f"{metadata['duration_seconds']:.3f}",
        "effective_duration_seconds": f"{effective_duration:.3f}",
        "coarse_5s_rows": len(coarse),
        "center10_rows": len(anchors),
        "yolo_status": yolo_status,
        "elapsed_seconds": f"{time.time() - t0:.3f}",
        "output_table_dir": str(table_dir),
        "score_timeline_figure": str(figure_path),
    }
    write_csv(table_dir / "precompute_summary.csv", [summary])
    decision = "NO-GO" if any(row["status"] == "FAIL" for row in sanity) else "GO"
    title = f"Video Feature Precompute v1 {'Smoke' if args.run_name != 'tables' else 'Final'} Report"
    report_path = report_dir / ("SMOKE_REPORT.md" if args.run_name != "tables" else "FINAL_REPORT.md")
    write_report(report_path, title, summary, sanity, decision)
    if args.run_name == "tables":
        (OUT / "FINAL_REPORT.md").write_text(report_path.read_text())
    (OUT / "reproducible_commands.md").write_text(
        "# Reproducible Commands\n\n"
        "```bash\n"
        "python outputs/video_feature_precompute_v1/scripts/precompute_video_features.py --video data/realcam/long_video_data/long_video_dataset3.mp4 --video-id long_video_dataset3 --run-name smoke_tables --max-duration 300\n"
        "python outputs/video_feature_precompute_v1/scripts/precompute_video_features.py --video data/realcam/long_video_data/long_video_dataset3.mp4 --video-id long_video_dataset3 --run-name tables\n"
        "```\n"
    )
    append_progress(
        "Run video feature precompute",
        "python outputs/video_feature_precompute_v1/scripts/precompute_video_features.py ...",
        f"{args.run_name}: center10_rows={len(anchors)}, decision={decision}, elapsed={time.time() - t0:.1f}s.",
        failure="; ".join(r["check"] for r in sanity if r["status"] == "FAIL") or "none",
        next_action="Run query runtime against generated center10 feature tables.",
    )
    if decision == "NO-GO":
        raise SystemExit("Precompute sanity failed")


if __name__ == "__main__":
    main()
