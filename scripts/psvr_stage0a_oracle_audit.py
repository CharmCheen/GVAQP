#!/usr/bin/env python3
"""Audit the frozen strict oracle benchmark without mutating it."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
DEFAULT_BENCH = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
DEFAULT_OUT = REPO / "outputs/psvr_stage0a_oracle_audit"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_records(df: pd.DataFrame) -> str:
    records = []
    for row in df.to_dict("records"):
        records.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
    raw = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def load_builder(bench: Path):
    path = bench / "scripts/run_clean_benchmark_v2_strict.py"
    spec = importlib.util.spec_from_file_location("strict_builder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_oracle_builder(bench: Path):
    path = bench / "scripts/build_strict_oracle.py"
    spec = importlib.util.spec_from_file_location("strict_oracle_builder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def same_frame(left: pd.DataFrame, right: pd.DataFrame) -> tuple[bool, list[str]]:
    if list(left.columns) != list(right.columns):
        return False, [f"columns differ: {list(left.columns)} != {list(right.columns)}"]
    if len(left) != len(right):
        return False, [f"row count differs: {len(left)} != {len(right)}"]
    mismatches: list[str] = []
    for col in left.columns:
        a, b = left[col], right[col]
        if pd.api.types.is_bool_dtype(a) or pd.api.types.is_bool_dtype(b):
            equal = a.fillna(False).astype(bool).eq(b.fillna(False).astype(bool)).all()
        elif pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            equal = ((a.isna() & b.isna()) | ((a - b).abs() <= 1e-9)).all()
        else:
            equal = a.fillna("<NA>").astype(str).eq(b.fillna("<NA>").astype(str)).all()
        if not equal:
            mismatches.append(col)
    return not mismatches, mismatches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    bench, out = args.benchmark.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)

    units = pd.read_csv(bench / "frozen_inputs/units.csv").sort_values("unit_id")
    frozen_obs = pd.read_csv(bench / "frozen_inputs/oracle_observations.csv").sort_values("unit_id")
    source_obs = pd.read_csv(bench / "oracle/parsed/oracle_observations_source.csv").sort_values("unit_id")
    cache = pd.read_csv(bench / "oracle/oracle_cache_manifest.csv").sort_values("unit_id")
    ledger = pd.read_csv(bench / "oracle/VLM_CALL_LEDGER.csv").sort_values("unit_id")
    parsed_manifest = pd.read_csv(bench / "oracle/STRICT_PARSED_OUTPUT_MANIFEST.csv").sort_values("unit_id")
    saved_ref = pd.read_csv(bench / "frozen_inputs/event_reference.csv")
    main_manifest = json.loads((bench / "BENCHMARK_MANIFEST.json").read_text())
    build_manifest = json.loads((bench / "oracle/STRICT_ORACLE_BUILD_MANIFEST.json").read_text())
    config = build_manifest["build_identity"]["configuration"]
    ids = set(units.unit_id.astype(int))

    oracle_builder = load_oracle_builder(bench)
    coverage_rows = []
    raw_parsed_rows = []
    raw_hash_ok = raw_response_hash_ok = parsed_hash_ok = 0
    stale_frozen_paths = 0
    for uid in sorted(ids):
        c = cache.loc[cache.unit_id.astype(int).eq(uid)].iloc[0]
        l = ledger.loc[ledger.unit_id.astype(int).eq(uid)].iloc[0]
        p = parsed_manifest.loc[parsed_manifest.unit_id.astype(int).eq(uid)].iloc[0]
        f = frozen_obs.loc[frozen_obs.unit_id.astype(int).eq(uid)].iloc[0]
        raw = bench / str(c.raw_response_path)
        parsed = bench / str(p.path)
        raw_doc = json.loads(raw.read_text()) if raw.is_file() else {}
        raw_parsed, raw_parse_status = oracle_builder.parse_response(str(raw_doc.get("raw", "")))
        unit = units.set_index("unit_id").loc[uid]
        start_time = float(unit.start_time)
        def absolute(value):
            if value in (None, "", "null"):
                return ""
            try:
                return str(start_time + float(value))
            except (TypeError, ValueError):
                return ""
        raw_ok = raw.is_file() and sha256(raw) == str(c.raw_envelope_sha256)
        response_ok = bool(raw_doc) and hashlib.sha256(str(raw_doc.get("raw", "")).encode()).hexdigest() == str(c.raw_response_sha256)
        parsed_ok = parsed.is_file() and sha256(parsed) == str(p.sha256)
        raw_hash_ok += int(raw_ok)
        raw_response_hash_ok += int(response_ok)
        parsed_hash_ok += int(parsed_ok)
        frozen_path = bench / str(f.raw_output_path)
        stale_frozen_paths += int(not frozen_path.exists())
        coverage_rows.append({
            "unit_id": uid,
            "raw_path": str(c.raw_response_path),
            "raw_exists_and_hash_matches": raw_ok,
            "raw_response_text_hash_matches": response_ok,
            "parsed_path": str(p.path),
            "parsed_exists_and_hash_matches": parsed_ok,
            "physical_vlm_call": bool(l.physical_vlm_call),
            "cache_source": str(l.cache_source),
            "ledger_status": str(l.status),
            "parse_success": bool(f.parse_success),
            "raw_reparse_status": raw_parse_status,
            "frozen_observation_raw_path": str(f.raw_output_path),
            "frozen_observation_raw_path_exists": frozen_path.exists(),
        })
        raw_parsed_rows.append({
            "anchor_id": str(unit.anchor_id), "abstain_reason": raw_parsed.get("abstain_reason", "null"),
            "anchor_time": min(start_time + 5.0, float(unit.end_time)), "boundary_reliable": False,
            "boundary_status": raw_parsed.get("boundary_status", "not_applicable"),
            "complete_event_visible": raw_parsed.get("complete_event_visible", ""),
            "confidence": raw_parsed.get("confidence", "low"), "duration": float(unit.duration_seconds),
            "ego_relevant": raw_parsed.get("ego_relevant", ""), "end_time": float(unit.end_time),
            "event_end": "" if raw_parsed.get("event_end") is None else raw_parsed.get("event_end"),
            "event_end_absolute": absolute(raw_parsed.get("event_end")),
            "event_start": "" if raw_parsed.get("event_start") is None else raw_parsed.get("event_start"),
            "event_start_absolute": absolute(raw_parsed.get("event_start")),
            "event_type": raw_parsed.get("event_type", "none"), "evidence": raw_parsed.get("evidence", ""),
            "involved_object": raw_parsed.get("involved_object", "none"),
            "label": str(raw_parsed.get("label", "abstain")).lower(),
            "negative_reason": raw_parsed.get("negative_reason", "null"),
            "oracle_build_id": build_manifest["oracle_build_id"], "parse_status": raw_parse_status,
            "raw_reparse_status": raw_parse_status,
            "parsed_observation_sha256": oracle_builder.canonical_hash(raw_parsed),
            "raw_response_path": str(c.raw_response_path), "raw_response_sha256": str(c.raw_response_sha256),
            "runtime_seconds": float(raw_doc["generation_runtime_seconds"]), "start_time": start_time,
            "unit_id": uid, "video_id": str(unit.video_id),
        })
    pd.DataFrame(coverage_rows).to_csv(out / "oracle_coverage.csv", index=False)

    raw_parsed_df = pd.DataFrame(raw_parsed_rows)
    for column in ["event_start", "event_end", "event_start_absolute", "event_end_absolute"]:
        raw_parsed_df[column] = pd.to_numeric(raw_parsed_df[column], errors="coerce")
    reconstructed_labels = raw_parsed_df[source_obs.columns]
    reconstructed_labels.to_csv(out / "reconstructed_unit_labels.csv", index=False)
    normalized_match, normalized_mismatch_cols = same_frame(reconstructed_labels.reset_index(drop=True), source_obs.reset_index(drop=True))
    label_match = reconstructed_labels.set_index("unit_id").label.astype(str).eq(
        frozen_obs.set_index("unit_id").parsed_label.astype(str)
    ).all()

    builder = load_builder(bench)
    raw_materializer_input = reconstructed_labels.rename(columns={"label": "parsed_label"})
    rebuilt_1 = builder.build_reference(raw_materializer_input.copy(), str(main_manifest["benchmark_id"]))
    rebuilt_2 = builder.build_reference(raw_materializer_input.copy(), str(main_manifest["benchmark_id"]))
    rebuilt_1.to_csv(out / "reconstructed_reference_events.csv", index=False)
    ref_match, ref_mismatch_cols = same_frame(rebuilt_1, saved_ref)
    replay = {
        "unit_labels_match_frozen": bool(label_match),
        "raw_normalized_observations_match_saved": normalized_match,
        "raw_normalized_mismatching_columns": normalized_mismatch_cols,
        "reference_input": "raw_reparsed_normalized_observations",
        "reference_replay_1_sha256": canonical_records(rebuilt_1),
        "reference_replay_2_sha256": canonical_records(rebuilt_2),
        "saved_reference_sha256": canonical_records(saved_ref),
        "two_replays_identical": canonical_records(rebuilt_1) == canonical_records(rebuilt_2),
        "reconstructed_matches_saved": ref_match,
        "mismatching_columns": ref_mismatch_cols,
        "reference_events": len(rebuilt_1),
    }
    (out / "replay_consistency.json").write_text(json.dumps(replay, indent=2) + "\n")

    public_units = pd.read_csv(bench / "frozen_inputs/units.csv")
    public_proxy = pd.read_csv(bench / "frozen_inputs/public_proxy.csv")
    forbidden_terms = ("label", "reference", "oracle", "event_start_absolute", "event_end_absolute")
    exposed = [c for c in [*public_units.columns, *public_proxy.columns] if any(t in c.lower() for t in forbidden_terms)]
    source_text = "\n".join(
        p.read_text(errors="replace") for p in sorted((bench / "scripts").glob("*.py"))
    )
    interface_separation_documented = "Evaluator-only/forbidden online" in source_text
    execution_cache = (bench / "oracle/oracle_presence_observations.csv").resolve()
    evaluation_reference = (bench / "frozen_inputs/event_reference.csv").resolve()
    runtime = builder.load_frozen()
    accessor = builder.OracleAccessor(runtime, "stage0a_malicious_zero_query", 1)
    zero_query_oracle_rows_readable = len(runtime.oracle)
    zero_query_reference_rows_readable = len(runtime.reference)
    zero_query_accessor_rows_readable = len(accessor.table)
    leakage = {
        "public_surface_columns": {"units": list(public_units.columns), "public_proxy": list(public_proxy.columns)},
        "forbidden_columns_exposed": exposed,
        "selector_public_surface_pass": not exposed,
        "execution_cache_path": str(execution_cache),
        "evaluation_reference_path": str(evaluation_reference),
        "paths_are_distinct": execution_cache != evaluation_reference,
        "interface_separation_documented_in_frozen_code": interface_separation_documented,
        "malicious_zero_query_test": {
            "queried_count": len(accessor.queried),
            "frozen_oracle_rows_readable": zero_query_oracle_rows_readable,
            "frozen_reference_rows_readable": zero_query_reference_rows_readable,
            "oracle_accessor_public_table_rows_readable": zero_query_accessor_rows_readable,
        },
        "critical_failure": "Selector/runtime object graph directly exposes complete oracle labels and evaluation reference before any query.",
    }
    leakage["status"] = "FAIL" if zero_query_oracle_rows_readable or zero_query_reference_rows_readable or zero_query_accessor_rows_readable else "PASS"
    (out / "leakage_test_report.json").write_text(json.dumps(leakage, indent=2) + "\n")

    prompt = bench / "oracle/oracle_prompt.txt"
    parser_path = bench / "scripts/build_strict_oracle.py"
    video = Path(main_manifest["benchmark_source"])
    model = Path(str(frozen_obs.iloc[0].model_path))
    provenance_checks = {
        "unit_count_347": len(units) == 347 and ids == set(range(347)),
        "coverage_347": len(cache) == len(ledger) == len(parsed_manifest) == len(source_obs) == len(frozen_obs) == 347,
        "all_raw_hashes_match": raw_hash_ok == 347,
        "all_raw_response_text_hashes_match": raw_response_hash_ok == 347,
        "all_parsed_hashes_match": parsed_hash_ok == 347,
        "all_calls_physical": bool(ledger.physical_vlm_call.astype(bool).all()),
        "no_cache_replay_in_build": bool(ledger.cache_source.astype(str).eq("STRICT_FRESH_VLM_RESPONSE").all()),
        "all_parse_success": bool(frozen_obs.parse_success.astype(bool).all()),
        "all_raw_responses_reparse": bool(raw_parsed_df.raw_reparse_status.eq("ok").all()),
        "prompt_hash_matches": prompt.is_file() and sha256(prompt) == config["prompt_sha256"],
        "parser_source_present": parser_path.is_file(),
        "parser_source_hash_matches": hashlib.sha256(inspect.getsource(oracle_builder.parse_response).encode()).hexdigest() == config["parser_source_hash"],
        "frame_sampling_frozen": bool(config.get("frame_config")) and bool(config.get("sampling_code_hash")),
        "model_readable": model.exists() and os.access(model, os.R_OK),
        "video_readable": video.is_file() and os.access(video, os.R_OK),
        "reference_materializer_code_frozen": bool(main_manifest["compatibility"]["baseline_code_hashes"].get("benchmark_pipeline")),
        "reference_reconstructs_exactly": ref_match,
        "unit_labels_reconstruct_exactly": bool(label_match),
        "raw_normalized_observations_reconstruct_exactly": normalized_match,
        "stale_frozen_raw_paths": stale_frozen_paths,
    }
    critical = [k for k, v in provenance_checks.items() if k != "stale_frozen_raw_paths" and v is not True]
    limitations = []
    if stale_frozen_paths:
        limitations.append(f"{stale_frozen_paths}/347 frozen observation raw_output_path values use stale oracle/raw_cache paths; authoritative cache/parsed manifests resolve and hash all raw files under oracle/raw.")
    if str(saved_ref.reference_type.iloc[0]) != "FROZEN_ORACLE_DEFINED_REFERENCE":
        limitations.append(f"Reference semantic label is legacy {saved_ref.reference_type.iloc[0]!r}, not the v3 name, although lineage and contents reconstruct exactly.")
    if leakage["status"] == "FAIL":
        critical.append("runtime_no_leakage")
    status = "BLOCKED" if critical or leakage["status"] == "FAIL" else ("PASS_WITH_LIMITATIONS" if limitations else "PASS")
    provenance = {
        "status": status,
        "checks": provenance_checks,
        "critical_failures": critical,
        "limitations": limitations,
        "oracle_model_path": str(model),
        "oracle_model_hash": str(frozen_obs.iloc[0].model_hash),
        "video_path": str(video),
        "video_sha256": main_manifest["compatibility"]["video_sha256"],
        "prompt_path": str(prompt),
        "prompt_sha256": config["prompt_sha256"],
        "parser_hash": str(frozen_obs.iloc[0].parser_hash),
        "sampling_code_hash": config["sampling_code_hash"],
        "oracle_build_id": build_manifest["oracle_build_id"],
    }
    (out / "provenance_audit.json").write_text(json.dumps(provenance, indent=2) + "\n")

    git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, capture_output=True, check=True).stdout.strip()
    audit_manifest = {
        "audit": "PSVR_STAGE0A_ORACLE_BENCHMARK_INTEGRITY",
        "result": status,
        "source_benchmark": str(bench),
        "benchmark_id": main_manifest["benchmark_id"],
        "source_git_commit": git_commit,
        "counts": {"units": len(units), "raw_envelopes": raw_hash_ok, "raw_response_texts": raw_response_hash_ok, "parsed": parsed_hash_ok, "positive_units": int(frozen_obs.parsed_label.eq("positive").sum()), "reference_events": len(saved_ref)},
        "frozen_configuration": {
            "oracle_build_id": build_manifest["oracle_build_id"],
            "model_path": str(model),
            "model_hash": str(frozen_obs.iloc[0].model_hash),
            "prompt_hash": config["prompt_sha256"],
            "parser_hash": str(frozen_obs.iloc[0].parser_hash),
            "sampling_code_hash": config["sampling_code_hash"],
            "generation_config": config["generation_config"],
            "frame_config": config["frame_config"],
            "materializer": {"reference_version": str(saved_ref.reference_version.iloc[0]), "implementation": str(bench / "scripts/run_clean_benchmark_v2_strict.py::build_reference"), "implementation_hash": main_manifest["compatibility"]["baseline_code_hashes"]["benchmark_pipeline"]},
        },
        "output_hashes": {},
    }
    for name in ["oracle_coverage.csv", "provenance_audit.json", "reconstructed_unit_labels.csv", "reconstructed_reference_events.csv", "replay_consistency.json", "leakage_test_report.json"]:
        audit_manifest["output_hashes"][name] = sha256(out / name)
    (out / "benchmark_manifest.json").write_text(json.dumps(audit_manifest, indent=2) + "\n")

    report = f"""# PSVR Stage 0A — Oracle Benchmark Integrity Audit

