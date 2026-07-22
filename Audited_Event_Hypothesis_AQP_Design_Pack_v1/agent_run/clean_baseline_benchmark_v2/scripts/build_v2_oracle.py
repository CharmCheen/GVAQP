#!/usr/bin/env python3
"""Build the content-bound clean benchmark v2 oracle cache.

Stages are idempotent and atomic.  Only ``infer`` loads the VLM, and it is
hard-coded to unit 346.  Units 0--345 reuse validated raw response bytes after
the Phase-0 frame/content and frozen-configuration lineage checks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import cv2


REPO = Path(__file__).resolve().parents[4]
PACK = Path(__file__).resolve().parents[1]
V1 = PACK.parent / "clean_baseline_benchmark_v1"
P0 = PACK.parent / "bcm_aqp_experiment_v1"
VIDEO = REPO / "data/realcam/long_video_data/long_video_dataset3.mp4"
MODEL = REPO / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT_SOURCE = V1 / "oracle/oracle_prompt.txt"
PROMPT_TARGET = PACK / "oracle/oracle_prompt.txt"
RAW_DIR = PACK / "oracle/raw"
PARSED_DIR = PACK / "oracle/parsed"
IDENTITIES = PACK / "oracle/input_identities.jsonl"
PHASE0_INTERVALS = P0 / "audit/oracle_cache_interval_audit.csv"
PHASE0_UNIT346 = P0 / "audit/unit346_frame_equivalence.csv"
V1_UNITS = V1 / "frozen_inputs/unit_table.csv"
V1_OBSERVATIONS = V1 / "oracle/oracle_presence_observations.csv"
V1_CACHE_MANIFEST = V1 / "oracle/oracle_cache_manifest.csv"
V1_MODEL_MANIFEST = V1 / "oracle/oracle_model_manifest.csv"
STATE_UPDATER = PACK / "scripts/atomic_run_state.py"
PARSER_VERSION = "presence_json_parser_v1_stage2_compatible"
PARSER_CONFIG = {"parser_version": PARSER_VERSION, "required_keys": ["label", "confidence"]}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    return sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: object) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def atomic_write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    from io import StringIO
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(path, buffer.getvalue())


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in read_csv(path)}


def update_state(*args: str) -> None:
    import subprocess
    subprocess.run([os.environ.get("PYTHON", "python"), str(STATE_UPDATER), *args], check=True)


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def extract_frames(clip_start, clip_end, video_fps, fps=2.0):
    frames = []
    cap = cv2.VideoCapture(str(VIDEO))
    start_frame = int(clip_start * video_fps)
    end_frame = int(clip_end * video_fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_interval = max(1, int(video_fps / fps))
    for fi in range(start_frame, end_frame + 1):
        ret, frame = cap.read()
        if not ret:
            break
        decoded_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
        decoded_timestamp_seconds = float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
        if (fi - start_frame) % frame_interval == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            digest = hashlib.sha256()
            digest.update(str(rgb.shape).encode("ascii"))
            digest.update(str(rgb.dtype).encode("ascii"))
            digest.update(rgb.tobytes(order="C"))
            frames.append({
                "requested_index": fi,
                "decoded_index": decoded_index,
                "decoded_timestamp_seconds": decoded_timestamp_seconds,
                "content_sha256": digest.hexdigest(),
                "rgb": rgb,
            })
    cap.release()
    return frames


def config_identity() -> dict:
    benchmark_manifest = json.loads((V1 / "BENCHMARK_MANIFEST.json").read_text())
    processor_files = [
        "config.json", "preprocessor_config.json", "video_preprocessor_config.json",
        "tokenizer_config.json", "chat_template.json", "tokenizer.json",
        "merges.txt", "vocab.json",
    ]
    processor_hash = canonical_hash({name: sha256_file(MODEL / name) for name in processor_files})
    video_processor = {
        "loader": "cv2.VideoCapture",
        "start_index": "int(clip_start*video_fps)",
        "end_index": "int(clip_end*video_fps)",
        "inclusive_end_loop": True,
        "target_decode_fps": 2.0,
        "frame_interval": "max(1,int(video_fps/fps))",
        "color": "cv2.COLOR_BGR2RGB",
        "container": "list[PIL.Image]",
        "message_fps": 2.0,
        "qwen_process": "process_vision_info(messages)",
    }
    generation = {
        "torch_dtype": "bfloat16",
        "device_map": "auto",
        "trust_remote_code": True,
        "max_new_tokens": 256,
        "temperature": 0.1,
        "sampling_flags_explicit": {},
        "generation_config_sha256": sha256_file(MODEL / "generation_config.json"),
    }
    sampling_source = inspect.getsource(extract_frames)
    return {
        "model_hash": benchmark_manifest["compatibility"]["oracle_model_hash"],
        "processor_hash": processor_hash,
        "video_processor_hash": canonical_hash(video_processor),
        "generation_config_hash": canonical_hash(generation),
        "prompt_hash": sha256_file(PROMPT_SOURCE),
        "parser_hash": canonical_hash(PARSER_CONFIG),
        "parser_source_hash": sha256_text(inspect.getsource(parse_response)),
        "sampling_code_hash": sha256_text(sampling_source),
        "sampling_semantics_hash": canonical_hash(video_processor),
        "processor_files": {name: sha256_file(MODEL / name) for name in processor_files},
        "generation_config": generation,
        "video_processor_config": video_processor,
        "runtime_versions": {
            "opencv": cv2.__version__,
            "opencv_python": package_version("opencv-python"),
            "qwen_vl_utils": package_version("qwen-vl-utils"),
            "transformers": package_version("transformers"),
            "torch": package_version("torch"),
            "pillow": package_version("pillow"),
        },
    }


def parse_response(raw_text: str) -> tuple[dict, str]:
    try:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {}
        return parsed, "ok"
    except Exception:
        return {}, "parse_error"


def build_identities() -> list[dict]:
    units = read_index(V1_UNITS, "unit_id")
    phase0 = read_index(PHASE0_INTERVALS, "unit_id")
    cfg = config_identity()
    identities = []
    for uid in range(347):
        u = units[str(uid)]
        p = phase0[str(uid)]
        identity = {
            "video_sha256": u["video_sha256"],
            "unit_id": uid,
            "unit_start": float(u["start_time"]),
            "unit_end": float(u["end_time"]),
            "decoded_frame_indices": [int(x) for x in p["frozen_decoded_frame_indices"].split("|") if x],
            "decoded_frame_indices_sha256": p["frozen_frame_indices_hash"],
            "decoded_frame_content_sha256": p["frozen_frame_content_hash"],
            "decoded_frame_count": int(p["frozen_num_frames"]),
            "model_hash": cfg["model_hash"],
            "processor_hash": cfg["processor_hash"],
            "video_processor_hash": cfg["video_processor_hash"],
            "generation_config_hash": cfg["generation_config_hash"],
            "prompt_hash": cfg["prompt_hash"],
            "parser_hash": cfg["parser_hash"],
            "sampling_code_hash": cfg["sampling_code_hash"],
        }
        identity["cache_input_identity_sha256"] = canonical_hash(identity)
        identities.append(identity)
    return identities


def stage_prepare() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    if sha256_file(PROMPT_SOURCE) != "12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33":
        raise RuntimeError("Frozen prompt hash changed")
    atomic_write_bytes(PROMPT_TARGET, PROMPT_SOURCE.read_bytes())
    identities = build_identities()
    atomic_write_text(IDENTITIES, "".join(json.dumps(row, sort_keys=True) + "\n" for row in identities))
    v1_cache = read_index(V1_CACHE_MANIFEST, "unit_id")
    phase0 = read_index(PHASE0_INTERVALS, "unit_id")
    comparisons = []
    reused = 0
    for identity in identities:
        uid = identity["unit_id"]
        anchor = f"center10_anchor_{uid:04d}"
        target = RAW_DIR / f"{anchor}.json"
        p0 = phase0[str(uid)]
        if uid < 346:
            if not (p0["same_frame_indices"] == "True" and p0["same_frame_content"] == "True"):
                raise RuntimeError(f"Phase-0 equivalence failed for unit {uid}")
            source = V1 / v1_cache[str(uid)]["raw_output_path"]
            if sha256_file(source) != v1_cache[str(uid)]["raw_sha256"]:
                raise RuntimeError(f"v1 raw envelope hash failed for unit {uid}")
            if target.exists() and sha256_file(target) != sha256_file(source):
                preserved = target.with_suffix(f".invalid.{int(time.time())}.json")
                os.replace(target, preserved)
            if not target.exists():
                atomic_write_bytes(target, source.read_bytes())
            reused += 1
            action = "V1_RAW_RESPONSE_REUSED"
            reuse_basis = "FRAME_INDICES_AND_CONTENT_EQUIVALENT"
        else:
            action = "V2_REQUERY_REQUIRED"
            reuse_basis = "V1_FRAME_INPUT_MISMATCH"
        comparisons.append({
            "unit_id": uid,
            "v1_cache_start": p0["cache_start"],
            "v1_cache_end": p0["cache_end"],
            "v2_unit_start": f"{identity['unit_start']:.6f}",
            "v2_unit_end": f"{identity['unit_end']:.6f}",
            "v1_frame_indices_sha256": p0["cache_frame_indices_hash"],
            "v2_frame_indices_sha256": identity["decoded_frame_indices_sha256"],
            "v1_frame_content_sha256": p0["cache_frame_content_hash"],
            "v2_frame_content_sha256": identity["decoded_frame_content_sha256"],
            "same_frame_indices": p0["same_frame_indices"],
            "same_frame_content": p0["same_frame_content"],
            "cache_action": action,
            "reuse_basis": reuse_basis,
            "v2_cache_input_identity_sha256": identity["cache_input_identity_sha256"],
        })
    atomic_write_csv(PACK / "audit/v1_v2_oracle_input_comparison.csv", comparisons)
    atomic_write_json(PACK / "oracle/oracle_configuration.json", config_identity())
    update_state("--phase", "oracle_prepare", "--phase-status", "completed", "--completed-units", str(reused))
    print(json.dumps({"prepared_reused_units": reused, "requery_units": 1}, sort_keys=True))


def validate_existing_unit346(identity: dict) -> bool:
    path = RAW_DIR / "center10_anchor_0346.json"
    if not path.exists():
        return False
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return (
            obj.get("unit_id") == 346
            and obj.get("cache_input_identity_sha256") == identity["cache_input_identity_sha256"]
            and isinstance(obj.get("raw"), str)
            and len(obj["raw"].strip()) > 0
            and obj.get("physical_vlm_call") is True
        )
    except Exception:
        return False


def stage_infer() -> None:
    identities = [json.loads(line) for line in IDENTITIES.read_text().splitlines() if line.strip()]
    identity = identities[346]
    output_path = RAW_DIR / "center10_anchor_0346.json"
    if output_path.exists() and not validate_existing_unit346(identity):
        preserved = output_path.with_suffix(f".invalid.{int(time.time())}.json")
        os.replace(output_path, preserved)
    if validate_existing_unit346(identity):
        update_state("--phase", "oracle_inference", "--phase-status", "completed", "--completed-units", "347", "--physical-vlm-calls", "1")
        print(json.dumps({"unit_id": 346, "status": "VALID_EXISTING_RAW_REUSED", "new_physical_calls": 0}))
        return

    cap = cv2.VideoCapture(str(VIDEO))
    video_fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    frames = extract_frames(identity["unit_start"], identity["unit_end"], video_fps, fps=2.0)
    if len(frames) < 5:
        frames = extract_frames(identity["unit_start"], identity["unit_end"], video_fps, fps=4.0)
    indices = [int(x["decoded_index"]) for x in frames]
    contents = [str(x["content_sha256"]) for x in frames]
    if indices != identity["decoded_frame_indices"] or len(frames) != 10:
        raise RuntimeError(f"Unit 346 frame sequence mismatch: {indices}")
    if canonical_hash(indices) != identity["decoded_frame_indices_sha256"]:
        raise RuntimeError("Unit 346 frame-index hash mismatch")
    if canonical_hash(contents) != identity["decoded_frame_content_sha256"]:
        raise RuntimeError("Unit 346 frame-content hash mismatch")

    update_state("--phase", "oracle_inference", "--phase-status", "in_progress", "--completed-units", "346")
    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    load_start = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    load_seconds = time.time() - load_start
    torch.cuda.reset_peak_memory_stats()
    pil_frames = [Image.fromarray(x["rgb"]) for x in frames]
    messages = [{"role": "user", "content": [
        {"type": "video", "video": pil_frames, "fps": 2.0},
        {"type": "text", "text": PROMPT_TARGET.read_text(encoding="utf-8")},
    ]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)
    call_started = utc_now()
    t0 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=256, temperature=0.1)
    torch.cuda.synchronize()
    runtime = time.time() - t0
    generated_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    output_text = processor.batch_decode(generated_trimmed, skip_special_tokens=True)[0]
    peak_allocated = int(torch.cuda.max_memory_allocated())
    peak_reserved = int(torch.cuda.max_memory_reserved())
    raw_record = {
        "anchor_id": "center10_anchor_0346",
        "unit_id": 346,
        "unit_start": identity["unit_start"],
        "unit_end": identity["unit_end"],
        "decoded_frame_indices": indices,
        "decoded_frame_timestamps_seconds": [round(float(x["decoded_timestamp_seconds"]), 9) for x in frames],
        "per_frame_content_sha256": contents,
        "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
        "raw": output_text,
        "raw_response_sha256": sha256_text(output_text),
        "physical_vlm_call": True,
        "call_started_at_utc": call_started,
        "call_completed_at_utc": utc_now(),
        "model_load_seconds": load_seconds,
        "generation_runtime_seconds": runtime,
        "peak_gpu_memory_allocated_bytes": peak_allocated,
        "peak_gpu_memory_reserved_bytes": peak_reserved,
    }
    # The raw response is atomically durable before any parsing occurs.
    atomic_write_json(output_path, raw_record)
    atomic_write_json(PACK / "oracle/unit346_call_record.json", {
        key: raw_record[key] for key in raw_record if key != "raw"
    })
    update_state("--phase", "oracle_inference", "--phase-status", "completed", "--completed-units", "347", "--physical-vlm-calls", "1")
    print(json.dumps({
        "unit_id": 346,
        "status": "NEW_V2_RAW_SAVED",
        "physical_vlm_calls": 1,
        "raw_response_sha256": raw_record["raw_response_sha256"],
        "generation_runtime_seconds": runtime,
        "peak_gpu_memory_allocated_bytes": peak_allocated,
    }, sort_keys=True))


def stage_finalize() -> None:
    identities = [json.loads(line) for line in IDENTITIES.read_text().splitlines() if line.strip()]
    units = read_index(V1_UNITS, "unit_id")
    v1_obs = read_index(V1_OBSERVATIONS, "unit_id")
    v1_cache = read_index(V1_CACHE_MANIFEST, "unit_id")
    cfg = config_identity()
    cache_rows, ledger_rows, observation_rows = [], [], []
    comparison_rows = read_csv(PACK / "audit/v1_v2_oracle_input_comparison.csv")
    comparison_by_uid = {int(x["unit_id"]): x for x in comparison_rows}
    for identity in identities:
        uid = identity["unit_id"]
        anchor = f"center10_anchor_{uid:04d}"
        raw_path = RAW_DIR / f"{anchor}.json"
        if not raw_path.exists():
            raise RuntimeError(f"Missing v2 raw response for unit {uid}")
        raw_obj = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_text = raw_obj.get("raw")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise RuntimeError(f"Missing nested raw response for unit {uid}")
        parsed, parse_status = parse_response(raw_text)
        label = str(parsed.get("label", "abstain")).lower()
        unit = units[str(uid)]
        start = float(unit["start_time"])
        def absolute(value):
            if value in (None, "", "null"):
                return ""
            try:
                return str(start + float(value))
            except Exception:
                return ""
        parsed_record = {
            "unit_id": uid,
            "anchor_id": anchor,
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "parser_hash": cfg["parser_hash"],
            "parser_source_hash": cfg["parser_source_hash"],
            "parse_status": parse_status,
            "parsed": parsed,
            "parsed_sha256": canonical_hash(parsed),
        }
        atomic_write_json(PARSED_DIR / f"{anchor}.json", parsed_record)
        raw_response_hash = sha256_text(raw_text)
        raw_envelope_hash = sha256_file(raw_path)
        physical_call = uid == 346
        cache_source = "V2_NEW_VLM_RESPONSE" if physical_call else "V1_RAW_RESPONSE_REUSED"
        reuse_basis = "V1_FRAME_INPUT_MISMATCH_REQUERIED" if physical_call else "FRAME_INDICES_AND_CONTENT_EQUIVALENT"
        cache_rows.append({
            **{k: identity[k] for k in [
                "video_sha256", "unit_id", "unit_start", "unit_end",
                "decoded_frame_indices_sha256", "decoded_frame_content_sha256",
                "decoded_frame_count", "model_hash", "processor_hash",
                "video_processor_hash", "generation_config_hash", "prompt_hash",
                "parser_hash", "sampling_code_hash", "cache_input_identity_sha256",
            ]},
            "decoded_frame_indices": "|".join(map(str, identity["decoded_frame_indices"])),
            "raw_response_path": str(raw_path.relative_to(PACK)),
            "raw_response_sha256": raw_response_hash,
            "raw_envelope_sha256": raw_envelope_hash,
            "parsed_observation_path": str((PARSED_DIR / f"{anchor}.json").relative_to(PACK)),
            "parsed_observation_sha256": parsed_record["parsed_sha256"],
            "cache_source": cache_source,
            "reuse_basis": reuse_basis,
            "physical_vlm_call": physical_call,
            "cache_valid": True,
        })
        ledger_rows.append({
            "unit_id": uid,
            "anchor_id": anchor,
            "cache_source": cache_source,
            "physical_vlm_call": physical_call,
            "physical_call_count": 1 if physical_call else 0,
            "logical_method_budget_charged": False,
            "raw_response_path": str(raw_path.relative_to(PACK)),
            "raw_response_sha256": raw_response_hash,
            "cache_input_identity_sha256": identity["cache_input_identity_sha256"],
            "generation_runtime_seconds": raw_obj.get("generation_runtime_seconds", raw_obj.get("runtime", "")),
            "peak_gpu_memory_allocated_bytes": raw_obj.get("peak_gpu_memory_allocated_bytes", ""),
            "status": "VALID",
        })
        observation_rows.append({
            "anchor_id": anchor,
            "video_id": "long_video_dataset3",
            "unit_id": uid,
            "anchor_time": float(unit["end_time"]) if uid == 346 else start + 5.0,
            "start_time": start,
            "end_time": float(unit["end_time"]),
            "duration": float(unit["duration_seconds"]),
            "label": label,
            "event_start": "" if parsed.get("event_start") is None else parsed.get("event_start"),
            "event_end": "" if parsed.get("event_end") is None else parsed.get("event_end"),
            "event_start_absolute": absolute(parsed.get("event_start")),
            "event_end_absolute": absolute(parsed.get("event_end")),
            "event_type": parsed.get("event_type", "none"),
            "involved_object": parsed.get("involved_object", "none"),
            "ego_relevant": parsed.get("ego_relevant", ""),
            "boundary_status": parsed.get("boundary_status", "not_applicable"),
            "complete_event_visible": parsed.get("complete_event_visible", ""),
            "confidence": parsed.get("confidence", "low"),
            "evidence": parsed.get("evidence", ""),
            "negative_reason": parsed.get("negative_reason", "null"),
            "abstain_reason": parsed.get("abstain_reason", "null"),
            "runtime_seconds": raw_obj.get("generation_runtime_seconds", raw_obj.get("runtime", 0.0)),
            "raw_response_path": str(raw_path.relative_to(PACK)),
            "raw_response_sha256": raw_response_hash,
            "parsed_observation_sha256": parsed_record["parsed_sha256"],
            "parse_status": parse_status,
            "boundary_reliable": False,
        })
        old = v1_obs[str(uid)]
        comparison_by_uid[uid].update({
            "v1_raw_response_sha256": v1_cache[str(uid)]["raw_sha256"],
            "v2_raw_response_sha256": raw_response_hash,
            "raw_response_changed": str(sha256_text(json.loads((V1 / v1_cache[str(uid)]["raw_output_path"]).read_text())["raw"]) != raw_response_hash),
            "v1_parsed_label": old["parsed_label"],
            "v2_parsed_label": label,
            "parsed_label_changed": str(str(old["parsed_label"]).lower() != label),
            "v1_event_start_absolute": old.get("event_start_absolute", ""),
            "v2_event_start_absolute": observation_rows[-1]["event_start_absolute"],
            "v1_event_end_absolute": old.get("event_end_absolute", ""),
            "v2_event_end_absolute": observation_rows[-1]["event_end_absolute"],
            "parsed_boundaries_changed": str(
                str(old.get("event_start_absolute", "")) != str(observation_rows[-1]["event_start_absolute"])
                or str(old.get("event_end_absolute", "")) != str(observation_rows[-1]["event_end_absolute"])
            ),
        })
    atomic_write_csv(PACK / "oracle/oracle_cache_manifest.csv", cache_rows)
    atomic_write_csv(PACK / "oracle/VLM_CALL_LEDGER.csv", ledger_rows)
    atomic_write_csv(PARSED_DIR / "oracle_observations_source.csv", observation_rows)
    atomic_write_csv(PACK / "audit/v1_v2_oracle_input_comparison.csv", [comparison_by_uid[i] for i in range(347)])
    old346 = v1_obs["346"]["parsed_label"]
    new346 = observation_rows[346]["label"]
    report = f"""# Benchmark v2 Oracle Build Report

