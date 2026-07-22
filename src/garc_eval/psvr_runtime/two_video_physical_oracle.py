"""Persistent-model, session-isolated physical oracle for two-video PSVR.

The policy still receives the unchanged three-method :class:`OracleAccessor`.
Only the trusted launcher can start or end a logical run session.  Keeping the
frozen model resident removes repeated model-load overhead; every query still
executes a new cache-free physical generation and duplicate unit queries are
rejected within each run.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
from pathlib import Path
from typing import Any

from .capabilities import OracleAccessor


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def project_generic_label(parsed: dict[str, Any], allowed_objects: set[str]) -> str:
    """Apply the frozen deterministic Q1/Q2 type projection."""

    generic = str(parsed.get("label", "abstain")).lower()
    if generic == "abstain":
        return "abstain"
    involved = str(parsed.get("involved_object", "none")).lower()
    if generic == "positive" and involved in allowed_objects:
        return "positive"
    return "negative"


def verify_two_video_configuration(configuration: dict[str, Any]) -> dict[str, Any]:
    required = {
        "frozen_oracle_source",
        "frozen_oracle_source_sha256",
        "prompt_path",
        "prompt_sha256",
        "model_path",
        "model_full_content_hash",
        "model_file_identity",
        "videos",
        "queries",
    }
    if set(configuration) != required:
        raise ValueError(
            "two-video physical oracle configuration schema mismatch: "
            f"{sorted(set(configuration) ^ required)}"
        )
    source = Path(configuration["frozen_oracle_source"])
    prompt = Path(configuration["prompt_path"])
    if _sha256_file(source) != configuration["frozen_oracle_source_sha256"]:
        raise RuntimeError("frozen oracle source hash changed")
    if _sha256_file(prompt) != configuration["prompt_sha256"]:
        raise RuntimeError("frozen oracle prompt hash changed")
    videos = dict(configuration["videos"])
    if set(videos) != {"V0", "V1"}:
        raise ValueError("physical oracle requires exactly frozen V0 and V1")
    verified_videos: dict[str, dict[str, Any]] = {}
    for video_id, row in videos.items():
        expected = {
            "video_path",
            "video_sha256",
            "input_identities_path",
            "input_identities_sha256",
            "oracle_build_id",
        }
        if set(row) != expected:
            raise ValueError(f"{video_id} physical-oracle schema mismatch")
        video_path = Path(row["video_path"])
        identities_path = Path(row["input_identities_path"])
        observed = {
            "video_sha256": _sha256_file(video_path),
            "input_identities_sha256": _sha256_file(identities_path),
        }
        if observed["video_sha256"] != row["video_sha256"]:
            raise RuntimeError(f"{video_id} video hash changed")
        if observed["input_identities_sha256"] != row["input_identities_sha256"]:
            raise RuntimeError(f"{video_id} input identities hash changed")
        identities = [
            json.loads(line)
            for line in identities_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        unit_ids = [int(identity["unit_id"]) for identity in identities]
        if unit_ids != list(range(len(unit_ids))):
            raise RuntimeError(f"{video_id} input identities are not contiguous")
        for identity in identities:
            build = identity.get("oracle_build_id", identity.get("build_id"))
            if build != row["oracle_build_id"]:
                raise RuntimeError(f"{video_id} identity has wrong oracle build")
            if identity.get("prompt_hash") != configuration["prompt_sha256"]:
                raise RuntimeError(f"{video_id} identity has wrong prompt hash")
            if identity.get("video_sha256") != row["video_sha256"]:
                raise RuntimeError(f"{video_id} identity has wrong video hash")
        verified_videos[video_id] = {
            **observed,
            "units": len(identities),
            "oracle_build_id": row["oracle_build_id"],
        }
    queries = dict(configuration["queries"])
    if set(queries) != {"Q1", "Q2"}:
        raise ValueError("physical oracle requires exactly Q1 and Q2")
    for query_id, row in queries.items():
        if set(row) != {"allowed_involved_objects"}:
            raise ValueError(f"{query_id} projection schema mismatch")
        allowed = list(row["allowed_involved_objects"])
        if not allowed or allowed != sorted(set(map(str, allowed))):
            raise ValueError(f"{query_id} projection objects must be nonempty sorted unique strings")
    model_directory = Path(configuration["model_path"])
    declared = {str(row["file"]): row for row in configuration["model_file_identity"]}
    current_names = {path.name for path in model_directory.iterdir() if path.is_file()}
    if current_names != set(declared):
        raise RuntimeError("physical oracle model-directory membership changed")
    for name, row in declared.items():
        stat = (model_directory / name).stat()
        if stat.st_size != int(row["size_bytes"]) or stat.st_mtime_ns != int(row["mtime_ns"]):
            raise RuntimeError(f"physical oracle model file changed after freeze: {name}")
    return {
        "configuration_sha256": _canonical_hash(configuration),
        "frozen_oracle_source_sha256": configuration["frozen_oracle_source_sha256"],
        "prompt_sha256": configuration["prompt_sha256"],
        "model_full_content_hash": configuration["model_full_content_hash"],
        "model_file_count": len(declared),
        "videos": verified_videos,
        "queries": queries,
    }


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


def _service_main(connection, configuration: dict[str, Any]) -> None:
    import gc
    import os
    import time
    from datetime import datetime, timezone

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    try:
        import cv2
        import torch
        from PIL import Image
        from qwen_vl_utils import process_vision_info
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        verified = verify_two_video_configuration(configuration)
        frozen = _load_module(
            "psvr_two_video_frozen_strict_oracle",
            configuration["frozen_oracle_source"],
        )
        identities_by_video: dict[str, dict[int, dict[str, Any]]] = {}
        fps_by_video: dict[str, float] = {}
        for video_id, video in configuration["videos"].items():
            identities = [
                json.loads(line)
                for line in Path(video["input_identities_path"]).read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            identities_by_video[video_id] = {
                int(identity["unit_id"]): identity for identity in identities
            }
            cap = cv2.VideoCapture(str(video["video_path"]))
            fps_by_video[video_id] = float(cap.get(cv2.CAP_PROP_FPS))
            cap.release()
        prompt = Path(configuration["prompt_path"]).read_text(encoding="utf-8")
        load_start = time.perf_counter_ns()
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            configuration["model_path"],
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        processor = AutoProcessor.from_pretrained(
            configuration["model_path"], trust_remote_code=True
        )
        model.eval()
        torch.cuda.synchronize()
        initialization_seconds = (time.perf_counter_ns() - load_start) / 1e9
        connection.send(
            (
                "ready",
                {
                    "pid": os.getpid(),
                    "initialization_seconds": initialization_seconds,
                    "physical_oracle": True,
                    "cache_loaded": False,
                    "persistent_model_across_logical_sessions": True,
                    "verified_configuration": verified,
                    "torch_version": torch.__version__,
                    "torch_cuda_version": torch.version.cuda,
                },
            )
        )
        active: dict[str, Any] | None = None
        while True:
            request = connection.recv()
            operation = request[0]
            if operation == "shutdown":
                if active is not None:
                    connection.send(("error", "cannot shutdown with active logical session"))
                    continue
                connection.send(("ok", None))
                break
            if operation == "start_session":
                if active is not None:
                    connection.send(("error", "a logical oracle session is already active"))
                    continue
                session_id, video_id, query_id = map(str, request[1:4])
                if video_id not in identities_by_video or query_id not in configuration["queries"]:
                    connection.send(("error", "unknown frozen video/query task"))
                    continue
                active = {
                    "session_id": session_id,
                    "video_id": video_id,
                    "query_id": query_id,
                    "queried": [],
                    "physical_calls": 0,
                }
                connection.send(
                    (
                        "ok",
                        {
                            "session_id": session_id,
                            "video_id": video_id,
                            "query_id": query_id,
                            "prior_query_count": 0,
                        },
                    )
                )
                continue
            if operation == "end_session":
                session_id = str(request[1])
                if active is None or active["session_id"] != session_id:
                    connection.send(("error", "logical oracle session identity mismatch"))
                    continue
                summary = {
                    "session_id": session_id,
                    "video_id": active["video_id"],
                    "query_id": active["query_id"],
                    "physical_calls": active["physical_calls"],
                    "queried_ids": sorted(set(active["queried"])),
                }
                active = None
                connection.send(("ok", summary))
                continue
            if operation not in {
                "session_query",
                "session_queried_ids",
                "session_query_count",
            }:
                connection.send(
                    ("error", "operation is not in the trusted physical-oracle protocol")
                )
                continue
            session_id = str(request[1])
            if active is None or active["session_id"] != session_id:
                connection.send(("error", "stale or inactive logical oracle accessor"))
                continue
            if operation == "session_queried_ids":
                connection.send(("ok", tuple(sorted(set(active["queried"])))))
                continue
            if operation == "session_query_count":
                connection.send(("ok", len(active["queried"])))
                continue
            unit_id = int(request[2])
            if unit_id in active["queried"]:
                connection.send(("error", f"duplicate query: {unit_id}"))
                continue
            video_id = active["video_id"]
            identity = identities_by_video[video_id].get(unit_id)
            if identity is None:
                connection.send(("error", f"unknown unit: {unit_id}"))
                continue
            video_path = str(configuration["videos"][video_id]["video_path"])
            try:
                frozen.VIDEO = Path(video_path)
                torch.cuda.synchronize()
                total_start = time.perf_counter_ns()
                start = time.perf_counter_ns()
                frames = frozen.frames_for_unit(
                    float(identity["start_time"]),
                    float(identity["end_time"]),
                    fps_by_video[video_id],
                )
                indices = [int(frame["decoded_index"]) for frame in frames]
                contents = [frame["content_sha256"] for frame in frames]
                if frozen.canonical_hash(indices) != identity["decoded_frame_indices_sha256"]:
                    raise RuntimeError("decoded frame indices changed")
                if frozen.canonical_hash(contents) != identity["decoded_frame_content_sha256"]:
                    raise RuntimeError("decoded frame contents changed")
                clip_extraction = (time.perf_counter_ns() - start) / 1e9

                start = time.perf_counter_ns()
                pil_frames = [Image.fromarray(frame["rgb"]) for frame in frames]
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "video",
                                "video": pil_frames,
                                "fps": frozen.FRAME_CONFIG["message_fps"],
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ]
                prompt_text = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = processor(
                    text=[prompt_text],
                    images=image_inputs,
                    videos=video_inputs,
                    padding=True,
                    return_tensors="pt",
                ).to(model.device)
                rng_seed = int(identity["rng_seed"])
                frozen.configure_rng(rng_seed, torch)
                preprocessing = (time.perf_counter_ns() - start) / 1e9

                torch.cuda.synchronize()
                start = time.perf_counter_ns()
                with torch.no_grad():
                    generated = model.generate(
                        **inputs,
                        do_sample=False,
                        max_new_tokens=frozen.GENERATION_CONFIG["max_new_tokens"],
                    )
                torch.cuda.synchronize()
                inference = (time.perf_counter_ns() - start) / 1e9

                start = time.perf_counter_ns()
                trimmed = [
                    output[len(input_ids) :]
                    for input_ids, output in zip(inputs.input_ids, generated)
                ]
                raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
                postprocessing = (time.perf_counter_ns() - start) / 1e9
                start = time.perf_counter_ns()
                parsed, parse_status = frozen.parse_response(raw)
                projected_label = project_generic_label(
                    parsed,
                    set(
                        configuration["queries"][active["query_id"]][
                            "allowed_involved_objects"
                        ]
                    ),
                )
                parsing = (time.perf_counter_ns() - start) / 1e9

                start = time.perf_counter_ns()
                del inputs, generated, frames, pil_frames
                del image_inputs, video_inputs, messages
                gc.collect()
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                cleanup = (time.perf_counter_ns() - start) / 1e9
                service_total = (time.perf_counter_ns() - total_start) / 1e9
                active["queried"].append(unit_id)
                active["physical_calls"] += 1
                result = {
                    "session_id": active["session_id"],
                    "video_id": video_id,
                    "query_id": active["query_id"],
                    "unit_id": unit_id,
                    "start_time": float(identity["start_time"]),
                    "end_time": float(identity["end_time"]),
                    "parsed_label": projected_label,
                    "generic_parsed_label": str(
                        parsed.get("label", "abstain")
                    ).lower(),
                    "confidence": str(parsed.get("confidence", "low")).lower(),
                    "parsed": parsed,
                    "parse_status": parse_status,
                    "raw": raw,
                    "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "physical_oracle_invocation": True,
                    "cache_replay": False,
                    "logical_oracle_call": True,
                    "cuda_synchronized_before_and_after": True,
                    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
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
                    "oracle_build_id": configuration["videos"][video_id][
                        "oracle_build_id"
                    ],
                    "rng_seed": rng_seed,
                    "projection_allowed_involved_objects": configuration["queries"][
                        active["query_id"]
                    ]["allowed_involved_objects"],
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


class TwoVideoPhysicalOracleHandle:
    """Trusted launcher handle; session controls are never exposed to policy."""

    def __init__(self, connection, process: mp.Process, initialization: dict[str, Any]):
        self._connection = connection
        self._process = process
        self._active_session: str | None = None
        self.initialization = dict(initialization)

    def _request(self, message: tuple):
        self._connection.send(message)
        status, payload = self._connection.recv()
        if status != "ok":
            raise RuntimeError(str(payload))
        return payload

    def start_session(
        self, session_id: str, video_id: str, query_id: str
    ) -> tuple[OracleAccessor, dict[str, Any]]:
        if self._active_session is not None:
            raise RuntimeError("trusted launcher already has an active oracle session")
        session_id = str(session_id)
        initialization = dict(
            self._request(("start_session", session_id, str(video_id), str(query_id)))
        )
        self._active_session = session_id

        def request(message: tuple):
            operation = message[0]
            if operation == "query":
                return self._request(("session_query", session_id, int(message[1])))
            if operation == "queried_ids":
                return self._request(("session_queried_ids", session_id))
            if operation == "query_count":
                return self._request(("session_query_count", session_id))
            raise RuntimeError("operation is not in the OracleAccessor protocol")

        return OracleAccessor(request), initialization

    def end_session(self, session_id: str) -> dict[str, Any]:
        if self._active_session != str(session_id):
            raise RuntimeError("trusted launcher session identity mismatch")
        summary = dict(self._request(("end_session", str(session_id))))
        self._active_session = None
        return summary

    def close(self) -> None:
        if self._active_session is not None:
            raise RuntimeError("refusing to close physical oracle with active session")
        if self._process.is_alive():
            self._request(("shutdown",))
            self._process.join(timeout=30)
        self._connection.close()
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=10)


def start_two_video_physical_oracle_service(
    configuration: dict[str, Any],
) -> TwoVideoPhysicalOracleHandle:
    context = mp.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(target=_service_main, args=(child, dict(configuration)))
    process.start()
    child.close()
    status, payload = parent.recv()
    if status != "ready":
        process.join(timeout=10)
        raise RuntimeError(f"two-video physical oracle startup failed: {payload}")
    return TwoVideoPhysicalOracleHandle(parent, process, dict(payload))
