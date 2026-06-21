#!/usr/bin/env python3
"""Calibrate a conservative Qwen3-VL-32B predicate on a 20-clip subset."""

import argparse
import csv
import json
import math
import time
from collections import Counter
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, validate_base_paths


CALIBRATION_FIELDS = [
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "selected_reason",
    "old_vlm_relevant",
    "old_vlm_risk_level",
    "old_vlm_affected_ego",
    "old_vlm_event_type",
    "old_vlm_confidence",
]

RESULT_FIELDS = CALIBRATION_FIELDS + [
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
    "label_conservative_positive",
    "validation_reason",
    "raw_response",
]

FAILED_FIELDS = ["clip_id", "attempt", "error", "timestamp_unix"]

PROMPT = """You are a conservative driver-assistance safety verifier.
The video is recorded from the ego vehicle's front-facing dashcam.

Goal: identify ONLY clear ego-path conflict events. Be conservative.

Do NOT mark positive for ordinary traffic, many vehicles, normal following, vehicles already in the ego lane from the start, adjacent-lane vehicles that never enter the ego path, far vehicles, roadside/static vehicles, or ambiguous apparent motion caused by road curvature or ego-camera motion.

Answer these visual checks before deciding:
1. Is there an object that starts outside the ego vehicle's projected path?
2. Does the object enter, cross, or clearly intrude into the ego vehicle's projected path during this clip?
3. Is the interaction close enough or relevant enough that the ego vehicle may need to brake, slow down, or pay attention?
4. Is this merely normal following, dense traffic, roadside/static vehicles, or a vehicle already in the ego lane?
5. Is there clear visual evidence in the clip, not just possible or ambiguous motion?

Positive ONLY if all are visually supported:
- the object starts outside the ego path, or the event is crossing / sudden_braking / lane_conflict;
- the object enters, crosses, or intrudes into the ego path;
- the interaction is spatially close or clearly ego-relevant;
- visible evidence is clear within the clip;
- risk_level is L2 or L3;
- confidence is medium or high.

If evidence is ambiguous, choose conservative_positive="uncertain" or "no".

Return exactly one JSON object and no markdown:
{
  "conservative_positive": "yes|no|uncertain",
  "risk_level": "L0|L1|L2|L3",
  "affected_ego": "true|false|uncertain",
  "event_type": "cut_in|crossing|sudden_braking|lane_conflict|close_approach|normal_following|dense_traffic_only|roadside_static|far_vehicle|ambiguous|none",
  "starts_outside_ego_path": "true|false|uncertain",
  "enters_ego_path": "true|false|uncertain",
  "requires_ego_attention": "true|false|uncertain",
  "negative_reason": "normal_following|dense_traffic_only|already_in_ego_lane|adjacent_no_intrusion|roadside_static|far_vehicle|camera_motion_apparent|insufficient_evidence|none",
  "confidence": "low|medium|high",
  "evidence": "brief visual evidence"
}"""

VALID_POSITIVE = {"yes", "no", "uncertain"}
VALID_RISK = {"L0", "L1", "L2", "L3"}
VALID_BOOL = {"true", "false", "uncertain"}
VALID_EVENT = {
    "cut_in",
    "crossing",
    "sudden_braking",
    "lane_conflict",
    "close_approach",
    "normal_following",
    "dense_traffic_only",
    "roadside_static",
    "far_vehicle",
    "ambiguous",
    "none",
}
VALID_NEGATIVE = {
    "normal_following",
    "dense_traffic_only",
    "already_in_ego_lane",
    "adjacent_no_intrusion",
    "roadside_static",
    "far_vehicle",
    "camera_motion_apparent",
    "insufficient_evidence",
    "none",
}
VALID_CONFIDENCE = {"low", "medium", "high"}


def require_vlm_deps():
    try:
        import torch
        from qwen_vl_utils import process_vision_info
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    except ImportError as exc:
        fail(f"missing VLM dependency: {exc}")
    return torch, process_vision_info, AutoProcessor, Qwen3VLForConditionalGeneration


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def append_csv(path: Path, row: dict, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.is_file()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


def normalize_bool(value) -> str:
    text = str(value).strip().lower()
    if text in {"true", "yes", "1", "y"}:
        return "true"
    if text in {"false", "no", "0", "n"}:
        return "false"
    return "uncertain"


def normalize_yes_no(value) -> str:
    text = str(value).strip().lower()
    if text in {"yes", "true", "1", "positive"}:
        return "yes"
    if text in {"no", "false", "0", "negative"}:
        return "no"
    return "uncertain"


def normalize_risk(value) -> str:
    text = str(value).strip().lower()
    mapping = {
        "l0": "L0",
        "0": "L0",
        "none": "L0",
        "l1": "L1",
        "1": "L1",
        "low": "L1",
        "l2": "L2",
        "2": "L2",
        "medium": "L2",
        "moderate": "L2",
        "l3": "L3",
        "3": "L3",
        "high": "L3",
        "critical": "L3",
    }
    return mapping.get(text, "L1" if text == "uncertain" else "L0")


def normalize_event(value) -> str:
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "lane_cut_in": "cut_in",
        "cut-in": "cut_in",
        "close_following": "normal_following",
        "other": "ambiguous",
        "": "none",
    }
    text = mapping.get(text, text)
    return text if text in VALID_EVENT else "ambiguous"


