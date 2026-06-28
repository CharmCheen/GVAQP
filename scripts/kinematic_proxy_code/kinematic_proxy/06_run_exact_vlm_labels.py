#!/usr/bin/env python3
"""Run exact clip_id-level Qwen3-VL-32B labels for kinematic proxy clips."""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, validate_base_paths


FIELDNAMES = [
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "vlm_relevant",
    "vlm_risk_level",
    "vlm_affected_ego",
    "vlm_event_type",
    "vlm_confidence",
    "vlm_reason",
    "raw_response",
]

FAILED_FIELDNAMES = [
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "attempt",
    "error",
    "timestamp_unix",
]

PROMPT = """You are a strict driver-assistance safety analyst.
The video is recorded from the ego vehicle's front-facing dashcam.

Task: determine whether this short clip contains a traffic interaction relevant to semantic driving-risk clip retrieval.

Rules:
1. Ignore subtitles, OSD, timestamps, occlusion bars, black borders, and other overlays.
2. Do not label high risk merely because many vehicles are visible.
3. Set vlm_affected_ego=true only when a vehicle, pedestrian, cyclist, or other object has a clear spatial interaction with the ego vehicle's future driving path.
4. Normal following, roadside parking, distant vehicles, and dense traffic without a clear conflict should be L0 or L1.
5. dense traffic only is not a strict positive.
6. Use L2 or L3 only for cut-ins, crossing traffic, close approach, sudden braking, lane conflict, or similar events that may affect ego driving.
7. If evidence is insufficient, use uncertain rather than forcing a label.

Return exactly one JSON object and no markdown:
{
  "vlm_relevant": "yes|no|uncertain",
  "vlm_risk_level": "L0|L1|L2|L3",
  "vlm_affected_ego": "true|false|uncertain",
  "vlm_event_type": "cut_in|crossing|close_following|sudden_braking|lane_conflict|dense_traffic_only|roadside_static|other|none",
  "vlm_confidence": "low|medium|high",
  "vlm_reason": "brief explanation"
}"""

VALID_RELEVANT = {"yes", "no", "uncertain"}
VALID_RISK = {"L0", "L1", "L2", "L3"}
VALID_AFFECTED = {"true", "false", "uncertain"}
VALID_EVENT = {
    "cut_in",
    "crossing",
    "close_following",
    "sudden_braking",
    "lane_conflict",
    "dense_traffic_only",
    "roadside_static",
    "other",
    "none",
}
VALID_CONF = {"low", "medium", "high"}


def require_vlm_deps():
    try:
        import torch
        from qwen_vl_utils import process_vision_info
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    except ImportError as exc:
        fail(f"missing VLM dependency: {exc}")
    return torch, process_vision_info, AutoProcessor, Qwen3VLForConditionalGeneration


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


def normalize_relevant(value) -> str:
    text = str(value).strip().lower()
    if text in {"yes", "true", "1", "relevant", "positive"}:
        return "yes"
    if text in {"no", "false", "0", "irrelevant", "negative"}:
        return "no"
    return "uncertain"


def normalize_risk(value) -> str:
    text = str(value).strip().lower()
    mapping = {
        "l0": "L0",
        "0": "L0",
        "none": "L0",
        "no relevant traffic risk": "L0",
        "normal": "L0",
        "normal_driving": "L0",
        "l1": "L1",
        "1": "L1",
        "low": "L1",
        "weak": "L1",
        "ambiguous": "L1",
        "l2": "L2",
        "2": "L2",
        "medium": "L2",
        "moderate": "L2",
        "clear": "L2",
        "l3": "L3",
        "3": "L3",
        "high": "L3",
        "critical": "L3",
    }
    return mapping.get(text, "L1" if text == "uncertain" else "L0")


def normalize_affected(value) -> str:
    text = str(value).strip().lower()
    if text in {"true", "yes", "1", "affected"}:
        return "true"
    if text in {"false", "no", "0", "not_affected", "none"}:
        return "false"
    return "uncertain"


def normalize_event(value) -> str:
    text = str(value).strip().lower()
    mapping = {
        "lane_cut_in": "cut_in",
        "cut-in": "cut_in",
        "pedestrian_or_bike_conflict": "crossing",
        "pedestrian_or_bike_crossing": "crossing",
        "near_collision": "other",
        "abnormal_lane_change": "lane_conflict",
        "normal_driving": "none",
        "ego_static_no_conflict": "none",
        "": "none",
    }
    text = mapping.get(text, text)
    return text if text in VALID_EVENT else "other"


def normalize_confidence(value) -> str:
    text = str(value).strip().lower()
    if text in VALID_CONF:
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


