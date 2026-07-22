#!/usr/bin/env python3
"""Finalize and verify the persistent MF-PSVR Stage-A research state."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
CANDIDATES = CYCLE / "candidates"
STAGE = CYCLE / "stage_a"
MODEL = STAGE / "modeling"

CANDIDATE_AUDIT = CANDIDATES / "CANDIDATE_EXTRACTION_COMPLETION_AUDIT.json"
CANDIDATE_COST = CANDIDATES / "CANDIDATE_EXTRACTION_COST.json"
CANDIDATE_INCIDENT = CANDIDATES / "CANDIDATE_AUDITOR_LIFECYCLE_INCIDENT_AUDIT.json"
FREEZE = STAGE / "STAGE_A_FREEZE_MANIFEST.json"
ORACLE_COMPLETE = STAGE / "oracle/STAGE_A_ORACLE_COMPLETE.json"
ORACLE_AUDIT = STAGE / "STAGE_A_ORACLE_ROUNDTRIP_VERIFICATION_AUDIT.json"
EXECUTION_DIFFERENCE = STAGE / "STAGE_A_EXECUTION_DIFFERENCE_AUDIT.json"
PHYSICAL_COST = STAGE / "STAGE_A_PHYSICAL_COST.json"
STAGE_STATE = STAGE / "STAGE_A_STATE.json"
SUPPORT_GATE = STAGE / "STAGE_A_SUPPORT_GATE_REPORT.json"
TEMPORAL_AUDIT = MODEL / "STAGE_A_TEMPORAL_MATERIALIZATION_AUDIT.json"
DATASET_AUDIT = MODEL / "STAGE_A_DATASET_COMPLETION_AUDIT.json"
FEATURE_SCHEMA = MODEL / "STAGE_A_FEATURE_SCHEMA.json"
PROTOCOL_PROVENANCE = MODEL / "STAGE_A_MODELING_PROTOCOL_PROVENANCE.json"
MODEL_AUDIT = MODEL / "STAGE_A_MODELING_COMPLETION_AUDIT.json"
READINESS = MODEL / "STAGE_A_MODEL_READINESS_DECISION.json"
METRICS = MODEL / "STAGE_A_MODEL_METRICS.csv"
PER_QUERY = MODEL / "STAGE_A_PER_QUERY_RESULTS.csv"
CONTROLS = MODEL / "STAGE_A_CONTROL_SUMMARY.csv"
BOOTSTRAP = MODEL / "STAGE_A_GROUP_BOOTSTRAP_INTERVALS.csv"
FINAL_REPORT = STAGE / "STAGE_A_TO_MODEL_FINAL_REPORT.md"
INDEPENDENT_REVIEW = MODEL / "STAGE_A_INDEPENDENT_ADVERSARIAL_REVIEW.json"
INDEPENDENT_REVIEW_MD = MODEL / "STAGE_A_INDEPENDENT_ADVERSARIAL_REVIEW.md"

STATE_JSON = STAGE / "STAGE_A_RESEARCH_STATE.json"
STATE_MD = STAGE / "STAGE_A_RESEARCH_STATE.md"
STATE_AUDIT = STAGE / "STAGE_A_RESEARCH_STATE_AUDIT.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode())


def finite(value: Any) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def one(frame: pd.DataFrame, **filters: str) -> dict[str, Any]:
    selected = frame
    for column, value in filters.items():
        selected = selected[selected[column] == value]
    if len(selected) != 1:
        raise RuntimeError(f"Expected one row for {filters}, found {len(selected)}")
    return selected.iloc[0].to_dict()


def validate_prerequisites() -> dict[str, Any]:
    required = [
        CANDIDATE_AUDIT, CANDIDATE_COST, CANDIDATE_INCIDENT, FREEZE,
        ORACLE_COMPLETE, ORACLE_AUDIT, EXECUTION_DIFFERENCE, PHYSICAL_COST,
        STAGE_STATE, SUPPORT_GATE, TEMPORAL_AUDIT, DATASET_AUDIT, FEATURE_SCHEMA,
        PROTOCOL_PROVENANCE, MODEL_AUDIT, READINESS, METRICS, PER_QUERY,
        CONTROLS, BOOTSTRAP, FINAL_REPORT, INDEPENDENT_REVIEW, INDEPENDENT_REVIEW_MD,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Research-state prerequisite missing: {missing}")
    values = {
        "candidate": load_json(CANDIDATE_AUDIT),
        "candidate_cost": load_json(CANDIDATE_COST),
        "candidate_incident": load_json(CANDIDATE_INCIDENT),
        "freeze": load_json(FREEZE),
        "oracle_complete": load_json(ORACLE_COMPLETE),
        "oracle_audit": load_json(ORACLE_AUDIT),
        "execution_difference": load_json(EXECUTION_DIFFERENCE),
        "physical_cost": load_json(PHYSICAL_COST),
        "stage_state": load_json(STAGE_STATE),
        "support_gate": load_json(SUPPORT_GATE),
        "temporal": load_json(TEMPORAL_AUDIT),
        "dataset": load_json(DATASET_AUDIT),
        "features": load_json(FEATURE_SCHEMA),
        "provenance": load_json(PROTOCOL_PROVENANCE),
        "model": load_json(MODEL_AUDIT),
        "readiness": load_json(READINESS),
        "review": load_json(INDEPENDENT_REVIEW),
    }
    checks = {
        "candidate_pass": values["candidate"].get("status") == "PASS",
        "candidate_incident_recovered": str(values["candidate_incident"].get("status", "")).startswith("PASS_RECOVERED"),
        "freeze_exact": values["freeze"].get("physical_call_identities") == 96 and values["freeze"].get("query_verification_keys") == 192,
        "oracle_complete": values["oracle_complete"].get("status") == "COMPLETE_COMMIT",
        "oracle_roundtrip_pass": values["oracle_audit"].get("status") == "PASS" and values["oracle_audit"].get("frozen_verify_result", {}).get("status") == "VERIFIED_COMPLETE_COMMIT",
        "verifier_exception_preserved": values["execution_difference"].get("status") == "PASS_WITH_RECORDED_FROZEN_VERIFIER_DEFECT",
        "semantic_stage_stop": values["stage_state"].get("status") == "STAGE_A_FAIL_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE",
        "temporal_pass": values["temporal"].get("status") == "PASS",
        "dataset_pass": values["dataset"].get("status") == "PASS",
        "model_pass": values["model"].get("status") == "PASS",
        "not_ready": values["readiness"].get("decision") == "NOT_READY_FOR_PHYSICAL_PILOT",
        "modeling_exploratory": values["provenance"].get("status") == "EXPLORATORY_FIXED_DURING_ORACLE_ACQUISITION",
        "independent_review_pass": "PASS" in str(values["review"].get("verdict", values["review"].get("status", ""))),
        "heldout_closed": all(value.get("heldout_opened") is False for value in (
            values["candidate"], values["freeze"], values["oracle_complete"],
            values["oracle_audit"], values["temporal"], values["dataset"], values["model"],
        )),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Research-state prerequisite checks failed: {checks}")
    values["checks"] = checks
    values["required"] = required
    return values


def build_state(created_at_utc: str) -> dict[str, Any]:
    values = validate_prerequisites()
    metrics = pd.read_csv(METRICS)
    per_query = pd.read_csv(PER_QUERY)
    controls = pd.read_csv(CONTROLS)
    bootstrap = pd.read_csv(BOOTSTRAP)
    readiness = values["readiness"]
    selected = readiness["selected_representation"]
    aggregate = readiness["best_aggregate_model"]
    temporal = readiness["best_temporal_model"]
    selected_dev = one(metrics, evaluation_scope="development_loso", model=selected)
    selected_audit = one(metrics, evaluation_scope="fixed_pool_audit", model=selected)
    raw_dev = one(metrics, evaluation_scope="development_loso", model="B0_RAW_YOLO")
    aggregate_dev = one(metrics, evaluation_scope="development_loso", model=aggregate)
    temporal_dev = one(metrics, evaluation_scope="development_loso", model=temporal)
    q1_selected = one(per_query, evaluation_scope="development_loso", model=selected, query_id="Q1")
    q2_selected = one(per_query, evaluation_scope="development_loso", model=selected, query_id="Q2")
    q1_raw = one(per_query, evaluation_scope="development_loso", model="B0_RAW_YOLO", query_id="Q1")
    q2_raw = one(per_query, evaluation_scope="development_loso", model="B0_RAW_YOLO", query_id="Q2")
    q1_stratum = one(per_query, evaluation_scope="development_loso", model="SELECTION_STRATUM_ONLY", query_id="Q1")
    stratum = one(controls, control="SELECTION_STRATUM_ONLY")
    shuffled = one(controls, control="SHUFFLED_LABEL_M0")
    selected_raw_macro = one(
        bootstrap,
        evaluation_scope="development_loso",
        estimate_type="paired_model_delta",
        comparison="selected_minus_raw_yolo",
        metric="macro_query_auprc",
    )
    temporal_aggregate_pooled = one(
        bootstrap,
        evaluation_scope="development_loso",
        estimate_type="paired_model_delta",
        comparison="best_temporal_minus_best_aggregate",
        metric="auprc",
    )
    bindings = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in values["required"]
    }
    state: dict[str, Any] = {
        "state_id": "MF_PSVR_STAGE_A_RESEARCH_STATE_V1",
        "created_at_utc": created_at_utc,
        "status": "STAGE_A_COMPLETE_NOT_READY_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE",
        "current_objective": "Determine whether query-aligned candidate-value or temporal modeling on the exact frozen Stage-A evidence justifies entering an MF-PSVR V0/V1 physical pilot.",
        "established_findings": [
            {
                "evidence_type": "observed",
                "finding": "Candidate extraction is exact and complete.",
                "values": {"providers": 603, "units": 2654, "score_rows": 5308, "track_rows": 28551, "detector_gpu_seconds": values["candidate_cost"]["detector_gpu_seconds"]},
            },
            {
                "evidence_type": "observed",
                "finding": "The frozen physical oracle execution completed without uncertainty or parse failure.",
                "values": {"attempts": 96, "accepted_calls": 96, "projected_labels": 192, "uncertain": 0, "parse_failures": 0, "physical_cost_seconds": values["physical_cost"]["total_physical_cost_seconds"]},
            },
            {
                "evidence_type": "observed_with_explicit_exception",
                "finding": "The default frozen verifier fails only on one non-round-tripped CSV float; the unchanged frozen verifier fully passes with a parser-only round-trip shim.",
                "values": {"default_verify": "FAIL", "roundtrip_verify": "VERIFIED_COMPLETE_COMMIT"},
            },
            {
                "evidence_type": "observed",
                "finding": "The query-aligned dataset contains 192 semantic rows; 172 are binary, with 24 positives overall and 61 full-rank aggregate features retained from 72 candidates.",
                "values": {"semantic_rows": values["dataset"]["semantic_samples"], "binary_rows": values["dataset"]["binary_training_samples"], "positive_rows": values["dataset"]["positive_samples"], "retained_features": values["features"]["aggregate_redundancy_pruning"]["retained_feature_count"]},
            },
            {
                "evidence_type": "observed_exploratory",
                "finding": "M0 logistic is the development-pooled aggregate winner, but its macro-query advantage over raw YOLO is small and bootstrap-uncertain.",
                "values": {"selected": selected, "pooled_auprc": finite(selected_dev["auprc"]), "macro_query_auprc": finite(selected_dev["macro_query_auprc"]), "raw_pooled_auprc": finite(raw_dev["auprc"]), "raw_macro_query_auprc": finite(raw_dev["macro_query_auprc"]), "macro_delta": finite(selected_raw_macro["estimate"]), "macro_delta_ci_95": [finite(selected_raw_macro["ci_lower_2_5"]), finite(selected_raw_macro["ci_upper_97_5"])]},
            },
            {
                "evidence_type": "observed_exploratory",
                "finding": "Q1 M0 is indistinguishable from the selection-stratum control, while Q2 M0 is only slightly above raw YOLO.",
                "values": {"Q1_M0": finite(q1_selected["auprc"]), "Q1_stratum_only": finite(q1_stratum["auprc"]), "Q1_raw": finite(q1_raw["auprc"]), "Q2_M0": finite(q2_selected["auprc"]), "Q2_raw": finite(q2_raw["auprc"]), "pooled_stratum_only": finite(stratum["auprc_mean"]), "shuffled_p95_noisy": finite(shuffled["auprc_p95"])},
            },
            {
                "evidence_type": "observed_exploratory",
                "finding": "The best temporal model does not improve on the best aggregate model and is heterogeneous across queries.",
                "values": {"best_aggregate": aggregate, "aggregate_auprc": finite(aggregate_dev["auprc"]), "best_temporal": temporal, "temporal_auprc": finite(temporal_dev["auprc"]), "pooled_delta": finite(temporal_aggregate_pooled["estimate"]), "pooled_delta_ci_95": [finite(temporal_aggregate_pooled["ci_lower_2_5"]), finite(temporal_aggregate_pooled["ci_upper_97_5"])]},
            },
            {
                "evidence_type": "observed",
                "finding": "The fixed audit is arithmetically excluded from fitting/selection and favors M0, but it is small and was not cryptographically blinded.",
                "values": {"audit_rows": int(selected_audit["n"]), "audit_positives": int(selected_audit["positives"]), "audit_auprc": finite(selected_audit["auprc"]), "audit_ece": finite(selected_audit["ece"])},
            },
        ],
        "derived_conclusions": [
            "Stage A does not justify V0/V1 physical-pilot execution.",
            "The decisive blocker is the frozen support STOP plus insufficient per-query positive/calibration support; the exploratory model metrics do not override it.",
            "The large pooled M0-versus-raw AUPRC difference is partly cross-query score harmonization and cannot be interpreted as uniform query-specific refinement.",
            "Aggregate temporal summaries remain the better current representation; a causal TCN/GRU adds complexity without demonstrated stable incremental value.",
            "Individual feature coefficients are hypothesis-generating associations only, despite label-free rank pruning.",
        ],
        "active_hypotheses": [
            {
                "id": "H_TRANSPORTABLE_AGGREGATE_REFINEMENT",
                "hypothesis": "A compact aggregate model can improve macro-query and per-query ranking on a second licensed query-enriched source.",
                "prediction": "Prospectively frozen grouped evaluation shows positive per-query deltas over raw YOLO and stratum-only controls, with group intervals excluding zero.",
                "next_discriminating_action": "Acquire a second licensed query-enriched dataset under identical Q1/Q2 semantics and preregister analysis before any oracle output is readable.",
                "rejection_observation": "Either query fails to exceed its strongest raw/selection control or the macro-query paired interval continues to include zero.",
            },
            {
                "id": "H_Q1_REQUIRES_BETTER_QUERY_ALIGNED_SUPPORT",
                "hypothesis": "Q1 weakness is dominated by sparse, selection-driven support rather than lack of usable visual signal.",
                "prediction": "More independent Q1-positive event groups improve performance beyond a frozen stratum-only baseline.",
                "next_discriminating_action": "Measure prospective Q1 lift after support enrichment; do not tune new mechanisms on the current 7-positive development subset.",
                "rejection_observation": "Q1 remains at stratum-only performance after adequate independent positive-group support.",
            },
        ],
        "rejected_hypotheses": [
            {"hypothesis": "The lightweight temporal refiner is ready to replace aggregate features.", "reason": f"{temporal} minus {aggregate} pooled AUPRC is {float(temporal_aggregate_pooled['estimate']):+.6f}, with no stable per-query gain."},
            {"hypothesis": "The pooled M0 lift demonstrates uniform learned refinement.", "reason": f"Q1 M0 ({float(q1_selected['auprc']):.6f}) is below stratum-only ({float(q1_stratum['auprc']):.6f}); Q2 M0 ({float(q2_selected['auprc']):.6f}) is close to raw ({float(q2_raw['auprc']):.6f}); the macro paired interval spans zero."},
            {"hypothesis": "Final Platt calibration is deployable.", "reason": "The calibration role has one positive total (Q1=1, Q2=0); all fitted final calibrators are explicitly non-deployable."},
            {"hypothesis": "Stage A supports immediate physical-pilot execution.", "reason": "Frozen support decision STOP, only one dataset family, 7/9 development positives per query, and non-deployable calibration."},
        ],
        "important_failures_and_lessons": [
            "The frozen oracle runner omitted a writer for a required physical-cost artifact; independent reconstruction was required and bound before finalization.",
            "The frozen verifier used default pandas float parsing with bit-exact comparison; preserve the default failure and round-trip-parser receipt together.",
            "The initial aggregate schema treated witness_class_id as ordinal and contained affine redundancies; categorical encoding plus label-free full-rank pruning is required.",
            "The modeling protocol was fixed after 70 readable oracle envelopes existed; all model/readiness/bootstrap evidence is exploratory, not preregistered.",
            "A pre-oracle-only candidate auditor initially lacked lifecycle-safe CLI behavior and accidentally overwrote three summary receipts; exact recovery and a non-mutating verify path are now documented.",
            "VERIFY budgets must count physical generic calls, not the two semantic projections returned by each call.",
        ],
        "unresolved_uncertainties": [
            "Cross-dataset transport is unidentifiable with one dataset family.",
            "Natural-prevalence precision and recall are not identifiable from the enriched sample.",
            "The current positive count is too small for stable per-query feature attribution or calibration.",
            "Whether Q1 can exceed selection-stratum prevalence and whether Q2 can improve materially over raw YOLO require prospective evidence.",
            "Bootstrap intervals are conditional on fixed OOF predictions and do not include dataset-family uncertainty.",
        ],
        "next_highest_value_action": "Acquire one licensed query-enriched source dataset under the same frozen Q1/Q2 label semantics, freeze the provider/unit/oracle universe, and preregister grouped macro/per-query analysis before any oracle output is readable. Do not run V0/V1.",
        "next_handoff_integrity_command": "python scripts/finalize_mf_psvr_stage_a_research_state.py verify",
        "authorization_boundary": "No additional oracle calls, acquisition, or V0/V1 physical-method execution is authorized by this state.",
        "independent_review_verdict": values["review"].get("verdict", values["review"].get("status")),
        "artifact_bindings": bindings,
        "heldout_opened": False,
        "v0_v1_executed": False,
    }
    state["state_hash"] = canonical_hash(state)
    return state


def render_markdown(state: dict[str, Any]) -> str:
    findings = "\n".join(
        f"- [{row['evidence_type']}] {row['finding']} Values: `{json.dumps(row['values'], sort_keys=True)}`"
        for row in state["established_findings"]
    )
    conclusions = "\n".join(f"- {value}" for value in state["derived_conclusions"])
    active = "\n".join(
        f"- `{row['id']}`: {row['hypothesis']} Prediction: {row['prediction']} Next test: {row['next_discriminating_action']} Reject if: {row['rejection_observation']}"
        for row in state["active_hypotheses"]
    )
    rejected = "\n".join(f"- {row['hypothesis']} Rejected here because: {row['reason']}" for row in state["rejected_hypotheses"])
    failures = "\n".join(f"- {value}" for value in state["important_failures_and_lessons"])
    uncertainties = "\n".join(f"- {value}" for value in state["unresolved_uncertainties"])
    return f"""# MF-PSVR Stage-A persistent research state

