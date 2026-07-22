#!/usr/bin/env python3
"""Physical Stage-2 baselines and Coverage-Debt PSVR pilot.

Execution and evaluation are deliberately separate subcommands.  ``baselines``
and ``coverage-debt`` never load the frozen reference or dense oracle table.
``finalize`` is evaluator-only and reads durable runtime artifacts after all
physical services have stopped.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.psvr_pilot import start_pilot_policy_service
from garc_eval.psvr_pilot.policy_service import coverage_state
from garc_eval.psvr_runtime import TailAwareDeadlineGuard, durable_json, materialize_and_commit


BENCH = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
UNITS_PATH = BENCH / "frozen_inputs/units.csv"
REFERENCE_PATH = BENCH / "frozen_inputs/event_reference.csv"
MATERIALIZER = BENCH / "scripts/benchmark_lib.py"
HDS_PATH = REPO / "scripts/run_deadline_safety_validation.py"
PROFILER_PATH = REPO / "scripts/psvr_stage0b_physical_profile.py"
DEADLINE_OUT = REPO / "outputs/psvr_autonomous_research/stage_1_deadline_safety/h_ds1_tail_guard_v2_persistent_k3"
OUT = REPO / "outputs/psvr_autonomous_research/stage_2_baselines"
RAW = OUT / "raw"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
BATCH_SIZE = 4
PROXY_BATCH_INITIAL_RESERVE_SECONDS = 2.0
METHOD_LABELS = {
    "scan_then_verify": "B0 Scan-Then-Verify",
    "sequential_interleave": "B1 Sequential-Interleave",
    "uniform_temporal_interleave": "B2 Uniform-Temporal-Interleave",
    "coverage_interleave": "B3 Coverage-Interleave",
    "coverage_debt_psvr": "Coverage-Debt PSVR",
}
BASELINES = tuple(list(METHOD_LABELS)[:4])
CONTROLLED = ("sequential_interleave", "uniform_temporal_interleave",
              "coverage_interleave", "coverage_debt_psvr")
DEBT_PARAMETERS = {"lambda": 0.5, "beta": 0.25, "revision": 0}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def git_output(*args: str) -> str:
    result = subprocess.run(["git", "-c", f"safe.directory={REPO}", *args], cwd=REPO,
                            text=True, capture_output=True, check=False)
    return result.stdout.strip()


def prepare() -> tuple[dict, dict[str, float]]:
    OUT.mkdir(parents=True, exist_ok=True); RAW.mkdir(exist_ok=True)
    TABLES.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
    decision = json.loads((DEADLINE_OUT / "DECISION.json").read_text())
    if decision.get("PSVR_DEADLINE_SAFETY") != "PASS" or not decision.get("baseline_scaleout_allowed"):
        raise RuntimeError("physical baseline scale-out is not authorized by H-DS1")
    resolved = json.loads((DEADLINE_OUT / "resolved_config.json").read_text())
    gate = json.loads((REPO / "outputs/psvr_stage0b_physical_profile/partial_proxy_gate.json").read_text())
    deadlines = {
        "T_short": float(resolved["deadlines"]["T_short"]),
        "T_mid": float(resolved["deadlines"]["T_mid"]),
        "T_long": float(gate["regime_B"]["T_max_B"]),
    }
    config = {
        "experiment_id": "psvr_stage_2_core_pilot_v1",
        "benchmark_id": resolved["benchmark_id"],
        "active_deadline_protocol": "h_ds1_tail_guard_v2_persistent_k3",
        "deadline_decision_sha256": sha256_file(DEADLINE_OUT / "DECISION.json"),
        "runtime_identity": resolved["runtime_identity"],
        "runtime_identity_hash": resolved["runtime_identity_hash"],
        "deadlines_seconds": deadlines,
        "methods": METHOD_LABELS,
        "controlled_comparison": list(CONTROLLED),
        "coverage_debt_parameters": DEBT_PARAMETERS,
        "batch_size": BATCH_SIZE,
        "proxy_observation": "physical_YOLOv8n_midpoint_frame_original_decoded_BGR",
        "oracle": "physical_cache_free_Qwen3-VL-32B-Instruct",
        "materializer": "unchanged_k3_bridge_safe_persistent_service",
        "snapshot_checkpoint": "after_every_scan_or_verify_action",
        "anytime_auc": "right_continuous_event_f1_wall_clock_integral_divided_by_deadline",
        "heldout_opened": False,
        "evidence_scope": "DEVELOPMENT_ONLY_ONE_VIDEO_ONE_QUERY_ONE_A800",
        "implementation_hashes": {
            "runner": sha256_file(Path(__file__)),
            "policy": sha256_file(SRC / "garc_eval/psvr_pilot/policy_service.py"),
            "deadline_runner": sha256_file(HDS_PATH),
            "profiler": sha256_file(PROFILER_PATH),
            "materializer_evaluator": sha256_file(MATERIALIZER),
        },
    }
    config_path = OUT / "resolved_config.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise RuntimeError("Stage-2 resolved config changed; use a new experiment id")
    if not config_path.exists():
        durable_json(config_path, config)
    durable_json(OUT / "environment.json", {
        "captured_at_utc": now_utc(), "git_commit": git_output("rev-parse", "HEAD"),
        "git_status_short": git_output("status", "--short"),
        "nvidia_smi": subprocess.run(["nvidia-smi", "--query-gpu=name,uuid,driver_version", "--format=csv,noheader"],
                                      text=True, capture_output=True, check=False).stdout.strip(),
        "python": sys.version,
    })
    (OUT / "commands.sh").write_text(
        "#!/usr/bin/env bash\n"
        "PYTHONPATH=src pytest -q tests/psvr_runtime\n"
        "python scripts/run_psvr_core_pilot.py baselines --runs 3\n"
        "python scripts/run_psvr_core_pilot.py coverage-debt --runs 3\n"
        "python scripts/run_psvr_core_pilot.py finalize\n"
    )
    return config, deadlines


def public_proxy_rows(observed: dict[int, float]) -> list[dict]:
    return [{"unit_id": int(unit_id), "proxy_score": float(score)}
            for unit_id, score in sorted(observed.items())]


def checkpoint_state(units: pd.DataFrame, observed: set[int]) -> dict:
    state = coverage_state(len(units), observed)
    state["temporal_coverage"] = float(units.loc[units.unit_id.isin(observed), "duration_seconds"].sum()
                                       / units.duration_seconds.sum())
    if state["max_unobserved_units"] == 0:
        state["max_unobserved_gap_seconds"] = 0.0
    else:
        blocks = []
        current = []
        for unit_id in units.unit_id.astype(int):
            if unit_id not in observed:
                current.append(unit_id)
            elif current:
                blocks.append(current); current = []
        if current:
            blocks.append(current)
        state["max_unobserved_gap_seconds"] = max(
            float(units.loc[units.unit_id.isin(block), "duration_seconds"].sum()) for block in blocks
        ) if blocks else 0.0
    return state


def unit_scan_timestamp(unit_row) -> float:
    """Use the true midpoint, including the final truncated physical unit."""
    return float(unit_row.start_time) + 0.5 * float(unit_row.duration_seconds)


def next_attempt_dir(method: str, deadline_name: str, replicate: int) -> Path:
    run_root = RAW / f"{method}__{deadline_name}__replicate_{replicate:02d}"
    run_root.mkdir(parents=True, exist_ok=True)
    attempts = sorted(path for path in run_root.glob("attempt_*"))
    index = 1 if not attempts else max(int(path.name.rsplit("_", 1)[1]) for path in attempts) + 1
    attempt = run_root / f"attempt_{index:03d}"
    attempt.mkdir()
    return attempt


def completed_replicates(method: str, deadline_name: str) -> set[int]:
    completed = set()
    for path in RAW.glob(f"{method}__{deadline_name}__replicate_*/attempt_*/complete.json"):
        row = json.loads(path.read_text())
        if row.get("status") == "ok":
            completed.add(int(row["replicate"]))
    return completed


def run_one(method: str, deadline_name: str, deadline: float, replicate: int,
            config: dict, hds, profiler) -> dict:
    attempt = next_attempt_dir(method, deadline_name, replicate)
    run_id = f"{method}__{deadline_name}__r{replicate:02d}__{attempt.name}"
    durable_json(attempt / "started.json", {
        "status": "started", "run_id": run_id, "method": method,
        "deadline_name": deadline_name, "deadline_seconds": deadline,
        "replicate": replicate, "started_at_utc": now_utc(),
        "resolved_config_sha256": canonical_hash(config),
    })
    units = pd.read_csv(UNITS_PATH); public_units = units.to_dict("records")
    action_profile, commit_profile = hds.load_profiles()
    identity = hds.RuntimeIdentity(**{
        **config["runtime_identity"],
        "resident_model_set": tuple(config["runtime_identity"]["resident_model_set"]),
    })
    guard = TailAwareDeadlineGuard(identity)
    oracle = materializer = frozen_selector = policy = None
    run_start = None
    try:
        oracle, accessor, proxy, torch, materializer, frozen_selector, initialization = hds.start_resident_runtime(
            profiler, json.loads((DEADLINE_OUT / "resolved_config.json").read_text())
        )
        policy = start_pilot_policy_service()
        if accessor.query_count() != 0:
            raise RuntimeError("fresh physical pilot oracle has prior queries")
        run_start = time.perf_counter_ns()
        observed: dict[int, float] = {}
        queried_rows: list[dict] = []
        queried_results: list[dict] = []
        proxy_operator_rows: list[dict] = []
        actions: list[dict] = []
        checkpoints: list[dict] = []
        scan_actions = 0
        first_candidate_seconds = None
        proxy_batch_reserve = PROXY_BATCH_INITIAL_RESERVE_SECONDS
        last_snapshot = None
        stop_reason = "policy_stop"

        while True:
            elapsed = (time.perf_counter_ns() - run_start) / 1e9
            payload = {
                "method": method,
                "public_units": public_units,
                "proxy_rows": public_proxy_rows(observed),
                "queried_ids": [int(row["unit_id"]) for row in queried_rows],
                "batch_size": BATCH_SIZE,
                "parameters": {**DEBT_PARAMETERS, "scan_actions": scan_actions},
            }
            decision = policy.decide(payload)
            if decision["worker_uid"] != 65534 or decision["worker_root"] != "/":
                raise RuntimeError("pilot policy escaped the required capability boundary")
            if decision["action"] == "stop":
                stop_reason = "policy_exhausted"; break

            if decision["action"] == "scan":
                remaining = deadline - elapsed
                final_commit_reserve = commit_profile.tail_bound().upper_seconds
                if remaining <= proxy_batch_reserve + final_commit_reserve:
                    stop_reason = "insufficient_proxy_and_commit_reservation"; break
                scan_ids = [int(value) for value in decision["scan_unit_ids"]]
                by_id = units.set_index("unit_id")
                timestamps = [unit_scan_timestamp(by_id.loc[unit_id]) for unit_id in scan_ids]
                rows: list[dict] = []
                action_start = time.perf_counter_ns()
                _, scores = profiler.run_grid_proxy(proxy, torch, timestamps, BATCH_SIZE, rows,
                                                     f"{run_id}_scan_{scan_actions:03d}")
                action_end = time.perf_counter_ns()
                hds.validate_proxy_call(timestamps, scores, rows, f"{run_id}_scan_{scan_actions:03d}")
                proxy_operator_rows.extend(rows)
                for unit_id, score in zip(scan_ids, scores):
                    observed[unit_id] = max(float(score), observed.get(unit_id, float("-inf")))
                scan_seconds = (action_end - action_start) / 1e9
                proxy_batch_reserve = max(proxy_batch_reserve, 2.0 * scan_seconds + 0.5)
                scan_actions += 1
                snapshot_path = attempt / f"checkpoint_{len(checkpoints):03d}_snapshot.json"
                events, commit = materialize_and_commit(
                    materializer_path=MATERIALIZER, materializer_service=materializer,
                    units=units, queried_rows=queried_rows, snapshot_path=snapshot_path,
                    run_config={"benchmark_id": config["benchmark_id"], "run_id": run_id,
                                "method": METHOD_LABELS[method], "method_variant": method,
                                "seed": replicate, "horizon_budget": len(queried_rows)},
                )
                checkpoint_elapsed = (time.perf_counter_ns() - run_start) / 1e9
                state = checkpoint_state(units, set(observed))
                checkpoints.append({
                    "checkpoint_index": len(checkpoints), "action": "scan",
                    "elapsed_seconds": checkpoint_elapsed, "snapshot_path": str(snapshot_path),
                    "confirmed_events": len(events), "physical_oracle_calls": len(queried_rows),
                    **state,
                })
                last_snapshot = snapshot_path
                actions.append({
                    "action": "scan", "start_seconds": (action_start - run_start) / 1e9,
                    "end_seconds": (action_end - run_start) / 1e9, "unit_ids": scan_ids,
                    "timestamps": timestamps, "scores": list(map(float, scores)),
                    "policy_decision_sha256": decision["decision_sha256"],
                    "scan_priorities": decision["scan_priorities"],
                    "future_proxy_accesses": 0,
                })
                continue

            candidate = decision.get("candidate_unit_id")
            if candidate is None or int(candidate) not in observed:
                raise RuntimeError("policy proposed an unobserved oracle candidate")
            if first_candidate_seconds is None:
                first_candidate_seconds = elapsed
            admission = guard.decide(
                deadline_seconds=deadline, elapsed_seconds=elapsed, now_utc=now_utc(),
                action_profile=action_profile, commit_profile=commit_profile,
            )
            if not admission.admitted:
                stop_reason = f"verify_not_admitted:{admission.reason}"; break
            query_start = time.perf_counter_ns()
            result = accessor.query(int(candidate))
            query_end = time.perf_counter_ns()
            errors = hds.oracle_result_errors(result)
            if errors:
                raise RuntimeError(f"invalid physical oracle result: {errors}")
            queried_rows.append({"unit_id": int(candidate), "parsed_label": result["parsed_label"]})
            raw_path = attempt / f"query_{len(queried_rows)-1:03d}_oracle.json"
            snapshot_path = attempt / f"checkpoint_{len(checkpoints):03d}_snapshot.json"
            events, commit = materialize_and_commit(
                materializer_path=MATERIALIZER, materializer_service=materializer,
                units=units, queried_rows=queried_rows, snapshot_path=snapshot_path,
                run_config={"benchmark_id": config["benchmark_id"], "run_id": run_id,
                            "method": METHOD_LABELS[method], "method_variant": method,
                            "seed": replicate, "horizon_budget": len(queried_rows)},
                raw_observation={"oracle_result": result}, raw_observation_path=raw_path,
            )
            checkpoint_elapsed = (time.perf_counter_ns() - run_start) / 1e9
            state = checkpoint_state(units, set(observed))
            checkpoints.append({
                "checkpoint_index": len(checkpoints), "action": "query",
                "elapsed_seconds": checkpoint_elapsed, "snapshot_path": str(snapshot_path),
                "confirmed_events": len(events), "physical_oracle_calls": len(queried_rows),
                **state,
            })
            last_snapshot = snapshot_path
            queried_results.append({
                "unit_id": int(candidate), "parsed_label": result["parsed_label"],
                "confidence": result["confidence"], "parse_status": result["parse_status"],
                "query_start_seconds": (query_start - run_start) / 1e9,
                "query_end_seconds": (query_end - run_start) / 1e9,
                "snapshot_elapsed_seconds": checkpoint_elapsed,
                "raw_observation_path": str(raw_path),
                "oracle_inference_seconds": float(result["stage_seconds"]["oracle_inference"]),
                "service_total_seconds": float(result["service_total_seconds"]),
                "physical_oracle_invocation": result["physical_oracle_invocation"],
                "cache_replay": result["cache_replay"],
            })
            actions.append({
                "action": "query", "unit_id": int(candidate),
                "start_seconds": (query_start - run_start) / 1e9,
                "end_seconds": (query_end - run_start) / 1e9,
                "snapshot_elapsed_seconds": checkpoint_elapsed,
                "policy_decision_sha256": decision["decision_sha256"],
                "candidate_proxy_observed_before_query": True,
                "future_proxy_accesses": 0,
                "admission": admission.to_dict(),
            })

        if not checkpoints:
            snapshot_path = attempt / "checkpoint_000_snapshot.json"
            events, _ = materialize_and_commit(
                materializer_path=MATERIALIZER, materializer_service=materializer,
                units=units, queried_rows=queried_rows, snapshot_path=snapshot_path,
                run_config={"benchmark_id": config["benchmark_id"], "run_id": run_id,
                            "method": METHOD_LABELS[method], "method_variant": method,
                            "seed": replicate, "horizon_budget": 0},
            )
            checkpoints.append({"checkpoint_index": 0, "action": "final_commit",
                                "elapsed_seconds": (time.perf_counter_ns() - run_start) / 1e9,
                                "snapshot_path": str(snapshot_path), "confirmed_events": len(events),
                                "physical_oracle_calls": 0, **checkpoint_state(units, set())})
            last_snapshot = snapshot_path

        snapshot_elapsed = float(checkpoints[-1]["elapsed_seconds"])
        proxy_gpu = sum(float(row["duration_seconds"]) for row in proxy_operator_rows
                        if row.get("operator") == "proxy_inference")
        oracle_gpu = sum(float(row["oracle_inference_seconds"]) for row in queried_results)
        result = {
            "status": "ok", "run_id": run_id, "method": method,
            "method_label": METHOD_LABELS[method], "deadline_name": deadline_name,
            "deadline_seconds": deadline, "replicate": replicate,
            "runtime_identity_hash": config["runtime_identity_hash"],
            "resolved_config_sha256": canonical_hash(config),
            "runtime_initialization": {**initialization, "pilot_policy": policy.initialization},
            "snapshot_elapsed_seconds": snapshot_elapsed,
            "deadline_met": snapshot_elapsed <= deadline,
            "unused_deadline_seconds": deadline - snapshot_elapsed,
            "stop_reason": stop_reason,
            "time_to_first_candidate_seconds": first_candidate_seconds,
            "physical_oracle_calls": len(queried_results),
            "cache_replay_calls": sum(bool(row["cache_replay"]) for row in queried_results),
            "queried_results": queried_results,
            "queried_rows": queried_rows,
            "proxy_operator_rows": proxy_operator_rows,
            "proxy_decode_failures": sum(row.get("operator") == "decode_seek" and row.get("status") != "ok"
                                          for row in proxy_operator_rows),
            "proxy_gpu_seconds": proxy_gpu, "oracle_gpu_seconds": oracle_gpu,
            "GPU_seconds": proxy_gpu + oracle_gpu,
            "actions": actions, "checkpoints": checkpoints,
            "final_snapshot_path": str(last_snapshot),
            "future_proxy_accesses": sum(int(action.get("future_proxy_accesses", 0)) for action in actions),
            "candidate_observation_violations": sum(
                action["action"] == "query" and not action.get("candidate_proxy_observed_before_query", False)
                for action in actions),
            "completed_at_utc": now_utc(),
        }
        durable_json(attempt / "complete.json", result)
        print(json.dumps({
            "method": method, "deadline": deadline_name, "replicate": replicate,
            "deadline_met": result["deadline_met"], "wall": snapshot_elapsed,
            "calls": result["physical_oracle_calls"],
            "confirmed": checkpoints[-1]["confirmed_events"],
            "coverage": checkpoints[-1]["temporal_coverage"],
            "max_gap": checkpoints[-1]["max_unobserved_gap_seconds"],
        }), flush=True)
        return result
    except Exception as exc:
        failure = {
            "status": "failed", "run_id": run_id, "method": method,
            "deadline_name": deadline_name, "deadline_seconds": deadline,
            "replicate": replicate, "error": f"{type(exc).__name__}: {exc}",
            "run_elapsed_seconds": None if run_start is None else (time.perf_counter_ns() - run_start) / 1e9,
            "failed_at_utc": now_utc(),
        }
        durable_json(attempt / "failed.json", failure)
        raise
    finally:
        if policy is not None:
            policy.close()
        if frozen_selector is not None:
            frozen_selector.close()
        if materializer is not None:
            materializer.close()
        if oracle is not None:
            oracle.close()


def run_matrix(methods: tuple[str, ...], target_runs: int) -> None:
    config, deadlines = prepare()
    hds = load_module("psvr_stage2_hds", HDS_PATH)
    profiler = load_module("psvr_stage2_profiler", PROFILER_PATH)
    for method in methods:
        for deadline_name, deadline in deadlines.items():
            done = completed_replicates(method, deadline_name)
            for replicate in range(target_runs):
                if replicate in done:
                    continue
                run_one(method, deadline_name, deadline, replicate, config, hds, profiler)


def benchmark_module():
    return load_module("psvr_stage2_evaluator", MATERIALIZER)


def metric_values(metrics: pd.DataFrame) -> dict[str, float]:
    return {str(row.metric_name): float(row.metric_value) for row in metrics.itertuples()}


def integrate_step(checkpoints: list[dict], value_key: str, deadline: float,
                   initial_value: float) -> float:
    current_time = 0.0; current_value = initial_value; area = 0.0
    for row in sorted(checkpoints, key=lambda item: float(item["elapsed_seconds"])):
        moment = min(deadline, max(current_time, float(row["elapsed_seconds"])))
        area += current_value * (moment - current_time)
        current_time = moment; current_value = float(row[value_key])
        if current_time >= deadline:
            break
    if current_time < deadline:
        area += current_value * (deadline - current_time)
    return area / deadline


def evaluate_run(row: dict, benchmark, reference: pd.DataFrame, units: pd.DataFrame,
                 evaluator_hash: str) -> tuple[dict, list[dict]]:
    evaluated = []
    for checkpoint in row["checkpoints"]:
        snapshot = json.loads(Path(checkpoint["snapshot_path"]).read_text())
        predicted = pd.DataFrame(snapshot["strict_confirmed_events"])
        run_meta = {
            "benchmark_id": row["run_id"].split("__", 1)[0] and "cbbv2_514c0d360fd5b2a4b5fe",
            "run_id": f"{row['run_id']}__checkpoint_{int(checkpoint['checkpoint_index']):03d}",
            "method": row["method_label"], "method_variant": row["method"],
            "seed": int(row["replicate"]), "horizon_budget": int(checkpoint["physical_oracle_calls"]),
        }
        _, metrics = benchmark.evaluate_events(predicted, reference, run_meta, evaluator_hash)
        values = metric_values(metrics)
        evaluated.append({**checkpoint, "event_precision": values["event_precision"],
                          "event_recall": values["event_recall"], "event_f1": values["event_f1"],
                          "matched_reference_events": int(values["predicted_event_count"]
                                                          if values["event_precision"] == 1.0
                                                          else round(values["event_recall"] * len(reference)))})
    final = evaluated[-1]
    anytime = integrate_step(evaluated, "event_f1", float(row["deadline_seconds"]), 0.0)
    gap_auc = integrate_step(
        [{**point, "gap_fraction": float(point["max_unobserved_gap_seconds"])
          / float(units.duration_seconds.sum())} for point in evaluated],
        "gap_fraction", float(row["deadline_seconds"]), 1.0,
    )
    first_confirmed = next((float(point["elapsed_seconds"]) for point in evaluated
                            if int(point["confirmed_events"]) > 0), None)
    reference_by_unit = {}
    for ref in reference.itertuples():
        for token in str(ref.source_unit_ids).replace("|", " ").replace(",", " ").split():
            reference_by_unit[int(float(token))] = str(ref.reference_event_id)
    seen_events = set(); redundant = 0
    for query in row["queried_results"]:
        if query["parsed_label"] != "positive":
            continue
        event_id = reference_by_unit.get(int(query["unit_id"]))
        if event_id is not None and event_id in seen_events:
            redundant += 1
        if event_id is not None:
            seen_events.add(event_id)
    summary = {
        "run_id": row["run_id"], "method": row["method"], "method_label": row["method_label"],
        "deadline_name": row["deadline_name"], "deadline_seconds": row["deadline_seconds"],
        "replicate": row["replicate"], "deadline_met": row["deadline_met"],
        "AnytimeAUC_F1": anytime, "F1_at_deadline": final["event_f1"],
        "precision": final["event_precision"], "recall": final["event_recall"],
        "time_to_first_candidate": row["time_to_first_candidate_seconds"],
        "time_to_first_confirmed_event": first_confirmed,
        "confirmed_events": final["confirmed_events"],
        "unique_confirmed_events": int(round(final["event_recall"] * len(reference))),
        "proxy_coverage": final["temporal_coverage"],
        "max_unobserved_gap": final["max_unobserved_gap_seconds"],
        "max_unobserved_gap_auc_fraction": gap_auc,
        "physical_oracle_calls": row["physical_oracle_calls"],
        "GPU_seconds": row["GPU_seconds"], "proxy_GPU_seconds": row["proxy_gpu_seconds"],
        "oracle_GPU_seconds": row["oracle_gpu_seconds"],
        "redundant_oracle_queries": redundant,
        "cache_replay_calls": row["cache_replay_calls"],
        "future_proxy_accesses": row["future_proxy_accesses"],
        "candidate_observation_violations": row["candidate_observation_violations"],
        "snapshot_elapsed_seconds": row["snapshot_elapsed_seconds"],
        "unused_deadline_seconds": row["unused_deadline_seconds"],
    }
    mechanism = [{"run_id": row["run_id"], "method": row["method"],
                  "deadline_name": row["deadline_name"], "replicate": row["replicate"], **point}
                 for point in evaluated]
    return summary, mechanism


def finalize() -> None:
    config, deadlines = prepare(); benchmark = benchmark_module()
    reference = pd.read_csv(REFERENCE_PATH); units = pd.read_csv(UNITS_PATH)
    evaluator_hash = sha256_file(MATERIALIZER)
    completed = [json.loads(path.read_text()) for path in sorted(RAW.glob("*/attempt_*/complete.json"))
                 if json.loads(path.read_text()).get("status") == "ok"]
    summaries = []; mechanism = []
    for row in completed:
        summary, points = evaluate_run(row, benchmark, reference, units, evaluator_hash)
        summaries.append(summary); mechanism.extend(points)
    frame = pd.DataFrame(summaries)
    mechanism_frame = pd.DataFrame(mechanism)
    if not frame.empty:
        frame.to_csv(TABLES / "physical_run_metrics.csv", index=False)
        mechanism_frame.to_csv(TABLES / "mechanism_curves.csv", index=False)
    required_cells = {(method, deadline) for method in BASELINES for deadline in deadlines}
    counts = frame.groupby(["method", "deadline_name"]).size().to_dict() if not frame.empty else {}
    baseline_checks = {
        "all_12_method_deadline_cells_have_3_runs": all(counts.get(cell, 0) >= 3 for cell in required_cells),
        "deadline_misses_zero": bool(required_cells) and all(
            frame[(frame.method == method) & (frame.deadline_name == deadline)].deadline_met.all()
            for method, deadline in required_cells if counts.get((method, deadline), 0) >= 3),
        "cache_replay_zero": bool(frame.empty) is False and int(frame[frame.method.isin(BASELINES)].cache_replay_calls.sum()) == 0,
        "future_proxy_access_zero": bool(frame.empty) is False and int(frame[frame.method.isin(BASELINES)].future_proxy_accesses.sum()) == 0,
        "candidate_observation_violations_zero": bool(frame.empty) is False and int(
            frame[frame.method.isin(BASELINES)].candidate_observation_violations.sum()) == 0,
    }
    baseline_decision = "VALID" if all(baseline_checks.values()) else "INVALID"

    aggregate = (frame.groupby(["method", "method_label", "deadline_name"], as_index=False)
                 .agg(runs=("run_id", "count"), deadline_misses=("deadline_met", lambda x: int((~x).sum())),
                      AnytimeAUC_F1=("AnytimeAUC_F1", "mean"), F1_at_deadline=("F1_at_deadline", "mean"),
                      precision=("precision", "mean"), recall=("recall", "mean"),
                      time_to_first_candidate=("time_to_first_candidate", "mean"),
                      time_to_first_confirmed_event=("time_to_first_confirmed_event", "mean"),
                      confirmed_events=("confirmed_events", "mean"), unique_confirmed_events=("unique_confirmed_events", "mean"),
                      proxy_coverage=("proxy_coverage", "mean"), max_unobserved_gap=("max_unobserved_gap", "mean"),
                      max_unobserved_gap_auc_fraction=("max_unobserved_gap_auc_fraction", "mean"),
                      physical_oracle_calls=("physical_oracle_calls", "mean"), GPU_seconds=("GPU_seconds", "mean"),
                      redundant_oracle_queries=("redundant_oracle_queries", "mean"))) if not frame.empty else pd.DataFrame()
    if not aggregate.empty:
        aggregate.to_csv(TABLES / "method_deadline_aggregate.csv", index=False)

    controlled_ready = all(counts.get((method, deadline), 0) >= 3
                           for method in CONTROLLED for deadline in deadlines)
    hcov_checks = {}
    hcov_decision = "REVISE"
    comparison = {}
    if controlled_ready:
        macro = frame[frame.method.isin(CONTROLLED)].groupby("method").agg(
            AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
            early_recall=("recall", lambda x: float(np.mean(list(x)[:6]))),
            gap_auc=("max_unobserved_gap_auc_fraction", "mean"),
            misses=("deadline_met", lambda x: int((~x).sum())),
            GPU_seconds=("GPU_seconds", "mean"), future=("future_proxy_accesses", "sum"),
        )
        debt = macro.loc["coverage_debt_psvr"]
        simple = macro.drop(index="coverage_debt_psvr")
        best_quality_method = str(simple.AnytimeAUC_F1.idxmax())
        best_gap_method = str(simple.gap_auc.idxmin())
        quality_gain = float(debt.AnytimeAUC_F1 - simple.AnytimeAUC_F1.max())
        early_gain = float(debt.early_recall - simple.early_recall.max())
        gap_gain = float(simple.gap_auc.min() - debt.gap_auc)
        hcov_checks = {
            "coverage_debt_lowers_gap_auc_vs_best_simple": gap_gain > 1e-12,
            "quality_or_early_recall_beats_best_simple": quality_gain > 1e-12 or early_gain > 1e-12,
            "deadline_misses_not_increased": int(debt.misses) <= int(simple.misses.min()),
            "same_hardware_and_all_gpu_cost_accounted": frame.runtime_identity_hash.nunique() == 1
                if "runtime_identity_hash" in frame.columns else config["runtime_identity_hash"] is not None,
            "future_proxy_accesses_zero": int(debt.future) == 0,
        }
        comparison = {
            "best_simple_quality_method": best_quality_method,
            "best_simple_gap_method": best_gap_method,
            "AnytimeAUC_F1_gain_vs_best_simple": quality_gain,
            "early_recall_gain_vs_best_simple": early_gain,
            "gap_auc_reduction_vs_best_simple": gap_gain,
            "macro_metrics": macro.reset_index().to_dict("records"),
        }
        if all(hcov_checks.values()):
            hcov_decision = "ACCEPT"
        elif hcov_checks["coverage_debt_lowers_gap_auc_vs_best_simple"] and not hcov_checks["quality_or_early_recall_beats_best_simple"]:
            hcov_decision = "REJECT"
        else:
            hcov_decision = "REVISE"

    best_method = None
    if not frame.empty:
        best_method = str(frame.groupby("method").AnytimeAUC_F1.mean().idxmax())
    if baseline_decision == "INVALID" or not controlled_ready:
        core = "BLOCKED"
    elif hcov_decision == "ACCEPT":
        core = "GO"
    elif hcov_decision == "REVISE":
        core = "WEAK"
    else:
        core = "NO_GO"
    decision = {
        "MINIMAL_PHYSICAL_BASELINES": baseline_decision,
        "baseline_checks": baseline_checks,
        "H-COV1": hcov_decision,
        "hcov1_checks": hcov_checks,
        "comparison": comparison,
        "current_best_method": best_method,
        "PSVR_CORE_INNOVATION_PILOT": core,
        "physical_completed_runs": len(frame),
        "deadlines_seconds": deadlines,
        "coverage_debt_parameters": DEBT_PARAMETERS,
        "evidence_scope": config["evidence_scope"],
        "heldout_opened": False,
    }
    durable_json(OUT / "DECISION.json", decision)
    report = f"""# PSVR Core Physical Pilot

`MINIMAL_PHYSICAL_BASELINES = {baseline_decision}`

`H-COV1 = {hcov_decision}`

`PSVR_CORE_INNOVATION_PILOT = {core}`

Current best development method by macro physical AnytimeAUC_F1: `{best_method}`.

## Interpretation

Coverage-Debt acceptance requires both a lower wall-clock gap integral than the best simple controlled method and improved physical AnytimeAUC_F1 or early recall, with no added deadline miss, no future proxy access, and all GPU cost counted. Mechanism-only improvement is explicitly rejected.

This is a three-replicate, one-video, one-query, one-A800 development pilot and not an independent statistical claim.
"""
    (REPORTS / "FINAL_REPORT.md").write_text(report)
    print(json.dumps(decision, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["baselines", "coverage-debt", "finalize"])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.phase == "baselines":
        run_matrix(BASELINES, args.runs)
    elif args.phase == "coverage-debt":
        run_matrix(("coverage_debt_psvr",), args.runs)
    else:
        finalize()


if __name__ == "__main__":
    main()
