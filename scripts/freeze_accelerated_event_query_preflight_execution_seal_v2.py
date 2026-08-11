#!/usr/bin/env python3
"""Freeze the complete executable and protocol surface for AEQ preflight V2."""

from __future__ import annotations

import json
import os
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V2_PREREGISTRATION.json"
DESTINATION = OUT / "operational_oracle/preflight_v2/PREFLIGHT_V2_EXECUTION_SEAL.json"
SOURCES = {
    "runner": ROOT / "scripts/run_accelerated_event_query_oracle_preflight_v2.py",
    "analyzer": ROOT / "scripts/analyze_accelerated_event_query_oracle_preflight_v2.py",
    "finalizer": ROOT / "scripts/finalize_accelerated_event_query_oracle_preflight_v2.py",
}


def build() -> dict:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    checked_bindings = {}
    for key, relative in prereg["bindings"].items():
        if not key.endswith("_path"):
            continue
        hash_key = key.removesuffix("_path") + "_sha256"
        if hash_key not in prereg["bindings"]:
            continue
        observed = sha256_file(ROOT / relative)
        if observed != prereg["bindings"][hash_key]:
            raise RuntimeError(f"preregistration binding mismatch: {relative}")
        checked_bindings[key] = {"path": relative, "sha256": observed}
    sources = {}
    for name, path in SOURCES.items():
        sources[f"{name}_source_path"] = str(path.relative_to(ROOT))
        sources[f"{name}_source_sha256"] = sha256_file(path)
    return {
        "status": "FROZEN_BEFORE_NEW_QUERY_ORACLE_EXECUTION",
        "experiment_id": prereg["experiment_id"],
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "preregistration_sha256": sha256_file(PREREG),
        "sources": sources,
        "checked_preregistration_bindings": checked_bindings,
        "execution_rule": "Runner, analyzer, and finalizer must match these source hashes; any change requires a new pre-output seal and review.",
    }


def main() -> None:
    value = build()
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists():
        if DESTINATION.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite nonmatching execution seal: {DESTINATION}")
    else:
        temporary = DESTINATION.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, DESTINATION)
    print(json.dumps({"path": str(DESTINATION.relative_to(ROOT)),
                      "sha256": sha256_file(DESTINATION)}, indent=2))


if __name__ == "__main__":
    main()
