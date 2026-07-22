#!/usr/bin/env python3
"""Audit and freeze the pre-inference MF-PSVR independent training pool.

This stage performs no detector, tracker, VLM, oracle, or semantic inspection.
It hashes local media, validates provider download metadata, probes container
metadata, quarantines sources without direct license evidence, and writes the
frozen acquisition protocol that must precede expensive Cycle-1 work.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.mf_psvr.stage_a import selection_spec  # noqa: E402
from garc_eval.mf_psvr.training_pool import (  # noqa: E402
    QUERY_TYPE_PROJECTIONS,
    deterministic_split,
    frame_bounds,
    project_generic_label,
    unit_windows,
)
from garc_eval.psvr_runtime.two_video_physical_oracle import (  # noqa: E402
    project_generic_label as deployed_project_generic_label,
)


DEFAULT_OUT = (
    ROOT
    / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
)
NEXAR_ROOT = ROOT / "datasets/casq_external/nexar/videos_hf/train"
NEXAR_CACHE = ROOT / "datasets/casq_external/nexar/videos_hf/.cache/huggingface/download"
NEXAR_METADATA = ROOT / "datasets/casq_external/nexar/hf_metadata_probe/train"
DD_ZIP = ROOT / "datasets/DrivingDojo-mini/drivingdojo_mini.zip"
DD_DOWNLOAD_METADATA = (
    ROOT / "datasets/DrivingDojo-mini/.cache/huggingface/download/drivingdojo_mini.zip.metadata"
)
QUERY_MANIFEST = ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/QUERY_MANIFEST.json"
FROZEN_V1_UNITS = ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/units/V1_units.csv"
FROZEN_V0_UNITS = (
    ROOT
    / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
    "clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv"
)
VIDEO_MANIFEST = ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/VIDEO_MANIFEST.json"
ORACLE_CONFIG = ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/raw_oracle/V1/ORACLE_CONFIG.json"
ORACLE_RUNTIME_CONFIG = ROOT / "outputs/psvr_two_video_loop/deadlines/ORACLE_RUNTIME_CONFIG.json"
TASK_DEADLINE_MANIFEST = ROOT / "outputs/psvr_two_video_loop/deadlines/TASK_DEADLINE_MANIFEST.json"
PROXY_PREREGISTRATION = (
    ROOT / "outputs/psvr_two_video_loop/proxy_finalization/H_PROXY_2VIDEO_PREREGISTRATION.json"
)
PROXY_IMPLEMENTATION_FREEZE = (
    ROOT / "outputs/psvr_two_video_loop/proxy_finalization/PROXY_IMPLEMENTATION_FREEZE.json"
)
Y8_COST = ROOT / "outputs/psvr_two_video_loop/proxy_finalization/physical_cost/Y8_PHYSICAL_COST.json"
ORACLE_PROFILE_INITIALIZATION = (
    ROOT / "outputs/psvr_two_video_loop/deadlines/PROFILE_INITIALIZATION.json"
)
TRAINING_POOL_HELPER = ROOT / "src/garc_eval/mf_psvr/training_pool.py"
STAGE_A_SELECTOR = ROOT / "src/garc_eval/mf_psvr/stage_a.py"
CANDIDATE_RUNNER = ROOT / "scripts/run_mf_psvr_training_pool_candidates.py"
STAGE_A_FREEZER = ROOT / "scripts/freeze_mf_psvr_stage_a_sample.py"
SHORT_CLIP_PROFILE_RUNNER = ROOT / "scripts/profile_mf_psvr_short_clip_overhead.py"
SHORT_CLIP_PROFILE = DEFAULT_OUT / "SHORT_CLIP_OVERHEAD_PROFILE.json"
LEGACY_INDEPENDENCE_AUDIT = (
    ROOT / "outputs/psvr_autonomous_research/benchmark_unblock/SOURCE_INDEPENDENCE_AUDIT.json"
)
OLD_NEXAR_VLM_REPORT = (
    ROOT
    / "experiments/clip_aqp/clip_aqp_phase1_nexar_candidate_v2/reports/"
    "VLM_MICRO_AUDIT_PROVENANCE.md"
)

NEXAR_REPOSITORY = "nexar-ai/nexar_collision_prediction"
NEXAR_REVISION = "aa97deda5a59f00bb7187739053b7c72e14374df"
NEXAR_LICENSE_SHA256 = "9c62949a76b4a3039023a93a31aac964847cbcfcac8376daaa541cc620788824"
NEXAR_API_SNAPSHOT_SHA256 = "cf71460f26da0b9006cfbaab59d785b8d98159b2e5aa30bed2d30c9def38ae59"
NEXAR_LICENSE_URL = (
    f"https://huggingface.co/datasets/{NEXAR_REPOSITORY}/raw/{NEXAR_REVISION}/LICENSE"
)
NEXAR_API_URL = (
    f"https://huggingface.co/api/datasets/{NEXAR_REPOSITORY}/revision/{NEXAR_REVISION}"
)
DD_REPOSITORY = "jiaweihe/DrivingDojo-mini"
DD_REVISION = "97092ae989332696f88567f8dfaae704b1529b59"
DD_ARCHIVE_SHA256 = "5f7cb0796f74ed52f427bd342c9f170b1c165c8e1c394fa2853eaf3d9158d8ff"
DD_API_URL = f"https://huggingface.co/api/datasets/{DD_REPOSITORY}/revision/{DD_REVISION}"
UNIT_SECONDS = 10.0


POOL_FIELDS = [
    "pool_row_id",
    "source_dataset",
    "source_repository",
    "source_revision",
    "provider_split",
    "session_id",
    "media_kind",
    "local_locator",
    "content_identity_kind",
    "content_sha256",
    "file_size_bytes",
    "duration_seconds",
    "nominal_oracle_units_10s",
    "frame_or_image_count",
    "fps",
    "width",
    "height",
    "sampling_tag_only",
    "sampling_anchor_seconds",
    "sampling_covariates",
    "model_split_role",
    "license_status",
    "independence_status",
    "technical_probe_status",
    "pool_status",
    "candidate_pipeline_status",
    "oracle_label_status",
    "query_support_status",
    "heldout_paper_split_accessed",
    "notes",
]

ORACLE_CALL_FIELDS = [
    "physical_call_id",
    "source_dataset",
    "session_id",
    "source_sha256",
    "model_split_role",
    "unit_id",
    "unit_start_seconds",
    "unit_end_seconds",
    "anchor_id",
    "selection_stage",
    "sampling_stratum",
    "raw_response_path",
    "raw_response_sha256",
    "oracle_generic_label",
    "oracle_generic_involved_object",
    "confidence",
    "parse_status",
    "physical_call",
    "generation_runtime_seconds",
    "model_hash",
    "prompt_hash",
    "parser_schema_hash",
    "parser_source_hash",
    "sampling_code_hash",
    "call_status",
    "notes",
]

ORACLE_LABEL_FIELDS = [
    "label_row_id",
    "physical_call_id",
    "source_dataset",
    "session_id",
    "source_sha256",
    "model_split_role",
    "unit_id",
    "unit_start_seconds",
    "unit_end_seconds",
    "anchor_id",
    "selection_stage",
    "sampling_stratum",
    "query_id",
    "verification_key",
    "witness_track_id",
    "projected_label",
    "projection_actor_set",
    "oracle_generic_label",
    "oracle_generic_involved_object",
    "raw_response_path",
    "raw_response_sha256",
    "confidence",
    "parse_status",
    "model_hash",
    "prompt_hash",
    "parser_schema_hash",
    "parser_source_hash",
    "sampling_code_hash",
    "label_status",
    "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_text(path: Path, text: str) -> None:
    atomic_bytes(path, text.encode("utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_text(path, buffer.getvalue())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row[key]: row for row in csv.DictReader(handle)}


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def fetch_pinned_bytes(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": "G-ARC-research-audit/1.0"})
    with urlopen(request, timeout=60) as response:
        payload = response.read()
    return payload, utc_now()


def preserve_web_snapshot(
    directory: Path,
    name: str,
    url: str,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    path = directory / name
    receipt_path = directory / f"{name}.retrieval.json"
    if path.exists() and receipt_path.exists():
        payload = path.read_bytes()
        receipt = load_json(receipt_path)
        if receipt["url"] != url:
            raise RuntimeError(f"Preserved source URL changed for {name}")
        retrieved_at = receipt["retrieved_at_utc"]
    else:
        payload, retrieved_at = fetch_pinned_bytes(url)
        atomic_bytes(path, payload)
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is not None and observed_sha256 != expected_sha256:
        raise RuntimeError(f"Pinned web source hash changed for {name}")
    receipt = {
        "url": url,
        "retrieved_at_utc": retrieved_at,
        "sha256": observed_sha256,
        "bytes": len(payload),
    }
    atomic_json(receipt_path, receipt)
    return {**receipt, "path": relative(path), "receipt_path": relative(receipt_path)}


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()  # noqa: S324 - provider Git identity


def audit_nexar_metadata_files() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for provider_class in ("positive", "negative"):
        path = NEXAR_METADATA / provider_class / "metadata.csv"
        cache_path = (
            NEXAR_METADATA.parent
            / ".cache/huggingface/download/train"
            / provider_class
            / "metadata.csv.metadata"
        )
        lines = cache_path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 3 or lines[0] != NEXAR_REVISION:
            raise RuntimeError(f"Nexar {provider_class} metadata revision is not frozen")
        etag = lines[1]
        if len(etag) == 40:
            observed_identity = git_blob_sha1(path)
            identity_kind = "git_blob_sha1"
        elif len(etag) == 64:
            observed_identity = sha256_file(path)
            identity_kind = "sha256_lfs"
        else:
            raise RuntimeError(f"Unexpected Nexar metadata ETag: {etag}")
        if observed_identity != etag:
            raise RuntimeError(f"Nexar {provider_class} metadata bytes do not match HF ETag")
        result[provider_class] = {
            "path": relative(path),
            "sha256": sha256_file(path),
            "provider_revision": lines[0],
            "provider_etag": etag,
            "provider_identity_kind": identity_kind,
            "cache_metadata_path": relative(cache_path),
            "download_recorded_at_utc": datetime.fromtimestamp(
                float(lines[2]), tz=timezone.utc
            ).isoformat(),
        }
    return result


def hf_download_identity(relative_media_path: Path) -> tuple[str, str]:
    metadata = NEXAR_CACHE / Path(str(relative_media_path) + ".metadata")
    lines = metadata.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        raise RuntimeError(f"Malformed Hugging Face download metadata: {metadata}")
    return lines[0].strip(), lines[1].strip()


def probe_video(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate,nb_frames,width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"status": "FFPROBE_FAILED", "error": result.stderr.strip()[:500]}
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        duration = float(payload["format"]["duration"])
        numerator, denominator = str(stream.get("avg_frame_rate", "0/1")).split("/")
        fps = float(numerator) / float(denominator)
        frames = int(stream.get("nb_frames") or round(duration * fps))
        if not math.isfinite(duration) or duration <= 0 or frames <= 0:
            raise ValueError("non-positive duration or frame count")
        return {
            "status": "FFPROBE_PASS",
            "duration_seconds": duration,
            "frames": frames,
            "fps": fps,
            "width": int(stream["width"]),
            "height": int(stream["height"]),
        }
    except Exception as exc:  # pragma: no cover - exercised only for malformed external media
        return {"status": "FFPROBE_PARSE_FAILED", "error": str(exc)[:500]}


def audit_nexar_file(
    path: Path,
    provider_tag: str,
    metadata_row: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    rel_media = path.relative_to(NEXAR_ROOT.parent)
    revision, expected_sha = hf_download_identity(rel_media)
    actual_sha = sha256_file(path)
    probe = probe_video(path)
    failures: list[str] = []
    if revision != NEXAR_REVISION:
        failures.append("provider_revision_mismatch")
    if actual_sha != expected_sha:
        failures.append("provider_lfs_sha_mismatch")
    if probe["status"] != "FFPROBE_PASS":
        failures.append("ffprobe_failed")
    duration = float(probe.get("duration_seconds", 0.0))
    event_time = metadata_row.get("time_of_event", "")
    alert_time = metadata_row.get("time_of_alert", "")
    sampling_anchor = ""
    if provider_tag == "collision_or_near_collision":
        sampling_anchor = alert_time or event_time
    covariates = {
        key: metadata_row.get(key, "")
        for key in ("light_conditions", "weather", "scene")
    }
    # Nexar's numeric video identity is unique across provider classes.  Keep
    # the weak positive/negative directory out of the split hash so the split
    # cannot depend on that sampling tag, even indirectly.
    session_id = f"nexar:{path.name}"
    pool_status = "ELIGIBLE_PENDING_CANDIDATE_EXTRACTION" if not failures else "QUARANTINED_TECHNICAL"
    row = {
        "pool_row_id": "",
        "source_dataset": "nexar_collision_prediction",
        "source_repository": NEXAR_REPOSITORY,
        "source_revision": revision,
        "provider_split": "train",
        "session_id": session_id,
        "media_kind": "video/mp4",
        "local_locator": relative(path),
        "content_identity_kind": "sha256_validated_against_hf_lfs_metadata",
        "content_sha256": actual_sha,
        "file_size_bytes": path.stat().st_size,
        "duration_seconds": f"{duration:.6f}" if duration else "",
        "nominal_oracle_units_10s": len(unit_windows(duration)) if duration else 0,
        "frame_or_image_count": probe.get("frames", ""),
        "fps": f"{float(probe.get('fps', 0.0)):.9f}" if probe.get("fps") else "",
        "width": probe.get("width", ""),
        "height": probe.get("height", ""),
        "sampling_tag_only": provider_tag,
        "sampling_anchor_seconds": sampling_anchor,
        "sampling_covariates": json.dumps(covariates, sort_keys=True, separators=(",", ":")),
        "model_split_role": deterministic_split("nexar_collision_prediction", path.name),
        "license_status": "ELIGIBLE_NEXAR_OPEN_DATA_LICENSE",
        "independence_status": (
            "NO_EXACT_BENCHMARK_OVERLAP_PROVIDER_SEPARATED_"
            "PERCEPTUAL_AND_CAPTURE_SESSION_LINEAGE_UNRESOLVED"
        ),
        "technical_probe_status": probe["status"],
        "pool_status": pool_status,
        "candidate_pipeline_status": "NOT_RUN_PENDING_AUTHORITY",
        "oracle_label_status": "NOT_RUN_PENDING_AUTHORITY",
        "query_support_status": "UNKNOWN_NO_FROZEN_ORACLE_LABELS",
        "heldout_paper_split_accessed": "false",
        "notes": (
            "Provider collision/normal tag and timing are sampling metadata only; they are not "
            "Q1/Q2 labels, targets, or model features."
        ),
    }
    return row, failures


def build_nexar_rows(workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    positive_metadata = load_csv_index(NEXAR_METADATA / "positive/metadata.csv", "file_name")
    negative_metadata = load_csv_index(NEXAR_METADATA / "negative/metadata.csv", "file_name")
    jobs: list[tuple[Path, str, dict[str, str]]] = []
    missing_metadata: list[dict[str, Any]] = []
    for directory, tag, index in [
        (NEXAR_ROOT / "positive", "collision_or_near_collision", positive_metadata),
        (NEXAR_ROOT / "negative", "normal_driving", negative_metadata),
    ]:
        for path in sorted(directory.glob("*.mp4")):
            metadata = index.get(path.name)
            if metadata is None:
                missing_metadata.append({"path": relative(path), "reason": "provider_metadata_row_missing"})
                metadata = {"file_name": path.name}
            jobs.append((path, tag, metadata))
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = missing_metadata.copy()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(audit_nexar_file, *job) for job in jobs]
        for job, future in zip(jobs, futures):
            row, row_failures = future.result()
            rows.append(row)
            failures.extend(
                {"path": relative(job[0]), "reason": reason}
                for reason in row_failures
            )
    rows.sort(key=lambda row: row["session_id"])
    return rows, failures


def dd_session_duration(session_id: str) -> float:
    match = re.search(r"_([0-9]+(?:\.[0-9]+)?)_([0-9]+(?:\.[0-9]+)?)$", session_id)
    if not match:
        raise ValueError(f"Cannot derive DrivingDojo session duration: {session_id}")
    return float(match.group(2)) - float(match.group(1))


def build_drivingdojo_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    archive_sha = sha256_file(DD_ZIP)
    metadata_lines = DD_DOWNLOAD_METADATA.read_text(encoding="utf-8").splitlines()
    if metadata_lines[:2] != [DD_REVISION, DD_ARCHIVE_SHA256]:
        raise RuntimeError("DrivingDojo-mini download metadata does not match the frozen source identity")
    if archive_sha != DD_ARCHIVE_SHA256:
        raise RuntimeError("DrivingDojo-mini archive bytes changed")
    rows: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    with zipfile.ZipFile(DD_ZIP) as archive:
        dataset = json.loads(archive.read("drivingdojo_mini/mini_dataset.json"))
        names = set(archive.namelist())
        for session_id, record in sorted(dataset.items()):
            member_names = sorted(
                "drivingdojo_mini/" + name
                for key in ("videos", "camera_info", "action_info")
                for name in record.get(key, [])
            )
            missing = [name for name in member_names if name not in names]
            if missing:
                raise RuntimeError(f"Missing archive members for {session_id}: {missing[:3]}")
            member_identity = [
                {
                    "path": name,
                    "crc32": archive.getinfo(name).CRC,
                    "uncompressed_bytes": archive.getinfo(name).file_size,
                }
                for name in member_names
            ]
            duration = dd_session_duration(session_id)
            description = record.get("description", {})
            types = sorted(str(value) for value in description.get("type", []))
            tag = str(description.get("tag", ""))
            type_counts.update(types)
            if tag:
                tag_counts[tag] += 1
            rows.append({
                "pool_row_id": "",
                "source_dataset": "drivingdojo_mini",
                "source_repository": DD_REPOSITORY,
                "source_revision": DD_REVISION,
                "provider_split": "mini",
                "session_id": session_id,
                "media_kind": "image_sequence/jpeg",
                "local_locator": f"{relative(DD_ZIP)}::drivingdojo_mini/videos/{session_id}/",
                "content_identity_kind": "sha256_of_sorted_zip_member_path_crc32_size_manifest",
                "content_sha256": canonical_hash(member_identity),
                "file_size_bytes": sum(item["uncompressed_bytes"] for item in member_identity),
                "duration_seconds": f"{duration:.6f}",
                "nominal_oracle_units_10s": len(unit_windows(duration)),
                "frame_or_image_count": len(record.get("videos", [])),
                "fps": "UNKNOWN_IMAGE_SEQUENCE_CADENCE",
                "width": 1920,
                "height": 1080,
                "sampling_tag_only": "|".join([*types, tag]).strip("|"),
                "sampling_anchor_seconds": "",
                "sampling_covariates": json.dumps(record.get("meta_info", {}), sort_keys=True, separators=(",", ":")),
                "model_split_role": "NONE_QUARANTINED",
                "license_status": "QUARANTINED_EXACT_MINI_LICENSE_UNRESOLVED",
                "independence_status": (
                    "NO_EXACT_BENCHMARK_OVERLAP_PROVIDER_SEPARATED_LICENSE_QUARANTINED"
                ),
                "technical_probe_status": "ZIP_MEMBER_MANIFEST_PASS_NO_VIDEO_CONTAINER",
                "pool_status": "QUARANTINED_LICENSE_UNRESOLVED",
                "candidate_pipeline_status": "PROHIBITED_WHILE_QUARANTINED",
                "oracle_label_status": "PROHIBITED_WHILE_QUARANTINED",
                "query_support_status": "UNKNOWN_NO_FROZEN_ORACLE_LABELS",
                "heldout_paper_split_accessed": "false",
                "notes": (
                    "Official project page links this mini archive, but the exact mini repository "
                    "has no license metadata or license file. Full-dataset Apache-2.0 metadata is "
                    "not imputed to these bytes."
                ),
            })
    evidence = {
        "archive_sha256": archive_sha,
        "archive_bytes": DD_ZIP.stat().st_size,
        "repository": DD_REPOSITORY,
        "revision": DD_REVISION,
        "sessions": len(rows),
        "type_counts": dict(sorted(type_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
        "license_status": "UNRESOLVED_QUARANTINED",
    }
    return rows, evidence


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def validate_frozen_unit_table(
    video_id: str,
    video: dict[str, Any],
    path: Path,
) -> dict[str, Any]:
    generated = unit_windows(float(video["duration_seconds"]))
    with path.open(newline="", encoding="utf-8") as handle:
        frozen = list(csv.DictReader(handle))
    failures = []
    if len(generated) != len(frozen):
        failures.append(f"row_count:{len(generated)}!={len(frozen)}")
    for expected, observed in zip(generated, frozen):
        unit_id = expected.unit_id
        if int(observed["unit_id"]) != unit_id:
            failures.append(f"unit_id:{unit_id}")
        if observed["video_sha256"] != video["sha256"]:
            failures.append(f"video_sha256:{unit_id}")
        if abs(float(observed["start_time"]) - expected.start_seconds) > 1e-3:
            failures.append(f"start_time:{unit_id}")
        if abs(float(observed["end_time"]) - expected.end_seconds) > 1e-3:
            failures.append(f"end_time:{unit_id}")
        if observed["anchor_id"] != f"center10_anchor_{unit_id:04d}":
            failures.append(f"anchor_id:{unit_id}")
        # Both frozen tables were constructed on the explicit nominal 30-fps
        # frame grid. Compare effective decodable endpoints because V0's last
        # requested endpoint intentionally exercises the one-frame clamp.
        expected_start, expected_end = frame_bounds(
            expected.start_seconds,
            expected.end_seconds,
            30.0,
            int(video["frame_count"]),
        )
        observed_start = int(observed["start_frame"])
        observed_end = min(int(observed["end_frame"]), int(video["frame_count"]) - 1)
        if observed_start != expected_start:
            failures.append(f"start_frame:{unit_id}:{observed_start}!={expected_start}")
        if observed_end != expected_end:
            failures.append(f"effective_end_frame:{unit_id}:{observed_end}!={expected_end}")
    overlaps_previous = (
        len(generated) > 1 and generated[-1].start_seconds < generated[-2].end_seconds
    )
    result = {
        "video_id": video_id,
        "status": "PASS" if not failures else "FAIL",
        "video_sha256": video["sha256"],
        "frame_count": int(video["frame_count"]),
        "frozen_rows": len(frozen),
        "generated_rows": len(generated),
        "frozen_units_path": relative(path),
        "frozen_units_sha256": sha256_file(path),
        "failures": failures[:20],
        "tail_window": {
            "unit_id": generated[-1].unit_id,
            "anchor_seconds": generated[-1].anchor_seconds,
            "start_seconds": generated[-1].start_seconds,
            "end_seconds": generated[-1].end_seconds,
            "overlaps_previous": overlaps_previous,
            "frozen_requested_end_frame": int(frozen[-1]["end_frame"]),
            "effective_end_frame": min(
                int(frozen[-1]["end_frame"]), int(video["frame_count"]) - 1
            ),
        },
    }
    if failures:
        raise RuntimeError(f"Cycle-1 unitization diverges from frozen {video_id}: {failures[:5]}")
    return result


def validate_unitization_and_projection(video_manifest: dict[str, Any]) -> dict[str, Any]:
    unit_results = {
        "V0": validate_frozen_unit_table("V0", video_manifest["V0"], FROZEN_V0_UNITS),
        "V1": validate_frozen_unit_table("V1", video_manifest["V1"], FROZEN_V1_UNITS),
    }
    if unit_results["V0"]["tail_window"]["overlaps_previous"] is not True:
        raise RuntimeError("V0 no longer exercises the overlapping-tail branch")
    parity_rows = []
    for generic_label in ("positive", "negative", "abstain", "unexpected"):
        for actor in (
            "vehicle", "cyclist", "pedestrian", "motorcycle", "other", "none", "uncertain", ""
        ):
            for query_id, actors in QUERY_TYPE_PROJECTIONS.items():
                helper = project_generic_label(generic_label, actor, query_id)
                deployed = deployed_project_generic_label(
                    {"label": generic_label, "involved_object": actor}, set(actors)
                )
                parity_rows.append((generic_label, actor, query_id, helper, deployed))
    failures = [row for row in parity_rows if row[-2] != row[-1]]
    if failures:
        raise RuntimeError(f"Projection helper diverges from deployed runtime: {failures[:5]}")
    return {
        "status": "PASS",
        "videos": unit_results,
        "projection_parity": {
            "status": "PASS",
            "exhaustive_cases": len(parity_rows),
            "deployed_source": relative(
                ROOT / "src/garc_eval/psvr_runtime/two_video_physical_oracle.py"
            ),
            "deployed_source_sha256": sha256_file(
                ROOT / "src/garc_eval/psvr_runtime/two_video_physical_oracle.py"
            ),
        },
    }


def build_training_pool_proxy_config(
    preregistration: dict[str, Any],
    implementation_freeze: dict[str, Any],
) -> dict[str, Any]:
    y8 = preregistration["candidates"]["Y8"]
    common = preregistration["common_pipeline"]
    query_heads = {
        query_id: {"Y8": values["Y8"]}
        for query_id, values in preregistration["query_heads"].items()
    }
    config = {
        "config_id": "MF_PSVR_TRAINING_POOL_Y8_LABEL_INDEPENDENT_V1",
        "status": "FROZEN_BEFORE_POOL_CANDIDATE_EXTRACTION",
        "selected_proxy_config": "Y8",
        "selected_proxy_family": y8["family"],
        "detector": y8["detector"],
        "weight_path": y8["weight_path"],
        "weight_sha256": y8["weight_sha256"],
        "resolution": y8["resolution"],
        "sample_fps": common["sample_fps"],
        "confidence_threshold": common["confidence_threshold"],
        "nms_iou": common["nms_iou"],
        "tracker": common["tracker"],
        "query_heads": query_heads,
        "feature_schema": preregistration["feature_definitions"],
        "normalization": common["normalization"],
        "fallback": "no eligible track => unit score 0 and explicit empty evidence",
        "selection_basis": (
            "Label-independent structural query coverage: among the three preregistered local "
            "detectors, Y8 alone has nonempty registered class support for both Q1 and Q2."
        ),
        "outcome_metrics_or_v0_v1_oracle_labels_used_for_selection": False,
        "final_proxy_selection_artifact_read": False,
        "upstream_preregistration_path": relative(PROXY_PREREGISTRATION),
        "upstream_preregistration_file_sha256": sha256_file(PROXY_PREREGISTRATION),
        "upstream_preregistration_hash": preregistration["preregistration_hash"],
        "implementation_path": implementation_freeze["implementation_path"],
        "implementation_sha256": implementation_freeze["implementation_sha256"],
        "implementation_freeze_hash": implementation_freeze["freeze_hash"],
        "implementation_outcome_information_used": implementation_freeze["outcome_information_used"],
        "heldout_opened": False,
    }
    config["training_pool_proxy_config_hash"] = canonical_hash(config)
    return config


def build_acquisition_protocol(
    query_manifest: dict[str, Any],
    oracle_config: dict[str, Any],
    training_proxy: dict[str, Any],
) -> dict[str, Any]:
    bindings = oracle_config["bindings"]
    parser_schema_hash = canonical_hash(bindings["parser_config"])
    return {
        "protocol_id": "MF_PSVR_CYCLE1_ACQUISITION_V1",
        "status": "FROZEN_BEFORE_CANDIDATE_EXTRACTION_OR_ORACLE_LABELING",
        "scientific_question": (
            "Does a licensed, provider-separated pool with no exact V0/V1 overlap contain enough "
            "Q1/Q2-positive unit-level verify "
            "opportunities, including score failures, to train and discriminate an L1 refiner?"
        ),
        "unit_and_label_scope": {
            "unit_seconds": UNIT_SECONDS,
            "unitization": (
                "anchors at 5,15,25,... seconds; if the final nominal anchor exceeds duration, "
                "anchor at duration and use the preceding 5 seconds; the final unit may overlap "
                "the prior unit"
            ),
            "verification_key": "(source_dataset, session_id, query_id, unit_id)",
            "opportunity_witness": "track_id is scheduling provenance only",
            "track_label_available": False,
            "row_rule": (
                "One supervised opportunity row per verification key. Do not copy a unit label "
                "onto all tracks. A pre-label deterministic witness or explicit multiple-instance "
                "model is required."
            ),
            "duplicate_event_rule": (
                "Frozen K3 bridge-safe grouping within source video and query: join only directly "
                "adjacent queried-positive unit IDs, never bridge a queried negative, and require "
                "the proposed core duration <= min(d_core_max=40s,d_seg_max=60s). Candidate "
                "opportunities remain separate verification keys."
            ),
            "duplicate_event_materializer": {
                "name": "k3_bridge_safe",
                "g_max": 1,
                "d_core_max_seconds": 40.0,
                "d_seg_max_seconds": 60.0,
                "negative_barrier": True,
                "source": (
                    "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
                    "clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py"
                ),
            },
        },
        "frozen_oracle": {
            "policy": "one generic OBJECT_ENTERS_EGO_PATH call per selected 10-second unit",
            "model_hash": bindings["model_full_content_hash"],
            "prompt_hash": bindings["prompt_sha256"],
            "parser_schema_hash": parser_schema_hash,
            "parser_source_hash": oracle_config["bindings"]["parser_source_sha256"],
            "sampling_code_hash": bindings["sampling_code_hash"],
            "frame_config": bindings["frame_config"],
            "generation_config": bindings["generation_config"],
            "projection": {
                query["query_id"]: query["type_projection"]
                for query in query_manifest["queries"]
            },
            "projection_uses_free_text": False,
            "abstention_policy": "retain as abstain; never coerce or drop",
            "old_nexar_vlm_audit_reuse": "PROHIBITED_AS_LABEL_OR_SELECTION_SIGNAL",
        },
        "candidate_pipeline": {
            "status": "NOT_RUN_PENDING_AUTHORITY",
            "config_identity": training_proxy["training_pool_proxy_config_hash"],
            "config_artifact": "TRAINING_POOL_PROXY_CONFIG.json",
            "detector": training_proxy["detector"],
            "weight_sha256": training_proxy["weight_sha256"],
            "resolution": training_proxy["resolution"],
            "sample_fps": training_proxy["sample_fps"],
            "confidence_threshold": training_proxy["confidence_threshold"],
            "nms_iou": training_proxy["nms_iou"],
            "tracker": training_proxy["tracker"],
            "query_heads": training_proxy["query_heads"],
            "label_independent_selection_basis": training_proxy["selection_basis"],
            "v0_v1_outcome_dependency": False,
            "tracker_scope": "fresh tracker state per 10-second unit, matching frozen proxy semantics",
            "candidate_rows": "track x unit opportunities plus a deduplicated verification-key table",
        },
        "sampling_metadata_policy": {
            "allowed": [
                "Nexar collision/normal provider tag",
                "Nexar alert/event time as a weak sampling anchor",
                "weather/light/scene covariates",
                "causally extracted frozen Y8 features and scores",
            ],
            "prohibited": [
                "V0/V1 oracle/reference outcomes or configurations selected from those outcomes",
                "V0/V1 media, slices, re-encodings, or other media derivatives as pool examples",
                "paper held-out split",
                "old 5-second Nexar VLM outputs as labels or selection signals",
                "oracle evidence free text for Q1/Q2 projection",
            ],
            "weak_tags_are_targets": False,
        },
        "stage_a_support_pilot": {
            **selection_spec(),
            "maximum_unique_generic_oracle_calls": 96,
            "selection_implementation_path": relative(STAGE_A_SELECTOR),
            "selection_implementation_sha256": sha256_file(STAGE_A_SELECTOR),
            "freeze_runner_path": relative(STAGE_A_FREEZER),
            "freeze_runner_sha256": sha256_file(STAGE_A_FREEZER),
            "freeze_timing": "all 96 identities frozen before first Stage-A oracle call",
            "support_existence_gate": {
                "Q1": {"minimum_positive_units": 8, "minimum_positive_source_videos": 5},
                "Q2": {"minimum_positive_units": 8, "minimum_positive_source_videos": 5},
                "each_query_positive_in_model_calibration_or_pool_audit": True,
                "failure_action": (
                    "Do not scale oracle calls on Nexar alone; acquire a directly licensed, "
                    "query-enriched independent source."
                ),
            },
            "split_specific_usability_gates_per_query": {
                "model_train": {
                    "minimum_positive_units": 4,
                    "minimum_positive_source_videos": 3,
                    "minimum_negative_units": 8,
                    "minimum_negative_source_videos": 5,
                    "failure_action": "Stage B may enrich model_train only if evaluation splits pass.",
                },
                "model_calibration": {
                    "minimum_positive_units": 2,
                    "minimum_positive_source_videos": 2,
                    "minimum_negative_units": 4,
                    "minimum_negative_source_videos": 3,
                    "failure_action": "Reject frozen-pool trainability; do not adaptively replace rows.",
                },
                "pool_audit": {
                    "minimum_positive_units": 2,
                    "minimum_positive_source_videos": 2,
                    "minimum_negative_units": 4,
                    "minimum_negative_source_videos": 3,
                    "failure_action": "Reject frozen-pool trainability; do not adaptively replace rows.",
                },
            },
            "abstain_and_retry": {
                "abstain_counts_as_positive": False,
                "abstain_counts_as_negative": False,
                "retry_within_stage_a": False,
                "parse_or_runtime_failure": (
                    "retain the call identity and failure status; no replacement identity and no "
                    "additional call without a separately authorized protocol amendment"
                ),
            },
        },
        "stage_b_bounded_top_up": {
            "authority": "requires a separate post-pilot decision",
            "maximum_additional_calls": 224,
            "maximum_total_calls": 320,
            "pool_audit_selection_frozen_before_stage_a_labels": True,
            "model_calibration_selection_frozen_before_stage_a_labels": True,
            "adaptive_label_aware_top_up_allowed_only_in": "model_train",
            "adjacent_unit_follow_up": "at most two neighbors per positive unit, within total cap",
            "completion_targets_per_query": {
                "positive_units": 30,
                "positive_source_videos": 12,
                "negative_units": 60,
                "negative_source_videos": 20,
                "low_score_hard_positives": 8,
                "high_score_hard_negatives": 16,
                "multi_unit_positive_event_groups": 6,
            },
            "hard_positive_definition": "oracle positive in bottom frozen Y8 score quartile for query",
            "hard_negative_definition": "oracle negative in top frozen Y8 score quartile for query",
            "multi_unit_positive_event_definition": (
                "one k3_bridge_safe event group containing at least two directly adjacent "
                "oracle-positive unit IDs within a source video and query"
            ),
            "failure_action": "reject Nexar-only sufficiency and add a new independent source",
        },
        "decision_interpretation": {
            "enriched_sample_positive_fraction_is_prevalence": False,
            "stage_a_is_a_support_test": True,
            "cycle1_complete_only_after": [
                "candidate extraction audited",
                "frozen identities physically labeled",
                "both query support targets evaluated",
                "positive/negative, hard-positive/hard-negative, and duplicate-event coverage audited",
            ],
        },
        "heldout_opened": False,
    }


def render_licenses() -> str:
    return f"""# MF-PSVR Cycle 1 training-pool licenses

