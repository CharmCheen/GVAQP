#!/usr/bin/env python3
"""Freeze the two-query protocol before new proxy or scheduler evaluation."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_two_video_loop"
INPUT_GATE = OUT / "state/INPUT_GATE_DECISION.json"
VIDEO_MANIFEST = OUT / "VIDEO_MANIFEST.json"
FROZEN_BENCH = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1"
    / "agent_run/clean_baseline_benchmark_v2_strict"
)
ORACLE_PROMPT = FROZEN_BENCH / "oracle/oracle_prompt.txt"
ORACLE_CONFIG = FROZEN_BENCH / "oracle/oracle_configuration.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    gate = json.loads(INPUT_GATE.read_text(encoding="utf-8"))
    if gate.get("VIDEO_INPUT_GATE") != "PASS":
        raise RuntimeError("Two-video input gate is not PASS; run audit_psvr_two_video_inputs.py")
    videos = json.loads(VIDEO_MANIFEST.read_text(encoding="utf-8"))
    oracle = json.loads(ORACLE_CONFIG.read_text(encoding="utf-8"))
    if sha256_file(ORACLE_PROMPT) != oracle["prompt_sha256"]:
        raise RuntimeError("Frozen oracle prompt hash does not match its configuration")

    exclusions = [
        "ego vehicle lane change causing relative motion",
        "ordinary adjacent parallel travel",
        "distant irrelevant lane change",
        "object visible without entering the ego path",
        "road curvature causing apparent lateral motion",
        "static parked actor",
    ]
    queries = [
        {
            "query_id": "Q1",
            "name": "OTHER_VEHICLE_ENTERS_EGO_PATH",
            "definition": (
                "A non-ego vehicle, motorcycle, or bicycle enters, crosses, or persistently "
                "occupies the ego vehicle's potential driving path from outside that path."
            ),
            "frozen_oracle_type_projection": ["vehicle", "cyclist"],
            "projection_reason": (
                "The immutable oracle schema represents bicycle/cyclist with involved_object="
                "cyclist and does not expose a separate motorcycle category."
            ),
            "exclusions": exclusions,
        },
        {
            "query_id": "Q2",
            "name": "VRU_ENTERS_EGO_PATH",
            "definition": (
                "A pedestrian, cyclist, or other vulnerable road user enters, crosses, or "
                "persistently occupies the ego vehicle's potential driving path."
            ),
            "frozen_oracle_type_projection": ["pedestrian", "cyclist"],
            "projection_reason": (
                "The immutable schema reliably identifies pedestrian and cyclist. The generic "
                "'other' value is excluded because vulnerability is not encoded deterministically."
            ),
            "exclusions": exclusions,
        },
    ]
    protocol = {
        "protocol_version": "PSVR_TWO_QUERY_SELECTION_V1",
        "frozen_at_utc": utc_now(),
        "selection_timing": "before any new two-video proxy or scheduler evaluation",
        "video_ids": ["V0", "V1"],
        "queries": queries,
        "task_count": 4,
        "reference_construction": {
            "oracle_policy": (
                "Run/reuse the immutable exhaustive OBJECT_ENTERS_EGO_PATH oracle exactly once "
                "per video-unit, then deterministically project positive observations using only "
                "the parsed involved_object field."
            ),
            "negative_policy": (
                "A unit is positive for a query iff the frozen oracle label is positive and "
                "involved_object belongs to that query's preregistered projection; every other "
                "successfully parsed unit is negative for that query, except oracle abstentions "
                "which remain abstentions."
            ),
            "multiple_query_membership": (
                "cyclist is intentionally eligible for both Q1 and Q2 because the user-frozen "
                "definitions overlap; tasks need not be mutually exclusive."
            ),
            "text_evidence_used_for_projection": False,
            "reference_or_proxy_outcome_used_for_query_choice": False,
        },
        "feasibility_rule": {
            "same_queries_across_both_videos": True,
            "single_video_zero_event": "retain as sparse stress task",
            "both_video_zero_event": "consider preregistered fallback order Q3 then Q4",
            "fallback_order": [
                "Q3_DYNAMIC_AGENT_BLOCKS_EGO_PATH",
                "Q4_FRONT_VEHICLE_ABRUPTLY_STOPS_OR_SLOWS",
            ],
            "fallback_constraint": (
                "A fallback may be used only if it can be evaluated without changing the frozen "
                "oracle/prompt/parser. Otherwise reference integrity fails closed."
            ),
        },
        "immutable_oracle_binding": {
            "model_full_content_hash": oracle["model_full_content_hash"],
            "prompt_sha256": oracle["prompt_sha256"],
            "prompt_path": str(ORACLE_PROMPT),
            "parser_config": oracle["parser_config"],
            "parser_source_hash": oracle["parser_source_hash"],
            "sampling_code_hash": oracle["sampling_code_hash"],
            "frame_config": oracle["frame_config"],
            "generation_config": oracle["generation_config"],
        },
        "heldout_opened": False,
    }
    protocol["protocol_hash"] = canonical_hash(protocol)
    manifest = {
        "manifest_version": "PSVR_TWO_QUERY_MANIFEST_V1",
        "frozen_at_utc": protocol["frozen_at_utc"],
        "query_protocol_hash": protocol["protocol_hash"],
        "queries": [
            {
                "query_id": query["query_id"],
                "query_name": query["name"],
                "type_projection": query["frozen_oracle_type_projection"],
            }
            for query in queries
        ],
        "tasks": [
            {
                "task_id": f"{video_id}_{query['query_id']}",
                "video_id": video_id,
                "video_sha256": videos[video_id]["sha256"],
                "query_id": query["query_id"],
                "query_name": query["name"],
            }
            for video_id in ("V0", "V1")
            for query in queries
        ],
        "DEV_SOURCE_VIDEOS": 2,
        "DEV_QUERIES": 2,
        "DEV_VIDEO_QUERIES": 4,
        "QUERY_FREEZE": "PASS",
        "heldout_opened": False,
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    atomic_json(OUT / "QUERY_SELECTION_PROTOCOL.json", protocol)
    atomic_json(OUT / "QUERY_MANIFEST.json", manifest)
    atomic_json(OUT / "benchmark/QUERY_SELECTION_PROTOCOL.json", protocol)
    atomic_json(OUT / "benchmark/QUERY_MANIFEST.json", manifest)
    atomic_json(OUT / "state/QUERY_FREEZE_DECISION.json", {
        "QUERY_FREEZE": "PASS",
        "QUERY_PROTOCOL_HASH": protocol["protocol_hash"],
        "QUERY_MANIFEST_HASH": manifest["manifest_hash"],
        "NEXT_EXACT_COMMAND": "python scripts/build_psvr_two_video_references.py prepare",
        "heldout_opened": False,
    })
    print(json.dumps({
        "QUERY_FREEZE": "PASS",
        "queries": [query["name"] for query in queries],
        "tasks": 4,
        "protocol_hash": protocol["protocol_hash"],
    }, indent=2))


if __name__ == "__main__":
    main()
