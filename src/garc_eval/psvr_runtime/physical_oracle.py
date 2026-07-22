"""Physical, cache-free oracle service behind the restricted three-method facade."""

from __future__ import annotations

import multiprocessing as mp
import hashlib
import json
from pathlib import Path

from .capabilities import OracleAccessor


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_physical_oracle_configuration(configuration: dict) -> dict:
    """Fail closed if any frozen oracle input differs from the declared contract."""

    required = {
        "frozen_oracle_source", "input_identities_path", "prompt_path", "video_path", "model_path",
        "strict_manifest_path", "model_manifest_path", "expected_hashes", "expected_oracle_build_id",
        "model_file_identity",
    }
    if set(configuration) != required:
        raise ValueError(f"physical oracle configuration schema mismatch: {sorted(set(configuration) ^ required)}")
    expected = dict(configuration["expected_hashes"])
    path_by_name = {
        "frozen_oracle_source": Path(configuration["frozen_oracle_source"]),
        "input_identities": Path(configuration["input_identities_path"]),
        "prompt": Path(configuration["prompt_path"]),
        "video": Path(configuration["video_path"]),
        "strict_manifest": Path(configuration["strict_manifest_path"]),
        "model_manifest": Path(configuration["model_manifest_path"]),
    }
    if set(expected) != set(path_by_name):
        raise ValueError("physical oracle expected-hash schema mismatch")
    observed = {name: _sha256_file(path) for name, path in path_by_name.items()}
    mismatches = {name: {"expected": expected[name], "observed": observed[name]}
                  for name in observed if observed[name] != expected[name]}
    if mismatches:
        raise RuntimeError(f"physical oracle frozen-input hash mismatch: {mismatches}")
    manifest = json.loads(path_by_name["strict_manifest"].read_text())
    if manifest.get("status") != "COMPLETE" or manifest.get("oracle_build_id") != configuration["expected_oracle_build_id"]:
        raise RuntimeError("strict oracle build manifest is not the expected completed build")
    if manifest.get("input_identities_sha256") != observed["input_identities"]:
        raise RuntimeError("strict manifest does not bind the current input identities")
    build_configuration = manifest["build_identity"]["configuration"]
    if build_configuration.get("prompt_sha256") != observed["prompt"]:
        raise RuntimeError("strict manifest does not bind the current prompt")
    if build_configuration.get("video_sha256") != observed["video"]:
        raise RuntimeError("strict manifest does not bind the current video")
    if manifest.get("artifact_hashes", {}).get("oracle/STRICT_MODEL_FILE_MANIFEST.csv") != observed["model_manifest"]:
        raise RuntimeError("strict manifest does not bind the model-file manifest")
    model_directory = Path(configuration["model_path"])
    declared_model_files = {row["file"]: row for row in configuration["model_file_identity"]}
    current_names = {path.name for path in model_directory.iterdir() if path.is_file()}
    if current_names != set(declared_model_files):
        raise RuntimeError("physical oracle model-directory membership changed")
    for name, row in declared_model_files.items():
        stat = (model_directory / name).stat()
        if stat.st_size != int(row["size_bytes"]) or stat.st_mtime_ns != int(row["mtime_ns"]):
            raise RuntimeError(f"physical oracle model file changed after launcher verification: {name}")
    return {"observed_hashes": observed, "oracle_build_id": manifest["oracle_build_id"],
            "model_file_count": len(declared_model_files)}


