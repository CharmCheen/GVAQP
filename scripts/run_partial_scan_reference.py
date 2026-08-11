#!/usr/bin/env python3
"""Evaluator-only full-context reference construction.

This executable intentionally does not import the SCAN implementation and has
no code path to scan outputs, candidates, policy traces, or candidate maps.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IMMUTABLE = ROOT / "benchmarks/partial_scan_pilot_v1/immutable"
DERIVED = ROOT / "benchmarks/partial_scan_pilot_v1/derived"
WINDOWS = DERIVED / "reference_construction/reference_windows.csv"
IDENTITIES = DERIVED / "reference_construction/input_identities.jsonl"
RAW = DERIVED / "reference_construction/raw"
ATTEMPTS = DERIVED / "reference_construction/attempt_ledger.jsonl"
REFERENCE = IMMUTABLE / "reference_events.csv"
MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
DECODE_FPS = 2.0
MAX_ATTEMPTS = 2
SEED = 20260723
INPUT_PROTOCOL_VERSION = "decoded_2fps_with_explicit_video_metadata_v4"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_text(path, frame.to_csv(index=False, lineterminator="\n"))


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prepare() -> None:
    prefreeze = json.loads((IMMUTABLE / "preexecution_freeze.json").read_text())
    query = json.loads((IMMUTABLE / "contracts/query_contract.yaml").read_text())
    reference_contract = json.loads(
        (IMMUTABLE / "contracts/reference_construction_contract.yaml").read_text()
    )
    if reference_contract["query_prompt_hash"] != query["query_prompt_hash"]:
        raise RuntimeError("Query/reference prompt mismatch")
    videos = pd.read_csv(IMMUTABLE / "videos.csv")
    rows = []
    identities = []
    for video in videos.to_dict("records"):
        duration = float(video["duration_sec"])
        starts = np.arange(0.0, duration, 15.0)
        for index, start in enumerate(starts):
            end = min(duration, start + 30.0)
            if end - start < 1.0:
                continue
            window_id = f"{video['video_id']}_rw{index:04d}"
            row = {
                "video_id": video["video_id"], "window_id": window_id,
                "start_sec": float(start), "end_sec": float(end),
                "duration_sec": float(end - start), "stride_sec": 15.0,
                "video_hash": video["video_hash"],
            }
            rows.append(row)
            identities.append({
                **row, "video_path": video["video_path"],
                "query_prompt_hash": query["query_prompt_hash"],
                "reference_contract_hash": reference_contract["contract_hash"],
                "rng_seed": SEED + len(identities),
                "identity_hash": canonical_hash(row),
            })
    frame = pd.DataFrame(rows)
    atomic_csv(WINDOWS, frame)
    atomic_text(
        IDENTITIES,
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in identities),
    )
    atomic_json(DERIVED / "audits/reference_independence_audit.json", {
        "status": "PASS_BY_CONSTRUCTION_PENDING_ORACLE_COMPLETION",
        "reference_builder_path": "scripts/run_partial_scan_reference.py",
        "reference_builder_sha256": sha256_file(Path(__file__)),
        "allowed_inputs": [
            "immutable/videos.csv", "immutable/contracts/query_contract.yaml",
            "immutable/contracts/reference_construction_contract.yaml",
            "source video bytes", "frozen local Oracle model",
        ],
        "forbidden_inputs_absent_from_builder": [
            "scan_outputs", "raw_candidates", "P0/P1/P2", "policy_runs",
            "candidate_event_map",
        ],
        "preexecution_freeze_hash": prefreeze["freeze_hash"],
        "window_count": len(frame),
    })
    print(json.dumps({
        "REFERENCE_PREPARE": "PASS",
        "window_counts": frame.groupby("video_id").size().to_dict(),
    }, indent=2))


def frames_for_window(video_path: str, start: float, end: float) -> tuple[list[np.ndarray], list[int], list[float], list[str]]:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = sorted(set(
        min(frame_count - 1, max(0, int(round(value * fps))))
        for value in np.arange(start, end + 1e-9, 1.0 / DECODE_FPS)
    ))
    frames, timestamps, hashes = [], [], []
    try:
        for index in indices:
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
                raise RuntimeError(f"seek failed at {index}")
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"decode failed at {index}")
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(rgb)
            timestamps.append(index / fps)
            hashes.append(sha256_bytes(frame.tobytes()))
    finally:
        capture.release()
    return frames, indices, timestamps, hashes


def extract_json(raw: str) -> tuple[dict[str, Any], str]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}, "no_json_object"
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}, "invalid_json"
    if not isinstance(value, dict) or not isinstance(value.get("events"), list):
        return {}, "schema_invalid"
    cleaned_events = []
    for event in value["events"]:
        if not isinstance(event, dict):
            return {}, "event_not_object"
        try:
            start, end = float(event["start_sec"]), float(event["end_sec"])
        except (KeyError, TypeError, ValueError):
            return {}, "event_time_invalid"
        actor = str(event.get("actor_type", "")).lower()
        if actor != "motor_vehicle" or not (0 <= start <= end <= 30.0001):
            return {}, "event_semantics_invalid"
        cleaned_events.append({
            "start_sec": start, "end_sec": end, "actor_type": actor,
            "confidence": str(event.get("confidence", "low")).lower(),
            "description": str(event.get("description", "")),
        })
    return {
        "events": cleaned_events,
        "ambiguous": [str(value) for value in value.get("ambiguous", [])],
    }, "ok"


def infer(limit: int | None = None) -> None:
    if not IDENTITIES.exists():
        raise RuntimeError("Run reference prepare first")
    identities = read_jsonl(IDENTITIES)
    query = json.loads((IMMUTABLE / "contracts/query_contract.yaml").read_text())
    valid = {
        path.stem for path in RAW.glob("*.json")
        if json.loads(path.read_text()).get("parse_status") == "ok"
    }
    remaining = [row for row in identities if row["window_id"] not in valid]
    if limit is not None:
        remaining = remaining[:limit]
    if not remaining:
        print(json.dumps({"REFERENCE_INFER": "ALL_VALID_EXISTING"}, indent=2))
        return
    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    load_started = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    model.eval()
    model_load_sec = time.perf_counter() - load_started
    completed_now = 0
    for identity in remaining:
        window_id = identity["window_id"]
        prior_attempts = sum(
            row.get("window_id") == window_id
            and row.get("event") == "STARTED"
            and row.get("input_protocol_version") == INPUT_PROTOCOL_VERSION
            for row in read_jsonl(ATTEMPTS)
        )
        accepted = False
        for sequence in range(prior_attempts + 1, MAX_ATTEMPTS + 1):
            attempt_id = f"{window_id}_a{sequence:02d}"
            append_jsonl(ATTEMPTS, {
                "event": "STARTED", "attempt_id": attempt_id,
                "window_id": window_id, "physical_oracle_call": True,
                "input_protocol_version": INPUT_PROTOCOL_VERSION,
                "timestamp_utc": utc_now(),
            })
            try:
                frames, indices, timestamps, content_hashes = frames_for_window(
                    identity["video_path"], float(identity["start_sec"]), float(identity["end_sec"])
                )
                pil_frames = [Image.fromarray(frame) for frame in frames]
                messages = [{"role": "user", "content": [
                    {
                        "type": "video", "video": pil_frames,
                        "sample_fps": DECODE_FPS, "raw_fps": DECODE_FPS,
                    },
                    {"type": "text", "text": query["query_prompt"]},
                ]}]
                prompt_text = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                image_inputs, video_inputs, video_kwargs = process_vision_info(
                    messages, return_video_kwargs=True, return_video_metadata=True
                )
                video_metadata = [value[1] for value in video_inputs]
                video_inputs = [value[0] for value in video_inputs]
                video_kwargs["video_metadata"] = video_metadata
                inputs = processor(
                    text=[prompt_text], images=image_inputs, videos=video_inputs,
                    padding=True, return_tensors="pt", **video_kwargs,
                ).to(model.device)
                torch.manual_seed(int(identity["rng_seed"]))
                torch.cuda.manual_seed_all(int(identity["rng_seed"]))
                torch.cuda.synchronize()
                started = time.perf_counter()
                with torch.no_grad():
                    generated = model.generate(
                        **inputs, do_sample=False, max_new_tokens=512
                    )
                torch.cuda.synchronize()
                generation_sec = time.perf_counter() - started
                trimmed = [
                    output[len(input_ids):]
                    for input_ids, output in zip(inputs.input_ids, generated)
                ]
                raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
                parsed, parse_status = extract_json(raw)
                record = {
                    **identity, "attempt_id": attempt_id,
                    "physical_oracle_call": True, "policy_execution_oracle": False,
                    "input_protocol_version": INPUT_PROTOCOL_VERSION,
                    "decoded_frame_indices": indices,
                    "decoded_frame_timestamps_sec": timestamps,
                    "decoded_frame_content_hashes": content_hashes,
                    "raw": raw, "raw_response_sha256": sha256_bytes(raw.encode()),
                    "parsed": parsed, "parsed_sha256": canonical_hash(parsed),
                    "parse_status": parse_status,
                    "generation_runtime_sec": generation_sec,
                    "model_load_sec": model_load_sec if completed_now == 0 else 0.0,
                    "model_path": str(MODEL), "model_hash": (
                        "c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210"
                    ),
                    "created_at_utc": utc_now(),
                }
                destination = RAW / f"{window_id}.json"
                if parse_status == "ok":
                    atomic_json(destination, record)
                    append_jsonl(ATTEMPTS, {
                        "event": "ACCEPTED", "attempt_id": attempt_id,
                        "window_id": window_id,
                        "envelope_sha256": sha256_file(destination),
                        "timestamp_utc": utc_now(),
                    })
                    accepted = True
                    completed_now += 1
                    print(json.dumps({
                        "window_id": window_id, "generation_sec": generation_sec,
                        "completed_now": completed_now, "requested": len(remaining),
                    }), flush=True)
                    break
                failed = RAW / "failed" / f"{attempt_id}.json"
                atomic_json(failed, record)
                append_jsonl(ATTEMPTS, {
                    "event": "INVALID_PARSE", "attempt_id": attempt_id,
                    "window_id": window_id, "parse_status": parse_status,
                    "timestamp_utc": utc_now(),
                })
            except Exception as exc:
                append_jsonl(ATTEMPTS, {
                    "event": "FAILED", "attempt_id": attempt_id,
                    "window_id": window_id, "error_type": type(exc).__name__,
                    "error": str(exc), "timestamp_utc": utc_now(),
                })
            finally:
                for name in ["inputs", "generated", "frames", "pil_frames"]:
                    if name in locals():
                        del locals()[name]
                gc.collect()
                torch.cuda.empty_cache()
        if not accepted:
            raise RuntimeError(f"Reference window exhausted attempts: {window_id}")
    print(json.dumps({"REFERENCE_INFER": "PASS", "completed_now": completed_now}, indent=2))


def merge_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for event in sorted(events, key=lambda row: (row["video_id"], row["event_start_sec"], row["event_end_sec"])):
        if output and output[-1]["video_id"] == event["video_id"]:
            prior = output[-1]
            midpoint_distance = abs(
                (prior["event_start_sec"] + prior["event_end_sec"]) / 2
                - (event["event_start_sec"] + event["event_end_sec"]) / 2
            )
            overlaps = (
                min(prior["event_end_sec"], event["event_end_sec"])
                >= max(prior["event_start_sec"], event["event_start_sec"])
            )
            if overlaps or midpoint_distance <= 2.0:
                prior["event_start_sec"] = min(prior["event_start_sec"], event["event_start_sec"])
                prior["event_end_sec"] = max(prior["event_end_sec"], event["event_end_sec"])
                prior["reference_window_ids"].extend(event["reference_window_ids"])
                prior["confidence"] = (
                    "high" if "high" in {prior["confidence"], event["confidence"]}
                    else "medium" if "medium" in {prior["confidence"], event["confidence"]}
                    else "low"
                )
                continue
        output.append(event)
    return output


def finalize() -> None:
    identities = read_jsonl(IDENTITIES)
    records = []
    missing = []
    for identity in identities:
        path = RAW / f"{identity['window_id']}.json"
        if not path.is_file():
            missing.append(identity["window_id"])
            continue
        record = json.loads(path.read_text())
        if record.get("parse_status") != "ok":
            missing.append(identity["window_id"])
        else:
            records.append(record)
    event_rows = []
    ambiguous = []
    for record in records:
        window_start = float(record["start_sec"])
        for event in record["parsed"]["events"]:
            event_rows.append({
                "video_id": record["video_id"],
                "event_start_sec": window_start + float(event["start_sec"]),
                "event_end_sec": window_start + float(event["end_sec"]),
                "event_type": "TARGET_VEHICLE_CUT_IN",
                "actor_type": "motor_vehicle",
                "reference_source": "QWEN3_VL_32B_FULL_CONTEXT",
                "reference_window_ids": [record["window_id"]],
                "adjudication_status": "oracle_pseudo_reference_not_human_adjudicated",
                "confidence": event["confidence"],
                "ambiguity_reason": "",
                "reference_version": "partial_scan_full_context_30s_stride15_v1",
            })
        for value in record["parsed"].get("ambiguous", []):
            ambiguous.append({"video_id": record["video_id"], "window_id": record["window_id"], "reason": value})
    merged = merge_events(event_rows)
    for video_id in sorted({row["video_id"] for row in merged}):
        index = 0
        for row in merged:
            if row["video_id"] != video_id:
                continue
            row["reference_event_id"] = f"{video_id}_ref_{index:04d}"
            row["reference_window_ids"] = "|".join(sorted(set(row["reference_window_ids"])))
            index += 1
    columns = [
        "video_id", "reference_event_id", "event_type", "event_start_sec",
        "event_end_sec", "actor_type", "reference_source", "reference_window_ids",
        "adjudication_status", "confidence", "ambiguity_reason", "reference_version",
    ]
    frame = pd.DataFrame(merged).reindex(columns=columns)
    atomic_csv(REFERENCE, frame)
    if ambiguous:
        atomic_csv(DERIVED / "reference_construction/ambiguous_windows.csv", pd.DataFrame(ambiguous))
    else:
        atomic_csv(
            DERIVED / "reference_construction/ambiguous_windows.csv",
            pd.DataFrame(columns=["video_id", "window_id", "reason"]),
        )
    complete = len(missing) == 0
    atomic_json(DERIVED / "audits/reference_completeness_audit.json", {
        "status": "COMPLETE" if complete else "PARTIAL_OR_UNVERIFIED",
        "systematic_window_count": len(identities),
        "parse_valid_window_count": len(records),
        "missing_or_invalid_windows": missing,
        "ambiguous_statement_count": len(ambiguous),
        "reference_event_count": len(frame),
        "event_counts": frame.groupby("video_id").size().to_dict() if len(frame) else {},
        "reference_type": "FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "human_adjudicated": False,
    })
    independence = json.loads((DERIVED / "audits/reference_independence_audit.json").read_text())
    independence.update({
        "status": "PASS" if complete else "PASS_REFERENCE_COMPLETENESS_PARTIAL",
        "reference_events_sha256": sha256_file(REFERENCE),
        "physical_oracle_call_count": len(records),
        "policy_execution_oracle_calls": 0,
    })
    atomic_json(DERIVED / "audits/reference_independence_audit.json", independence)
    print(json.dumps({
        "REFERENCE_FINALIZE": "PASS" if complete else "PARTIAL",
        "events": len(frame), "missing": len(missing), "ambiguous": len(ambiguous),
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    infer_parser = sub.add_parser("infer")
    infer_parser.add_argument("--limit", type=int)
    sub.add_parser("finalize")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "infer":
        infer(args.limit)
    elif args.command == "finalize":
        finalize()


if __name__ == "__main__":
    main()
