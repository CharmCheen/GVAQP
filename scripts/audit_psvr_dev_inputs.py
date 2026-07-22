#!/usr/bin/env python3
"""Audit the bounded local PSVR development-video pool (Phase A only).

This script deliberately searches only repository data roots and paths already
named by historical manifests.  Its formal execution never reads held-out
media bytes or semantic reference material.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_autonomous_research/benchmark_unblock"
USER_INPUT_ROOT = ROOT / "data/realcam/psvr_dev_inputs"
CANONICAL_DATASET3 = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
CANONICAL_DATASET3_SHA256 = "bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610"
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
MIN_WORKLOAD_SECONDS = 1200.0  # 29 A0 batches * 4 units * 10 s, rounded up.
RECOMMENDED_SECONDS = 1800.0   # historical new-video scout data gate.

SEARCH_ROOTS = [
    (ROOT / "data/realcam/long_video_data", "repository_source_video_root", True),
    (USER_INPUT_ROOT, "user_provided_psvr_development_input_root", True),
    (ROOT / "try_or_no", "historically_referenced_video_root", True),
    (ROOT / "data/videos", "GARC_DATA_DIR_configured_video_root", True),
    (ROOT / "datasets/casq_external/nexar/videos_hf", "mounted_nexar_video_root", True),
    (ROOT / "datasets/casq_external/nexar/videos_smoke", "mounted_nexar_smoke_root", True),
    (ROOT / "datasets/DrivingDojo-mini", "local_archive_root", False),
    (ROOT / "datasets/clips", "known_derived_clip_root", False),
]
HELDOUT_ROOT = ROOT / "AQP_Algorithm_Invention_Sprint_v1/operator_validation/heldout_reference_v1/media"
HELDOUT_VIDEO = ROOT / "try_or_no/test.mov"
MISSING_REFERENCES = [
    (ROOT / "data/realcam/long_video_data/long_video_dataset2.mp4", "long_video_dataset2", 4617.0,
     "historical scout manifest; bytes now absent; later role audit found in-cabin driver-facing view unsuitable for ego-path queries"),
    (ROOT / "try_or_no/videos/realcartest.mp4", "realcartest", 3987.104,
     "historical V13 development/reference source; bytes absent"),
]

FIELDS = [
    "absolute_path", "exists", "source_name", "container", "codec", "duration_seconds",
    "frame_rate", "width", "height", "resolution", "frame_count", "file_size_bytes",
    "file_sha256", "creation_time", "mtime_utc", "configured_dataset_identity",
    "capture_session_id", "provenance_declaration",
    "known_parent_video", "known_derivation_operation", "lineage_independence",
    "decode_evidence", "proxy_feasibility", "oracle_feasibility", "workload_units_10s",
    "length_sufficient", "duplicate_group", "input_pool_eligible", "decision_reason",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        return {"error": result.stderr.strip() or f"ffprobe_exit_{result.returncode}"}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"error": f"invalid_ffprobe_json:{exc}"}
    video = next((row for row in payload.get("streams", []) if row.get("codec_type") == "video"), {})
    fmt = payload.get("format", {})
    return {
        "container": fmt.get("format_name", ""), "codec": video.get("codec_name", ""),
        "duration": float(fmt.get("duration") or video.get("duration") or 0.0),
        "frame_rate": video.get("avg_frame_rate") or video.get("r_frame_rate") or "",
        "width": int(video.get("width") or 0), "height": int(video.get("height") or 0),
        "frame_count": video.get("nb_frames") or "",
        "creation_time": (fmt.get("tags", {}).get("creation_time") or
                          video.get("tags", {}).get("creation_time") or ""),
    }


def representative_decode_probe(path: Path, duration: float) -> tuple[bool, str]:
    """Test the media/clip interface at start, middle, and tail.

    This is deliberately a technical compatibility probe, not an oracle call
    and not evidence that a particular query will be semantically eligible.
    """
    positions = sorted({0.0, max(0.0, duration / 2.0 - 0.5), max(0.0, duration - 2.0)})
    for position in positions:
        command = [
            "ffmpeg", "-v", "error", "-ss", f"{position:.6f}", "-i", str(path),
            "-t", "1", "-map", "0:v:0", "-an", "-f", "null", "-",
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode:
            return False, f"ffmpeg_sample_decode_at_{position:.3f}s:{result.stderr.strip()}"
    return True, "start_mid_tail_1s_decode_pass"


def provenance_declaration(path: Path) -> tuple[str, str, str, str]:
    """Read the explicit original-source declaration for a supplied video."""
    if USER_INPUT_ROOT not in path.parents:
        return "", "", "", ""
    sidecar = path.with_suffix(path.suffix + ".source.json")
    if not sidecar.is_file():
        return "", "MISSING", "", ""
    try:
        payload = json.loads(sidecar.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return "", f"INVALID:{exc}", "", ""
    session = str(payload.get("capture_session_id") or "").strip()
    kind = str(payload.get("source_kind") or "").strip()
    parent = str(payload.get("known_parent_video") or "").strip()
    operation = str(payload.get("known_derivation_operation") or "").strip()
    valid = bool(session and kind == "original_continuous_capture" and not parent and not operation)
    return session, ("PASS" if valid else "INVALID"), parent, operation


def qualifies_user_input(*, length_ok: bool, probe_error: bool,
                         declaration: str, technical_ok: bool) -> bool:
    """Pure decision rule used by the audit and exercised by its verifier."""
    return bool(length_ok and not probe_error and declaration == "PASS" and technical_ok)


def identify(path: Path) -> tuple[str, str, str, str, str]:
    text = str(path)
    name = path.stem
    if path.resolve() == CANONICAL_DATASET3.resolve():
        return "long_video_dataset3", "long_video_dataset3", "", "", "ESTABLISHED_INDEPENDENT_SOURCE"
    if path.name == "realcartest_5k.mp4":
        return "realcartest_5k", "realcartest_5k", str(ROOT / "try_or_no/videos/realcartest.mp4"), "first 5000 frames / 208.33-second prefix", "DERIVED_FROM_REPORTED_PARENT"
    if path.name == "test.mov":
        return "test", "test", "", "", "DISTINCT_FILE_BUT_SESSION_PROVENANCE_UNVERIFIED"
    if USER_INPUT_ROOT in path.parents:
        return path.stem, f"user_provided_{path.stem}", "", "", "USER_DECLARATION_REQUIRED"
    if "nexar/videos_hf" in text or "nexar/videos_smoke" in text:
        label = path.parent.name
        return f"nexar_{name}", f"nexar_train_{label}_{name}", "", "downloaded dataset clip", "COLLECTION_CLIP_SESSION_INDEPENDENCE_NOT_NEEDED_AFTER_LENGTH_FAIL"
    return name, name, "", "", "UNKNOWN"


def inspect(path: Path) -> dict:
    meta = ffprobe(path)
    source, identity, parent, operation, lineage = identify(path)
    stat = path.stat(); duration = float(meta.get("duration", 0.0)); units = int((duration + 9.999999) // 10)
    length_ok = duration >= MIN_WORKLOAD_SECONDS
    file_hash = sha256(path)
    session_id, declaration, declared_parent, declared_operation = provenance_declaration(path)
    if declared_parent:
        parent = declared_parent
    if declared_operation:
        operation = declared_operation
    user_candidate = USER_INPUT_ROOT in path.parents
    technical_ok = False
    technical_detail = "not_run"
    if user_candidate and length_ok and not meta.get("error"):
        technical_ok, technical_detail = representative_decode_probe(path, duration)
    if meta.get("error"):
        decode = f"FAIL:{meta['error']}"
    elif path.resolve() == CANONICAL_DATASET3.resolve():
        decode = "PASS:historical_full_sequential_read_100_percent_and_current_physical_runtime"
    elif path.name == "realcartest_5k.mp4":
        decode = "PASS:historical_full_5000_frame_decode"
    elif user_candidate and technical_ok:
        decode = f"PASS:representative_decode:{technical_detail}"
        lineage = "DECLARED_ORIGINAL_SOURCE__EXACT_DUPLICATE_AUDIT_PENDING"
    elif user_candidate:
        decode = f"FAIL:{technical_detail}" if technical_detail != "not_run" else "NOT_RUN:length_or_probe_gate"
    else:
        decode = "PASS:ffprobe_container_and_video_stream"
    if path.resolve() == CANONICAL_DATASET3.resolve():
        proxy, oracle = "PASS:existing_full_physical_proxy", "PASS:347_of_347_frozen_physical_oracle"
    elif not length_ok:
        proxy = oracle = "NOT_ASSESSED_FOR_POOL:length_fatal"
    elif user_candidate and declaration == "PASS" and technical_ok:
        proxy = "PASS_TECHNICAL:frozen_proxy_media_decode_interface_compatible"
        oracle = "PASS_TECHNICAL:frozen_oracle_clip_decode_interface_compatible"
    elif user_candidate:
        proxy = oracle = f"UNVERIFIED:user_source_declaration_{declaration.lower()}"
    else:
        proxy = oracle = "UNVERIFIED"
    eligible = bool(
        (path.resolve() == CANONICAL_DATASET3.resolve() and file_hash == CANONICAL_DATASET3_SHA256
         and length_ok and not meta.get("error"))
        or (user_candidate and qualifies_user_input(
            length_ok=length_ok, probe_error=bool(meta.get("error")),
            declaration=declaration, technical_ok=technical_ok))
    )
    if eligible:
        reason = "PASS:independent_long_source_decode_proxy_oracle_evidence"
    elif path.name == "realcartest_5k.mp4":
        reason = "REJECT:documented_prefix_of_missing_realcartest_parent"
    elif path.resolve() == CANONICAL_DATASET3.resolve():
        reason = "REJECT:canonical_dataset3_identity_or_decode_mismatch"
    elif user_candidate and declaration != "PASS":
        reason = f"REJECT:user_source_provenance_declaration_{declaration.lower()}"
    elif user_candidate and not technical_ok:
        reason = f"REJECT:representative_decode_failed:{technical_detail}"
    elif not length_ok:
        reason = f"REJECT:duration_{duration:.6f}s_below_{MIN_WORKLOAD_SECONDS:.0f}s_partial_proxy_requirement"
    elif meta.get("error"):
        reason = "REJECT:decode_probe_failed"
    else:
        reason = "REJECT:independence_or_physical_operator_feasibility_unverified"
    return {
        "absolute_path": str(path.resolve()), "exists": True, "source_name": source,
        "container": meta.get("container", ""), "codec": meta.get("codec", ""),
        "duration_seconds": round(duration, 6), "frame_rate": meta.get("frame_rate", ""),
        "width": meta.get("width", 0), "height": meta.get("height", 0),
        "resolution": f"{meta.get('width', 0)}x{meta.get('height', 0)}",
        "frame_count": meta.get("frame_count", ""), "file_size_bytes": stat.st_size,
        "file_sha256": file_hash, "creation_time": meta.get("creation_time", ""),
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "configured_dataset_identity": identity, "capture_session_id": session_id,
        "provenance_declaration": declaration, "known_parent_video": parent,
        "known_derivation_operation": operation, "lineage_independence": lineage,
        "decode_evidence": decode, "proxy_feasibility": proxy, "oracle_feasibility": oracle,
        "workload_units_10s": units, "length_sufficient": length_ok,
        "duplicate_group": "", "input_pool_eligible": eligible, "decision_reason": reason,
    }


def json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    roots = []
    candidates: list[Path] = []
    configured_environment_roots = {k: v for k, v in sorted(os.environ.items())
                                    if k.startswith(("GARC_", "DATASET_", "VIDEO_"))}
    search_roots = list(SEARCH_ROOTS)
    known_root_paths = {path.resolve() for path, _, _ in search_roots}
    for variable, value in configured_environment_roots.items():
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        if path.resolve() not in known_root_paths:
            search_roots.append((path, f"configured_environment_root:{variable}", True))
            known_root_paths.add(path.resolve())
    for path, role, searched in search_roots:
        count = 0
        if path.exists():
            discovered = ([path] if path.is_file() else path.rglob("*"))
            videos = [p for p in discovered if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES]
            count = len(videos)
            if searched:
                candidates.extend(p for p in videos if p.resolve() != HELDOUT_VIDEO.resolve())
        roots.append({"absolute_path": str(path), "exists": path.exists(), "role": role,
                      "searched_for_video_files": searched, "video_file_count": count})
    roots.append({"absolute_path": str(HELDOUT_ROOT), "exists": HELDOUT_ROOT.exists(),
                  "role": "existing_heldout_split", "searched_for_video_files": False,
                  "video_file_count": None, "reason": "explicitly excluded from byte and semantic access"})
    roots.append({"absolute_path": str(HELDOUT_VIDEO), "exists": HELDOUT_VIDEO.exists(),
                  "role": "canonical_heldout_video", "searched_for_video_files": False,
                  "video_file_count": None, "reason": "explicitly excluded by existing INPUT_MANIFEST; no labels/reference/method evaluation opened"})
    roots.extend([
        {"absolute_path": str(ROOT / "data/videos/sample.mp4"), "exists": (ROOT / "data/videos/sample.mp4").exists(),
         "role": "configured sample path", "searched_for_video_files": False, "video_file_count": None},
        {"absolute_path": str(ROOT / "data/videos/driv100_sample.mp4"), "exists": (ROOT / "data/videos/driv100_sample.mp4").exists(),
         "role": "configured DRIV100 sample path", "searched_for_video_files": False, "video_file_count": None},
        {"absolute_path": str(ROOT / "try_or_no/videos/test.mov"), "exists": (ROOT / "try_or_no/videos/test.mov").exists(),
         "role": "legacy manifest alias of canonical heldout", "searched_for_video_files": False, "video_file_count": None},
        {"absolute_path": str(ROOT / "data/realcam/heldout_v1/raw"), "exists": (ROOT / "data/realcam/heldout_v1/raw").exists(),
         "role": "configured heldout root", "searched_for_video_files": False, "video_file_count": None,
         "reason": "explicitly excluded"},
        {"absolute_path": "/mnt/resized_video/archie.mp4", "exists": Path("/mnt/resized_video/archie.mp4").exists(),
         "role": "legacy Everest configured path", "searched_for_video_files": False, "video_file_count": None},
    ])
    roots.append({"absolute_path": str(ROOT / "src/garc_eval/outputs/new_video_scout_gate_v1/config/scout_config.yaml"),
                  "exists": True, "role": "historical manifest naming dataset2/dataset3/realcartest", "searched_for_video_files": False, "video_file_count": None})
    json_write(OUT / "INPUT_ROOTS.json", {"audit_version": "PSVR_PHASE_A_v1", "repository": str(ROOT),
        "search_policy": "bounded repository data roots plus historical manifest paths; never whole-system scan",
        "configured_environment_roots": configured_environment_roots,
        "roots": roots, "heldout_opened": False,
        "heldout_opened_definition": "no heldout semantic reference, label, method evaluation, or tuning access"})

    # Preserve path-level duplicates; remove only accidental repeated discovery of the same path.
    candidates = sorted(set(p.resolve() for p in candidates))
    with ThreadPoolExecutor(max_workers=min(16, max(1, os.cpu_count() or 1))) as pool:
        rows = list(pool.map(inspect, candidates))
    for path, identity, duration, note in MISSING_REFERENCES:
        rows.append({"absolute_path": str(path), "exists": False, "source_name": identity,
            "container": "", "codec": "", "duration_seconds": duration, "frame_rate": "",
            "width": "", "height": "", "resolution": "", "frame_count": "", "file_size_bytes": 0,
            "file_sha256": "", "creation_time": "", "mtime_utc": "", "configured_dataset_identity": identity,
            "capture_session_id": "", "provenance_declaration": "NOT_APPLICABLE_MISSING",
            "known_parent_video": "", "known_derivation_operation": "", "lineage_independence": "HISTORICALLY_DISTINCT_BUT_BYTES_MISSING",
            "decode_evidence": "FAIL:bytes_missing", "proxy_feasibility": "FAIL:bytes_missing",
            "oracle_feasibility": "FAIL:bytes_missing", "workload_units_10s": int((duration + 9.999999) // 10),
            "length_sufficient": True, "duplicate_group": "", "input_pool_eligible": False,
            "decision_reason": f"REJECT:MISSING_BYTES:{note}"})
    # Metadata below are copied from the pre-existing heldout identity manifest;
    # the heldout bytes and semantic reference are not opened by this audit.
    rows.append({"absolute_path": str(HELDOUT_VIDEO), "exists": HELDOUT_VIDEO.exists(), "source_name": "test_heldout",
        "container": "mov,mp4,m4a,3gp,3g2,mj2", "codec": "h264", "duration_seconds": 43.043333,
        "frame_rate": "13320/323", "width": 2940, "height": 1912, "resolution": "2940x1912",
        "frame_count": 1776, "file_size_bytes": 212638897,
        "file_sha256": "282804b7eaeb83eb9c7fc1cff456dddec7eef80750d207e5907e8e1ca053fdcb",
        "creation_time": "", "mtime_utc": "", "configured_dataset_identity": "canonical_heldout",
        "capture_session_id": "", "provenance_declaration": "NOT_APPLICABLE_HELDOUT",
        "known_parent_video": "", "known_derivation_operation": "", "lineage_independence": "EXCLUDED_HELDOUT",
        "decode_evidence": "NOT_PROBED:heldout_excluded", "proxy_feasibility": "NOT_ASSESSED:heldout_excluded",
        "oracle_feasibility": "NOT_ASSESSED:heldout_excluded", "workload_units_10s": 5,
        "length_sufficient": False, "duplicate_group": "", "input_pool_eligible": False,
        "decision_reason": "EXCLUDE:canonical_heldout_and_too_short; metadata copied from existing identity manifest"})

    hashes: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["file_sha256"]:
            hashes[str(row["file_sha256"])].append(row)
    duplicate_groups = []
    number = 0
    for digest, members in sorted(hashes.items()):
        if len(members) > 1:
            number += 1; group = f"DUPLICATE_{number:03d}"
            for row in members: row["duplicate_group"] = group
            duplicate_groups.append({"group_id": group, "sha256": digest,
                                     "paths": [row["absolute_path"] for row in members]})
    session_groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("capture_session_id"):
            session_groups[str(row["capture_session_id"])].append(row)
    for row in rows:
        if not row.get("input_pool_eligible") or USER_INPUT_ROOT not in Path(str(row["absolute_path"])).parents:
            continue
        if row.get("duplicate_group"):
            row["input_pool_eligible"] = False
            row["decision_reason"] = "REJECT:exact_content_duplicate_of_existing_candidate"
            row["lineage_independence"] = "FAILED_EXACT_CONTENT_DUPLICATE"
        elif len(session_groups.get(str(row.get("capture_session_id")), [])) != 1:
            row["input_pool_eligible"] = False
            row["decision_reason"] = "REJECT:duplicate_capture_session_id"
            row["lineage_independence"] = "FAILED_DUPLICATE_DECLARED_SESSION"
        else:
            row["lineage_independence"] = "PASS_DECLARED_DISTINCT_CAPTURE_SESSION_AND_NO_EXACT_DUPLICATE"
            row["decision_reason"] = "PASS:user_provided_original_long_source_technical_operator_compatibility"
    rows.sort(key=lambda row: str(row["absolute_path"]))
    with (OUT / "VIDEO_CANDIDATES.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)

    nexar = [r for r in rows if str(r["source_name"]).startswith("nexar_") and r["exists"]]
    nexar_unique = len({r["file_sha256"] for r in nexar})
    nexar_durations = [float(r["duration_seconds"]) for r in nexar]
    accepted = [r for r in rows if r["input_pool_eligible"]]
    independence = {
        "definition": ["not crop/reencode/resolution/fps copy", "not overlapping same source session",
                       "sufficient duration for progressive partial-proxy", "stable decode",
                       "physical proxy and oracle executable"],
        "workload_length_derivation": {"A0_scan_batches_before_verify": 29, "batch_size": 4,
             "frozen_unit_seconds": 10, "units_needed_before_full_coverage": 117,
             "minimum_seconds_used": MIN_WORKLOAD_SECONDS, "recommended_seconds": RECOMMENDED_SECONDS},
        "user_input_qualification": {
            "placement_root": str(USER_INPUT_ROOT),
            "required_sidecar_suffix": ".source.json",
            "required_declaration": {
                "source_kind": "original_continuous_capture",
                "capture_session_id": "nonempty and unique",
                "known_parent_video": None,
                "known_derivation_operation": None
            },
            "technical_probe": "ffprobe plus start/middle/tail one-second physical decode",
            "independence_limit": "provider capture-session declaration plus exact-content duplicate audit; any uncertain lineage remains ineligible",
            "query_semantic_eligibility": "not assessed until frozen Phase B/C"
        },
        "eligible_sources": [{k: r[k] for k in ("source_name", "absolute_path", "duration_seconds", "file_sha256")} for r in accepted],
        "rejected_key_candidates": [
            {"source": "long_video_dataset2", "reason": "bytes absent; later role audit identifies in-cabin driver-facing view as semantically unsuitable"},
            {"source": "realcartest", "reason": "historical development/reference long-source bytes are absent"},
            {"source": "realcartest_5k", "reason": "documented first-5000-frame derivative of realcartest"},
            {"source": "test_heldout", "reason": "canonical heldout explicitly excluded; existing manifest also records only 43.043333 seconds"},
            {"source": "Nexar collection", "reason": f"{len(nexar)} paths / {nexar_unique} unique files, duration {min(nexar_durations):.6f}-{max(nexar_durations):.6f}s; each <=5 frozen units"},
            {"source": "DrivingDojo-mini archive", "reason": "archive has no video-container entries; image-sequence sessions are approximately 10-26 seconds"},
        ],
        "content_identity_evidence": {
                                      "full_file_sha256_computed_by_this_audit": len([r for r in rows if r["file_sha256"] and r["source_name"] != "test_heldout"]),
                                      "heldout_identity_hashes_copied_from_existing_manifest": 1,
                                      "duplicate_groups": duplicate_groups,
                                      "dataset2_role_artifact": "src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/reports/DATASET2_ROLE_ANALYSIS.md",
                                      "realcartest_lineage_artifact": "AQP_Algorithm_Invention_Sprint_v1/operator_validation/realcartest_event_enumerate_v2/video/DERIVED_SLICE_LINEAGE.csv"},
        "nexar_duration_audit": {"path_count": len(nexar), "unique_file_count": nexar_unique, "minimum_seconds": min(nexar_durations),
                                 "maximum_seconds": max(nexar_durations),
                                 "over_60_seconds": sum(d > 60 for d in nexar_durations),
                                 "over_minimum_workload_seconds": sum(d >= MIN_WORKLOAD_SECONDS for d in nexar_durations)},
        "heldout_opened": False,
        "heldout_opened_definition": "no heldout semantic reference, label, method evaluation, or tuning access",
    }
    json_write(OUT / "SOURCE_INDEPENDENCE_AUDIT.json", independence)
    json_write(OUT / "DERIVATION_GROUPS.json", {"groups": [
        {"group_id": "dataset3_family", "canonical_source": str(CANONICAL_DATASET3), "candidate_source_eligible": True,
         "excluded_derivatives": ["outputs/probe_set_v1/probe_media/clips", "outputs/video_feature_precompute_runtime_v1/clips", "src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/review_media/clips"]},
        {"group_id": "realcartest_family", "canonical_source": str(ROOT / "try_or_no/videos/realcartest.mp4"), "canonical_exists": False,
         "members": [{"path": str(ROOT / "try_or_no/videos/realcartest_5k.mp4"), "relation": "reported_first_5000_frames"},
                     {"path": "datasets/clips/clips/round1_stride10 and round2_5k_*", "relation": "short clips from realcartest_5k"}]},
        {"group_id": "test_heldout_family", "canonical_source": str(HELDOUT_VIDEO), "candidate_source_eligible": False,
         "reason": "existing canonical heldout; explicitly excluded (also too short)", "excluded_derivatives": ["datasets/clips/clips/round1_extra"]},
        {"group_id": "nexar_collection", "path_count": len(nexar), "unique_file_count": nexar_unique, "candidate_source_eligible": False,
         "reason": "individual independent clips are too short", "exact_duplicate_groups": duplicate_groups},
        {"group_id": "drivingdojo_mini", "archive": str(ROOT / "datasets/DrivingDojo-mini/drivingdojo_mini.zip"),
         "candidate_source_eligible": False, "reason": "no video containers; short image-sequence sessions"}],
         "heldout_opened": False,
         "heldout_opened_definition": "no heldout semantic reference, label, method evaluation, or tuning access"})

    decision = "PASS" if len(accepted) >= 3 else "INSUFFICIENT"
    pool = {"BENCHMARK_INPUT_POOL": decision, "required_independent_source_videos": 3,
            "eligible_independent_source_videos": len(accepted), "additional_sources_needed": max(0, 3-len(accepted)),
            "eligible_source_ids": [r["source_name"] for r in accepted],
            "DEV_BENCHMARK_UNBLOCK": "NOT_RUN_INPUT_INSUFFICIENT" if decision == "INSUFFICIENT" else "READY_FOR_PHASE_B",
            "AUTONOMOUS_RESEARCH_STATUS": "PAUSED_INPUT_REQUIRED" if decision == "INSUFFICIENT" else "RUNNING",
            "AUTONOMOUS_RESEARCH": "PAUSED_INPUT_REQUIRED" if decision == "INSUFFICIENT" else "RUNNING",
            "PSVR_METHOD_USABILITY": "NOT_YET",
            "PSVR_CORE_INNOVATION": "BLOCKED" if decision == "INSUFFICIENT" else "WEAK",
            "next_exact_command": "python scripts/audit_psvr_dev_inputs.py", "heldout_opened": False,
            "heldout_opened_definition": "no heldout semantic reference, label, method evaluation, or tuning access"}
    json_write(OUT / "INPUT_POOL_DECISION.json", pool)
    request = f"""# PSVR development input request

