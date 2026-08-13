#!/usr/bin/env python3
"""Freeze executable P1 analysis provenance before P1 outcomes are available."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
MANIFEST = OUT / "P1_ANALYSIS_IMPLEMENTATION_MANIFEST.json"
HUMAN_LOG = OUT / "human_reference_package/HUMAN_EVENT_LABELS.jsonl"
QWEN_RAW = OUT / "qwen32_oracle/raw"


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if MANIFEST.exists():
        raise RuntimeError("P1 analysis implementation manifest already frozen")
    if HUMAN_LOG.exists() and HUMAN_LOG.stat().st_size:
        raise RuntimeError("refusing implementation freeze after human labels exist")
    # Raw outcomes may be partial during an ongoing acquisition, but no full table
    # or decision can yet exist. The manifest therefore freezes implementation,
    # not the data being acquired.
    if (OUT/"qwen32_oracle/P1_QWEN32_UNIT_OUTCOMES.parquet").exists() or (OUT/"P1_DECISION.json").exists():
        raise RuntimeError("refusing implementation freeze after primary P1 outcomes/finalization")
    files=[
        "scripts/analyze_p1_independent_geometry.py",
        "scripts/finalize_p1_no_go.py",
        "src/garc_eval/accelerated_event_query/matching.py",
        "src/garc_eval/accelerated_event_query/types.py",
        "scripts/analyze_p0_v3_materializer_mechanisms.py",
    ]
    payload={
        "protocol_id":"P1_INDEPENDENT_GEOMETRY_ANALYSIS_IMPLEMENTATION_V1",
        "status":"FROZEN_BEFORE_SECOND_QUERY_OUTCOMES_AND_HUMAN_REFERENCE",
        "analysis_protocol_sha256":sha(OUT/"P1_ANALYSIS_PROTOCOL.json"),
        "p1_protocol_sha256":sha(OUT/"P1_PROTOCOL.json"),
        "files":{relative:sha(ROOT/relative) for relative in files},
        "scope":"Executable provenance for P1 primary analysis, frozen evaluator matcher, frozen C1 implementation, and terminal P1 NO-GO archival writer.",
        "outcome_state_at_freeze":{"qwen_raw_record_count":len(list(QWEN_RAW.glob("*.json"))),"human_label_log_bytes":HUMAN_LOG.stat().st_size if HUMAN_LOG.exists() else 0},
    }
    payload["manifest_hash"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    MANIFEST.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"FROZEN","manifest":str(MANIFEST),"qwen_raw_record_count":payload["outcome_state_at_freeze"]["qwen_raw_record_count"]},sort_keys=True))


if __name__=="__main__":
    main()
