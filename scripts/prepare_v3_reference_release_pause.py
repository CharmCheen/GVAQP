#!/usr/bin/env python3
"""Produce an evidence-only V3 reference-release pause package.

This script performs no model inference and does not inspect downstream
selector/materializer metrics.  It records the sealed V7 reference protocol,
the prior V5 incomplete raw run, and the exact prerequisites that prevent a
formal release in the current environment.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/v3_reference_release_v1"
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
V7 = BASE / "full_grid_preregistration_staged_v7_review_corrections"
V5 = BASE / "full_grid_execution_staged_v5_atomic_idle_reservation"
VIDEOS = ROOT / "outputs/accelerated_event_query_v1/video_manifests/frozen_videos_v1.json"
EXEC_CONFIG = BASE / "configs/oracle_v3_execution_config.json"
PROMPT = BASE / "configs/query_prompt_v3_model_relative.txt"
K3 = BASE / "k3_eventization/K3_UNIT_EVENT_CONFIG_V3.json"
SCAN_STATUS = ROOT / "outputs/accelerated_event_query_v1/scan_candidates/STATUS.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def environment() -> dict:
    import cv2
    import numpy
    import PIL
    import torch
    import transformers

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "opencv": cv2.__version__,
        "pillow": PIL.__version__,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    videos = load(VIDEOS)["videos"]
    prereg = load(V7 / "FULL_GRID_PREREGISTRATION.json")
    approval = load(V7 / "FULL_GRID_COMPUTE_APPROVAL.json")
    v5_state = load(V5 / "GLOBAL_EXECUTION_STATE.json")
    execution = load(EXEC_CONFIG)
    k3 = load(K3)
    expected_env = load(V7 / "FULL_GRID_PROCESSED_INPUT_MANIFEST.json")["processor_environment"]
    observed_env = environment()
    runtime_match = observed_env == expected_env
    source_commit = prereg["bindings"]["source_bindings"]["sha256"]
    protocol = {
        "status": "RECOVERED_BUT_NOT_EXECUTABLE_IN_CURRENT_RUNTIME",
        "experiment_id": prereg["experiment_id"],
        "query_id": execution["query_id"],
        "query_semantics_zh": execution["query_semantics_zh"],
        "unitization": prereg["workload"],
        "model": {
            "path": execution["model_path"],
            "content_hash": execution["model_content_hash"],
            "host_execution": execution["host_execution"],
            "processor": execution["processor"],
        },
        "decoding": prereg["decoding"],
        "failure_semantics": prereg["authoritative_schema"],
        "reference_relation_semantics": prereg["coverage_policy"]["primary_relation"],
        "protocol_bindings": {
            "preregistration_hash": sha256(V7 / "FULL_GRID_PREREGISTRATION.json"),
            "execution_seal_hash": sha256(V7 / "FULL_GRID_EXECUTION_SEAL.json"),
            "execution_config_hash": sha256(EXEC_CONFIG),
            "prompt_hash": sha256(PROMPT),
            "unitization_hash": prereg["bindings"]["unit_grid"]["sha256"],
            "parser_hash": prereg["bindings"]["parser"]["sha256"],
            "k3_config_hash": sha256(K3),
            "query_definition_hash": sha256(PROMPT),
            "source_bindings_hash": source_commit,
        },
        "expected_processor_environment": expected_env,
        "observed_processor_environment": observed_env,
        "processor_environment_match": runtime_match,
        "fresh_execution_root": approval["fresh_execution_root"],
        "prior_labels_reuse": "FORBIDDEN_BY_V7",
    }
    write_json(OUT / "FROZEN_REFERENCE_PROTOCOL.json", protocol)

    state_rows = []
    completeness = []
    summary = []
    for video in videos:
        vid = video["video_id"]
        total = int(video["expected_units"])
        prior_completed = sum(1 for unit in v5_state.get("completed_unit_ids", []) if unit.startswith(vid + "_"))
        # V7 expressly forbids promotion/reuse of V5 records, so formal cells are zero.
        row = {
            "video_id": vid,
            "source_path": video["path"],
            "source_hash": video["sha256"],
            "total_units": total,
            "completed_units": 0,
            "missing_units": total,
            "parse_failure_units": 0,
            "failed_units": 0,
            "candidate_table_exists": False,
            "proxy_table_exists": False,
            "k3_relation_exists": False,
            "finalizer_exists": False,
            "provenance_exists": False,
            "current_status": "MISSING_REQUIRED_INPUT",
            "prior_v5_raw_completed_units_nonreusable": prior_completed,
            "blocking_reason": "V7 fresh execution requires frozen processor environment; current environment mismatch; V3 scan/proxy candidates remain NOT_RUN",
        }
        state_rows.append(row)
        completeness.append({
            "video_id": vid, "expected_units": total, "relevant": 0,
            "not_relevant": 0, "unknown": 0, "parse_failure": 0,
            "unaccounted_units": total, "completeness_pass": False,
            "reason": "No formal V7 terminal outcomes exist; V5 raw outcomes are nonreusable by frozen V7 policy.",
        })
        manifest = {
            "status": "NOT_RELEASED",
            "video_id": vid,
            "source_path": video["path"],
            "video_sha256": video["sha256"],
            "query_id": execution["query_id"],
            "frozen_protocol_hash": sha256(OUT / "FROZEN_REFERENCE_PROTOCOL.json"),
            "source_commit": git("rev-parse", "HEAD"),
            "dirty_worktree": git("status", "--porcelain").splitlines(),
            "reused_units": 0,
            "newly_inferred_units": 0,
            "invalidated_units": prior_completed,
            "prior_v5_raw_units_nonreusable": prior_completed,
            "formal_completeness_status": "FAIL",
            "release_gates": {
                "G1_source_identity_frozen": True,
                "G2_protocol_recovered": True,
                "G3_complete_authoritative_unit_outcomes": False,
                "G4_no_silent_missing_units": False,
                "G5_frozen_unit_table": False,
                "G6_deterministic_k3_reference_relation": False,
                "G7_candidate_table_available": False,
                "G8_proxy_table_available": False,
                "G9_selector_visibility_audit_passed": False,
                "G10_provenance_manifest_complete": False,
                "G11_deterministic_rebuild_passed": False,
                "G12_no_downstream_performance_informed_edits": True,
            },
            "blockers": [
                "Frozen processor runtime environment differs from current runtime.",
                "No formal V7 full-grid terminal outcomes exist.",
                "V3 scan candidate/proxy execution is frozen pending and has no released tables.",
            ],
        }
        write_json(OUT / f"{vid}_REFERENCE_MANIFEST.json", manifest)
        summary.append({
            "video_id": vid, "total_units": total, "reused_units": 0,
            "new_units": 0, "invalid_units": prior_completed, "missing_units": total,
            "relevant_units": 0, "not_relevant_units": 0, "parse_failure_units": 0,
            "event_count": 0, "candidate_rows": 0, "proxy_rows": 0,
            "completeness_pass": False, "determinism_pass": False,
            "visibility_pass": False, "provenance_pass": False,
            "release_status": "NOT_RELEASED",
        })
    write_csv(OUT / "REFERENCE_STATE_AUDIT.csv", state_rows, list(state_rows[0]))
    write_csv(OUT / "COMPLETENESS_AUDIT.csv", completeness, list(completeness[0]))
    visibility = []
    for vid in (row["video_id"] for row in state_rows):
        visibility.append({
            "video_id": vid, "candidate_feature": "candidate/proxy table",
            "source": "outputs/accelerated_event_query_v1/scan_candidates/STATUS.md",
            "available_before_oracle": "UNKNOWN_FROM_REPOSITORY",
            "uses_GT": "UNKNOWN_FROM_REPOSITORY", "uses_future_outcome": "UNKNOWN_FROM_REPOSITORY",
            "allowed": False, "status": "NOT_SELECTOR_VISIBLE",
            "reason": "No V3 candidate or proxy table exists; STATUS is FROZEN_SCAN_EXECUTION_PENDING.",
        })
    write_csv(OUT / "SELECTOR_VISIBILITY_AUDIT.csv", visibility, list(visibility[0]))
    write_csv(OUT / "REFERENCE_RELEASE_SUMMARY.csv", summary, list(summary[0]))

    report = f"""# V3 Full-Grid Reference Release Report

