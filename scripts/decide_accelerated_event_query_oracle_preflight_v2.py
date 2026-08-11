#!/usr/bin/env python3
"""Map the frozen V2 finalizer status to the user-authorized three-way decision."""

from __future__ import annotations

import json
import os
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_protocol import canonical_hash, sha256_file
from garc_eval.accelerated_event_query.oracle_response_protocol import loads_unique


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "outputs/accelerated_event_query_v1/operational_oracle/preflight_v2"
MAPPING = PREFLIGHT / "USER_DECISION_MAPPING_V2.json"
FINALIZER_DECISION = PREFLIGHT / "PREFLIGHT_FINAL_DECISION_V2.json"
DESTINATION = PREFLIGHT / "TARGETED_PILOT_DECISION_V2.json"


def load(path: Path) -> dict:
    return loads_unique(path.read_text(encoding="utf-8"))


def main() -> None:
    mapping = load(MAPPING)
    if mapping.get("status") != "FROZEN_BEFORE_PHYSICAL_ORACLE_EXECUTION":
        raise RuntimeError("user decision mapping was not frozen before execution")
    if mapping.get("mapper_source_sha256") != sha256_file(Path(__file__)):
        raise RuntimeError("user decision mapper source mismatch")
    finalizer = load(FINALIZER_DECISION)
    if finalizer.get("execution_seal_sha256") != mapping["execution_seal_sha256"]:
        raise RuntimeError("finalizer decision/execution seal mismatch")
    source_status = finalizer.get("final_status")
    if source_status not in mapping["finalizer_status_mapping"]:
        raise RuntimeError(f"unmapped finalizer status: {source_status}")
    decision = mapping["finalizer_status_mapping"][source_status]
    if decision not in mapping["allowed_user_decisions"]:
        raise RuntimeError("mapped decision is outside the user-authorized set")
    result = {
        "experiment_id": "AEQ_ORACLE_PREFLIGHT_V2",
        "decision": decision,
        "source_finalizer_status": source_status,
        "finalizer_decision_sha256": sha256_file(FINALIZER_DECISION),
        "execution_seal_sha256": mapping["execution_seal_sha256"],
        "mapping_sha256": sha256_file(MAPPING),
        "scope": "Targeted 32-call protocol pilot only; no representative/full-oracle or downstream claim.",
    }
    result["decision_payload_sha256"] = canonical_hash(result)
    if DESTINATION.exists():
        raise RuntimeError(f"refusing to overwrite decision: {DESTINATION}")
    temporary = DESTINATION.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, DESTINATION)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
