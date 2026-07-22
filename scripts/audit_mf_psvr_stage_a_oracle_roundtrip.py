#!/usr/bin/env python3
"""Run the frozen Stage-A verifier with round-trip CSV float parsing.

The frozen verifier uses pandas' default C float parser and then requires
bit-exact equality with raw JSON timing floats.  That parser changes at least
one correctly round-trippable decimal by one ULP.  This wrapper does not edit
the frozen runner or any oracle artifact: it replaces only the runner module's
pandas facade so every read_csv call defaults to float_precision='round_trip',
then executes the original hash-frozen verify() implementation in full.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a"
RUNNER = ROOT / "scripts/run_mf_psvr_stage_a_oracle.py"
SPEC = STAGE / "STAGE_A_ORACLE_EXECUTION_SPEC.json"
DIFFERENCE = STAGE / "STAGE_A_EXECUTION_DIFFERENCE_AUDIT.json"
REPORT_AUDIT = STAGE / "STAGE_A_COMPLETION_AUDIT.json"
CALLS = STAGE.parent / "ORACLE_CALL_MANIFEST.csv"
RAW_ONE = STAGE / "oracle/raw/mf_psvr_stage_a_001.json"
OUTPUT = STAGE / "STAGE_A_ORACLE_ROUNDTRIP_VERIFICATION_AUDIT.json"


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


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RoundTripPandas:
    """Proxy pandas while changing only the default read_csv float parser."""

    def __getattr__(self, name: str) -> Any:
        return getattr(pd, name)

    @staticmethod
    def read_csv(*args: Any, **kwargs: Any) -> pd.DataFrame:
        kwargs.setdefault("float_precision", "round_trip")
        return pd.read_csv(*args, **kwargs)


def run_frozen_verify() -> dict[str, Any]:
    spec = load_json(SPEC)
    expected_runner = spec["bindings"]["runner_source_sha256"]
    observed_runner = sha256_file(RUNNER)
    if observed_runner != expected_runner:
        raise RuntimeError("Frozen oracle runner no longer matches execution spec")
    module_spec = importlib.util.spec_from_file_location("mf_psvr_frozen_oracle_roundtrip_verify", RUNNER)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("Cannot import frozen oracle runner")
    runner = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner)
    runner.pd = RoundTripPandas()
    result = runner.locked(runner.verify)
    if not (
        result.get("status") == "VERIFIED_COMPLETE_COMMIT"
        and result.get("physical_attempts_started") == 96
        and result.get("accepted_durable_calls") == 96
        and result.get("uncertain_started_calls") == 0
        and result.get("heldout_opened") is False
    ):
        raise RuntimeError("Round-trip frozen verification did not return the exact complete state")
    return result


def compute() -> dict[str, Any]:
    with CALLS.open(newline="", encoding="utf-8") as handle:
        first = next(csv.DictReader(handle))
    csv_text = first["generation_runtime_seconds"]
    raw_value = float(load_json(RAW_ONE)["generation_runtime_seconds"])
    default_value = float(pd.read_csv(CALLS).iloc[0]["generation_runtime_seconds"])
    roundtrip_value = float(pd.read_csv(CALLS, float_precision="round_trip").iloc[0]["generation_runtime_seconds"])
    python_value = float(csv_text)
    if python_value != raw_value or roundtrip_value != raw_value or default_value == raw_value:
        raise RuntimeError("The isolated float-parser diagnosis no longer reproduces")
    result = run_frozen_verify()
    value = {
        "audit_id": "MF_PSVR_STAGE_A_ORACLE_ROUNDTRIP_VERIFICATION_V1",
        "created_at_utc": utc_now(),
        "status": "PASS",
        "qualification": "FULL_FROZEN_VERIFY_WITH_PARSER_ONLY_ROUNDTRIP_SHIM",
        "frozen_verify_result": result,
        "parser_shim": "module-local pandas facade; read_csv defaults float_precision=round_trip; no other behavior changed",
        "isolated_call_id": "mf_psvr_stage_a_001",
        "isolated_csv_text": csv_text,
        "python_float_equals_raw_json": python_value == raw_value,
        "pandas_roundtrip_equals_raw_json": roundtrip_value == raw_value,
        "pandas_default_equals_raw_json": default_value == raw_value,
        "pandas_default_value_repr": repr(default_value),
        "raw_json_value_repr": repr(raw_value),
        "frozen_runner_sha256": sha256_file(RUNNER),
        "expected_frozen_runner_sha256": load_json(SPEC)["bindings"]["runner_source_sha256"],
        "wrapper_source_sha256": sha256_file(Path(__file__)),
        "execution_difference_audit_sha256": sha256_file(DIFFERENCE),
        "prior_report_audit_sha256": sha256_file(REPORT_AUDIT),
        "call_manifest_sha256": sha256_file(CALLS),
        "oracle_artifacts_modified_by_wrapper": 0,
        "heldout_opened": False,
    }
    value["audit_hash"] = canonical_hash(value)
    return value


def write() -> dict[str, Any]:
    value = compute()
    atomic_json(OUTPUT, value)
    return value


def verify() -> dict[str, Any]:
    if not OUTPUT.is_file():
        raise RuntimeError("Round-trip verification receipt is absent")
    observed = load_json(OUTPUT)
    if observed.get("audit_hash") != canonical_hash({key: value for key, value in observed.items() if key != "audit_hash"}):
        raise RuntimeError("Round-trip verification receipt self-hash is invalid")
    recomputed = compute()
    for key, value in recomputed.items():
        if key not in {"created_at_utc", "audit_hash"} and observed.get(key) != value:
            raise RuntimeError(f"Round-trip verification receipt does not recompute: {key}")
    return observed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["write", "verify"])
    args = parser.parse_args()
    result = write() if args.stage == "write" else verify()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
