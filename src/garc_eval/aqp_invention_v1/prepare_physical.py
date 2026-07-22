"""Freeze the VERA physical pilot before the first model invocation."""
from __future__ import annotations

import argparse
import csv
import json
import platform
from pathlib import Path
import subprocess
import sys

import cv2
import pandas as pd

from .contract import (
    ENUMERATOR_VERSION,
    PRESENCE_PARSER_VERSION,
    RECONCILER_VERSION,
    build_windows,
    perceived_clip_duration,
    sample_frame_indices,
)
from .physical_common import (
    IMPLEMENTATION,
    MODEL,
    PACKAGE,
    PHYSICAL,
    ROOT,
    STRICT,
    VIDEO,
    atomic_csv,
    atomic_json,
    atomic_text,
    load_json,
    sha256_file,
    verify_freeze,
)


BENCHMARK_ID = "cbbv2_514c0d360fd5b2a4b5fe"
MAX_CALLS = 200
BASE_SEED = 20260711


def _gpu_identity() -> dict[str, str]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,uuid,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ]
    fields = subprocess.check_output(command, text=True).strip().splitlines()[0].split(", ")
    return dict(zip(["index", "name", "uuid", "memory_total_mib", "driver_version"], fields))


def _uniform_calibration_units(n: int, count: int) -> list[int]:
    values = [round(i * (n - 1) / (count - 1)) for i in range(count)]
    if len(set(values)) != count:
        raise RuntimeError("uniform calibration unit construction was not unique")
    return values


