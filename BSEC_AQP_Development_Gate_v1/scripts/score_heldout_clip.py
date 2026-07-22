#!/usr/bin/env python3
"""Label-blind CLIP scoring for the frozen realcartest held-out interval."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import platform
import sys
import time
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
FROZEN = PACKAGE / "config" / "frozen_protocol.json"
PROTOCOL_HASHES = {
    "frozen_protocol.json": "4eea29f266f35be771ee430bb04221babe32c48adffc7bd7dd4a64e3ac7fd42a",
    "frozen_continuation_v2.json": "f62800ece1edee2751afa646efe8d8d344dd8a04de3b1392c9845d0aa15e1daa",
    "frozen_continuation_v3.json": "5fad1ac9b59430d9d19363c66c55001d33b5da9fc1c56552081d611336ee61ef",
}
GATE_A_RUNNER = REPO / "DARE_AQP_Experiment_v1" / "scripts" / "run_gate_a_inference.py"
SCENE_WINDOWS = (
    REPO / "experiments" / "roadclip_budget_v2" / "roadclip_budget_v2" / "scene_windows"
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_gate_a_runner():
    spec = importlib.util.spec_from_file_location("frozen_gate_a_runner", GATE_A_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GATE_A_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_window(unit_id: int, absolute_index_start: int) -> Path:
    absolute_index = absolute_index_start + unit_id
    start_ms = absolute_index * 10_000
    end_ms = start_ms + 10_000
    name = (
        f"realcartest_win{absolute_index:05d}_"
        f"s{start_ms:09d}ms_e{end_ms:09d}ms.mp4"
    )
    return SCENE_WINDOWS / name


def read_checkpoint(path: Path, expected: dict) -> dict | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise RuntimeError(
                f"checkpoint identity mismatch at {path}: {key}="
                f"{value.get(key)!r}, expected {expected_value!r}"
            )
    embedding = value.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != 512:
        raise RuntimeError(f"invalid CLIP embedding at {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=PACKAGE / "outputs" / "heldout" / "clip_inference"
    )
    parser.add_argument("--protocol", type=Path, default=FROZEN)
    parser.add_argument("--unit-count", type=int, default=120)
    parser.add_argument("--absolute-index-start", type=int, default=200)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--threads", type=int, default=31)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    expected_hash = PROTOCOL_HASHES.get(args.protocol.name)
    if expected_hash is None:
        raise RuntimeError(f"unrecognized frozen protocol: {args.protocol}")
    frozen_hash = sha256_file(args.protocol)
    if frozen_hash != expected_hash:
        raise RuntimeError(
            f"frozen protocol changed: {frozen_hash} != {expected_hash}"
        )
    config = json.loads(args.protocol.read_text(encoding="utf-8"))
    clip = config["clip"]
    if args.unit_count < 1 or args.absolute_index_start < 0:
        raise ValueError("invalid unit population")
    unit_ids = list(range(args.unit_count))
    sources = [source_window(unit_id, args.absolute_index_start) for unit_id in unit_ids]
    absolute_start = 10.0 * args.absolute_index_start
    absolute_end = absolute_start + 10.0 * args.unit_count
    missing = [str(path) for path in sources if not path.is_file()]
    audit = {
        "status": "DRY_RUN_ONLY" if not args.execute else "EXECUTING",
        "frozen_protocol": str(args.protocol),
        "frozen_protocol_sha256": frozen_hash,
        "units": len(unit_ids),
        "relative_interval_seconds": [0.0, 10.0 * args.unit_count],
        "absolute_interval_seconds": [absolute_start, absolute_end],
        "source_windows_found": len(sources) - len(missing),
        "missing_source_windows": missing,
        "model_id": clip["model_id"],
        "model_revision": clip["revision"],
        "query_text": config["query_text"],
        "sampling": clip["sampling"],
        "device": args.device,
        "cpu_threads": args.threads,
        "forbidden_label_or_reference_inputs_opened": [],
        "downloads_allowed": False,
    }
    print(json.dumps(audit, indent=2), flush=True)
    if not args.execute:
        return
    if missing:
        raise RuntimeError(f"held-out media recovery incomplete: {len(missing)} missing windows")

    import torch
    import transformers

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if args.threads < 1:
        raise ValueError("--threads must be positive")
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(min(4, args.threads))
    torch.manual_seed(20260712)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    runner = load_gate_a_runner()
    spec = {
        "model_id": clip["model_id"],
        "revision": clip["revision"],
    }
    started = time.perf_counter()
    processor, model, model_load_seconds = runner.load_model("image_text", spec, args.device)
    embeddings: dict[int, list[float]] = {}
    mapping_rows: list[dict] = []
    checkpoint_rows: list[dict] = []
    checkpoint_dir = args.output / "checkpoints"
    cache_hits = 0
    for ordinal, (unit_id, source) in enumerate(zip(unit_ids, sources), 1):
        source_hash = sha256_file(source)
        checkpoint_path = checkpoint_dir / f"unit_{unit_id:04d}.json"
        identity = {
            "signal_id": "image_text",
            "model_id": clip["model_id"],
            "model_revision": clip["revision"],
            "unit_id": unit_id,
            "source_sha256": source_hash,
            "relative_timestamp_seconds": 5.0,
        }
        record = read_checkpoint(checkpoint_path, identity)
        if record is None:
            frames, loading_seconds = runner.extract_rgb_frames(source, [5.0])
            if len(frames) != 1:
                raise RuntimeError(f"expected one decoded frame for unit {unit_id}")
            frame_hash = sha256_bytes(frames[0].tobytes())
            embedding, _, preprocessing_seconds, forward_seconds = runner.embed_unit(
                "image_text", processor, model, frames, args.device
            )
            record = {
                **identity,
                "source_path": str(source),
                "absolute_timestamp_seconds": absolute_start + 5.0 + 10.0 * unit_id,
                "decoded_frame_sha256": frame_hash,
                "frames": 1,
                "data_loading_seconds": loading_seconds,
                "preprocessing_cpu_seconds": preprocessing_seconds,
                "model_forward_seconds": forward_seconds,
                "embedding": embedding,
            }
            runner.atomic_json(checkpoint_path, record)
        else:
            cache_hits += 1
        embeddings[unit_id] = record["embedding"]
        checkpoint_hash = sha256_file(checkpoint_path)
        mapping_rows.append(
            {
                "unit_id": unit_id,
                "relative_start_time": 10.0 * unit_id,
                "relative_end_time": 10.0 * (unit_id + 1),
                "absolute_start_time": absolute_start + 10.0 * unit_id,
                "absolute_end_time": absolute_start + 10.0 * (unit_id + 1),
                "absolute_center_time": absolute_start + 5.0 + 10.0 * unit_id,
                "source_path": str(source),
                "source_sha256": source_hash,
                "requested_relative_timestamp_seconds": 5.0,
                "decoded_frame_sha256": record["decoded_frame_sha256"],
                "checkpoint_path": str(checkpoint_path),
                "checkpoint_sha256": checkpoint_hash,
            }
        )
        checkpoint_rows.append(
            {
                "unit_id": unit_id,
                "path": str(checkpoint_path),
                "sha256": checkpoint_hash,
            }
        )
        if ordinal == 1 or ordinal % 10 == 0 or ordinal == len(unit_ids):
            print(
                f"image_text heldout: {ordinal}/{len(unit_ids)} cache_hits={cache_hits}",
                flush=True,
            )

    values, text_prep, text_forward, similarity, ranking_seconds = runner.score_index(
        "image_text",
        processor,
        model,
        config["query_text"],
        embeddings,
        unit_ids,
        args.device,
    )
    score_rows = [
        {
            "signal_id": "image_text",
            "unit_id": unit_id,
            "score": repr(values[unit_id]),
            "model_id": clip["model_id"],
            "model_revision": clip["revision"],
            "prompt_id": clip["prompt_id"],
        }
        for unit_id in unit_ids
    ]
    order = sorted(unit_ids, key=lambda unit_id: (-values[unit_id], unit_id))
    ranking_rows = [
        {
            "signal_id": "image_text",
            "rank": rank,
            "unit_id": unit_id,
            "score": repr(values[unit_id]),
        }
        for rank, unit_id in enumerate(order, 1)
    ]
    runtime_rows = [
        {
            "device": args.device,
            "cpu_threads": torch.get_num_threads(),
            "cpu_interop_threads": torch.get_num_interop_threads(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "model_load_seconds": model_load_seconds,
            "total_wall_seconds": time.perf_counter() - started,
            "text_preprocessing_seconds": text_prep,
            "text_forward_seconds": text_forward,
            "similarity_seconds": similarity,
            "ranking_seconds": ranking_seconds,
            "checkpoint_cache_hits": cache_hits,
            "physical_exact_oracle_vlm_calls": 0,
        }
    ]
    runner.atomic_csv(args.output / "clip_scores.csv", score_rows)
    runner.atomic_csv(args.output / "sealed_ranking.csv", ranking_rows)
    runner.atomic_csv(args.output / "media_mapping.csv", mapping_rows)
    runner.atomic_csv(args.output / "checkpoint_manifest.csv", checkpoint_rows)
    runner.atomic_csv(args.output / "runtime.csv", runtime_rows)
    completion = {
        **audit,
        "status": "COMPLETE",
        "python": sys.version,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "scores_sha256": sha256_file(args.output / "clip_scores.csv"),
        "ranking_sha256": sha256_file(args.output / "sealed_ranking.csv"),
        "media_mapping_sha256": sha256_file(args.output / "media_mapping.csv"),
        "checkpoint_manifest_sha256": sha256_file(args.output / "checkpoint_manifest.csv"),
        "physical_exact_oracle_vlm_calls": 0,
    }
    runner.atomic_json(args.output / "INFERENCE_COMPLETE.json", completion)
    print(args.output / "INFERENCE_COMPLETE.json", flush=True)


if __name__ == "__main__":
    main()
