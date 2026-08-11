#!/usr/bin/env python3
"""Create the P0 materializer-validation gate artifacts without running inference.

This script intentionally stops before constructing a selector/materializer
matrix when the frozen V3 full-grid reference has not been released.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "p0_materializer_validation_v1"
V3 = ROOT / "outputs" / "accelerated_event_query_v1" / "oracle_protocol_v3_model_relative"
CONFIG = V3 / "k3_eventization" / "K3_UNIT_EVENT_CONFIG_V3.json"
EXECUTION = V3 / "full_grid_execution_staged_v5_atomic_idle_reservation" / "GLOBAL_EXECUTION_STATE.json"
PREREG = V3 / "full_grid_preregistration_staged_v7_review_corrections" / "FULL_GRID_PREREGISTRATION.json"


def command(*args: str) -> str:
    try:
        return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "UNKNOWN"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "MISSING"


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dirty = command("git", "status", "--short")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    manifest = {
        "schema_version": "P0_MATERIALIZER_VALIDATION_MANIFEST_V1",
        "timestamp_utc": now,
        "repo": str(ROOT),
        "branch": command("git", "branch", "--show-current"),
        "commit": command("git", "rev-parse", "HEAD"),
        "dirty_files": [] if not dirty or dirty == "UNKNOWN" else dirty.splitlines(),
        "dirty_worktree_risk": bool(dirty and dirty != "UNKNOWN"),
        "python_version": sys.version,
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "cuda_version": command("nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"),
        "torch_version": "NOT_QUERIED_NO_EXPERIMENT_RUN",
        "gpu": command("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"),
        "v3_k3_config_path": str(CONFIG.relative_to(ROOT)),
        "v3_k3_config_sha256": sha256(CONFIG),
        "v3_k3_config": config,
        "gate_result": "PAUSED_INPUT_REQUIRED",
        "gate_reason": "Formal V3 full-grid reference is not published; partial/fail-stop outputs cannot be used as a reference.",
    }
    (OUT / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    videos = [
        ("DALI", "data/realcam/dali.mp4", "realcam", "DALI", True),
        ("HANGZHOU", "data/realcam/hangzhou.mp4", "realcam", "HANGZHOU", True),
        ("WUHAN", "data/realcam/wuhan.mp4", "realcam", "WUHAN", True),
        ("GUANGZHOU", "data/realcam/guangzhou.mp4", "realcam", "GUANGZHOU", True),
        ("long_video_dataset3", "data/realcam/long_video_data/long_video_dataset3.mp4.source.json", "long_video_dataset3", "long_video_dataset3", True),
    ]
    inventory = []
    provenance = []
    for video_id, source_path, dataset, identity, independent in videos:
        exists = (ROOT / source_path).exists()
        is_v3 = video_id in {"DALI", "HANGZHOU", "WUHAN"}
        reason = (
            "V3 full-grid was fail-stop/incomplete; no formal unit_labels.parquet or K3 relation released"
            if is_v3 else "No frozen V3 candidate universe and model-relative oracle reference located"
        )
        inventory.append({
            "video_id": video_id, "source_path": source_path, "source_dataset": dataset,
            "duration_sec": "UNKNOWN_FROM_REPOSITORY", "fps": "UNKNOWN_FROM_REPOSITORY",
            "resolution": "UNKNOWN_FROM_REPOSITORY", "source_identity": identity,
            "independent_source": independent, "has_candidate_table": False,
            "has_oracle_reference": False, "has_human_reference": False,
            "has_model_relative_reference": False, "eligible_main_eval": False,
            "reason": reason + ("; source asset missing" if not exists else ""),
        })
        provenance.append({
            "video_id": video_id, "query_id": "V3_QUERY_NOT_RELEASED_FOR_MAIN_EVAL",
            "reference_source": "NOT_PUBLISHED" if is_v3 else "UNKNOWN_FROM_REPOSITORY",
            "human": False, "official_dataset": False, "VLM": False,
            "model_relative": False, "synthetic": False, "generation_model": "N/A",
            "generation_prompt": "N/A", "generated_at": "N/A",
            "was_used_for_threshold_tuning": "UNKNOWN_PROVENANCE",
            "was_used_for_selector_tuning": "UNKNOWN_PROVENANCE",
            "was_used_for_proxy_calibration": "UNKNOWN_PROVENANCE",
            "held_out": "UNKNOWN_PROVENANCE", "event_count": "UNKNOWN_FROM_REPOSITORY",
            "notes": reason,
        })
    write_csv(OUT / "VIDEO_INVENTORY.csv", list(inventory[0]), inventory)
    write_csv(OUT / "REFERENCE_PROVENANCE.csv", list(provenance[0]), provenance)

    protocol = {
        "schema_version": "P0_MATERIALIZER_VALIDATION_PROTOCOL_V1",
        "status": "NOT_EXECUTED_STOP_C_REFERENCE_UNAVAILABLE",
        "budget_semantics": "QUERY_BUDGET",
        "selectors": [],
        "materializers": {
            "K3": "src/garc_eval/accelerated_event_query/k3_unit_event_adapter.py::K3UnitEventAdapter",
            "K0": "NOT_DEFINED: prohibited until same-input V3 reference is released",
        },
        "v3_k3_config_sha256": sha256(CONFIG),
        "planned_independent_video_minimum": 3,
        "candidate_universe": "NOT_RELEASED",
        "oracle_outcomes": "NOT_RELEASED_AS_FORMAL_FULL_GRID",
        "reference": "NOT_RELEASED_AS_FORMAL_K3_RELATION",
        "matching_protocol": "NOT_FROZEN: must bind to released V3 finalizer/evaluator",
        "reason_not_frozen": "Freezing selectors, budgets, or K0 before authoritative reference release would create an unexecutable and potentially misleading protocol.",
        "evidence": {
            "latest_preregistration": str(PREREG.relative_to(ROOT)),
            "execution_state": str(EXECUTION.relative_to(ROOT)),
            "formal_reference_files_present": False,
        },
    }
    (OUT / "EXPERIMENT_PROTOCOL.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")

    paused = """# P0 Materializer Validation — Paused Input Required