def normalize_negative_reason(value) -> str:
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return text if text in VALID_NEGATIVE else "insufficient_evidence"


def normalize_confidence(value) -> str:
    text = str(value).strip().lower()
    if text in VALID_CONFIDENCE:
        return text
    try:
        score = float(text)
    except ValueError:
        return "low" if text == "uncertain" else "medium"
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def parse_json_object(raw: str) -> tuple[dict | None, str]:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text), ""
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1]), ""
        except json.JSONDecodeError as exc:
            return None, f"JSON parse error: {exc}"
    return None, "No JSON object found"


def enforce_positive(row: dict) -> tuple[int, str]:
    if row["conservative_positive"] != "yes":
        return 0, f"model conservative_positive={row['conservative_positive']}"
    checks = [
        row["affected_ego"] == "true",
        row["enters_ego_path"] == "true",
        row["starts_outside_ego_path"] == "true" or row["event_type"] in {"crossing", "sudden_braking", "lane_conflict"},
        row["requires_ego_attention"] == "true",
        row["risk_level"] in {"L2", "L3"},
        row["confidence"] in {"medium", "high"},
    ]
    if all(checks):
        return 1, "passes conservative positive definition"
    failed = []
    names = [
        "affected_ego",
        "enters_ego_path",
        "starts_outside_or_allowed_event",
        "requires_ego_attention",
        "risk_level_L2_L3",
        "confidence_medium_high",
    ]
    for name, ok in zip(names, checks):
        if not ok:
            failed.append(name)
    return 0, "failed positive definition: " + ",".join(failed)


def normalize_result(clip: dict, parsed: dict | None, raw: str, parse_error: str) -> dict:
    if parsed is None:
        row = {
            **clip,
            "conservative_positive": "uncertain",
            "risk_level": "L1",
            "affected_ego": "uncertain",
            "event_type": "ambiguous",
            "starts_outside_ego_path": "uncertain",
            "enters_ego_path": "uncertain",
            "requires_ego_attention": "uncertain",
            "negative_reason": "insufficient_evidence",
            "confidence": "low",
            "evidence": parse_error or "JSON parse failed",
            "raw_response": raw or "",
        }
    else:
        row = {
            **clip,
            "conservative_positive": normalize_yes_no(parsed.get("conservative_positive")),
            "risk_level": normalize_risk(parsed.get("risk_level")),
            "affected_ego": normalize_bool(parsed.get("affected_ego")),
            "event_type": normalize_event(parsed.get("event_type")),
            "starts_outside_ego_path": normalize_bool(parsed.get("starts_outside_ego_path")),
            "enters_ego_path": normalize_bool(parsed.get("enters_ego_path")),
            "requires_ego_attention": normalize_bool(parsed.get("requires_ego_attention")),
            "negative_reason": normalize_negative_reason(parsed.get("negative_reason", "none")),
            "confidence": normalize_confidence(parsed.get("confidence")),
            "evidence": str(parsed.get("evidence", ""))[:1200],
            "raw_response": raw or "",
        }
    label, validation = enforce_positive(row)
    row["label_conservative_positive"] = label
    row["validation_reason"] = validation
    return row


def is_valid_existing(row: dict) -> bool:
    return (
        row.get("clip_id")
        and str(row.get("raw_response", "")).strip()
        and str(row.get("conservative_positive", "")).strip().lower() in VALID_POSITIVE
        and str(row.get("risk_level", "")).strip().upper() in VALID_RISK
        and str(row.get("affected_ego", "")).strip().lower() in VALID_BOOL
        and str(row.get("event_type", "")).strip().lower() in VALID_EVENT
        and str(row.get("confidence", "")).strip().lower() in VALID_CONFIDENCE
    )


def even_sample(rows: list[dict], n: int) -> list[dict]:
    if len(rows) <= n:
        return rows
    if n <= 1:
        return [rows[0]]
    out = []
    for i in range(n):
        idx = round(i * (len(rows) - 1) / (n - 1))
        out.append(rows[idx])
    return out


