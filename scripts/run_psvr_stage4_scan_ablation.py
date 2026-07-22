#!/usr/bin/env python3
"""Run exactly the 18 preregistered physical S2/S3/S4 component ablations."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from garc_eval.psvr_runtime import durable_json
from garc_eval.psvr_scan_ablation import start_scan_ablation_policy_service

OUT = REPO / "outputs/psvr_autonomous_research/stage_4_scan_component_ablation"
RAW = OUT / "raw_matrix"
STAGE2_RUNNER = REPO / "scripts/run_psvr_core_pilot.py"
METHODS = ("S2", "S3", "S4")
LABELS = {"S2": "S2 Duration+Proxy", "S3": "S3 Duration+Debt", "S4": "S4 Debt+Proxy"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_stage2():
    spec = importlib.util.spec_from_file_location("psvr_stage4_stage2_runtime", STAGE2_RUNNER)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.METHOD_LABELS = LABELS
    module.start_pilot_policy_service = start_scan_ablation_policy_service
    module.OUT = OUT; module.RAW = RAW
    module.TABLES = OUT / "tables"; module.REPORTS = OUT / "reports"
    return module


def prepare(stage2) -> tuple[dict, dict[str, float]]:
    RAW.mkdir(parents=True, exist_ok=True); (OUT / "tables").mkdir(exist_ok=True); (OUT / "reports").mkdir(exist_ok=True)
    manifest_path = OUT / "DEV_TASK_MANIFEST.json"; prereg_path = OUT / "PREREGISTRATION.json"
    manifest = json.loads(manifest_path.read_text()); prereg = json.loads(prereg_path.read_text())
    stage3 = json.loads((REPO / "outputs/psvr_autonomous_research/stage_3_factorization/DEV_TASK_MANIFEST.json").read_text())
    config = {
        "experiment_id": "psvr_stage_4_H_SCAN_COMP1_v1",
        "benchmark_id": manifest["task"]["benchmark_id"],
        "runtime_identity": stage3["runtime_identity"],
        "runtime_identity_hash": manifest["runtime_identity_hash"],
        "deadlines_seconds": manifest["deadlines_seconds"],
        "methods": LABELS,
        "coverage_debt_parameters": {"lambda": 0.5, "beta": 0.25, "revision": 0},
        "batch_size": 4,
        "proxy_observation": manifest["shared_physical_rules"]["proxy"],
        "oracle": manifest["shared_physical_rules"]["oracle"],
        "materializer": manifest["shared_physical_rules"]["K3"],
        "snapshot_checkpoint": manifest["shared_physical_rules"]["snapshots"],
        "heldout_opened": False,
        "evidence_scope": manifest["scope"],
        "scan_quota_batches": 29,
        "expected_physical_VERIFY": 5,
        "frozen_input_hashes": {"manifest": sha256(manifest_path), "preregistration": sha256(prereg_path)},
        "implementation_hashes": {
            "runner": sha256(Path(__file__)),
            "policy": sha256(SRC / "garc_eval/psvr_scan_ablation/policy_service.py"),
            "stage2_physical_runtime": sha256(STAGE2_RUNNER),
            "deadline_runtime": sha256(stage2.HDS_PATH),
            "proxy_profiler": sha256(stage2.PROFILER_PATH),
            "materializer_evaluator": sha256(stage2.MATERIALIZER),
        },
        "component_methods": prereg["methods"],
    }
    path = OUT / "resolved_config.json"
    if path.exists() and json.loads(path.read_text()) != config:
        raise RuntimeError("Stage-4 resolved config changed after freeze")
    if not path.exists():
        durable_json(path, config)
    return config, dict(manifest["deadlines_seconds"])


def attempted(method: str, deadline: str, replicate: int) -> bool:
    root = RAW / f"{method}__{deadline}__replicate_{replicate:02d}"
    return any(root.glob("attempt_*/complete.json")) or any(root.glob("attempt_*/failed.json"))


def physical_attempts() -> int:
    completed = sum(1 for _ in RAW.glob("*/attempt_*/complete.json"))
    failed = sum(json.loads(path.read_text()).get("run_elapsed_seconds") is not None
                 for path in RAW.glob("*/attempt_*/failed.json"))
    return completed + failed


def main() -> None:
    stage2 = load_stage2(); config, deadlines = prepare(stage2)
    hds = stage2.load_module("psvr_stage4_hds", stage2.HDS_PATH)
    profiler = stage2.load_module("psvr_stage4_profiler", stage2.PROFILER_PATH)
    jobs = [(method, deadline, deadlines[deadline], replicate)
            for method in METHODS for deadline in ("T_transition", "T_high") for replicate in range(3)]
    for method, deadline_name, deadline, replicate in jobs:
        if attempted(method, deadline_name, replicate):
            continue
        if physical_attempts() >= 18:
            raise RuntimeError("Stage-4 physical cap 18 reached")
        stage2.run_one(method, deadline_name, deadline, replicate, config, hds, profiler)
    completed = [json.loads(path.read_text()) for path in RAW.glob("*/attempt_*/complete.json")]
    summary = {"expected": 18, "completed": len(completed),
               "runtime_failures": len(list(RAW.glob("*/attempt_*/failed.json"))),
               "deadline_misses": sum(not row["deadline_met"] for row in completed),
               "cache_replays": sum(row["cache_replay_calls"] for row in completed),
               "future_proxy_accesses": sum(row["future_proxy_accesses"] for row in completed),
               "candidate_observation_violations": sum(row["candidate_observation_violations"] for row in completed),
               "physical_attempts": physical_attempts()}
    durable_json(OUT / "MATRIX_RESULTS.json", summary); print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
