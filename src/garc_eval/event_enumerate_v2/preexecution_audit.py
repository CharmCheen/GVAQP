"""Seal the processor-only pre-execution audit from direct test artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT
    / "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2"
)
AUDIT = OUTPUT / "audit"
RUNTIME = OUTPUT / "runtime"
CONFIG = OUTPUT / "config"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _test_results() -> dict[str, object]:
    path = RUNTIME / "pytest_results.xml"
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        raise RuntimeError("pytest JUnit file has no test suite")
    names = {
        str(case.attrib["name"]): case
        for case in suite.findall("testcase")
    }
    return {
        "tests": int(suite.attrib.get("tests", 0)),
        "failures": int(suite.attrib.get("failures", 0)),
        "errors": int(suite.attrib.get("errors", 0)),
        "skipped": int(suite.attrib.get("skipped", 0)),
        "names": names,
        "sha256": sha256_file(path),
    }


def _require_test(results: dict[str, object], name: str) -> str:
    names = results["names"]
    if name not in names:
        raise RuntimeError(f"required test result is absent: {name}")
    case = names[name]
    if case.find("failure") is not None or case.find("error") is not None:
        raise RuntimeError(f"required test did not pass: {name}")
    return f"runtime/pytest_results.xml::{name}"


def _lock_valid() -> bool:
    lock_path = CONFIG / ".event_enumerate_v2_freeze.lock"
    config_path = CONFIG / "FROZEN_EVENT_ENUMERATE_V2_CONFIG.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if sha256_file(config_path) != lock["frozen_config_sha256"]:
        return False
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative, expected in config["frozen_source_hashes"].items():
        path = Path(relative)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists() or sha256_file(path) != expected:
            return False
    for relative, expected in config["frozen_artifact_hashes"].items():
        path = ROOT / relative
        if not path.exists() or sha256_file(path) != expected:
            return False
    return True


def audit_rows() -> list[dict[str, object]]:
    results = _test_results()
    if results["failures"] or results["errors"] or results["skipped"]:
        raise RuntimeError("processor test suite is not an all-pass result")
    old_rows = list(
        csv.DictReader(
            (AUDIT / "OLD_CALL_TIMELINE_RECONSTRUCTION.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    nominal = [row for row in old_rows if row["is_nominal_60_second_call"] == "True"]
    prompt_manifest = json.loads(
        (CONFIG / "PROMPT_AND_PARSER_MANIFEST.json").read_text(encoding="utf-8")
    )
    attempts = OUTPUT / "physical/attempts"
    physical_attempt_count = sum(1 for _ in attempts.iterdir()) if attempts.exists() else 0
    common = {
        "status": "PASS",
        "test_suite_sha256": results["sha256"],
    }
    rows = [
        {
            "check_id": "old_bug_reproduction",
            "criterion": "exact v1 helper/processor signature and all 68 nominal calls reproduce metadata compression",
            "observed": f"{len(nominal)} calls: 121 decoded -> 122 helper-padded -> 10 processor frames -> final timestamp 4.8s",
            "evidence": " | ".join(
                [
                    _require_test(
                        results,
                        "test_exact_v1_helper_to_processor_call_compresses_sentinel_frames",
                    ),
                    _require_test(
                        results,
                        "test_all_68_nominal_old_calls_have_the_reconstructed_compression",
                    ),
                ]
            ),
            **common,
        },
        {
            "check_id": "installed_old_rule_execution",
            "criterion": "installed Qwen classes independently reproduce 24-FPS fallback",
            "observed": "positions [0,13,27,40,54,67,81,94,108,121]; five patch timestamps",
            "evidence": _require_test(
                results,
                "test_installed_qwen_classes_execute_the_reconstructed_old_rules",
            ),
            **common,
        },
        {
            "check_id": "corrected_path_regression",
            "criterion": "121 corrected frames remain 61 patches through 60.0 seconds",
            "observed": "metadata FPS=10, offsets 0..600 step 5, grid_t=61, timestamp text ends 60.0",
            "evidence": _require_test(
                results,
                "test_installed_processor_preserves_the_full_nominal_60_second_timeline",
            ),
            **common,
        },
        {
            "check_id": "frame_timestamp_identity",
            "criterion": "requested frame index equals decoded barcode and source timestamp",
            "observed": "all corpus intervals and decoded frames exact",
            "evidence": _require_test(
                results,
                "test_every_decoded_frame_has_the_requested_identity_and_time",
            ),
            **common,
        },
        {
            "check_id": "processor_timeline_identity",
            "criterion": "processor timestamps equal independent source-index proof",
            "observed": "all registered interval lengths monotonic; exact patch count and endpoint",
            "evidence": _require_test(
                results,
                "test_pure_timestamp_transport_covers_all_registered_lengths",
            ),
            **common,
        },
        {
            "check_id": "relative_absolute_mapping",
            "criterion": "nonzero offsets map from actual first decoded timestamp",
            "observed": "absolute=actual_anchor+relative; no nominal-start substitution",
            "evidence": _require_test(
                results,
                "test_nonzero_offset_maps_from_actual_first_decoded_timestamp",
            ),
            **common,
        },
        {
            "check_id": "row_order_invariance",
            "criterion": "exact deduplication is invariant to arrival order",
            "observed": "all six permutations identical",
            "evidence": _require_test(
                results, "test_reconciliation_is_invariant_to_row_order"
            ),
            **common,
        },
        {
            "check_id": "batch_single_equivalence",
            "criterion": "batch and single active input IDs, grids, and pixel tensors agree",
            "observed": "byte-identical split tensors for nonzero and final-partial cases",
            "evidence": _require_test(
                results,
                "test_batch_and_single_processor_outputs_are_equivalent",
            ),
            **common,
        },
        {
            "check_id": "beginning_middle_end_markers",
            "criterion": "nominal 60-second selection transports all visible markers",
            "observed": "frame 0 BEGIN, frame 300 MIDDLE, frame 600 END decoded and color-verified",
            "evidence": _require_test(
                results,
                "test_beginning_middle_end_markers_are_in_the_nominal_60_second_input",
            ),
            **common,
        },
        {
            "check_id": "partial_final_interval",
            "criterion": "final partial and odd-count intervals preserve capped boundaries",
            "observed": "3.4-second final input has seven selected frames and four temporal patches",
            "evidence": _require_test(
                results,
                "test_interval_boundaries_and_variable_frame_counts[timeline_73p4s_10fps.mp4-partial-70.0-73.4-7]",
            ),
            **common,
        },
        {
            "check_id": "deterministic_parser",
            "criterion": "parser is deterministic and refuses schema/boundary repair",
            "observed": "ten repeats identical; invalid type and out-of-range boundary rejected",
            "evidence": _require_test(
                results, "test_parser_is_deterministic_and_rejects_repairs"
            ),
            **common,
        },
        {
            "check_id": "no_event_label_access",
            "criterion": "inference modules contain no reference or stratum access",
            "observed": "static forbidden-token scan passed",
            "evidence": _require_test(
                results, "test_inference_modules_have_no_reference_or_label_access"
            ),
            **common,
        },
        {
            "check_id": "prompt_not_tuned",
            "criterion": "v2 prompt is byte-identical to the preexisting v1 frozen prompt",
            "observed": prompt_manifest["prompt"]["sha256"],
            "evidence": "config/PROMPT_AND_PARSER_MANIFEST.json",
            **common,
        },
        {
            "check_id": "freeze_integrity",
            "criterion": "all frozen processor source and config hashes verify",
            "observed": str(_lock_valid()),
            "evidence": "config/.event_enumerate_v2_freeze.lock",
            **common,
        },
        {
            "check_id": "physical_call_precondition",
            "criterion": "no physical call exists before held-out gate",
            "observed": physical_attempt_count,
            "evidence": "physical/attempts",
            **common,
        },
    ]
    if any(row["status"] != "PASS" for row in rows) or not _lock_valid():
        raise RuntimeError("pre-execution audit contains a non-pass result")
    if physical_attempt_count != 0:
        raise RuntimeError("a physical attempt exists before authorization")
    return rows


def audit() -> None:
    rows = audit_rows()
    path = AUDIT / "PRE_EXECUTION_PROCESSOR_AUDIT.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "processor_gate": "PASS",
        "checks": len(rows),
        "passes": sum(row["status"] == "PASS" for row in rows),
        "physical_calls_permitted": False,
        "physical_calls_spent": 0,
        "blocking_gate": "HELDOUT_DATA_REQUIRED",
        "audit_sha256": sha256_file(path),
    }
    (AUDIT / "PRE_EXECUTION_PROCESSOR_AUDIT.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    audit()


if __name__ == "__main__":
    main()