## Decision

`MATERIALIZATION_MAINLINE_DECISION = PAUSED_INPUT_REQUIRED`

## Stop condition

`STOP-C`: the current V3-controlled matrix requires a frozen common candidate
universe, authoritative oracle outcomes, and a released model-relative K3
reference. The repository has three independent V3 source videos (DALI,
HANGZHOU, WUHAN) and their raw source assets, but not a valid released V3
reference for any of them.

The latest visible V3 full-grid execution state is preserved fail-stop evidence.
The V3 preregistration explicitly marks partial formal reference publication as
forbidden. This P0 run therefore must not derive labels or events from partial
raw output files.

## Available independent videos

- Raw independent V3 sources: 3 (`DALI`, `HANGZHOU`, `WUHAN`).
- Eligible controlled-main-evaluation videos: 0.
- Required minimum: 3 eligible controlled-main-evaluation videos.

## Missing requirement

Release or provide a completed, authenticated V3 full-grid package containing,
for the same frozen unit grid, `unit_labels`, a K3 model-relative event
relation/reference, candidate/proxy tables, and finalizer/provenance artifacts.
The package must cover at least DALI, HANGZHOU, and WUHAN and preserve the
frozen K3 config and matching rule.

## Minimum user action

Authorize/complete the already preregistered V3 full-grid reference release, or
provide an equivalent completed frozen V3 reference package. No new dataset,
manual relabeling, selector tuning, or algorithm change is required to resume.
"""
    (OUT / "PAUSED_INPUT_REQUIRED.md").write_text(paused)
    (OUT / "MAINLINE_DECISION.md").write_text("""# Materialization Mainline Decision

Decision:
PAUSED_INPUT_REQUIRED

Evidence level:
Pre-experiment input/provenance gate only; no controlled pairs were run.

Independent videos:
3 raw V3 sources; 0 eligible controlled evaluation sources.

Comparable selectors:
0 (not frozen before formal V3 reference release).

Controlled pairs:
0

Median Delta F1:
NOT_COMPUTED

Fraction K3 > K0:
NOT_COMPUTED

Main failure mode reduced:
NOT_EVALUATED

Main unresolved risk:
No released V3 full-grid unit labels / K3 reference; partial fail-stop output is prohibited as a formal reference.

Recommended next experiment:
After formal V3 reference release, run the preregistered 3-video same-trace K0-versus-K3 matrix.
""")
    (OUT / "FINAL_RESEARCH_REPORT.md").write_text("""# P0 Materializer Validation Report