def build_calibration_set(output_dir: Path, full_run: bool) -> list[dict]:
    proxy_rows = read_csv(output_dir / "proxy_scores.csv")
    labels_rows = read_csv(output_dir / "vlm_labels_strict_variants_exact_102.csv")
    review_path = output_dir / "review_pool.csv"
    review_rows = read_csv(review_path) if review_path.is_file() else []
    by_id = {row["clip_id"]: row for row in proxy_rows}
    labels_by_id = {row["clip_id"]: row for row in labels_rows}
    review_by_id = {row["clip_id"]: row for row in review_rows}

    def make_row(clip_id: str, reason: str) -> dict:
        proxy = by_id[clip_id]
        old = labels_by_id.get(clip_id, {})
        return {
            "clip_id": clip_id,
            "start_time": proxy["start_time"],
            "end_time": proxy["end_time"],
            "clip_path": proxy["clip_path"],
            "selected_reason": reason,
            "old_vlm_relevant": old.get("vlm_relevant", ""),
            "old_vlm_risk_level": old.get("vlm_risk_level", ""),
            "old_vlm_affected_ego": old.get("vlm_affected_ego", ""),
            "old_vlm_event_type": old.get("vlm_event_type", ""),
            "old_vlm_confidence": old.get("vlm_confidence", ""),
        }

    if full_run:
        return [make_row(row["clip_id"], "full_run_all_clips") for row in proxy_rows]

    selected = []
    selected_ids = set()

    def add(clip_id: str, reason: str) -> bool:
        if clip_id in selected_ids or clip_id not in by_id:
            return False
        selected.append(make_row(clip_id, reason))
        selected_ids.add(clip_id)
        return True

    strict_positive = [
        row for row in labels_rows
        if str(row.get("label_strict", "")).strip() == "1" and row["clip_id"] in by_id
    ]
    strict_positive.sort(key=lambda r: (float(r.get("start_time", 0.0)), r["clip_id"]))
    for row in even_sample(strict_positive, 10):
        add(row["clip_id"], "even_sample_old_strict_positive")

    review_negative_ids = {
        row["clip_id"] for row in review_rows
        if str(row.get("label", "")).strip() == "0"
    }
    high_count_naive = sorted(
        proxy_rows,
        key=lambda r: (max(float(r["score_count"]), float(r["score_naive"])), float(r["score_count"])),
        reverse=True,
    )
    neg_added = 0
    for row in high_count_naive:
        if neg_added >= 5:
            break
        if row["clip_id"] in review_negative_ids and add(row["clip_id"], "review_negative_high_count_naive"):
            neg_added += 1
    for row in high_count_naive:
        if neg_added >= 5:
            break
        if add(row["clip_id"], "fallback_high_count_naive"):
            neg_added += 1

    kin_added = 0
    for row in sorted(proxy_rows, key=lambda r: float(r["score_kinematic"]), reverse=True):
        if kin_added >= 5:
            break
        if add(row["clip_id"], "top_kinematic_high_score"):
            kin_added += 1

    for row in high_count_naive:
        if len(selected) >= 20:
            break
        add(row["clip_id"], "fill_to_20_high_count_naive")
    return selected[:20]


def build_messages(video_path: str, fps: float) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": video_path, "fps": fps},
                {"type": "text", "text": PROMPT},
            ],
        }
    ]


def load_model(model_dir: Path):
    torch, process_vision_info, AutoProcessor, Qwen3VLForConditionalGeneration = require_vlm_deps()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(model_dir),
        dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
        local_files_only=True,
    )
    processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True)
    return torch, process_vision_info, model, processor


def run_one_clip(torch, process_vision_info, model, processor, clip_path: str, fps: float) -> str:
    messages = build_messages(clip_path, fps)
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]


