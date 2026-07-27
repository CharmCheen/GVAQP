from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

from .config import (
    ROOT,
    V1_BENCH,
    V1_DERIVED,
    V1_IMMUTABLE,
    V1_OUTPUT,
    V2_AUDITS,
    V2_BENCH,
    V2_COST,
    V2_DERIVED,
    V2_IMMUTABLE,
    V2_ISOLATION,
    V2_OUTPUT,
    V2_PHYSICAL,
    V2_REPLAY,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(
        path,
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
    )


def file_record(path: Path) -> dict[str, Any]:
    return {"sha256": sha256_file(path), "bytes": path.stat().st_size}


def recursive_manifest(root: Path, excluded: Iterable[Path] = ()) -> dict[str, Any]:
    excluded_resolved = {path.resolve() for path in excluded}
    return {
        str(path.relative_to(root)): file_record(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.resolve() not in excluded_resolved
    }


def verify_manifest_assets(root: Path, assets: dict[str, Any]) -> dict[str, Any]:
    actual_paths = {
        str(path.relative_to(root)): path
        for path in root.rglob("*")
        if path.is_file()
    }
    expected_keys = set(assets)
    actual_keys = set(actual_paths)
    missing = sorted(expected_keys - actual_keys)
    unexpected = sorted(actual_keys - expected_keys)
    mismatches = []
    for relative in sorted(expected_keys & actual_keys):
        record = file_record(actual_paths[relative])
        if record != assets[relative]:
            mismatches.append(relative)
    return {
        "missing": missing,
        "unexpected": unexpected,
        "hash_or_size_mismatches": mismatches,
        "status": (
            "PASS"
            if not missing and not unexpected and not mismatches
            else "FAIL"
        ),
    }


def verify_v1_immutable() -> dict[str, Any]:
    manifest_path = V1_IMMUTABLE / "immutable_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    actual = {
        str(path.relative_to(V1_IMMUTABLE)): file_record(path)
        for path in sorted(V1_IMMUTABLE.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    mismatch = [
        relative
        for relative in sorted(set(actual) | set(manifest["assets"]))
        if actual.get(relative) != manifest["assets"].get(relative)
    ]
    root_hash = canonical_hash(actual)
    return {
        "status": (
            "PASS"
            if not mismatch
            and len(actual) == int(manifest["asset_count"])
            and root_hash == manifest["immutable_root_hash"]
            else "FAIL"
        ),
        "parent_manifest_sha256": sha256_file(manifest_path),
        "expected_root_hash": manifest["immutable_root_hash"],
        "computed_root_hash": root_hash,
        "expected_asset_count": int(manifest["asset_count"]),
        "actual_asset_count": len(actual),
        "mismatch_count": len(mismatch),
        "mismatches": mismatch,
    }


def _selected_v1_derived_files() -> list[Path]:
    explicit = [
        V1_DERIVED / "timeline_units_offset5.csv",
        V1_DERIVED / "candidate_event_map.parquet",
        V1_DERIVED / "full_scan_exposure_audit.json",
        V1_DERIVED / "audits/timeline_audit.json",
        V1_DERIVED / "audits/unit_determinism_audit.json",
        V1_DERIVED / "audits/reference_independence_audit.json",
        V1_DERIVED / "audits/reference_completeness_audit.json",
        V1_DERIVED / "audits/partition_phase_audit.json",
        V1_DERIVED / "audits/event_exposure_audit.json",
        V1_DERIVED / "audits/candidate_replay_audit.json",
        V1_DERIVED / "audits/policy_isolation_audit.json",
        V1_DERIVED / "audits/postfreeze_policy_leakage_correction.json",
        V1_DERIVED / "audits/physical_trace_audit.json",
        V1_DERIVED / "audits/cache_protocol_audit.json",
        V1_DERIVED / "audits/deadline_enforcement_audit.json",
        V1_DERIVED / "audits/replay_physical_agreement.json",
        V1_DERIVED / "audits/FINAL_PILOT_DECISION.md",
        V1_OUTPUT / "reports/FINAL_PILOT_DECISION.md",
        V1_OUTPUT / "repair_log.json",
        V1_OUTPUT / "code_version.json",
    ]
    roots = [
        V1_DERIVED / "offset5_scan_outputs",
        V1_DERIVED / "visible_subset_candidates",
        V1_DERIVED / "policy_runs/physical",
        V1_DERIVED / "cost_calibration",
    ]
    files = [path for path in explicit if path.is_file()]
    for root in roots:
        files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(set(files))


def build_parent_v1_manifest() -> dict[str, Any]:
    immutable_audit = verify_v1_immutable()
    if immutable_audit["status"] != "PASS":
        raise RuntimeError("v1 immutable evidence failed parent verification")
    parent_manifest_path = V1_IMMUTABLE / "immutable_manifest.json"
    parent_manifest = json.loads(parent_manifest_path.read_text())
    selected = _selected_v1_derived_files()
    derived_assets = {
        str(path.relative_to(ROOT)): file_record(path) for path in selected
    }
    v1_policy = json.loads(
        (V1_DERIVED / "audits/policy_isolation_audit.json").read_text()
    )
    v1_decision = (
        V1_OUTPUT / "reports/FINAL_PILOT_DECISION.md"
    ).read_text()
    if (
        v1_policy.get("status") != "FAIL"
        or "OVERALL_PARTIAL_SCAN_BENCHMARK = BLOCKED" not in v1_decision
    ):
        raise RuntimeError("v1 terminal blocked state is not preserved")
    payload = {
        "benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V2",
        "parent_benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V1",
        "repair_scope": "OUT_OF_PROCESS_POLICY_ISOLATION_ONLY",
        "created_at_utc": utc_now(),
        "parent_immutable_manifest_sha256": sha256_file(parent_manifest_path),
        "parent_immutable_root_hash": parent_manifest["immutable_root_hash"],
        "parent_immutable_asset_count": parent_manifest["asset_count"],
        "parent_immutable_manifest": parent_manifest,
        "inherited_derived_assets": derived_assets,
        "inherited_derived_asset_count": len(derived_assets),
        "v1_terminal_status": "BLOCKED_POLICY_INFORMATION_ISOLATION",
        "v1_immutable_verification": immutable_audit,
    }
    payload["parent_asset_manifest_hash"] = canonical_hash(
        {
            "parent_immutable_manifest_sha256": payload[
                "parent_immutable_manifest_sha256"
            ],
            "parent_immutable_root_hash": payload[
                "parent_immutable_root_hash"
            ],
            "inherited_derived_assets": derived_assets,
            "v1_terminal_status": payload["v1_terminal_status"],
        }
    )
    return payload


def verify_parent_v1_manifest(path: Path | None = None) -> dict[str, Any]:
    path = path or (V2_IMMUTABLE / "parent_v1_manifest.json")
    frozen = json.loads(path.read_text())
    current_immutable = verify_v1_immutable()
    derived_mismatch = []
    for relative, expected in frozen["inherited_derived_assets"].items():
        candidate = ROOT / relative
        if not candidate.is_file() or file_record(candidate) != expected:
            derived_mismatch.append(relative)
    link_payload = {
        "parent_immutable_manifest_sha256": frozen[
            "parent_immutable_manifest_sha256"
        ],
        "parent_immutable_root_hash": frozen["parent_immutable_root_hash"],
        "inherited_derived_assets": frozen["inherited_derived_assets"],
        "v1_terminal_status": frozen["v1_terminal_status"],
    }
    current_link_hash = canonical_hash(link_payload)
    status = (
        current_immutable["status"] == "PASS"
        and current_immutable["parent_manifest_sha256"]
        == frozen["parent_immutable_manifest_sha256"]
        and current_immutable["expected_root_hash"]
        == frozen["parent_immutable_root_hash"]
        and not derived_mismatch
        and current_link_hash == frozen["parent_asset_manifest_hash"]
    )
    return {
        "status": "PASS" if status else "FAIL",
        "v1_immutable": current_immutable,
        "inherited_derived_asset_count": len(
            frozen["inherited_derived_assets"]
        ),
        "derived_mismatch_count": len(derived_mismatch),
        "derived_mismatches": derived_mismatch,
        "expected_parent_asset_manifest_hash": frozen[
            "parent_asset_manifest_hash"
        ],
        "computed_parent_asset_manifest_hash": current_link_hash,
    }


def create_v2_directories() -> None:
    for path in [
        V2_IMMUTABLE / "v2_contracts",
        V2_IMMUTABLE / "policy_bundle",
        V2_AUDITS,
        V2_ISOLATION,
        V2_REPLAY,
        V2_PHYSICAL,
        V2_COST,
        V2_OUTPUT / "reports",
        V2_OUTPUT / "private_policy_logs",
        V2_OUTPUT / "physical_run_logs",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def compile_launcher(source: Path, destination: Path) -> None:
    temporary = destination.with_suffix(".tmp")
    subprocess.run(
        [
            "gcc",
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-o",
            str(temporary),
            str(source),
        ],
        cwd=ROOT,
        check=True,
    )
    os.chmod(temporary, 0o555)
    os.replace(temporary, destination)


def freeze_v2_immutable() -> dict[str, Any]:
    manifest_path = V2_IMMUTABLE / "immutable_manifest.json"
    if manifest_path.exists():
        raise RuntimeError("v2 immutable manifest already exists")
    assets = recursive_manifest(V2_IMMUTABLE, excluded=[manifest_path])
    payload = {
        "benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V2",
        "parent_benchmark": "PARTIAL_SCAN_BENCHMARK_PILOT_V1",
        "repair_scope": "OUT_OF_PROCESS_POLICY_ISOLATION_ONLY",
        "frozen_at_utc": utc_now(),
        "asset_count": len(assets),
        "assets": assets,
        "immutable_root_hash": canonical_hash(assets),
        "manifest_scope_excludes_self": True,
        "modification_rule": "new benchmark version required",
    }
    atomic_json(manifest_path, payload)
    executable_names = {"sandbox_launcher"}
    for candidate in sorted(V2_IMMUTABLE.rglob("*"), reverse=True):
        if candidate.is_file():
            candidate.chmod(
                0o555 if candidate.name in executable_names else 0o444
            )
        else:
            candidate.chmod(0o555)
    V2_IMMUTABLE.chmod(0o555)
    return payload


def verify_v2_immutable() -> dict[str, Any]:
    path = V2_IMMUTABLE / "immutable_manifest.json"
    manifest = json.loads(path.read_text())
    actual = recursive_manifest(V2_IMMUTABLE, excluded=[path])
    mismatch = [
        relative
        for relative in sorted(set(actual) | set(manifest["assets"]))
        if actual.get(relative) != manifest["assets"].get(relative)
    ]
    root_hash = canonical_hash(actual)
    return {
        "status": (
            "PASS"
            if not mismatch
            and len(actual) == manifest["asset_count"]
            and root_hash == manifest["immutable_root_hash"]
            else "FAIL"
        ),
        "asset_count": len(actual),
        "mismatch_count": len(mismatch),
        "mismatches": mismatch,
        "expected_root_hash": manifest["immutable_root_hash"],
        "computed_root_hash": root_hash,
    }


def code_version(paths: list[Path]) -> dict[str, Any]:
    return {
        "created_at_utc": utc_now(),
        "files": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in paths
        },
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip(),
        "git_worktree_dirty": bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
        ),
    }
