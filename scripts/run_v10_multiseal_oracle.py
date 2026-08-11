#!/usr/bin/env python3
"""Execute frozen V10-MS shadow or missing-unit seals without P0 access.

Each unit result is an immutable checkpoint.  Semantic construction is copied
from the sealed V3 runner: exact frozen frame decode, processor input hash,
Qwen generation configuration, and strict parser.  This runner changes only
execution packaging: records carry a V10-MS seal id rather than the aborted
V9 single-execution seal.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
V9 = BASE / "full_grid_preregistration_staged_v9_runtime_recovery"
OUT = ROOT / "outputs/v10_multiseal_reference_v1"
PROTOCOL_PATH = OUT / "MULTI_SEAL_PROTOCOL.json"
SINGLE_GPU = os.environ.get("V10MS_SINGLE_GPU", "0") == "1"
SINGLE_GPU_INDEX = int(os.environ.get("V10MS_GPU_INDEX", "7"))
SINGLE_GPU_CPU_OFFLOAD = os.environ.get("V10MS_SINGLE_GPU_CPU_OFFLOAD", "0") == "1"
SINGLE_GPU_GPU_MEMORY_GIB = int(os.environ.get("V10MS_SINGLE_GPU_GPU_MEMORY_GIB", "64"))
SINGLE_GPU_RESIDENT_TEXT_LAYERS = int(os.environ.get("V10MS_SINGLE_GPU_RESIDENT_TEXT_LAYERS", "44"))
TWO_GPU_IDS_RAW = os.environ.get("V10MS_TWO_GPU_IDS", "").strip()
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.accelerated_event_query.oracle_v3_full_grid_manifest import fraction_fps, decode_full_grid_unit, public_frame
from garc_eval.accelerated_event_query.oracle_v3_full_grid_processing import load_frozen_processor, prepare_frozen_model_inputs, runtime_environment_identity, tensor_bundle_sha256
from garc_eval.accelerated_event_query.oracle_v3_full_grid_runner import authenticate_gpu_exclusivity, _gpu_identity
from garc_eval.accelerated_event_query.oracle_v3_manifest import atomic_text, canonical_hash, load_json, sha256_file
from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response


def current_execution_topology() -> dict[str, Any]:
    """Current V10-MS execution authority, independent of V3 worker history."""
    if SINGLE_GPU:
        return {"mode": "single_gpu", "physical_gpu_id": SINGLE_GPU_INDEX}
    if not TWO_GPU_IDS_RAW:
        raise RuntimeError("V10-MS two-GPU execution requires V10MS_TWO_GPU_IDS")
    physical = sorted(int(token) for token in TWO_GPU_IDS_RAW.split(",") if token.strip())
    if len(physical) != 2 or len(set(physical)) != 2:
        raise RuntimeError("V10MS_TWO_GPU_IDS must name exactly two distinct physical GPUs")
    return {"mode": "two_gpu_balanced", "physical_gpu_ids": physical}


def current_execution_physical_devices() -> list[int]:
    topology = current_execution_topology()
    if topology["mode"] == "single_gpu":
        return [topology["physical_gpu_id"]]
    return list(topology["physical_gpu_ids"])


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(path, text)


def append_event(path: Path, event: dict[str, Any]) -> None:
    rows = []
    if path.exists():
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    row = dict(event)
    row["recorded_at_unix_ns"] = time.time_ns()
    row["previous_event_sha256"] = rows[-1]["event_sha256"] if rows else None
    row["event_sha256"] = canonical_hash(row)
    rows.append(row)
    atomic_text(path, "".join(json.dumps(x, sort_keys=True) + "\n" for x in rows))


def frozen() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    protocol = load_json(PROTOCOL_PATH)
    if not protocol.get("PROTOCOL_FROZEN") or protocol.get("DOWNSTREAM_P0_OBSERVED"):
        raise RuntimeError("V10-MS protocol is not a valid frozen pre-P0 contract")
    if sha256_file(PROTOCOL_PATH) != protocol["protocol_hash"]:
        # Canonical hash, not byte hash, is the protocol identity.
        unsigned = {k: v for k, v in protocol.items() if k != "protocol_hash"}
        if canonical_hash(unsigned) != protocol["protocol_hash"]:
            raise RuntimeError("V10-MS protocol hash mismatch")
    if protocol.get("execution_topology") != current_execution_topology():
        raise RuntimeError("runner topology does not match frozen V10-MS amendment")
    expected_runtime = {
        "pytorch_cuda_alloc_conf": os.environ.get("PYTORCH_ALLOC_CONF", ""),
        "single_gpu_cpu_offload": SINGLE_GPU_CPU_OFFLOAD,
        "single_gpu_gpu_memory_gib": SINGLE_GPU_GPU_MEMORY_GIB,
        "single_gpu_resident_text_layers": SINGLE_GPU_RESIDENT_TEXT_LAYERS,
    }
    if protocol.get("execution_runtime") != expected_runtime:
        raise RuntimeError("runner allocator configuration does not match frozen V10-MS amendment")
    prereg = load_json(V9 / "FULL_GRID_PREREGISTRATION.json")
    units_payload = load_json(V9 / "FULL_GRID_UNIT_MANIFEST.json")
    frames_payload = load_json(V9 / "FULL_GRID_FRAME_MANIFEST.json")
    schedule = load_json(V9 / "FULL_GRID_WORKER_SCHEDULE.json")
    expected_contract = protocol["semantic_contract"]
    checks = {
        "source_bindings_hash": prereg["bindings"]["source_bindings"]["sha256"],
        "unitization_hash": sha256_file(ROOT / prereg["bindings"]["unit_grid"]["path"]),
        "model_hash": prereg["model"]["content_hash"],
        "processor_hash": sha256_file(V9 / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json"),
        "prompt_hash": prereg["bindings"]["prompt"]["sha256"],
        "generation_config_hash": canonical_hash(prereg["decoding"]),
        "parser_hash": sha256_file(ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_parser.py"),
        "k3_config_hash": prereg["bindings"]["k3_config"]["sha256"],
    }
    if any(expected_contract.get(key) != value for key, value in checks.items()):
        raise RuntimeError("frozen semantic contract mismatch")
    frame_map: dict[str, list[dict[str, Any]]] = {}
    for row in frames_payload["frames"]:
        frame_map.setdefault(row["unit_id"], []).append({
            "ordinal": row["unit_frame_ordinal"],
            "target_relative_seconds": row["target_relative_seconds"],
            "target_absolute_seconds": row["target_absolute_seconds"],
            "ideal_requested_index": row["ideal_requested_index"],
            "requested_index": row["requested_index"],
            "source_boundary_resolution": row["source_boundary_resolution"],
            "decoded_index": row["decoded_index"],
            "decoded_timestamp_seconds": row["decoded_timestamp_seconds"],
            "content_sha256": row["content_sha256"],
        })
    videos = {r["video_id"]: r for r in load_json(ROOT / prereg["bindings"]["video_manifest"]["path"])["videos"]}
    return protocol, prereg, {r["unit_id"]: r for r in units_payload["units"]}, {r["worker_id"]: r for r in schedule["workers"]}, frame_map, videos


def selected_ids(kind: str) -> list[str]:
    if kind == "shadow":
        payload = load_json(OUT / "SHADOW_COMPATIBILITY_SET.json")
        return [row["unit_id"] for row in payload["units"]]
    if kind == "missing":
        return list(load_json(OUT / "MISSING_UNIT_SET.json")["missing_unit_ids"])
    raise ValueError(kind)


def seal_path(kind: str) -> Path:
    return OUT / "seals" / {"shadow": "SEAL_SHADOW", "missing": "SEAL_B"}[kind]


def runtime_physical_devices(seal: dict[str, Any], worker_id: str) -> list[int]:
    """Execution topology authority; never fall back to historical pairs."""
    physical = seal.get("gpu_topology", {}).get(worker_id)
    if not isinstance(physical, list) or not physical or not all(isinstance(x, int) for x in physical):
        raise RuntimeError("current V10-MS seal lacks worker runtime topology")
    return physical


def prepare(kind: str) -> None:
    protocol, prereg, units, workers, _, _ = frozen()
    selected = selected_ids(kind)
    if not selected or len(selected) != len(set(selected)) or not set(selected) <= set(units):
        raise RuntimeError("invalid frozen unit selection")
    assignments: dict[str, list[str]] = {}
    for unit_id in selected:
        row = units[unit_id]
        assignments.setdefault(row["worker_id"], []).append(unit_id)
    for ids in assignments.values(): ids.sort(key=lambda x: units[x]["ordinal"])
    manifest = {
        "status": "FROZEN_V10_MS_EXECUTION_SEAL",
        "seal_kind": kind,
        "seal_id": f"V10_MS_{kind.upper()}_{protocol['protocol_hash'][:12]}",
        "protocol_hash": protocol["protocol_hash"],
        "semantic_contract": protocol["semantic_contract"],
        "unit_ids": selected,
        "unit_ids_hash": canonical_hash(selected),
        "assignments": assignments,
        "gpu_topology": {worker_id: current_execution_physical_devices() for worker_id in assignments},
        "V9_execution_seal_sha256": protocol["seal_a"]["execution_seal_sha256"],
        "execution_policy": "immutable per-unit checkpoint records; no overwrite; a later seal may contain only unit IDs without authoritative records",
        "downstream_metrics_observed": False,
    }
    manifest["seal_hash"] = canonical_hash(manifest)
    write_json_once(seal_path(kind) / "EXECUTION_SEAL.json", manifest)
    print(json.dumps({"kind": kind, "seal_hash": manifest["seal_hash"], "units": len(selected), "workers": sorted(assignments)}, sort_keys=True))


def decode(unit: dict[str, Any], video: dict[str, Any], expected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kind, frames = decode_full_grid_unit(ROOT / video["path"], unit["start_time"], unit["end_time"], fraction_fps(video["nominal_fps"]), include_rgb=True)
    public = [public_frame(x) for x in frames]
    if kind != unit["unit_kind"] or public != expected or canonical_hash(public) != unit["frame_set_sha256"]:
        raise RuntimeError(f"frozen frame identity mismatch: {unit['unit_id']}")
    return frames


def single_gpu_cpu_offload_map() -> dict[str, Any]:
    """Fixed execution map for the 64-layer frozen Qwen checkpoint.

    The map is deliberately independent of video, unit, label, and model
    output.  It reserves inference headroom on one A100 by keeping a fixed
    44-layer prefix resident and attaching Accelerate CPU-offload hooks to the
    remaining suffix.
    """
    if not 1 <= SINGLE_GPU_RESIDENT_TEXT_LAYERS < 64:
        raise RuntimeError("single-GPU resident layer count must be in [1, 63]")
    result: dict[str, Any] = {
        "model.visual": 0,
        "model.language_model.embed_tokens": 0,
        "model.language_model.rotary_emb": 0,
    }
    for index in range(64):
        result[f"model.language_model.layers.{index}"] = 0 if index < SINGLE_GPU_RESIDENT_TEXT_LAYERS else "cpu"
    result["model.language_model.norm"] = "cpu"
    result["lm_head"] = "cpu"
    return result


def worker(kind: str, worker_id: str) -> None:
    import numpy as np
    import torch
    import transformers
    from transformers import Qwen3VLForConditionalGeneration
    protocol, prereg, units, workers, frame_map, videos = frozen()
    seal = load_json(seal_path(kind) / "EXECUTION_SEAL.json")
    if seal["protocol_hash"] != protocol["protocol_hash"]:
        raise RuntimeError("execution seal/protocol mismatch")
    assigned = seal["assignments"].get(worker_id, [])
    if not assigned:
        return
    # Historical worker bindings own unit assignment only.  Runtime placement
    # is exclusively owned by the current V10-MS seal amendment.
    physical = runtime_physical_devices(seal, worker_id)
    expected_visible = ",".join(map(str, physical))
    expected_devices = len(physical)
    if os.environ.get("CUDA_VISIBLE_DEVICES") != expected_visible or torch.cuda.device_count() != expected_devices:
        raise RuntimeError("worker does not have its current V10-MS runtime topology")
    directory = seal_path(kind)
    ledger = directory / "attempt_ledgers" / f"{worker_id}.jsonl"
    raw_dir = directory / "raw"
    if ledger.exists() or any((raw_dir / f"{unit_id}.json").exists() for unit_id in assigned):
        raise RuntimeError("this immutable seal worker has already started; create a later seal for infrastructure recovery")
    exclusivity = authenticate_gpu_exclusivity(physical)
    identities = [_gpu_identity(i) for i in physical]
    runtime_identity = runtime_environment_identity()
    processed = load_json(V9 / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json")
    if runtime_identity != processed["processor_environment"]:
        raise RuntimeError("frozen V7 processor runtime mismatch")
    append_event(ledger, {"event": "MODEL_LOAD_STARTED", "worker_id": worker_id, "physical_gpu_ids": physical, "seal_hash": seal["seal_hash"]})
    model_path = ROOT / prereg["model"]["path"]
    started = time.perf_counter()
    if SINGLE_GPU and SINGLE_GPU_CPU_OFFLOAD:
        # Execution-only memory placement: preserve the frozen checkpoint and
        # BF16 dtype while leaving generation headroom on a single 80GB A100.
        placement: Any = single_gpu_cpu_offload_map()
        model_kwargs: dict[str, Any] = {
            "offload_buffers": True,
        }
    else:
        placement = {"": 0} if SINGLE_GPU else "balanced"
        model_kwargs = {}
    model = Qwen3VLForConditionalGeneration.from_pretrained(model_path, dtype=torch.bfloat16, device_map=placement, trust_remote_code=True, local_files_only=True, **model_kwargs)
    model.to(dtype=torch.bfloat16); model.eval(); torch.use_deterministic_algorithms(True, warn_only=False)
    processor = load_frozen_processor(model_path)
    seed = int(prereg["decoding"]["seed"])
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.cuda.synchronize(); load_seconds = time.perf_counter() - started
    append_event(ledger, {"event": "MODEL_LOAD_COMPLETED", "worker_id": worker_id, "wall_seconds": load_seconds, "hf_device_map": {str(k): str(v) for k, v in sorted(getattr(model, "hf_device_map", {}).items())}})
    prompt = (ROOT / prereg["bindings"]["prompt"]["path"]).read_text(encoding="utf-8")
    try:
        for unit_id in assigned:
            unit = units[unit_id]
            frames = decode(unit, videos[unit["video_id"]], frame_map[unit_id])
            inputs = prepare_frozen_model_inputs(processor, prompt=prompt, rgb_frames=[x["rgb"] for x in frames], unit_kind=unit["unit_kind"], true_duration_seconds=unit["duration_seconds"], sampling_fps=2.0).to(model.device)
            processed_hash = tensor_bundle_sha256(inputs)
            if processed_hash != unit["expected_processed_input_sha256"]:
                raise RuntimeError(f"processor tensor mismatch: {unit_id}")
            attempt_id = f"{seal['seal_id']}:{worker_id}:{unit_id}:{time.time_ns()}"
            common = {"worker_id": worker_id, "unit_id": unit_id, "attempt_id": attempt_id, "processed_input_sha256": processed_hash}
            append_event(ledger, {"event": "PREPARED", **common})
            append_event(ledger, {"event": "INFERENCE_STARTED", **common})
            tic = time.perf_counter()
            with torch.no_grad(): generated = model.generate(**inputs, do_sample=False, max_new_tokens=int(prereg["decoding"]["max_new_tokens"]))
            torch.cuda.synchronize(); infer_s = time.perf_counter() - tic
            generated_hash = tensor_bundle_sha256({"generated": generated})
            append_event(ledger, {"event": "INFERENCE_COMPLETED", **common, "generated_token_ids_sha256": generated_hash})
            trimmed = [output[len(ids):] for ids, output in zip(inputs.input_ids, generated)]
            raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            parsed = parse_oracle_v3_response(raw)
            record = {
                "status": "AUTHENTICATED_V10_MS_RAW_OUTPUT", "mock_not_oracle": False,
                "protocol_hash": protocol["protocol_hash"], "seal_hash": seal["seal_hash"], "seal_id": seal["seal_id"],
                "semantic_contract": protocol["semantic_contract"], "unit_id": unit_id, "unit_ordinal": unit["ordinal"], "video_id": unit["video_id"], "worker_id": worker_id,
                "physical_gpu_ids": physical, "attempt_id": attempt_id, "call_spec_sha256": unit["call_spec_sha256"], "frame_set_sha256": unit["frame_set_sha256"],
                "processed_input_sha256": processed_hash, "generated_token_ids_sha256": generated_hash,
                "raw": raw, "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest(), "parse_status": parsed.parse_status,
                "authoritative_label": parsed.effective_label, "parsed": parsed.parsed,
                "runtime": {"gpu_identities": identities, "worker_preload_gpu_exclusivity": exclusivity, "pytorch_cuda_alloc_conf": os.environ.get("PYTORCH_ALLOC_CONF", ""), "single_gpu_cpu_offload": SINGLE_GPU_CPU_OFFLOAD, "single_gpu_gpu_memory_gib": SINGLE_GPU_GPU_MEMORY_GIB, "single_gpu_resident_text_layers": SINGLE_GPU_RESIDENT_TEXT_LAYERS, "hf_device_map": {str(k): str(v) for k, v in sorted(getattr(model, "hf_device_map", {}).items())}, "model_load_seconds": load_seconds, "inference_seconds": infer_s, "processor_class": f"{processor.__class__.__module__}.{processor.__class__.__qualname__}", "python": platform.python_version(), "torch": torch.__version__, "transformers": transformers.__version__, "qwen_vl_utils": importlib.metadata.version("qwen-vl-utils")},
            }
            record["record_payload_sha256"] = canonical_hash(record)
            destination = raw_dir / f"{unit_id}.json"; destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(destination, json.dumps(record, indent=2, sort_keys=True) + "\n")
            append_event(ledger, {"event": "ACCEPTED", **common, "record_payload_sha256": record["record_payload_sha256"]})
    finally:
        import gc
        del model; gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()
    append_event(ledger, {"event": "WORKER_COMPLETED", "worker_id": worker_id, "unit_count": len(assigned)})


def launch(kind: str) -> None:
    seal = load_json(seal_path(kind) / "EXECUTION_SEAL.json")
    procs = []
    for worker_id, physical in seal["gpu_topology"].items():
        env = os.environ.copy(); env["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, physical)); env["V10MS_SINGLE_GPU"] = "1" if SINGLE_GPU else "0"; env["V10MS_GPU_INDEX"] = str(SINGLE_GPU_INDEX); env["V10MS_TWO_GPU_IDS"] = TWO_GPU_IDS_RAW
        process = subprocess.Popen([sys.executable, str(Path(__file__)), "worker", "--kind", kind, "--worker", worker_id], cwd=ROOT, env=env)
        procs.append((worker_id, process))
        # One current runtime topology is shared by all logical workers, so
        # workers must serialise even when that topology contains two GPUs.
        if SINGLE_GPU or TWO_GPU_IDS_RAW:
            if process.wait() != 0:
                break
    failures = {}
    for worker_id, proc in procs:
        code = proc.wait()
        if code: failures[worker_id] = code
    status = "COMPLETE" if not failures else "INFRASTRUCTURE_FAILURE"
    result = {"status": status, "seal_hash": seal["seal_hash"], "worker_returncodes": {w: p.returncode for w,p in procs}, "failures": failures}
    write_json_once(seal_path(kind) / "EXECUTION_RESULT.json", result)
    print(json.dumps(result, sort_keys=True))
    if failures: raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "launch"):
        p = sub.add_parser(name); p.add_argument("--kind", choices=["shadow", "missing"], required=True)
    p = sub.add_parser("worker"); p.add_argument("--kind", choices=["shadow", "missing"], required=True); p.add_argument("--worker", required=True)
    args = parser.parse_args()
    if args.cmd == "prepare": prepare(args.kind)
    elif args.cmd == "launch": launch(args.kind)
    else: worker(args.kind, args.worker)


if __name__ == "__main__": main()