def write_blocking_report(path: Path, missing: list[str], related: list[Path]) -> None:
    lines = [
        "# BLOCKED: Conservative VLM Calibration",
        "",
        "The calibration run could not start because required local inputs are missing.",
        "",
        "## Missing",
        "",
    ]
    lines.extend(f"- {item}" for item in missing)
    lines.extend(["", "## Related Files Found", ""])
    lines.extend(f"- `{p}`" for p in related) if related else lines.append("- none")
    lines.extend(
        [
            "",
            "Expected inputs include proxy_scores.csv, vlm_labels_strict_variants_exact_102.csv, clip files, and the local Qwen3-VL-32B model directory.",
            "No calibration labels were fabricated.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(path: Path, calibration_rows: list[dict], result_rows: list[dict], full_run: bool = False) -> None:
    old_strict_count = sum(1 for row in calibration_rows if row.get("old_vlm_affected_ego") == "true" and row.get("old_vlm_risk_level") in {"L2", "L3"})
    result_by_id = {row["clip_id"]: row for row in result_rows}
    completed = [row for row in calibration_rows if row["clip_id"] in result_by_id]
    positives = [result_by_id[row["clip_id"]] for row in completed if int(result_by_id[row["clip_id"]].get("label_conservative_positive", 0)) == 1]
    new_positive_count = len(positives)
    positive_rate = new_positive_count / len(completed) if completed else 0.0
    old_strict_to_no = 0
    old_strict_to_uncertain = 0
    negative_reasons = Counter()
    for cal in completed:
        res = result_by_id[cal["clip_id"]]
        old_strict = cal.get("old_vlm_affected_ego") == "true" and cal.get("old_vlm_risk_level") in {"L2", "L3"}
        if int(res.get("label_conservative_positive", 0)) == 0:
            negative_reasons[res.get("negative_reason", "insufficient_evidence")] += 1
            if old_strict and res.get("conservative_positive") == "no":
                old_strict_to_no += 1
            if old_strict and res.get("conservative_positive") == "uncertain":
                old_strict_to_uncertain += 1

    if positive_rate > 0.50:
        judgment = "positive rate is still >50%; the conservative prompt is still too broad for rare-risk retrieval."
        recommend = "Do not proceed directly to full 102 labeling without tightening the prompt again."
    elif 0.10 <= positive_rate <= 0.30:
        judgment = "positive rate is in the 10%-30% target range; this predicate is a plausible full-run candidate."
        recommend = "Use this conservative pseudo-GT for budget simulation and policy sweep." if full_run else "Recommend full 102 conservative labeling if this calibration set looks qualitatively acceptable."
    elif positive_rate < 0.05:
        judgment = "positive rate is <5%; the prompt may be too strict."
        recommend = "Do not full-run until deciding whether this rare predicate is intended."
    else:
        judgment = "positive rate is outside the preferred 10%-30% band but not extreme."
        recommend = "Full run is possible only if this positive rate is acceptable for the next experiment."

    title = "# Conservative 102-Clip VLM Predicate Full-Run Report" if full_run else "# Conservative VLM Predicate Calibration Report"
    intro = (
        "This report uses all 102 clips and a more conservative Qwen3-VL-32B prompt. These are still VLM pseudo labels, not human ground truth."
        if full_run
        else "This report uses a 20-clip calibration subset and a more conservative Qwen3-VL-32B prompt. These are still VLM pseudo labels, not human ground truth."
    )
    count_label = "full-run clip count" if full_run else "calibration clip count"
    old_count_label = "old strict positive count in completed full-run set" if full_run else "old strict positive count in completed calibration set"
    lines = [
        title,
        "",
        intro,
        "",
        f"1. {count_label}: {len(completed)} completed / {len(calibration_rows)} selected",
        f"2. {old_count_label}: {old_strict_count}",
        f"3. new conservative positive count: {new_positive_count}",
        f"4. new positive rate: {positive_rate:.3f}",
        f"5. old strict -> conservative no: {old_strict_to_no}",
        f"6. old strict -> conservative uncertain: {old_strict_to_uncertain}",
        "",
        "## Conservative Positives",
        "",
        "| clip_id | event_type | evidence |",
        "|---|---|---|",
    ]
    for row in positives:
        lines.append(f"| {row['clip_id']} | {row['event_type']} | {str(row.get('evidence', ''))[:240]} |")
    if not positives:
        lines.append("| none |  |  |")
    lines.extend(["", "## Conservative Negative Reasons", "", "| negative_reason | count |", "|---|---:|"])
    for reason, count in negative_reasons.most_common():
        lines.append(f"| {reason} | {count} |")
    if not negative_reasons:
        lines.append("| none | 0 |")
    lines.extend(
        [
            "",
            "## Judgment",
            "",
            f"- {judgment}",
            f"- {recommend}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate conservative Qwen3-VL-32B predicate on selected clips.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--limit", type=int, default=0, help="Run only first N selected clips.")
    parser.add_argument("--full-run", action="store_true", help="Select all 102 clips. Do not use unless explicitly requested.")
    parser.add_argument("--overwrite", action="store_true", help="Re-run clips already present in output CSV.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    conservative_cfg = cfg.get("conservative_vlm_calibration") or {}
    model_path = Path(conservative_cfg.get("model_path", (cfg.get("exact_vlm_labels") or {}).get("model_path", "")))
    if args.full_run:
        out_csv = Path(conservative_cfg.get("full_output_csv", output_dir / "vlm_labels_conservative_exact_102.csv"))
        set_csv = Path(conservative_cfg.get("full_set_csv", output_dir / "conservative_full_set_102.csv"))
        failed_csv = Path(conservative_cfg.get("full_failed_csv", output_dir / "vlm_labels_conservative_exact_102_failed.csv"))
        report_path = Path(conservative_cfg.get("full_report_md", output_dir / "conservative_vlm_full_102_report.md"))
    else:
        out_csv = Path(conservative_cfg.get("output_csv", output_dir / "vlm_labels_conservative_calibration_20.csv"))
        set_csv = Path(conservative_cfg.get("calibration_set_csv", output_dir / "conservative_calibration_set.csv"))
        failed_csv = Path(conservative_cfg.get("failed_csv", output_dir / "vlm_labels_conservative_calibration_20_failed.csv"))
        report_path = Path(conservative_cfg.get("report_md", output_dir / "conservative_vlm_calibration_report.md"))
    fps = float(conservative_cfg.get("fps", 1.0))
    retries = int(conservative_cfg.get("retries", 1))

    missing = []
    for input_path in [output_dir / "proxy_scores.csv", output_dir / "vlm_labels_strict_variants_exact_102.csv"]:
        if not input_path.is_file():
            missing.append(f"missing input file: `{input_path}`")
    if not model_path.is_dir():
        missing.append(f"missing local Qwen3-VL-32B model directory: `{model_path}`")
    related = [p for p in [output_dir / "vlm_labels_exact_102.csv", output_dir / "review_pool.csv", model_path] if p.exists()]
    if missing:
        block_path = output_dir / "BLOCKED_conservative_vlm_calibration.md"
        write_blocking_report(block_path, missing, related)
        fail(f"blocked conservative calibration. Wrote {block_path}")

    calibration_rows = build_calibration_set(output_dir, args.full_run)
    if args.limit > 0:
        calibration_rows = calibration_rows[: args.limit]
    for row in calibration_rows:
        if not Path(row["clip_path"]).is_file():
            fail(f"selected clip_path not found: {row['clip_path']}")
    write_csv(set_csv, calibration_rows, CALIBRATION_FIELDS)

    existing = {}
    if out_csv.is_file() and not args.overwrite:
        for row in read_csv(out_csv):
            if is_valid_existing(row):
                existing[row["clip_id"]] = row
    pending = [row for row in calibration_rows if args.overwrite or row["clip_id"] not in existing]
    print(f"selected={len(calibration_rows)} existing_valid={len(existing)} pending={len(pending)}")
    if pending:
        print(f"Loading Qwen3-VL-32B from {model_path}")
        torch, process_vision_info, model, processor = load_model(model_path)
        for i, clip in enumerate(pending, start=1):
            print(f"[{i}/{len(pending)}] {clip['clip_id']}", flush=True)
            last_error = ""
            for attempt in range(1, max(1, retries) + 1):
                try:
                    raw = run_one_clip(torch, process_vision_info, model, processor, clip["clip_path"], fps)
                    parsed, parse_error = parse_json_object(raw)
                    row = normalize_result(clip, parsed, raw, parse_error)
                    existing[clip["clip_id"]] = row
                    break
                except Exception as exc:
                    last_error = str(exc)
                    append_csv(failed_csv, {"clip_id": clip["clip_id"], "attempt": attempt, "error": last_error, "timestamp_unix": int(time.time())}, FAILED_FIELDS)
                    print(f"  attempt={attempt} error={last_error}", flush=True)
            if clip["clip_id"] not in existing:
                row = normalize_result(clip, None, "", f"runtime_error: {last_error}")
                existing[clip["clip_id"]] = row
            print(
                f"  positive={existing[clip['clip_id']]['label_conservative_positive']} "
                f"event={existing[clip['clip_id']]['event_type']} "
                f"reason={existing[clip['clip_id']]['validation_reason']}",
                flush=True,
            )
            ordered_rows = [existing[row["clip_id"]] for row in calibration_rows if row["clip_id"] in existing]
            write_csv(out_csv, ordered_rows, RESULT_FIELDS)
    result_rows = [existing[row["clip_id"]] for row in calibration_rows if row["clip_id"] in existing]
    write_csv(out_csv, result_rows, RESULT_FIELDS)
    write_report(report_path, calibration_rows, result_rows, full_run=args.full_run)
    print(f"calibration_set={set_csv}")
    print(f"conservative_labels={out_csv}")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