Status: `{state['status']}`  
Independent review: `{state['independent_review_verdict']}`  
State hash: `{state['state_hash']}`

## Current objective

{state['current_objective']}

## Established findings

{findings}

## Derived conclusions

{conclusions}

## Active falsifiable hypotheses

{active}

## Rejected hypotheses

{rejected}

## Important failures and lessons

{failures}

## Unresolved uncertainties

{uncertainties}

## Next highest-value action

{state['next_highest_value_action']}

Authorization boundary: {state['authorization_boundary']}

Handoff verification:

```bash
{state['next_handoff_integrity_command']}
```
"""


def write() -> dict[str, Any]:
    state = build_state(utc_now())
    atomic_json(STATE_JSON, state)
    atomic_bytes(STATE_MD, render_markdown(state).encode())
    audit = {
        "audit_id": "MF_PSVR_STAGE_A_RESEARCH_STATE_AUDIT_V1",
        "created_at_utc": utc_now(),
        "status": "PASS",
        "state_sha256": sha256_file(STATE_JSON),
        "state_markdown_sha256": sha256_file(STATE_MD),
        "state_hash": state["state_hash"],
        "independent_review_sha256": sha256_file(INDEPENDENT_REVIEW),
        "candidate_incident_audit_sha256": sha256_file(CANDIDATE_INCIDENT),
        "final_report_sha256": sha256_file(FINAL_REPORT),
        "source_sha256": sha256_file(Path(__file__)),
        "heldout_opened": False,
        "v0_v1_executed": False,
    }
    audit["audit_hash"] = canonical_hash(audit)
    atomic_json(STATE_AUDIT, audit)
    return audit


def verify() -> dict[str, Any]:
    if not all(path.is_file() for path in (STATE_JSON, STATE_MD, STATE_AUDIT)):
        raise RuntimeError("Persistent research-state artifact set is incomplete")
    observed = load_json(STATE_JSON)
    if observed.get("state_hash") != canonical_hash({key: value for key, value in observed.items() if key != "state_hash"}):
        raise RuntimeError("Research state self-hash is invalid")
    expected = build_state(observed["created_at_utc"])
    if observed != expected:
        raise RuntimeError("Research state no longer recomputes from bound evidence")
    if STATE_MD.read_text(encoding="utf-8") != render_markdown(expected):
        raise RuntimeError("Research-state Markdown does not recompute")
    audit = load_json(STATE_AUDIT)
    if audit.get("audit_hash") != canonical_hash({key: value for key, value in audit.items() if key != "audit_hash"}):
        raise RuntimeError("Research-state audit self-hash is invalid")
    bindings = {
        "state_sha256": sha256_file(STATE_JSON),
        "state_markdown_sha256": sha256_file(STATE_MD),
        "state_hash": observed["state_hash"],
        "independent_review_sha256": sha256_file(INDEPENDENT_REVIEW),
        "candidate_incident_audit_sha256": sha256_file(CANDIDATE_INCIDENT),
        "final_report_sha256": sha256_file(FINAL_REPORT),
        "source_sha256": sha256_file(Path(__file__)),
    }
    if audit.get("status") != "PASS" or any(audit.get(key) != value for key, value in bindings.items()):
        raise RuntimeError("Research-state audit binding changed")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["write", "verify"])
    args = parser.parse_args()
    result = write() if args.stage == "write" else verify()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