Status: **Nexar eligible; DrivingDojo-mini quarantined**.

## Nexar Collision Prediction

- Exact source: <https://huggingface.co/datasets/{NEXAR_REPOSITORY}>
- Audited repository revision: `{NEXAR_REVISION}`
- Revision-addressed official license: <{NEXAR_LICENSE_URL}>
- License name in the official dataset card: `nexar-open-data-license`
- Raw license SHA-256 at audit: `{NEXAR_LICENSE_SHA256}`

The exact retrieved license and revision-API bytes are preserved under `provenance/` with URL,
retrieval time, and content-hash receipts.

The license grants use, copying, modification, and distribution subject to attribution,
retention of terms on redistribution, no resale without consent, ethical-use restrictions,
legal compliance, and an as-is disclaimer. This research use is in scope. The project must cite
Nexar and Moura et al.; must not redistribute the videos without retaining the terms; and must not
attempt re-identification, surveillance, weaponization, deceptive media, unsafe-system development,
or exploitative use. This is a custom license, not MIT/Apache.

Primary provenance is also supported by the CVPR 2025 workshop paper:
<https://openaccess.thecvf.com/content/CVPR2025W/WAD/papers/Moura_Nexar_Dashcam_Collision_Prediction_Dataset_and_Challenge_CVPRW_2025_paper.pdf>.

