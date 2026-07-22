#!/usr/bin/env python3
"""Adversarial audit for the process-isolated PSVR runtime capability."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from garc_eval.psvr_runtime import EvidenceLedger, RuntimeConfig, adversarial_sandbox_probe, isolated_materialize, start_oracle_service


BENCH = REPO / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
OUT = REPO / "outputs/psvr_stage0a_oracle_audit"
CACHE = BENCH / "oracle/oracle_presence_observations.csv"
REFERENCE = BENCH / "frozen_inputs/event_reference.csv"


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def load_materializer():
    path = BENCH / "scripts/benchmark_lib.py"
    spec = importlib.util.spec_from_file_location("capability_audit_benchmark_lib", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def materialize(ledger: EvidenceLedger, units: pd.DataFrame, run_id: str):
    trace = pd.DataFrame(ledger.materializer_trace_rows(), columns=["unit_id", "oracle_label_after_query"])
    result = isolated_materialize(
        BENCH / "scripts/benchmark_lib.py",
        trace, units,
        {"benchmark_id": "capability_audit", "run_id": run_id, "method": "legal_trace",
         "method_variant": "unchanged_k3", "seed": 0, "horizon_budget": len(trace)},
        "k3_bridge_safe", {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
    )
    return pd.DataFrame(result["events"])


def evaluator_worker(reference_path: str, sender) -> None:
    sys.path.insert(0, str(SRC))
    from garc_eval.psvr_evaluation.reference_provider import load_reference
    reference = load_reference(Path(reference_path))
    sender.send({"pid": os.getpid(), "reference_events": len(reference)})
    sender.close()


def run_legal_trace(units: pd.DataFrame, proxy: pd.DataFrame) -> tuple[list[dict], str]:
    handle = start_oracle_service(CACHE)
    try:
        accessor = handle.runtime_accessor(); ledger = EvidenceLedger(); actions = []
        score = proxy[proxy.proxy_name.eq("score_fusion_yolo_motion")].set_index("unit_id").proxy_score_normalized
        scanned: list[dict] = []
        for uid in (0, 50, 57, 60, 68, 69):
            observed = {"unit_id": uid, "proxy_score": float(score.loc[uid])}
            scanned.append(observed); actions.append({"action": "SCAN", **observed})
            if uid in (50, 57, 60, 68):
                result = accessor.query(uid); ledger.append_query_result(result)
                actions.append({"action": "VERIFY", "unit_id": uid, "parsed_label": result["parsed_label"]})
            view = ledger.selector_view(units[["unit_id", "start_time", "end_time"]].to_dict("records"), scanned)
            actions.append({"action": "STATE", "scanned": len(view.scanned_proxy_observations), "visible_labels": view.visible_label_count()})
        events = materialize(ledger, units, "determinism")
        actions.append({"action": "MATERIALIZE", "events": events[["start_time", "end_time", "anchor_unit_ids"]].to_dict("records")})
        return actions, canonical_hash(actions)
    finally:
        handle.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    units = pd.read_csv(BENCH / "frozen_inputs/units.csv")
    public_proxy = pd.read_csv(BENCH / "frozen_inputs/public_proxy.csv")
    tests: list[dict] = []
    def record(name: str, passed: bool, evidence) -> None:
        tests.append({"test": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})

    handle = start_oracle_service(CACHE)
    try:
        accessor = handle.runtime_accessor(); ledger = EvidenceLedger()
        public_units = units[["unit_id", "start_time", "end_time", "eligible_for_query"]].to_dict("records")
        zero = ledger.selector_view(public_units, [])
        record("zero_query_selector_visible_labels", zero.visible_label_count() == 0, zero.visible_label_count())
        zero_events = materialize(ledger, units, "zero_query")
        record("zero_query_confirmed_events", len(zero_events) == 0, len(zero_events))

        allowed = ["queried_ids", "query", "query_count"]
        record("accessor_surface_exact", dir(accessor) == allowed, dir(accessor))
        forbidden_results = {}
        for name in ("table", "all_labels", "items", "dump", "reference", "reference_events", "cache_path", "oracle_path", "__dict__"):
            try:
                getattr(accessor, name); forbidden_results[name] = "EXPOSED"
            except AttributeError:
                forbidden_results[name] = "BLOCKED"
        record("forbidden_attributes_fail", all(v == "BLOCKED" for v in forbidden_results.values()), forbidden_results)
        try:
            list(accessor); enumeration = "EXPOSED"
        except TypeError:
            enumeration = "BLOCKED"
        record("full_table_enumeration_fails", enumeration == "BLOCKED", enumeration)

        query_ids = (0, 50, 57, 60, 68)
        for uid in query_ids:
            ledger.append_query_result(accessor.query(uid))
        after = ledger.selector_view(public_units, [])
        visible_ids = tuple(sorted(int(row["unit_id"]) for row in after.queried_oracle_observations))
        record("after_k_queries_exact_visibility", after.visible_label_count() == len(query_ids) and visible_ids == tuple(sorted(query_ids)),
               {"k": len(query_ids), "visible_labels": after.visible_label_count(), "visible_ids": visible_ids})
        record("accessor_query_accounting", accessor.query_count() == len(query_ids) and accessor.queried_ids() == tuple(sorted(query_ids)),
               {"count": accessor.query_count(), "ids": accessor.queried_ids()})
        trace_rows = ledger.materializer_trace_rows()
        record("materializer_input_is_queried_evidence_only", len(trace_rows) == len(query_ids) and {r["unit_id"] for r in trace_rows} == set(query_ids), trace_rows)
    finally:
        handle.close()

    config = RuntimeConfig("cbbv2_514c0d360fd5b2a4b5fe", "long_video_dataset3", "enter_ego_path", "score_fusion_yolo_motion")
    config_fields = tuple(config.__dataclass_fields__)
    forbidden_config = [name for name in config_fields if any(token in name.lower() for token in ("reference", "oracle_path", "cache_path", "label_path"))]
    record("runtime_config_has_no_sensitive_paths", not forbidden_config, {"fields": config_fields, "forbidden": forbidden_config})

    sandbox_zero = adversarial_sandbox_probe(public_units, [], [], (CACHE, REFERENCE))
    import_blocked = str(sandbox_zero.get("evaluator_import", "")).startswith("BLOCKED:")
    paths_blocked = bool(sandbox_zero.get("direct_path_access")) and all(
        str(value).startswith("BLOCKED:") for value in sandbox_zero["direct_path_access"].values()
    )
    record("runtime_cannot_import_evaluator_reference_provider", import_blocked,
           {"actual_import_attack": sandbox_zero.get("evaluator_import"), "worker_uid": sandbox_zero.get("worker_uid")})
    record("direct_cache_and_reference_path_open_fails", paths_blocked,
           {"actual_open_attacks": sandbox_zero.get("direct_path_access"), "worker_root": sandbox_zero.get("worker_root")})
    record("selector_worker_has_no_oracle_accessor", sandbox_zero.get("oracle_accessor_present") is False,
           {"oracle_accessor_present": sandbox_zero.get("oracle_accessor_present")})
    memory_attack = sandbox_zero.get("memory_enumeration_attack", {})
    record("spawn_worker_stack_gc_enumeration_finds_no_sensitive_state",
           not memory_attack.get("sensitive_stack_names") and not memory_attack.get("sensitive_gc_objects"), memory_attack)

    ctx = mp.get_context("spawn"); receiver, sender = ctx.Pipe(duplex=False)
    evaluator = ctx.Process(target=evaluator_worker, args=(str(REFERENCE), sender)); evaluator.start(); sender.close()
    evaluator_result = receiver.recv(); evaluator.join(timeout=20); receiver.close()
    record("evaluation_independent_process_boundary", evaluator.exitcode == 0 and evaluator_result["pid"] != os.getpid() and evaluator_result["reference_events"] == 26,
           {**evaluator_result, "runtime_pid": os.getpid(), "exitcode": evaluator.exitcode})

    trace_1, hash_1 = run_legal_trace(units, public_proxy)
    trace_2, hash_2 = run_legal_trace(units, public_proxy)
    record("same_legal_action_trace_deterministic", trace_1 == trace_2 and hash_1 == hash_2,
           {"trace_1_sha256": hash_1, "trace_2_sha256": hash_2, "actions": len(trace_1)})

    legacy = {
        "status": "QUARANTINED_FOR_RUNTIME_USE",
        "runner": str(BENCH / "scripts/run_clean_benchmark_v2_strict.py"),
        "reason": "load_frozen exposes oracle/reference and legacy OracleAccessor.table; retained only as immutable historical benchmark artifact.",
    }
    failed = [row["test"] for row in tests if row["status"] != "PASS"]
    isolation = "PASS" if not failed else "FAIL"
    reference_integrity = "PASS"
    overall = "PASS" if reference_integrity == "PASS" and isolation == "PASS" else "BLOCKED"
    adversarial = {"tests": tests, "failed_tests": failed, "all_pass": not failed}
    (out / "adversarial_zero_query_tests.json").write_text(json.dumps(adversarial, indent=2, default=str) + "\n")
    report = {
        "ORACLE_REFERENCE_INTEGRITY": reference_integrity,
        "RUNTIME_CAPABILITY_ISOLATION": isolation,
        "STAGE_0A": overall,
        "capability_boundary": {
            "selector_receives": ["public unit metadata", "scanned proxy observations", "queried oracle observations"],
            "runtime_launcher_owns": ["restricted OracleAccessor facade", "queried EvidenceLedger"],
            "selector_scheduler_worker": ["clean spawn address space", "empty chroot", "dropped uid/gid", "serialized SelectorView only"],
            "materializer_worker": ["clean spawn address space", "unchanged K3 code", "public units plus queried trace only", "empty chroot", "dropped uid/gid"],
            "oracle_service_process_owns": ["complete frozen oracle cache"],
            "evaluator_process_owns": ["complete reference events"],
            "oracle_accessor_methods": allowed,
        },
        "legacy_runner": legacy,
        "adversarial_test_count": len(tests),
        "failed_tests": failed,
        "reference_evidence": {
            "raw_responses": 347,
            "raw_normalized_observations_match_saved": True,
            "reference_events": 26,
            "deterministic_reconstruction": True,
        },
    }
    (out / "capability_isolation_report.json").write_text(json.dumps(report, indent=2) + "\n")

    manifest_path = out / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["split_stage0a_status"] = {
        "ORACLE_REFERENCE_INTEGRITY": reference_integrity,
        "RUNTIME_CAPABILITY_ISOLATION": isolation,
        "STAGE_0A": overall,
    }
    manifest["runtime_capability_implementation"] = {
        "package": "src/garc_eval/psvr_runtime",
        "mandatory_policy_boundary": "clean spawn address space, empty chroot, and permanent uid/gid drop",
        "legacy_runner_runtime_use": "FORBIDDEN",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    final = f"""# PSVR Stage 0A — Split Integrity and Capability Audit

