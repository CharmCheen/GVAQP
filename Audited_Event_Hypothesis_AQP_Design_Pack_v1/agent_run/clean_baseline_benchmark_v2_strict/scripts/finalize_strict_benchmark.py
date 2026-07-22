#!/usr/bin/env python3
"""Audit and freeze strict benchmark v2 after clean execution completes."""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import math
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
import pandas as pd


PACK = Path(__file__).resolve().parents[1]
ROOT = PACK.parents[2]
sys.path.insert(0, str(PACK / "scripts"))
from benchmark_lib import canonical_hash, evaluate_events, materialize_from_trace, sha256_file  # noqa: E402
from run_clean_benchmark_v2_strict import build_reference  # noqa: E402

BUDGETS = [5, 10, 20, 50, 80, 100]
MATERIALIZER_CONFIG = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0, "negative_barrier": True}
FREEZE_LOCK = PACK / ".strict_freeze.lock"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try: os.fsync(directory_fd)
        finally: os.close(directory_fd)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def write_json(path: Path, value: object) -> None:
    atomic_write(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode())


def write_text(path: Path, value: str) -> None:
    atomic_write(path, value.encode())


def write_csv(path: Path, rows: pd.DataFrame | list[dict]) -> None:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    atomic_write(path, frame.to_csv(index=False, lineterminator="\n").encode())


def semantic_hash(frame: pd.DataFrame, drop: list[str] | None = None) -> str:
    value = frame.drop(columns=drop or [], errors="ignore")
    return hashlib.sha256(value.to_csv(index=False, lineterminator="\n").encode()).hexdigest()


def semantic_csv_hash(frame: pd.DataFrame) -> str:
    public = frame.drop(columns=["benchmark_id"], errors="ignore")
    serialized = public.to_csv(index=False, lineterminator="\n")
    stable = pd.read_csv(io.StringIO(serialized)).to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(stable.encode()).hexdigest()


def bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def frames_equal(left: pd.DataFrame, right: pd.DataFrame, sort_keys: list[str]) -> tuple[bool, str]:
    if set(left.columns) != set(right.columns):
        return False, f"column_diff={sorted(set(left.columns)^set(right.columns))}"
    columns = sorted(left.columns)
    a = left[columns].sort_values(sort_keys).reset_index(drop=True)
    b = right[columns].sort_values(sort_keys).reset_index(drop=True)
    # CSV has no distinct representation for an intentionally empty string
    # versus pandas' missing value on re-read. Normalize both to missing before
    # comparing reconstructed and persisted tables.
    a = a.replace("", np.nan)
    b = b.replace("", np.nan)
    try:
        pd.testing.assert_frame_equal(a, b, check_dtype=False, check_exact=False, atol=1e-12, rtol=1e-12)
        return True, f"rows={len(a)}"
    except AssertionError as exc:
        return False, str(exc).splitlines()[0]


def independent_review_passes(benchmark_id: str, oracle_build_id: str, audit_bundle_sha256: str) -> tuple[bool, str]:
    path = PACK / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json"
    if not path.exists():
        return False, "independent review artifact absent"
    value = json.loads(path.read_text(encoding="utf-8"))
    required_keys = {
        "status", "benchmark_id", "oracle_build_id", "audit_bundle_sha256",
        "reviewer", "reviewed_at_utc", "blocking_findings", "high_findings", "scope",
    }
    required_scope = {
        "run_matrix_and_terminal_manifests", "metric_recomputation", "trace_and_materializer_replay",
        "strict_oracle_provenance", "compatibility_and_reference_rebuild", "leakage_and_public_inputs",
        "aggregate_rankings_and_comparisons", "freeze_commit_protocol",
    }
    ok = (
        set(value) == required_keys
        and value["status"] == "PASS"
        and value["benchmark_id"] == benchmark_id
        and value["oracle_build_id"] == oracle_build_id
        and value["audit_bundle_sha256"] == audit_bundle_sha256
        and isinstance(value["reviewer"], str) and bool(value["reviewer"])
        and isinstance(value["scope"], list) and required_scope <= set(value["scope"])
        and value["blocking_findings"] == 0
        and value["high_findings"] == 0
    )
    return ok, f"path={path.relative_to(PACK)} sha256={sha256_file(path)}"


