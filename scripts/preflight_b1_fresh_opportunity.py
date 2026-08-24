#!/usr/bin/env python3
"""CPU-only preregistration audit; never opens video or runs inference."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "b1_fresh_opportunity_preregistration_20260824"
MANIFEST = DOC / "B1A_PROTOCOL_FREEZE_MANIFEST.json"
REPORT = DOC / "11_CPU_PREFLIGHT_REPORT.md"
PROTOCOL_FILES = tuple(f"docs/b1_fresh_opportunity_preregistration_20260824/{name}" for name in (
    "00_PROTOCOL_DECISION.md",
    "01_RESEARCH_QUESTION_AND_CLAIM_BOUNDARY.md",
    "02_FRESH_WORKLOAD_PROTOCOL.md",
    "03_B1_QUERY_REGISTRY.csv",
    "04_ACTION_BASELINE_AND_COST_PROTOCOL.md",
    "05_METRICS_GATES_AND_STATISTICS.md",
    "06_ANALYSIS_AND_ROBUSTNESS_PLAN.md",
    "07_RESULT_TABLE_TEMPLATES.md",
    "08_INPUT_BINDING.json",
    "09_FRESH_VIDEO_INTAKE_TEMPLATE.csv",
    "10_EXECUTION_PRIORITY.md",
))
SUPPORT_FILES = (
    "PROJECT_STATE_OF_TRUTH.md",
    "NEXT_STAGE_STATE_MACHINE.md",
    "DISCOVERY_QUERY_REGISTRY.csv",
    "src/garc/endogenous_contract.py",
    "scripts/preflight_b1_fresh_opportunity.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(None in row for row in rows):
        raise SystemExit(f"invalid CSV: {path}")
    return rows


def main() -> int:
    if MANIFEST.exists() or REPORT.exists():
        raise SystemExit("refusing to overwrite frozen B1a preflight")
    for relative in PROTOCOL_FILES + SUPPORT_FILES:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"missing file: {relative}")

    frozen = read_csv(DOC / "03_B1_QUERY_REGISTRY.csv")
    discovery = {row["query_id"]: row for row in read_csv(ROOT / "DISCOVERY_QUERY_REGISTRY.csv")}
    if len(frozen) != 6 or len({row["query_id"] for row in frozen}) != 6:
        raise SystemExit("B1a requires exactly six unique frozen queries")
    for row in frozen:
        source = discovery.get(row["query_id"])
        if source is None or source["exact_query_text"] != row["exact_query_text"]:
            raise SystemExit(f"query drift: {row['query_id']}")
        if row["post_outcome_changes_allowed"] != "NO":
            raise SystemExit("post-outcome query changes are forbidden")

    binding = json.loads((DOC / "08_INPUT_BINDING.json").read_text(encoding="utf-8"))
    intake = read_csv(DOC / "09_FRESH_VIDEO_INTAKE_TEMPLATE.csv")
    if len(intake) != 3:
        raise SystemExit("intake template must contain exactly three ordered slots")

    blockers: list[str] = []
    if binding["binding_status"] != "BOUND":
        blockers.append("fresh inputs are not bound")
    if len(binding["fresh_videos"]) != 3:
        blockers.append("three eligible fresh video hashes are absent")
    scan = binding["scan_generator"]
    if not all((scan["implementation_id"], scan["artifact_path"], scan["artifact_sha256"], scan["query_conditioned"], scan["measured_runtime_ready"])):
        blockers.append("query-conditioned SCAN implementation/artifact/runtime is unbound")
    verifier = binding["semantic_verifier"]
    if not all((verifier["implementation_id"], verifier["model_or_service_id"], verifier["prompt_hash"], verifier["decoding_config_hash"], verifier["runtime_ready"])):
        blockers.append("semantic verifier/prompt/runtime is unbound")
    if binding["execution_authorized"] is not True:
        blockers.append("external execution is not authorized")
    if binding["exact_deadlines_seconds"]:
        blockers.append("deadlines must remain empty until blinded cost calibration")

    decision = "B1A_PROTOCOL_READY_TO_EXECUTE" if not blockers else "B1A_PROTOCOL_FROZEN_EXECUTION_BLOCKED_INPUTS_UNBOUND"
    files = PROTOCOL_FILES + SUPPORT_FILES
    manifest = {
        "schema_version": 1,
        "protocol_id": "B1A_NATURAL_OPPORTUNITY_KILLER_V1",
        "decision": decision,
        "execution_performed": False,
        "semantic_outcomes_seen": False,
        "query_count": len(frozen),
        "required_video_count": 3,
        "analysis_seconds_per_video": 600,
        "region_seconds": 10,
        "video_query_workloads": 18,
        "exhaustive_direct_verify_calls": 1080,
        "maximum_primary_candidate_verify_calls": 2160,
        "blockers": blockers,
        "files": {relative: digest(ROOT / relative) for relative in files},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    bullet_blockers = "\n".join(f"- {item}" for item in blockers) or "- none"
    REPORT.write_text(f"""# B1a CPU preregistration preflight

## Decision

`{decision}`

The protocol is internally frozen and result-neutral. Exactly six inherited
queries match the discovery registry byte-for-byte; three ordered fresh-video
slots exist; no semantic execution was performed.

## Blocking inputs

{bullet_blockers}

## Planned scale

- 3 fresh independent videos × 6 queries = 18 workloads.
- 60 analysis regions per video.
- 1,080 exhaustive DirectVerify calls.
- At most 2,160 primary candidate-VERIFY calls.

These counts show why “continue” should not silently trigger external compute.
Binding and execution require a separate, hash-complete authorization.

## Scientific disposition

The next action is input binding, not algorithm design. If eligible videos or a
query-conditioned scanner cannot be bound, B1 remains blocked. Human annotation
is not required by this model-relative B1a protocol.
""", encoding="utf-8")
    print(json.dumps({"decision": decision, "blockers": blockers}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
