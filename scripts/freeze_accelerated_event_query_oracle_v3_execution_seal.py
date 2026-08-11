#!/usr/bin/env python3
"""Freeze the exact executable surface for the AEQ V3 11-call preflight."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_v3_manifest import (
    atomic_text,
    load_json,
    sha256_file,
    validate_call_manifest,
    validate_payload_hash,
    write_json_once,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
PREREG = BASE / "preflight/V3_SCHEMA_PREFLIGHT_PREREGISTRATION.json"
SEAL = BASE / "execution_seal/V3_SCHEMA_PREFLIGHT_EXECUTION_SEAL.json"
APPROVAL_TEMPLATE = BASE / "execution_seal/V3_SCHEMA_PREFLIGHT_APPROVAL_TEMPLATE.md"
PROVENANCE = BASE / "preflight/V3_SCHEMA_PREFLIGHT_PROVENANCE_MANIFEST.json"


SOURCE_KEYS = {
    "runner": "runner_source",
    "runner_cli": "runner_cli_source",
    "analyzer": "analyzer_source",
    "analyzer_cli": "analyzer_cli_source",
    "decision": "decision_source",
    "seal_builder": "seal_source",
}


def build_seal() -> dict:
    prereg = load_json(PREREG)
    if prereg.get("status") != "FROZEN_BEFORE_V3_ORACLE_EXECUTION":
        raise RuntimeError("V3 preregistration is not frozen")
    checked_bindings = {}
    for key, relative in prereg["bindings"].items():
        if not key.endswith("_path"):
            continue
        hash_key = key.removesuffix("_path") + "_sha256"
        if hash_key not in prereg["bindings"]:
            continue
        observed = sha256_file(ROOT / relative)
        if observed != prereg["bindings"][hash_key]:
            raise RuntimeError(f"preregistration binding mismatch: {relative}")
        checked_bindings[key] = {"path": relative, "sha256": observed}
    call_manifest = load_json(ROOT / prereg["bindings"]["authorized_call_manifest_path"])
    validate_call_manifest(call_manifest, 11)
    if not all(call_manifest["assertions"].values()):
        raise RuntimeError("authorized call manifest assertions failed")
    provenance = load_json(PROVENANCE)
    validate_payload_hash(provenance, "provenance_payload_sha256")
    if not all((
        provenance.get("status") == "FROZEN_PREEXECUTION_PROVENANCE",
        provenance.get("experiment_id") == prereg["experiment_id"],
        provenance.get("preregistration_sha256") == sha256_file(PREREG),
        len(provenance.get("expected_calls", [])) == 11,
        provenance.get("producer_source_sha256")
            == prereg["bindings"]["analyzer_cli_source_sha256"],
        provenance.get("physical_outputs_present_when_frozen") is False,
    )):
        raise RuntimeError("preexecution provenance manifest mismatch")
    forbidden_preexecution = [
        *(ROOT / row["artifact_path"] for row in call_manifest["calls"]),
        *(ROOT / row["expected_parsed_path"] for row in provenance["expected_calls"]),
        *(ROOT / path for path in provenance["expected_attempt_ledgers"]),
        ROOT / provenance["expected_metrics_path"],
        ROOT / provenance["expected_evidence_manifest_path"],
        BASE / "preflight/V3_SCHEMA_PREFLIGHT_DECISION.json",
        BASE / "execution_seal/V3_SCHEMA_PREFLIGHT_COMPUTE_APPROVAL.json",
    ]
    if any(path.exists() for path in forbidden_preexecution):
        raise RuntimeError("physical or postrun V3 artifact exists before sealing")
    sources = {}
    for public_name, binding_name in SOURCE_KEYS.items():
        path = prereg["bindings"][f"{binding_name}_path"]
        observed = sha256_file(ROOT / path)
        sources[f"{public_name}_source_path"] = path
        sources[f"{public_name}_source_sha256"] = observed
    cost = load_json(ROOT / prereg["bindings"]["cost_estimate_path"])
    return {
        "status": "FROZEN_AWAITING_EXPLICIT_COMPUTE_APPROVAL",
        "experiment_id": prereg["experiment_id"],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_sha256": sha256_file(PREREG),
        "sources": sources,
        "checked_preregistration_bindings": checked_bindings,
        "exact_call_count": 11,
        "exact_sample_ids": sorted({row["candidate_id"] for row in call_manifest["calls"]}),
        "repair_membership": ["DALI_u0548"],
        "same_process_anchor_membership": ["DALI_u0555", "HANGZHOU_u0234", "WUHAN_u0217"],
        "cross_replica_anchor_membership": ["DALI_u0555"],
        "potential_unknown_membership": ["DALI_u0501"],
        "frame_manifest_sha256": prereg["bindings"]["frame_manifest_sha256"],
        "model_path": prereg["model"]["model_path"],
        "model_content_hash": prereg["model"]["model_content_hash"],
        "prompt_sha256": prereg["bindings"]["prompt_sha256"],
        "schema_sha256": prereg["bindings"]["schema_sha256"],
        "parser_sha256": prereg["bindings"]["parser_source_sha256"],
        "decoding_configuration": prereg["workload"]["generation"],
        "seed": prereg["workload"]["seed"],
        "gpu_schedule": prereg["gpu_schedule"],
        "no_retry_policy": "zero physical-generation retry; any failed or uncertain start requires new approval",
        "analyzer_sha256": prereg["bindings"]["analyzer_source_sha256"],
        "decision_mapping_sha256": prereg["bindings"]["decision_mapping_sha256"],
        "k3_config_sha256": load_json(
            ROOT / prereg["bindings"]["k3_config_path"]
        )["k3_config_sha256"],
        "estimated_a100_gpu_hours_including_load_and_call_overhead": cost[
            "estimated_a100_gpu_hours_including_load_and_call_overhead"
        ],
        "raw_output_root": str((BASE / "raw").relative_to(ROOT)),
        "parsed_output_root": str((BASE / "parsed").relative_to(ROOT)),
        "attempt_ledger_root": str((BASE / "preflight/attempt_ledgers").relative_to(ROOT)),
        "provenance_manifest_path": str(PROVENANCE.relative_to(ROOT)),
        "provenance_manifest_sha256": sha256_file(PROVENANCE),
        "postrun_evidence_manifest_path": provenance["expected_evidence_manifest_path"],
        "execution_session_rule": (
            "same-process pairs must share one authenticated session identity; cross-replica "
            "members must have distinct authenticated session identities"
        ),
        "independent_review_path": str((
            BASE / "execution_seal/V3_SCHEMA_PREFLIGHT_INDEPENDENT_REVIEW.md"
        ).relative_to(ROOT)),
        "execution_rule": (
            "All bindings and source hashes must match; an exact approval artifact must bind this "
            "seal before any physical inference; otherwise abort."
        ),
        "scope": "11-call schema/determinism preflight only; no full grid or downstream authorization",
    }


def approval_template(seal_sha256: str, prereg: dict) -> str:
    call_hash = prereg["bindings"]["authorized_call_manifest_sha256"]
    return f"""# V3 Schema Preflight Compute Approval Template

