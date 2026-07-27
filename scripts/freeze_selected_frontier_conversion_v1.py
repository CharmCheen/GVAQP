#!/usr/bin/env python3
"""Freeze the V1 calibration contract before evaluating the input gate."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/selected_frontier_conversion_v1"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else "UNAVAILABLE"


def main() -> None:
    created = datetime.now(timezone.utc).isoformat()
    previous_freeze = OUT / "contracts/freeze_manifest.json"
    previous_manifest = json.loads(previous_freeze.read_text()) if previous_freeze.exists() else None
    assets = [
        ROOT / "docs/SELECTED_FRONTIER_CONVERSION_CALIBRATION_CONTRACT_V1.md",
        ROOT / "scripts/freeze_selected_frontier_conversion_v1.py",
        ROOT / "scripts/audit_selected_frontier_conversion_inputs_v1.py",
        ROOT / "outputs/scan_confirm_common_utility_v1/reports/FINAL_DECISION.md",
        ROOT / "outputs/scan_confirm_decision_v1/fixed_ratio_baselines/selected_controller.json",
        ROOT / "outputs/online_macro_activity_replication/technical_normalization/HANGZHOU_PAIR_CONTENT_IDENTITY_AUDIT.json",
        ROOT / "outputs/online_macro_activity_replication/reports/INPUT_ELIGIBILITY_REPORT.md",
        ROOT / "outputs/psvr_autonomous_research/benchmark_unblock/SOURCE_INDEPENDENCE_AUDIT.json",
        ROOT / "docs/PSVR_FAILURE_CATALOG.md",
        ROOT / "src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/tables/media_manifest.csv",
    ]
    assets += sorted((ROOT / "data/realcam/long_video_data").glob("*.source.json"))
    assets += sorted((ROOT / "data/realcam/psvr_dev_inputs").glob("*.source.json"))
    missing = [str(p.relative_to(ROOT)) for p in assets if not p.is_file()]
    if missing:
        raise SystemExit(f"required freeze assets missing: {missing}")
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in assets}
    env = {
        "created_utc": created, "python": platform.python_version(),
        "platform": platform.platform(), "ffprobe": subprocess.run(
            ["ffprobe", "-version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
    }
    write(OUT / "environment_lock.json", env)
    code = {"commit": git("rev-parse", "HEAD"), "worktree_status": git("status", "--short")}
    write(OUT / "code_version.json", code)
    contract = ROOT / "docs/SELECTED_FRONTIER_CONVERSION_CALIBRATION_CONTRACT_V1.md"
    manifest = {
        "status": "REFROZEN_AFTER_NON_SEMANTIC_INVENTORY_SCOPE_REPAIR" if previous_manifest else "FROZEN_BEFORE_INPUT_GATE_EVALUATION",
        "created_utc": created,
        "contract_sha256": sha(contract),
        "environment_lock_sha256": sha(OUT / "environment_lock.json"),
        "code_version_sha256": sha(OUT / "code_version.json"),
        "assets": hashes,
        "semantic_artifacts_authorized": False,
        "new_oracle_calls_authorized": False,
    }
    if previous_manifest:
        manifest["pre_repair_freeze_manifest"] = previous_manifest
        manifest["repair_scope"] = "Added explicit inventory rows for three already-known excluded media files; no eligibility rule or semantic result changed."
    write(OUT / "contracts/freeze_manifest.json", manifest)
    write(OUT / "contracts/input_selection_protocol.json", {
        "status": "FROZEN", "required_new_sources": 4,
        "ordering": ["registration_utc ASC", "source_filename ASC"],
        "role_assignment": "first three eligible calibration/validation; fourth eligible sealed test",
        "legacy_registration_rule": "hash-bound prior audit or attestation date",
        "replacement_based_on_semantics": "PROHIBITED",
    })
    write(OUT / "repair_log.json", {
        "max_repair_cycles": 1,
        "repairs": ([{
            "repair_id": 1,
            "reason": "Independent verification found three >100MB media files omitted from the explicit inventory table.",
            "change": "Inventory and exclude the V0-derived review clip, canonical 43-second heldout, and 208-second realcartest_5k derivative.",
            "scientific_effect": "No count or gate decision changed; semantic artifacts remained unopened and Oracle calls remained zero.",
        }] if previous_manifest else []),
    })


if __name__ == "__main__":
    main()
