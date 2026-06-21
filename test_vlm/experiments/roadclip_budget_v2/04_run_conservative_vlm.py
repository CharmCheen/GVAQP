#!/usr/bin/env python3
"""Run conservative Qwen3-VL pseudo-labeling on roadclip_budget_v2 clips."""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, load_config, read_csv, validate_base_paths, write_blocked, write_csv
from vlm_utils import CONSERVATIVE_RISK_PROMPT, load_qwen3_vl, parse_json_object, run_video_prompt


FIELDS = [
    "clip_id",
    "video_id",
    "segment_id",
    "start_time",
    "end_time",
    "clip_path",
    "conservative_positive",
    "risk_level",
    "affected_ego",
    "event_type",
    "starts_outside_ego_path",
    "enters_ego_path",
    "requires_ego_attention",
    "negative_reason",
    "confidence",
    "evidence",
    "raw_response",
    "runtime_sec",
    "status",
    "error_message",
]


def norm(value, allowed: set[str], default: str) -> str:
    value = str(value or "").strip().lower()
    return value if value in allowed else default


def norm_bool(value) -> str:
    return norm(value, {"true", "false", "uncertain"}, "uncertain")


def positive_by_rule(row: dict) -> str:
    if row["affected_ego"] != "true":
        return "no"
    if row["enters_ego_path"] != "true":
        return "no"
    starts_or_event = row["starts_outside_ego_path"] == "true" or row["event_type"] in {"crossing", "sudden_braking", "lane_conflict"}
    if not starts_or_event:
        return "no"
    if row["risk_level"] not in {"L2", "L3"}:
        return "no"
    if row["confidence"] not in {"medium", "high"}:
        return "no"
    return "yes"