`BENCHMARK_INPUT_POOL = {decision}`

## Current valid input

- `long_video_dataset3.mp4`: 3462.93 seconds, 347 frozen 10-second units, stable decode/proxy/oracle evidence.

## Missing input

The development pool needs **{max(0, 3-len(accepted))} additional independent source videos**. Existing references to `long_video_dataset2.mp4` and `realcartest.mp4` do not help because their bytes are absent; dataset2 was also later identified as an in-cabin driver-facing view unsuitable for ego-path queries.

## Rejected local candidates

- `realcartest_5k.mp4`: documented first-5000-frame derivative of missing `realcartest.mp4`.
- `test.mov`: existing canonical held-out video, explicitly excluded; its manifest also records only 43.04 seconds.
- Nexar: {len(nexar)} ffprobe-visible paths / {nexar_unique} unique clips, {min(nexar_durations):.2f}-{max(nexar_durations):.2f} seconds; every clip has at most five 10-second units.
- DrivingDojo-mini: local archive contains short image-sequence sessions, not continuous video containers.
- Any clips/reencodes/crops under outputs, experiments, or `datasets/clips`: derivatives, not independent sources.

## Files to provide

- Supported containers: MP4, MOV, MKV, AVI, WebM, or M4V with a normally decodable video stream.
- Recommended minimum duration: **30 minutes**; hard workload screen is 1200 seconds so 29×4 A0 scans do not exhaust the video.
- Prefer forward-facing road views from different capture sessions, with varied scene categories, event layouts, weather/lighting, and traffic density.
- Do not provide crops, reencodes, frame-rate/resolution conversions, overlapping segments, or splits of existing sources.
- Place files in: `{ROOT / 'data/realcam/psvr_dev_inputs/'}`.

For each `name.mp4`, also provide `name.mp4.source.json` so independence is explicit:

```json
{{
  "source_kind": "original_continuous_capture",
  "capture_session_id": "a unique capture/session identifier",
  "known_parent_video": null,
  "known_derivation_operation": null
}}
```

The audit rejects a missing/invalid declaration, repeated session identifier, or exact-content duplicate. Query semantics and reference eligibility are assessed only after this source-input gate passes.

No query or algorithm work will resume until this input gate passes. Held-out semantic/reference evaluation remains unopened.

## Resume

```bash
python scripts/audit_psvr_dev_inputs.py
```
"""
    (OUT / "INPUT_REQUEST.md").write_text(request)
    print(json.dumps(pool, indent=2))


if __name__ == "__main__":
    main()