def uncertain_row(clip: dict, raw_response: str, reason: str) -> dict:
    return {
        "clip_id": clip["clip_id"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"],
        "clip_path": clip["clip_path"],
        "vlm_relevant": "uncertain",
        "vlm_risk_level": "L1",
        "vlm_affected_ego": "uncertain",
        "vlm_event_type": "other",
        "vlm_confidence": "low",
        "vlm_reason": reason,
        "raw_response": raw_response or "",
    }


def normalize_result(clip: dict, parsed: dict | None, raw_response: str, parse_error: str) -> dict:
    if not parsed:
        return uncertain_row(clip, raw_response, parse_error or "JSON parse failed")
    return {
        "clip_id": clip["clip_id"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"],
        "clip_path": clip["clip_path"],
        "vlm_relevant": normalize_relevant(parsed.get("vlm_relevant", "uncertain")),
        "vlm_risk_level": normalize_risk(parsed.get("vlm_risk_level", "L0")),
        "vlm_affected_ego": normalize_affected(parsed.get("vlm_affected_ego", "uncertain")),
        "vlm_event_type": normalize_event(parsed.get("vlm_event_type", "other")),
        "vlm_confidence": normalize_confidence(parsed.get("vlm_confidence", "medium")),
        "vlm_reason": str(parsed.get("vlm_reason", ""))[:1000],
        "raw_response": raw_response or "",
    }


def is_valid_result(row: dict) -> bool:
    return (
        str(row.get("clip_id", "")).strip()
        and str(row.get("raw_response", "")).strip()
        and str(row.get("vlm_relevant", "")).strip().lower() in VALID_RELEVANT
        and str(row.get("vlm_risk_level", "")).strip().upper() in VALID_RISK
        and str(row.get("vlm_affected_ego", "")).strip().lower() in VALID_AFFECTED
        and str(row.get("vlm_event_type", "")).strip().lower() in VALID_EVENT
        and str(row.get("vlm_confidence", "")).strip().lower() in VALID_CONF
    )


def read_csv_dicts(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"required CSV not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_results(path: Path, rows_by_id: dict[str, dict], ordered_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for clip_id in ordered_ids:
            row = rows_by_id.get(clip_id)
            if row:
                writer.writerow({name: row.get(name, "") for name in FIELDNAMES})


def append_failed(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.is_file()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FAILED_FIELDNAMES)
        if not exists:
            writer.writeheader()
        writer.writerow({name: row.get(name, "") for name in FAILED_FIELDNAMES})


def load_existing_results(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {str(row.get("clip_id", "")): row for row in rows if row.get("clip_id")}


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
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [
        out_ids[len(in_ids) :]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    return processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]


def write_blocking_report(path: Path, cfg: dict, missing: list[str], related: list[Path]) -> None:
    output_csv = cfg.get("exact_vlm_labels", {}).get(
        "output_csv",
        "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels_exact_102.csv",
    )
    lines = [
        "# BLOCKED: Exact 102-Clip VLM32B Labeling",
        "",
        "Exact clip_id-level VLM pseudo-labeling was not run because required local inputs are missing.",
        "",
        "## Missing Requirements",
        "",
    ]
    lines.extend(f"- {item}" for item in missing)
    lines.extend(
        [
            "",
            "## Related Files Found",
            "",
        ]
    )
    if related:
        lines.extend(f"- `{p}`" for p in related)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Required User Input",
            "",
            "- Provide the local Qwen3-VL-32B model directory or set `exact_vlm_labels.model_path` in `config.yaml`.",
            "- Provide `proxy_scores.csv` with `clip_id,start_time,end_time,clip_path` under the kinematic proxy output directory.",
            "- Ensure each `clip_path` points to an existing local clip video.",
            "",
            "## Expected Output",
            "",
            f"`{output_csv}`",
            "",
            "```text",
            ",".join(FIELDNAMES),
            "```",
            "",
            "The VLM labels are pseudo-GT for budget allocation experiments, not human ground truth.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_exact_cfg(cfg: dict, output_dir: Path) -> dict:
    exact = cfg.get("exact_vlm_labels") or {}
    return {
        "model_path": Path(
            exact.get(
                "model_path",
                "/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct",
            )
        ),
        "output_csv": Path(exact.get("output_csv", output_dir / "vlm_labels_exact_102.csv")),
        "failed_csv": Path(exact.get("failed_csv", output_dir / "vlm_labels_exact_102_failed.csv")),
        "fps": float(exact.get("fps", 1.0)),
        "retries": int(exact.get("retries", 1)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run exact Qwen3-VL-32B labels for 102 proxy clips.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--limit", type=int, default=0, help="Process first N pending clips only; 0 means all.")
    parser.add_argument("--model", type=Path, default=None, help="Override local Qwen3-VL-32B model directory.")
    parser.add_argument("--out", type=Path, default=None, help="Override exact label CSV output path.")
    parser.add_argument("--fps", type=float, default=None, help="Override video sampling FPS.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    exact_cfg = resolve_exact_cfg(cfg, output_dir)
    if args.model is not None:
        exact_cfg["model_path"] = args.model
    if args.out is not None:
        exact_cfg["output_csv"] = args.out
    if args.fps is not None:
        exact_cfg["fps"] = args.fps

    output_csv = exact_cfg["output_csv"]
    failed_csv = exact_cfg["failed_csv"]
    block_path = output_dir / "BLOCKED_exact_102_vlm.md"
    proxy_path = output_dir / "proxy_scores.csv"

    missing = []
    if not exact_cfg["model_path"].is_dir():
        missing.append(f"Qwen3-VL-32B model directory not found: `{exact_cfg['model_path']}`")
    if not proxy_path.is_file():
        missing.append(f"proxy_scores.csv not found: `{proxy_path}`")

    related = [
        p
        for p in [
            Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/scripts/run_qwen3_vl_batch.py"),
            Path("/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"),
            Path("/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/qwen3_vl_32b_round2_5k_raw_fps1_review.csv"),
        ]
        if p.exists()
    ]
    if missing:
        write_blocking_report(block_path, cfg, missing, related)
        fail(f"blocked exact VLM labeling. Wrote {block_path}")

    clips = read_csv_dicts(proxy_path)
    required = {"clip_id", "start_time", "end_time", "clip_path"}
    if clips and not required.issubset(clips[0].keys()):
        write_blocking_report(
            block_path,
            cfg,
            [f"proxy_scores.csv missing columns: {sorted(required - set(clips[0].keys()))}"],
            related,
        )
        fail(f"blocked exact VLM labeling. Wrote {block_path}")
    missing_clips = [row for row in clips if not Path(row["clip_path"]).is_file()]
    if missing_clips:
        examples = ", ".join(row["clip_path"] for row in missing_clips[:3])
        write_blocking_report(block_path, cfg, [f"{len(missing_clips)} clip_path files missing, e.g. {examples}"], related)
        fail(f"blocked exact VLM labeling. Wrote {block_path}")

    ordered_ids = [row["clip_id"] for row in clips]
    results = load_existing_results(output_csv)
    done_ids = {cid for cid, row in results.items() if is_valid_result(row)}
    pending = [row for row in clips if row["clip_id"] not in done_ids]
    if args.limit > 0:
        pending = pending[: args.limit]

    print(f"proxy_clips={len(clips)} existing_valid={len(done_ids)} pending_this_run={len(pending)}")
    if not pending:
        write_results(output_csv, results, ordered_ids)
        print(f"exact_labels={output_csv}")
        return

    print(f"Loading Qwen3-VL-32B from {exact_cfg['model_path']}")
    torch, process_vision_info, model, processor = load_model(exact_cfg["model_path"])

    for i, clip in enumerate(pending, start=1):
        clip_id = clip["clip_id"]
        print(f"[{i}/{len(pending)}] {clip_id}", flush=True)
        success = False
        last_error = ""
        for attempt in range(1, max(1, exact_cfg["retries"]) + 1):
            try:
                t0 = time.time()
                raw = run_one_clip(
                    torch,
                    process_vision_info,
                    model,
                    processor,
                    clip["clip_path"],
                    exact_cfg["fps"],
                )
                parsed, parse_error = parse_json_object(raw)
                row = normalize_result(clip, parsed, raw, parse_error)
                results[clip_id] = row
                write_results(output_csv, results, ordered_ids)
                success = True
                print(
                    f"  relevant={row['vlm_relevant']} risk={row['vlm_risk_level']} "
                    f"ego={row['vlm_affected_ego']} json_ok={bool(parsed)} latency={time.time() - t0:.1f}s",
                    flush=True,
                )
                break
            except Exception as exc:
                last_error = str(exc)
                append_failed(
                    failed_csv,
                    {
                        "clip_id": clip_id,
                        "start_time": clip["start_time"],
                        "end_time": clip["end_time"],
                        "clip_path": clip["clip_path"],
                        "attempt": attempt,
                        "error": last_error,
                        "timestamp_unix": int(time.time()),
                    },
                )
                print(f"  attempt={attempt} error={last_error}", flush=True)
        if not success:
            results[clip_id] = uncertain_row(clip, "", f"runtime_error: {last_error}")
            write_results(output_csv, results, ordered_ids)

    print(f"exact_labels={output_csv}")
    print(f"failed_log={failed_csv}")


if __name__ == "__main__":
    main()
