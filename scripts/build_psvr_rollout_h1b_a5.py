#!/usr/bin/env python3
"""Materialize A5's audit only; never execute a development identity."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "outputs/psvr_rollout_r2b_dev"
OUT = ROOT / "outputs/psvr_rollout_r2b_a5"
RUNNER = ROOT / "scripts/run_psvr_rollout_h1b_ic1_development.py"
ATTEMPT_LEDGER = ROOT / "outputs/psvr_rollout_r2b_ic1/development_attempt_v9/DEVELOPMENT_ATTEMPT_LEDGER.jsonl"
SEEDS = (-10001, -10002, -10003, -10004, -10005, -10006)
METHODS = (
    "B1_SHIELDED_PI0", "APPROX_NO_FALLBACK", "APPROX_POINT_ESTIMATE_FALLBACK",
    "APPROX_LCB_FALLBACK", "APPROX_PLANNING_ADMISSION_LCB",
)
EXTRA = (
    ("ic1-cfg-13", "b-4x4", "scan_candidate_yield", "independent_variance", .20, "p-0"),
    ("ic1-cfg-14", "b-16x16", "confirm_positive_probability", "state_dependent_calibration", .20, "p-2"),
    ("ic1-cfg-15", "b-64x64", "novelty_duplicate_probability", "independent_variance", .10, "p-5"),
    ("ic1-cfg-16", "b-256x256", "grouping_transition", "state_dependent_calibration", .10, "p-10"),
    ("ic1-cfg-17", "b-4x4", "action_duration", "independent_variance", .05, "p-20"),
    ("ic1-cfg-18", "b-16x16", "materialization_success", "state_dependent_calibration", .05, "p-2"),
)

def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def direction(form: str) -> str:
    return {"systematic_optimism": "OPTIMISTIC", "systematic_pessimism": "PESSIMISTIC"}[form]

def fallback(method: str) -> str:
    return {
        "B1_SHIELDED_PI0": "BASELINE", "APPROX_NO_FALLBACK": "NONE",
        "APPROX_POINT_ESTIMATE_FALLBACK": "POINT", "APPROX_LCB_FALLBACK": "LCB",
        "APPROX_PLANNING_ADMISSION_LCB": "LCB_ADMISSION",
    }[method]

def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    registry_path = DEV / "H1B_DEVELOPMENT_COVERAGE_MATRIX.json"
    original = json.loads(registry_path.read_text())["rows"]
    if len(original) != 13 or len({row["configuration_id"] for row in original}) != 13:
        raise RuntimeError("original registry is not the stated unique 13-row registry")
    first_attempt_mtime = ATTEMPT_LEDGER.stat().st_mtime_ns
    runner_mtime = RUNNER.stat().st_mtime_ns
    if not runner_mtime > first_attempt_mtime:
        raise RuntimeError("timestamp evidence no longer establishes post-attempt runtime append")
    extra_rows = []
    for config_id, budget, target, form, magnitude, cost in EXTRA:
        extra_rows.append({
            "configuration_id": config_id, "budget_id": budget, "error_target_id": target,
            "error_form": form, "error_magnitude": magnitude, "planning_cost_id": cost,
            "first_introduction_file": str(RUNNER.relative_to(ROOT)),
            "first_introduction_commit": "UNAVAILABLE_UNTRACKED_WORKTREE",
            "timestamp_evidence": {
                "runner_mtime_utc": RUNNER.stat().st_mtime_ns,
                "attempt_ledger_mtime_utc": first_attempt_mtime,
                "ordering": "runner modification is later than development_attempt_v9 ledger",
            },
            "stated_rationale": "runner comment: complete unexercised form/magnitude axes",
            "present_in_frozen_registry": False,
            "derivable_from_original_13_row_registry": False,
            "development_metrics_visible_before_introduction": True,
            "result_influence": "NOT_EXCLUDABLE_FROM_AVAILABLE_PROVENANCE",
            "classification": "UNAUTHORIZED_POSTHOC_CONFIGURATION",
            "authorized_scientific": False,
            "reason": "introduced only by a runtime append after a development attempt; no pre-result authorization artifact",
        })
    seed_hash = digest({"namespace": "H1B_DEVELOPMENT_PUBLIC_V1", "seeds": SEEDS})
    method_hash = digest(METHODS)
    registry_hash = digest(original)
    schema = {
        "fields": ["development_episode_id", "configuration_id", "method_id", "posterior_budget_id",
                   "trajectory_budget_id", "error_target", "error_form", "error_magnitude",
                   "error_direction", "planning_cost_id", "fallback_variant", "canonical_lineage_hash"],
        "encoding": "canonical-json-sha256",
    }
    lineage = {
        "parent_lineage": "BASE -> A1 -> A2 -> A3 -> A4 -> V1 -> V2",
        "original_registry_hash": file_digest(registry_path),
        "canonical_snapshot_hash": file_digest(ROOT / "outputs/psvr_rollout_r2b/H1B_EXECUTION_READY_RESULT_BLIND_FREEZE_MANIFEST.json"),
    }
    lineage_hash = digest(lineage)
    manifest_preimage = {
        "universe_id": "H1B_A5_ORIGINAL_13ROW_UNIVERSE_V1",
        "universe_version": 1, "seeds": SEEDS, "seed_registry_hash": seed_hash,
        "scientific_configuration_ids": [row["configuration_id"] for row in original],
        "scientific_configuration_registry_hash": registry_hash, "methods": METHODS,
        "method_registry_hash": method_hash, "canonical_identity_schema": schema,
        "canonical_identity_schema_hash": digest(schema),
        "cartesian_product_rule": "sorted(seed index) x original-registry order x declared method order",
        "canonical_lineage_hash": lineage_hash, "expected_scientific_identity_count": 390,
    }
    universe_hash = digest(manifest_preimage)
    manifest = {**manifest_preimage, "development_universe_hash": universe_hash,
                "freeze_status": "NOT_FROZEN_BLOCKED_POSTHOC_CONFIGURATION"}
    identities = []
    for seed_index, _ in enumerate(SEEDS):
        for config in original:
            posterior, trajectory = config["budget_id"].removeprefix("b-").split("x")
            for method in METHODS:
                identity = {
                    "development_episode_id": f"development-{seed_index:04d}",
                    "configuration_id": config["configuration_id"], "method_id": method,
                    "posterior_budget_id": f"posterior-{posterior}", "trajectory_budget_id": f"trajectory-{trajectory}",
                    "error_target": config["error_target_id"], "error_form": config["error_form"],
                    "error_magnitude": config["error_magnitude"], "error_direction": direction(config["error_form"]),
                    "planning_cost_id": config["planning_cost_id"], "fallback_variant": fallback(method),
                    "canonical_lineage_hash": lineage_hash, "development_universe_hash": universe_hash,
                }
                identities.append({**identity, "identity_hash": digest(identity)})
    if len(identities) != 390 or len({item["identity_hash"] for item in identities}) != 390:
        raise RuntimeError("A5 390 identity materialization failed")
    write("A5_ORIGINAL_13_ROW_REGISTRY.json", {"status": "ORIGINAL_FROZEN_REGISTRY", "source": str(registry_path.relative_to(ROOT)), "source_hash": file_digest(registry_path), "rows": original})
    write("A5_RUNTIME_6_ROW_AUDIT.json", {"status": "UNBOUND_RUNTIME_EFFECTIVE_UNIVERSE", "rows": extra_rows})
    write("A5_AUTHORIZED_CONFIGURATION_REGISTRY.json", {"status": "PROVISIONAL_ORIGINAL_ONLY_NOT_FROZEN", "count": 13, "rows": original, "hash": registry_hash})
    write("A5_AUTHORIZED_IDENTITY_UNIVERSE.json", {"status": "NOT_EXECUTABLE", "identities": identities, "count": 390, "hash": digest(identities)})
    write("A5_DEVELOPMENT_UNIVERSE_MANIFEST.json", manifest)
    write("A5_IDENTITY_UNIVERSE_HASH.json", {"algorithm": "SHA-256 over the documented full universe preimage", "development_universe_hash": universe_hash, "full_identity_list_hash": digest(identities), "identity_count": 390, "full_identity_universe_bound": True, "execution_authorized": False})
    write("A5_COVERAGE_OBLIGATION_MATRIX.json", {
        "scientific_grid_obligations_from_core": ["four error forms", "magnitudes 0, 0.05, 0.10, 0.20", "all six targets plus JOINT", "four budget families", "five planning costs", "five methods"],
        "original_13_coverage": {"forms": sorted({x["error_form"] for x in original}), "magnitudes": sorted({x["error_magnitude"] for x in original})},
        "conclusion": "original registry does not cover the frozen full error-form/magnitude obligation; runtime additions cannot cure it because they are post-hoc",
    })
    rows = ["configuration_id,in_original_390,in_runtime_570,a5_classification,authorized_scientific,reason"]
    rows += [f'{row["configuration_id"]},true,true,ORIGINAL_FROZEN_REGISTRY,true,original registry' for row in original]
    rows += [f'{row["configuration_id"]},false,true,UNAUTHORIZED_POSTHOC_CONFIGURATION,false,post-attempt runtime append without pre-result authorization' for row in extra_rows]
    (OUT / "A5_DIFF_390_VS_570.csv").write_text("\n".join(rows) + "\n")
    write("A5_AMENDMENT.json", {
        "amendment_id": "H1B_A5_DEVELOPMENT_IDENTITY_UNIVERSE",
        "amendment_type": "RESULT_BLIND_SCIENTIFIC_AND_EXECUTION_CLARIFICATION",
        "parent_lineage": lineage["parent_lineage"],
        "confirmatory_results_visible_before_a5": False,
        "development_performance_used_for_selection": False,
        "scope": ["seed universe", "configuration registry", "method universe", "canonical identities", "coverage rule", "universe-hash semantics"],
        "scientific_semantics_changed": False,
        "status": "BLOCKED_POSTHOC_CONFIGURATION",
    })
    write("A5_FIXTURE_VERIFICATION_AUDIT.json", {
        "checks": [
            {"check": "original rows unique", "expected": 13, "observed": len(original), "status": "PASS"},
            {"check": "exact seed count", "expected": 6, "observed": len(SEEDS), "status": "PASS"},
            {"check": "exact method count", "expected": 5, "observed": len(METHODS), "status": "PASS"},
            {"check": "original Cartesian product", "expected": 390, "observed": len(identities), "status": "PASS"},
            {"check": "runtime rows individually classified", "expected": 6, "observed": len(extra_rows), "status": "PASS"},
            {"check": "all runtime rows pre-result authorized", "expected": 6, "observed": 0, "status": "FAIL"},
            {"check": "frozen full-form/magnitude coverage", "expected": "four forms / 0,.05,.10,.20", "observed": "two forms / 0,.05,.10", "status": "FAIL"},
        ],
        "commands": ["python scripts/build_psvr_rollout_h1b_a5.py", "python -m json.tool outputs/psvr_rollout_r2b_a5/A5_DEVELOPMENT_UNIVERSE_MANIFEST.json", "python -m py_compile scripts/build_psvr_rollout_h1b_a5.py"],
        "result": "BLOCKED_POSTHOC_CONFIGURATION",
    })
    write("A5_FREEZE_MANIFEST.json", {
        "a5_freeze_gate": "FAIL", "status": "BLOCKED_POSTHOC_CONFIGURATION",
        "authorized_original_universe_hash": universe_hash,
        "runtime_570_status": "UNBOUND_RUNTIME_EFFECTIVE_UNIVERSE",
        "v2_resumed": False, "ic1_resumed": False,
        "confirmatory_runner_created": False, "confirmatory_seeds_created": False, "confirmatory_results_exist": False,
    })
    write("A5_COMPLETION_AUDIT.json", {
        "input_state": {"a4_freeze_gate": "FAIL", "v2_final_state": "BLOCKED_REQUIRES_SCIENTIFIC_AMENDMENT", "ic1_resumed": False},
        "original_configuration_rows": 13, "runtime_added_rows": 6,
        "added_rows_unauthorized": 6, "authorized_scientific_config_count": 13,
        "authorized_diagnostic_config_count": 0, "seed_count": 6, "method_count": 5,
        "expected_scientific_identities": 390, "expected_diagnostic_identities": 0,
        "development_universe_hash": universe_hash, "full_identity_universe_bound": True,
        "development_results_used_for_selection": False,
        "blind_red_team": "BLOCKED_POSTHOC_CONFIGURATION",
        "a5_freeze_gate": "FAIL", "v2_resumed": False, "a4_freeze_gate": "FAIL",
        "ic1_resumed": False, "h1b_development_gate": "BLOCKED",
        "final_state": "BLOCKED_POSTHOC_CONFIGURATION",
        "unresolved_blockers": ["BLOCKED_POSTHOC_CONFIGURATION"],
        "next_research_stage": "obtain a new explicitly authorized, result-blind scientific-grid amendment or retain original incomplete registry without claiming full frozen-grid coverage",
    })

if __name__ == "__main__":
    main()
