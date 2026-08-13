#!/usr/bin/env python3
"""Freeze the isolated, method-blind P1 shadow VLM reference protocol."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P1 = ROOT / "outputs/p1_independent_geometry_replication_v1"
OUT = ROOT / "outputs/p1_shadow_vlm_direct_reference_v1"
CASES = P1 / "ANNOTATOR_VIEW_CASES.json"
QUERY = P1 / "QUERY_DEFINITIONS.md"
GUIDE = P1 / "ANNOTATION_GUIDE.md"
PAIR = P1 / "PRIMARY_GEOMETRY_PAIR_MANIFEST_V1_2.csv"
QWEN = ROOT / "models/Qwen3-VL-8B-Instruct"
SMOL = Path("/root/.cache/huggingface/hub/models--HuggingFaceTB--SmolVLM2-500M-Video-Instruct/snapshots/7b375e1b73b11138ff12fe22c8f2822d8fe03467")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    for item in sorted(x for x in path.rglob("*") if x.is_file()):
        h.update(str(item.relative_to(path)).encode())
        h.update(str(item.stat().st_size).encode())
        # Hash small identity/config files and weight filenames/sizes; the local
        # artifact identity is also pinned in the raw-call records.
        if item.stat().st_size < 4_000_000:
            h.update(bytes.fromhex(sha(item)))
    return h.hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite shadow study: {OUT}")
    cases = json.loads(CASES.read_text())
    if len(cases) != 6 or len({x["case_id"] for x in cases}) != 6:
        raise RuntimeError("expected frozen six-case package")
    if not QWEN.is_dir() or not SMOL.is_dir():
        raise RuntimeError("both frozen local VLMs are required")
    blind_cases = []
    for case in cases:
        video = ROOT / case["video_path"]
        if sha(video) != case["video_sha256"]:
            raise RuntimeError(f"video hash mismatch: {video}")
        blind_cases.append({
            "case_id": case["case_id"], "video_id": case["video_id"],
            "query_id": case["query_id"], "query_definition": case["query_definition"],
            "duration_sec": case["duration_sec"], "video_path": str(video),
            "video_sha256": case["video_sha256"],
        })
    prompt = """You are a blinded temporal-event annotator. The images are chronological samples from one raw driving-video window. The window begins at ABS_START seconds and ends at ABS_END seconds in the full video. Apply only the frozen semantic query below. Do not use a fixed temporal-gap rule. Identify maximal semantic occurrences visible in this window. Return exactly one JSON object and no markdown:
{"events":[{"start_offset_sec":0.0,"end_offset_sec":0.0,"boundary_ambiguous":false,"semantic_ambiguous":false,"notes":"short visible rationale"}]}

Offsets are seconds from the window start, constrained to [0, WINDOW_DURATION]. If no qualifying occurrence is visible, return {"events":[]}. Do not infer events from timestamps or sampling; use visible semantics. If an occurrence crosses the window edge, clip it to that edge and set boundary_ambiguous=true.

FROZEN QUERY:
QUERY_TEXT
"""
    protocol = {
        "protocol_id": "GVAQP_P1_SHADOW_VLM_DIRECT_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_frozen": True,
        "reference_type": "VLM_DIRECT_SHADOW",
        "human_reference": False,
        "formal_p1_modified": False,
        "method_blinding": {
            "visible": ["raw video frames", "frozen query text", "video-window timestamps"],
            "hidden": ["proxy", "policy", "candidate trace", "verified positives", "geometry", "pair manifest", "C0/C1/K3", "pseudo-reference", "EventF1", "algorithm output"],
        },
        "windowing": {
            "window_sec": 60.0, "stride_sec": 50.0, "sample_fps": 0.25,
            "frame_cap": 15, "boundary": "half-open except final window",
            "stitch": "within annotator/query, merge only positive-overlap proposals; no fixed gap",
        },
        "annotators": {
            "VLM_A": {"model": "Qwen/Qwen3-VL-8B-Instruct", "family": "Qwen3-VL", "path": str(QWEN), "identity_hash": tree_hash(QWEN)},
            "VLM_B": {"model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct", "family": "SmolVLM2", "path": str(SMOL), "identity_hash": tree_hash(SMOL)},
        },
        "independence": "cross-family models, separate raw logs and serial sessions; VLM_B never reads VLM_A output",
        "generation": {"do_sample": False, "max_new_tokens": 512, "parse_once": True, "parse_failure": "empty uncertain window; never retry semantic output"},
        "prompt_template": prompt,
        "pseudo_adjudication": {
            "rule": "one-to-one maximum-IoU matching at IoU>0; matched interval is union; unmatched events retained; deterministic sort and renumber",
            "method_outcomes_visible": False,
        },
        "frozen_analysis": {
            "pair_manifest_sha256": sha(PAIR), "pair_count": 198,
            "primary_geometry": "number_of_temporal_regions_touched",
            "primary_attribution": "ANCHOR_ASSIGNED_EVENT",
            "secondary_attribution": "OVERLAP_ANY_EVENT",
            "primary_generalization": "LOVO", "secondary_generalization": "LOVQ",
            "inference_unit": "video-query cluster",
        },
        "input_hashes": {"cases": sha(CASES), "query_definitions": sha(QUERY), "annotation_guide": sha(GUIDE), "pair_manifest": sha(PAIR)},
        "cases": blind_cases,
    }
    protocol["protocol_hash"] = canonical_hash({k: v for k, v in protocol.items() if k not in {"created_at_utc", "protocol_hash"}})
    OUT.mkdir(parents=True)
    (OUT / "SHADOW_PROTOCOL.json").write_text(json.dumps(protocol, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (OUT / "BLINDED_CASES.json").write_text(json.dumps(blind_cases, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (OUT / "SHADOW_STATE.json").write_text(json.dumps({
        "status": "PROTOCOL_FROZEN", "protocol_hash": protocol["protocol_hash"],
        "vlm_a_complete": False, "vlm_b_complete": False, "shadow_reference_frozen": False,
        "formal_p1_status": "WAITING_HUMAN_REFERENCE", "p2_authorized": False,
    }, indent=2, sort_keys=True) + "\n")
    (OUT / "BLINDING_CONTRACT.md").write_text("# P1 shadow blinding contract\n\nThe two annotator runners may read only `SHADOW_PROTOCOL.json`, `BLINDED_CASES.json`, and raw video files. They must finish and hash-freeze both annotation streams before any trace, proxy, pair, semantic-unit outcome, C1/K3, or EventF1 artifact is opened. This is a VLM-direct shadow reference, never a human reference or formal P1 result.\n")
    print(json.dumps({"status": "PROTOCOL_FROZEN", "protocol_hash": protocol["protocol_hash"], "cases": 6, "annotators": ["VLM_A", "VLM_B"]}, sort_keys=True))


if __name__ == "__main__":
    main()