## DrivingDojo-mini

- Exact source: <https://huggingface.co/datasets/{DD_REPOSITORY}>
- Audited repository revision: `{DD_REVISION}`
- Official project page linking the mini archive: <https://drivingdojo.github.io/>
- Full dataset repository: <https://huggingface.co/datasets/Yuqi1997/DrivingDojo>

Observed evidence: the exact mini repository contains only `.gitattributes` and
`drivingdojo_mini.zip`; its API has no license tag and the archive contains no LICENSE, COPYING,
NOTICE, or README. The later full-dataset repository is marked Apache-2.0, but that does not directly
establish terms for the independently hosted mini archive. The project website's CC BY-SA notice
explicitly concerns the website source, not the dataset bytes.

Decision: all 32 mini sessions are quarantined. They may not be used for detector extraction,
oracle labeling, training, evaluation, or publication claims until a direct license grant covering
the exact mini archive is documented. This conservative decision can be revised by direct evidence;
it is not a claim that reuse is forbidden.
"""


def render_dataset_card(
    counts: dict[str, Any],
    cost: dict[str, Any],
    dd_evidence: dict[str, Any],
) -> str:
    return f"""# MF-PSVR provider-separated training-pool dataset card

## Current status

`AUDIT_READY_ORACLE_NOT_RUN`. This is a source and protocol freeze, not a labeled dataset and not a
Cycle-1 completion claim. No YOLO, tracking, frozen-oracle, model-training, V0/V1 semantic-label, or
paper-held-out access occurred in this stage.