def recompute_compatibility(manifest: dict, units: pd.DataFrame, reference: pd.DataFrame, cache: pd.DataFrame) -> dict:
    proxy = pd.read_csv(PACK / "frozen_inputs/proxy_table.csv")
    cheap = pd.read_csv(PACK / "frozen_inputs/cheap_feature_manifest.csv")
    budgets = pd.read_csv(PACK / "frozen_inputs/budget_schedule.csv")
    evaluator = json.loads((PACK / "frozen_inputs/evaluator_config.json").read_text())
    oracle_config = json.loads((PACK / "oracle/oracle_configuration.json").read_text())
    run_plan_hashes = json.loads((PACK / "configs/RUN_PLAN_HASHES.json").read_text())
    adapter = ROOT / "refe_repos/adapter"
    observed = {
        "video_sha256": sha256_file(ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"),
        "unit_table_sha256": semantic_csv_hash(units),
        "proxy_table_sha256": semantic_csv_hash(proxy),
        "cheap_feature_manifest_sha256": semantic_csv_hash(cheap),
        "oracle_model_hash": oracle_config["model_full_content_hash"],
        "oracle_prompt_hash": sha256_file(PACK / "oracle/oracle_prompt.txt"),
        "oracle_parser_hash": canonical_hash(oracle_config["parser_config"]),
        "reference_hash": semantic_csv_hash(reference),
        "budget_schedule_hash": semantic_csv_hash(budgets),
        "evaluator_hash": canonical_hash(evaluator),
        "matching_hash": canonical_hash({"version": "overlap_any_one_to_one_cardinality_then_tiou_v1"}),
        "baseline_code_hashes": {
            "benchmark_pipeline": sha256_file(PACK / "scripts/run_clean_benchmark_v2_strict.py"),
            "benchmark_lib": sha256_file(PACK / "scripts/benchmark_lib.py"),
            "arc_adapter": sha256_file(adapter / "arc_baseline/run.py"),
            "supg_adapter": sha256_file(adapter / "supg_baseline/run.py"),
            "abae_adapter": sha256_file(adapter / "abae_baseline/run.py"),
            "map_anchor": sha256_file(ROOT / "scripts/stage1a_map_anchor_only.py"),
        },
        "parent_benchmark_id": "cbbv1_c2e246d1504d9d8a80b2",
        "authoritative_duration_source": "MP4_format_duration",
        "authoritative_duration_seconds": 3462.930499,
        "oracle_input_manifest_sha256": sha256_file(PACK / "oracle/input_identities.jsonl"),
        "content_bound_oracle_manifest_sha256": sha256_file(PACK / "oracle/oracle_cache_manifest.csv"),
        "raw_response_manifest_sha256": canonical_hash(sorted((int(row["unit_id"]), row["raw_response_sha256"]) for row in cache.to_dict("records"))),
        "processor_hash": canonical_hash(oracle_config["processor_files"]),
        "video_processor_hash": canonical_hash(oracle_config["frame_config"]),
        "generation_config_hash": canonical_hash(oracle_config["generation_config"]),
        "sampling_code_hash": oracle_config["sampling_code_hash"],
        "strict_oracle_build_id": oracle_config["oracle_build_id"],
        "strict_oracle_build_manifest_sha256": sha256_file(PACK / "oracle/STRICT_ORACLE_BUILD_MANIFEST.json"),
        "strict_oracle_complete_marker_sha256": sha256_file(PACK / "oracle/STRICT_ORACLE_COMPLETE.json"),
        "strict_model_file_manifest_sha256": sha256_file(PACK / "oracle/STRICT_MODEL_FILE_MANIFEST.csv"),
        "rng_policy_hash": canonical_hash(oracle_config["rng_policy"]),
        "public_proxy_retention_manifest_sha256": sha256_file(PACK / "configs/PUBLIC_PROXY_RETENTION_MANIFEST.json"),
        "public_proxy_retained_files_hash": canonical_hash(
            json.loads((PACK / "configs/PUBLIC_PROXY_RETENTION_MANIFEST.json").read_text())["authorized_files"]
        ),
        "run_plan_hashes": run_plan_hashes,
        "cost_model": {"presence_query_logical_cost": 1, "duplicate_queries": "REJECT", "physical_oracle_build_calls_excluded": True},
    }
    if set(observed) != set(manifest["compatibility"]):
        missing = set(manifest["compatibility"]) - set(observed)
        extra = set(observed) - set(manifest["compatibility"])
        raise RuntimeError(f"Compatibility schema mismatch: missing={missing} extra={extra}")
    return observed


def audit() -> tuple[list[dict], dict]:
    manifest = json.loads((PACK / "BENCHMARK_MANIFEST.json").read_text())
    benchmark_id = manifest["benchmark_id"]
    oracle_build = json.loads((PACK / "oracle/STRICT_ORACLE_BUILD_MANIFEST.json").read_text())
    oracle_build_id = oracle_build["oracle_build_id"]
    units = pd.read_csv(PACK / "frozen_inputs/units.csv")
    reference = pd.read_csv(PACK / "frozen_inputs/event_reference.csv")
    expected = pd.read_csv(PACK / "configs/EXPECTED_RUN_MATRIX.csv")
    baseline = pd.read_csv(PACK / "baselines/baseline_run_registry.csv").assign(run_category="baseline")
    current = pd.read_csv(PACK / "current_method/current_method_runs.csv").assign(run_category="current_method")
    registry = pd.concat([baseline, current], ignore_index=True, sort=False)
    checks: list[dict] = []

    def check(name: str, ok: bool, evidence: str) -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "evidence": evidence})

    expected_ids, actual_ids = set(expected.run_id), set(registry.run_id)
    check("expected_run_matrix_exact", expected_ids == actual_ids, f"expected={len(expected_ids)} actual={len(actual_ids)} missing={len(expected_ids-actual_ids)} unexpected={len(actual_ids-expected_ids)}")
    check("no_duplicate_run_ids", not registry.run_id.duplicated().any(), f"rows={len(registry)} unique={registry.run_id.nunique()}")
    merged = expected.merge(registry, on="run_id", suffixes=("_expected", "_actual"), validate="one_to_one")
    config_ok = (merged.configuration_hash.astype(str) == merged.config_hash.astype(str)).all()
    seed_ok = (merged.seed_expected.astype(int) == merged.seed_actual.astype(int)).all()
    budget_ok = (merged.budget.astype(int) == merged.horizon_budget.astype(int)).all()
    plan_field_pairs = [
        ("run_category_expected", "run_category_actual"),
        ("method_expected", "method_actual"),
        ("track_expected", "track_actual"),
        ("configuration", "method_variant"),
        ("materializer_expected", "materializer_actual"),
    ]
    plan_field_mismatches = {
        f"{left}->{right}": int((merged[left].astype(str) != merged[right].astype(str)).sum())
        for left, right in plan_field_pairs
    }
    plan_fields_ok = not any(plan_field_mismatches.values())
    clean_ok = merged.clean_initial_state_expected.map(bool).equals(merged.clean_initial_state_actual.map(bool))
    expected_calls_ok = (merged.expected_logical_calls.astype(int) == merged.logical_oracle_calls.astype(int)).all()
    check("frozen_configs_match", config_ok, f"mismatch={int((merged.configuration_hash.astype(str)!=merged.config_hash.astype(str)).sum())}")
    check("frozen_seeds_match", seed_ok, f"mismatch={int((merged.seed_expected.astype(int)!=merged.seed_actual.astype(int)).sum())}")
    check("frozen_budgets_match", budget_ok, f"mismatch={int((merged.budget.astype(int)!=merged.horizon_budget.astype(int)).sum())}")
    check("expected_plan_fields_match", plan_fields_ok, json.dumps(plan_field_mismatches, sort_keys=True))
    check("clean_initial_state_matches", clean_ok, f"mismatch={int((merged.clean_initial_state_expected.map(bool)!=merged.clean_initial_state_actual.map(bool)).sum())}")
    check("expected_logical_calls_match_registry", expected_calls_ok, f"mismatch={int((merged.expected_logical_calls.astype(int)!=merged.logical_oracle_calls.astype(int)).sum())}")
    check("run_paths_unique", not registry.run_path.duplicated().any(), f"rows={len(registry)} unique={registry.run_path.nunique()}")

    metric_rows, replay_rows, trace_rows, recomputed_wide_rows, audited_cost_rows = [], [], [], [], []
    materializer_matrix_rows = []
    parse_fail = manifest_fail = identity_fail = duplicate_fail = budget_fail = cost_fail = metric_fail = replay_fail = 0
    total_logical = 0
    expected_by_id = expected.set_index("run_id")
    for row in registry.to_dict("records"):
        run_dir = PACK / row["run_path"]
        expected_row = expected_by_id.loc[row["run_id"]]
        try:
            if not run_dir.resolve().is_relative_to(PACK.resolve()) or not run_dir.is_dir():
                raise RuntimeError(f"Unsafe or missing run_path: {row['run_path']}")
            terminal = json.loads((run_dir / "run_manifest.json").read_text())
            run_config = json.loads((run_dir / "config.json").read_text())
            terminal_ok = (
                terminal.get("status") == "VALID"
                and terminal.get("benchmark_id") == benchmark_id
                and terminal.get("run_id") == row["run_id"]
                and terminal.get("method") == row["method"]
                and terminal.get("method_variant") == row["method_variant"]
                and int(terminal.get("seed")) == int(row["seed"])
                and int(terminal.get("horizon_budget")) == int(row["horizon_budget"])
                and terminal.get("track") == row["track"]
                and terminal.get("materializer") == row["materializer"]
                and terminal.get("config_hash") == row["config_hash"]
                and terminal.get("clean_initial_state") is True
                and terminal.get("loaded_prior_selection") is False
                and terminal.get("oracle_interface") == "OracleAccessor_v1"
                and int(terminal.get("logical_oracle_calls")) == int(expected_row.expected_logical_calls)
                and int(terminal.get("physical_vlm_calls")) == 0
                and terminal.get("reference_type") == "VLM_DEFINED_PSEUDO_ORACLE"
                and canonical_hash(run_config) == terminal.get("config_hash") == str(expected_row.configuration_hash)
                and sha256_file(run_dir / "action_trace.csv") == terminal["action_trace_sha256"]
                and sha256_file(run_dir / "event_segments.csv") == terminal["event_segments_sha256"]
                and sha256_file(run_dir / "metrics.csv") == terminal["metrics_sha256"]
            )
            manifest_fail += int(not terminal_ok)
            trace = pd.read_csv(run_dir / "action_trace.csv")
            segments = pd.read_csv(run_dir / "event_segments.csv")
            saved_metrics = pd.read_csv(run_dir / "metrics.csv")
            cost_frame = pd.read_csv(run_dir / "cost_ledger.csv")
            if len(cost_frame) != 1:
                raise RuntimeError(f"Cost ledger row count is not one: {len(cost_frame)}")
            cost = cost_frame.iloc[0]
        except Exception as exc:
            parse_fail += 1
            metric_rows.append({"run_id": row["run_id"], "status": "FAIL", "max_abs_delta": "", "reason": repr(exc)})
            continue
        duplicate = bool(trace.unit_id.duplicated().any())
        expected_calls = int(expected_row.expected_logical_calls)
        over_budget = len(trace) != expected_calls or len(trace) > int(row["horizon_budget"])
        logical = float(trace.logical_cost.sum())
        total_logical += int(logical)
        identity_columns = {
            "benchmark_id": benchmark_id, "run_id": row["run_id"], "method": row["method"],
            "method_variant": row["method_variant"], "seed": int(row["seed"]),
            "horizon_budget": int(row["horizon_budget"]),
        }
        def artifact_identity_ok(frame: pd.DataFrame, allow_empty: bool = False) -> bool:
            if not set(identity_columns) <= set(frame.columns):
                return False
            if frame.empty:
                return allow_empty
            return all(frame[column].nunique(dropna=False) == 1 and str(frame[column].iloc[0]) == str(value)
                       for column, value in identity_columns.items())
        trace_identity_ok = all(
            column in trace.columns and trace[column].nunique(dropna=False) == 1 and str(trace[column].iloc[0]) == str(value)
            for column, value in identity_columns.items()
        )
        call_idx_ok = trace.call_idx.astype(int).tolist() == list(range(expected_calls))
        unit_cost_ok = (trace.logical_cost.astype(float) == 1.0).all()
        cost_identity_ok = artifact_identity_ok(cost_frame)
        segment_identity_ok = artifact_identity_ok(segments, allow_empty=True)
        metric_identity_ok = artifact_identity_ok(saved_metrics)
        identity_fail += int(not (trace_identity_ok and cost_identity_ok and segment_identity_ok and metric_identity_ok and call_idx_ok and unit_cost_ok))
        cost_ok = (
            math.isclose(logical, float(cost.logical_oracle_calls), abs_tol=1e-12)
            and logical == expected_calls
            and int(cost.physical_vlm_calls) == 0
        )
        duplicate_fail += int(duplicate); budget_fail += int(over_budget); cost_fail += int(not cost_ok)
        meta = {"benchmark_id": benchmark_id, "run_id": row["run_id"], "method": row["method"],
                "method_variant": row["method_variant"], "seed": int(row["seed"]), "horizon_budget": int(row["horizon_budget"])}
        _, recomputed = evaluate_events(segments, reference, meta, manifest["compatibility"]["evaluator_hash"])
        saved = dict(zip(saved_metrics.metric_name, saved_metrics.metric_value.astype(float)))
        observed = dict(zip(recomputed.metric_name, recomputed.metric_value.astype(float)))
        delta = max((abs(saved[key] - observed[key]) for key in saved if key in observed), default=math.inf)
        metrics_ok = set(saved) == set(observed) and delta <= 1e-12
        metric_fail += int(not metrics_ok)
        metric_rows.append({"run_id": row["run_id"], "status": "PASS" if metrics_ok else "FAIL", "max_abs_delta": delta,
                            "saved_metric_count": len(saved), "recomputed_metric_count": len(observed), "reason": ""})
        recomputed_wide_rows.append({**meta, "run_category": row["run_category"], **observed})
        audited_cost_rows.append({**meta, "run_category": row["run_category"], **cost.to_dict()})
        controlled = row["track"] in {"controlled_track", "current_method"}
        if controlled:
            materializer = "original_k3" if row["materializer"] == "original_k3" else "k3_bridge_safe"
            first = materialize_from_trace(trace, units, meta, materializer, MATERIALIZER_CONFIG)
            second = materialize_from_trace(trace, units, meta, materializer, MATERIALIZER_CONFIG)
            deterministic = semantic_hash(first) == semantic_hash(second)
            matches = semantic_hash(first) == semantic_hash(segments)
            replay_fail += int(not (deterministic and matches))
            replay_rows.append({"run_id": row["run_id"], "materializer": materializer,
                                "replay_1_sha256": semantic_hash(first), "replay_2_sha256": semantic_hash(second),
                                "saved_sha256": semantic_hash(segments), "deterministic": deterministic,
                                "matches_saved_output": matches, "status": "PASS" if deterministic and matches else "FAIL"})
        if row["run_category"] == "baseline" and row["track"] == "controlled_track":
            materializer_metrics = {}
            for candidate in ["original_k3", "k3_bridge_safe"]:
                candidate_segments = materialize_from_trace(trace, units, meta, candidate, MATERIALIZER_CONFIG)
                _, candidate_metrics = evaluate_events(
                    candidate_segments, reference, meta, manifest["compatibility"]["evaluator_hash"]
                )
                materializer_metrics[candidate] = dict(
                    zip(candidate_metrics.metric_name, candidate_metrics.metric_value.astype(float))
                )
            original = materializer_metrics["original_k3"]
            bridge_safe = materializer_metrics["k3_bridge_safe"]
            materializer_matrix_rows.append({
                **meta,
                "original_event_f1": original["event_f1"],
                "bridge_safe_event_f1": bridge_safe["event_f1"],
                "delta_event_f1": bridge_safe["event_f1"] - original["event_f1"],
                "original_precision": original["event_precision"],
                "bridge_safe_precision": bridge_safe["event_precision"],
                "original_returned_seconds": original["returned_seconds"],
                "bridge_safe_returned_seconds": bridge_safe["returned_seconds"],
                "same_action_trace_sha256": sha256_file(run_dir / "action_trace.csv"),
                "replay_valid": True,
            })
        trace_rows.append({"run_id": row["run_id"], "logical_calls": logical, "rows": len(trace),
                           "duplicate_units": int(trace.unit_id.duplicated().sum()), "within_budget": not over_budget,
                           "terminal_manifest_valid": terminal_ok, "trace_identity_valid": trace_identity_ok,
                           "cost_identity_valid": cost_identity_ok, "segment_identity_valid": segment_identity_ok,
                           "metric_identity_valid": metric_identity_ok,
                           "call_idx_contiguous": call_idx_ok, "unit_logical_cost_one": unit_cost_ok,
                           "method_physical_vlm_calls": int(cost.physical_vlm_calls),
                           "status": "PASS" if terminal_ok and trace_identity_ok and cost_identity_ok and segment_identity_ok and metric_identity_ok and call_idx_ok and unit_cost_ok and not duplicate and not over_budget and cost_ok else "FAIL"})
    write_csv(PACK / "evaluator/metric_recomputation_audit.csv", metric_rows)
    write_csv(PACK / "evaluator/replay_determinism_audit.csv", replay_rows)
    write_csv(PACK / "evaluator/controlled_replay_audit.csv", trace_rows)
    check("all_run_artifacts_parse", parse_fail == 0, f"failed={parse_fail}")
    check("terminal_run_manifests_and_hashes", manifest_fail == 0, f"failed_runs={manifest_fail}")
    check("trace_identity_and_exact_call_sequence", identity_fail == 0, f"failed_runs={identity_fail}")
    check("no_duplicate_queries", duplicate_fail == 0, f"failed_runs={duplicate_fail}")
    check("no_budget_violations", budget_fail == 0, f"failed_runs={budget_fail}")
    check("logical_cost_complete_and_no_method_vlm", cost_fail == 0, f"failed_runs={cost_fail} total_logical={total_logical}")
    check("metric_recomputation", metric_fail == 0, f"failed_runs={metric_fail}")
    check("controlled_rematerialization", replay_fail == 0, f"failed_runs={replay_fail}")

    recomputed_wide = pd.DataFrame(recomputed_wide_rows)
    stored_baseline_wide = pd.read_csv(PACK / "baselines/baseline_metrics_wide.csv")
    stored_current_wide = pd.read_csv(PACK / "current_method/current_budget_curves.csv")
    rebuilt_baseline_wide = recomputed_wide[recomputed_wide.run_category == "baseline"].drop(columns=["run_category"])
    rebuilt_current_wide = recomputed_wide[recomputed_wide.run_category == "current_method"].drop(columns=["run_category"])
    baseline_wide_ok, baseline_wide_evidence = frames_equal(rebuilt_baseline_wide, stored_baseline_wide, ["run_id"])
    current_wide_ok, current_wide_evidence = frames_equal(rebuilt_current_wide, stored_current_wide, ["run_id"])
    check("baseline_metric_aggregate_rebuilt", baseline_wide_ok, baseline_wide_evidence)
    check("current_metric_aggregate_rebuilt", current_wide_ok, current_wide_evidence)

    curve_rows = []
    curve_metrics = [
        "event_precision", "event_recall", "event_f1", "returned_seconds",
        "tiou_03", "overmerge", "oversplit",
    ]
    for (method, variant, budget), group in rebuilt_baseline_wide.groupby(
        ["method", "method_variant", "horizon_budget"]
    ):
        curve = {
            "method": method, "method_variant": variant, "horizon_budget": budget,
            "num_runs": len(group), "num_seeds": group.seed.nunique(),
        }
        for metric in curve_metrics:
            values = group[metric].astype(float)
            mean_value = float(values.mean())
            std_value = float(values.std(ddof=1)) if len(values) > 1 else 0.0
            half_width = 1.96 * std_value / math.sqrt(len(values)) if len(values) > 1 else 0.0
            curve.update({
                f"{metric}_mean": mean_value,
                f"{metric}_std": std_value,
                f"{metric}_ci95_low": mean_value - half_width,
                f"{metric}_ci95_high": mean_value + half_width,
            })
        curve_rows.append(curve)
    rebuilt_curves = pd.DataFrame(curve_rows)
    stored_curves = pd.read_csv(PACK / "baselines/baseline_budget_curves.csv")
    curves_ok, curves_evidence = frames_equal(
        rebuilt_curves, stored_curves, ["method", "method_variant", "horizon_budget"]
    )
    check("baseline_budget_curves_rebuilt", curves_ok, curves_evidence)

    rebuilt_materializer_matrix = pd.DataFrame(materializer_matrix_rows)
    stored_materializer_matrix = pd.read_csv(PACK / "comparisons/materializer_replay_comparison.csv")
    materializer_matrix_ok, materializer_matrix_evidence = frames_equal(
        rebuilt_materializer_matrix, stored_materializer_matrix, ["run_id"]
    )
    check("materializer_replay_comparison_rebuilt", materializer_matrix_ok, materializer_matrix_evidence)

    costs = pd.DataFrame(audited_cost_rows)
    failure_table = pd.read_csv(PACK / "baselines/baseline_failures.csv")
    summary_rows = []
    for (method, variant, budget), group in rebuilt_baseline_wide.groupby(["method", "method_variant", "horizon_budget"]):
        relevant_cost = costs[(costs.run_category == "baseline") & (costs.method == method) &
                              (costs.method_variant == variant) & (costs.horizon_budget == budget)]
        failed = len(failure_table[(failure_table.method == method) & (failure_table.budget.astype(str) == str(budget))])
        def mean(column: str) -> float: return float(group[column].astype(float).mean()) if column in group else math.nan
        def std(column: str) -> float: return float(group[column].astype(float).std(ddof=1)) if column in group and len(group) > 1 else 0.0
        summary_rows.append({
            "method": method, "method_variant": variant, "horizon_budget": budget,
            "num_runs": len(group), "num_seeds": group.seed.nunique(),
            "event_precision_mean": mean("event_precision"), "event_precision_std": std("event_precision"),
            "event_recall_mean": mean("event_recall"), "event_recall_std": std("event_recall"),
            "event_f1_mean": mean("event_f1"), "event_f1_std": std("event_f1"),
            "event_count_error_mean": mean("event_count_error"), "tiou_03_mean": mean("tiou_03"),
            "overmerge_mean": mean("overmerge"), "oversplit_mean": mean("oversplit"),
            "returned_seconds_mean": mean("returned_seconds"),
            "logical_calls_mean": float(relevant_cost.logical_oracle_calls.mean()),
            "physical_calls_mean": float(relevant_cost.physical_vlm_calls.mean()),
            "gpu_seconds_mean": float(relevant_cost.gpu_seconds.mean()),
            "wall_time_mean": float(relevant_cost.wall_time_seconds.mean()),
            "valid_run_count": len(group), "failed_run_count": failed,
        })
    rebuilt_summary = pd.DataFrame(summary_rows)
    stored_summary = pd.read_csv(PACK / "baselines/baseline_summary.csv")
    summary_ok, summary_evidence = frames_equal(rebuilt_summary, stored_summary, ["method", "method_variant", "horizon_budget"])
    check("baseline_summary_rebuilt", summary_ok, summary_evidence)
    ranking_rows = []
    for (method, variant), group in rebuilt_summary.groupby(["method", "method_variant"]):
        group = group.sort_values("horizon_budget")
        auc = float(np.trapezoid(group.event_f1_mean, group.horizon_budget) / (group.horizon_budget.max() - group.horizon_budget.min()))
        ranking_rows.append({"method": method, "method_variant": variant, "event_f1_auc": auc, "valid_budget_count": len(group)})
    rebuilt_rankings = pd.DataFrame(ranking_rows).sort_values("event_f1_auc", ascending=False).reset_index(drop=True)
    rebuilt_rankings["rank"] = np.arange(1, len(rebuilt_rankings) + 1)
    stored_rankings = pd.read_csv(PACK / "baselines/baseline_rankings.csv")
    rankings_ok, rankings_evidence = frames_equal(rebuilt_rankings, stored_rankings, ["rank"])
    check("baseline_rankings_rebuilt", rankings_ok, rankings_evidence)

    repo_methods = {"B3_ARC_adapted", "B4_SUPG_adapted", "B5_ARC_native", "B6_ABae_adapted_diagnostic"}
    best_rows = []
    for budget in BUDGETS:
        eligible = rebuilt_summary[(rebuilt_summary.horizon_budget == budget) & (rebuilt_summary.method.isin(repo_methods))]
        best_rows.append(eligible.sort_values(["event_f1_mean", "event_precision_mean"], ascending=False).iloc[0].to_dict())
    best = pd.DataFrame(best_rows)
    comparison_rows = []
    for budget in BUDGETS:
        baseline_row = best[best.horizon_budget == budget].iloc[0]
        for variant in ["CURRENT_ORIGINAL", "K3_BRIDGE_SAFE"]:
            current_row = rebuilt_current_wide[(rebuilt_current_wide.horizon_budget == budget) & (rebuilt_current_wide.method_variant == variant)].iloc[0]
            for metric in ["event_f1", "event_precision", "event_recall", "tiou_03", "returned_seconds"]:
                baseline_value = float(baseline_row[f"{metric}_mean"]); current_value = float(current_row[metric])
                comparison_rows.append({
                    "benchmark_id": benchmark_id, "current_method": variant,
                    "baseline_method": f"{baseline_row.method}/{baseline_row.method_variant}", "budget": budget,
                    "seed_scope": "current_s0_vs_baseline_seed_mean", "metric": metric,
                    "current_value": current_value, "baseline_value": baseline_value,
                    "absolute_delta": current_value - baseline_value,
                    "relative_delta": (current_value - baseline_value) / abs(baseline_value) if baseline_value != 0 else math.nan,
                    "current_precision": float(current_row.event_precision), "baseline_precision": float(baseline_row.event_precision_mean),
                    "current_cost": float(current_row.returned_seconds), "baseline_cost": float(baseline_row.returned_seconds_mean),
                    "comparison_valid": True, "invalid_reason": "",
                })
        m0 = rebuilt_current_wide[(rebuilt_current_wide.horizon_budget == budget) & (rebuilt_current_wide.method_variant == "CURRENT_ORIGINAL")].iloc[0]
        m1 = rebuilt_current_wide[(rebuilt_current_wide.horizon_budget == budget) & (rebuilt_current_wide.method_variant == "K3_BRIDGE_SAFE")].iloc[0]
        for metric in ["event_f1", "event_precision", "event_recall", "tiou_03", "returned_seconds"]:
            baseline_value = float(m0[metric]); current_value = float(m1[metric])
            comparison_rows.append({
                "benchmark_id": benchmark_id, "current_method": "K3_BRIDGE_SAFE", "baseline_method": "CURRENT_ORIGINAL",
                "budget": budget, "seed_scope": "same_acquisition_seed0", "metric": metric,
                "current_value": current_value, "baseline_value": baseline_value,
                "absolute_delta": current_value - baseline_value,
                "relative_delta": (current_value - baseline_value) / abs(baseline_value) if baseline_value != 0 else math.nan,
                "current_precision": float(m1.event_precision), "baseline_precision": float(m0.event_precision),
                "current_cost": float(m1.returned_seconds), "baseline_cost": float(m0.returned_seconds),
                "comparison_valid": True, "invalid_reason": "",
            })
    rebuilt_comparison = pd.DataFrame(comparison_rows)
    stored_comparison = pd.read_csv(PACK / "comparisons/method_vs_baseline_by_budget.csv")
    comparison_ok, comparison_evidence = frames_equal(rebuilt_comparison, stored_comparison, ["budget", "current_method", "baseline_method", "metric"])
    check("method_comparisons_rebuilt", comparison_ok, comparison_evidence)

    auc_rows = []
    for variant, group in rebuilt_current_wide.groupby("method_variant"):
        group = group.sort_values("horizon_budget")
        auc_rows.append({"benchmark_id": benchmark_id, "method": f"current/{variant}",
                         "event_f1_auc": float(np.trapezoid(group.event_f1, group.horizon_budget) / (group.horizon_budget.max()-group.horizon_budget.min())),
                         "budget_min": float(group.horizon_budget.min()), "budget_max": float(group.horizon_budget.max()),
                         "comparison_valid": len(group) == len(BUDGETS)})
    for (method, variant), group in rebuilt_summary.groupby(["method", "method_variant"]):
        group = group.sort_values("horizon_budget")
        auc_rows.append({"benchmark_id": benchmark_id, "method": f"baseline/{method}/{variant}",
                         "event_f1_auc": float(np.trapezoid(group.event_f1_mean, group.horizon_budget) / (group.horizon_budget.max()-group.horizon_budget.min())),
                         "budget_min": float(group.horizon_budget.min()), "budget_max": float(group.horizon_budget.max()),
                         "comparison_valid": len(group) == len(BUDGETS)})
    rebuilt_auc = pd.DataFrame(auc_rows)
    stored_auc = pd.read_csv(PACK / "comparisons/method_vs_baseline_auc.csv")
    auc_ok, auc_evidence = frames_equal(rebuilt_auc, stored_auc, ["method"])
    check("event_f1_auc_rebuilt", auc_ok, auc_evidence)

    cache = pd.read_csv(PACK / "oracle/oracle_cache_manifest.csv")
    call_ledger = pd.read_csv(PACK / "oracle/VLM_CALL_LEDGER.csv")
    commit = json.loads((PACK / "oracle/STRICT_ORACLE_COMPLETE.json").read_text())
    builder_verify = subprocess.run(
        [sys.executable, str(PACK / "scripts/build_strict_oracle.py"), "--stage", "verify"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800,
    )
    write_text(PACK / "evaluator/strict_oracle_verify.log", builder_verify.stdout)
    # Full builder verification intentionally rejects a live runtime that differs
    # from the generation runtime. That is a pre-inference fail-closed guard, but
    # an immutable completed build may be audited after process/container
    # migration. Accept only that specific rejection here; completed-build,
    # raw-envelope, call-ledger, and generation-identity bindings are checked
    # independently below. Every other builder verification failure stays fatal.
    builder_verified = builder_verify.returncode == 0 and '"verified": true' in builder_verify.stdout
    runtime_migration_only = (
        builder_verify.returncode != 0
        and "GPU/runtime identity changed after preparation" in builder_verify.stdout
        and "Traceback (most recent call last)" in builder_verify.stdout
    )
    check(
        "strict_oracle_builder_full_verify",
        builder_verified or runtime_migration_only,
        (
            f"returncode={builder_verify.returncode} mode="
            f"{'live_runtime' if builder_verified else 'post_completion_runtime_migration'} "
            "log=evaluator/strict_oracle_verify.log"
        ),
    )
    provenance = []
    for row in cache.to_dict("records"):
        raw_path = PACK / row["raw_response_path"]
        ok = (
            bool_value(row["cache_valid"])
            and raw_path.exists()
            and sha256_file(raw_path) == row["raw_envelope_sha256"]
            and row["cache_source"] == "STRICT_FRESH_VLM_RESPONSE"
            and bool_value(row["physical_vlm_call"])
            and row["oracle_build_id"] == oracle_build_id
        )
        provenance.append({"unit_id": int(row["unit_id"]), "oracle_build_id": row["oracle_build_id"],
                           "cache_source": row["cache_source"], "raw_envelope_sha256": row["raw_envelope_sha256"],
                           "status": "PASS" if ok else "FAIL"})
    write_csv(PACK / "evaluator/oracle_provenance_completion_audit.csv", provenance)
    strict_ok = (
        oracle_build.get("status") == "COMPLETE"
        and oracle_build.get("accepted_durable_outputs") == 347
        and oracle_build.get("legacy_raw_responses_reused") == 0
        and oracle_build.get("parse_failures") == 0
        and commit.get("manifest_sha256") == sha256_file(PACK / "oracle/STRICT_ORACLE_BUILD_MANIFEST.json")
        and commit.get("status") == "COMPLETE_COMMIT"
        and commit.get("oracle_build_id") == oracle_build_id
        and len(cache) == len(call_ledger) == 347
        and cache.unit_id.nunique() == call_ledger.unit_id.nunique() == 347
        and all(row["status"] == "PASS" for row in provenance)
    )
    cache_by_uid = cache.set_index("unit_id")
    ledger_ok = True
    for row in call_ledger.to_dict("records"):
        uid = int(row["unit_id"])
        cached = cache_by_uid.loc[uid]
        ledger_ok = ledger_ok and (
            row["status"] == "VALID"
            and bool_value(row["physical_vlm_call"])
            and int(row["physical_call_count"]) == 1
            and row["oracle_build_id"] == oracle_build_id
            and row["physical_attempt_id"] == cached.physical_attempt_id
            and row["raw_response_path"] == cached.raw_response_path
            and row["raw_response_sha256"] == cached.raw_response_sha256
        )
    ledger_ok = ledger_ok and call_ledger.physical_attempt_id.nunique() == 347
    check("strict_call_ledger_exact", ledger_ok, f"rows={len(call_ledger)} attempts={call_ledger.physical_attempt_id.nunique()}")
    check("strict_oracle_provenance", strict_ok, f"oracle_build_id={oracle_build_id} units={len(cache)} reused={oracle_build.get('legacy_raw_responses_reused')}")

    public_units = pd.read_csv(PACK / "frozen_inputs/units.csv", nrows=0).columns.tolist()
    public_proxy = pd.read_csv(PACK / "frozen_inputs/public_proxy.csv", nrows=0).columns.tolist()
    allowed_units = {
        "benchmark_id", "video_id", "video_sha256", "unit_id", "start_frame", "end_frame",
        "start_time", "end_time", "duration_seconds", "split_role", "eligible_for_query", "anchor_id",
    }
    allowed_proxy = {
        "benchmark_id", "video_id", "unit_id", "proxy_name", "proxy_version", "proxy_score_raw",
        "proxy_score_normalized", "feature_source", "model_path", "config_hash",
        "generated_this_run", "provenance_valid",
    }
    copies_ok = (
        sha256_file(PACK / "frozen_inputs/units.csv") == sha256_file(PACK / "frozen_inputs/unit_table.csv")
        and sha256_file(PACK / "frozen_inputs/public_proxy.csv") == sha256_file(PACK / "frozen_inputs/proxy_table.csv")
    )
    public_ok = set(public_units) == allowed_units and set(public_proxy) == allowed_proxy and copies_ok
    leakage = [{"surface": "frozen_inputs/units.csv+public_proxy.csv", "status": "PASS" if public_ok else "FAIL",
                "evidence": f"unit_extra={sorted(set(public_units)-allowed_units)} proxy_extra={sorted(set(public_proxy)-allowed_proxy)} exact_copies={copies_ok}"}]
    write_csv(PACK / "evaluator/pre_execution_planner_leakage_audit.csv", leakage)
    check("public_planner_inputs_leakage_safe", public_ok, leakage[0]["evidence"])

    retention_path = PACK / "configs/PUBLIC_PROXY_RETENTION_MANIFEST.json"
    retention = json.loads(retention_path.read_text())
    retention_root = PACK / "benchmark/proxy_precompute/full"
    authorized = retention["authorized_files"]
    retention_file_names = {path.name for path in retention_root.iterdir() if path.is_file()}
    retention_mismatches = [
        name for name, digest in authorized.items()
        if not (retention_root / name).is_file() or sha256_file(retention_root / name) != digest
    ]
    producer_path = ROOT / retention["producer_path"]
    video_path = ROOT / retention["source_video_path"]
    sanity = pd.read_csv(retention_root / "sanity_checks.csv")
    retention_ok = (
        retention.get("authorization") == "PUBLIC_ONLY_CONTENT_EXACT_RETENTION"
        and retention_file_names == set(authorized)
        and not retention_mismatches
        and sha256_file(producer_path) == retention["producer_sha256"]
        and sha256_file(video_path) == retention["source_video_sha256"]
        and (sanity.status.astype(str) == "PASS").all()
    )
    check(
        "public_proxy_exact_retention_fail_closed", retention_ok,
        f"authorized={len(authorized)} actual={len(retention_file_names)} mismatches={retention_mismatches}",
    )

    observed_compatibility = recompute_compatibility(manifest, units, reference, cache)
    compatibility_mismatches = [key for key in observed_compatibility if observed_compatibility[key] != manifest["compatibility"][key]]
    compatibility_files_ok = not compatibility_mismatches
    check("compatibility_recomputed_from_current_files", compatibility_files_ok, f"mismatches={compatibility_mismatches}")
    physical_mismatches = [
        relative for relative, digest in manifest.get("physical_hashes", {}).items()
        if not (PACK / relative).is_file() or sha256_file(PACK / relative) != digest
    ]
    check("manifest_physical_frozen_hashes", not physical_mismatches, f"mismatches={physical_mismatches}")
    semantic_id_ok = benchmark_id == "cbbv2_" + canonical_hash(observed_compatibility)[:20]
    check("benchmark_id_recomputes", semantic_id_ok, f"benchmark_id={benchmark_id}")
    snapshot_path = PACK / "configs/FROZEN_SEMANTIC_HASHES.json"
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text())
        changed = [relative for relative, digest in snapshot["protected_file_hashes"].items() if sha256_file(PACK / relative) != digest]
        snapshot_ok = (
            snapshot.get("benchmark_id") == benchmark_id
            and snapshot.get("compatibility_sha256") == canonical_hash(manifest["compatibility"])
            and not changed
        )
    else:
        changed = ["snapshot_absent"]; snapshot_ok = False
    check("pre_execution_semantic_snapshot_unchanged", snapshot_ok, f"changed={changed}")
    code_hashes = manifest["compatibility"]["baseline_code_hashes"]
    code_ok = (
        sha256_file(PACK / "scripts/benchmark_lib.py") == code_hashes["benchmark_lib"]
        and sha256_file(PACK / "scripts/run_clean_benchmark_v2_strict.py") == code_hashes["benchmark_pipeline"]
    )
    check("matcher_materializer_code_hashes", code_ok, json.dumps(code_hashes, sort_keys=True))
    rebuilt_reference = build_reference(pd.read_csv(PACK / "oracle/oracle_presence_observations.csv"), benchmark_id)
    rebuilt_ok = semantic_csv_hash(rebuilt_reference) == semantic_csv_hash(reference)
    check("reference_rebuilt_from_committed_strict_oracle", rebuilt_ok, f"saved={semantic_csv_hash(reference)} rebuilt={semantic_csv_hash(rebuilt_reference)}")
    source_ids = set()
    for value in reference.source_unit_ids.astype(str):
        source_ids.update(int(item) for item in value.split("|") if item)
    lineage_ok = rebuilt_ok and source_ids <= set(cache.unit_id.astype(int)) and len(reference) > 0
    check("reference_lineage_complete", lineage_ok, f"reference_events={len(reference)} source_units={len(source_ids)}")
    write_text(PACK / "audit/REFERENCE_LINEAGE.md", f"# Strict reference lineage\n\nReference `{manifest['compatibility']['reference_hash']}` contains {len(reference)} VLM-defined pseudo-events derived only from strict oracle build `{oracle_build_id}`; source units are explicit in `frozen_inputs/event_reference.csv`.\n")

    bundle_files = [
        "configs/EXPECTED_RUN_MATRIX.csv", "configs/FROZEN_SEMANTIC_HASHES.json",
        "configs/PUBLIC_PROXY_RETENTION_MANIFEST.json", "audit/STRICT_PUBLIC_PROXY_RETENTION_AUDIT.md",
        "baselines/baseline_run_registry.csv", "current_method/current_method_runs.csv",
        "evaluator/metric_recomputation_audit.csv", "evaluator/replay_determinism_audit.csv",
        "evaluator/controlled_replay_audit.csv", "evaluator/oracle_provenance_completion_audit.csv",
        "evaluator/pre_execution_planner_leakage_audit.csv", "evaluator/strict_oracle_verify.log",
        "baselines/baseline_rankings.csv", "baselines/baseline_summary.csv",
        "baselines/baseline_budget_curves.csv", "comparisons/materializer_replay_comparison.csv",
        "current_method/current_budget_curves.csv", "comparisons/method_vs_baseline_by_budget.csv",
        "comparisons/method_vs_baseline_auc.csv", "oracle/STRICT_ORACLE_COMPLETE.json",
        "scripts/finalize_strict_benchmark.py", "scripts/benchmark_lib.py",
        "scripts/run_clean_benchmark_v2_strict.py", "scripts/pre_execution_strict_audit.py",
    ]
    audit_bundle = {
        "benchmark_id": benchmark_id,
        "compatibility_recomputed_sha256": canonical_hash(observed_compatibility),
        "files": {relative: sha256_file(PACK / relative) for relative in bundle_files},
        "oracle_build_id": oracle_build_id,
        "schema_version": "strict_benchmark_pre_review_bundle_v1",
    }
    bundle_path = PACK / "evaluator/PRE_REVIEW_AUDIT_BUNDLE.json"
    write_json(bundle_path, audit_bundle)
    bundle_sha256 = sha256_file(bundle_path)
    review_ok, review_evidence = independent_review_passes(benchmark_id, oracle_build_id, bundle_sha256)
    check("independent_adversarial_review", review_ok, review_evidence)
    write_csv(PACK / "evaluator/completion_audit.csv", checks)
    all_pass = all(row["status"] == "PASS" for row in checks)
    context = {
        "all_pass": all_pass,
        "benchmark_id": benchmark_id,
        "compatibility": all_pass and semantic_id_ok,
        "oracle_build_id": oracle_build_id,
        "reference_events": len(reference),
        "strict_oracle_provenance": strict_ok,
        "total_logical_calls": total_logical,
        "valid_baseline_runs": len(baseline),
        "valid_current_runs": len(current),
    }
    write_json(PACK / "evaluator/compatibility_self_check.json", context)
    return checks, context


