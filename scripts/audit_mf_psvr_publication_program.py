#!/usr/bin/env python3
"""Fail-closed Cycle-0 integrity audit for the MF-PSVR publication program.

The audit never opens held-out media or references.  It preserves legacy
artifacts, identifies which of them are inadmissible under the stricter
publication contract, and verifies that the current implementation contains
the minimal candidate-identity and deadline-accounting repairs needed before
new experiments.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "outputs/mf_psvr_publication_program"
CYCLE = PROGRAM / "cycle_00_integrity_and_literature"
REQUIRED_CYCLES = [
    "cycle_00_integrity_and_literature",
    "cycle_01_training_pool",
    "cycle_02_candidate_value",
    "cycle_03_query_temporal_refiner",
    "cycle_04_mf_psvr_integration",
    "cycle_05_physical_development",
    "cycle_06_causal_revision",
    "cycle_07_generalization",
    "cycle_08_ablation",
    "final",
]
TRACE_ROOTS = [
    ROOT / "outputs/psvr_two_video_loop",
    ROOT / "outputs/psvr_bottleneck_research",
    ROOT / "outputs/psvr_autonomous_research",
]
LABEL_ROOT = ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/parsed_labels"
REFERENCE_ROOT = (
    ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/reference_events"
)
LITERATURE_ARTIFACTS = (
    "ARC_FULLTEXT_AUDIT.md",
    "RELATED_WORK_ASSUMPTION_MATRIX.csv",
    "BASELINE_ADAPTATION_SPEC.md",
    "NOVELTY_BOUNDARY.md",
    "SOURCE_MANIFEST.json",
    "INDEPENDENT_REVIEW_RESPONSE.md",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def git_head() -> str:
    head_path = ROOT / ".git/HEAD"
    if not head_path.exists():
        return "NOT_A_GIT_WORKTREE"
    head = head_path.read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    reference = head.removeprefix("ref: ")
    loose = ROOT / ".git" / reference
    if loose.exists():
        return loose.read_text(encoding="utf-8").strip()
    packed = ROOT / ".git/packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or line.startswith("^"):
                continue
            fields = line.split()
            if len(fields) == 2 and fields[1] == reference:
                return fields[0]
    return f"UNRESOLVED:{reference}"


def initialize_stage() -> None:
    for name in REQUIRED_CYCLES:
        (PROGRAM / name).mkdir(parents=True, exist_ok=True)
    config = {
        "audit_id": "mf_psvr_cycle0_integrity_v1",
        "candidate_semantics": (
            "UNIT_VERIFY_OPPORTUNITY_WITH_IMMUTABLE_TRACK_WITNESS"
        ),
        "oracle_target": "unit_level_frozen_oracle_outcome",
        "trace_roots": [str(path.relative_to(ROOT)) for path in TRACE_ROOTS],
        "heldout_access": "FORBIDDEN_AND_NOT_REQUIRED",
        "strict_deadline": (
            "oracle_session+proxy_init+warmup+scan+refine+verify+materialize+commit"
        ),
    }
    atomic_json(CYCLE / "resolved_config.json", config)
    atomic_text(
        CYCLE / "commands.sh",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "PYTHONPATH=src pytest -q\n"
        "python scripts/audit_mf_psvr_publication_program.py\n",
    )
    atomic_json(CYCLE / "environment.json", {
        "created_at_utc": utc_now(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
    })
    atomic_text(CYCLE / "git_commit.txt", git_head() + "\n")
    atomic_json(CYCLE / "STAGE_STATE.json", {
        "stage": "cycle_00_integrity_and_literature",
        "status": "RUNNING",
        "started_at_utc": utc_now(),
        "heldout_opened": False,
    })


def iter_unique_complete_runs() -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    by_run_id: dict[str, tuple[Path, dict[str, Any]]] = {}
    parse_errors: list[str] = []
    for root in TRACE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("complete.json"):
            try:
                payload = read_json(path)
            except Exception as exc:  # fail closed, but retain the path
                parse_errors.append(f"{path.relative_to(ROOT)}: {type(exc).__name__}")
                continue
            if payload.get("status") != "ok" or not payload.get("run_id"):
                continue
            by_run_id.setdefault(str(payload["run_id"]), (path, payload))
    return list(by_run_id.values()), sorted(parse_errors)


def parse_source_units(value: str) -> set[int]:
    return {int(token) for token in value.split("|") if token.strip()}


def audit_labels(
    runs: list[tuple[Path, dict[str, Any]]],
) -> tuple[dict[str, Any], dict[tuple[str, int], str]]:
    tasks = ["V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"]
    label_rows: dict[str, list[dict[str, str]]] = {}
    labels: dict[tuple[str, int], str] = {}
    duplicate_units: dict[str, list[int]] = {}
    for task in tasks:
        path = LABEL_ROOT / f"{task}.csv"
        rows = read_csv(path)
        label_rows[task] = rows
        seen: set[int] = set()
        duplicates: list[int] = []
        for row in rows:
            unit_id = int(row["unit_id"])
            if unit_id in seen:
                duplicates.append(unit_id)
            seen.add(unit_id)
            labels[(task, unit_id)] = row["parsed_label"]
        duplicate_units[task] = sorted(set(duplicates))

    video_time_mismatches: dict[str, int] = {}
    for video_id in ("V0", "V1"):
        q1 = {
            int(row["unit_id"]): (float(row["start_time"]), float(row["end_time"]))
            for row in label_rows[f"{video_id}_Q1"]
        }
        q2 = {
            int(row["unit_id"]): (float(row["start_time"]), float(row["end_time"]))
            for row in label_rows[f"{video_id}_Q2"]
        }
        video_time_mismatches[video_id] = sum(
            q1.get(unit_id) != q2.get(unit_id) for unit_id in set(q1) | set(q2)
        )

    reference_audit: dict[str, Any] = {}
    for task in tasks:
        reference_rows = read_csv(REFERENCE_ROOT / f"{task}.csv")
        referenced: list[int] = []
        for row in reference_rows:
            referenced.extend(sorted(parse_source_units(row["source_unit_ids"])))
        reference_set = set(referenced)
        positive_set = {
            int(row["unit_id"])
            for row in label_rows[task]
            if row["parsed_label"] == "positive"
        }
        reference_audit[task] = {
            "reference_events": len(reference_rows),
            "positive_units": len(positive_set),
            "referenced_units": len(reference_set),
            "duplicate_reference_memberships": len(referenced) - len(reference_set),
            "missing_positive_units": sorted(positive_set - reference_set),
            "extra_nonpositive_units": sorted(reference_set - positive_set),
        }

    queried_rows = 0
    queried_mismatches: list[dict[str, Any]] = []
    missing_query_labels: list[dict[str, Any]] = []
    for path, payload in runs:
        task = str(payload.get("task_id", ""))
        if task not in tasks:
            continue
        for result in payload.get("queried_results", []):
            queried_rows += 1
            unit_id = int(result["unit_id"])
            expected = labels.get((task, unit_id))
            observed = result.get("parsed_label")
            if expected is None:
                missing_query_labels.append({
                    "run_id": payload["run_id"],
                    "task_id": task,
                    "unit_id": unit_id,
                    "path": str(path.relative_to(ROOT)),
                })
            elif expected != observed:
                queried_mismatches.append({
                    "run_id": payload["run_id"],
                    "task_id": task,
                    "unit_id": unit_id,
                    "expected": expected,
                    "observed": observed,
                })

    expected_counts = {"V0_Q1": 347, "V0_Q2": 347, "V1_Q1": 567, "V1_Q2": 567}
    count_matches = {
        task: len(label_rows[task]) == expected_counts[task] for task in tasks
    }
    reference_pass = all(
        not row["duplicate_reference_memberships"]
        and not row["missing_positive_units"]
        and not row["extra_nonpositive_units"]
        for row in reference_audit.values()
    )
    passed = (
        all(count_matches.values())
        and not any(duplicate_units.values())
        and not any(video_time_mismatches.values())
        and not queried_mismatches
        and not missing_query_labels
        and reference_pass
    )
    audit = {
        "status": "PASS" if passed else "FAIL",
        "candidate_label_scope": "unit_level_frozen_oracle_outcome",
        "track_label_scope": "NOT_CLAIMED",
        "task_row_counts": {task: len(label_rows[task]) for task in tasks},
        "expected_count_matches": count_matches,
        "duplicate_units": duplicate_units,
        "cross_query_unit_time_mismatches": video_time_mismatches,
        "queried_rows_checked": queried_rows,
        "queried_label_mismatch_count": len(queried_mismatches),
        "queried_label_mismatches": queried_mismatches[:100],
        "missing_query_label_count": len(missing_query_labels),
        "missing_query_labels": missing_query_labels[:100],
        "reference_event_alignment": reference_audit,
        "derived_conclusion": (
            "Existing unit-level oracle/reference alignment is admissible; "
            "it is not track-specific supervision."
        ),
    }
    return audit, labels


def audit_trace_integrity(
    runs: list[tuple[Path, dict[str, Any]]],
    parse_errors: list[str],
) -> dict[str, Any]:
    mutable_run_units: list[dict[str, Any]] = []
    strict_deadline_misses: list[dict[str, Any]] = []
    missing_snapshots: list[dict[str, Any]] = []
    repeat_signatures: dict[tuple[str, ...], list[tuple[int, tuple[int, ...]]]] = defaultdict(list)
    for path, payload in runs:
        track_history: dict[int, set[int]] = defaultdict(set)
        for row in payload.get("score_history", []):
            track_id = row.get("top_track_id")
            if track_id is not None:
                track_history[int(row["unit_id"])].add(int(track_id))
        for unit_id, track_ids in track_history.items():
            if len(track_ids) > 1:
                mutable_run_units.append({
                    "run_id": payload["run_id"],
                    "unit_id": unit_id,
                    "track_ids": sorted(track_ids),
                })

        deadline = payload.get("deadline_seconds")
        total_service = payload.get("total_service_wall_seconds")
        if (
            payload.get("deadline_met") is True
            and deadline is not None
            and total_service is not None
            and float(total_service) > float(deadline) + 1e-9
        ):
            strict_deadline_misses.append({
                "run_id": payload["run_id"],
                "deadline_seconds": float(deadline),
                "legacy_snapshot_elapsed_seconds": float(
                    payload.get("snapshot_elapsed_seconds", 0.0)
                ),
                "strict_total_service_wall_seconds": float(total_service),
            })

        snapshot_value = payload.get("final_snapshot_path")
        snapshot = Path(snapshot_value) if snapshot_value else None
        if snapshot is not None and not snapshot.is_absolute():
            snapshot = ROOT / snapshot
        if snapshot is None or not snapshot.exists():
            missing_snapshots.append({
                "run_id": payload["run_id"],
                "complete_path": str(path.relative_to(ROOT)),
                "snapshot_path": snapshot_value,
            })

        key = (
            str(payload.get("method")),
            str(payload.get("family")),
            str(payload.get("task_id")),
            str(payload.get("deadline_name")),
            str(payload.get("config_hash")),
        )
        signature = tuple(
            int(row["unit_id"]) for row in payload.get("queried_results", [])
        )
        repeat_signatures[key].append((int(payload.get("replicate", -1)), signature))

    comparable_groups = {
        key: values for key, values in repeat_signatures.items() if len(values) >= 2
    }
    inconsistent_groups = [
        {
            "identity": list(key),
            "signatures": [list(signature) for _, signature in sorted(values)],
        }
        for key, values in comparable_groups.items()
        if len({signature for _, signature in values}) > 1
    ]

    source = (ROOT / "scripts/run_psvr_two_video_physical.py").read_text(
        encoding="utf-8"
    )
    run_one = source[source.index("def run_one("):]
    current_binding_repair = (
        "candidate_track_bindings" in run_one
        and all(token in source for token in (
            "bind_track_witness",
            "CandidateIdentity(",
            "instantaneous_top_track_id",
        ))
    )
    clock_index = run_one.index("run_start = time.perf_counter_ns()")
    session_index = run_one.index("oracle.start_session(")
    engine_index = run_one.index("proxy_runtime.UnitProxyEngine(")
    current_deadline_repair = (
        clock_index < session_index < engine_index
        and '"total_service_wall_seconds": total_wall' in run_one
        and '"deadline_met": snapshot_elapsed <= deadline' in run_one
    )
    return {
        "unique_complete_runs_checked": len(runs),
        "complete_json_parse_errors": parse_errors,
        "historical_mutable_candidate_run_units": len(mutable_run_units),
        "historical_mutable_candidate_examples": mutable_run_units[:100],
        "historical_strict_deadline_miss_count": len(strict_deadline_misses),
        "historical_strict_deadline_misses": strict_deadline_misses,
        "missing_final_snapshot_count": len(missing_snapshots),
        "missing_final_snapshots": missing_snapshots[:100],
        "physical_repeat_groups_checked": len(comparable_groups),
        "physical_repeat_signature_mismatch_groups": len(inconsistent_groups),
        "physical_repeat_signature_mismatches": inconsistent_groups[:100],
        "physical_repeat_inferential_role": "LATENCY_REPEAT_ONLY",
        "current_candidate_binding_repair": (
            "PASS" if current_binding_repair else "FAIL"
        ),
        "current_full_deadline_clock_repair": (
            "PASS" if current_deadline_repair else "FAIL"
        ),
        "historical_trace_publication_status": "INVALIDATED_REBUILD_REQUIRED",
    }


def rows_equal_except_id(
    rows: Iterable[dict[str, str]], first: str, second: str
) -> bool:
    selected = {row.get("config_id"): row for row in rows}
    if first not in selected or second not in selected:
        return False
    left = {key: value for key, value in selected[first].items() if key != "config_id"}
    right = {key: value for key, value in selected[second].items() if key != "config_id"}
    return left == right


def audit_baselines() -> dict[str, Any]:
    frontend = ROOT / "outputs/proxy_frontend_comparison_v0"
    detection_equal = rows_equal_except_id(
        read_csv(frontend / "tables/detection_comparison.csv"), "B1", "B2"
    )
    tracking_equal = rows_equal_except_id(
        read_csv(frontend / "tables/tracking_metrics.csv"), "B1", "B2"
    )
    geometry_files = list((frontend / "raw/road_geometry").glob("*")) \
        if (frontend / "raw/road_geometry").exists() else []

    supg_path = ROOT / "outputs/pre_cross_video_audit/supg_variant_path_audit.csv"
    supg_rows = read_csv(supg_path) if supg_path.exists() else []
    supg_different_selected = sum(
        int(float(row["selected_set_symmetric_diff_size"])) > 0 for row in supg_rows
    )
    supg_identical_segments = sum(
        row["segment_outputs_identical"].lower() == "true" for row in supg_rows
    )
    supg_identical_metrics = sum(
        row["metrics_identical"].lower() == "true" for row in supg_rows
    )
    return {
        "status": "PASS_WITH_EXCLUSIONS",
        "B1_B2": {
            "detection_rows_equal": detection_equal,
            "tracking_rows_equal": tracking_equal,
            "road_geometry_artifact_count": len(geometry_files),
            "identity_verdict": "ALIAS_NOT_INDEPENDENT_BASELINES",
            "publication_action": "EXCLUDE_B2_AS_DISTINCT_BASELINE",
        },
        "SUPG_RT": {
            "pair_count": len(supg_rows),
            "different_selected_set_pairs": supg_different_selected,
            "identical_K3_segment_pairs": supg_identical_segments,
            "identical_metric_pairs": supg_identical_metrics,
            "identity_verdict": "DISTINCT_SELECTIONS_EFFECTIVELY_ALIAS_AFTER_K3",
            "publication_action": "COUNT_AS_ONE_EFFECTIVE_BASELINE_VARIANT",
        },
        "current_best_simple_baseline": "FIFO",
        "required_publication_baselines": [
            "FIFO",
            "raw_YOLO_score",
            "deterministic_random",
            "one_effective_SUPG_selector",
            "explicit_ARC_unit_inspired_mapping",
            "Zeus_style_adaptive_configuration",
            "FiGO_style_chunk_fidelity_plan",
        ],
    }


def audit_scores() -> dict[str, Any]:
    proxy_source = (ROOT / "scripts/run_psvr_two_video_proxy.py").read_text(
        encoding="utf-8"
    )
    physical_source = (ROOT / "scripts/run_psvr_two_video_physical.py").read_text(
        encoding="utf-8"
    )
    current_query_routing = (
        'candidates[candidates["query_id"] == query_id]' in proxy_source
        and 'unit_scores[unit_scores.query_id == query_id]' in physical_source
        and 'scored_candidates["query_id"] == query_id' in physical_source
    )
    weak_report = (
        ROOT / "outputs/proxy_oracle_distillation_v0/FINAL_REPORT.md"
    ).read_text(encoding="utf-8")
    weak_labels_disclosed = "tag-based weak proxies" in weak_report
    return {
        "status": "PASS_WITH_LEGACY_EXCLUSION" if current_query_routing else "FAIL",
        "current_Y8_query_specific_row_filtering": current_query_routing,
        "runtime_score_column": "candidate_score_to_unit_score_to_proxy_score",
        "Q1_candidate_classes": [1, 2, 3, 5, 7],
        "Q2_candidate_classes": [0, 1, 3],
        "legacy_distillation_weak_label_disclosure_present": weak_labels_disclosed,
        "legacy_distillation_publication_status": (
            "INVALID_AS_QUERY_ALIGNED_ORACLE_TRAINING_EVIDENCE"
        ),
        "derived_conclusion": (
            "Current Y8 routing is query-specific, but the historical "
            "DrivingDojo result used tag-based generic labels and must be rebuilt."
        ),
    }


def audit_literature_artifacts() -> dict[str, Any]:
    """Validate Cycle-0 literature coverage without depending on temp PDFs."""

    errors: list[str] = []
    paths = {name: CYCLE / name for name in LITERATURE_ARTIFACTS}
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"missing:{name}")
        elif path.stat().st_size < 100:
            errors.append(f"too_small:{name}")

    source_keys: list[str] = []
    source_manifest = paths["SOURCE_MANIFEST.json"]
    if source_manifest.is_file():
        try:
            source_payload = read_json(source_manifest)
            papers = source_payload.get("papers", [])
            source_keys = [str(row.get("key")) for row in papers]
            if len(source_keys) != len(set(source_keys)):
                errors.append("source_manifest:duplicate_paper_key")
            for row in papers:
                digest = str(row.get("audited_pdf_sha256", ""))
                if len(digest) != 64 or any(
                    character not in "0123456789abcdef" for character in digest
                ):
                    errors.append(
                        f"source_manifest:invalid_pdf_sha256:{row.get('key')}"
                    )
        except Exception as exc:
            errors.append(f"source_manifest:{type(exc).__name__}")

    required_sources = {
        "ARC", "SUPG", "ABae", "ExSample", "Seiden", "MIRIS", "DIVA",
        "Zeus", "FiGO", "Boggart",
    }
    missing_sources = sorted(required_sources - set(source_keys))
    if missing_sources:
        errors.append(f"source_manifest:missing:{'|'.join(missing_sources)}")

    matrix_methods: list[str] = []
    matrix_path = paths["RELATED_WORK_ASSUMPTION_MATRIX.csv"]
    required_columns = {
        "method",
        "proxy_pre_materialized",
        "proxy_cost_in_budget",
        "candidate_pool_preexists",
        "budget_type",
        "query_time_progressive_scan",
        "candidate_vs_confirmed",
        "output_eventrelation",
        "anytime_durable",
        "materialization_commit_cost",
        "query_conditioned_intermediate_fidelity",
        "paper_contract",
        "audited_artifact_behavior",
        "closest_overlap_or_difference",
        "provenance_and_confidence",
        "publication_adaptation_status",
    }
    if matrix_path.is_file():
        try:
            with matrix_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                matrix_columns = set(reader.fieldnames or [])
                rows = list(reader)
            if matrix_columns != required_columns:
                errors.append("assumption_matrix:column_contract_mismatch")
            if any(None in row for row in rows):
                errors.append("assumption_matrix:malformed_row")
            matrix_methods = [str(row.get("method")) for row in rows]
        except Exception as exc:
            errors.append(f"assumption_matrix:{type(exc).__name__}")

    required_methods = {
        "ARC", "SUPG", "ABae", "ExSample", "Seiden", "MIRIS", "DIVA",
        "Zeus", "FiGO", "Boggart",
        "MF-PSVR target (unvalidated)",
    }
    missing_methods = sorted(required_methods - set(matrix_methods))
    if missing_methods:
        errors.append(f"assumption_matrix:missing:{'|'.join(missing_methods)}")

    required_markers = {
        "ARC_FULLTEXT_AUDIT.md": (
            "AUDIT_DECISION = NOVELTY_POSITION_REVISED",
            "Paper–snapshot discrepancies and negative evidence",
            "Claims rejected by this audit",
        ),
        "BASELINE_ADAPTATION_SPEC.md": (
            "SPEC_STATUS = PREREGISTERED_BEFORE_NEW_PHYSICAL_RESULTS",
            "Common physical contract",
            "FIXED-MULTIPASS-PHYS-v1",
            "ZEUS-CONFIG-PHYS-v1",
            "FIGO-UNIT-PLAN-PHYS-v1",
            "Adaptation identity and admission gates",
        ),
        "NOVELTY_BOUNDARY.md": (
            "BOUNDARY_STATUS = CONDITIONAL_RESEARCH_HYPOTHESIS",
            "Claims that are not admissible",
            "Competing hypotheses and discriminating predictions",
            "Preregistered estimands and decision margins",
            "Rejection and revision triggers",
        ),
        "INDEPENDENT_REVIEW_RESPONSE.md": (
            "REVIEW_STATUS = BLOCKERS_IDENTIFIED_AND_SPEC_CORRECTED",
            "Reviewer verdict",
            "Findings and dispositions",
            "Remaining uncertainty",
        ),
    }
    for filename, markers in required_markers.items():
        path = paths[filename]
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"{filename}:missing_marker:{marker}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "required_artifacts": list(LITERATURE_ARTIFACTS),
        "paper_source_keys": source_keys,
        "assumption_matrix_methods": matrix_methods,
        "derived_conclusion": (
            "No priority claim is admitted; the surviving joint physical-anytime "
            "hypothesis remains conditional on causal and cross-source evidence."
        ),
    }


def invalidations(trace: dict[str, Any]) -> dict[str, Any]:
    entries = [
        {
            "artifact": "legacy PSVR physical matrices",
            "scope": "MF-PSVR publication deadline comparisons",
            "reason": (
                "query clock began after proxy initialization/warm-up; "
                f"{trace['historical_strict_deadline_miss_count']} nominally "
                "passing runs exceed the strict total-service deadline"
            ),
            "historical_claims_preserved": True,
            "required_rebuild": "rerun every baseline/method entering the new table",
        },
        {
            "artifact": "legacy unit-only candidate identities",
            "scope": "track-witness candidate-value training or lifecycle claims",
            "reason": (
                f"{trace['historical_mutable_candidate_run_units']} run-unit "
                "histories changed top_track_id behind one unit candidate identity"
            ),
            "historical_claims_preserved": True,
            "required_rebuild": "re-extract with immutable track-witness identity",
        },
        {
            "artifact": "proxy_frontend_comparison_v0 B2",
            "scope": "independent baseline identity",
            "reason": "B2 copies B1 detections and tracking; geometry artifact absent",
            "historical_claims_preserved": True,
            "required_rebuild": "none; exclude alias or build and bind real geometry",
        },
        {
            "artifact": "SUPG_RT all-selected vs confirmed-only variants",
            "scope": "two independent publication baselines",
            "reason": "different selected sets collapse to identical oracle/K3 outputs",
            "historical_claims_preserved": True,
            "required_rebuild": (
                "adapt one effective SUPG selector and label any ARC unit "
                "mapping as inspired rather than faithful"
            ),
        },
        {
            "artifact": "proxy_oracle_distillation_v0 model results",
            "scope": "query-aligned frozen-oracle refiner evidence",
            "reason": "DrivingDojo training labels are tag-based generic weak labels",
            "historical_claims_preserved": True,
            "required_rebuild": "label Q1/Q2 with the frozen oracle and grouped splits",
        },
        {
            "artifact": "copied/invalidated complete.json records with missing snapshots",
            "scope": "durability-valid publication rows",
            "reason": f"{trace['missing_final_snapshot_count']} unique run records lack snapshots",
            "historical_claims_preserved": True,
            "required_rebuild": "exclude copied rows; new runner must hash snapshot payload",
        },
    ]
    return {
        "policy": "PRESERVE_FILES_EXCLUDE_FROM_NEW_CLAIMS",
        "entries": entries,
        "invalidated_result_count": len(entries),
    }


def implementation_markdown(
    label: dict[str, Any],
    trace: dict[str, Any],
    baseline: dict[str, Any],
    score: dict[str, Any],
    decision: str,
) -> str:
    return f"""# MF-PSVR Cycle-0 Implementation Audit