## Objective

Test whether provider-separated driving clips with unresolved capture-session lineage contain enough
frozen-query support to train and validate
the MF-PSVR L1 refiner, especially where raw detector scores fail. The decision-critical uncertainty
is Q2 support; Nexar's collision tag is not semantically equivalent to either frozen query.

## Observed composition

- Nexar: {counts['nexar_provider_videos']} exact local provider video clips, {counts['nexar_duration_hours']:.3f} video hours,
  {counts['nexar_nominal_units']} nominal 10-second units, and {counts['nexar_bytes']} bytes.
- Nexar weak sampling tags: {counts['nexar_weak_positive']} collision/near-collision and
  {counts['nexar_weak_negative']} normal-driving videos. These are **not** Q1/Q2 labels.
- Frozen session roles: {json.dumps(counts['split_counts'], sort_keys=True)}.
- DrivingDojo-mini: {dd_evidence['sessions']} image-sequence sessions, all license-quarantined.
- Frozen-oracle labels: 0. Q1 positives: unknown. Q2 positives: unknown.

## Identity and independence

Every eligible Nexar MP4 is SHA-256 hashed and matched to its Hugging Face LFS object identity at
repository revision `{NEXAR_REVISION}`. The manifest's `session_id` field is currently a provider
video-ID proxy because the released metadata contains no trip/capture-session lineage. Exact overlap with
V0/V1 is zero, and no V0/V1 slice, re-encode, or derivative was intentionally selected. Cross-provider
separation is established, but perceptual equivalence and shared capture-session lineage remain
unresolved; this is not reported as proven statistical independence.

