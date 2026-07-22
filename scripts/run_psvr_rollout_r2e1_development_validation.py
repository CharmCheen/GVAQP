#!/usr/bin/env python3
"""Development-only E1 execution-contract validation; never creates an attempt root."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from garc_eval.psvr_rollout_toy.r2e1_execution import METHOD_IDS, append_ledger, execute_identity, export_derived_layer
from garc_eval.psvr_rollout_toy.r2e1_verifier import verify_attempt

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "outputs/psvr_rollout_r2e1/E1_DEVELOPMENT_VALIDATION_AUDIT.json"


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="psvr-r2e1-development-") as temp:
        root = Path(temp)
        ledger = root / "CONFIRMATORY_ATTEMPT_LEDGER.jsonl"
        # The coordinator's identity grammar is intentionally reused in this
        # disposable fixture; the root and ledger label retain its non-confirmatory status.
        episode = "confirmatory-0000"
        for method in METHOD_IDS:
            append_ledger(ledger, {"episode_public_id":episode, "sealed_seed_hash":"DEVELOPMENT_FIXTURE_ONLY", "method_id":method, "state":"PREPARED", "attempt_ordinal":0, "timestamp":datetime.now(timezone.utc).isoformat(), "raw_trace_path":None, "raw_trace_sha256":None, "failure_class":None, "recovery_status":"NONE"})
        for method in METHOD_IDS:
            execute_identity(root, 0, 101, method, {"development_fixture":"NOT_CONFIRMATORY"})
        exports = export_derived_layer(root)
        verifier = verify_attempt(root, allow_fixture=True)
    report = {"status":"PASS" if verifier["status"] == "PASS" else "FAIL", "scope":"DEVELOPMENT_FIXTURE_ONLY", "confirmatory_attempt_root_created":False, "heldout_seed_file_read":False, "heldout_runner_invoked":False, "development_identity_count":1, "method_count":len(METHOD_IDS), "exports":exports, "independent_verifier":{key: verifier[key] for key in ("status", "ledger_row_count", "latest_identity_count", "committed_identity_count", "error_count", "raw_layer_only", "derived_outputs_read")}, "timestamp":datetime.now(timezone.utc).isoformat()}
    atomic_json(AUDIT, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
