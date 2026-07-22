#!/usr/bin/env python3
"""Read-only static validator for the PSVR preimplementation package."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/psvr_rollout_preimplementation"
OUT = ROOT / "outputs/psvr_rollout_preimplementation"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def splitmix64_sequence(seed: int, n: int) -> list[int]:
    mask = (1 << 64) - 1
    state = seed & mask
    result = []
    for _ in range(n):
        state = (state + 0x9E3779B97F4A7C15) & mask
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & mask
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
        result.append((z ^ (z >> 31)) & mask)
    return result


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def resolve_ref(root: dict, ref: str):
    if not ref.startswith("#/"):
        raise ValueError(f"only local refs are permitted: {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def validate_instance(value, schema: dict, root: dict, where: str = "$") -> None:
    """Small dependency-free validator for the schema features used here."""
    if "$ref" in schema:
        return validate_instance(value, resolve_ref(root, schema["$ref"]), root, where)
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{where}: value not in enum")
    expected = schema.get("type")
    allowed = expected if isinstance(expected, list) else [expected] if expected else []
    type_ok = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "boolean": lambda x: isinstance(x, bool),
        "null": lambda x: x is None,
    }
    if allowed and not any(type_ok[t](value) for t in allowed):
        raise ValueError(f"{where}: expected {allowed}, got {type(value).__name__}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise ValueError(f"{where}: missing {sorted(missing)}")
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise ValueError(f"{where}: unexpected {sorted(set(value)-set(props))}")
        for key, item in value.items():
            if key in props:
                validate_instance(item, props[key], root, f"{where}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise ValueError(f"{where}: invalid item count")
        for i, subschema in enumerate(schema.get("prefixItems", [])):
            if i < len(value):
                validate_instance(value[i], subschema, root, f"{where}[{i}]")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                validate_instance(item, schema["items"], root, f"{where}[{i}]")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{where}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{where}: above maximum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise ValueError(f"{where}: not above exclusiveMinimum")


def main() -> int:
    failures: list[str] = []
    required = [
        *(DOC / name for name in [
            "00_AUTHORITY_AND_TERMINOLOGY.md", "01_D1_UTILITY_REGISTRY.md",
            "02_D2_SHIELDED_BASE_POLICY.md", "03_D3_TOY_GENERATIVE_MODEL.md",
            "04_D4_H_ROLLOUT1A_PREREGISTRATION.md",
            "05_MATHEMATICAL_IDENTITIES_AND_ASSUMPTIONS.md",
            "06_COUNTEREXAMPLE_AND_EDGE_CASE_CATALOG.md",
            "07_DESIGN_DECISION_LEDGER.md", "08_SUPERSEDED_DESIGNS.md",
        ]),
        *(OUT / name for name in [
            "UTILITY_REGISTRY.json", "BASE_POLICY_SPEC.json",
            "TOY_ENVIRONMENT_SCHEMA.json", "TOY_PARAMETER_DISTRIBUTION.yaml",
            "H_ROLLOUT1A_PREREGISTRATION.json",
            "PREIMPLEMENTATION_FREEZE_MANIFEST.json",
            "PREIMPLEMENTATION_COMPLETION_AUDIT.json",
            "INDEPENDENT_ADVERSARIAL_REVIEW.md", "FINAL_REPORT.md",
            "NEXT_EXACT_COMMAND.md",
        ]),
    ]
    for path in required:
        check(path.is_file() and path.stat().st_size > 0, f"missing/empty {path}", failures)
    if failures:
        print(json.dumps({"status": "FAIL", "failures": failures}, indent=2))
        return 1

    utility = json.loads((OUT / "UTILITY_REGISTRY.json").read_text())
    base = json.loads((OUT / "BASE_POLICY_SPEC.json").read_text())
    schema = json.loads((OUT / "TOY_ENVIRONMENT_SCHEMA.json").read_text())
    construction = json.loads((OUT / "TOY_CONSTRUCTION_SPEC.json").read_text())
    named = json.loads((OUT / "TOY_NAMED_SCENARIOS.json").read_text())
    params = yaml.safe_load((OUT / "TOY_PARAMETER_DISTRIBUTION.yaml").read_text())
    prereg = json.loads((OUT / "H_ROLLOUT1A_PREREGISTRATION.json").read_text())
    manifest = json.loads((OUT / "PREIMPLEMENTATION_FREEZE_MANIFEST.json").read_text())

    check(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "wrong JSON Schema dialect", failures)
    # Resolve every reference, then validate a minimal construction instance.
    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                resolve_ref(schema, node["$ref"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    walk(schema)
    dist = lambda family="CONSTANT": {"family": family, "parameters": {"value": 1}}
    sample_episode = {
        "episode_id": "schema_smoke", "seed": 1, "horizon_seconds": 10,
        "regions": [{"region_id": "r0", "media_start": 0, "media_end": 10,
                     "latent_event_ids": ["e0"], "scan_duration_distribution": dist(),
                     "candidate_emission": {"candidate_quality": 0.5, "duplicate_factor": 1,
                                            "region_activity": 1},
                     "hard_negative_process": {"rate": 0}}],
        "latent_events": [{"event_id": "e0", "query_id": "q", "region_ids": ["r0"],
                           "interval": [1, 2], "actor_id": "a", "detectability": 0.5,
                           "candidate_multiplicity": dist("POISSON"),
                           "confirm_characteristics": {"nominal_duration_seconds": 5}}],
        "cost_process": {"scan": dist(), "confirm": dist(), "mode_switch": dist(),
                         "planning": dist(), "variance_scale": 0,
                         "scan_confirm_ratio_regime": "BALANCED"},
        "grouping": {"under_merge_rate": 0, "over_merge_rate": 0,
                     "over_merge_suppression_loss": True},
        "oracle": {"true_positive_rate": 1, "false_positive_rate": 0,
                   "materialization_success_rate": 1},
        "planning": {"mode": "IDEAL_ZERO", "duration_distribution": dist()},
    }
    validate_instance(sample_episode, schema, schema)
    check(utility["initial_utility"]["u0"] == 0, "u(0) is not zero", failures)
    check(utility["lambda_primary"] == 1, "primary lambda changed", failures)
    check(utility["lambda_sensitivity"] == [0, 2], "lambda sensitivities changed", failures)
    check(base["logical_spec_status"] == "COMPLETE", "D2 logic incomplete", failures)
    check(base["numeric_binding"]["TOTAL_SCAN_BOUND"] is None, "unsubstantiated scan bound appeared", failures)
    check(base["status"] == "BLOCKED_NUMERIC_BINDING", "D2 block was hidden", failures)
    dev = params["splits"]["development"]["seeds"]
    held = params["splits"]["heldout"]["seeds"]
    check(not set(dev) & set(held), "development/heldout seed overlap", failures)
    check(params["axes"]["estimator_noise"]["H_ROLLOUT1A"] == 0.0, "H-ROLLOUT1A estimator noise not zero", failures)
    check(params["planning"]["primary"]["seconds"] == 0.0, "H-ROLLOUT1A planning cost not zero", failures)
    check(params["named_scenarios_in_primary_inference"] is False, "named scenarios promoted to primary inference", failures)
    bindings = {
        "utility_registry_hash": sha(OUT / "UTILITY_REGISTRY.json"),
        "base_policy_hash": sha(OUT / "BASE_POLICY_SPEC.json"),
        "toy_environment_hash": canonical_hash({"schema_sha256": sha(OUT / "TOY_ENVIRONMENT_SCHEMA.json"), "construction_sha256": sha(OUT / "TOY_CONSTRUCTION_SPEC.json")}),
        "parameter_distribution_hash": sha(OUT / "TOY_PARAMETER_DISTRIBUTION.yaml"),
    }
    for key, value in bindings.items():
        check(prereg[key] == value, f"D4 stale binding: {key}", failures)
    check(prereg["development_seed_hash"] == canonical_hash(dev), "development seed hash mismatch", failures)
    check(prereg["heldout_seed_hash"] == canonical_hash(held), "held-out seed hash mismatch", failures)
    check(prereg["toy_environment_schema_hash"] == sha(OUT / "TOY_ENVIRONMENT_SCHEMA.json"), "toy schema hash mismatch", failures)
    check(prereg["toy_construction_hash"] == sha(OUT / "TOY_CONSTRUCTION_SPEC.json"), "toy construction hash mismatch", failures)
    check(params["construction_spec_sha256"] == sha(OUT / "TOY_CONSTRUCTION_SPEC.json"), "parameter file has stale construction binding", failures)
    check(params["named_scenario_spec_sha256"] == sha(OUT / "TOY_NAMED_SCENARIOS.json"), "parameter file has stale named-scenario binding", failures)
    check(construction["rng"]["fixture_first_uint64"] == splitmix64_sequence(construction["rng"]["fixture_seed"], 8), "SplitMix64 conformance fixture mismatch", failures)
    expected_scenarios = {"VERIFY_FIRST_FAILURE", "SCAN_FIRST_FAILURE", "FIXED_PERIODIC_FAILURE", "CAPACITY_MATCHING_LOW_QUALITY_FAILURE", "SINGLE_HIGH_VALUE_FRONTIER", "DUPLICATE_HEAVY_FRONTIER", "LATE_HORIZON_CLOSURE", "HETEROGENEOUS_CONFIRM_COST", "DENSE_HOMOGENEOUS_BASELINE_FAVORABLE", "BURSTY_SCAN_FAVORABLE"}
    check({s["scenario_id"] for s in named["scenarios"]} == expected_scenarios, "named scenario fixture set mismatch", failures)
    check(all(s["primary_inference"] is False for s in named["scenarios"]), "named scenario promoted to primary inference", failures)
    check(prereg["named_scenario_hash"] == sha(OUT / "TOY_NAMED_SCENARIOS.json"), "D4 named-scenario hash mismatch", failures)
    check(prereg["status"] == "BLOCKED_DEPENDENCY_D2_NUMERIC_BINDING", "D4 improperly marked executable", failures)
    check(prereg["execution_authorized"] is False, "D4 execution accidentally authorized", failures)
    for entry in manifest["artifacts"]:
        path = ROOT / entry["path"]
        check(path.is_file(), f"manifest path missing: {entry['path']}", failures)
        if path.is_file():
            check(path.stat().st_size == entry["size"], f"size mismatch: {entry['path']}", failures)
            check(sha(path) == entry["sha256"], f"hash mismatch: {entry['path']}", failures)
    for entry in manifest["source_inputs"]:
        path = ROOT / entry["path"]
        check(path.is_file() and sha(path) == entry["sha256"], f"source input hash mismatch: {entry['path']}", failures)
    result_files = [p for p in OUT.iterdir() if p.name.startswith(("RUN_METRICS", "POLICY_COMPARISON", "HELDOUT_RESULTS"))]
    check(not result_files, f"toy result artifacts present: {result_files}", failures)
    review = (OUT / "INDEPENDENT_ADVERSARIAL_REVIEW.md").read_text()
    check("PENDING_INDEPENDENT_REVIEW" not in review, "independent review still pending", failures)

    status = "PASS_BLOCKED_D2_NUMERIC_BINDING" if not failures else "FAIL"
    print(json.dumps({"status": status, "checks": 33, "failures": failures}, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