The `pool_audit` role is an internal independent-pool slice. It is not the unopened paper held-out
split. Splits are deterministic at provider-video level and independent of weak tags and oracle
outcomes. Leave-one-source-video-out is supported; a stronger leave-one-capture-session-out claim is
not supported until trip lineage is available.

## Labels and supervision scope

The authoritative oracle emits one generic unit label and `involved_object` for a center-anchored
10-second unit. The frozen final-tail rule uses the last 5 seconds when the nominal final anchor is
past the media end, so that unit may overlap its predecessor.
Q1 is projected from `vehicle|cyclist`; Q2 from `pedestrian|cyclist`; free-text evidence is never used
for projection. A track is only the causal scheduling witness. No track is oracle-confirmed.

Consequently, supervised data use one row per `(source, session, query, unit)` verification key.
Duplicating a unit label over every track is prohibited. If track-level rows are studied, they require
either a witness frozen before the label or an explicitly reported multiple-instance objective.

## Acquisition design

The frozen candidate pipeline is the label-independent pool Y8 configuration: YOLOv8n at 640, 5 fps, confidence
0.25, NMS IoU 0.45, and frozen ByteTrack parameters, with fresh tracker state per 10-second unit.
Y8 is selected here because it is the only preregistered local detector with nonempty ontology support
for both Q1 and Q2; the V0/V1 outcome-selected final-proxy artifact is not an input.
The initial 96-call support pilot is frozen across query-score, weak-tag, hard-case, and random strata
before its first oracle call. One generic call supplies both deterministic query projections.