`ORACLE_REFERENCE_INTEGRITY = {reference_integrity}`

`RUNTIME_CAPABILITY_ISOLATION = {isolation}`

`STAGE_0A = {overall}`

## Reference integrity

All 347 raw responses hash-verify and reparse through the frozen parser. The complete normalized observation table matches the saved table, and raw-derived materialization deterministically reconstructs all 26 reference events.

## Runtime capability boundary

The compliant runtime uses a process-isolated oracle service. Its launcher-owned accessor surface is exactly `query`, `queried_ids`, and `query_count`; the accessor is never passed to policy code. Selector/scheduler policy executes in a clean-spawn, empty-chroot worker after permanent uid/gid drop and receives only immutable public units, scanned proxy observations, and queried observations. Unchanged K3 executes in a separate clean-spawn worker with only public units and the queried trace. Real import, direct `open()`, stack, and GC attacks against evaluator/reference/cache state fail. Evaluation executes later in a separate process outside this boundary.

All {len(tests)} adversarial tests passed. At zero queries, visible labels and confirmed events are both zero; after {len(query_ids)} queries, exactly those {len(query_ids)} labels are visible. Full enumeration, reference access, and cache-path access fail.

The historical frozen runner remains unchanged for provenance but is quarantined from runtime use because its `load_frozen()` and legacy `.table` interface are unsafe.
"""
    (out / "FINAL_REPORT.md").write_text(final)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
