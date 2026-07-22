"""Execute the frozen VERA pilot with atomic, cap-aware checkpoints.

Run only inside a persistent tmux session.  A ``*.started.json`` checkpoint is
durably written immediately before every generate invocation; therefore a
crash can never cause an uncertain call to be silently repeated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import time
import traceback
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .contract import ContractError, canonical_json_hash, parse_dense_presence, parse_event_enumeration
from .physical_common import (
    IMPLEMENTATION,
    MODEL,
    PHYSICAL,
    ROOT,
    STRICT,
    VIDEO,
    atomic_json,
    atomic_text,
    load_json,
    sha256_file,
    verify_freeze,
)


def _gpu_identity() -> dict[str, str]:
    command = ["nvidia-smi", "--query-gpu=name,uuid", "--format=csv,noheader,nounits"]
    name, uuid = subprocess.check_output(command, text=True).strip().splitlines()[0].split(", ")
    return {"name": name, "uuid": uuid}


def _attempt_paths(attempt_id: str) -> tuple[Path, Path, Path]:
    return (
        PHYSICAL / "attempts" / f"{attempt_id}.started.json",
        PHYSICAL / "attempts" / f"{attempt_id}.complete.json",
        PHYSICAL / "raw" / f"{attempt_id}.txt",
    )


def _started_count() -> int:
    return len(list((PHYSICAL / "attempts").glob("*.started.json")))


def _extract_frames(task: dict[str, Any]) -> tuple[list[Image.Image], list[dict[str, Any]], float]:
    requested = [int(x) for x in task["frame_indices"]]
    wanted = set(requested)
    cap = cv2.VideoCapture(str(VIDEO))
    cap.set(cv2.CAP_PROP_POS_FRAMES, requested[0])
    images: list[Image.Image] = []
    identities: list[dict[str, Any]] = []
    start = time.perf_counter()
    for frame_index in range(requested[0], requested[-1] + 1):
        ok, frame = cap.read()
        if not ok:
            break
        if frame_index not in wanted:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        digest = hashlib.sha256()
        digest.update(str(rgb.shape).encode("ascii"))
        digest.update(rgb.tobytes(order="C"))
        images.append(Image.fromarray(rgb))
        identities.append({
            "frame_index": frame_index,
            "shape": list(rgb.shape),
            "rgb_sha256": digest.hexdigest(),
        })
    cap.release()
    elapsed = time.perf_counter() - start
    actual = [x["frame_index"] for x in identities]
    if actual != requested:
        raise RuntimeError(f"decoded frames differ from frozen schedule: {task['planned_attempt_id']}")
    return images, identities, elapsed


def _render_prompt(task: dict[str, Any], sample: dict[str, Any]) -> str:
    prompts = {p["key"]: p for p in load_json(PHYSICAL / "PROMPT_MANIFEST.json")["prompts"]}
    item = prompts[task["prompt_key"]]
    text = (ROOT / item["path"]).read_text(encoding="utf-8")
    if task["prompt_key"] == "EVENT_ENUMERATE_V1":
        text = text.replace("__CLIP_DURATION_SECONDS__", f"{task['perceived_clip_duration']:.1f}")
    return text


def _seed_everything(seed: int, torch: Any) -> None:
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=False)


def _state(status: str, config: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
    payload = {
        "status": status,
        "freeze_version": config["freeze_version"],
        "physical_attempts_started": _started_count(),
        "maximum_physical_calls": config["plan"]["maximum_physical_calls"],
        "updated_unix": time.time(),
    }
    if extra:
        payload.update(extra)
    atomic_json(PHYSICAL / "RUN_STATE.json", payload)


def _run_one(
    task: dict[str, Any],
    ordinal: int,
    model: Any,
    processor: Any,
    process_vision_info: Any,
    torch: Any,
    config: dict[str, Any],
    sample: dict[str, Any],
) -> dict[str, Any] | None:
    attempt_id = task["planned_attempt_id"]
    started_path, complete_path, raw_path = _attempt_paths(attempt_id)
    if complete_path.exists():
        return load_json(complete_path)
    if started_path.exists():
        # The old process may have reached model.generate.  It counts and is
        # intentionally not retried.
        return None
    if _started_count() >= int(config["plan"]["maximum_physical_calls"]):
        raise RuntimeError("physical call cap reached")

    call_wall_start = time.perf_counter()
    images, frame_identities, frame_decode_seconds = _extract_frames(task)
    prompt = _render_prompt(task, sample)
    rendered_prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    messages = [{"role": "user", "content": [
        {"type": "video", "video": images, "fps": float(task["message_fps"])},
        {"type": "text", "text": prompt},
    ]}]
    processor_start = time.perf_counter()
    chat_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[chat_text], images=image_inputs, videos=video_inputs,
        padding=True, return_tensors="pt",
    )
    inputs = inputs.to(model.device)
    processor_seconds = time.perf_counter() - processor_start
    seed = int(config["generation"]["base_seed"]) + ordinal
    _seed_everything(seed, torch)
    input_identity = {
        "attempt_id": attempt_id,
        "operator": task["operator"],
        "task": task,
        "frame_identities": frame_identities,
        "rendered_prompt_sha256": rendered_prompt_sha,
        "model_full_content_hash": config["model"]["full_content_hash"],
        "seed": seed,
    }
    started = {
        **input_identity,
        "input_identity_sha256": canonical_json_hash(input_identity),
        "started_unix": time.time(),
        "started_checkpoint_semantics": "physical call counted; generate is the immediately following operation",
    }
    atomic_json(started_path, started)
    _state("RUNNING", config, {"current_attempt_id": attempt_id})

    max_tokens = (
        config["generation"]["max_new_tokens_event_enumerate"]
        if task["operator"] == "EVENT_ENUMERATE"
        else config["generation"]["max_new_tokens_dense"]
    )
    try:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        event_start = torch.cuda.Event(enable_timing=True)
        event_end = torch.cuda.Event(enable_timing=True)
        generation_start = time.perf_counter()
        event_start.record()
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=int(max_tokens),
                do_sample=False,
            )
        event_end.record()
        torch.cuda.synchronize()
        generation_wall_seconds = time.perf_counter() - generation_start
        cuda_event_seconds = event_start.elapsed_time(event_end) / 1000.0
        peak_memory_bytes = int(torch.cuda.max_memory_allocated())
        generated_trimmed = [
            output[len(input_ids):]
            for input_ids, output in zip(inputs.input_ids, generated_ids)
        ]
        output_token_count = int(sum(x.numel() for x in generated_trimmed))
        output_text = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
        atomic_text(raw_path, output_text)
        parse_start = time.perf_counter()
        try:
            if task["operator"] == "EVENT_ENUMERATE":
                parsed = parse_event_enumeration(output_text, float(task["perceived_clip_duration"]))
            else:
                parsed = parse_dense_presence(output_text, float(task["perceived_clip_duration"]))
            parse_status = "valid"
            parse_error = None
        except ContractError as exc:
            parsed = None
            parse_status = "contract_error"
            parse_error = str(exc)
        parse_seconds = time.perf_counter() - parse_start
        complete = {
            "attempt_id": attempt_id,
            "operator": task["operator"],
            "role": task["role"],
            "task": task,
            "input_identity_sha256": started["input_identity_sha256"],
            "raw_response_path": str(raw_path.relative_to(ROOT)),
            "raw_response_sha256": sha256_file(raw_path),
            "parsed_response": parsed,
            "parse_status": parse_status,
            "parse_error": parse_error,
            "retry_number": 0,
            "physical_call_count": 1,
            "cache_reuse": False,
            "cold_warm_state": "first_call_after_model_load" if ordinal == 0 else "warm_model",
            "frame_count": len(images),
            "input_token_count": int(inputs.input_ids.numel()),
            "output_token_count": output_token_count,
            "frame_decode_hash_seconds": frame_decode_seconds,
            "processor_seconds": processor_seconds,
            "generation_wall_seconds": generation_wall_seconds,
            "decision_gpu_seconds": generation_wall_seconds,
            "cuda_event_seconds": cuda_event_seconds,
            "parse_seconds": parse_seconds,
            "total_call_wall_seconds": time.perf_counter() - call_wall_start,
            "peak_memory_bytes": peak_memory_bytes,
            "completed_unix": time.time(),
            "status": "VALID" if parse_status == "valid" else "INVALID_RESPONSE",
        }
    except Exception as exc:  # preserve the attempt and trigger frozen fallback
        failed_generation_wall = (
            time.perf_counter() - generation_start if "generation_start" in locals() else math.nan
        )
        complete = {
            "attempt_id": attempt_id,
            "operator": task["operator"],
            "role": task["role"],
            "task": task,
            "input_identity_sha256": started["input_identity_sha256"],
            "raw_response_path": None,
            "raw_response_sha256": None,
            "parsed_response": None,
            "parse_status": "physical_error",
            "parse_error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "retry_number": 0,
            "physical_call_count": 1,
            "cache_reuse": False,
            "frame_count": len(images),
            "frame_decode_hash_seconds": frame_decode_seconds,
            "processor_seconds": processor_seconds,
            "generation_wall_seconds": failed_generation_wall,
            "decision_gpu_seconds": failed_generation_wall,
            "total_call_wall_seconds": time.perf_counter() - call_wall_start,
            "completed_unix": time.time(),
            "status": "PHYSICAL_ERROR",
        }
    atomic_json(complete_path, complete)
    _state("RUNNING", config, {"last_completed_attempt_id": attempt_id})
    try:
        del inputs, images, messages, image_inputs, video_inputs
        if "generated_ids" in locals():
            del generated_ids, generated_trimmed
        torch.cuda.empty_cache()
    except Exception:
        pass
    return complete


def _fallback_tasks(sample: dict[str, Any]) -> list[dict[str, Any]]:
    base_by_window = {
        task["window_id"]: task
        for task in sample["execution_order"]
        if task["operator"] == "EVENT_ENUMERATE"
    }
    needs_fallback: set[str] = set()
    for window_id, task in base_by_window.items():
        started, completed, _ = _attempt_paths(task["planned_attempt_id"])
        if not completed.exists():
            if started.exists():
                needs_fallback.add(window_id)
            continue
        result = load_json(completed)
        parsed = result.get("parsed_response")
        if result.get("status") != "VALID" or not parsed or parsed.get("clip_status") == "abstain":
            needs_fallback.add(window_id)
    units: set[int] = set()
    for window_id in needs_fallback:
        units.update(int(x) for x in sample["fallback_matrix"][window_id])
    unit_table = {
        int(row["unit_id"]): row
        for row in __import__("csv").DictReader((STRICT / "frozen_inputs/unit_table.csv").open())
    }
    tasks = []
    for unit_id in sorted(units):
        row = unit_table[unit_id]
        input_start, input_end = float(row["start_time"]), float(row["end_time"])
        indices = []
        # Reuse the already frozen schedule for the same unit when available.
        for base in sample["execution_order"]:
            if base.get("unit_id") == unit_id:
                indices = list(base["frame_indices"])
                break
        if not indices:
            fps = float(sample["video"]["fps"])
            total = int(sample["video"]["total_frames"])
            stride = max(1, int(fps / 2.0))
            indices = list(range(int(input_start * fps), min(total - 1, int(input_end * fps)) + 1, stride))
        tasks.append({
            "order": len(sample["execution_order"]) + len(tasks),
            "planned_attempt_id": f"dense_fallback_u{unit_id:04d}_a001",
            "operator": "DENSE_UNIT_FALLBACK",
            "role": "selected_algorithm_fallback",
            "unit_id": unit_id,
            "trigger_windows": sorted(w for w in needs_fallback if unit_id in sample["fallback_matrix"][w]),
            "input_start": input_start,
            "input_end": input_end,
            "core_start": input_start,
            "core_end": input_end,
            "frame_indices": indices,
            "frame_count": len(indices),
            "message_fps": 2.0,
            "perceived_clip_duration": (len(indices) - 1) / 2.0,
            "prompt_key": "DENSE_PRESENCE_STRICT_V13_6",
        })
    return tasks


def execute() -> None:
    if not os.environ.get("TMUX"):
        raise RuntimeError("physical execution is permitted only inside a persistent tmux session")
    config = verify_freeze()
    sample = load_json(PHYSICAL / "SAMPLE_MANIFEST.json")
    gpu = _gpu_identity()
    if gpu["uuid"] != config["model"]["frozen_gpu"]["uuid"]:
        raise RuntimeError(f"assigned GPU differs from frozen GPU: {gpu}")
    _state("LOADING_MODEL", config)

    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    load_start = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(MODEL), torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(str(MODEL), trust_remote_code=True)
    model_load_wall = time.perf_counter() - load_start
    run_metadata = {
        "model_load_wall_seconds": model_load_wall,
        "gpu": gpu,
        "process_id": os.getpid(),
        "tmux": os.environ.get("TMUX"),
        "run_started_unix": time.time(),
        "freeze_config_sha256": sha256_file(PHYSICAL / "FROZEN_PHYSICAL_CONFIG.json"),
    }
    atomic_json(PHYSICAL / "RUN_METADATA.json", run_metadata)

    base = list(sample["execution_order"])
    for ordinal, task in enumerate(base):
        _run_one(task, ordinal, model, processor, process_vision_info, torch, config, sample)
    fallback = _fallback_tasks(sample)
    atomic_json(PHYSICAL / "REALIZED_FALLBACK_PLAN.json", {
        "tasks": fallback,
        "count": len(fallback),
        "constructed_only_from_frozen_failure_states": True,
    })
    cap_exhausted = False
    for offset, task in enumerate(fallback):
        if _started_count() >= int(config["plan"]["maximum_physical_calls"]):
            cap_exhausted = True
            break
        _run_one(task, len(base) + offset, model, processor, process_vision_info, torch, config, sample)

    incomplete_started = []
    for path in (PHYSICAL / "attempts").glob("*.started.json"):
        if not path.with_name(path.name.replace(".started.json", ".complete.json")).exists():
            incomplete_started.append(path.stem.replace(".started", ""))
    fallback_missing = [
        task["planned_attempt_id"] for task in fallback
        if not _attempt_paths(task["planned_attempt_id"])[1].exists()
    ]
    final_status = "COMPLETE" if not cap_exhausted and not incomplete_started and not fallback_missing else "INCOMPLETE"
    run_metadata.update({
        "run_finished_unix": time.time(),
        "physical_attempts_started": _started_count(),
        "base_tasks": len(base),
        "fallback_tasks": len(fallback),
        "cap_exhausted": cap_exhausted,
        "incomplete_started_attempts": sorted(incomplete_started),
        "missing_fallback_attempts": fallback_missing,
        "status": final_status,
    })
    atomic_json(PHYSICAL / "RUN_COMPLETE.json", run_metadata)
    _state(final_status, config, run_metadata)
    print(json.dumps({
        "status": final_status,
        "physical_attempts": _started_count(),
        "fallback_tasks": len(fallback),
        "model_load_wall_seconds": model_load_wall,
    }, sort_keys=True))


def preflight() -> None:
    config = verify_freeze()
    sample = load_json(PHYSICAL / "SAMPLE_MANIFEST.json")
    result = {
        "freeze": "PASS",
        "tmux": bool(os.environ.get("TMUX")),
        "gpu": _gpu_identity(),
        "gpu_matches_freeze": _gpu_identity()["uuid"] == config["model"]["frozen_gpu"]["uuid"],
        "base_calls": len(sample["execution_order"]),
        "started_calls": _started_count(),
        "max_calls": config["plan"]["maximum_physical_calls"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.execute == args.preflight:
        parser.error("choose exactly one of --execute or --preflight")
    execute() if args.execute else preflight()


if __name__ == "__main__":
    main()