def _load_module(name: str, path: str):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load frozen oracle implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _physical_oracle_main(connection, configuration: dict) -> None:
    import gc
    import os
    import time
    from datetime import datetime, timezone

    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    try:
        import cv2
        import torch
        from PIL import Image
        from qwen_vl_utils import process_vision_info
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        verified_configuration = verify_physical_oracle_configuration(configuration)
        frozen = _load_module("psvr_frozen_strict_oracle", configuration["frozen_oracle_source"])
        identities = {
            int(row["unit_id"]): row
            for row in (json.loads(line) for line in Path(configuration["input_identities_path"]).read_text().splitlines() if line.strip())
        }
        prompt = Path(configuration["prompt_path"]).read_text(encoding="utf-8")
        expected_build = configuration["expected_oracle_build_id"]
        for unit_id, identity in identities.items():
            if identity.get("oracle_build_id") != expected_build:
                raise RuntimeError(f"unit {unit_id} has the wrong oracle build identity")
            if identity.get("prompt_hash") != configuration["expected_hashes"]["prompt"]:
                raise RuntimeError(f"unit {unit_id} has the wrong prompt identity")
            if identity.get("video_sha256") != configuration["expected_hashes"]["video"]:
                raise RuntimeError(f"unit {unit_id} has the wrong video identity")
        video_path = str(configuration["video_path"])
        # The frozen implementation uses its module-level VIDEO path. Verify the
        # launcher identity rather than silently redirecting sampling semantics.
        if Path(frozen.VIDEO).resolve() != Path(video_path).resolve():
            raise RuntimeError("frozen oracle video path does not match runtime configuration")
        cap = cv2.VideoCapture(video_path)
        video_fps = float(cap.get(cv2.CAP_PROP_FPS)); cap.release()
        load_start = time.perf_counter_ns()
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            configuration["model_path"], torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
        processor = AutoProcessor.from_pretrained(configuration["model_path"], trust_remote_code=True)
        model.eval(); torch.cuda.synchronize()
        initialization_seconds = (time.perf_counter_ns() - load_start) / 1e9
        connection.send(("ready", {
            "pid": os.getpid(), "initialization_seconds": initialization_seconds,
            "physical_oracle": True, "cache_loaded": False,
            "verified_configuration": verified_configuration,
            "torch_version": torch.__version__, "torch_cuda_version": torch.version.cuda,
        }))
        queried: list[int] = []
        while True:
            request = connection.recv(); operation = request[0]
            if operation == "shutdown":
                connection.send(("ok", None)); break
            if operation == "queried_ids":
                connection.send(("ok", tuple(sorted(set(queried))))); continue
            if operation == "query_count":
                connection.send(("ok", len(queried))); continue
            if operation != "query":
                connection.send(("error", "operation is not in the physical oracle capability protocol")); continue
            unit_id = int(request[1])
            if unit_id not in identities:
                connection.send(("error", f"unknown unit: {unit_id}")); continue
            if unit_id in queried:
                connection.send(("error", f"duplicate query: {unit_id}")); continue
            identity = identities[unit_id]
            try:
                torch.cuda.synchronize()
                total_start = time.perf_counter_ns()
                start = time.perf_counter_ns()
                frames = frozen.frames_for_unit(float(identity["start_time"]), float(identity["end_time"]), video_fps)
                frame_indices = [int(frame["decoded_index"]) for frame in frames]
                frame_contents = [frame["content_sha256"] for frame in frames]
                if frozen.canonical_hash(frame_indices) != identity["decoded_frame_indices_sha256"]:
                    raise RuntimeError("decoded frame indices changed")
                if frozen.canonical_hash(frame_contents) != identity["decoded_frame_content_sha256"]:
                    raise RuntimeError("decoded frame contents changed")
                clip_extraction = (time.perf_counter_ns() - start) / 1e9

                start = time.perf_counter_ns()
                pil_frames = [Image.fromarray(frame["rgb"]) for frame in frames]
                messages = [{"role": "user", "content": [
                    {"type": "video", "video": pil_frames, "fps": frozen.FRAME_CONFIG["message_fps"]},
                    {"type": "text", "text": prompt},
                ]}]
                prompt_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = processor(text=[prompt_text], images=image_inputs, videos=video_inputs,
                                   padding=True, return_tensors="pt").to(model.device)
                frozen.configure_rng(int(identity["rng_seed"]), torch)
                preprocessing = (time.perf_counter_ns() - start) / 1e9

                torch.cuda.synchronize(); start = time.perf_counter_ns()
                with torch.no_grad():
                    generated = model.generate(**inputs, do_sample=False,
                                               max_new_tokens=frozen.GENERATION_CONFIG["max_new_tokens"])
                torch.cuda.synchronize(); inference = (time.perf_counter_ns() - start) / 1e9

                start = time.perf_counter_ns()
                trimmed = [output[len(input_ids):] for input_ids, output in zip(inputs.input_ids, generated)]
                raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
                postprocessing = (time.perf_counter_ns() - start) / 1e9
                start = time.perf_counter_ns(); parsed, parse_status = frozen.parse_response(raw)
                parsing = (time.perf_counter_ns() - start) / 1e9

                start = time.perf_counter_ns()
                del inputs, generated, frames, pil_frames, image_inputs, video_inputs, messages
                gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()
                cleanup = (time.perf_counter_ns() - start) / 1e9
                service_total = (time.perf_counter_ns() - total_start) / 1e9
                recorded_at = datetime.now(timezone.utc).isoformat()
                queried.append(unit_id)
                result = {
                    "unit_id": unit_id,
                    "start_time": float(identity["start_time"]),
                    "end_time": float(identity["end_time"]),
                    "parsed_label": str(parsed.get("label", "abstain")).lower(),
                    "confidence": str(parsed.get("confidence", "low")).lower(),
                    "parsed": parsed,
                    "parse_status": parse_status,
                    "raw": raw,
                    "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "physical_oracle_invocation": True,
                    "cache_replay": False,
                    "logical_oracle_call": True,
                    "cuda_synchronized_before_and_after": True,
                    "recorded_at_utc": recorded_at,
                    "stage_seconds": {
                        "clip_extraction": clip_extraction,
                        "oracle_preprocess": preprocessing,
                        "oracle_inference": inference,
                        "oracle_postprocess": postprocessing,
                        "oracle_parse": parsing,
                        "cleanup": cleanup,
                    },
                    "service_total_seconds": service_total,
                    "frame_identity_verified": True,
                    "oracle_build_id": identity["oracle_build_id"],
                }
                connection.send(("ok", result))
            except Exception as exc:
                connection.send(("error", f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        try:
            connection.send(("startup_error", f"{type(exc).__name__}: {exc}"))
        except Exception:
            pass
    finally:
        connection.close()


class PhysicalOracleServiceHandle:
    """Trusted-launcher lifecycle handle; never pass it or its accessor to policy."""

    def __init__(self, accessor: OracleAccessor, connection, process: mp.Process, initialization: dict) -> None:
        self.__accessor = accessor
        self.__connection = connection
        self.__process = process
        self.initialization = dict(initialization)

    def runtime_accessor(self) -> OracleAccessor:
        return self.__accessor

    def close(self) -> None:
        if self.__process.is_alive():
            self.__connection.send(("shutdown",)); self.__connection.recv(); self.__process.join(timeout=30)
        self.__connection.close()
        if self.__process.is_alive():
            self.__process.terminate(); self.__process.join(timeout=10)


def start_physical_oracle_service(configuration: dict) -> PhysicalOracleServiceHandle:
    context = mp.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(target=_physical_oracle_main, args=(child, dict(configuration)))
    process.start(); child.close()
    status, payload = parent.recv()
    if status != "ready":
        process.join(timeout=10)
        raise RuntimeError(f"physical oracle startup failed: {payload}")

    def request(message: tuple):
        parent.send(message)
        response_status, response_payload = parent.recv()
        if response_status != "ok":
            raise RuntimeError(str(response_payload))
        return response_payload

    return PhysicalOracleServiceHandle(OracleAccessor(request), parent, process, payload)
