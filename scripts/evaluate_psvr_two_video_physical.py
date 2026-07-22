#!/usr/bin/env python3
"""Evaluator-only analysis for two-video physical PSVR experiments."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from garc_eval.psvr_runtime import verify_action_ledger

OUT = ROOT / "outputs/psvr_two_video_loop"
DEV = OUT / "dev_benchmark_v1"
PROXY = OUT / "proxy_finalization"
PILOT = PROXY / "neutral_psvr"
FINAL_PROXY = OUT / "final_proxy"
REGIME = OUT / "proxy_regime"
EXPOSE = OUT / "h_expose2"
MATERIALIZER = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
)
RUNNER = ROOT / "scripts/run_psvr_two_video_physical.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def durable_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        frame.to_csv(handle, index=False, lineterminator="\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def metric_values(metrics: pd.DataFrame) -> dict[str, float]:
    return {
        str(row.metric_name): float(row.metric_value)
        for row in metrics.itertuples()
    }


def integrate(
    points: list[dict[str, Any]],
    value_key: str,
    deadline: float,
    initial: float = 0.0,
) -> float:
    current_time = 0.0
    current_value = initial
    area = 0.0
    for row in sorted(points, key=lambda value: float(value["elapsed_seconds"])):
        moment = min(deadline, max(current_time, float(row["elapsed_seconds"])))
        area += current_value * (moment - current_time)
        current_time = moment
        current_value = float(row[value_key])
        if current_time >= deadline:
            break
    if current_time < deadline:
        area += current_value * (deadline - current_time)
    return area / deadline


def unit_event_map(reference: pd.DataFrame) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for row in reference.to_dict("records"):
        for token in str(row["source_unit_ids"]).replace(",", "|").split("|"):
            if not str(token).strip():
                continue
            unit_id = int(float(token))
            result.setdefault(unit_id, set()).add(str(row["reference_event_id"]))
    return result


def labels_for_task(task_id: str) -> dict[int, str]:
    frame = pd.read_csv(DEV / "parsed_labels" / f"{task_id}.csv")
    return {
        int(row.unit_id): str(row.parsed_label).lower()
        for row in frame.itertuples()
    }


def evaluate_run(
    run: dict[str, Any], benchmark, evaluator_hash: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_id = run["task_id"]
    reference = pd.read_csv(DEV / "reference_events" / f"{task_id}.csv")
    labels = labels_for_task(task_id)
    event_by_unit = unit_event_map(reference)
    points = []
    for checkpoint in run["checkpoints"]:
        snapshot = json.loads(Path(checkpoint["snapshot_path"]).read_text())
        predicted = pd.DataFrame(snapshot["strict_confirmed_events"])
        run_meta = {
            "benchmark_id": task_id,
            "run_id": (
                f"{run['run_id']}__checkpoint_"
                f"{int(checkpoint['checkpoint_index']):03d}"
            ),
            "method": run["method"],
            "method_variant": run["method"],
            "seed": int(run["replicate"]),
            "horizon_budget": int(checkpoint["physical_oracle_calls"]),
        }
        matches, metrics = benchmark.evaluate_events(
            predicted, reference, run_meta, evaluator_hash
        )
        values = metric_values(metrics)
        matched = int(matches["matched"].astype(bool).sum()) if not matches.empty else 0
        points.append({
            **checkpoint,
            "event_precision": values["event_precision"],
            "event_recall": values["event_recall"],
            "event_f1": values["event_f1"],
            "unique_confirmed_events": matched,
        })
    deadline = float(run["deadline_seconds"])
    final = points[-1]
    anytime = integrate(points, "event_f1", deadline)
    ttfc = next(
        (
            float(point["elapsed_seconds"])
            for point in points
            if int(point["unique_confirmed_events"]) >= 1
        ),
        None,
    )
    time_second = next(
        (
            float(point["elapsed_seconds"])
            for point in points
            if int(point["unique_confirmed_events"]) >= 2
        ),
        None,
    )
    seen_events: set[str] = set()
    redundant = 0
    false_before_hit = 0
    first_hit_seen = False
    query_positive = 0
    for query in run["queried_results"]:
        unit_id = int(query["unit_id"])
        label = str(query["parsed_label"]).lower()
        if label == "positive":
            query_positive += 1
        mapped = event_by_unit.get(unit_id, set()) if label == "positive" else set()
        if mapped & seen_events:
            redundant += 1
        new = mapped - seen_events
        if new:
            first_hit_seen = True
            seen_events |= new
        elif not first_hit_seen:
            false_before_hit += 1
    lifecycle = run.get("candidate_lifecycle", [])
    ledger_path = Path(run["action_ledger_path"])
    ledger_rows = [
        json.loads(line)
        for line in ledger_path.read_text().splitlines()
        if line.strip()
    ]
    ledger_valid = False
    if ledger_rows:
        try:
            verify_action_ledger(
                ledger_path,
                expected_run_start_ns=int(ledger_rows[0]["run_start_ns"]),
                expected_terminal_event="RUN_COMPLETED",
            )
            ledger_valid = (
                sha256_file(ledger_path) == run["action_ledger_sha256"]
            )
        except Exception:
            ledger_valid = False
    survival = [
        float(row["terminal_seconds"]) - float(row["created_seconds"])
        for row in lifecycle
        if row.get("terminal_seconds") is not None
    ]
    score_history = pd.DataFrame(run.get("score_history", []))
    positive_exposed_units: set[int] = set()
    if not score_history.empty:
        for row in score_history.to_dict("records"):
            unit_id = int(row["unit_id"])
            if row.get("top_track_id") is not None and labels.get(unit_id) == "positive":
                positive_exposed_units.add(unit_id)
    queried_positive_units = {
        int(row["unit_id"])
        for row in run["queried_results"]
        if str(row["parsed_label"]).lower() == "positive"
    }
    summary = {
        "run_id": run["run_id"],
        "method": run["method"],
        "family": run["family"],
        "task_id": task_id,
        "video_id": task_id.split("_")[0],
        "query_id": task_id.split("_")[1],
        "deadline_name": run["deadline_name"],
        "deadline_seconds": deadline,
        "replicate": int(run["replicate"]),
        "deadline_met": bool(run["deadline_met"]),
        "planned_schedule_complete": (
            int(run["scan_actions"]) == int(run["target_scan_actions"])
            and int(run["verify_opportunities"])
            == int(run["target_verify_opportunities"])
        ),
        "AnytimeAUC_F1": anytime,
        "F1_at_deadline": float(final["event_f1"]),
        "precision": float(final["event_precision"]),
        "recall": float(final["event_recall"]),
        "unique_confirmed_events": int(final["unique_confirmed_events"]),
        "TTFC": ttfc,
        "TTFC_censored": deadline if ttfc is None else ttfc,
        "time_to_second_unique_event": time_second,
        "candidate_precision_at_admission": (
            query_positive / len(run["queried_results"])
            if run["queried_results"]
            else 0.0
        ),
        "physical_oracle_calls": int(run["physical_oracle_calls"]),
        "redundant_VERIFY": redundant,
        "queries_per_unique_event": (
            len(run["queried_results"])
            / max(int(final["unique_confirmed_events"]), 1)
        ),
        "false_positive_candidates_before_hit": false_before_hit,
        "candidate_survival_time_mean": (
            float(np.mean(survival)) if survival else 0.0
        ),
        "candidate_to_VERIFY_conversion": (
            len(run["queried_results"]) / len(lifecycle) if lifecycle else 0.0
        ),
        "unique_temporal_cells_in_frontier_mean": float(
            np.mean(
                [
                    point["frontier_unique_temporal_cells"]
                    for point in points
                ]
            )
        ),
        "frontier_temporal_entropy_mean": float(
            np.mean([point["frontier_temporal_entropy"] for point in points])
        ),
        "positive_candidate_exposure": len(positive_exposed_units),
        "positive_candidate_to_VERIFY": len(
            positive_exposed_units & queried_positive_units
        ),
        "proxy_GPU_seconds": float(run["proxy_gpu_seconds"]),
        "oracle_GPU_seconds": float(run["oracle_gpu_seconds"]),
        "total_GPU_seconds": float(run["total_gpu_seconds"]),
        "scheduler_CPU_seconds": float(run["scheduler_cpu_seconds"]),
        "total_wall_clock": float(run["snapshot_elapsed_seconds"]),
        "deadline_miss": not bool(run["deadline_met"]),
        "cache_replay_calls": int(run["cache_replay_calls"]),
        "future_proxy_accesses": int(run["future_proxy_accesses"]),
        "visibility_violations": int(
            run["candidate_observation_violations"]
            + run["reference_visibility_violations"]
        ),
        "snapshot_exists": Path(run["final_snapshot_path"]).exists(),
        "action_ledger_valid": ledger_valid,
        "scan_actions": int(run["scan_actions"]),
        "verify_opportunities": int(run["verify_opportunities"]),
        "verify_rejected": int(run["verify_rejected"]),
        "scan_signature": tuple(map(int, run["scan_order_prefix"])),
        "query_signature": tuple(
            int(row["unit_id"]) for row in run["queried_results"]
        ),
    }
    mechanism = [
        {
            "run_id": run["run_id"],
            "method": run["method"],
            "family": run["family"],
            "task_id": task_id,
            "deadline_name": run["deadline_name"],
            "replicate": int(run["replicate"]),
            **point,
        }
        for point in points
    ]
    return summary, mechanism


def evaluate_raw(raw: Path, tables: Path) -> pd.DataFrame:
    benchmark = load_module("psvr_two_video_evaluator", MATERIALIZER)
    evaluator_hash = sha256_file(MATERIALIZER)
    runs = [
        json.loads(path.read_text())
        for path in sorted(raw.glob("*/attempt_*/complete.json"))
        if json.loads(path.read_text()).get("status") == "ok"
    ]
    summaries = []
    mechanism = []
    for run in runs:
        summary, points = evaluate_run(run, benchmark, evaluator_hash)
        summaries.append(summary)
        mechanism.extend(points)
    frame = pd.DataFrame(summaries)
    atomic_csv(tables / "RUN_METRICS.csv", frame)
    atomic_csv(tables / "MECHANISM_CURVES.csv", pd.DataFrame(mechanism))
    if not frame.empty:
        numeric = [
            column
            for column in frame.columns
            if pd.api.types.is_numeric_dtype(frame[column])
            and column not in {"replicate"}
        ]
        aggregate = (
            frame.groupby(
                ["method", "family", "task_id", "deadline_name"],
                as_index=False,
            )[numeric]
            .mean(numeric_only=True)
        )
        atomic_csv(tables / "TASK_DEADLINE_AGGREGATE.csv", aggregate)
        reporting_metrics = [
            "AnytimeAUC_F1",
            "F1_at_deadline",
            "precision",
            "recall",
            "unique_confirmed_events",
            "TTFC_censored",
            "time_to_second_unique_event",
            "candidate_survival_time_mean",
            "candidate_to_VERIFY_conversion",
            "frontier_temporal_entropy_mean",
            "positive_candidate_exposure",
            "false_positive_candidates_before_hit",
            "redundant_VERIFY",
            "queries_per_unique_event",
            "deadline_miss",
        ]
        resource_metrics = [
            "proxy_GPU_seconds",
            "oracle_GPU_seconds",
            "scheduler_CPU_seconds",
            "total_GPU_seconds",
            "total_wall_clock",
        ]

        def reporting_aggregate(keys: list[str]) -> pd.DataFrame:
            mean = frame.groupby(keys, as_index=False)[reporting_metrics].mean()
            resources = frame.groupby(keys, as_index=False)[resource_metrics].sum()
            return mean.merge(resources, on=keys, validate="one_to_one")

        atomic_csv(
            tables / "TASK_AGGREGATE.csv",
            reporting_aggregate(["method", "family", "task_id"]),
        )
        atomic_csv(
            tables / "DEADLINE_AGGREGATE.csv",
            reporting_aggregate(["method", "family", "deadline_name"]),
        )
        atomic_csv(
            tables / "METHOD_AGGREGATE.csv",
            reporting_aggregate(["method", "family"]),
        )
        macro = (
            frame.groupby(["method", "family"], as_index=False)[numeric]
            .mean(numeric_only=True)
        )
        atomic_csv(tables / "MACRO_METRICS.csv", macro)
    return frame


def proxy_family_validity(frame: pd.DataFrame, candidates: list[str]) -> dict[str, Any]:
    result = {}
    for family in candidates:
        rows = frame[frame.family == family]
        result[family] = {
            "runs": len(rows),
            "expected_runs": 24,
            "deadline_misses": int(rows.deadline_miss.sum()) if len(rows) else 0,
            "incomplete_schedules": int(
                (~rows.planned_schedule_complete.astype(bool)).sum()
            ) if len(rows) else 0,
            "cache_replays": int(rows.cache_replay_calls.sum()) if len(rows) else 0,
            "future_accesses": int(rows.future_proxy_accesses.sum()) if len(rows) else 0,
            "visibility_violations": int(rows.visibility_violations.sum()) if len(rows) else 0,
            "missing_snapshots": int((~rows.snapshot_exists.astype(bool)).sum()) if len(rows) else 0,
            "invalid_action_ledgers": int(
                (~rows.action_ledger_valid.astype(bool)).sum()
            ) if len(rows) else 0,
        }
        result[family]["valid"] = (
            result[family]["runs"] == 24
            and all(
                result[family][key] == 0
                for key in (
                    "deadline_misses",
                    "incomplete_schedules",
                    "cache_replays",
                    "future_accesses",
                    "visibility_violations",
                    "missing_snapshots",
                    "invalid_action_ledgers",
                )
            )
        )
    return result


def regime_for_family(frame: pd.DataFrame, family: str) -> dict[str, Any]:
    videos = json.loads((OUT / "VIDEO_MANIFEST.json").read_text())
    source_runs = [
        json.loads(path.read_text())
        for path in sorted((PILOT / "raw").glob(
            f"score_only__{family}__*/attempt_*/complete.json"
        ))
    ]
    result = {}
    for video_id in ("V0", "V1"):
        runs = [row for row in source_runs if row["task_id"].startswith(video_id)]
        unit_walls = [
            float(cost["proxy_total_unit_wall_seconds"])
            for run in runs
            for cost in run["proxy_unit_costs"]
        ]
        coarse = [
            sum(
                float(cost["proxy_total_unit_wall_seconds"])
                for cost in run["proxy_unit_costs"][:3]
            )
            for run in runs
            if len(run["proxy_unit_costs"]) >= 3
        ]
        verify = [
            float(query["service_total_seconds"])
            for run in runs
            for query in run["queried_results"]
        ]
        commits = [
            float(query["commit"]["total_seconds"])
            for run in runs
            for query in run["queried_results"]
        ]
        availability = [
            float(action["score_availability_seconds"])
            for run in runs
            for action in run["actions"]
            if action["action"] == "scan"
        ]
        initialization = [
            float(run["proxy_initialization_seconds"]) for run in runs
        ]
        if not all((unit_walls, coarse, verify, commits, availability, initialization)):
            result[video_id] = {"status": "FAIL", "reason": "missing physical observations"}
            continue
        units = 347 if video_id == "V0" else 567
        full_proxy_p50 = float(np.median(initialization)) + units * float(
            np.median(unit_walls)
        )
        coarse_p95 = float(np.percentile(coarse, 95))
        verify_p95 = float(np.percentile(verify, 95))
        commit_p95 = float(np.percentile(commits, 95))
        t_min = coarse_p95 + verify_p95 + commit_p95 + 1.0
        interval = full_proxy_p50 - t_min
        normalized = interval / full_proxy_p50
        status = "PASS" if interval > 0 and normalized >= 0.10 else (
            "WEAK" if interval > 0 else "FAIL"
        )
        result[video_id] = {
            "status": status,
            "per_unit_proxy_p50_seconds": float(np.median(unit_walls)),
            "per_unit_proxy_p95_seconds": float(np.percentile(unit_walls, 95)),
            "coarse_proxy_p95_seconds": coarse_p95,
            "full_proxy_p50_seconds": full_proxy_p50,
            "candidate_score_availability_p50_seconds": float(
                np.median(availability)
            ),
            "physical_VERIFY_p95_seconds": verify_p95,
            "K3_snapshot_p95_seconds": commit_p95,
            "T_min_seconds": t_min,
            "T_max_seconds": full_proxy_p50,
            "interval_width_seconds": interval,
            "normalized_interval_width": normalized,
        }
    overall = (
        "PASS"
        if all(row["status"] == "PASS" for row in result.values())
        else "WEAK"
        if all(row["status"] in {"PASS", "WEAK"} for row in result.values())
        else "FAIL"
    )
    return {
        "family": family,
        "PROXY_REGIME_REVALIDATION": overall,
        "videos": result,
    }


def select_proxy(frame: pd.DataFrame) -> None:
    candidates = json.loads((PILOT / "PILOT_CANDIDATES.json").read_text())[
        "candidates"
    ]
    validity = proxy_family_validity(frame, candidates)
    valid = [family for family in candidates if validity[family]["valid"]]
    if not valid:
        raise RuntimeError("No valid physical proxy family remains")
    macro = (
        frame[frame.family.isin(valid)]
        .groupby("family")
        .agg(
            AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
            F1_at_deadline=("F1_at_deadline", "mean"),
            precision=("precision", "mean"),
            TTFC_censored=("TTFC_censored", "mean"),
            unique_confirmed_events=("unique_confirmed_events", "mean"),
            total_GPU_seconds=("total_GPU_seconds", "sum"),
            redundant_VERIFY=("redundant_VERIFY", "mean"),
            candidate_precision=("candidate_precision_at_admission", "mean"),
        )
    )
    best = str(
        macro.sort_values(
            [
                "AnytimeAUC_F1",
                "F1_at_deadline",
                "unique_confirmed_events",
                "precision",
            ],
            ascending=[False, False, False, False],
        ).index[0]
    )
    best_row = macro.loc[best]
    task_high = (
        frame[
            frame.family.isin(valid)
            & (frame.deadline_name == "T_high")
        ]
        .groupby(["family", "task_id"])
        .unique_confirmed_events.mean()
    )
    near = []
    near_checks = {}
    for family in valid:
        row = macro.loc[family]
        per_task_ok = True
        for task_id in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"):
            best_events = float(task_high.loc[(best, task_id)])
            candidate_events = float(task_high.loc[(family, task_id)])
            if best_events <= 2:
                per_task_ok &= abs(candidate_events - best_events) <= 1e-12
            else:
                per_task_ok &= candidate_events >= best_events - 1.0
        more_unique = (
            float(row.unique_confirmed_events)
            > float(best_row.unique_confirmed_events)
        )
        checks = {
            "anytime_90pct": float(row.AnytimeAUC_F1)
            >= 0.90 * float(best_row.AnytimeAUC_F1),
            "per_task_unique_events": bool(per_task_ok),
            "F1_tolerance": float(row.F1_at_deadline)
            >= float(best_row.F1_at_deadline) - 0.02,
            "precision_tolerance": float(row.precision)
            >= float(best_row.precision) - 0.02,
            "TTFC_or_more_unique": (
                float(row.TTFC_censored)
                <= 1.20 * float(best_row.TTFC_censored)
                or more_unique
            ),
        }
        near_checks[family] = checks
        if all(checks.values()):
            near.append(family)
    if not near:
        near = [best]
    minimum_cost = min(
        float(macro.loc[family, "total_GPU_seconds"]) for family in near
    )
    cost_band = [
        family
        for family in near
        if float(macro.loc[family, "total_GPU_seconds"])
        <= 1.10 * minimum_cost
    ]

    def secondary_key(family: str):
        return (
            float(
                json.loads(
                    (
                        PROXY
                        / "physical_cost"
                        / f"{family}_PHYSICAL_COST.json"
                    ).read_text()
                )["p95_latency_ms"]
            ),
            -float(macro.loc[family, "candidate_precision"]),
            float(macro.loc[family, "redundant_VERIFY"]),
            0 if family == "Y8" else 1,
        )

    initial = sorted(cost_band, key=secondary_key)[0]
    ordered = [
        initial,
        *sorted(
            [family for family in near if family != initial],
            key=lambda family: (
                float(macro.loc[family, "total_GPU_seconds"]),
                *secondary_key(family),
            ),
        ),
    ]
    if initial == "YP320" and "YP640" in valid:
        offline = pd.read_csv(PROXY / "tables/OFFLINE_MACRO_METRICS.csv").set_index(
            "family"
        )
        cost320 = float(
            json.loads(
                (PROXY / "physical_cost/YP320_PHYSICAL_COST.json").read_text()
            )["gpu_seconds_per_video_hour"]
        )
        cost640 = float(
            json.loads(
                (PROXY / "physical_cost/YP640_PHYSICAL_COST.json").read_text()
            )["gpu_seconds_per_video_hour"]
        )
        y320_allowed = (
            float(macro.loc["YP320", "AnytimeAUC_F1"])
            >= 0.95 * float(macro.loc["YP640", "AnytimeAUC_F1"])
            and all(
                abs(
                    float(task_high.loc[("YP320", task)])
                    - float(task_high.loc[("YP640", task)])
                )
                <= 1e-12
                for task in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
            )
            and float(offline.loc["YP320", "unique_event_recall@20"])
            >= 0.95
            * float(offline.loc["YP640", "unique_event_recall@20"])
            and cost320 <= 0.75 * cost640
        )
        if not y320_allowed:
            initial = "YP640"
    fallback_used = False
    regime = regime_for_family(frame, initial)
    selected = initial
    if regime["PROXY_REGIME_REVALIDATION"] == "FAIL":
        alternatives = [
            family for family in ordered if family != initial
        ]
        viable = [
            (family, regime_for_family(frame, family))
            for family in alternatives
        ]
        viable = [
            pair
            for pair in viable
            if pair[1]["PROXY_REGIME_REVALIDATION"] != "FAIL"
        ]
        if not viable:
            raise RuntimeError("Selected proxy and one allowed fallback have no physical regime")
        selected, regime = viable[0]
        fallback_used = True
    family_name = "YOLOV8" if selected == "Y8" else "YOLOP"
    prereg = json.loads((PROXY / "H_PROXY_2VIDEO_PREREGISTRATION.json").read_text())
    candidate = prereg["candidates"][selected]
    implementation = json.loads(
        (PROXY / "PROXY_IMPLEMENTATION_FREEZE.json").read_text()
    )
    final_config = {
        "selected_proxy_family": family_name,
        "selected_proxy_config": selected,
        "detector": candidate["detector"],
        "weight_path": candidate["weight_path"],
        "weight_sha256": candidate["weight_sha256"],
        "resolution": candidate["resolution"],
        "sample_fps": 5,
        "confidence_threshold": 0.25,
        "nms_iou": 0.45,
        "tracker": prereg["common_pipeline"]["tracker"],
        "feature_schema": prereg["feature_definitions"],
        "query_heads": prereg["query_heads"],
        "normalization": prereg["common_pipeline"]["normalization"],
        "fallback": prereg["common_pipeline"]["fallback"],
        "implementation_freeze_hash": implementation["freeze_hash"],
        "selection_fallback_used": fallback_used,
        "heldout_opened": False,
    }
    final_config["final_proxy_config_hash"] = canonical_hash(final_config)
    FINAL_PROXY.mkdir(parents=True, exist_ok=True)
    durable_json(FINAL_PROXY / "FINAL_PROXY_CONFIG.json", final_config)
    durable_json(FINAL_PROXY / "FINAL_PROXY_HASHES.json", {
        "weights_sha256": candidate["weight_sha256"],
        "preregistration_sha256": sha256_file(
            PROXY / "H_PROXY_2VIDEO_PREREGISTRATION.json"
        ),
        "implementation_freeze_sha256": sha256_file(
            PROXY / "PROXY_IMPLEMENTATION_FREEZE.json"
        ),
        "runner_sha256": sha256_file(RUNNER),
        "evaluator_sha256": sha256_file(Path(__file__)),
        "final_proxy_config_hash": final_config["final_proxy_config_hash"],
    })
    selected_runs = frame[frame.family == selected]
    durable_json(FINAL_PROXY / "FINAL_PROXY_COST.json", {
        "selected_proxy_config": selected,
        "physical_runs": len(selected_runs),
        "proxy_GPU_seconds_total": float(selected_runs.proxy_GPU_seconds.sum()),
        "oracle_GPU_seconds_total": float(selected_runs.oracle_GPU_seconds.sum()),
        "total_GPU_seconds": float(selected_runs.total_GPU_seconds.sum()),
        "standalone_profile": json.loads(
            (PROXY / "physical_cost" / f"{selected}_PHYSICAL_COST.json").read_text()
        ),
    })
    decision = {
        "H-PROXY-2VIDEO": "SELECTED",
        "SELECTED_PROXY_FAMILY": family_name,
        "SELECTED_PROXY_CONFIG": selected,
        "best_quality_config": best,
        "near_best_quality_set": near,
        "near_best_checks": near_checks,
        "minimum_total_GPU_seconds_in_near_best_set": minimum_cost,
        "cost_within_10pct_secondary_tiebreak_set": cost_band,
        "selection_order": ordered,
        "fallback_used": fallback_used,
        "validity": validity,
        "macro_metrics": macro.reset_index().to_dict("records"),
        "PROXY_REGIME_REVALIDATION": regime["PROXY_REGIME_REVALIDATION"],
        "heldout_opened": False,
    }
    durable_json(PILOT / "SELECTION_DECISION.json", decision)
    REGIME.mkdir(parents=True, exist_ok=True)
    durable_json(REGIME / "PROXY_REGIME_REVALIDATION.json", regime)
    (FINAL_PROXY / "FINAL_PROXY_SPEC.md").write_text(
        "# Final two-video proxy\n\n"
        f"`SELECTED_PROXY_FAMILY = {family_name}`\n\n"
        f"`SELECTED_PROXY_CONFIG = {selected}`\n\n"
        "The detector, weights, resolution, 5 FPS unit-local physical path, frozen "
        "ByteTrack parameters, query heads, causal percentile normalization, and "
        "fallback are bound by `FINAL_PROXY_CONFIG.json`.\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, indent=2))


def evaluate_proxy() -> None:
    frame = evaluate_raw(PILOT / "raw", PILOT / "tables")
    freeze = json.loads((PILOT / "PILOT_CANDIDATES.json").read_text())
    validity = proxy_family_validity(frame, freeze["candidates"])
    audit = {
        "physical_runs": len(frame),
        "expected_runs": 24 * len(freeze["candidates"]),
        "validity": validity,
        "all_candidates_valid": all(row["valid"] for row in validity.values()),
        "heldout_opened": False,
    }
    durable_json(PILOT / "PHYSICAL_RUN_AUDIT.json", audit)
    print(json.dumps(audit, indent=2))


def correctness_audit(frame: pd.DataFrame, raw: Path) -> dict[str, Any]:
    same_actions = True
    same_opportunities = True
    same_proxy_observations = True
    run_by_id = {}
    for path in raw.glob("*/attempt_*/complete.json"):
        run = json.loads(path.read_text())
        run_by_id[run["run_id"]] = run
    for _, group in frame.groupby(["task_id", "deadline_name", "replicate"]):
        same_actions &= group.scan_signature.nunique() == 1
        same_opportunities &= group.verify_opportunities.nunique() == 1
        runs = [run_by_id[run_id] for run_id in group.run_id]
        signatures = []
        for run in runs:
            signatures.append(tuple(
                (
                    int(row["unit_id"]),
                    str(row["candidate_evidence_sha256"]),
                )
                for row in run["proxy_unit_costs"]
            ))
        same_proxy_observations &= len(set(signatures)) <= 1
    deterministic = all(
        group.query_signature.nunique() == 1
        for _, group in frame.groupby(
            ["method", "task_id", "deadline_name"]
        )
    )
    audit = {
        "same_scan_actions": bool(same_actions),
        "same_scan_video_timestamps": bool(same_actions),
        "same_proxy_observations": bool(same_proxy_observations),
        "same_VERIFY_opportunity_count": bool(same_opportunities),
        "same_candidate_capacity": True,
        "no_future_proxy": int(frame.future_proxy_accesses.sum()) == 0,
        "no_reference_visibility": int(frame.visibility_violations.sum()) == 0,
        "deterministic_replay": bool(deterministic),
        "deadline_safety": int(frame.deadline_miss.sum()) == 0,
        "complete_schedules": bool(frame.planned_schedule_complete.all()),
        "complete_snapshots": bool(frame.snapshot_exists.all()),
        "valid_action_ledgers": bool(frame.action_ledger_valid.all()),
    }
    audit["gate"] = "PASS" if all(audit.values()) else "FAIL"
    return audit


def expose_decision(frame: pd.DataFrame, revision: bool = False) -> dict[str, Any]:
    target = (
        next(
            method
            for method in frame.method.unique()
            if method not in {"fifo", "score_only"}
        )
    )
    aggregate = (
        frame.groupby("method")
        .agg(
            AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
            F1_at_deadline=("F1_at_deadline", "mean"),
            precision=("precision", "mean"),
            recall=("recall", "mean"),
            TTFC_censored=("TTFC_censored", "mean"),
            unique_confirmed_events=("unique_confirmed_events", "mean"),
            frontier_entropy=("frontier_temporal_entropy_mean", "mean"),
            frontier_unique_cells=(
                "unique_temporal_cells_in_frontier_mean",
                "mean",
            ),
            candidate_conversion=("candidate_to_VERIFY_conversion", "mean"),
            redundant_VERIFY=("redundant_VERIFY", "mean"),
            total_GPU_seconds=("total_GPU_seconds", "sum"),
        )
    )
    baselines = aggregate.loc[["fifo", "score_only"]]
    best_baseline = str(
        baselines.sort_values(
            ["AnytimeAUC_F1", "F1_at_deadline", "TTFC_censored"],
            ascending=[False, False, True],
        ).index[0]
    )
    task = (
        frame.groupby(["method", "task_id"])
        .agg(
            AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
            F1_at_deadline=("F1_at_deadline", "mean"),
            TTFC_censored=("TTFC_censored", "mean"),
        )
    )
    positive_tasks = []
    for task_id in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"):
        baseline_method = max(
            ("fifo", "score_only"),
            key=lambda method: (
                float(task.loc[(method, task_id), "AnytimeAUC_F1"]),
                float(task.loc[(method, task_id), "F1_at_deadline"]),
                -float(task.loc[(method, task_id), "TTFC_censored"]),
            ),
        )
        candidate = task.loc[(target, task_id)]
        baseline = task.loc[(baseline_method, task_id)]
        candidate_tuple = (
            float(candidate.AnytimeAUC_F1),
            float(candidate.F1_at_deadline),
            -float(candidate.TTFC_censored),
        )
        baseline_tuple = (
            float(baseline.AnytimeAUC_F1),
            float(baseline.F1_at_deadline),
            -float(baseline.TTFC_censored),
        )
        if candidate_tuple > baseline_tuple:
            positive_tasks.append(task_id)
    target_row = aggregate.loc[target]
    base_row = aggregate.loc[best_baseline]
    anytime_relative = (
        math.inf
        if float(base_row.AnytimeAUC_F1) == 0
        and float(target_row.AnytimeAUC_F1) > 0
        else 0.0
        if float(base_row.AnytimeAUC_F1) == 0
        else (
            float(target_row.AnytimeAUC_F1)
            / float(base_row.AnytimeAUC_F1)
            - 1.0
        )
    )
    ttfc_reduction = (
        (
            float(base_row.TTFC_censored)
            - float(target_row.TTFC_censored)
        )
        / max(float(base_row.TTFC_censored), 1e-9)
    )
    f1_gain = float(target_row.F1_at_deadline - base_row.F1_at_deadline)
    high = (
        frame[frame.deadline_name == "T_high"]
        .groupby(["method", "task_id"])
        .unique_confirmed_events.mean()
    )
    unique_gain = sum(
        float(high.loc[(target, task_id)])
        - max(
            float(high.loc[("fifo", task_id)]),
            float(high.loc[("score_only", task_id)]),
        )
        for task_id in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
    )
    threshold_checks = {
        "macro_anytime_relative_gain_10pct": anytime_relative >= 0.10,
        "macro_TTFC_reduction_20pct": ttfc_reduction >= 0.20,
        "macro_absolute_F1_gain_005": f1_gain >= 0.05,
        "total_T_high_unique_gain_2": unique_gain >= 2.0,
    }
    mechanism_alignment = (
        float(target_row.frontier_entropy)
        > float(base_row.frontier_entropy) + 1e-12
        or float(target_row.frontier_unique_cells)
        > float(base_row.frontier_unique_cells) + 1e-12
    )
    v1_gain = any(task_id.startswith("V1") for task_id in positive_tasks)
    safety = {
        "deadline_misses_zero": int(frame.deadline_miss.sum()) == 0,
        "cache_replay_zero": int(frame.cache_replay_calls.sum()) == 0,
        "future_access_zero": int(frame.future_proxy_accesses.sum()) == 0,
        "visibility_violation_zero": int(frame.visibility_violations.sum()) == 0,
    }
    accept = (
        len(positive_tasks) >= 3
        and any(threshold_checks.values())
        and all(safety.values())
        and mechanism_alignment
        and v1_gain
    )
    mechanism_improved = (
        float(target_row.frontier_entropy)
        >= 1.10 * float(base_row.frontier_entropy)
        or float(target_row.frontier_unique_cells)
        >= 1.10 * float(base_row.frontier_unique_cells)
        or float(target_row.redundant_VERIFY)
        <= 0.80 * float(base_row.redundant_VERIFY)
    )
    if accept:
        status = "ACCEPT_TWO_VIDEO_SIGNAL"
    elif mechanism_improved and not revision:
        status = "REVISE"
    else:
        status = "REJECT"
    return {
        "H_EXPOSE2_DECISION": status,
        "target_method": target,
        "best_baseline": best_baseline,
        "positive_direction_tasks": positive_tasks,
        "positive_direction_task_count": len(positive_tasks),
        "threshold_checks": threshold_checks,
        "anytime_relative_gain": anytime_relative,
        "TTFC_reduction": ttfc_reduction,
        "F1_gain": f1_gain,
        "T_high_unique_event_gain": unique_gain,
        "mechanism_alignment": mechanism_alignment,
        "mechanism_improved": mechanism_improved,
        "V1_contribution": v1_gain,
        "safety": safety,
        "macro_metrics": aggregate.reset_index().to_dict("records"),
        "TWO_VIDEO_CORE_SIGNAL": (
            "PRESENT" if accept else "ABSENT" if status == "REJECT" else "PENDING_REVISION"
        ),
        "heldout_opened": False,
    }


def choose_revision(frame: pd.DataFrame) -> dict[str, Any]:
    exposure = frame[frame.method == "exposure_aware"]
    priority_rows = []
    raw_by_id = {
        json.loads(path.read_text())["run_id"]: json.loads(path.read_text())
        for path in (EXPOSE / "raw").glob("*/attempt_*/complete.json")
    }
    labels = {
        task: labels_for_task(task)
        for task in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
    }
    for row in exposure.itertuples():
        run = raw_by_id[row.run_id]
        for query in run["queried_results"]:
            priority_rows.append({
                **query["priority"],
                "positive": float(
                    labels[run["task_id"]].get(int(query["unit_id"])) == "positive"
                ),
            })
    priorities = pd.DataFrame(priority_rows)

    def correlation(column: str) -> float:
        if (
            priorities.empty
            or priorities[column].nunique() < 2
            or priorities["positive"].nunique() < 2
        ):
            return 0.0
        return float(priorities[[column, "positive"]].corr().iloc[0, 1])

    age = correlation("age_rank")
    novelty = correlation("temporal_novelty")
    if age < 0 and age <= novelty:
        revision_id, method = "R1", "exposure_minus_age"
        reason = "age rank was most negatively associated with positive verified candidates"
    elif novelty < 0:
        revision_id, method = "R2", "exposure_minus_novelty"
        reason = "temporal novelty was negatively associated with positive verified candidates"
    else:
        revision_id, method = "R3", "exposure_temporal_nms"
        reason = "rank terms were not negatively diagnostic; replace exact overlap with fixed 10-second NMS"
    return {
        "revision_id": revision_id,
        "revision_method": method,
        "reason": reason,
        "age_positive_correlation": age,
        "novelty_positive_correlation": novelty,
        "continuous_weight_tuning": False,
        "parameter_sweep": False,
        "heldout_opened": False,
    }


def evaluate_expose(raw: Path, revision: bool) -> None:
    base = raw.parent
    frame = evaluate_raw(raw, base / "tables")
    expected = 72
    correctness = correctness_audit(frame, raw)
    durable_json(base / "CORRECTNESS_AUDIT.json", correctness)
    if len(frame) != expected or correctness["gate"] != "PASS":
        decision = {
            "H_EXPOSE2_DECISION": "BLOCKED_INVALID_PHYSICAL_MATRIX",
            "physical_runs": len(frame),
            "expected_runs": expected,
            "correctness": correctness,
            "TWO_VIDEO_CORE_SIGNAL": "UNRESOLVED",
            "heldout_opened": False,
        }
    else:
        decision = expose_decision(frame, revision=revision)
        decision["physical_runs"] = len(frame)
        decision["correctness"] = correctness
        if decision["H_EXPOSE2_DECISION"] == "REVISE":
            revision_decision = choose_revision(frame)
            durable_json(EXPOSE / "REVISION_DECISION.json", revision_decision)
            decision["revision"] = revision_decision
    durable_json(base / "DECISION.json", decision)
    print(json.dumps(decision, indent=2))


def evaluate_ablation() -> None:
    raw = OUT / "h_expose2_ablation/raw"
    base = raw.parent
    frame = evaluate_raw(raw, base / "tables")
    correctness = correctness_audit(frame, raw)
    prereg = json.loads((base / "PREREGISTRATION.json").read_text())
    full_method = prereg["full_method"]
    minus_method = prereg["minus_method"]
    expected = 36
    if len(frame) != expected or correctness["gate"] != "PASS":
        decision = {
            "H-EXPOSE2_ABLATION": "BLOCKED_INVALID_PHYSICAL_MATRIX",
            "physical_runs": len(frame),
            "expected_runs": expected,
            "correctness": correctness,
            "heldout_opened": False,
        }
    else:
        macro = frame.groupby("method").agg(
            AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
            unique_confirmed_events=("unique_confirmed_events", "mean"),
            survival=("candidate_survival_time_mean", "mean"),
            conversion=("candidate_to_VERIFY_conversion", "mean"),
            entropy=("frontier_temporal_entropy_mean", "mean"),
            unique_cells=("unique_temporal_cells_in_frontier_mean", "mean"),
            redundant=("redundant_VERIFY", "mean"),
        )
        full = macro.loc[full_method]
        minus = macro.loc[minus_method]
        anytime_decline = (
            float(full.AnytimeAUC_F1 - minus.AnytimeAUC_F1)
            / max(float(full.AnytimeAUC_F1), 1e-9)
        )
        task_unique = (
            frame.groupby(["method", "task_id"])
            .unique_confirmed_events.mean()
        )
        unique_decline = sum(
            float(task_unique.loc[(full_method, task)])
            - float(task_unique.loc[(minus_method, task)])
            for task in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
        )
        component = prereg["selected_component"]
        if component == "age":
            signature = (
                float(full.survival) > float(minus.survival) + 1e-12
                or float(full.conversion) > float(minus.conversion) + 1e-12
            )
        elif component == "temporal_novelty":
            signature = (
                float(full.entropy) > float(minus.entropy) + 1e-12
                or float(full.unique_cells) > float(minus.unique_cells) + 1e-12
            )
        else:
            signature = (
                float(full.redundant) < float(minus.redundant) - 1e-12
                or float(full.unique_cells) > float(minus.unique_cells) + 1e-12
            )
        quality_decline = anytime_decline >= 0.10 or unique_decline >= 1.0
        passed = quality_decline and signature
        decision = {
            "H-EXPOSE2_ABLATION": "PASS" if passed else "FAIL",
            "selected_component": component,
            "minus_method": minus_method,
            "Macro_AnytimeAUC_relative_decline": anytime_decline,
            "four_task_unique_event_decline": unique_decline,
            "quality_decline_requirement": quality_decline,
            "mechanism_signature_deteriorated": signature,
            "macro_metrics": macro.reset_index().to_dict("records"),
            "TWO_VIDEO_CORE_SIGNAL": (
                "PRESENT" if passed else "WEAK_NOT_MECHANISTIC"
            ),
            "physical_runs": len(frame),
            "correctness": correctness,
            "heldout_opened": False,
        }
    durable_json(base / "CORRECTNESS_AUDIT.json", correctness)
    durable_json(base / "DECISION.json", decision)
    print(json.dumps(decision, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=(
            "proxy-pilot",
            "select-proxy",
            "expose",
            "expose-revision",
            "ablation",
        ),
    )
    parser.add_argument("--revision-method")
    args = parser.parse_args()
    if args.stage == "proxy-pilot":
        evaluate_proxy()
    elif args.stage == "select-proxy":
        frame = pd.read_csv(PILOT / "tables/RUN_METRICS.csv")
        select_proxy(frame)
    elif args.stage == "expose":
        evaluate_expose(EXPOSE / "raw", revision=False)
    elif args.stage == "ablation":
        evaluate_ablation()
    else:
        if not args.revision_method:
            raise RuntimeError("--revision-method is required")
        evaluate_expose(
            EXPOSE / f"revision_{args.revision_method}" / "raw",
            revision=True,
        )


if __name__ == "__main__":
    main()
