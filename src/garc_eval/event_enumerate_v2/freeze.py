"""Freeze the single corrected processor path before any semantic call."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path

from .temporal_contract import (
    CONTRACT_VERSION,
    MAX_DECODED_FRAMES,
    MAX_INTERVAL_SECONDS,
    PARSER_VERSION,
    RECONCILER_VERSION,
    TARGET_SAMPLE_FPS,
    TEMPORAL_PATCH_SIZE,
    TIMESTAMP_DISPLAY_TOLERANCE_SECONDS,
)


ROOT = Path(__file__).resolve().parents[3]
SPRINT = ROOT / "AQP_Algorithm_Invention_Sprint_v1"
OUTPUT = SPRINT / "operator_validation/event_enumerate_v2"
CONFIG = OUTPUT / "config"
MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
OLD_MODEL_MANIFEST = SPRINT / "physical/MODEL_MANIFEST.csv"
PROMPT = ROOT / "src/garc_eval/event_enumerate_v2/prompts/event_enumerate_v2.txt"
OLD_PROMPT = ROOT / "src/garc_eval/aqp_invention_v1/prompts/event_enumerate_v1.txt"
IMPLEMENTATION = ROOT / "src/garc_eval/event_enumerate_v2"
TRANSFORMERS = Path(
    "/qiuyeqing/tools/miniconda3/envs/garc/lib/python3.10/site-packages/transformers"
)
QWEN_UTILS = Path(
    "/qiuyeqing/tools/miniconda3/envs/garc/lib/python3.10/site-packages/qwen_vl_utils"
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_model_manifest() -> None:
    with OLD_MODEL_MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["record_type"] != "model_file":
            continue
        path = Path(row["path"])
        if not path.exists() or path.stat().st_size != int(row["size_bytes"]):
            raise RuntimeError(f"model file missing or size changed: {path}")
    dependency_sources = [
        TRANSFORMERS / "models/qwen3_vl/processing_qwen3_vl.py",
        TRANSFORMERS / "models/qwen3_vl/video_processing_qwen3_vl.py",
        TRANSFORMERS / "video_processing_utils.py",
        TRANSFORMERS / "video_utils.py",
        QWEN_UTILS / "vision_process.py",
    ]
    for path in dependency_sources:
        rows.append(
            {
                "record_type": "processor_source",
                "item": path.name,
                "path": str(path),
                "size_bytes": str(path.stat().st_size),
                "sha256": sha256_file(path),
                "value": "",
            }
        )
    rows.extend(
        [
            {
                "record_type": "runtime",
                "item": "transformers_version",
                "path": "",
                "size_bytes": "",
                "sha256": "",
                "value": importlib.metadata.version("transformers"),
            },
            {
                "record_type": "runtime",
                "item": "transformers_vcs_commit",
                "path": "",
                "size_bytes": "",
                "sha256": "",
                "value": "effde20942e3f82a1b97449f60b3a48c5ff96145",
            },
            {
                "record_type": "runtime",
                "item": "qwen_vl_utils_version",
                "path": "",
                "size_bytes": "",
                "sha256": "",
                "value": importlib.metadata.version("qwen-vl-utils"),
            },
            {
                "record_type": "provenance",
                "item": "prior_audited_model_manifest",
                "path": _relative(OLD_MODEL_MANIFEST),
                "size_bytes": str(OLD_MODEL_MANIFEST.stat().st_size),
                "sha256": sha256_file(OLD_MODEL_MANIFEST),
                "value": "v2 rechecked existence and byte size; prior manifest retains file hashes",
            },
        ]
    )
    path = CONFIG / "MODEL_FILE_MANIFEST.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["record_type", "item", "path", "size_bytes", "sha256", "value"],
        )
        writer.writeheader()
        writer.writerows(rows)


def freeze() -> None:
    attempts = OUTPUT / "physical/attempts"
    if attempts.exists() and any(attempts.iterdir()):
        raise RuntimeError("cannot refreeze after a v2 physical attempt exists")
    CONFIG.mkdir(parents=True, exist_ok=True)
    if sha256_file(PROMPT) != sha256_file(OLD_PROMPT):
        raise RuntimeError("v2 prompt is not byte-identical to the frozen v1 prompt")
    write_model_manifest()

    processor_contract = {
        "contract_version": CONTRACT_VERSION,
        "selection": {
            "strategy_count": 1,
            "rule": "inclusive fixed source-frame stride",
            "start_frame": "int(input_start_seconds * source_fps)",
            "end_frame": "min(total_frames-1, int(input_end_seconds * source_fps))",
            "stride": "max(1, int(source_fps / 2.0))",
            "target_sample_fps": TARGET_SAMPLE_FPS,
            "maximum_interval_seconds": MAX_INTERVAL_SECONDS,
            "maximum_decoded_frames": MAX_DECODED_FRAMES,
        },
        "decode": "OpenCV sequential BGR decode then cv2.COLOR_BGR2RGB",
        "metadata": {
            "required": True,
            "fps": "exact probed source FPS",
            "frames_indices": "selected source index minus first selected source index",
            "total_num_frames": "last relative source index plus one",
            "anchor": "first selected source index divided by source FPS",
            "do_sample_frames": False,
            "return_metadata": True,
        },
        "temporal_patch_size": TEMPORAL_PATCH_SIZE,
        "processor_timestamp_formula": "pair-average(relative source frame index/source FPS), repeat final index for an odd frame count",
        "timestamp_text_precision_decimals": 1,
        "timestamp_display_tolerance_seconds": TIMESTAMP_DISPLAY_TOLERANCE_SECONDS,
        "relative_to_absolute_mapping": "absolute = actual_first_decoded_timestamp + generated_relative_seconds",
        "reconciler": RECONCILER_VERSION,
        "batch_size_for_physical_calls": 1,
        "forbidden": [
            "processor resampling",
            "missing video metadata",
            "timestamp clamping",
            "alternate sampling paths",
            "reference access in inference",
        ],
    }
    write_json(CONFIG / "PROCESSOR_CONTRACT.json", processor_contract)

    prompt_parser = {
        "manifest_version": "event_enumerate_v2_prompt_parser_freeze_v1",
        "frozen_before_semantic_calls": True,
        "semantic_calls_at_freeze": 0,
        "prompt": {
            "path": _relative(PROMPT),
            "sha256": sha256_file(PROMPT),
            "byte_identical_to_v1": True,
            "v1_path": _relative(OLD_PROMPT),
            "dynamic_substitution": {
                "__CLIP_DURATION_SECONDS__": "actual sampled span formatted to one decimal"
            },
            "selected_without_event_accuracy": True,
        },
        "parser": {
            "version": PARSER_VERSION,
            "module": "src/garc_eval/event_enumerate_v2/temporal_contract.py",
            "module_sha256": sha256_file(IMPLEMENTATION / "temporal_contract.py"),
            "repair": False,
            "clamp": False,
            "reference_access": False,
        },
        "thresholds": {
            "event_recall_minimum": 0.8,
            "event_f1_minimum": 0.8,
            "cost": "corrected enumerator synchronized GPU seconds strictly less than matched dense synchronized GPU seconds",
        },
    }
    write_json(CONFIG / "PROMPT_AND_PARSER_MANIFEST.json", prompt_parser)

    source_paths = sorted(
        path
        for path in IMPLEMENTATION.rglob("*.py")
        if "__pycache__" not in path.parts
    ) + [PROMPT]
    config = {
        "freeze_version": "metadata_correct_event_enumerate_operator_gate_v2_freeze_1",
        "freeze_date_utc": "2026-07-12",
        "operator": "EVENT_ENUMERATE",
        "algorithm_changes": False,
        "vera_execution": False,
        "canonical_processor_contract": CONTRACT_VERSION,
        "model": {
            "path": str(MODEL),
            "identity": "Qwen3-VL-32B-Instruct",
            "full_content_hash_from_prior_audited_manifest": "c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210",
            "dtype": "bfloat16",
            "device_map": "auto",
            "substitution_allowed": False,
            "fine_tuning_allowed": False,
        },
        "input": processor_contract,
        "prompt_parser_manifest_sha256": sha256_file(
            CONFIG / "PROMPT_AND_PARSER_MANIFEST.json"
        ),
        "generation": {
            "do_sample": False,
            "max_new_tokens": 768,
            "temperature": None,
            "retry_count": 0,
        },
        "quality_gate": {"event_recall_minimum": 0.8, "event_f1_minimum": 0.8},
        "cost_gate": {
            "rule": "corrected enumerator GPU seconds < matched dense 10-second GPU seconds",
            "old_compressed_runtime_reusable": False,
            "gpu_synchronization_required": True,
            "cold_warm_separate": True,
        },
        "physical_authorization": {
            "maximum_new_calls": 100,
            "new_calls_so_far": 0,
            "calls_permitted_now": False,
            "reason": "held-out data gate has not passed",
        },
        "semantic_call_matrix": {
            "status": "NOT_CREATED",
            "reason": "no valid disjoint held-out reference; terminal data gate precedes preregistration",
        },
        "terminal_decision_if_no_heldout": "HELDOUT_DATA_REQUIRED",
        "frozen_source_hashes": {
            _relative(path): sha256_file(path) for path in source_paths
        },
        "frozen_artifact_hashes": {
            _relative(CONFIG / "PROCESSOR_CONTRACT.json"): sha256_file(
                CONFIG / "PROCESSOR_CONTRACT.json"
            ),
            _relative(CONFIG / "PROMPT_AND_PARSER_MANIFEST.json"): sha256_file(
                CONFIG / "PROMPT_AND_PARSER_MANIFEST.json"
            ),
            _relative(CONFIG / "MODEL_FILE_MANIFEST.csv"): sha256_file(
                CONFIG / "MODEL_FILE_MANIFEST.csv"
            ),
        },
    }
    write_json(CONFIG / "FROZEN_EVENT_ENUMERATE_V2_CONFIG.json", config)
    lock = {
        "freeze_version": config["freeze_version"],
        "frozen_config_sha256": sha256_file(
            CONFIG / "FROZEN_EVENT_ENUMERATE_V2_CONFIG.json"
        ),
        "physical_attempt_files_at_freeze": 0,
        "semantic_calls_at_freeze": 0,
    }
    write_json(CONFIG / ".event_enumerate_v2_freeze.lock", lock)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    freeze()


if __name__ == "__main__":
    main()