The support-existence gate requires 8 positive units across 5 videos per query. Separate frozen
train/calibration/pool-audit positive and negative gates determine actual usability; calibration and
audit failures cannot be adaptively replaced. A later model-train-only top-up is capped at 320 total
calls and is permitted only after the pilot decision. Enriched positive fractions are not prevalence estimates.

## Cost estimate before authority

- Full-pool Y8 extraction: {cost['planned_sampled_frames']:,} exact planned frames imply about
  {cost['y8_detector_gpu_seconds_frame_component'] / 60.0:.1f} detector GPU-minutes; the frame-p95
  wall estimate plus initialization and the direct short-clip overhead profile is
  {cost['y8_p95_wall_seconds_plus_initialization_and_profiled_short_clip_overhead'] / 60.0:.1f} minutes.
- Stage-A 96-call oracle pilot: p95 sequential reservation about
  {cost['stage_a_oracle_sequential_reservation_hours_p95_plus_initialization']:.2f} hours including one model initialization.
- Full 320-call cap: p95 sequential reservation about
  {cost['maximum_oracle_sequential_reservation_hours_p95_plus_initialization']:.2f} hours including initialization.

No such compute was launched by this audit.

## Known biases and exclusions

- The usable pool currently has one provider dataset and many exact-unique provider videos, but no
  released trip/capture-session grouping; within-provider session leakage cannot yet be ruled out.
- Only 200 local Nexar collision-tagged videos are present versus 403 normal-tagged videos; this is a
  convenience subset, not a representative prevalence sample.
- Collision and alert-time metadata are only weak sampling aids and are unreliable for ego-path entry.
- The prior 5-second Nexar Qwen audit used a different prompt/sampling contract and is excluded from
  labels and exact unit selection.
- DrivingDojo-mini could plausibly enrich Q2, but license uncertainty currently blocks its use.
- Container metadata was probed; a complete decode of every frame was not performed in this stage.

## Falsifiable next decision