## Decision

`PAUSED_INPUT_REQUIRED`.

## What was already present?

The three preregistered independent sources are frozen: DALI (567 units), HANGZHOU (561), and WUHAN (347).  The V7 full-grid protocol, Qwen3-VL-32B checkpoint binding, prompt, unit grid, parser, K3 configuration, unit/frame/processed-input manifests, sealed staged launcher, and user compute approval are present.

The prior V5 run retained {len(v5_state.get('completed_unit_ids', []))} raw completed records, but it fail-stopped after {len(v5_state.get('attempted_unit_ids', []))} attempted units.  V7 explicitly declares those labels nonreusable and requires a fresh execution from ordinal zero.

## What was incomplete?

No V7 fresh execution root, formal unit-label table, authenticated full-grid manifest, K3 reference relation, finalizer release, V3 candidate table, or V3 proxy table exists.  `scan_candidates/STATUS.md` is `NOT_RUN — FROZEN_SCAN_EXECUTION_PENDING`.

## What was reused?

No semantic labels were reused: `REUSED_UNITS = 0`, as required by the V7 preregistration.  Prior V5 raw records remain evidence only and were not promoted to reference labels.

## What required new inference?

The sealed V7 workload requires 1,475 fresh oracle calls.  It cannot be started in this checkout because the frozen processor environment does not match: expected `{expected_env}`, observed `{observed_env}`.  This is a pre-inference fail-closed validation error, not a semantic result.