Status: `NOT_APPROVED_TEMPLATE`

No Qwen3-VL-32B inference is authorized by this template. After independent
review, the user must explicitly approve the unchanged sealed experiment.

- Execution seal SHA-256: `{seal_sha256}`
- Authorized call manifest SHA-256: `{call_hash}`
- Exact physical calls: `11`
- Estimated compute: approximately `0.19 A100 GPU-hours` plus normal host overhead
- Retry budget: `0`
- Full-grid authorization: `none`

Only after explicit approval, create
`execution_seal/V3_SCHEMA_PREFLIGHT_COMPUTE_APPROVAL.json` with exactly:

```json
{{
  "status": "APPROVED_BY_USER",
  "experiment_id": "AEQ_MODEL_RELATIVE_ORACLE_V3_SCHEMA_PREFLIGHT",
  "execution_seal_sha256": "{seal_sha256}",
  "authorized_call_manifest_sha256": "{call_hash}",
  "approved_physical_call_count": 11,
  "approval_scope": "exactly the 11 sealed V3 schema-and-determinism preflight calls; zero retry; no full-grid or downstream execution",
  "user_approval_evidence": "FILL_WITH_EXACT_USER_APPROVAL_REFERENCE"
}}
```

Abort rather than execute if any bound input, source, checkpoint, prompt,
schema, parser, schedule, analyzer, decision mapping, or seal differs.
"""


def main() -> None:
    seal = build_seal()
    write_json_once(SEAL, seal)
    prereg = load_json(PREREG)
    payload = approval_template(sha256_file(SEAL), prereg)
    if APPROVAL_TEMPLATE.exists():
        if APPROVAL_TEMPLATE.read_text(encoding="utf-8") != payload:
            raise RuntimeError("refusing to overwrite nonmatching approval template")
    else:
        atomic_text(APPROVAL_TEMPLATE, payload)
    print(json.dumps({
        "seal_path": str(SEAL.relative_to(ROOT)),
        "seal_sha256": sha256_file(SEAL),
        "approval_template": str(APPROVAL_TEMPLATE.relative_to(ROOT)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