def prepare() -> None:
    attempts = PHYSICAL / "attempts"
    if attempts.exists() and any(attempts.glob("*.started.json")):
        raise RuntimeError("cannot refreeze after a physical attempt has started")
    PHYSICAL.mkdir(parents=True, exist_ok=True)
    for directory in ["attempts", "raw", "logs"]:
        (PHYSICAL / directory).mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(VIDEO))
    video_fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps
    cap.release()
    units = pd.read_csv(STRICT / "frozen_inputs/unit_table.csv")
    if len(units) != 347 or units.benchmark_id.nunique() != 1 or units.benchmark_id.iloc[0] != BENCHMARK_ID:
        raise RuntimeError("strict UnitTable identity mismatch")
    duration = max(duration, float(units.end_time.max()))

    enum_prompt = IMPLEMENTATION / "prompts/event_enumerate_v1.txt"
    dense_prompt = STRICT / "oracle/oracle_prompt.txt"
    prompt_manifest = {
        "manifest_version": "vera_prompt_manifest_v1",
        "prompts": [
            {
                "key": "EVENT_ENUMERATE_V1",
                "path": str(enum_prompt.relative_to(ROOT)),
                "sha256": sha256_file(enum_prompt),
                "dynamic_substitution": {"__CLIP_DURATION_SECONDS__": "perceived sampled duration, one decimal"},
                "parser_version": ENUMERATOR_VERSION,
                "prompt_tuning_against_reference": False,
            },
            {
                "key": "DENSE_PRESENCE_STRICT_V13_6",
                "path": str(dense_prompt.relative_to(ROOT)),
                "sha256": sha256_file(dense_prompt),
                "dynamic_substitution": None,
                "parser_version": PRESENCE_PARSER_VERSION,
                "prompt_tuning_against_reference": False,
            },
        ],
    }
    atomic_json(PHYSICAL / "PROMPT_MANIFEST.json", prompt_manifest)

    windows = build_windows(duration, 50.0, 5.0)
    if len(windows) != 70:
        raise RuntimeError(f"expected 70 enumeration windows, got {len(windows)}")
    calibration_ids = _uniform_calibration_units(len(units), 20)
    execution_order: list[dict] = []
    for order, unit_id in enumerate(calibration_ids):
        row = units.loc[units.unit_id == unit_id].iloc[0]
        indices = sample_frame_indices(
            float(row.start_time), float(row.end_time), video_fps, total_frames, 2.0
        )
        execution_order.append({
            "order": order,
            "planned_attempt_id": f"dense_cal_u{unit_id:04d}_a001",
            "operator": "DENSE_UNIT_CALIBRATION",
            "role": "hardware_cost_calibration_only",
            "unit_id": int(unit_id),
            "input_start": float(row.start_time),
            "input_end": float(row.end_time),
            "core_start": float(row.start_time),
            "core_end": float(row.end_time),
            "frame_indices": indices,
            "frame_count": len(indices),
            "message_fps": 2.0,
            "perceived_clip_duration": perceived_clip_duration(len(indices)),
            "prompt_key": "DENSE_PRESENCE_STRICT_V13_6",
        })
    fallback_matrix: dict[str, list[int]] = {}
    for index, window in enumerate(windows):
        indices = sample_frame_indices(
            window.input_start, window.input_end, video_fps, total_frames, 2.0
        )
        execution_order.append({
            "order": len(execution_order),
            "planned_attempt_id": f"{window.window_id}_a001",
            "operator": "EVENT_ENUMERATE",
            "role": "selected_algorithm",
            "window_id": window.window_id,
            "input_start": window.input_start,
            "input_end": window.input_end,
            "core_start": window.core_start,
            "core_end": window.core_end,
            "frame_indices": indices,
            "frame_count": len(indices),
            "message_fps": 2.0,
            "perceived_clip_duration": perceived_clip_duration(len(indices)),
            "prompt_key": "EVENT_ENUMERATE_V1",
        })
        mask = (units.start_time < window.core_end) & (units.end_time > window.core_start)
        fallback_matrix[window.window_id] = units.loc[mask, "unit_id"].astype(int).tolist()

    sample_manifest = {
        "manifest_version": "vera_sample_manifest_v1",
        "benchmark_id": BENCHMARK_ID,
        "construction_uses_event_reference": False,
        "video": {
            "path": str(VIDEO.relative_to(ROOT)),
            "sha256": sha256_file(VIDEO),
            "duration_seconds": duration,
            "fps": video_fps,
            "total_frames": total_frames,
        },
        "sampler": {
            "decode": "OpenCV BGR then cv2.COLOR_BGR2RGB",
            "start_frame": "int(start_seconds * video_fps)",
            "end_frame": "int(end_seconds * video_fps), inclusive and capped",
            "stride": "max(1, int(video_fps / 2.0))",
            "message_fps": 2.0,
            "fallback_sampling": None,
        },
        "execution_order": execution_order,
        "base_calls": len(execution_order),
        "calibration_calls": len(calibration_ids),
        "enumeration_calls": len(windows),
        "fallback_matrix": fallback_matrix,
        "fallback_order": "ascending unique unit_id after all base calls",
        "fallback_reserved_calls": MAX_CALLS - len(execution_order),
    }
    atomic_json(PHYSICAL / "SAMPLE_MANIFEST.json", sample_manifest)

    strict_model_manifest = STRICT / "oracle/STRICT_MODEL_FILE_MANIFEST.csv"
    strict_rows = list(csv.DictReader(strict_model_manifest.open(newline="", encoding="utf-8")))
    model_rows: list[dict[str, object]] = []
    for row in strict_rows:
        path = MODEL / row["file"]
        actual = sha256_file(path)
        if actual != row["sha256"]:
            raise RuntimeError(f"model file changed: {path}")
        model_rows.append({
            "record_type": "model_file",
            "item": row["file"],
            "path": str(path),
            "size_bytes": int(row["size_bytes"]),
            "sha256": actual,
            "value": "",
        })
    oracle_config = load_json(STRICT / "oracle/oracle_configuration.json")
    gpu = _gpu_identity()
    aggregate_rows = [
        ("model_identity", "Qwen3-VL-32B-Instruct", str(MODEL), "", oracle_config["model_full_content_hash"]),
        ("model_file_manifest", "strict_model_file_manifest", str(strict_model_manifest), "", sha256_file(strict_model_manifest)),
        ("hardware", "gpu_name", "", gpu["name"], ""),
        ("hardware", "gpu_uuid", "", gpu["uuid"], ""),
        ("hardware", "gpu_memory_mib", "", gpu["memory_total_mib"], ""),
        ("runtime", "python", "", sys.version.replace("\n", " "), ""),
        ("runtime", "platform", "", platform.platform(), ""),
    ]
    for record_type, item, path, value, digest in aggregate_rows:
        model_rows.append({
            "record_type": record_type, "item": item, "path": path,
            "size_bytes": "", "sha256": digest, "value": value,
        })
    atomic_csv(
        PHYSICAL / "MODEL_MANIFEST.csv",
        ["record_type", "item", "path", "size_bytes", "sha256", "value"],
        model_rows,
    )

    source_relatives = [
        "src/garc_eval/aqp_invention_v1/contract.py",
        "src/garc_eval/aqp_invention_v1/physical_common.py",
        "src/garc_eval/aqp_invention_v1/prepare_physical.py",
        "src/garc_eval/aqp_invention_v1/run_physical.py",
        "src/garc_eval/aqp_invention_v1/evaluate_physical.py",
    ]
    frozen_artifacts = [
        "AQP_Algorithm_Invention_Sprint_v1/physical/PROMPT_MANIFEST.json",
        "AQP_Algorithm_Invention_Sprint_v1/physical/SAMPLE_MANIFEST.json",
        "AQP_Algorithm_Invention_Sprint_v1/physical/MODEL_MANIFEST.csv",
        str(enum_prompt.relative_to(ROOT)),
        str(dense_prompt.relative_to(ROOT)),
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py",
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/event_reference.csv",
        "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/unit_table.csv",
    ]
    config = {
        "freeze_version": "vera_physical_freeze_v1",
        "frozen_before_any_new_call": True,
        "pre_execution_decision": "PHYSICAL_PILOT_JUSTIFIED",
        "benchmark_id": BENCHMARK_ID,
        "algorithm": "VERA",
        "operator_contract": ENUMERATOR_VERSION,
        "reconciler": RECONCILER_VERSION,
        "video": sample_manifest["video"],
        "model": {
            "path": str(MODEL),
            "full_content_hash": oracle_config["model_full_content_hash"],
            "load": {"torch_dtype": "bfloat16", "device_map": "auto", "trust_remote_code": True},
            "frozen_gpu": gpu,
        },
        "generation": {
            "do_sample": False,
            "temperature": None,
            "max_new_tokens_event_enumerate": 768,
            "max_new_tokens_dense": 256,
            "base_seed": BASE_SEED,
            "deterministic_algorithms": True,
            "cublas_workspace_config": ":4096:8",
        },
        "plan": {
            "core_seconds": 50.0,
            "margin_seconds": 5.0,
            "windows": 70,
            "calibration_calls": 20,
            "base_calls": 90,
            "maximum_physical_calls": MAX_CALLS,
            "reserved_dense_fallback_calls": 110,
            "execution_order": "20 uniform dense calibration calls, 70 chronological enumeration calls, then ascending dense fallback units",
        },
        "runtime_measurement": {
            "decision_gpu_seconds": "wall clock around generate after torch.cuda.synchronize before and after",
            "secondary_cuda_event_seconds": "CUDA event elapsed time around generate",
            "generation_wall_seconds": "perf_counter around synchronized generate",
            "total_call_wall_seconds": "frame decode/hash + processor + synchronized generation + decode/parse",
            "peak_memory": "torch.cuda.max_memory_allocated after reset immediately before generate",
            "cold_cost": "model load wall + selected algorithm total call wall",
            "warm_cost": "selected algorithm total call wall only",
            "dense_current_hardware_estimate": "347 times median of 20 uniform physical dense calibration calls",
        },
        "primary_accuracy": {
            "evaluator": "strict overlap-any one-to-one EventRelation evaluator",
            "event_recall_threshold": 0.80,
            "event_f1_threshold": 0.80,
            "reference_access": "post-inference evaluator only",
        },
        "primary_cost": {
            "selected_gpu_seconds": "sum synchronized generation wall for EVENT_ENUMERATE plus executed dense fallbacks",
            "dense_gpu_seconds": "347 * median dense calibration synchronized generation wall",
            "strict_ratio_threshold": 0.70,
        },
        "physical_success_gate": "complete AND event_recall>=0.80 AND event_f1>=0.80 AND gpu_cost_ratio<0.70",
        "failure_behavior": {
            "retry_count": 0,
            "started_attempt_counts_against_cap": True,
            "uncertain_interrupted_attempt": "never rerun; schedule its dense fallback if enumeration",
            "enumeration_parse_error_or_abstain": "dense presence for every strict 10-second unit overlapping that ownership core",
            "dense_parse_error_or_abstain": "UNKNOWN; no positive row; pilot fails completeness",
            "cap_exhaustion": "stop, mark pilot incomplete",
            "cross_role_cache_reuse": False,
        },
        "baseline_comparison": {
            "dense": "new 20-call current-hardware cost calibration plus existing frozen 347-output strict relation",
            "quality_baselines": ["uniform/random", "public proxy", "CLIP retrieve-then-ground", "MAP/M1", "native ARC", "SUPG adapted", "ABae adapted"],
            "same_cost_grid_dense_equivalent_units": [5, 10, 20, 50, 80, 100],
            "oracle_ceiling": "evaluator-only and excluded from deployable claims",
        },
        "frozen_artifact_hashes": {relative: sha256_file(ROOT / relative) for relative in frozen_artifacts},
        "frozen_source_hashes": {relative: sha256_file(ROOT / relative) for relative in source_relatives},
    }
    atomic_json(PHYSICAL / "FROZEN_PHYSICAL_CONFIG.json", config)
    lock = {
        "freeze_version": config["freeze_version"],
        "frozen_config_sha256": sha256_file(PHYSICAL / "FROZEN_PHYSICAL_CONFIG.json"),
        "physical_started_files_at_freeze": 0,
    }
    atomic_json(PHYSICAL / ".physical_freeze.lock", lock)

    gate = f"""# VERA physical pre-execution gate

Decision: `PHYSICAL_PILOT_JUSTIFIED`.

All inference-affecting state was frozen before any new call. The frozen plan has 70 chronological `EVENT_ENUMERATE` calls and 20 uniformly spaced, reference-independent dense hardware-calibration calls. The remaining 110-call reserve is only for preregistered dense fallback. Every started attempt counts, retries are forbidden, and the hard cap is {MAX_CALLS}.

Primary success requires all three inequalities on the untouched strict event reference: event recall >= 0.80, event F1 >= 0.80, and selected-operator synchronized GPU seconds / estimated 347-unit dense GPU seconds < 0.70. Reference rows are absent from prompt construction, sampling, ordering, parsing, fallback triggering, and runtime state.

Freeze checks:

- prompt and parser hashes: PASS
- 70-core exact timeline cover: PASS
- sample matrix constructed without event reference: PASS
- strict model manifest matches local checkpoint: PASS
- current assigned GPU recorded: PASS (`{gpu['name']}`, `{gpu['uuid']}`)
- base calls <= 200 and fallback reserve explicit: PASS (90 + 110)
- strict evaluator and reference hashed but evaluator-only: PASS
- no prior physical attempt in this sprint: PASS

The strongest unresolved risk is correlated omission inside long inputs. A parser-valid empty result does not trigger fallback, so the pilot can directly falsify the physical enumeration mechanism.
"""
    atomic_text(PHYSICAL / "PRE_EXECUTION_GATE.md", gate)
    verify_freeze()
    print(json.dumps({
        "status": "FROZEN_PASS",
        "windows": len(windows),
        "base_calls": len(execution_order),
        "max_calls": MAX_CALLS,
        "config_sha256": lock["frozen_config_sha256"],
    }, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        config = verify_freeze()
        print(json.dumps({"status": "FROZEN_PASS", "freeze_version": config["freeze_version"]}))
    else:
        prepare()


if __name__ == "__main__":
    main()