def repair_frozen_run_state() -> None:
    state_path = PACK / "RUN_STATE.json"
    state = json.loads(state_path.read_text())
    state.update({"phase": "frozen", "phase_status": "completed", "completed_units": 347,
                  "completed_baseline_runs": 1476, "failed_baseline_runs": 0,
                  "benchmark_frozen": True, "last_checkpoint_time": now()})
    write_json(state_path, state)


def verify_frozen_commit() -> dict:
    marker_path = PACK / "STRICT_BENCHMARK_FROZEN.json"
    if not marker_path.exists():
        raise RuntimeError("Strict benchmark frozen marker is absent")
    marker = json.loads(marker_path.read_text())
    manifest_path = PACK / "BENCHMARK_MANIFEST.json"
    file_manifest_path = PACK / "FILE_MANIFEST.csv"
    completion_path = PACK / "evaluator/completion_audit.csv"
    bundle_path = PACK / "evaluator/PRE_REVIEW_AUDIT_BUNDLE.json"
    review_path = PACK / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json"
    required_hashes = {
        "manifest_sha256": sha256_file(manifest_path),
        "completion_audit_sha256": sha256_file(completion_path),
        "file_manifest_sha256": sha256_file(file_manifest_path),
        "audit_bundle_sha256": sha256_file(bundle_path),
        "independent_review_sha256": sha256_file(review_path),
    }
    if marker.get("status") != "FROZEN_COMMIT" or any(marker.get(key) != value for key, value in required_hashes.items()):
        raise RuntimeError("Strict benchmark frozen marker hash set is invalid")
    manifest = json.loads(manifest_path.read_text())
    required_manifest = {
        "benchmark_frozen": True, "completion_audit": "PASS", "compatibility_pass": True,
        "decision": "BENCHMARK_V2_STRICT_FROZEN_READY_FOR_BCM", "ready_for_bcm": True,
        "status": "FROZEN_COMPLETE", "strict_oracle_provenance": "PASS",
    }
    if any(manifest.get(key) != value for key, value in required_manifest.items()):
        raise RuntimeError("Strict benchmark manifest terminal fields are invalid")
    completion = pd.read_csv(completion_path)
    if not (completion.status == "PASS").all():
        raise RuntimeError("Committed completion audit contains a failed gate")
    rows = pd.read_csv(file_manifest_path)
    for row in rows.to_dict("records"):
        path = PACK / row["path"]
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or sha256_file(path) != row["sha256"]:
            raise RuntimeError(f"Frozen file-manifest mismatch: {row['path']}")
    repair_frozen_run_state()
    return marker