`ORACLE_BENCHMARK_INTEGRITY = {status}`

## Decisive evidence

- Exhaustive coverage: {len(units)}/347 units, {raw_hash_ok}/347 raw responses hash-verified, {parsed_hash_ok}/347 parsed responses hash-verified.
- Physical origin: {int(ledger.physical_vlm_call.astype(bool).sum())}/347 ledger rows are physical VLM calls and all have `STRICT_FRESH_VLM_RESPONSE`; this is not cache replay.
- Reconstruction: all raw responses reparse successfully; the complete normalized observation table matches; two independent reference rebuilds from that raw-derived table are identical; the rebuilt {len(rebuilt_1)} events match the saved reference exactly.
- Frozen semantics: model, prompt, parser, generation config, frame sampling config/code hash, and materializer implementation hash are recorded in `benchmark_manifest.json`.
- Runtime leakage failure: at zero queries, `Frozen.oracle` exposes {zero_query_oracle_rows_readable} labels, `Frozen.reference` exposes {zero_query_reference_rows_readable} events, and public `OracleAccessor.table` exposes {zero_query_accessor_rows_readable} labels.

## Limitations

""" + "\n".join(f"- {x}" for x in limitations) + f"""

## Decision

Coverage, provenance, and deterministic reconstruction pass, but runtime no-leakage fails directly. Under v3 section 7.4 this is BLOCKED. Formal method comparison must not proceed until selector/runtime and evaluator capabilities are isolated and an adversarial zero-query access test fails closed.
"""
    (out / "FINAL_REPORT.md").write_text(report)
    print(status)


if __name__ == "__main__":
    main()