## Is reference construction frozen?

The recovered protocol and binding hashes are in `FROZEN_REFERENCE_PROTOCOL.json`; it is recovered but not executable in the present runtime.  No reference labels or K3 relation were created, so no evaluation substrate has been frozen.

## Leakage / circularity risk

No downstream F1, selector ranking, K0/K3 comparison, or materializer failure case was inspected or used.  The future reference relation is model-relative and uses K3 solely as the frozen evaluator-side reference relation; method-side K3 outputs must remain separately named.  Candidate/proxy visibility cannot pass because their tables do not exist.

## Independent sources

DALI, HANGZHOU, and WUHAN are distinct frozen source videos under the V7 manifest.  Their source identity is available, but none is released for controlled evaluation.

## Can P0 materializer validation now legally run?

`NO`.  It lacks complete formal model-relative labels/reference relations and a frozen common V3 candidate/proxy universe.

## Minimum required action

Restore the exact frozen processor runtime identity (Python is already compatible; install/use the bound `transformers==5.9.0`, `opencv==4.13.0`, and `numpy==2.4.6` environment without changing the sealed source/model/prompt), then execute the already approved V7 full grid.  Separately provide or authorize the already-pending frozen V3 scan/proxy candidate execution and its preregistered configuration; no selector experiment may start before both substrates release.
"""
    (OUT / "REFERENCE_RELEASE_REPORT.md").write_text(report, encoding="utf-8")
    decision = {
        "decision": "PAUSED_INPUT_REQUIRED",
        "DALI": "NOT_RELEASED", "HANGZHOU": "NOT_RELEASED", "WUHAN": "NOT_RELEASED",
        "eligible_independent_videos": "0 / 3",
        "frozen_protocol_hash": sha256(OUT / "FROZEN_REFERENCE_PROTOCOL.json"),
        "reference_leakage_status": "NO_DOWNSTREAM_PERFORMANCE_INSPECTION; CANDIDATE_VISIBILITY_UNAVAILABLE",
        "outstanding_blocker": "Frozen processor environment mismatch; V3 scan/proxy candidate tables are not released.",
        "P0_materializer_validation_authorized": "NO",
    }
    write_json(OUT / "REFERENCE_RELEASE_DECISION.json", decision)
    (OUT / "REFERENCE_RELEASE_DECISION.md").write_text(
        "# V3 Reference Release Decision\n\n"
        "Decision:\nPAUSED_INPUT_REQUIRED\n\n"
        "DALI:\nNOT_RELEASED\n\nHANGZHOU:\nNOT_RELEASED\n\nWUHAN:\nNOT_RELEASED\n\n"
        "Eligible independent videos:\n0 / 3\n\n"
        f"Frozen protocol hash:\n{decision['frozen_protocol_hash']}\n\n"
        "Reference leakage status:\nNO_DOWNSTREAM_PERFORMANCE_INSPECTION; CANDIDATE_VISIBILITY_UNAVAILABLE\n\n"
        "Outstanding blocker:\nFrozen processor environment mismatch; V3 scan/proxy candidate tables are not released.\n\n"
        "P0 materializer validation authorized:\nNO\n",
        encoding="utf-8",
    )
    (OUT / "PAUSED_INPUT_REQUIRED.md").write_text(
        "# V3 Reference Release Paused\n\n"
        "## Exact blocker\n\n"
        "The sealed V7 worker rejects the current processor environment before "
        "inference: the frozen `transformers`, OpenCV, and NumPy identities do "
        "not match.  In addition, V3 selector-facing scan candidate/proxy tables "
        "have not been executed or released.\n\n"
        "## Why it matters\n\n"
        "Using a substituted runtime would change frozen reference semantics; "
        "using V5 partial raw labels would violate V7's explicit fresh-execution "
        "and non-reuse policy.  Without candidate/proxy tables P0 cannot form a "
        "common selector-visible universe.\n\n"
        "## Minimum user action\n\n"
        "Make the exact frozen processor runtime available, then authorize/use "
        "the already preregistered frozen V3 scan/proxy execution configuration. "
        "No model, prompt, unitization, parser, or K3 configuration change is "
        "required or authorized by this package.\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
