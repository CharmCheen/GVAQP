#!/usr/bin/env python3
"""Run a complete 1,475-record mock and fault injection without model inference."""

import argparse
import json
import tempfile
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_v3_full_grid_dry_run import (
    run_complete_mock,
    run_fault_injections,
)
from garc_eval.accelerated_event_query.oracle_v3_full_grid_package import PACKAGE
from garc_eval.accelerated_event_query.oracle_v3_manifest import canonical_hash, write_json_once


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-audit", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="aeq_v3_full_grid_dry_run_") as temporary:
        root = Path(temporary)
        complete = run_complete_mock(root / "complete")
        faults = run_fault_injections(root / "faults")
    result = {
        "status": "PASS_NO_CHECKPOINT_LOAD_NO_MODEL_INFERENCE",
        "complete_mock": complete,
        "fault_injections": faults,
        "formal_full_grid_raw_output_created": False,
        "formal_reference_created": False,
    }
    result["dry_run_audit_payload_sha256"] = canonical_hash(result)
    if args.record_audit:
        write_json_once(PACKAGE / "FULL_GRID_DRY_RUN_AUDIT.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