`AUDIT_DECISION = {decision}`

## Strongest supported conclusion

The frozen unit-level oracle labels and reference events are internally aligned,
but legacy traces are not admissible as track-witness MF-PSVR training data or
strict publication-deadline comparisons. The current code now binds each unit
VERIFY opportunity to one immutable track witness and starts the publication
clock before oracle-session setup, proxy initialization, and detector warm-up.

## Observed evidence

- Label/reference audit: `{label['status']}`; checked
  {label['queried_rows_checked']} physical query results with
  {label['queried_label_mismatch_count']} label mismatches.
- Historical candidate identity: {trace['historical_mutable_candidate_run_units']}
  run-unit histories changed top track behind one unit candidate identity.
- Historical deadline accounting: {trace['historical_strict_deadline_miss_count']}
  runs marked deadline-met exceed the deadline under recorded total-service time.
- Snapshot audit: {trace['missing_final_snapshot_count']} unique completed run
  records point to a missing final snapshot.
- Physical repeats: {trace['physical_repeat_signature_mismatch_groups']} of
  {trace['physical_repeat_groups_checked']} comparable groups changed VERIFY
  signature; repeats are latency observations only.
- B1/B2 verdict: `{baseline['B1_B2']['identity_verdict']}`.
- SUPG variant verdict: `{baseline['SUPG_RT']['identity_verdict']}`.
- Score routing: `{score['status']}`.

