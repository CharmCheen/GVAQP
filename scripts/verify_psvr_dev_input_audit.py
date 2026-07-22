#!/usr/bin/env python3
"""Independently verify the frozen Cycle-07 PSVR Phase-A input audit.

The verifier reads only Phase-A metadata and approved development inputs.  It
does not open the canonical held-out video or any held-out reference material.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "outputs/psvr_autonomous_research/benchmark_unblock"
CYCLE_DIR = ROOT / "outputs/psvr_autonomous_research/cycle_07_BENCHMARK_UNBLOCK"
REPORT = CYCLE_DIR / "CORRECTNESS_REPORT.json"
HELDOUT_VIDEO = (ROOT / "try_or_no/test.mov").resolve()
REQUIRED_ARTIFACTS = [
    "INPUT_ROOTS.json",
    "VIDEO_CANDIDATES.csv",
    "SOURCE_INDEPENDENCE_AUDIT.json",
    "DERIVATION_GROUPS.json",
    "INPUT_POOL_DECISION.json",
    "INPUT_REQUEST.md",
]
EXPECTED_DATASET3_SHA256 = "bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610"
EXPECTED_NEXAR_DUPLICATE_SHA256 = "c79d4f8a8045e012905952c9b1cb79615db1300fa1799339f88bbb5f69636243"
EXPECTED_NEXAR_DUPLICATE_SUFFIXES = {
    "datasets/casq_external/nexar/videos_hf/train/positive/00822.mp4",
    "datasets/casq_external/nexar/videos_smoke/positive/00822.mp4",
}


def file_sha256(path: Path) -> str:
    if path.resolve() == HELDOUT_VIDEO:
        raise RuntimeError("verifier must not open held-out media")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(name: str) -> dict:
    return json.loads((AUDIT_DIR / name).read_text())


def truth(value: str) -> bool:
    return str(value).strip().lower() == "true"


def relative_if_possible(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def main() -> int:
    checks: list[dict] = []
    errors: list[str] = []

    def check(name: str, condition: bool, evidence: object) -> None:
        passed = bool(condition)
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})
        if not passed:
            errors.append(name)

    for name in REQUIRED_ARTIFACTS:
        check(f"artifact_exists:{name}", (AUDIT_DIR / name).is_file(), str(AUDIT_DIR / name))
    if errors:
        CYCLE_DIR.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"status": "FAIL", "errors": errors, "checks": checks}, indent=2) + "\n")
        return 1

    roots = load_json("INPUT_ROOTS.json")
    independence = load_json("SOURCE_INDEPENDENCE_AUDIT.json")
    derivations = load_json("DERIVATION_GROUPS.json")
    decision = load_json("INPUT_POOL_DECISION.json")
    request = (AUDIT_DIR / "INPUT_REQUEST.md").read_text()
    with (AUDIT_DIR / "VIDEO_CANDIDATES.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    expected_columns = {
        "absolute_path", "exists", "source_name", "container", "codec", "duration_seconds",
        "frame_rate", "resolution", "file_size_bytes", "file_sha256", "creation_time",
        "configured_dataset_identity", "capture_session_id", "provenance_declaration",
        "known_parent_video", "known_derivation_operation",
        "lineage_independence", "decode_evidence", "proxy_feasibility", "oracle_feasibility",
        "workload_units_10s", "length_sufficient", "duplicate_group", "input_pool_eligible",
        "decision_reason",
    }
    row_columns = set(rows[0]) if rows else set()
    check("candidate_schema", expected_columns.issubset(row_columns), sorted(row_columns))
    check("candidate_path_uniqueness", len(rows) == len({r["absolute_path"] for r in rows}), len(rows))
    check("frozen_candidate_row_count", len(rows) == 609, len(rows))
    existing = [row for row in rows if truth(row["exists"])]
    eligible = [row for row in rows if truth(row["input_pool_eligible"])]
    check("frozen_existing_path_count", len(existing) == 607, len(existing))
    check("exactly_one_eligible_source", [r["source_name"] for r in eligible] == ["long_video_dataset3"],
          [r["source_name"] for r in eligible])

    by_source = {row["source_name"]: row for row in rows}
    dataset3 = by_source.get("long_video_dataset3", {})
    dataset3_path = Path(dataset3.get("absolute_path", "/missing"))
    canonical_dataset3_path = (ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4").resolve()
    check("dataset3_canonical_path", dataset3_path.resolve() == canonical_dataset3_path,
          str(dataset3_path.resolve()))
    check("dataset3_duration_and_units",
          float(dataset3.get("duration_seconds", 0)) >= 1200 and int(dataset3.get("workload_units_10s", 0)) == 347,
          {"duration": dataset3.get("duration_seconds"), "units": dataset3.get("workload_units_10s")})
    check("dataset3_recorded_hash", dataset3.get("file_sha256") == EXPECTED_DATASET3_SHA256,
          dataset3.get("file_sha256"))
    actual_dataset3_hash = file_sha256(dataset3_path) if dataset3_path.is_file() else "MISSING"
    check("dataset3_physical_hash", actual_dataset3_hash == EXPECTED_DATASET3_SHA256, actual_dataset3_hash)
    check("dataset3_feasibility_evidence",
          dataset3.get("decode_evidence", "").startswith("PASS:")
          and dataset3.get("proxy_feasibility", "").startswith("PASS:")
          and dataset3.get("oracle_feasibility", "").startswith("PASS:"),
          {k: dataset3.get(k) for k in ("decode_evidence", "proxy_feasibility", "oracle_feasibility")})

    nexar = [r for r in rows if r["source_name"].startswith("nexar_") and truth(r["exists"])]
    nexar_durations = [float(r["duration_seconds"]) for r in nexar]
    nexar_hashes = {r["file_sha256"] for r in nexar}
    check("nexar_paths_and_unique_content", len(nexar) == 604 and len(nexar_hashes) == 603,
          {"paths": len(nexar), "unique_hashes": len(nexar_hashes)})
    nexar_min = min(nexar_durations) if nexar_durations else None
    nexar_max = max(nexar_durations) if nexar_durations else None
    check("nexar_length_fatal",
          nexar_min == 15.0 and nexar_max == 49.464883
          and sum(d >= 1200 for d in nexar_durations) == 0,
          {"min": nexar_min, "max": nexar_max,
           "at_least_1200s": sum(d >= 1200 for d in nexar_durations)})
    duplicate_rows = [r for r in nexar if r["file_sha256"] == EXPECTED_NEXAR_DUPLICATE_SHA256]
    duplicate_suffixes = {relative_if_possible(Path(r["absolute_path"])) for r in duplicate_rows}
    duplicate_group_ids = {r["duplicate_group"] for r in duplicate_rows}
    check("nexar_known_duplicate_group",
          len(duplicate_rows) == 2 and duplicate_suffixes == EXPECTED_NEXAR_DUPLICATE_SUFFIXES
          and len(duplicate_group_ids) == 1 and "" not in duplicate_group_ids,
          {"paths": sorted(duplicate_suffixes), "groups": sorted(duplicate_group_ids)})
    duplicate_actual_hashes = {file_sha256(Path(r["absolute_path"])) for r in duplicate_rows}
    check("nexar_duplicate_physical_hash", duplicate_actual_hashes == {EXPECTED_NEXAR_DUPLICATE_SHA256},
          sorted(duplicate_actual_hashes))

    realcartest_5k = by_source.get("realcartest_5k", {})
    check("realcartest_5k_derivative_excluded",
          not truth(realcartest_5k.get("input_pool_eligible", ""))
          and realcartest_5k.get("known_parent_video", "").endswith("try_or_no/videos/realcartest.mp4")
          and "first 5000" in realcartest_5k.get("known_derivation_operation", ""),
          {k: realcartest_5k.get(k) for k in ("known_parent_video", "known_derivation_operation", "decision_reason")})
    check("historical_long_sources_missing",
          not truth(by_source.get("long_video_dataset2", {}).get("exists", ""))
          and not truth(by_source.get("realcartest", {}).get("exists", "")),
          {k: by_source.get(k, {}).get("decision_reason") for k in ("long_video_dataset2", "realcartest")})

    heldout = by_source.get("test_heldout", {})
    check("heldout_row_metadata_only",
          Path(heldout.get("absolute_path", "/missing")).resolve() == HELDOUT_VIDEO
          and heldout.get("decode_evidence") == "NOT_PROBED:heldout_excluded"
          and not truth(heldout.get("input_pool_eligible", "")),
          {k: heldout.get(k) for k in ("absolute_path", "decode_evidence", "decision_reason")})
    heldout_root_rows = [r for r in roots.get("roots", []) if r.get("role") in {
        "existing_heldout_split", "canonical_heldout_video", "configured heldout root",
        "legacy manifest alias of canonical heldout",
    }]
    check("heldout_roots_not_searched",
          len(heldout_root_rows) == 4 and all(r.get("searched_for_video_files") is False for r in heldout_root_rows),
          heldout_root_rows)
    check("heldout_flags_false",
          roots.get("heldout_opened") is False and independence.get("heldout_opened") is False
          and derivations.get("heldout_opened") is False and decision.get("heldout_opened") is False,
          {"roots": roots.get("heldout_opened"), "independence": independence.get("heldout_opened"),
           "derivations": derivations.get("heldout_opened"), "decision": decision.get("heldout_opened")})

    content_evidence = independence.get("content_identity_evidence", {})
    check("hash_accounting_separates_heldout_manifest",
          content_evidence.get("full_file_sha256_computed_by_this_audit") == 606
          and content_evidence.get("heldout_identity_hashes_copied_from_existing_manifest") == 1,
          content_evidence)
    audit_duplicate_groups = content_evidence.get("duplicate_groups", [])
    derivation_nexar = next((g for g in derivations.get("groups", [])
                             if g.get("group_id") == "nexar_collection"), {})
    expected_duplicate_record = {
        "group_id": next(iter(duplicate_group_ids), ""),
        "sha256": EXPECTED_NEXAR_DUPLICATE_SHA256,
        "paths": [str(ROOT / suffix) for suffix in sorted(EXPECTED_NEXAR_DUPLICATE_SUFFIXES)],
    }
    normalize_record = lambda record: {
        "group_id": record.get("group_id"), "sha256": record.get("sha256"),
        "paths": sorted(record.get("paths", [])),
    }
    check("duplicate_record_cross_artifact_consistency",
          any(normalize_record(r) == normalize_record(expected_duplicate_record) for r in audit_duplicate_groups)
          and any(normalize_record(r) == normalize_record(expected_duplicate_record)
                  for r in derivation_nexar.get("exact_duplicate_groups", [])),
          {"expected": expected_duplicate_record, "independence": audit_duplicate_groups,
           "derivations": derivation_nexar.get("exact_duplicate_groups", [])})
    workload = independence.get("workload_length_derivation", {})
    check("workload_threshold_precedes_candidates",
          workload.get("A0_scan_batches_before_verify") == 29 and workload.get("batch_size") == 4
          and workload.get("frozen_unit_seconds") == 10 and workload.get("units_needed_before_full_coverage") == 117
          and workload.get("minimum_seconds_used") == 1200.0,
          workload)

    archive = ROOT / "datasets/DrivingDojo-mini/drivingdojo_mini.zip"
    video_entries: list[str] = []
    if archive.is_file():
        with zipfile.ZipFile(archive) as handle:
            video_entries = [name for name in handle.namelist()
                             if Path(name).suffix.lower() in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}]
    check("drivingdojo_archive_has_no_video_container", archive.is_file() and not video_entries,
          {"archive_exists": archive.is_file(), "video_entries": video_entries[:10]})

    decision_expected = {
        "BENCHMARK_INPUT_POOL": "INSUFFICIENT",
        "AUTONOMOUS_RESEARCH": "PAUSED_INPUT_REQUIRED",
        "AUTONOMOUS_RESEARCH_STATUS": "PAUSED_INPUT_REQUIRED",
        "DEV_BENCHMARK_UNBLOCK": "NOT_RUN_INPUT_INSUFFICIENT",
        "PSVR_METHOD_USABILITY": "NOT_YET",
        "PSVR_CORE_INNOVATION": "BLOCKED",
        "required_independent_source_videos": 3,
        "eligible_independent_source_videos": 1,
        "additional_sources_needed": 2,
        "eligible_source_ids": ["long_video_dataset3"],
        "next_exact_command": "python scripts/audit_psvr_dev_inputs.py",
        "heldout_opened": False,
    }
    check("input_pool_decision_exact",
          all(decision.get(key) == value for key, value in decision_expected.items()),
          {key: decision.get(key) for key in decision_expected})

    user_root = (ROOT / "data/realcam/psvr_dev_inputs").resolve()
    user_root_records = [r for r in roots.get("roots", [])
                         if Path(r.get("absolute_path", "/missing")).resolve() == user_root]
    check("advertised_user_input_root_is_searched",
          len(user_root_records) == 1 and user_root_records[0].get("searched_for_video_files") is True,
          user_root_records)
    supported = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
    actual_user_videos = ({str(p.resolve()) for p in user_root.rglob("*")
                           if p.is_file() and p.suffix.lower() in supported}
                          if user_root.is_dir() else set())
    recorded_user_videos = {r["absolute_path"] for r in rows
                            if user_root in Path(r["absolute_path"]).parents}
    check("all_supplied_user_inputs_are_in_candidate_table",
          actual_user_videos == recorded_user_videos,
          {"actual": sorted(actual_user_videos), "recorded": sorted(recorded_user_videos)})
    qualification = independence.get("user_input_qualification", {})
    check("user_input_qualification_is_explicit",
          qualification.get("placement_root") == str(user_root)
          and qualification.get("required_sidecar_suffix") == ".source.json"
          and "exact-content duplicate" in qualification.get("independence_limit", ""),
          qualification)
    audit_module_path = ROOT / "scripts/audit_psvr_dev_inputs.py"
    spec = importlib.util.spec_from_file_location("audit_psvr_dev_inputs_for_verify", audit_module_path)
    audit_module = importlib.util.module_from_spec(spec) if spec and spec.loader else None
    if audit_module is not None and spec is not None and spec.loader is not None:
        spec.loader.exec_module(audit_module)
        rule_positive = audit_module.qualifies_user_input(
            length_ok=True, probe_error=False, declaration="PASS", technical_ok=True)
        rule_negative = [
            audit_module.qualifies_user_input(length_ok=False, probe_error=False, declaration="PASS", technical_ok=True),
            audit_module.qualifies_user_input(length_ok=True, probe_error=True, declaration="PASS", technical_ok=True),
            audit_module.qualifies_user_input(length_ok=True, probe_error=False, declaration="MISSING", technical_ok=True),
            audit_module.qualifies_user_input(length_ok=True, probe_error=False, declaration="PASS", technical_ok=False),
        ]
    else:
        rule_positive, rule_negative = False, [True]
    check("new_input_eligibility_rule_reachable_and_fail_closed",
          rule_positive and not any(rule_negative),
          {"positive_case": rule_positive, "negative_cases": rule_negative})

    eligible_paths = [Path(r["absolute_path"]) for r in eligible]
    forbidden_parts = {"outputs", "experiments", "datasets/clips"}
    check("no_output_or_clip_derivative_eligible",
          all(not any(part in relative_if_possible(path) for part in forbidden_parts) for path in eligible_paths),
          [str(path) for path in eligible_paths])
    group_ids = {g.get("group_id") for g in derivations.get("groups", [])}
    check("derivation_groups_complete",
          {"dataset3_family", "realcartest_family", "test_heldout_family", "nexar_collection", "drivingdojo_mini"}.issubset(group_ids),
          sorted(group_ids))

    request_fragments = [
        "2 additional independent source videos", "MP4, MOV, MKV, AVI, WebM, or M4V",
        "30 minutes", "data/realcam/psvr_dev_inputs", "Do not provide crops, reencodes",
        "name.mp4.source.json", "capture_session_id",
        "python scripts/audit_psvr_dev_inputs.py",
    ]
    check("input_request_complete", all(fragment in request for fragment in request_fragments), request_fragments)

    resolved_path = CYCLE_DIR / "resolved_config.json"
    resolved = json.loads(resolved_path.read_text()) if resolved_path.is_file() else {}
    script_path = ROOT / "scripts/audit_psvr_dev_inputs.py"
    check("audit_script_hash_frozen", resolved.get("script_sha256") == file_sha256(script_path),
          {"recorded": resolved.get("script_sha256"), "actual": file_sha256(script_path)})
    output_hashes = resolved.get("output_hashes", {})
    actual_output_hashes = {name: file_sha256(AUDIT_DIR / name) for name in REQUIRED_ARTIFACTS}
    check("phase_a_artifact_hashes_frozen", output_hashes == actual_output_hashes,
          {"recorded": output_hashes, "actual": actual_output_hashes})

    cycle_decision_path = CYCLE_DIR / "AUDITED_DECISION.json"
    cycle_decision = json.loads(cycle_decision_path.read_text()) if cycle_decision_path.is_file() else {}
    state_path = ROOT / "outputs/psvr_autonomous_research/RESEARCH_STATE.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}
    synthesis_path = ROOT / "outputs/psvr_autonomous_research/FINAL_SYNTHESIS.md"
    synthesis = synthesis_path.read_text() if synthesis_path.is_file() else ""
    check("decision_state_synthesis_consistency",
          cycle_decision.get("AUTONOMOUS_RESEARCH_STATUS") == "PAUSED_INPUT_REQUIRED"
          and cycle_decision.get("PSVR_CORE_INNOVATION") == "BLOCKED"
          and state.get("autonomous_research_status") == "PAUSED_INPUT_REQUIRED"
          and state.get("core_innovation_status") == "BLOCKED"
          and "AUTONOMOUS_RESEARCH_STATUS = PAUSED_INPUT_REQUIRED" in synthesis
          and "PSVR_CORE_INNOVATION = BLOCKED" in synthesis,
          {"cycle": {k: cycle_decision.get(k) for k in ("AUTONOMOUS_RESEARCH_STATUS", "PSVR_CORE_INNOVATION")},
           "state": {k: state.get(k) for k in ("autonomous_research_status", "core_innovation_status")}})

    report = {
        "status": "PASS" if not errors else "FAIL",
        "verifier": "scripts/verify_psvr_dev_input_audit.py",
        "scope": "Cycle-07 frozen Phase-A input availability; this verifier does not open held-out media/reference",
        "heldout_opened": False,
        "checks_passed": sum(c["status"] == "PASS" for c in checks),
        "checks_total": len(checks),
        "errors": errors,
        "checks": checks,
    }
    CYCLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "checks_passed", "checks_total", "heldout_opened")}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
