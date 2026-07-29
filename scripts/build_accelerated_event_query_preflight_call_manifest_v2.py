#!/usr/bin/env python3
"""Materialize the explicit, write-once 32-call authorization manifest for V2."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_protocol import canonical_hash, sha256_file


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V2_PREREGISTRATION.json"
SELECTION = OUT / "operational_oracle/PREFLIGHT_V1_PREREGISTRATION.json"
FRAMES = OUT / "operational_oracle/preflight_v2/ORACLE_INPUT_FRAME_MANIFEST_V2.json"
DESTINATION = OUT / "operational_oracle/preflight_v2/AUTHORIZED_CALL_MANIFEST_V2.json"
SHARDS = ("DALI", "HANGZHOU", "WUHAN")


def artifact_name(candidate: str, variant: str, repeat: int, shard: str) -> str:
    if variant == "base":
        suffix = f"fps2_r{repeat}"
    elif variant == "fps_sensitivity":
        suffix = "fps4_sensitivity"
    else:
        suffix = f"fps2_cross_replica_{shard}"
    return f"{candidate}_{suffix}.json"


def build() -> dict:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    clips = {row["candidate_id"]: row for row in selection["clips"]}
    frame_sets = {
        (row["candidate_id"], float(row["sampling_fps"])): row
        for row in json.loads(FRAMES.read_text(encoding="utf-8"))["frame_sets"]
    }
    sensitivity = set(prereg["workload"]["sensitivity_candidate_ids"])
    anchor_id = prereg["workload"]["cross_replica_anchor_candidate_id"]
    calls = []
    for shard in SHARDS:
        for clip in selection["clips"]:
            if clip["video_id"] != shard:
                continue
            for repeat in (0, 1):
                calls.append((shard, clip, "base", repeat, 2.0))
            if clip["candidate_id"] in sensitivity:
                calls.append((shard, clip, "fps_sensitivity", 0, 4.0))
        if shard != "DALI":
            calls.append((shard, clips[anchor_id], "cross_replica_anchor", 0, 2.0))
    rows = []
    for ordinal, (shard, clip, variant, repeat, sampling_fps) in enumerate(calls):
        frame_set = frame_sets[(clip["candidate_id"], sampling_fps)]
        name = artifact_name(clip["candidate_id"], variant, repeat, shard)
        row = {
            "ordinal": ordinal,
            "execution_shard": shard,
            "artifact_name": name,
            "artifact_path": f"outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/raw/{shard}/{name}",
            "candidate_id": clip["candidate_id"],
            "video_id": clip["video_id"],
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
            "variant": variant,
            "repeat_index": repeat,
            "sampling_fps": sampling_fps,
            "frame_count": frame_set["frame_count"],
            "frame_set_sha256": frame_set["frame_set_sha256"],
            "model_input_group": f"{clip['candidate_id']}@{sampling_fps:g}fps",
        }
        row["call_spec_sha256"] = canonical_hash(row)
        rows.append(row)
    counts = Counter(row["variant"] for row in rows)
    shard_counts = Counter(row["execution_shard"] for row in rows)
    expected = prereg["workload"]
    assertions = {
        "total": len(rows) == expected["total_physical_calls"] == 32,
        "base": counts["base"] == expected["same_process_base_calls"] == 24,
        "sensitivity": counts["fps_sensitivity"] == expected["sampling_sensitivity_calls"] == 6,
        "extra_anchor": counts["cross_replica_anchor"] == expected["additional_cross_replica_calls"] == 2,
        "shards": dict(shard_counts) == {"DALI": 10, "HANGZHOU": 11, "WUHAN": 11},
        "unique_artifacts": len({row["artifact_path"] for row in rows}) == 32,
    }
    if not all(assertions.values()):
        raise RuntimeError(f"authorized-call arithmetic failed: {assertions}")
    return {
        "status": "FROZEN_BEFORE_NEW_QUERY_ORACLE_EXECUTION",
        "experiment_id": prereg["experiment_id"],
        "authorization_scope": "exactly these 32 physical generations; automatic inference retry is forbidden",
        "selection_source_sha256": sha256_file(SELECTION),
        "frame_manifest_sha256": sha256_file(FRAMES),
        "assertions": assertions,
        "counts_by_variant": dict(counts),
        "counts_by_shard": dict(shard_counts),
        "authorized_call_count": len(rows),
        "calls": rows,
    }


def main() -> None:
    value = build()
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists():
        if DESTINATION.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"refusing to overwrite nonmatching call manifest: {DESTINATION}")
    else:
        temporary = DESTINATION.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, DESTINATION)
    print(json.dumps({"path": str(DESTINATION.relative_to(ROOT)),
                      "sha256": sha256_file(DESTINATION),
                      "authorized_calls": value["authorized_call_count"]}, indent=2))


if __name__ == "__main__":
    main()
