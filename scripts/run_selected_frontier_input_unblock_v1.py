#!/usr/bin/env python3
"""Blind, non-semantic input-unblock pipeline for exactly three videos."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data/realcam/selected_frontier_calibration_inputs"
OUT = ROOT / "outputs/selected_frontier_conversion_v1/input_unblock"
PROTOCOL = ROOT / "docs/SELECTED_FRONTIER_INPUT_UNBLOCK_PROTOCOL_V1.md"
CONTRACT = ROOT / "docs/SELECTED_FRONTIER_CONVERSION_CALIBRATION_CONTRACT_V1.md"
REGISTRY = OUT / "candidate_registration_ledger.jsonl"
FAILURES = OUT / "eligibility_failure_ledger.jsonl"
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
BASELINES = [
    ("V0_DESIGN_ONLY", ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"),
    ("V1_DESIGN_ONLY", ROOT / "data/realcam/psvr_dev_inputs/驾驶-大理.mp4"),
    ("EXISTING_NEW_SOURCE_PRELIMINARY", ROOT / "data/realcam/long_video_data/杭州.mp4"),
]
KNOWN_EXCLUSIONS = [
    (ROOT / "data/realcam/long_video_data/杭州YouTube.mp4", "SAME_CONTENT_AS_HANGZHOU_AND_DECODE_FAILURE"),
    (ROOT / "data/realcam/long_video_data/杭州YouTube.normalized.mp4", "DERIVATIVE_AND_DECODE_FAILURE"),
    (ROOT / "data/realcam/long_video_data/杭州YouTube.normalized.transcoded.mp4", "DERIVATIVE_INCOMPLETE_TIMELINE"),
    (ROOT / "src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/review_media/clips/review_review_0102_0p0_1200p0.mp4", "V0_DERIVED_REVIEW_CLIP"),
    (ROOT / "try_or_no/test.mov", "CANONICAL_HELDOUT_AND_TOO_SHORT"),
    (ROOT / "try_or_no/videos/realcartest_5k.mp4", "REALCARTEST_DERIVATIVE_AND_TOO_SHORT"),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def jdump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def parse_utc(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def media_probe(path: Path) -> dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "format=duration:stream=width,height,avg_frame_rate,nb_frames,time_base,start_time,duration",
           "-of", "json", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        return {"ok": False, "error": p.stderr[-2000:]}
    try:
        raw = json.loads(p.stdout)
        stream = raw["streams"][0]
        return {
            "ok": True, "duration_sec": float(raw["format"]["duration"]),
            "width": int(stream["width"]), "height": int(stream["height"]),
            "avg_frame_rate": stream.get("avg_frame_rate"),
            "nb_frames": int(stream["nb_frames"]) if stream.get("nb_frames", "N/A") != "N/A" else None,
            "stream_start_time": stream.get("start_time"), "stream_duration": stream.get("duration"),
        }
    except Exception as exc:
        return {"ok": False, "error": f"probe_parse_error:{exc}"}


def full_decode(path: Path) -> dict[str, Any]:
    p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                        "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True)
    return {"pass": p.returncode == 0 and not p.stderr.strip(), "returncode": p.returncode,
            "stderr_tail": p.stderr[-4000:]}


def timeline_audit(path: Path, container_duration: float) -> dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
           "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0", str(path)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    points: list[float] = []
    assert p.stdout is not None
    for line in p.stdout:
        token = line.split(",", 1)[0].strip()
        try:
            points.append(float(token))
        except ValueError:
            pass
    stderr = p.stderr.read() if p.stderr else ""
    code = p.wait()
    if code or len(points) < 2:
        return {"pass": False, "packet_count": len(points), "error": stderr[-2000:] or "insufficient_pts"}
    diffs = [b - a for a, b in zip(points, points[1:])]
    positive = [x for x in diffs if x > 0]
    median_step = statistics.median(positive) if positive else math.inf
    threshold = max(2.0, 10.0 * median_step)
    max_gap = max(positive) if positive else math.inf
    nonmonotonic = sum(x < -1e-6 for x in diffs)
    covered = points[-1] - points[0]
    duration_error = abs(covered - container_duration)
    passed = nonmonotonic == 0 and max_gap <= threshold and duration_error <= max(2.0, 0.01 * container_duration)
    return {"pass": passed, "packet_count": len(points), "first_pts": points[0], "last_pts": points[-1],
            "covered_sec": covered, "container_duration_sec": container_duration,
            "duration_abs_error_sec": duration_error, "median_positive_step_sec": median_step,
            "gap_threshold_sec": threshold, "max_positive_gap_sec": max_gap,
            "nonmonotonic_count": nonmonotonic}


def seek_audit(path: Path, digest: str, duration: float) -> dict[str, Any]:
    rng = random.Random(int(digest[:16], 16))
    times = sorted(rng.uniform(1.0, max(1.001, duration - 1.0)) for _ in range(12))
    attempts = []
    for t in times:
        p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.6f}",
                            "-i", str(path), "-frames:v", "1", "-f", "null", "-"],
                           capture_output=True, text=True)
        attempts.append({"timestamp_sec": round(t, 6), "pass": p.returncode == 0 and not p.stderr.strip(),
                         "returncode": p.returncode, "stderr_tail": p.stderr[-1000:]})
    return {"pass": all(x["pass"] for x in attempts), "seed_sha256_prefix": digest[:16], "attempts": attempts}


def frame_signature(path: Path, timestamp: float) -> str | None:
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{timestamp:.6f}", "-i", str(path),
           "-frames:v", "1", "-vf", "scale=16:16,format=gray", "-f", "rawvideo", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode or len(p.stdout) != 256:
        return None
    values = list(p.stdout)
    med = statistics.median(values)
    bits = "".join("1" if x >= med else "0" for x in values)
    return f"{int(bits, 2):064x}"


def signatures(path: Path, duration: float) -> list[dict[str, Any]]:
    """Extract a 16x16 perceptual signature every 30 seconds in one decode."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vf",
           "fps=1/30,scale=16:16,format=gray", "-f", "rawvideo", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode:
        return []
    result = []
    for i in range(len(p.stdout) // 256):
        values = list(p.stdout[i * 256:(i + 1) * 256])
        med = statistics.median(values)
        bits = "".join("1" if x >= med else "0" for x in values)
        result.append({"sample_index": i, "timestamp_sec": min(duration, i * 30.0),
                       "signature": f"{int(bits, 2):064x}"})
    return result


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def pair_audit(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if left["sha256"] == right["sha256"]:
        reasons.append("EXACT_FILE_DUPLICATE")
    ls, rs = left.get("source", {}), right.get("source", {})
    if ls.get("capture_session_id") and ls.get("capture_session_id") == rs.get("capture_session_id"):
        reasons.append("SHARED_CAPTURE_SESSION_ID")
    left_names = {left["path"], Path(left["path"]).name, left["sha256"]}
    right_names = {right["path"], Path(right["path"]).name, right["sha256"]}
    if ls.get("known_parent_video") in right_names or rs.get("known_parent_video") in left_names:
        reasons.append("DECLARED_PARENT_RELATION")
    matches = []
    offset_counts: dict[int, int] = {}
    for a in left.get("signatures", []):
        for b in right.get("signatures", []):
            dist = hamming(a["signature"], b["signature"])
            if dist <= 4:
                offset_bin = round((b["timestamp_sec"] - a["timestamp_sec"]) / 30.0)
                offset_counts[offset_bin] = offset_counts.get(offset_bin, 0) + 1
                matches.append({"left_time_sec": a["timestamp_sec"], "right_time_sec": b["timestamp_sec"],
                                "offset_bin_30sec": offset_bin, "hamming": dist})
    max_offset_support = max(offset_counts.values(), default=0)
    if max_offset_support >= 3:
        reasons.append("OFFSET_CONSISTENT_CONTENT_OVERLAP")
    return {"left": left["path"], "right": right["path"], "exact_hash_equal": left["sha256"] == right["sha256"],
            "signature_matches_le4": matches, "max_offset_consistent_match_count": max_offset_support,
            "failure_reasons": reasons,
            "pass": not reasons, "limitation": "Sparse perceptual sampling cannot prove absence of all overlap."}


def provenance_audit(item: dict[str, Any], all_session_ids: list[str]) -> dict[str, Any]:
    s = item["source"]
    reasons = []
    required = ["source_kind", "capture_session_id", "registration_utc", "known_parent_video",
                "known_derivation_operation", "target_event_information_used_for_selection", "video_sha256",
                "is_event_centered", "is_original_continuous_video"]
    for key in required:
        if key not in s:
            reasons.append(f"MISSING_FIELD:{key}")
    if s.get("video_sha256") != item["sha256"]:
        reasons.append("HASH_BINDING_MISMATCH")
    if s.get("source_kind") != "original_continuous_capture" or s.get("is_original_continuous_video") is not True:
        reasons.append("NOT_DECLARED_ORIGINAL_CONTINUOUS_CAPTURE")
    if s.get("known_parent_video") is not None or s.get("known_derivation_operation") is not None:
        reasons.append("DECLARED_DERIVATIVE")
    if s.get("is_event_centered") is not False:
        reasons.append("EVENT_CENTERED_NOT_FALSE")
    if s.get("target_event_information_used_for_selection") is not False:
        reasons.append("TARGET_SELECTION_NOT_FALSE")
    sid = s.get("capture_session_id")
    if not isinstance(sid, str) or not sid.strip():
        reasons.append("INVALID_CAPTURE_SESSION_ID")
    elif all_session_ids.count(sid) > 1:
        reasons.append("DUPLICATE_CAPTURE_SESSION_ID")
    if parse_utc(s.get("registration_utc")) is None:
        reasons.append("INVALID_REGISTRATION_UTC")
    return {"path": item["path"], "sidecar": item["sidecar"], "declared": s,
            "failure_reasons": sorted(set(reasons)), "pass": not reasons}


def register_candidates() -> list[dict[str, Any]]:
    INBOX.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    REGISTRY.touch(exist_ok=True)
    FAILURES.touch(exist_ok=True)
    old = read_jsonl(REGISTRY)
    identities = {(r["path_at_registration"], r["candidate_sha256"]) for r in old}
    next_order = max((int(r["registration_order"]) for r in old), default=0) + 1
    discovered = sorted(p for p in INBOX.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES)
    new_rows = []
    for path in discovered:
        digest = sha256(path)
        relpath = str(path.relative_to(ROOT))
        if (relpath, digest) in identities:
            continue
        sidecar = Path(str(path) + ".source.json")
        source = read_json(sidecar) if sidecar.exists() else {}
        row = {"candidate_sha256": digest, "path_at_registration": relpath,
               "filename": path.name, "bytes": path.stat().st_size, "discovered_utc": now(),
               "declared_registration_utc": source.get("registration_utc"),
               "normalized_registration_utc": parse_utc(source.get("registration_utc")),
               "sidecar_at_registration": str(sidecar.relative_to(ROOT)) if sidecar.exists() else None,
               "semantic_information_opened": False}
        new_rows.append(row)
    new_rows.sort(key=lambda r: (r["normalized_registration_utc"] or "9999-12-31T23:59:59+00:00",
                                 r["filename"], r["candidate_sha256"]))
    for row in new_rows:
        row["registration_order"] = next_order
        next_order += 1
        append_jsonl(REGISTRY, row)
    return read_jsonl(REGISTRY)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register-only", action="store_true")
    args = parser.parse_args()
    created = now()
    registry = register_candidates()
    if args.register_only:
        print(f"registered candidates: {len(registry)}")
        return

    inventory: list[dict[str, Any]] = []
    technical: dict[str, Any] = {}
    content_items: list[dict[str, Any]] = []
    for role, path in BASELINES:
        digest = sha256(path)
        probe = media_probe(path)
        sidecar = Path(str(path) + ".source.json")
        source = read_json(sidecar)
        inventory.append({"selection_order": "", "role": role, "path": str(path.relative_to(ROOT)),
                          "sha256": digest, "bytes": path.stat().st_size,
                          "duration_sec": probe.get("duration_sec"), "capture_session_id": source.get("capture_session_id"),
                          "eligibility_status": role})
        content_items.append({"path": str(path.relative_to(ROOT)), "sha256": digest,
                              "source": source,
                              "signatures": signatures(path, probe["duration_sec"]) if registry else []})

    for path, reason in KNOWN_EXCLUSIONS:
        if not path.exists():
            continue
        probe = media_probe(path)
        inventory.append({"selection_order": "", "role": "PRIOR_PERMANENT_EXCLUSION",
                          "path": str(path.relative_to(ROOT)), "sha256": sha256(path),
                          "bytes": path.stat().st_size, "duration_sec": probe.get("duration_sec"),
                          "capture_session_id": "", "eligibility_status": reason})

    ordered = sorted(registry, key=lambda r: int(r["registration_order"]))
    candidate_items = []
    for index, reg in enumerate(ordered, 1):
        path = ROOT / reg["path_at_registration"]
        current_hash = sha256(path) if path.exists() else None
        sidecar = Path(str(path) + ".source.json")
        source = read_json(sidecar) if sidecar.exists() else {}
        item = {"order": index, "path": reg["path_at_registration"], "sidecar": str(sidecar.relative_to(ROOT)),
                "sha256": reg["candidate_sha256"], "current_sha256": current_hash, "source": source}
        probe = media_probe(path) if path.exists() and current_hash == reg["candidate_sha256"] else {"ok": False, "error": "MISSING_OR_BYTES_CHANGED"}
        item["probe"] = probe
        if probe.get("ok"):
            item["signatures"] = signatures(path, probe["duration_sec"])
        else:
            item["signatures"] = []
        candidate_items.append(item)
        content_items.append(item)

    session_ids = [x["source"].get("capture_session_id") for x in candidate_items + content_items[:3]
                   if isinstance(x["source"].get("capture_session_id"), str)]
    provenance_rows = [provenance_audit(x, session_ids) for x in candidate_items]
    provenance_by_path = {x["path"]: x for x in provenance_rows}

    for item in candidate_items:
        probe = item["probe"]
        if probe.get("ok"):
            duration_pass = probe["duration_sec"] >= 1200.0
            decode = full_decode(ROOT / item["path"])
            timeline = timeline_audit(ROOT / item["path"], probe["duration_sec"])
            seeks = seek_audit(ROOT / item["path"], item["sha256"], probe["duration_sec"])
        else:
            duration_pass, decode, timeline, seeks = False, {"pass": False, "error": probe.get("error")}, {"pass": False, "error": probe.get("error")}, {"pass": False, "error": probe.get("error")}
        technical[item["path"]] = {"probe": probe, "duration_pass": duration_pass,
                                   "complete_decode": decode, "continuous_timeline": timeline,
                                   "random_seek": seeks,
                                   "pass": bool(probe.get("ok") and duration_pass and decode["pass"] and timeline["pass"] and seeks["pass"])}

    pairs = []
    for i, left in enumerate(content_items):
        for right in content_items[i + 1:]:
            if left.get("signatures") and right.get("signatures"):
                pairs.append(pair_audit(left, right))
    pair_fail_paths: dict[str, list[str]] = {}
    for pair in pairs:
        if not pair["pass"]:
            pair_fail_paths.setdefault(pair["left"], []).extend(pair["failure_reasons"])
            pair_fail_paths.setdefault(pair["right"], []).extend(pair["failure_reasons"])

    accepted = []
    outcomes = []
    existing_failures = read_jsonl(FAILURES)
    existing_failure_keys = {(x["candidate_sha256"], x["failure_code"]) for x in existing_failures}
    for item in candidate_items:
        reasons = []
        if not technical[item["path"]]["pass"]:
            reasons.append("TECHNICAL_GATE_FAILED")
        reasons.extend(provenance_by_path[item["path"]]["failure_reasons"])
        reasons.extend(pair_fail_paths.get(item["path"], []))
        reasons = sorted(set(reasons))
        if not reasons and len(accepted) < 3:
            accepted.append(item)
            status = f"QUALIFYING_ADDITIONAL_{len(accepted)}"
        elif not reasons:
            status = "QUALIFYING_RESERVE_NOT_SELECTED"
        else:
            status = "PERMANENTLY_RECORDED_ELIGIBILITY_FAILURE"
            for reason in reasons:
                key = (item["sha256"], reason)
                if key not in existing_failure_keys:
                    append_jsonl(FAILURES, {"recorded_utc": created, "candidate_sha256": item["sha256"],
                                           "path": item["path"], "failure_code": reason,
                                           "replacement_authorized": True,
                                           "replacement_basis": "PREREGISTERED_TECHNICAL_OR_PROVENANCE_FAILURE_ONLY"})
                    existing_failure_keys.add(key)
        outcomes.append({"selection_order": item["order"], "path": item["path"], "sha256": item["sha256"],
                         "status": status, "failure_reasons": reasons})
        inventory.append({"selection_order": item["order"], "role": "INBOX_CANDIDATE", "path": item["path"],
                          "sha256": item["sha256"], "bytes": (ROOT / item["path"]).stat().st_size if (ROOT / item["path"]).exists() else None,
                          "duration_sec": item["probe"].get("duration_sec"),
                          "capture_session_id": item["source"].get("capture_session_id"), "eligibility_status": status})

    inventory.extend([
        {"selection_order": "", "role": "OFFICIAL_DATASET_NOT_LOCAL", "path": "HDD_OFFICIAL_REQUEST_ONLY", "sha256": "", "bytes": "", "duration_sec": "", "capture_session_id": "", "eligibility_status": "NOT_AUDITABLE_NO_LOCAL_SESSION_FILES"},
        {"selection_order": "", "role": "OFFICIAL_DATASET_NOT_LOCAL", "path": "HSD_OFFICIAL_REQUEST_ONLY", "sha256": "", "bytes": "", "duration_sec": "", "capture_session_id": "", "eligibility_status": "NOT_AUDITABLE_NO_LOCAL_SESSION_FILES"},
    ])
    with (OUT / "candidate_video_inventory.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["selection_order", "role", "path", "sha256", "bytes", "duration_sec", "capture_session_id", "eligibility_status"])
        writer.writeheader(); writer.writerows(inventory)
    with (OUT / "blind_selection_order.csv").open("w", newline="") as f:
        fields = ["selection_order", "path", "sha256", "status", "failure_reasons"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for row in outcomes:
            writer.writerow({**row, "failure_reasons": "|".join(row["failure_reasons"])})

    hdd_local = any("hdd" in {p.lower() for p in Path(x["path"]).parts} for x in candidate_items)
    hsd_local = any("hsd" in {p.lower() for p in Path(x["path"]).parts} for x in candidate_items)
    official = {
        "HDD": {"local_assets_found": hdd_local, "official_total_hours": 104,
                "official_description": "real human driving collected with an instrumented vehicle",
                "access": "NONCOMMERCIAL_UNIVERSITY_AFFILIATION_AND_UNIVERSITY_EMAIL_REQUEST_REQUIRED",
                "official_url": "https://usa.honda-ri.com/hdd",
                "qualification": "NOT_COUNTED_NO_LOCAL_FILE_SESSION_DURATION_OR_PROVENANCE_AUDIT"},
        "HSD": {"local_assets_found": hsd_local, "official_total_hours": 80,
                "official_description": "diverse high quality driving video data clips",
                "access": "NONCOMMERCIAL_UNIVERSITY_AFFILIATION_AND_UNIVERSITY_EMAIL_REQUEST_REQUIRED",
                "official_url": "https://usa.honda-ri.com/hsd",
                "qualification": "NOT_COUNTED_AGGREGATE_HOURS_DO_NOT_ESTABLISH_A_1200_SECOND_CONTINUOUS_SESSION"},
    }
    jdump(OUT / "provenance_audit.json", {"created_utc": created, "protocol_sha256": sha256(PROTOCOL),
          "contract_sha256": sha256(CONTRACT), "pipeline_semantic_information_opened": False,
          "selected_frontier_semantic_references_opened": False,
          "incidental_unrelated_semantic_text_exposure": True,
          "selection_contamination": False,
          "candidate_results": provenance_rows, "official_dataset_audit": official,
          "permanent_failure_ledger": str(FAILURES.relative_to(ROOT))})
    jdump(OUT / "decode_seek_audit.json", {"created_utc": created, "candidate_results": technical,
          "full_decode_executed_count": sum(1 for x in technical.values() if "returncode" in x["complete_decode"]),
          "semantic_information_opened": False})
    jdump(OUT / "pairwise_content_independence.json", {"created_utc": created,
          "method": "exact SHA-256, declared lineage/session, and 30-second 16x16 grayscale perceptual signatures with offset-consistent overlap detection",
          "pairs": pairs, "semantic_information_opened": False,
          "limitation": "Passing sparse content comparison does not prove independence; valid provenance remains mandatory."})

    passed = len(accepted) == 3
    decision = {"created_utc": created, "INPUT_GATE": "PASS" if passed else "BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS",
                "EXISTING_QUALIFYING_NEW_VIDEO_COUNT": 1, "ADDITIONAL_REQUIRED": 3,
                "ADDITIONAL_QUALIFYING_SELECTED_COUNT": len(accepted),
                "TOTAL_QUALIFYING_NEW_INDEPENDENT_VIDEOS": 1 + len(accepted),
                "SELECTED_ADDITIONAL_VIDEOS": [x["path"] for x in accepted],
                "SELECTED_FRONTIER_DATASET": "AUTHORIZED_FOR_SEPARATE_BUILD_STAGE" if passed else "NOT_BUILT",
                "CALIBRATION_MODELS": "NOT_RUN",
                "SELECTED_FRONTIER_SEMANTIC_REFERENCES_OPENED": False,
                "PIPELINE_SEMANTIC_INFORMATION_OPENED": False,
                "INCIDENTAL_UNRELATED_SEMANTIC_TEXT_EXPOSURE": True,
                "SELECTION_CONTAMINATION": False,
                "NEW_ORACLE_CALLS": 0, "RESEARCH_GATES_MODIFIED": False,
                "NEXT_ACTION": "FREEZE_FOUR_SOURCE_ROLES_AND_REQUEST_COMPUTE_AUTHORIZATION" if passed else f"PROVIDE_{3-len(accepted)}_ADDITIONAL_QUALIFYING_VIDEOS"}
    jdump(OUT / "input_gate_decision.json", decision)
    report = f"""# Input Unblock Report\n\n## Decision\n\n`INPUT_GATE = {decision['INPUT_GATE']}`\n\nThe immutable blind registry contains {len(ordered)} candidate byte identities. {len(accepted)} of the required three additional sources qualify, giving {1+len(accepted)} of four required new independent sources in total. The selected-Frontier dataset was not built and C0-C4 were not run. The pipeline opened no semantic reference, event count, candidate outcome, or selected-Frontier outcome.\n\n## Boundary disclosure\n\nBefore the pipeline ran, an overly broad local text search for HDD/HSD evidence returned snippets from unrelated old VLM outputs. No selected-Frontier reference was opened and the candidate registry was empty, so selection contamination is false; nevertheless the unrelated semantic-text exposure is explicitly recorded rather than described as zero exposure.\n\n## HDD/HSD audit\n\nHonda's official HDD page reports 104 aggregate hours and its HSD page reports 80 aggregate hours of video clips. Both require a non-commercial university-affiliated request. No HDD/HSD session media or provenance sidecars are present locally, so neither is counted. Aggregate hours do not establish that an individual file is a continuous session of at least 1,200 seconds. If obtained legitimately, every actual session file must enter the immutable registry and pass the same full decode, timeline, seek, provenance, and pairwise-independence gates.\n\n## Replacement rule\n\nEvery failure is retained in `eligibility_failure_ledger.jsonl`. Replacement is allowed only after a recorded preregistered technical/provenance failure; semantic performance can never justify replacement.\n"""
    (OUT / "INPUT_UNBLOCK_REPORT.md").write_text(report)


if __name__ == "__main__":
    main()