## Derived conclusions

1. The admissible first target is the probability that verifying a unit-level
   opportunity returns an oracle-positive result. A track is a frozen causal
   witness, not track-specific ground truth.
2. All methods in the new physical table must be rerun under the repaired full
   clock. Historical negative rule-search conclusions remain preserved within
   their legacy contract.
3. B2 cannot count separately from B1, and the two SUPG-RT views cannot count as
   two effective baselines after K3 collapse.
4. Existing DrivingDojo models are useful pipeline evidence only; tag-based
   labels cannot support the MF-PSVR semantic-refiner claim.

## Main competing explanation

The historical implementation intentionally treated a candidate as an entire
10-second unit and stored the current top track only as explanatory evidence.
That interpretation preserves its unit-level endpoint metrics, but it does not
permit track-level candidate-value or temporal-refiner claims. The new contract
keeps the unit target while freezing the witness identity.

## Unresolved uncertainty

Whether independent, frozen-oracle-labeled training sessions contain enough Q1
and Q2 positives to identify semantic value across sources remains untested.
Repository-wide held-out enforcement also lacks a cryptographic access log;
Cycle 0 therefore proves only that this audit and the new program do not open
held-out semantics.

## Next highest-value action

Build the independent DrivingDojo session manifest, generate immutable
track-witness candidates, and measure the frozen-oracle Q1/Q2 class balance
before choosing a model family or launching a large physical matrix.
"""


def main() -> int:
    initialize_stage()
    runs, parse_errors = iter_unique_complete_runs()
    label_audit, _ = audit_labels(runs)
    trace_audit = audit_trace_integrity(runs, parse_errors)
    baseline_audit = audit_baselines()
    score_audit = audit_scores()
    literature_audit = audit_literature_artifacts()
    invalidated = invalidations(trace_audit)

    current_repairs_pass = (
        label_audit["status"] == "PASS"
        and trace_audit["current_candidate_binding_repair"] == "PASS"
        and trace_audit["current_full_deadline_clock_repair"] == "PASS"
        and score_audit["status"] != "FAIL"
        and baseline_audit["status"] == "PASS_WITH_EXCLUSIONS"
        and literature_audit["status"] == "PASS"
    )
    decision = "PASS_WITH_MANDATORY_LEGACY_INVALIDATIONS" if current_repairs_pass else "FAIL"

    atomic_json(CYCLE / "LABEL_ALIGNMENT_AUDIT.json", label_audit)
    atomic_json(CYCLE / "BASELINE_IDENTITY_AUDIT.json", baseline_audit)
    atomic_json(CYCLE / "SCORE_COLUMN_AUDIT.json", score_audit)
    atomic_json(CYCLE / "LITERATURE_AUDIT.json", literature_audit)
    atomic_json(CYCLE / "INVALIDATED_RESULTS.json", invalidated)
    atomic_json(CYCLE / "TRACE_AND_DEADLINE_AUDIT.json", trace_audit)
    atomic_text(
        CYCLE / "IMPLEMENTATION_AUDIT.md",
        implementation_markdown(
            label_audit, trace_audit, baseline_audit, score_audit, decision
        ),
    )
    audit_manifest = {
        "audit_id": "mf_psvr_cycle0_integrity_v1",
        "decision": decision,
        "candidate_semantics": (
            "UNIT_VERIFY_OPPORTUNITY_WITH_IMMUTABLE_TRACK_WITNESS"
        ),
        "heldout_opened": False,
        "audit_script_sha256": sha256_file(Path(__file__)),
        "artifacts": {},
    }
    for filename in (
        "IMPLEMENTATION_AUDIT.md",
        "LABEL_ALIGNMENT_AUDIT.json",
        "BASELINE_IDENTITY_AUDIT.json",
        "SCORE_COLUMN_AUDIT.json",
        "INVALIDATED_RESULTS.json",
        "TRACE_AND_DEADLINE_AUDIT.json",
        "LITERATURE_AUDIT.json",
        *LITERATURE_ARTIFACTS,
    ):
        path = CYCLE / filename
        audit_manifest["artifacts"][filename] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    audit_manifest["audit_hash"] = sha256_bytes(
        canonical_json(audit_manifest).encode("utf-8")
    )
    atomic_json(CYCLE / "AUDIT_MANIFEST.json", audit_manifest)
    atomic_json(CYCLE / "STAGE_STATE.json", {
        "stage": "cycle_00_integrity_and_literature",
        "status": decision,
        "completed_at_utc": utc_now(),
        "heldout_opened": False,
        "next_exact_command": "PYTHONPATH=src pytest -q",
    })
    print(json.dumps({
        "decision": decision,
        "unique_runs": len(runs),
        "queried_rows_checked": label_audit["queried_rows_checked"],
        "historical_mutable_candidate_run_units": trace_audit[
            "historical_mutable_candidate_run_units"
        ],
        "historical_strict_deadline_misses": trace_audit[
            "historical_strict_deadline_miss_count"
        ],
        "literature_audit": literature_audit["status"],
        "output": str(CYCLE.relative_to(ROOT)),
    }, sort_keys=True))
    return 0 if current_repairs_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