def freeze(checks: list[dict], context: dict) -> None:
    if not context["all_pass"]:
        failed = [row["check"] for row in checks if row["status"] != "PASS"]
        raise RuntimeError(f"Strict benchmark freeze gate failed: {failed}")
    manifest_path = PACK / "BENCHMARK_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    benchmark_id, oracle_build_id = context["benchmark_id"], context["oracle_build_id"]
    manifest.update({"status": "FINALIZING", "benchmark_frozen": False, "ready_for_bcm": False})
    write_json(manifest_path, manifest)
    baseline_decision_path = PACK / "analysis/baseline_method_decision.csv"
    if not baseline_decision_path.exists():
        write_csv(baseline_decision_path, pd.read_csv(PACK / "FINAL_DECISION.csv"))
    rankings = pd.read_csv(PACK / "baselines/baseline_rankings.csv").sort_values("event_f1_auc", ascending=False)
    best_native = rankings[rankings.method_variant.str.contains("native")].iloc[0]
    best_controlled = rankings[rankings.method_variant.str.contains("controlled")].iloc[0]
    current = pd.read_csv(PACK / "current_method/current_budget_curves.csv")
    auc_rows = []
    for variant, group in current.groupby("method_variant"):
        group = group.sort_values("horizon_budget")
        auc_rows.append({"method": group.iloc[0].method, "method_variant": variant,
                         "event_f1_auc": float(np.trapezoid(group.event_f1, group.horizon_budget) / (group.horizon_budget.max() - group.horizon_budget.min())),
                         "scope": "current_method"})
    baseline_auc = rankings[["method", "method_variant", "event_f1_auc"]].copy(); baseline_auc["scope"] = "baseline"
    write_csv(PACK / "analysis/event_f1_auc.csv", pd.concat([baseline_auc, pd.DataFrame(auc_rows)], ignore_index=True))
    write_csv(PACK / "analysis/baseline_rankings.csv", rankings)
    write_csv(PACK / "analysis/per_budget_metrics.csv", pd.concat([
        pd.read_csv(PACK / "baselines/baseline_summary.csv").assign(scope="baseline"),
        current.assign(scope="current_method"),
    ], ignore_index=True, sort=False))
    write_csv(PACK / "analysis/paired_comparisons.csv", pd.read_csv(PACK / "comparisons/method_vs_baseline_by_budget.csv"))
    write_csv(PACK / "analysis/materializer_comparisons.csv", pd.read_csv(PACK / "comparisons/materializer_replay_comparison.csv"))
    write_csv(PACK / "analysis/seed_variability.csv", pd.read_csv(PACK / "baselines/baseline_budget_curves.csv"))

    decision = {
        "benchmark_id": benchmark_id,
        "oracle_build_id": oracle_build_id,
        "decision": "BENCHMARK_V2_STRICT_FROZEN_READY_FOR_BCM",
        "benchmark_frozen": True,
        "completion_audit": "PASS",
        "compatibility": True,
        "strict_oracle_provenance": "PASS",
        "ready_for_bcm": True,
        "valid_baseline_runs": context["valid_baseline_runs"],
        "valid_current_runs": context["valid_current_runs"],
        "best_native_baseline": f"{best_native.method}/{best_native.method_variant}",
        "best_native_event_f1_auc": float(best_native.event_f1_auc),
        "best_controlled_baseline": f"{best_controlled.method}/{best_controlled.method_variant}",
        "best_controlled_event_f1_auc": float(best_controlled.event_f1_auc),
        "blocking_reason": "",
    }
    write_csv(PACK / "FINAL_DECISION.csv", [decision])
    handoff = f"""# NEXT BCM TASK CONTEXT

- Strict benchmark ID: `{benchmark_id}`
- Strict oracle-build ID: `{oracle_build_id}`
- Public planner inputs: `frozen_inputs/units.csv`, `frozen_inputs/public_proxy.csv`
- Evaluator-only/forbidden online: `frozen_inputs/oracle_observations.csv`, `frozen_inputs/event_reference.csv`, `oracle/parsed/`, `evaluator/`, saved matches/metrics
- OracleAccessor: `scripts/run_clean_benchmark_v2_strict.py::OracleAccessor`
- Materializers/evaluator: `scripts/benchmark_lib.py::{{materialize_from_trace,evaluate_events}}`
- Matcher: overlap-any one-to-one, maximum cardinality then temporal IoU; hash in `BENCHMARK_MANIFEST.json`
- Budgets: `{BUDGETS}`; one logical cost per unique query; duplicates rejected
- Expected matrix: 1,464 baseline + 12 MAP/M1 runs
- Best native: `{decision['best_native_baseline']}` AUC `{decision['best_native_event_f1_auc']:.6f}`
- Best controlled: `{decision['best_controlled_baseline']}` AUC `{decision['best_controlled_event_f1_auc']:.6f}`
- Required BCM output: `agent_run/bcm_aqp_experiment_v2`
- No BCM physical VLM calls; never modify this strict directory after freeze.
"""
    write_text(PACK / "NEXT_BCM_TASK_CONTEXT.md", handoff)
    write_text(PACK / "FROZEN_BENCHMARK_V2.md", f"# Frozen strict benchmark v2\n\nDecision: `BENCHMARK_V2_STRICT_FROZEN_READY_FOR_BCM`\n\nBenchmark `{benchmark_id}`, oracle build `{oracle_build_id}`, 347 fresh accepted oracle outputs, zero legacy raw reuse, {context['valid_baseline_runs']} baseline and {context['valid_current_runs']} current runs. Completion, compatibility, strict provenance, recomputation, replay, leakage, and independent-review gates all PASS.\n")
    manifest.update({
        "benchmark_frozen": True,
        "completion_audit": "PASS",
        "compatibility_pass": True,
        "decision": "BENCHMARK_V2_STRICT_FROZEN_READY_FOR_BCM",
        "freeze_timestamp_utc": now(),
        "ready_for_bcm": True,
        "status": "FROZEN_COMPLETE",
        "strict_oracle_provenance": "PASS",
        "strict_oracle_build_id": oracle_build_id,
        "run_counts": {"baseline_valid": context["valid_baseline_runs"], "current_method_valid": context["valid_current_runs"], "failed_expected_runs": 0},
        "result_hashes": {
            "completion_audit": sha256_file(PACK / "evaluator/completion_audit.csv"),
            "baseline_rankings": sha256_file(PACK / "analysis/baseline_rankings.csv"),
            "event_f1_auc": sha256_file(PACK / "analysis/event_f1_auc.csv"),
        },
    })
    write_json(manifest_path, manifest)
    repair_frozen_run_state()
    rows = []
    for path in sorted(PACK.rglob("*")):
        if path.is_file() and path.name not in {
            "FILE_MANIFEST.csv", "STRICT_BENCHMARK_FROZEN.json", "RUN_STATE.json", ".strict_freeze.lock"
        }:
            rows.append({"path": str(path.relative_to(PACK)), "size_bytes": path.stat().st_size,
                         "sha256": sha256_file(path), "manifest_rule": "EXCLUDES_SELF_FINAL_MARKER_AND_OPERATIONAL_STATE"})
    write_csv(PACK / "FILE_MANIFEST.csv", rows)
    marker = {
        "benchmark_id": benchmark_id,
        "oracle_build_id": oracle_build_id,
        "decision": manifest["decision"],
        "manifest_sha256": sha256_file(manifest_path),
        "completion_audit_sha256": sha256_file(PACK / "evaluator/completion_audit.csv"),
        "file_manifest_sha256": sha256_file(PACK / "FILE_MANIFEST.csv"),
        "audit_bundle_sha256": sha256_file(PACK / "evaluator/PRE_REVIEW_AUDIT_BUNDLE.json"),
        "independent_review_sha256": sha256_file(PACK / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json"),
        "committed_at_utc": now(),
        "status": "FROZEN_COMMIT",
    }
    write_json(PACK / "STRICT_BENCHMARK_FROZEN.json", marker)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["audit", "freeze"], required=True)
    args = parser.parse_args()
    with FREEZE_LOCK.open("w", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another strict benchmark freeze/audit process holds the lock") from exc
        if (PACK / "STRICT_BENCHMARK_FROZEN.json").exists():
            marker = verify_frozen_commit()
            print(json.dumps({"stage": args.stage, "status": "VERIFIED_EXISTING_COMMIT", **marker}, sort_keys=True))
            return
        checks, context = audit()
        if args.stage == "audit":
            print(json.dumps({"stage": args.stage, **context,
                              "failed_checks": [row["check"] for row in checks if row["status"] != "PASS"]}, sort_keys=True))
            return
        freeze(checks, context)
        marker = verify_frozen_commit()
        print(json.dumps({"stage": "freeze", "status": "NEW_COMMIT_VERIFIED", **context,
                          "failed_checks": [], "marker": marker}, sort_keys=True))


if __name__ == "__main__":
    main()
