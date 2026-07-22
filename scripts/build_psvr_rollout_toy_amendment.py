#!/usr/bin/env python3
"""Build the result-blind D2 split amendment and D2-T binding artifacts.

This builder deliberately does not execute a policy, import the held-out runner,
or create a held-out result directory.  It may copy the already-frozen seed
lists into separate, hashable files.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_rollout_preimplementation"
DOC = ROOT / "docs/psvr_rollout_preimplementation"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    construction_path = OUT / "TOY_CONSTRUCTION_SPEC.json"
    utility_path = OUT / "UTILITY_REGISTRY.json"
    base_path = OUT / "BASE_POLICY_SPEC.json"
    env_path = OUT / "TOY_ENVIRONMENT_SCHEMA.json"
    prereg_path = OUT / "H_ROLLOUT1A_PREREGISTRATION.json"
    named_path = OUT / "TOY_NAMED_SCENARIOS.json"
    parameters_path = OUT / "TOY_PARAMETER_DISTRIBUTION.yaml"
    construction = json.loads(construction_path.read_text(encoding="utf-8"))

    amendment = {
        "amendment_id": "AMEND_D2_SPLIT_BEFORE_ANY_TOY_RESULTS",
        "amendment_reason": "Physical numerical calibration was incorrectly made a dependency of ideal toy mechanism evaluation.",
        "previous_terminal_state": "BLOCKED_D2_NUMERIC_BINDING",
        "results_visible_at_amendment": False,
        "toy_policy_results_exist": False,
        "heldout_toy_results_visible": False,
        "physical_policy_results_generated": False,
        "d2_logical_spec": "COMPLETE",
        "d2_toy_numeric_binding": "COMPLETE",
        "d2_physical_numeric_binding": "BLOCKED_CALIBRATION_REQUIRED",
        "physical_safety_claim": False,
        "prior_asset_hashes": {p.name: sha(p) for p in (utility_path, base_path, env_path, construction_path, prereg_path)},
    }
    write_json("PROTOCOL_AMENDMENT_D2_SPLIT.json", amendment)

    binding = {
        "binding_version": "D2_T_EXACT_SUPPORT_V1",
        "duration_distribution_family": "bounded two-point core duration plus bounded deterministic mode-switch cost",
        "support_bounds": {
            "confirm_nominal_seconds_supremum": 7.5,
            "cost_variance_supremum": 0.8,
            "duration_multiplier_supremum": 1.8,
            "mode_switch_seconds_supremum": 0.25,
            "scan_nominal_seconds_supremum": 31.25,
            "scan_core_seconds_supremum": 56.25,
            "scan_complete_seconds_supremum": 56.5,
            "confirm_core_seconds_supremum": 13.5,
            "confirm_complete_seconds_supremum": 13.75,
        },
        "scan_bound_function": "B_S(x,r)=scan_nominal(x,r)*(1+cost_variance(x))+I[mode switch]*0.25",
        "confirm_bound_function": "B_C(x,h,w)=confirm_nominal(x,h,w)*(1+cost_variance(x))+I[mode switch]*0.25",
        "standard_confirm_reserve": 13.75,
        "base_policy_reference": "D2-L / BASE_POLICY_SPEC.json logical policy, rebound to exact toy bounds",
        "toy_safety_semantics": "deterministic admission against exact mathematical support upper bounds; no empirical quantile or observed maximum",
        "physical_safety_claim": False,
        "configuration_universe": "frozen development and heldout parameter supports in TOY_CONSTRUCTION_SPEC.json; named fixtures are diagnostic only",
        "dependency_hashes": {
            "base_policy": sha(base_path),
            "construction": sha(construction_path),
            "environment_schema": sha(env_path),
            "parameter_distribution": sha(parameters_path),
        },
        "derivation": {
            "scan": "5*5*(0.75+0.5*2/2)*(1+0.8)+0.25 = 56.5",
            "confirm": "sup(5*(0.5+U))*(1+0.8)+0.25 = 13.75",
        },
        "validation_status": "MATHEMATICAL_BINDING_COMPLETE_IMPLEMENTATION_VALIDATION_PENDING",
    }
    write_json("D2_TOY_NUMERIC_BINDING.json", binding)

    graph = {
        "graph_version": "D2_SPLIT_V1",
        "edges": [
            {"from": ["D1"], "to": "D2-L"},
            {"from": ["D1"], "to": "D3"},
            {"from": ["D1"], "to": "UTILITY_METRIC_SEMANTICS"},
            {"from": ["D2-L", "D3"], "to": "D2-T"},
            {"from": ["D1", "D2-L", "D2-T", "D3"], "to": "D4A_H-ROLLOUT1A"},
            {"from": ["H-ROLLOUT1A_RESULT"], "to": "H-ROLLOUT1B"},
            {"from": ["D2-P_PHYSICAL_CALIBRATION"], "to": "H-ROLLOUT1C_PHYSICAL_PROTOTYPE"},
        ],
        "requires_d2_p": {"H-ROLLOUT1A": False, "H-ROLLOUT1B": False, "H-ROLLOUT1C": True},
        "claim_boundary": "toy mechanism evidence is not physical deadline-safety evidence",
    }
    write_json("D2_DEPENDENCY_GRAPH.json", graph)

    for split in ("development", "heldout"):
        seeds = construction["seed_mapping"][split]["ordered_seeds"]
        write_json(f"TOY_{split.upper()}_SEEDS.json", {
            "split": split,
            "ordered_seeds": seeds,
            "count": len(seeds),
            "canonical_seed_list_sha256": hashlib.sha256(canonical(seeds)).hexdigest(),
            "source": "TOY_CONSTRUCTION_SPEC.json",
            "source_sha256": sha(construction_path),
        })

    prereg = deepcopy(json.loads(prereg_path.read_text(encoding="utf-8")))
    prereg["status"] = "REBOUND_BUT_BLOCKED_INTERNAL_INCONSISTENCY"
    prereg["execution_authorized"] = False
    prereg["dependency_bindings"] = {
        "D1": sha(utility_path),
        "D2-L": sha(base_path),
        "D2-T": sha(OUT / "D2_TOY_NUMERIC_BINDING.json"),
        "D3": sha(construction_path),
        "D2-P_required": False,
    }
    prereg["toy_safety_binding"] = {
        "reference": "D2_TOY_NUMERIC_BINDING.json",
        "sha256": sha(OUT / "D2_TOY_NUMERIC_BINDING.json"),
        "physical_safety_claim": False,
    }
    prereg["excluded_claims"] = list(prereg["excluded_claims"]) + ["physical action calibration", "real runtime deadline safety"]
    prereg["blocking_consistency_audit"] = {
        "code": "MISSING_NONCLAIRVOYANT_CONDITIONAL_MODEL_KERNEL",
        "detail": "D4 requires visible-history conditional expected rollout, but frozen D3 specifies only complete seeded latent episodes and post-execution evaluator truth.",
    }
    write_json("UPDATED_H_ROLLOUT1A_PREREGISTRATION.json", prereg)

    config = {
        "configuration_id": "PSVR_TOY_SIMULATOR_V1_UNFROZEN_BLOCKED",
        "planning_primary_seconds": 0.0,
        "rng": "SplitMix64",
        "d2_t_binding_sha256": sha(OUT / "D2_TOY_NUMERIC_BINDING.json"),
        "development_seed_file": "TOY_DEVELOPMENT_SEEDS.json",
        "heldout_seed_file": "TOY_HELDOUT_SEEDS.json",
        "heldout_execution_authorized": False,
        "implementation_status": "BLOCKED_INTERNAL_INCONSISTENCY",
    }
    write_json("TOY_SIMULATOR_CONFIGURATION.json", config)

    generated = datetime.now(timezone.utc).isoformat()
    code_files = sorted((ROOT / "src/garc_eval/psvr_rollout_toy").glob("*.py"))
    code_manifest = {
        "generated_at": generated,
        "status": "PROTOTYPE_NOT_FROZEN",
        "files": [
            {"file": str(p.relative_to(ROOT)), "size": p.stat().st_size, "sha256": sha(p), "role": "prototype source", "dependency": "D1/D2-L/D2-T/D3"}
            for p in code_files
        ],
    }
    write_json("TOY_SIMULATOR_CODE_MANIFEST.json", code_manifest)

    smoke = {
        "status": "NOT_RUN_PROTOCOL_BLOCKED",
        "development_seed_file_opened": False,
        "heldout_seed_file_opened": False,
        "episodes_completed": 0,
        "exceptions": 0,
        "invariant_failures": 0,
        "hash_mismatches": 0,
        "deadline_violations": 0,
        "trace_recomputation_status": "NOT_RUN",
        "policy_metrics_generated": False,
        "policy_ranking_generated": False,
        "reason": "A smoke using the non-unique D3 generator or clairvoyant M1 would validate the wrong protocol.",
    }
    write_json("TOY_SIMULATOR_DEVELOPMENT_SMOKE_AUDIT.json", smoke)

    freeze = {
        "generated_at": generated,
        "status": "NOT_FROZEN_BLOCKED_INTERNAL_INCONSISTENCY",
        "code_manifest_sha256": sha(OUT / "TOY_SIMULATOR_CODE_MANIFEST.json"),
        "heldout_runner_exists": (ROOT / "scripts/run_psvr_rollout_h1a_heldout.py").exists(),
        "heldout_runner_executed": False,
        "heldout_comparison_run": False,
        "heldout_output_directory_exists": (OUT / "h_rollout1a_heldout").exists(),
        "blocking_defects": [
            "ratio draw absent from ordered RNG schedule",
            "offline future-aware grouping versus incremental visibility",
            "policy-dependent lazy cost tape lacks cross-method coupling",
            "missing visible-history conditional kernel for M1",
        ],
    }
    write_json("TOY_SIMULATOR_FREEZE_MANIFEST.json", freeze)

    completion = {
        "status": "BLOCKED_INTERNAL_INCONSISTENCY",
        "protocol_amendment_complete": True,
        "results_visible_at_amendment": False,
        "D1": "COMPLETE",
        "D2-L": "COMPLETE",
        "D2-T": "MATHEMATICAL_BINDING_COMPLETE",
        "D2-P": "BLOCKED_CALIBRATION_REQUIRED",
        "D3": "FROZEN_SOURCE_INTERNALLY_INSUFFICIENT_FOR_UNIQUE_EXECUTION",
        "D4A": "REBOUND_EXECUTION_BLOCKED",
        "toy_simulator_implemented": False,
        "development_smoke_passed": False,
        "heldout_seeds_read_by_runner": False,
        "heldout_comparison_run": False,
        "policy_ranking_generated": False,
        "physical_calls_started": 0,
        "gpu_jobs_started": 0,
        "heldout_real_data_opened": False,
        "unit_tests": {"command": "PYTHONPATH=src pytest -q tests/psvr_rollout_toy/test_protocol_block.py", "passed": 4, "failed": 0},
        "adversarial_review": "BLOCKED_INTERNAL_INCONSISTENCY",
        "all_hashes_recompute": True,
    }
    write_json("UPDATED_PREIMPLEMENTATION_COMPLETION_AUDIT.json", completion)

    amended_files = [
        "PROTOCOL_AMENDMENT_D2_SPLIT.json", "D2_TOY_NUMERIC_BINDING.json",
        "D2_DEPENDENCY_GRAPH.json", "UPDATED_H_ROLLOUT1A_PREREGISTRATION.json",
        "TOY_SIMULATOR_CONFIGURATION.json", "TOY_SIMULATOR_CODE_MANIFEST.json",
        "TOY_SIMULATOR_DEVELOPMENT_SMOKE_AUDIT.json", "TOY_SIMULATOR_FREEZE_MANIFEST.json",
        "UPDATED_PREIMPLEMENTATION_COMPLETION_AUDIT.json",
    ]
    updated_freeze = {
        "generated_at": generated,
        "status": "BLOCKED_INTERNAL_INCONSISTENCY",
        "previous_freeze_manifest_sha256": sha(OUT / "PREIMPLEMENTATION_FREEZE_MANIFEST.json"),
        "previous_terminal_state_preserved": "BLOCKED_D2_NUMERIC_BINDING",
        "results_visible_before_amendment": False,
        "amendment_reason": amendment["amendment_reason"],
        "files": [
            {"file": f"outputs/psvr_rollout_preimplementation/{name}", "size": (OUT / name).stat().st_size, "sha256": sha(OUT / name), "role": "amendment/audit", "dependency": "result-blind preimplementation state"}
            for name in amended_files
        ],
    }
    write_json("UPDATED_PREIMPLEMENTATION_FREEZE_MANIFEST.json", updated_freeze)


if __name__ == "__main__":
    main()
