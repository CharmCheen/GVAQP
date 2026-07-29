#!/usr/bin/env python3
"""Run one authenticated AEQ V2 preflight shard with durable attempt evidence."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import random
import subprocess
import time
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from garc_eval.accelerated_event_query.oracle_protocol import (
    canonical_hash,
    extract_exact_frames,
    parse_response_strict,
    public_frame_record,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V2_PREREGISTRATION.json"
RAW = OUT / "operational_oracle/preflight_v2/raw"
ATTEMPTS = OUT / "operational_oracle/preflight_v2/attempts"
SHARDS = ("DALI", "HANGZHOU", "WUHAN")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(
        path,
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
    )


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def validate_bindings(prereg: dict) -> None:
    for key, expected in prereg["bindings"].items():
        if not key.endswith("_path"):
            continue
        hash_key = key.removesuffix("_path") + "_sha256"
        if hash_key not in prereg["bindings"]:
            continue
        path = ROOT / expected
        observed = sha256_file(path)
        if observed != prereg["bindings"][hash_key]:
            raise RuntimeError(f"binding mismatch for {path}: {observed}")
    model_audit = load(ROOT / prereg["bindings"]["model_identity_audit_path"])
    if model_audit["expected_model_content_hash"] != prereg["bindings"]["model_content_hash"]:
        raise RuntimeError("model audit/content binding mismatch")


def frozen_context() -> tuple[dict, dict, dict, dict, dict]:
    prereg = load(PREREG)
    validate_bindings(prereg)
    config = load(ROOT / prereg["bindings"]["config_path"])
    selection = load(ROOT / prereg["bindings"]["selection_source_path"])
    videos = {
        row["video_id"]: row
        for row in load(ROOT / prereg["bindings"]["video_manifest_path"])["videos"]
    }
    frame_manifest = load(ROOT / prereg["bindings"]["frame_manifest_path"])
    frame_sets = {
        (row["candidate_id"], float(row["sampling_fps"])): row
        for row in frame_manifest["frame_sets"]
    }
    return prereg, config, selection, videos, frame_sets


def schedule_for_shard(prereg: dict, selection: dict, shard: str) -> list[dict]:
    clips = {row["candidate_id"]: row for row in selection["clips"]}
    schedule = []
    sensitivity = set(prereg["workload"]["sensitivity_candidate_ids"])
    for clip in selection["clips"]:
        if clip["video_id"] != shard:
            continue
        for repeat in (0, 1):
            schedule.append({"clip": clip, "variant": "base", "repeat_index": repeat,
                             "sampling_fps": 2.0, "execution_shard": shard})
        if clip["candidate_id"] in sensitivity:
            schedule.append({"clip": clip, "variant": "fps_sensitivity", "repeat_index": 0,
                             "sampling_fps": 4.0, "execution_shard": shard})
    if shard != "DALI":
        anchor = clips[prereg["workload"]["cross_replica_anchor_candidate_id"]]
        schedule.append({"clip": anchor, "variant": "cross_replica_anchor", "repeat_index": 0,
                         "sampling_fps": 2.0, "execution_shard": shard})
    return schedule


def artifact_name(call: dict) -> str:
    candidate = call["clip"]["candidate_id"]
    if call["variant"] == "base":
        suffix = f"fps2_r{call['repeat_index']}"
    elif call["variant"] == "fps_sensitivity":
        suffix = "fps4_sensitivity"
    else:
        suffix = f"fps2_cross_replica_{call['execution_shard']}"
    return f"{candidate}_{suffix}.json"


def identity_payload(prereg: dict, call: dict, frame_set: dict) -> dict:
    clip = call["clip"]
    return {
        "experiment_id": prereg["experiment_id"],
        "execution_shard": call["execution_shard"],
        "candidate_id": clip["candidate_id"],
        "video_id": clip["video_id"],
        "video_sha256": frame_set["source_video_sha256"],
        "start_time": clip["start_time"],
        "end_time": clip["end_time"],
        "variant": call["variant"],
        "repeat_index": call["repeat_index"],
        "sampling_fps": call["sampling_fps"],
        "frame_set_sha256": frame_set["frame_set_sha256"],
        "prompt_sha256": prereg["bindings"]["prompt_sha256"],
        "config_sha256": prereg["bindings"]["config_sha256"],
        "protocol_source_sha256": prereg["bindings"]["protocol_source_sha256"],
        "model_content_hash": prereg["bindings"]["model_content_hash"],
        "seed": prereg["workload"]["seed"],
        "generation": prereg["workload"]["generation"],
    }


def model_input_identity(payload: dict, frames: list[dict]) -> str:
    stable = {key: value for key, value in payload.items()
              if key not in {"execution_shard", "variant", "repeat_index"}}
    return canonical_hash({**stable, "frames": [public_frame_record(row) for row in frames]})


def validate_existing_record(
    record: dict, expected_payload: dict, expected_frame_set: dict
) -> None:
    expected_input_identity = canonical_hash(expected_payload)
    claimed = record.get("record_sha256")
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    if claimed != canonical_hash(payload):
        raise RuntimeError("existing raw record self-hash mismatch")
    if record.get("input_identity_sha256") != expected_input_identity:
        raise RuntimeError("existing raw record input identity mismatch")
    if record.get("identity") != expected_payload or record.get("frames") != expected_frame_set["frames"]:
        raise RuntimeError("existing raw record identity/frame mismatch")
    expected_model_identity = model_input_identity(
        expected_payload, [{**frame, "rgb": None} for frame in expected_frame_set["frames"]]
    )
    if record.get("model_input_identity_sha256") != expected_model_identity:
        raise RuntimeError("existing raw record model-input identity mismatch")
    raw = record.get("raw")
    if not isinstance(raw, str) or record.get("raw_response_sha256") != hashlib.sha256(raw.encode()).hexdigest():
        raise RuntimeError("existing raw response hash mismatch")
    parsed, status = parse_response_strict(raw)
    effective = parsed.get("label") if status == "ok" else "parse_failure"
    if (record.get("parsed"), record.get("parse_status"), record.get("effective_label")) != (
        parsed, status, effective
    ):
        raise RuntimeError("existing raw record stored parse mismatch")


def append_attempt(shard: str, event: dict) -> None:
    path = ATTEMPTS / f"{shard}.jsonl"
    rows = read_attempts(shard)
    previous = rows[-1]["event_sha256"] if rows else None
    payload = {**event, "previous_event_sha256": previous}
    payload["event_sha256"] = canonical_hash(payload)
    atomic_text(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in [*rows, payload]))


def read_attempts(shard: str) -> list[dict]:
    path = ATTEMPTS / f"{shard}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    previous = None
    started = set()
    terminal = set()
    for row in rows:
        claimed = row.get("event_sha256")
        payload = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("previous_event_sha256") != previous or claimed != canonical_hash(payload):
            raise RuntimeError(f"attempt ledger hash-chain mismatch: {path}")
        previous = claimed
        attempt_id = row.get("attempt_id")
        if row.get("event") == "STARTED":
            if attempt_id in started:
                raise RuntimeError("duplicate STARTED attempt")
            started.add(attempt_id)
        elif row.get("event") in {"ACCEPTED", "FAILED", "RECOVERED_ACCEPTED", "RECOVERED_UNCERTAIN"}:
            if attempt_id not in started or attempt_id in terminal:
                raise RuntimeError("orphan or duplicate terminal attempt")
            terminal.add(attempt_id)
        else:
            raise RuntimeError("unknown attempt event")
    return rows


def close_interrupted_attempts(
    shard: str, artifact: str, input_identity: str, raw_record_sha256: str | None
) -> None:
    rows = read_attempts(shard)
    terminal = {row["attempt_id"] for row in rows if row["event"] != "STARTED"}
    open_rows = [row for row in rows if row["event"] == "STARTED"
                 and row["attempt_id"] not in terminal
                 and row.get("artifact") == artifact
                 and row.get("input_identity_sha256") == input_identity]
    if len(open_rows) > 1:
        raise RuntimeError("multiple interrupted attempts for one artifact")
    if open_rows:
        append_attempt(shard, {
            "event": "RECOVERED_ACCEPTED" if raw_record_sha256 else "RECOVERED_UNCERTAIN",
            "attempt_id": open_rows[0]["attempt_id"],
            "artifact": artifact,
            "input_identity_sha256": input_identity,
            "record_sha256": raw_record_sha256,
            "recovery_reason": "valid durable raw exists" if raw_record_sha256 else "prior process ended without durable raw",
        })


def verify_video_files(schedule: list[dict], videos: dict) -> None:
    for video_id in sorted({call["clip"]["video_id"] for call in schedule}):
        video = videos[video_id]
        observed = sha256_file(ROOT / video["path"])
        if observed != video["sha256"]:
            raise RuntimeError(f"video content hash mismatch: {video_id}")


def validate_frames(call: dict, videos: dict, frame_set: dict) -> list[dict]:
    clip = call["clip"]
    video = videos[clip["video_id"]]
    if video["sha256"] != frame_set["source_video_sha256"]:
        raise RuntimeError("video/frame-manifest identity mismatch")
    frames = extract_exact_frames(
        ROOT / video["path"], float(clip["start_time"]), float(clip["end_time"]),
        float(Fraction(video["nominal_fps"])), float(call["sampling_fps"]),
    )
    public = [public_frame_record(row) for row in frames]
    if public != frame_set["frames"] or canonical_hash(public) != frame_set["frame_set_sha256"]:
        raise RuntimeError(f"exact frame mismatch for {clip['candidate_id']} at {call['sampling_fps']} fps")
    return frames


def validate_only(shard: str) -> dict:
    prereg, _, selection, videos, frame_sets = frozen_context()
    schedule = schedule_for_shard(prereg, selection, shard)
    verify_video_files(schedule, videos)
    rows = []
    for call in schedule:
        frame_set = frame_sets[(call["clip"]["candidate_id"], call["sampling_fps"])]
        frames = validate_frames(call, videos, frame_set)
        payload = identity_payload(prereg, call, frame_set)
        rows.append({"artifact": artifact_name(call), "frame_count": len(frames),
                     "input_identity_sha256": canonical_hash(payload),
                     "model_input_identity_sha256": model_input_identity(payload, frames)})
    return {"status": "PASS", "execution_shard": shard, "expected_calls": len(schedule), "calls": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-shard", choices=SHARDS, required=True)
    parser.add_argument("--declared-physical-gpus", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate_only(args.execution_shard), indent=2, sort_keys=True))
        return

    import numpy as np
    import torch
    import transformers
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    declared = [int(token) for token in args.declared_physical_gpus.split(",")]
    if len(declared) != 2 or torch.cuda.device_count() != 2:
        raise RuntimeError("V2 requires exactly two visible GPUs")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != args.declared_physical_gpus:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must exactly match --declared-physical-gpus")
    gpu_identities = [subprocess.check_output([
        "nvidia-smi", f"--id={index}", "--query-gpu=index,name,uuid", "--format=csv,noheader",
    ], text=True).strip() for index in declared]
    if any(not identity.startswith(f"{index},") for identity, index in zip(gpu_identities, declared)):
        raise RuntimeError("physical GPU declaration mismatch")

    prereg, config, selection, videos, frame_sets = frozen_context()
    schedule = schedule_for_shard(prereg, selection, args.execution_shard)
    verify_video_files(schedule, videos)
    prompt = (ROOT / prereg["bindings"]["prompt_path"]).read_text(encoding="utf-8")
    model_path = ROOT / config["oracle"]["model_path"]
    load_started = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path, dtype=torch.bfloat16, device_map="balanced",
        trust_remote_code=True, local_files_only=True,
    )
    model.to(dtype=torch.bfloat16)
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    model.eval()
    torch.use_deterministic_algorithms(True, warn_only=False)
    random.seed(int(prereg["workload"]["seed"]))
    np.random.seed(int(prereg["workload"]["seed"]))
    torch.manual_seed(int(prereg["workload"]["seed"]))
    torch.cuda.manual_seed_all(int(prereg["workload"]["seed"]))
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_started

    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    for call in schedule:
        frame_set = frame_sets[(call["clip"]["candidate_id"], call["sampling_fps"])]
        payload = identity_payload(prereg, call, frame_set)
        input_identity = canonical_hash(payload)
        destination = RAW / args.execution_shard / artifact_name(call)
        existing_record = load(destination) if destination.exists() else None
        if existing_record is not None:
            validate_existing_record(existing_record, payload, frame_set)
        close_interrupted_attempts(args.execution_shard, artifact_name(call), input_identity,
                                   existing_record.get("record_sha256") if existing_record else None)
        if destination.exists():
            rows = read_attempts(args.execution_shard)
            accepted = any(row["event"] in {"ACCEPTED", "RECOVERED_ACCEPTED"}
                           and row.get("artifact") == artifact_name(call)
                           and row.get("input_identity_sha256") == input_identity
                           and row.get("record_sha256") == existing_record["record_sha256"]
                           and row.get("attempt_id") for row in rows)
            if not accepted:
                raise RuntimeError("durable raw lacks an accepted attempt event")
            continue
        attempt_id = f"{args.execution_shard}:{artifact_name(call)}:{time.time_ns()}"
        append_attempt(args.execution_shard, {"event": "STARTED", "attempt_id": attempt_id,
                                               "artifact": artifact_name(call),
                                               "input_identity_sha256": input_identity})
        try:
            call_started = time.perf_counter()
            frames = validate_frames(call, videos, frame_set)
            pil_frames = [Image.fromarray(row["rgb"]) for row in frames]
            messages = [{"role": "user", "content": [
                {"type": "video", "video": pil_frames, "fps": call["sampling_fps"]},
                {"type": "text", "text": prompt},
            ]}]
            prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs, kwargs = process_vision_info(
                messages, return_video_kwargs=True, return_video_metadata=True
            )
            if kwargs != {"do_sample_frames": False}:
                raise RuntimeError(f"unexpected sampling kwargs: {kwargs}")
            inputs = processor(
                text=[prompt_text], images=image_inputs, videos=[row[0] for row in video_inputs],
                video_metadata=[row[1] for row in video_inputs], padding=True,
                return_tensors="pt", **kwargs,
            ).to(model.device)
            torch.cuda.synchronize()
            inference_started = time.perf_counter()
            with torch.no_grad():
                generated = model.generate(
                    **inputs, do_sample=False,
                    max_new_tokens=int(prereg["workload"]["generation"]["max_new_tokens"]),
                )
            torch.cuda.synchronize()
            inference_seconds = time.perf_counter() - inference_started
            trimmed = [output[len(ids):] for ids, output in zip(inputs.input_ids, generated)]
            raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            parsed, parse_status = parse_response_strict(raw)
            record = {
                "identity": payload,
                "input_identity_sha256": input_identity,
                "model_input_identity_sha256": model_input_identity(payload, frames),
                "frames": [public_frame_record(row) for row in frames],
                "parse_status": parse_status,
                "effective_label": parsed.get("label") if parse_status == "ok" else "parse_failure",
                "parsed": parsed,
                "raw": raw,
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "runtime": {
                    "declared_physical_gpus": declared, "gpu_identities": gpu_identities,
                    "model_load_seconds": load_seconds, "inference_seconds": inference_seconds,
                    "total_call_seconds": time.perf_counter() - call_started,
                    "git_head": git_head, "git_status_sha256": hashlib.sha256(git_status.encode()).hexdigest(),
                    "runner_source_sha256": sha256_file(Path(__file__)),
                    "parameter_dtypes": sorted({str(parameter.dtype) for parameter in model.parameters()}),
                    "torch": torch.__version__, "transformers": transformers.__version__,
                },
            }
            record["record_sha256"] = canonical_hash(record)
            if destination.exists():
                raise RuntimeError("destination appeared during inference")
            atomic_json(destination, record)
            append_attempt(args.execution_shard, {"event": "ACCEPTED", "attempt_id": attempt_id,
                                                   "artifact": artifact_name(call),
                                                   "input_identity_sha256": input_identity,
                                                   "record_sha256": record["record_sha256"]})
            print(json.dumps({"artifact": str(destination.relative_to(ROOT)),
                              "parse_status": parse_status, "label": record["effective_label"],
                              "inference_seconds": inference_seconds}), flush=True)
            del frames, pil_frames, messages, inputs, generated, trimmed
            gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()
        except Exception as exc:
            append_attempt(args.execution_shard, {"event": "FAILED", "attempt_id": attempt_id,
                                                   "artifact": artifact_name(call),
                                                   "input_identity_sha256": input_identity,
                                                   "error_type": type(exc).__name__, "error": str(exc)})
            raise


if __name__ == "__main__":
    main()
