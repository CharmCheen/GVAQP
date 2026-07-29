#!/usr/bin/env python3
"""Directly rehash every frozen 32B model file into a V2 identity artifact."""

from __future__ import annotations

import json
import os
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_protocol import canonical_hash, sha256_file


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models/Qwen3-VL-32B-Instruct-FP8"
PRIOR = ROOT / "outputs/binary_smdp_value_v1/hangzhou_physical/32b_results.json"
DESTINATION = ROOT / "outputs/accelerated_event_query_v1/operational_oracle/MODEL_FILE_MANIFEST_V2.json"


def main() -> None:
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    expected = {row["file"]: row for row in prior["model_file_manifest"]}
    observed_names = {path.name for path in MODEL.iterdir() if path.is_file()}
    if observed_names != set(expected):
        raise RuntimeError(f"model file-set mismatch: missing={set(expected)-observed_names}, extra={observed_names-set(expected)}")
    rows = []
    for name in sorted(expected):
        path = MODEL / name
        row = {"file": name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        if row != expected[name]:
            raise RuntimeError(f"model file identity mismatch: {name}")
        rows.append(row)
        print(json.dumps({"hashed": name, "size_bytes": row["size_bytes"]}), flush=True)
    content_hash = canonical_hash(rows)
    if content_hash != prior["model_content_hash"]:
        raise RuntimeError("canonical model content hash mismatch")
    value = {
        "status": "PASS_DIRECT_FULL_REHASH",
        "model_path": str(MODEL.relative_to(ROOT)),
        "file_count": len(rows),
        "total_size_bytes": sum(row["size_bytes"] for row in rows),
        "model_content_hash": content_hash,
        "prior_evidence_path": str(PRIOR.relative_to(ROOT)),
        "prior_evidence_sha256": sha256_file(PRIOR),
        "files": rows,
    }
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    if DESTINATION.exists():
        if DESTINATION.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite nonmatching model manifest: {DESTINATION}")
    else:
        temporary = DESTINATION.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, DESTINATION)
    print(json.dumps({"manifest": str(DESTINATION.relative_to(ROOT)),
                      "sha256": sha256_file(DESTINATION), "model_content_hash": content_hash}, indent=2))


if __name__ == "__main__":
    main()