- Status: `COMPLETE`
- Units: 347
- Reused raw responses: 346
- New raw responses: 1
- Physical VLM calls: 1
- Forced requery: unit 346, `[3457.93,3462.93]`
- Old unit-346 label: `{old346}`
- New unit-346 label: `{new346}`
- Prompt SHA256: `{cfg['prompt_hash']}`
- Model manifest hash: `{cfg['model_hash']}`
- Processor hash: `{cfg['processor_hash']}`
- Video-processor hash: `{cfg['video_processor_hash']}`
- Generation-config hash: `{cfg['generation_config_hash']}`
- Parser hash: `{cfg['parser_hash']}`
- Sampling-code hash: `{cfg['sampling_code_hash']}`

The unit-346 raw response was atomically saved before parsing.  Every raw cache
entry is copied/content-bound inside this package and keyed by video, unit
interval, frame indices/content, model/processor/generation/prompt/parser, and
sampling code.  Method budgets are not charged here; future logical queries are
charged through `OracleAccessor` even when these files are cache-backed.
"""
    atomic_write_text(PACK / "oracle/V2_ORACLE_BUILD_REPORT.md", report)
    update_state("--phase", "oracle_cache", "--phase-status", "completed", "--completed-units", "347", "--physical-vlm-calls", "1")
    print(json.dumps({"reused": 346, "new": 1, "old_unit346_label": old346, "new_unit346_label": new346}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["prepare", "infer", "finalize", "all"])
    args = parser.parse_args()
    if args.stage in {"prepare", "all"}:
        stage_prepare()
    if args.stage in {"infer", "all"}:
        stage_infer()
    if args.stage in {"finalize", "all"}:
        stage_finalize()


if __name__ == "__main__":
    main()