# 1. Executive Decision

`MATERIALIZATION_MAINLINE_DECISION = PAUSED_INPUT_REQUIRED`.

The repository contains three independent V3 source videos, but no released
complete V3 model-relative reference package. Running a selector × materializer
matrix from partial fail-stop raw labels would violate the V3 publication policy
and could turn incomplete execution into pseudo-ground truth.

# 2. Experimental Contract

No quality experiment was run. `RUN_MANIFEST.json`, `VIDEO_INVENTORY.csv`,
`REFERENCE_PROVENANCE.csv`, and `EXPERIMENT_PROTOCOL.json` freeze the observed
repository state and the exact input gate. Budget semantics for the future
matrix are `QUERY_BUDGET`, not wall-clock deadline.

# 3. Controlled Matrix

Not executed: 0 valid controlled pairs. K0 was intentionally not implemented,
because no released V3 common trace/reference exists against which to enforce
same-trace identity.

# 4–9. Effects, Diagnostics, Generalization, Failure Cases

Not computed. The only finding is an input-evidence failure, not a negative
finding about K3.

# 10. Provenance / Leakage

`UNKNOWN_PROVENANCE` for a released main-evaluation reference because none was
found. The latest V3 protocol states that partial formal references are
forbidden; this report follows that constraint.

# 11. Historical Bridge

Not executed. Historical Stage-0 traces cannot establish the current V3
multi-video claim without a released V3 reference/evaluator binding.

# 12. Deadline Interpretation

No deadline experiment ran. The blocking condition is reference completeness,
not compute timing.

# 13. Paper Claim Allowed

No new materialization claim is supported by this P0 run.

# 14. Paper Claim NOT Allowed

Do not claim current-V3, cross-video, selector-robust materialization benefit.

# 15. Next Research Action

Complete or provide the frozen V3 full-grid reference package, then run the
same-trace K0/K3 controlled matrix without changing the protocol.
""")
    # Preserve the required matrix artifact schema even when STOP-C prevents
    # execution. Empty tables are intentionally not zero-result tables.
    write_csv(OUT / "controlled_pairs.csv", [
        "video_id", "query_id", "budget", "seed", "selector", "materializer",
        "trace_hash", "queried_units_hash", "oracle_outcomes_hash", "oracle_calls",
        "TP", "FP", "FN", "precision", "recall", "F1", "event_count",
        "valid_controlled_pair", "not_run_reason",
    ], [])
    write_csv(OUT / "event_metrics.csv", [
        "video_id", "query_id", "budget", "seed", "selector", "materializer",
        "TP", "FP", "FN", "precision", "recall", "F1", "not_run_reason",
    ], [])
    write_csv(OUT / "materializer_effects.csv", [
        "video_id", "query_id", "selector", "budget", "F1_K0", "F1_K3",
        "Delta_F1", "Recall_K0", "Recall_K3", "Delta_Recall", "FP_K0", "FP_K3",
        "overmerge_K0", "overmerge_K3", "not_run_reason",
    ], [])
    write_csv(OUT / "selector_effects.csv", [
        "video_id", "query_id", "budget", "materializer", "selector_left",
        "selector_right", "Delta_F1", "not_run_reason",
    ], [])
    write_csv(OUT / "failure_taxonomy.csv", [
        "video_id", "query_id", "selector", "budget", "materializer",
        "failure_type", "count", "rate", "example", "not_run_reason",
    ], [])
    write_csv(OUT / "trace_identity_checks.csv", [
        "video_id", "query_id", "budget", "seed", "selector", "K0_trace_hash",
        "K3_trace_hash", "queried_unit_ids_identical", "query_order_identical",
        "oracle_outcomes_identical", "oracle_call_count_identical",
        "valid_controlled_pair", "not_run_reason",
    ], [])
    write_csv(OUT / "per_video_summary.csv", [
        "video_id", "independent_source", "eligible_main_eval", "valid_pairs",
        "median_delta_f1", "k3_better_fraction", "not_run_reason",
    ], [])
    write_csv(OUT / "pooled_summary.csv", [
        "independent_videos", "comparable_selectors", "valid_pairs",
        "median_delta_f1", "k3_better_fraction", "decision", "not_run_reason",
    ], [])


if __name__ == "__main__":
    main()
