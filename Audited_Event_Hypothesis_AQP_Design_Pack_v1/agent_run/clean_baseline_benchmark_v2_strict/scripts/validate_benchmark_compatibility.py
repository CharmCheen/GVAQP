#!/usr/bin/env python3
"""Compare a new run/benchmark manifest against clean baseline benchmark v1."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent

REQUIRED = [
    "video_sha256", "unit_table_sha256", "proxy_table_sha256", "cheap_feature_manifest_sha256",
    "oracle_model_hash", "oracle_prompt_hash", "oracle_parser_hash", "reference_hash",
    "budget_schedule_hash", "evaluator_hash", "matching_hash", "baseline_code_hashes",
]
WARN_ONLY = ["baseline_code_hashes"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-manifest", type=Path, default=PACK / "BENCHMARK_MANIFEST.json")
    parser.add_argument("--new-manifest", type=Path, required=True)
    parser.add_argument("--new-run-id", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark_manifest.read_text())
    new = json.loads(args.new_manifest.read_text())
    expected = benchmark.get("compatibility", benchmark)
    observed = new.get("compatibility", new)
    incompatible, warnings = [], []
    for field in REQUIRED:
        if field not in observed:
            (warnings if field in WARN_ONLY else incompatible).append(field)
        elif observed[field] != expected[field]:
            (warnings if field in WARN_ONLY else incompatible).append(field)
    result = {
        "compatible": not incompatible,
        "incompatible_fields": incompatible,
        "warning_fields": warnings,
        "benchmark_id": benchmark["benchmark_id"],
        "new_run_id": args.new_run_id or new.get("run_id") or f"new_{uuid.uuid4().hex[:12]}",
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(payload, end="")
    return 0 if result["compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

