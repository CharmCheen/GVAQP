#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy
import pandas
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/scan_confirm_decision_v1"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", f"--git-dir={ROOT / '.git'}", f"--work-tree={ROOT}", *args], text=True
    ).strip()


def main() -> None:
    contract = ROOT / "docs/SCAN_CONFIRM_DECISION_BENCHMARK_CONTRACT_V1.md"
    assets = [
        contract,
        ROOT / "configs/scan_confirm_myopic_vps.yaml",
        ROOT / "configs/safe_coverage_scan.yaml",
        ROOT / "src/garc_eval/scan_scheduler/policy.py",
        ROOT / "src/garc_eval/scan_headroom/trusted_policies.py",
        ROOT / "scripts/run_psvr_two_video_physical.py",
        ROOT / "scripts/run_psvr_two_video_proxy.py",
        ROOT / "src/garc_eval/psvr_exposure/policy_service.py",
        ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py",
        ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/BENCHMARK_MANIFEST.json",
        ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/TASK_MANIFEST.json",
        ROOT / "outputs/psvr_two_video_loop/state/FRONTIER_CAPACITY_FREEZE.json",
        ROOT / "outputs/psvr_two_video_loop/final_proxy/FINAL_PROXY_CONFIG.json",
        ROOT / "outputs/psvr_two_video_loop/deadlines/TASK_DEADLINE_MANIFEST.json",
    ] + sorted((ROOT / "src/garc_eval/scan_confirm_controller").glob("*.py")) + sorted(
        (ROOT / "scripts").glob("*scan_confirm*.py")
    )
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in assets}
    scan_hash = canon({k: v for k, v in hashes.items() if "scan_" in k or "safe_coverage" in k})
    confirm_hash = canon({k: v for k, v in hashes.items() if "benchmark_lib" in k or "BENCHMARK_MANIFEST" in k})
    frontier_hash = canon({k: v for k, v in hashes.items() if "FRONTIER" in k or "psvr_exposure" in k})
    mapping_hash = canon({
        "task_manifest": hashes["outputs/psvr_two_video_loop/dev_benchmark_v1/TASK_MANIFEST.json"],
        "references": {p.name: sha(p) for p in sorted((ROOT / "outputs/psvr_two_video_loop/dev_benchmark_v1/reference_events").glob("*.csv"))},
    })
    deadline_hash = canon({k: v for k, v in hashes.items() if "deadline" in k.lower()})
    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    environment = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "pyyaml": yaml.__version__,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    write(OUT / "environment_lock.json", environment)
    write(OUT / "code_version.json", {"code_commit": commit, "worktree_dirty": dirty})
    manifest = {
        "freeze_status": "FROZEN_BEFORE_CONTROLLER_EVALUATION",
        "created_utc": environment["created_utc"],
        "contract_hash": sha(contract),
        "code_commit": commit,
        "code_worktree_dirty": dirty,
        "asset_manifest_hash": canon(hashes),
        "environment_lock": sha(OUT / "environment_lock.json"),
        "scan_primitive_hash": scan_hash,
        "confirm_operator_hash": confirm_hash,
        "frontier_contract_hash": frontier_hash,
        "event_mapping_contract_hash": mapping_hash,
        "deadline_contract_hash": deadline_hash,
        "assets": hashes,
    }
    write(OUT / "contracts/freeze_manifest.json", manifest)
    write(OUT / "repair_log.json", {"max_repair_cycles": 1, "repairs": []})
    write(OUT / "contracts/public_state_schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "SCAN_CONFIRM_PUBLIC_STATE_V1",
        "type": "object",
        "additionalProperties": False,
        "required": sorted([
            "remaining_budget_sec", "coverage_fraction", "maximum_unobserved_gap_sec",
            "scan_actions_completed", "scan_time_spent_sec", "frontier_size",
            "frontier_score_min", "frontier_score_median", "frontier_score_max",
            "frontier_score_quantiles", "oldest_candidate_age_sec", "newest_candidate_age_sec",
            "novel_candidate_clusters_observed", "confirmed_distinct_utility_count",
            "recent_scan_novel_yield", "recent_scan_zero_yield_streak",
            "recent_confirm_success_rate", "recent_confirm_new_utility_rate",
            "recent_confirm_zero_yield_streak", "estimated_scan_cost_sec",
            "estimated_confirm_cost_sec", "actions_completed", "unused_budget_sec",
        ]),
        "properties": {},
        "forbidden_policy_fields": [
            "video_id", "filename", "source_dataset_id", "reference_event_locations",
            "future_scan_candidates", "future_confirm_outcomes", "future_actual_costs",
            "offline_action_oracle_order", "complete_event_count", "held_out_result",
        ],
    })
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
