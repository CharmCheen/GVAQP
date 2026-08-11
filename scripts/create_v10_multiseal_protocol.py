#!/usr/bin/env python3
"""Freeze the outcome-blind V10-MS amendment from V9 provenance only.

This command deliberately never aggregates labels, materializes events, or
opens P0 artifacts.  It validates that a V9 raw record has a traceable
terminal semantic field, then emits one admissibility row per frozen unit.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
V9_PACKAGE = BASE / "full_grid_preregistration_staged_v9_runtime_recovery"
V9_EXECUTION = BASE / "full_grid_execution_staged_v9_runtime_recovery"
OUT = ROOT / "outputs/v10_multiseal_reference_v1"
V9_SEAL = V9_PACKAGE / "FULL_GRID_EXECUTION_SEAL.json"

import sys
sys.path.insert(0, str(ROOT / "src"))
from garc_eval.accelerated_event_query.oracle_v3_full_grid_control import _read_jsonl
from garc_eval.accelerated_event_query.oracle_v3_full_grid_analyzer import _validate_record
from garc_eval.accelerated_event_query.oracle_v3_manifest import canonical_hash, load_json, sha256_file
from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response


CSV_FIELDS = [
    "video_id", "unit_id", "start_sec", "end_sec", "expected", "execution_seal",
    "attempt_id", "completion_state", "raw_output_exists", "raw_output_hash",
    "parsed_output_exists", "parsed_output_hash", "terminal_semantic_state",
    "model_hash", "processor_hash", "prompt_hash", "generation_config_hash",
    "parser_hash", "unitization_hash", "completed_before_failstop", "retry_count",
    "conflicting_duplicate", "admissibility_status", "admissibility_reason",
]


def execution_topology_from_env() -> dict[str, Any]:
    """Current execution authority; never recover historical worker pairs."""
    if os.environ.get("V10MS_SINGLE_GPU", "0") == "1":
        return {"mode": "single_gpu", "physical_gpu_id": int(os.environ.get("V10MS_GPU_INDEX", "7"))}
    raw = os.environ.get("V10MS_TWO_GPU_IDS", "").strip()
    if not raw:
        raise RuntimeError("V10-MS requires V10MS_TWO_GPU_IDS for two-GPU execution")
    values = sorted(int(token) for token in raw.split(",") if token.strip())
    if len(values) != 2 or len(set(values)) != 2:
        raise RuntimeError("V10MS_TWO_GPU_IDS must name exactly two distinct physical GPUs")
    return {"mode": "two_gpu_balanced", "physical_gpu_ids": values}


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise RuntimeError(f"refusing to overwrite nonmatching immutable artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")


def write_text_once(path: Path, value: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != value:
            raise RuntimeError(f"refusing to overwrite nonmatching immutable artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    package = load_json(V9_SEAL)
    prereg = load_json(V9_PACKAGE / "FULL_GRID_PREREGISTRATION.json")
    units = load_json(V9_PACKAGE / "FULL_GRID_UNIT_MANIFEST.json")
    schedule = load_json(V9_PACKAGE / "FULL_GRID_WORKER_SCHEDULE.json")
    state = load_json(V9_EXECUTION / "GLOBAL_EXECUTION_STATE.json")
    decision = load_json(V9_EXECUTION / "incomplete_diagnostics/FULL_GRID_FINAL_DECISION.json")
    if decision.get("decision") != "FULL_GRID_ABORTED_RUNTIME" or state.get("status") != "STOPPED":
        raise RuntimeError("V9 must be the formally aborted runtime execution")
    seal_sha = sha256_file(V9_SEAL)
    if state.get("execution_seal_sha256") != seal_sha:
        raise RuntimeError("V9 state/seal mismatch")
    workers = {row["worker_id"]: row for row in schedule["workers"]}
    expected = {row["unit_id"]: row for row in units["units"]}
    if len(expected) != 1475:
        raise RuntimeError("unexpected frozen V3 unit universe")
    completed = set(state.get("completed_unit_ids", []))
    attempted = list(state.get("attempted_unit_ids", []))
    if len(attempted) != len(set(attempted)):
        raise RuntimeError("V9 state contains a protocol-illegal retry")
    global_events = _read_jsonl(V9_EXECUTION / "GLOBAL_EXECUTION_LEDGER.jsonl")
    stops = [row for row in global_events if row.get("event") == "GLOBAL_FAIL_STOP"]
    if len(stops) != 1:
        raise RuntimeError("V9 requires exactly one durable global fail-stop")
    stop_time = stops[0]["recorded_at_unix_ns"]

    unit_events: dict[str, list[dict[str, Any]]] = {}
    for worker in workers.values():
        for row in _read_jsonl(V9_EXECUTION / worker["attempt_ledger_relative_path"]):
            unit_id = row.get("unit_id")
            if unit_id is not None:
                unit_events.setdefault(unit_id, []).append(row)

    processed = load_json(V9_PACKAGE / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json")
    processor_hash = sha256_file(V9_PACKAGE / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json")
    prompt_binding = prereg["bindings"]["prompt"]
    model_hash = prereg["model"]["content_hash"]
    prompt_hash = prompt_binding["sha256"]
    generation_config_hash = canonical_hash(prereg["decoding"])
    parser_hash = sha256_file(ROOT / "src/garc_eval/accelerated_event_query/oracle_v3_parser.py")
    unitization_hash = sha256_file(ROOT / prereg["bindings"]["unit_grid"]["path"])
    if processor_hash != prereg["bindings"]["processed_input_manifest"]["sha256"]:
        raise RuntimeError("processor manifest binding mismatch")
    if parser_hash != prereg["bindings"]["parser"]["sha256"]:
        raise RuntimeError("parser binding mismatch")
    if unitization_hash != prereg["bindings"]["unit_grid"]["sha256"]:
        raise RuntimeError("unit grid binding mismatch")
    _ = processed  # explicit binding read; no semantic aggregation

    rows: list[dict[str, Any]] = []
    admissible_ids: list[str] = []
    raw_paths_seen: dict[Path, str] = {}
    for unit in sorted(expected.values(), key=lambda row: row["ordinal"]):
        unit_id = unit["unit_id"]
        raw_path = V9_EXECUTION / unit["raw_output_relative_path"]
        record: dict[str, Any] | None = None
        reason = ""
        status = "MISSING"
        raw_hash = ""
        parsed_hash = ""
        terminal = ""
        attempt_id = ""
        completion_state = "NOT_ATTEMPTED"
        completed_before_stop = False
        duplicate = False
        if raw_path.exists():
            raw_hash = sha256_file(raw_path)
            if raw_path in raw_paths_seen:
                duplicate = True
                status, reason = "CONFLICTING_DUPLICATE", "raw path is shared by two expected units"
            else:
                raw_paths_seen[raw_path] = unit_id
                try:
                    record = load_json(raw_path)
                    parsed = _validate_record(
                        record, unit, execution_seal_sha256=seal_sha,
                        worker=workers[unit["worker_id"]], allow_mock=False,
                    )
                    parsed_hash = canonical_hash({
                        "parse_status": record["parse_status"],
                        "authoritative_label": record["authoritative_label"],
                        "parsed": record["parsed"],
                    })
                    terminal = str(record["authoritative_label"])
                    attempt_id = str(record["attempt_id"])
                    events = unit_events.get(unit_id, [])
                    names = [event.get("event") for event in events]
                    accepted = [event for event in events if event.get("event") == "ACCEPTED"]
                    complete_event = [event for event in global_events if event.get("event") == "CALL_COMPLETED" and event.get("unit_id") == unit_id]
                    completed_before_stop = bool(
                        unit_id in completed and len(accepted) == 1 and len(complete_event) == 1
                        and accepted[0]["recorded_at_unix_ns"] < stop_time
                        and complete_event[0]["recorded_at_unix_ns"] < stop_time
                    )
                    completion_state = "ACCEPTED_TERMINAL" if completed_before_stop else "RAW_WITHOUT_COMPLETION"
                    if names != ["PREPARED", "INFERENCE_STARTED", "INFERENCE_COMPLETED", "ACCEPTED"]:
                        status, reason = "PROVENANCE_INCOMPLETE", "worker ledger transition is not the exact accepted sequence"
                    elif terminal not in {"relevant", "not_relevant", "unknown"}:
                        status, reason = "CORRUPT", "terminal semantic state outside frozen schema"
                    elif not completed_before_stop:
                        status, reason = "POST_FAILSTOP_INVALID", "not durably completed before V9 fail-stop"
                    elif record["execution_seal_sha256"] != seal_sha:
                        status, reason = "CONFIG_MISMATCH", "raw execution seal mismatch"
                    else:
                        # Re-parse above proves raw->parsed provenance without grouping labels.
                        status, reason = "ADMISSIBLE_V9", "all provenance, terminality, and frozen binding checks passed"
                        admissible_ids.append(unit_id)
                except Exception as exc:
                    status, reason = "CORRUPT", f"{type(exc).__name__}:{exc}"
        elif unit_id in attempted:
            status, reason, completion_state = "INCOMPLETE", "attempted without authenticated raw terminal output", "ATTEMPTED_INCOMPLETE"
        row = {
            "video_id": unit["video_id"], "unit_id": unit_id,
            "start_sec": unit["start_time"], "end_sec": unit["end_time"], "expected": True,
            "execution_seal": seal_sha, "attempt_id": attempt_id,
            "completion_state": completion_state, "raw_output_exists": raw_path.exists(),
            "raw_output_hash": raw_hash, "parsed_output_exists": bool(parsed_hash),
            "parsed_output_hash": parsed_hash, "terminal_semantic_state": terminal,
            "model_hash": model_hash, "processor_hash": processor_hash,
            "prompt_hash": prompt_hash, "generation_config_hash": generation_config_hash,
            "parser_hash": parser_hash, "unitization_hash": unitization_hash,
            "completed_before_failstop": completed_before_stop,
            "retry_count": attempted.count(unit_id) - 1, "conflicting_duplicate": duplicate,
            "admissibility_status": status, "admissibility_reason": reason,
        }
        rows.append(row)
    if len(rows) != len(expected):
        raise RuntimeError("admissibility audit did not cover every expected unit")
    missing_ids = [row["unit_id"] for row in rows if row["admissibility_status"] != "ADMISSIBLE_V9"]
    missing = {
        "status": "FROZEN_OUTCOME_BLIND_MISSING_SET",
        "source_execution_seal_sha256": seal_sha,
        "expected_unit_count": len(expected), "admissible_v9_unit_count": len(admissible_ids),
        "missing_unit_ids": missing_ids,
    }
    missing["missing_set_hash"] = canonical_hash(missing)
    by_video: dict[str, list[str]] = {}
    for unit in sorted(expected.values(), key=lambda row: row["ordinal"]):
        if unit["unit_id"] in admissible_ids:
            by_video.setdefault(unit["video_id"], []).append(unit["unit_id"])
    shadows = []
    for video_id, ids in sorted(by_video.items()):
        if len(ids) < 3:
            raise RuntimeError(f"insufficient admissible units for outcome-blind shadow set: {video_id}")
        for position, index in (("first", 0), ("middle", len(ids)//2), ("last", len(ids)-1)):
            shadows.append({"video_id": video_id, "position_rule": position, "unit_id": ids[index]})
    shadow = {
        "status": "FROZEN_OUTCOME_BLIND_SHADOW_COMPATIBILITY_SET",
        "selection_rule": "per video, first/middle/last admissible unit by frozen unit ordinal; no semantic field was read for selection",
        "units": shadows,
    }
    shadow["shadow_set_hash"] = canonical_hash(shadow)

    csv_path = OUT / "V9_UNIT_ADMISSIBILITY.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader(); writer.writerows(rows)
    missing["admissibility_csv_sha256"] = sha256_file(csv_path)
    write_json_once(OUT / "MISSING_UNIT_SET.json", missing)
    write_json_once(OUT / "SHADOW_COMPATIBILITY_SET.json", shadow)
    single_gpu = os.environ.get("V10MS_SINGLE_GPU", "0") == "1"
    # This is explicitly execution-only provenance.  It captures allocator
    # behavior needed to load the frozen BF16 realization on an A100; it is
    # not part of the semantic contract (model, inputs, or generation).
    execution_runtime = {
        "pytorch_cuda_alloc_conf": os.environ.get("PYTORCH_ALLOC_CONF", ""),
        "single_gpu_cpu_offload": os.environ.get("V10MS_SINGLE_GPU_CPU_OFFLOAD", "0") == "1",
        "single_gpu_gpu_memory_gib": int(os.environ.get("V10MS_SINGLE_GPU_GPU_MEMORY_GIB", "64")),
        "single_gpu_resident_text_layers": int(os.environ.get("V10MS_SINGLE_GPU_RESIDENT_TEXT_LAYERS", "44")),
    }
    protocol = {
        "PROTOCOL_TYPE": "POST-RUNTIME-FAILURE_PROSPECTIVE_EXECUTION_AMENDMENT",
        "protocol_id": "V10_MULTI_SEAL_REFERENCE_PROTOCOL",
        "reason_for_amendment": "single-seal V9 execution exhausted frozen runtime cost envelope before complete reference release",
        "execution_topology": execution_topology_from_env(),
        "execution_runtime": execution_runtime,
        "PROTOCOL_FROZEN": True,
        "DOWNSTREAM_P0_OBSERVED": False,
        "NO_P0_METRICS_OBSERVED_BEFORE_AMENDMENT": True,
        "NO_K0_K3_RESULTS_OBSERVED_BEFORE_AMENDMENT": True,
        "NO_SELECTOR_RANKINGS_OBSERVED_BEFORE_AMENDMENT": True,
        "source_commit": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "seal_a": {"kind": "V9_ADMISSIBLE_CHECKPOINTS", "execution_seal_sha256": seal_sha, "unit_ids_hash": canonical_hash(sorted(admissible_ids))},
        "seal_b": {"kind": "EXACT_FROZEN_MISSING_SET_COMPLETION", "unit_ids_hash": canonical_hash(missing_ids)},
        "semantic_contract": {
            "source_bindings_hash": prereg["bindings"]["source_bindings"]["sha256"],
            "unitization_hash": unitization_hash, "model_hash": model_hash,
            "processor_hash": processor_hash, "prompt_hash": prompt_hash,
            "generation_config_hash": generation_config_hash, "parser_hash": parser_hash,
            "k3_config_hash": prereg["bindings"]["k3_config"]["sha256"],
            "candidate_proxy_protocol_hash": "83642c42ed0ab578cdf5db81ccbf29fbcfbd3458b98909c92190fb88920dceab",
        },
        "implementation_bindings": {
            "admissibility_builder": {
                "path": "scripts/create_v10_multiseal_protocol.py",
                "sha256": sha256_file(Path(__file__)),
            },
            "multi_seal_runner": {
                "path": "scripts/run_v10_multiseal_oracle.py",
                "sha256": sha256_file(ROOT / "scripts/run_v10_multiseal_oracle.py"),
            },
            "multi_seal_finalizer": {
                "path": "scripts/finalize_v10_multiseal_reference.py",
                "sha256": sha256_file(ROOT / "scripts/finalize_v10_multiseal_reference.py"),
            },
        },
        "admissibility_rule": "expected unit + unique terminal raw record + exact V9 seal/config + exact ledger sequence + durable pre-fail-stop completion + no retry + parser revalidation",
        "cross_seal_validation_rule": "outcome-blind nine-unit shadow set; identical semantic bindings and deterministic input hashes required; raw variation is qualified only if frozen parser terminal state agrees",
        "merge_rule": "one authoritative terminal record per frozen unit: Seal A only for ADMISSIBLE_V9; Seal B/C only for frozen missing-set units; duplicate/conflict rejects release",
        "failure_rule": "a failed Seal B/C may create a later seal only for units not yet authoritative; no semantic-result-driven selection or overwrite",
        "finalizer_rule": "release only when the cross-seal union covers exactly the 1,475-unit frozen universe with identical semantic contract hashes",
        "missing_set_hash": missing["missing_set_hash"], "shadow_set_hash": shadow["shadow_set_hash"],
    }
    protocol["protocol_hash"] = canonical_hash(protocol)
    write_json_once(OUT / "MULTI_SEAL_PROTOCOL.json", protocol)
    write_text_once(OUT / "PROTOCOL_HASH.txt", protocol["protocol_hash"] + "\n")
    amendment = f"""# V10-MS Protocol Amendment\n\n`POST-RUNTIME-FAILURE_PROSPECTIVE_EXECUTION_AMENDMENT`, frozen before any V10-MS oracle call.\n\nV9 formally stopped before a complete single-seal reference release. This amendment changes only checkpoint admission, cross-seal validation, and complete-only finalization. It preserves every listed semantic binding in `MULTI_SEAL_PROTOCOL.json`.\n\nNo P0, K0-vs-K3, selector ranking, Event-F1, reference-event, or semantic-distribution result was used to make this amendment. Shadow units are selected by frozen ordinal position only.\n\nProtocol hash: `{protocol['protocol_hash']}`.\n"""
    write_text_once(OUT / "PROTOCOL_AMENDMENT.md", amendment)
    seal_a = {
        "status": "SEALED_ADMISSIBLE_V9_CHECKPOINTS", "execution_seal_sha256": seal_sha,
        "admissibility_csv_sha256": sha256_file(csv_path), "unit_count": len(admissible_ids),
        "unit_ids_hash": canonical_hash(sorted(admissible_ids)), "protocol_hash": protocol["protocol_hash"],
    }
    seal_a["manifest_hash"] = canonical_hash(seal_a)
    write_json_once(OUT / "SEAL_A_MANIFEST.json", seal_a)
    print(json.dumps({"protocol_hash": protocol["protocol_hash"], "expected": len(expected), "admissible": len(admissible_ids), "missing": len(missing_ids), "missing_set_hash": missing["missing_set_hash"], "shadow_count": len(shadows)}, sort_keys=True))


if __name__ == "__main__":
    main()
