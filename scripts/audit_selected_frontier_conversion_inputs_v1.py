#!/usr/bin/env python3
"""Non-semantic input audit for the selected-Frontier calibration benchmark."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/selected_frontier_conversion_v1"
CONTRACT = ROOT / "docs/SELECTED_FRONTIER_CONVERSION_CALIBRATION_CONTRACT_V1.md"
PAIR_AUDIT = ROOT / "outputs/online_macro_activity_replication/technical_normalization/HANGZHOU_PAIR_CONTENT_IDENTITY_AUDIT.json"
ELIGIBILITY_REPORT = ROOT / "outputs/online_macro_activity_replication/reports/INPUT_ELIGIBILITY_REPORT.md"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def probe(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=width,height,nb_frames,avg_frame_rate",
        "-of", "json", str(path),
    ]
    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    raw = json.loads(p.stdout)
    stream = raw["streams"][0]
    return {
        "duration_sec": float(raw["format"]["duration"]),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frames": int(stream["nb_frames"]) if stream.get("nb_frames", "N/A") != "N/A" else None,
        "avg_frame_rate": stream.get("avg_frame_rate"),
    }


def main() -> None:
    created = datetime.now(timezone.utc).isoformat()
    files = [
        ("V0_DESIGN_ONLY", ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"),
        ("V1_DESIGN_ONLY", ROOT / "data/realcam/psvr_dev_inputs/驾驶-大理.mp4"),
        ("NEW_SOURCE_CANDIDATE", ROOT / "data/realcam/long_video_data/杭州.mp4"),
        ("REJECTED_SAME_CONTENT_AND_DECODE_FAILURE", ROOT / "data/realcam/long_video_data/杭州YouTube.mp4"),
        ("REJECTED_DERIVATIVE_AND_DECODE_FAILURE", ROOT / "data/realcam/long_video_data/杭州YouTube.normalized.mp4"),
        ("REJECTED_DERIVATIVE_AND_INCOMPLETE_TIMELINE", ROOT / "data/realcam/long_video_data/杭州YouTube.normalized.transcoded.mp4"),
        ("REJECTED_DESIGN_SOURCE_DERIVATIVE_REVIEW_CLIP", ROOT / "src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/review_media/clips/review_review_0102_0p0_1200p0.mp4"),
        ("REJECTED_CANONICAL_HELDOUT_AND_TOO_SHORT", ROOT / "try_or_no/test.mov"),
        ("REJECTED_REALCARTEST_DERIVATIVE_AND_TOO_SHORT", ROOT / "try_or_no/videos/realcartest_5k.mp4"),
    ]
    rows = []
    for role, path in files:
        if not path.exists():
            continue
        meta = probe(path)
        sidecar = Path(str(path) + ".source.json")
        rows.append({
            "path": str(path.relative_to(ROOT)), "role": role, "bytes": path.stat().st_size,
            "sha256": sha256(path), **meta,
            "sidecar": str(sidecar.relative_to(ROOT)) if sidecar.exists() else "",
            "sidecar_sha256": sha256(sidecar) if sidecar.exists() else "",
        })

    inv = OUT / "input_audit/video_inventory.csv"
    inv.parent.mkdir(parents=True, exist_ok=True)
    with inv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    pair = json.loads(PAIR_AUDIT.read_text())
    independence = {
        "created_utc": created,
        "scope": "technical/provenance only; no semantic labels, references, candidates, or method outputs opened",
        "design_only_sources": ["long_video_dataset3.mp4", "驾驶-大理.mp4"],
        "new_source_groups": [{
            "source_group_id": "OWNER_ATTESTED_SESSION_BV1S6fGYgE7V",
            "accepted_representation": "杭州.mp4",
            "status": "PRELIMINARY_ELIGIBLE_NEW_SOURCE",
            "registration_utc": "2026-07-24T00:00:00Z",
            "registration_basis": "legacy hash-bound owner attestation date",
            "independence_from_design_sources": "OWNER_ATTESTED_NOT_EXTERNALLY_VERIFIED",
            "rejected_representations": [
                "杭州YouTube.mp4", "杭州YouTube.normalized.mp4",
                "杭州YouTube.normalized.transcoded.mp4",
            ],
            "direct_contradiction": pair["conclusion"],
            "interpretation": "The Hangzhou representations count as at most one source; direct content evidence overrides distinct-session claims for the pair.",
        }],
        "independent_new_source_count": 1,
        "required_new_source_count": 4,
        "missing_new_source_count": 3,
        "uncertainty": "Independence of the accepted Hangzhou source from V0/V1 rests on owner attestation; no contradictory content evidence was found in the frozen prior audits.",
    }
    write_json(OUT / "input_audit/source_independence_audit.json", independence)

    technical = {
        "created_utc": created,
        "minimum_duration_sec": 1200,
        "recommended_duration_sec": 1800,
        "inventory": rows,
        "杭州.mp4": {
            "status": "PRELIMINARY_PASS_USING_PRIOR_FULL_DECODE_EVIDENCE",
            "evidence": str(ELIGIBILITY_REPORT.relative_to(ROOT)),
            "note": "No new full decode was consumed in this gate audit.",
        },
        "杭州YouTube.mp4": "FAIL_PRIOR_FULL_DECODE_AND_FAIL_SESSION_INDEPENDENCE",
        "杭州YouTube.normalized.mp4": "FAIL_DERIVATIVE_AND_PRIOR_FULL_DECODE",
        "杭州YouTube.normalized.transcoded.mp4": "FAIL_DERIVATIVE_AND_ONLY_8.4581_PERCENT_TIMELINE_RETAINED",
        "review_review_0102_0p0_1200p0.mp4": "FAIL_DERIVATIVE_OF_V0_DESIGN_SOURCE; MEDIA_MANIFEST_MAPS_SOURCE_TO_LONG_VIDEO_DATASET3_AT_2000_SECONDS",
        "test.mov": "FAIL_CANONICAL_HELDOUT_ROLE_AND_DURATION_43.043333_SECONDS",
        "realcartest_5k.mp4": "FAIL_DOCUMENTED_FIRST_5000_FRAME_DERIVATIVE_AND_DURATION_208.333333_SECONDS",
    }
    write_json(OUT / "input_audit/technical_eligibility_audit.json", technical)

    decision = {
        "created_utc": created,
        "contract_sha256": sha256(CONTRACT),
        "SELECTED_CONTROLLER": "R4_FIXED_TIME_RATIO_25_75",
        "REQUIRED_NEW_VIDEO_COUNT": 4,
        "PRELIMINARY_ELIGIBLE_NEW_VIDEO_COUNT": 1,
        "MISSING_NEW_VIDEO_COUNT": 3,
        "INPUT_GATE": "BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS",
        "SELECTED_FRONTIER_DATASET": "NOT_BUILT",
        "CALIBRATION_MODELS": "NOT_RUN",
        "RATIO_ANCHORED_CONTROLLER": "BLOCKED",
        "NEW_ORACLE_CALLS": 0,
        "SEMANTIC_ARTIFACTS_OPENED": False,
        "NEXT_ACTION": "PROVIDE_3_NEW_INDEPENDENT_COMPLETE_VIDEOS",
    }
    write_json(OUT / "input_audit/input_gate_decision.json", decision)

    request = """# Exact input request\n\nProvide at least **three additional** mutually independent, complete forward-facing road videos. Each must be at least 1,200 seconds (1,800 seconds recommended), come from a distinct non-overlapping capture session, and not be a crop, split, overlap, reencode, or derivative of any existing source.\n\nPlace each video in `data/realcam/selected_frontier_calibration_inputs/` with a sibling `<filename>.source.json` containing the fields frozen in the contract, including an immutable `registration_utc`, unique `capture_session_id`, provenance, parent/derivation declarations, and `target_event_information_used_for_selection=false`. Do not select or replace inputs based on event density or model behavior.\n\nAfter receipt, rerun only the technical/provenance input gate. Oracle work still requires the four-video gate, frozen role/hash assignment, and explicit compute authorization.\n"""
    p = OUT / "input_audit/INPUT_REQUEST.md"
    p.write_text(request)

    report = f"""# Asset and identification audit\n\n## Strongest supported conclusion\n\nThe Stage-1 benchmark cannot start. The local workspace contains only one preliminary eligible new source group (`杭州.mp4`) against a frozen requirement of four, so three additional independent complete videos are missing.\n\n## Decisive evidence\n\nV0 and V1 are design-only. `杭州YouTube.mp4` has the same duration/frame count as `杭州.mp4` and an exact aligned perceptual-hash match in the prior blind audit, so the Hangzhou pair is one source, not two. The normalized files are derivatives; the transcoded recovery retained only 8.4581% of the timeline. The 1,208-second review clip is explicitly mapped to V0 at offset 2,000 seconds; `test.mov` is the 43-second canonical heldout; and `realcartest_5k` is a documented 208-second derivative. No other inventoried large media file satisfies the gate.\n\n## Competing explanation and uncertainty\n\nThe accepted Hangzhou representation is technically executable under prior direct evidence, but its independence from V0/V1 is owner-attested rather than externally verified. Treating it as ineligible would strengthen, not reverse, the blocker (four videos missing instead of three).\n\n## Decision\n\n`INPUT_GATE=BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS`. Dataset construction, C0-C4, calibration metrics, static common-utility analysis, and Ratio-Anchored replay were not run. New Oracle calls: zero.\n"""
    (OUT / "reports").mkdir(parents=True, exist_ok=True)
    (OUT / "reports/ASSET_AND_IDENTIFICATION_AUDIT.md").write_text(report)
    final = """# Final decision\n\n```text\nSELECTED_CONTROLLER = R4_FIXED_TIME_RATIO_25_75\nSELECTED_FRONTIER_CONVERSION_CALIBRATION = BLOCKED_INPUT_NOT_AVAILABLE\nINPUT_GATE = BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS\nPRELIMINARY_ELIGIBLE_NEW_VIDEOS = 1\nREQUIRED_NEW_VIDEOS = 4\nMISSING_NEW_VIDEOS = 3\nSELECTED_FRONTIER_DATASET = NOT_BUILT\nCALIBRATION_MODELS = NOT_RUN\nNEW_ORACLE_CALLS = 0\nRATIO_ANCHORED_CONTROLLER = BLOCKED\nBANDIT = DEFERRED\nSMDP = DEFERRED\nRL = PROHIBITED\nNEXT_ACTION = PROVIDE_3_NEW_INDEPENDENT_COMPLETE_VIDEOS\n```\n\nThis is an input-availability result, not evidence for or against selected-Frontier calibratability.\n"""
    (OUT / "reports/FINAL_DECISION.md").write_text(final)

    completion = {
        "created_utc": created,
        "contract_frozen": True,
        "input_audit_complete": True,
        "input_gate_passed": False,
        "semantic_work_prohibited_and_not_run": True,
        "new_oracle_calls": 0,
        "scientific_interpretation": "BLOCKED_INPUT_NOT_AVAILABLE_NOT_A_CALIBRATION_FAILURE",
    }
    write_json(OUT / "reports/INDEPENDENT_COMPLETION_AUDIT.json", completion)

    artifacts = {
        str(path.relative_to(ROOT)): sha256(path)
        for path in sorted(OUT.rglob("*"))
        if path.is_file() and path.name != "artifact_hash_manifest.json"
    }
    write_json(OUT / "artifact_hash_manifest.json", {
        "created_utc": created, "artifact_count": len(artifacts), "artifacts": artifacts,
    })


if __name__ == "__main__":
    main()