def normalize_result(clip: dict, raw: str, parsed: dict | None, parse_error: str, runtime_sec: float, status: str, error: str = "") -> dict:
    parsed = parsed or {}
    risk = str(parsed.get("risk_level", "L0")).strip().upper()
    if risk not in {"L0", "L1", "L2", "L3"}:
        risk = "L0"
    row = {
        "clip_id": clip["clip_id"],
        "video_id": clip["video_id"],
        "segment_id": clip["segment_id"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"],
        "clip_path": clip["clip_path"],
        "conservative_positive": norm(parsed.get("conservative_positive"), {"yes", "no", "uncertain"}, "uncertain"),
        "risk_level": risk,
        "affected_ego": norm_bool(parsed.get("affected_ego")),
        "event_type": norm(
            parsed.get("event_type"),
            {"cut_in", "crossing", "sudden_braking", "lane_conflict", "close_approach", "normal_following", "dense_traffic_only", "roadside_static", "far_vehicle", "ambiguous", "none"},
            "ambiguous",
        ),
        "starts_outside_ego_path": norm_bool(parsed.get("starts_outside_ego_path")),
        "enters_ego_path": norm_bool(parsed.get("enters_ego_path")),
        "requires_ego_attention": norm_bool(parsed.get("requires_ego_attention")),
        "negative_reason": norm(
            parsed.get("negative_reason"),
            {"normal_following", "dense_traffic_only", "already_in_ego_lane", "adjacent_no_intrusion", "roadside_static", "far_vehicle", "camera_motion_apparent", "insufficient_evidence", "none"},
            "insufficient_evidence",
        ),
        "confidence": norm(parsed.get("confidence"), {"low", "medium", "high"}, "low"),
        "evidence": str(parsed.get("evidence", ""))[:1200],
        "raw_response": raw,
        "runtime_sec": f"{runtime_sec:.3f}",
        "status": status,
        "error_message": error,
    }
    if parse_error:
        row.update(
            {
                "conservative_positive": "uncertain",
                "risk_level": "L0",
                "affected_ego": "uncertain",
                "event_type": "ambiguous",
                "starts_outside_ego_path": "uncertain",
                "enters_ego_path": "uncertain",
                "requires_ego_attention": "uncertain",
                "negative_reason": "insufficient_evidence",
                "confidence": "low",
                "status": "parse_failed",
                "error_message": parse_error,
            }
        )
    else:
        row["conservative_positive"] = positive_by_rule(row)
        if row["conservative_positive"] != "yes" and row["negative_reason"] == "none":
            row["negative_reason"] = "insufficient_evidence"
    return row


def write_report(path: Path, rows: list[dict], total: int) -> None:
    valid = [r for r in rows if r["status"] in {"ok", "parse_failed"}]
    positives = [r for r in valid if r["conservative_positive"] == "yes"]
    rate = len(positives) / len(valid) if valid else 0.0
    runtime = sum(float(r.get("runtime_sec") or 0) for r in rows)
    lines = [
        "# Conservative VLM Label Report",
        "",
        f"- total clips: {total}",
        f"- completed labels: {len(rows)}",
        f"- valid labels: {len(valid)}",
        f"- positive count: {len(positives)}",
        f"- positive rate: {rate:.3f}",
        f"- total runtime sec: {runtime:.3f}",
        f"- runtime per completed clip sec: {runtime / len(rows):.3f}" if rows else "- runtime per completed clip sec: n/a",
    ]
    if rate < 0.05 or rate > 0.50:
        lines.append("- WARNING: positive rate is outside [0.05, 0.50]; predicate or dataset may be unsuitable.")
    for title, key in [("Negative Reason Distribution", "negative_reason"), ("Event Type Distribution", "event_type"), ("Status Distribution", "status")]:
        lines += ["", f"## {title}", "", f"| {key} | count |", "|---|---:|"]
        for k, v in Counter(r.get(key, "") for r in rows).most_common():
            lines.append(f"| {k} | {v} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run conservative VLM labeling on road clips.")
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
        path = write_blocked(output_dir, "BLOCKED_conservative_vlm.md", "BLOCKED: Conservative VLM", [f"missing model path `{model_path}`"])
        print(f"blocked_report={path}")
        return
    clips_path = output_dir / "clips.csv"
    if not clips_path.is_file():
        path = write_blocked(output_dir, "BLOCKED_missing_clips.md", "BLOCKED: Missing Clips", ["Run `02_make_road_clips.py` first."])
        print(f"blocked_report={path}")
        return
    clips = read_csv(clips_path)
    selected = clips[: args.limit] if args.limit else clips
    out_path = output_dir / "vlm_labels_conservative.csv"
    existing = {}
    if out_path.is_file() and not args.overwrite:
        existing = {r["clip_id"]: r for r in read_csv(out_path) if r.get("status") in {"ok", "parse_failed", "runtime_failed"}}
    pending = [c for c in selected if args.overwrite or c["clip_id"] not in existing]
    print(f"clips={len(selected)} existing={len(existing)} pending={len(pending)}")

    vlm_cfg = cfg.get("vlm") or {}
    fps = float(vlm_cfg.get("fps", 1.0))
    retries = int(vlm_cfg.get("retries", 1))
    if pending:
        print(f"Loading Qwen3-VL-32B from {model_path}", flush=True)
        torch, process_vision_info, model, processor = load_qwen3_vl(model_path)
        for i, clip in enumerate(pending, 1):
            last_error = ""
            row = None
            for _attempt in range(1, max(1, retries) + 1):
                start = time.time()
                try:
                    raw = run_video_prompt(torch, process_vision_info, model, processor, clip["clip_path"], CONSERVATIVE_RISK_PROMPT, fps)
                    parsed, parse_error = parse_json_object(raw)
                    row = normalize_result(clip, raw, parsed, parse_error, time.time() - start, "ok")
                    break
                except Exception as exc:
                    last_error = str(exc)
            if row is None:
                row = normalize_result(clip, "", None, "", 0.0, "runtime_failed", last_error)
            existing[clip["clip_id"]] = row
            ordered = [existing[c["clip_id"]] for c in selected if c["clip_id"] in existing]
            write_csv(out_path, ordered, FIELDS)
            print(f"[{i}/{len(pending)}] {clip['clip_id']} {row['conservative_positive']} {row['event_type']}", flush=True)

    rows = [existing[c["clip_id"]] for c in selected if c["clip_id"] in existing]
    write_csv(out_path, rows, FIELDS)
    write_report(output_dir / "vlm_label_report.md", rows, len(selected))
    print(f"vlm_labels={out_path}")
    print(f"completed={len(rows)}")
    if args.smoke_only:
        print("smoke_only=true")


if __name__ == "__main__":
    main()