Run the frozen Y8 extraction and the 96-call support pilot only after compute/oracle authority. Reject
the Nexar-only training-pool hypothesis if either query fails the preregistered support gate. In that
case the next action is to acquire a directly licensed Q2-enriched independent source, not to retune
the frozen oracle or reinterpret weak tags.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 16:
        raise SystemExit("--workers must be in [1,16]")
    out = args.out.resolve()

    required = [
        NEXAR_ROOT,
        NEXAR_CACHE,
        DD_ZIP,
        DD_DOWNLOAD_METADATA,
        QUERY_MANIFEST,
        FROZEN_V0_UNITS,
        FROZEN_V1_UNITS,
        VIDEO_MANIFEST,
        ORACLE_CONFIG,
        ORACLE_RUNTIME_CONFIG,
        TASK_DEADLINE_MANIFEST,
        PROXY_PREREGISTRATION,
        PROXY_IMPLEMENTATION_FREEZE,
        Y8_COST,
        ORACLE_PROFILE_INITIALIZATION,
        TRAINING_POOL_HELPER,
        STAGE_A_SELECTOR,
        CANDIDATE_RUNNER,
        STAGE_A_FREEZER,
        SHORT_CLIP_PROFILE_RUNNER,
        SHORT_CLIP_PROFILE,
        LEGACY_INDEPENDENCE_AUDIT,
        OLD_NEXAR_VLM_REPORT,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing required evidence: {missing}")

    query_manifest = load_json(QUERY_MANIFEST)
    video_manifest = load_json(VIDEO_MANIFEST)
    oracle_config = load_json(ORACLE_CONFIG)
    oracle_runtime = load_json(ORACLE_RUNTIME_CONFIG)
    proxy_preregistration = load_json(PROXY_PREREGISTRATION)
    proxy_implementation_freeze = load_json(PROXY_IMPLEMENTATION_FREEZE)
    training_proxy = build_training_pool_proxy_config(
        proxy_preregistration, proxy_implementation_freeze
    )
    y8_cost = load_json(Y8_COST)
    oracle_initialization = load_json(ORACLE_PROFILE_INITIALIZATION)
    short_clip_profile = load_json(SHORT_CLIP_PROFILE)
    legacy_independence = load_json(LEGACY_INDEPENDENCE_AUDIT)
    if query_manifest.get("heldout_opened") is not False:
        raise RuntimeError("Frozen benchmark records unexpected heldout access")
    if training_proxy["selected_proxy_config"] != "Y8":
        raise RuntimeError("Training-pool acquisition proxy is not Y8")
    if (
        proxy_implementation_freeze["preregistration_hash"]
        != proxy_preregistration["preregistration_hash"]
    ):
        raise RuntimeError("Pool proxy preregistration and implementation freeze diverge")
    if proxy_implementation_freeze["outcome_information_used"] is not False:
        raise RuntimeError("Pool proxy implementation freeze used outcome information")
    weight_path = Path(training_proxy["weight_path"])
    if sha256_file(weight_path) != training_proxy["weight_sha256"]:
        raise RuntimeError("Frozen Y8 weights changed")
    tracker_path = Path(training_proxy["tracker"]["implementation_path"])
    if sha256_file(tracker_path) != training_proxy["tracker"]["implementation_sha256"]:
        raise RuntimeError("Frozen ByteTrack implementation changed")
    strict_builder = Path(oracle_config["bindings"]["strict_builder_path"])
    if sha256_file(strict_builder) != oracle_config["bindings"]["strict_builder_sha256"]:
        raise RuntimeError("Frozen oracle builder changed")
    prompt_path = Path(oracle_runtime["prompt_path"])
    if sha256_file(prompt_path) != oracle_runtime["prompt_sha256"]:
        raise RuntimeError("Frozen oracle prompt changed")
    if oracle_runtime["model_full_content_hash"] != oracle_config["bindings"]["model_full_content_hash"]:
        raise RuntimeError("Frozen oracle model identity mismatch")
    unitization_audit = validate_unitization_and_projection(video_manifest)
    metadata_provenance = audit_nexar_metadata_files()

    nexar_rows, nexar_failures = build_nexar_rows(args.workers)
    dd_rows, dd_evidence = build_drivingdojo_rows()
    for index, row in enumerate([*nexar_rows, *dd_rows]):
        row["pool_row_id"] = f"pool_{index:04d}"
    rows = [*nexar_rows, *dd_rows]

    exact_hashes: defaultdict[str, list[str]] = defaultdict(list)
    for row in nexar_rows:
        exact_hashes[row["content_sha256"]].append(row["session_id"])
    duplicate_groups = [sessions for sessions in exact_hashes.values() if len(sessions) > 1]
    benchmark_hashes = sorted({task["video_sha256"] for task in query_manifest["tasks"]})
    overlaps = [row["session_id"] for row in nexar_rows if row["content_sha256"] in benchmark_hashes]
    eligible = [row for row in nexar_rows if row["pool_status"] == "ELIGIBLE_PENDING_CANDIDATE_EXTRACTION"]
    durations = [float(row["duration_seconds"]) for row in eligible]
    total_duration = sum(durations)
    total_units = sum(int(row["nominal_oracle_units_10s"]) for row in eligible)
    split_counts = dict(sorted(Counter(row["model_split_role"] for row in eligible).items()))
    weak_counts = Counter(row["sampling_tag_only"] for row in eligible)
    source_revision_counts = Counter(row["source_revision"] for row in nexar_rows)

    independence_decision = (
        "ELIGIBLE_NO_EXACT_OVERLAP_LINEAGE_UNRESOLVED_DRIVINGDOJO_QUARANTINED"
        if not nexar_failures and not duplicate_groups and not overlaps and eligible
        else "BLOCKED_SOURCE_INTEGRITY"
    )
    independence = {
        "audit_id": "MF_PSVR_CYCLE1_POOL_INDEPENDENCE_V1",
        "audited_at_utc": utc_now(),
        "decision": independence_decision,
        "heldout_opened": False,
        "semantic_labels_accessed_by_this_script": False,
        "paper_heldout_accessed": False,
        "benchmark_source_hashes": benchmark_hashes,
        "nexar": {
            "repository": NEXAR_REPOSITORY,
            "expected_revision": NEXAR_REVISION,
            "revision_counts": dict(source_revision_counts),
            "local_provider_videos": len(nexar_rows),
            "eligible_provider_videos": len(eligible),
            "capture_session_grouping": "UNAVAILABLE_IN_RELEASED_METADATA",
            "unique_exact_content_hashes": len(exact_hashes),
            "duplicate_groups": duplicate_groups,
            "exact_benchmark_hash_overlaps": overlaps,
            "metadata_or_probe_failures": nexar_failures,
            "metadata_file_provenance": metadata_provenance,
            "duration_seconds": {
                "total": total_duration,
                "minimum": min(durations) if durations else 0.0,
                "p50": percentile(durations, 0.50),
                "p95": percentile(durations, 0.95),
                "maximum": max(durations) if durations else 0.0,
            },
            "provider_video_identity": (
                "Each train/<provider-class>/<file> is a provider video identity; local SHA-256 "
                "matches its Hugging Face LFS object identity. The release exposes no trip or "
                "capture-session grouping field."
            ),
            "derivative_exclusion_evidence": [
                "zero exact-content overlap with V0/V1",
                "different public provider and provider video IDs",
                "existing pre-benchmark audit rejected Nexar only for short workload duration",
            ],
            "residual_uncertainty": (
                "Exact hashes cannot alone rule out every perceptually equivalent crop or re-encode, "
                "or multiple clips from one capture trip. No such lineage is indicated, but the "
                "released metadata is insufficient to test it."
            ),
        },
        "drivingdojo_mini": dd_evidence,
        "legacy_audit_binding": {
            "path": relative(LEGACY_INDEPENDENCE_AUDIT),
            "sha256": sha256_file(LEGACY_INDEPENDENCE_AUDIT),
            "nexar_prior_role": next(
                row["reason"]
                for row in legacy_independence["rejected_key_candidates"]
                if row["source"] == "Nexar collection"
            ),
        },
        "interpretation": (
            "Nexar has zero exact-content overlap with V0/V1 and provider-level separation, so "
            "it is eligible for training-pool use under a residual-lineage caveat. Perceptual "
            "equivalence and shared capture sessions remain unresolved. DrivingDojo-mini has "
            "provider separation but remains legally quarantined."
        ),
    }

    duration_hours = total_duration / 3600.0
    sample_fps = float(training_proxy["sample_fps"])
    unit_window_seconds = 0.0
    planned_sampled_frames = 0
    for row in eligible:
        fps = float(row["fps"])
        frame_count = int(row["frame_or_image_count"])
        interval = max(1, int(round(fps / sample_fps)))
        for window in unit_windows(float(row["duration_seconds"])):
            start_frame, end_frame = frame_bounds(
                window.start_seconds, window.end_seconds, fps, frame_count
            )
            unit_window_seconds += window.end_seconds - window.start_seconds
            planned_sampled_frames += ((end_frame - start_frame) // interval) + 1
    verify_p95 = max(
        float(value["physical_verify_p95_seconds"])
        for value in load_json(TASK_DEADLINE_MANIFEST)["video_regimes"].values()
    )
    oracle_initialization_seconds = float(oracle_initialization["oracle"]["initialization_seconds"])
    if (
        short_clip_profile["semantic_frames_inspected"] != 0
        or short_clip_profile["detector_loaded"] is not False
        or short_clip_profile["gpu_inference"] is not False
        or int(short_clip_profile["video_open_close"]["count"]) != len(eligible)
        or int(short_clip_profile["tracker_reset"]["count"]) != total_units
        or short_clip_profile["proxy_source_sha256"]
        != proxy_implementation_freeze["implementation_sha256"]
    ):
        raise RuntimeError("Short-clip overhead profile scope or identity mismatch")
    short_clip_overhead_seconds = max(
        float(short_clip_profile["observed_sum_seconds"]),
        float(short_clip_profile["p95_product_envelope_seconds"]),
    )
    gpu_seconds_per_sample = float(y8_cost["gpu_seconds_per_video_hour"]) / (3600.0 * sample_fps)
    cpu_seconds_per_sample = float(y8_cost["cpu_seconds_per_video_hour"]) / (3600.0 * sample_fps)
    y8_initialization_seconds = float(y8_cost["initialization_seconds"])
    cost = {
        "basis": {
            "y8_physical_cost_path": relative(Y8_COST),
            "y8_physical_cost_sha256": sha256_file(Y8_COST),
            "oracle_p95_seconds_per_verify_upper_envelope": verify_p95,
            "oracle_p95_source": relative(TASK_DEADLINE_MANIFEST),
            "oracle_initialization_path": relative(ORACLE_PROFILE_INITIALIZATION),
            "oracle_initialization_sha256": sha256_file(ORACLE_PROFILE_INITIALIZATION),
            "frame_cost_scaling": "exact planned sampled frames, not source-video duration",
        },
        "eligible_video_hours": duration_hours,
        "eligible_nominal_units": total_units,
        "candidate_unit_window_hours_including_overlap": unit_window_seconds / 3600.0,
        "unit_window_inflation_over_source_duration_fraction": (
            unit_window_seconds / total_duration - 1.0
        ),
        "planned_sampled_frames": planned_sampled_frames,
        "y8_detector_gpu_seconds_frame_component": planned_sampled_frames * gpu_seconds_per_sample,
        "y8_cpu_seconds_frame_component": planned_sampled_frames * cpu_seconds_per_sample,
        "y8_initialization_seconds": y8_initialization_seconds,
        "y8_mean_wall_seconds_frame_component": (
            planned_sampled_frames / float(y8_cost["end_to_end_fps"])
        ),
        "y8_p95_wall_seconds_frame_component": (
            planned_sampled_frames * float(y8_cost["p95_latency_ms"]) / 1000.0
        ),
        "y8_p95_wall_seconds_plus_initialization_before_short_clip_overhead": (
            y8_initialization_seconds
            + planned_sampled_frames * float(y8_cost["p95_latency_ms"]) / 1000.0
        ),
        "short_clip_overhead_profile": {
            "path": relative(SHORT_CLIP_PROFILE),
            "sha256": sha256_file(SHORT_CLIP_PROFILE),
            "observed_sum_seconds": short_clip_profile["observed_sum_seconds"],
            "p95_product_envelope_seconds": short_clip_profile[
                "p95_product_envelope_seconds"
            ],
            "planning_addend_seconds": short_clip_overhead_seconds,
            "scope": short_clip_profile["scope"],
            "residual_limitation": short_clip_profile["residual_limitation"],
        },
        "y8_p95_wall_seconds_plus_initialization_and_profiled_short_clip_overhead": (
            y8_initialization_seconds
            + planned_sampled_frames * float(y8_cost["p95_latency_ms"]) / 1000.0
            + short_clip_overhead_seconds
        ),
        "stage_a_calls": 96,
        "oracle_initialization_seconds": oracle_initialization_seconds,
        "stage_a_oracle_call_wall_seconds_p95_envelope": 96 * verify_p95,
        "stage_a_oracle_sequential_reservation_hours_p95_plus_initialization": (
            oracle_initialization_seconds + 96 * verify_p95
        ) / 3600.0,
        "maximum_calls": 320,
        "maximum_oracle_sequential_reservation_hours_p95_plus_initialization": (
            oracle_initialization_seconds + 320 * verify_p95
        ) / 3600.0,
        "oracle_time_semantics": (
            "Service wall-clock / GPU reservation envelope; active GPU kernel time was not "
            "separately measured and is not claimed."
        ),
        "note": "Planning estimates, not billing promises; all physical costs must be recorded.",
    }
    protocol = build_acquisition_protocol(query_manifest, oracle_config, training_proxy)
    protocol["unitization_equivalence_audit"] = unitization_audit
    protocol["protocol_hash"] = canonical_hash(protocol)

    counts = {
        "nexar_provider_videos": len(eligible),
        "nexar_duration_hours": duration_hours,
        "nexar_nominal_units": total_units,
        "nexar_bytes": sum(int(row["file_size_bytes"]) for row in eligible),
        "nexar_weak_positive": weak_counts["collision_or_near_collision"],
        "nexar_weak_negative": weak_counts["normal_driving"],
        "split_counts": split_counts,
    }

    out.mkdir(parents=True, exist_ok=True)
    provenance_dir = out / "provenance"
    nexar_license_snapshot = preserve_web_snapshot(
        provenance_dir,
        "NEXAR_LICENSE.txt",
        NEXAR_LICENSE_URL,
        NEXAR_LICENSE_SHA256,
    )
    nexar_api_snapshot = preserve_web_snapshot(
        provenance_dir,
        "NEXAR_REVISION_API.json",
        NEXAR_API_URL,
        NEXAR_API_SNAPSHOT_SHA256,
    )
    dd_api_snapshot = preserve_web_snapshot(
        provenance_dir,
        "DRIVINGDOJO_MINI_REVISION_API.json",
        DD_API_URL,
    )
    dd_api_value = json.loads(
        (provenance_dir / "DRIVINGDOJO_MINI_REVISION_API.json").read_text(encoding="utf-8")
    )
    if dd_api_value.get("sha") != DD_REVISION:
        raise RuntimeError("Preserved DrivingDojo API snapshot revision mismatch")
    if any(str(tag).startswith("license:") for tag in dd_api_value.get("tags", [])):
        raise RuntimeError("DrivingDojo-mini now exposes a license tag; re-audit quarantine")
    atomic_csv(out / "TRAINING_POOL_MANIFEST.csv", rows, POOL_FIELDS)
    if short_clip_profile["pool_manifest_sha256"] != sha256_file(
        out / "TRAINING_POOL_MANIFEST.csv"
    ):
        raise RuntimeError("Short-clip profile is stale for the regenerated pool manifest")
    if short_clip_profile["unit_manifest_sha256"] != sha256_file(
        out / "candidates/UNIT_MANIFEST.csv"
    ):
        raise RuntimeError("Short-clip profile is stale for the candidate unit manifest")
    atomic_text(out / "TRAINING_POOL_LICENSES.md", render_licenses())
    atomic_json(out / "TRAINING_POOL_INDEPENDENCE_AUDIT.json", independence)
    atomic_csv(out / "ORACLE_CALL_MANIFEST.csv", [], ORACLE_CALL_FIELDS)
    atomic_csv(out / "ORACLE_LABEL_MANIFEST.csv", [], ORACLE_LABEL_FIELDS)
    atomic_text(out / "TRAINING_DATASET_CARD.md", render_dataset_card(counts, cost, dd_evidence))
    atomic_json(out / "ORACLE_ACQUISITION_PROTOCOL.json", protocol)
    atomic_json(out / "TRAINING_POOL_PROXY_CONFIG.json", training_proxy)
    atomic_json(out / "COST_AND_SUPPORT_PLAN.json", cost)
    atomic_json(out / "SOURCE_PROVENANCE_SNAPSHOT.json", {
        "nexar": {
            "repository": NEXAR_REPOSITORY,
            "revision": NEXAR_REVISION,
            "api_snapshot_sha256": NEXAR_API_SNAPSHOT_SHA256,
            "license_sha256": NEXAR_LICENSE_SHA256,
            "license_name": "nexar-open-data-license",
            "license_snapshot": nexar_license_snapshot,
            "api_snapshot": nexar_api_snapshot,
            "metadata_files": metadata_provenance,
        },
        "drivingdojo_mini": {
            "repository": DD_REPOSITORY,
            "revision": DD_REVISION,
            "archive_sha256": DD_ARCHIVE_SHA256,
            "exact_repository_license_metadata": None,
            "license_status": "UNRESOLVED_QUARANTINED",
            "api_snapshot": dd_api_snapshot,
        },
        "web_evidence_retrieval_times_are_in_snapshot_receipts": True,
        "heldout_opened": False,
    })
    state = {
        "stage": "cycle_01_training_pool",
        "status": (
            "AUDIT_READY_ORACLE_NOT_RUN"
            if independence_decision.startswith("ELIGIBLE_")
            else "BLOCKED_SOURCE_INTEGRITY"
        ),
        "cycle_complete": False,
        "candidate_pipeline_run": False,
        "physical_oracle_calls": 0,
        "frozen_oracle_labels": 0,
        "Q1_support": "UNKNOWN",
        "Q2_support": "UNKNOWN",
        "drivingdojo_status": "QUARANTINED_LICENSE_UNRESOLVED",
        "heldout_opened": False,
        "next_high_information_action": (
            "After explicit compute/oracle authority, run frozen full-pool Y8 extraction and freeze "
            "the 96-unit Stage-A support sample before any oracle call."
        ),
    }
    atomic_json(out / "STAGE_STATE.json", state)

    artifact_names = [
        "TRAINING_POOL_MANIFEST.csv",
        "TRAINING_POOL_LICENSES.md",
        "TRAINING_POOL_INDEPENDENCE_AUDIT.json",
        "ORACLE_CALL_MANIFEST.csv",
        "ORACLE_LABEL_MANIFEST.csv",
        "TRAINING_DATASET_CARD.md",
        "ORACLE_ACQUISITION_PROTOCOL.json",
        "TRAINING_POOL_PROXY_CONFIG.json",
        "COST_AND_SUPPORT_PLAN.json",
        "SOURCE_PROVENANCE_SNAPSHOT.json",
        "STAGE_STATE.json",
        "SHORT_CLIP_OVERHEAD_PROFILE.json",
        "provenance/NEXAR_LICENSE.txt",
        "provenance/NEXAR_LICENSE.txt.retrieval.json",
        "provenance/NEXAR_REVISION_API.json",
        "provenance/NEXAR_REVISION_API.json.retrieval.json",
        "provenance/DRIVINGDOJO_MINI_REVISION_API.json",
        "provenance/DRIVINGDOJO_MINI_REVISION_API.json.retrieval.json",
    ]
    manifest = {
        "audit_id": "MF_PSVR_CYCLE1_PREINFERENCE_AUDIT_V1",
        "created_at_utc": utc_now(),
        "script": relative(Path(__file__)),
        "script_sha256": sha256_file(Path(__file__)),
        "decision": state["status"],
        "cycle_complete": False,
        "heldout_opened": False,
        "code_and_test_bindings": {
            relative(TRAINING_POOL_HELPER): sha256_file(TRAINING_POOL_HELPER),
            relative(STAGE_A_SELECTOR): sha256_file(STAGE_A_SELECTOR),
            relative(CANDIDATE_RUNNER): sha256_file(CANDIDATE_RUNNER),
            relative(STAGE_A_FREEZER): sha256_file(STAGE_A_FREEZER),
            relative(SHORT_CLIP_PROFILE_RUNNER): sha256_file(SHORT_CLIP_PROFILE_RUNNER),
            "tests/psvr_runtime/test_mf_training_pool.py": sha256_file(
                ROOT / "tests/psvr_runtime/test_mf_training_pool.py"
            ),
            "tests/psvr_runtime/test_mf_stage_a_selection.py": sha256_file(
                ROOT / "tests/psvr_runtime/test_mf_stage_a_selection.py"
            ),
            "tests/psvr_runtime/test_mf_candidate_preflight.py": sha256_file(
                ROOT / "tests/psvr_runtime/test_mf_candidate_preflight.py"
            ),
        },
        "artifacts": {
            name: {"sha256": sha256_file(out / name), "bytes": (out / name).stat().st_size}
            for name in artifact_names
        },
    }
    manifest["audit_hash"] = canonical_hash(manifest)
    atomic_json(out / "AUDIT_MANIFEST.json", manifest)
    print(json.dumps({
        "decision": state["status"],
        "eligible_nexar_provider_videos": len(eligible),
        "quarantined_drivingdojo_sessions": len(dd_rows),
        "nominal_oracle_units": total_units,
        "physical_oracle_calls": 0,
        "Q1_support": "UNKNOWN",
        "Q2_support": "UNKNOWN",
        "output": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
