#!/usr/bin/env python3
"""Execute preregistered H-SCAN1B tie gate and conditional factorial."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]; SRC = REPO / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
from garc_eval.psvr_hscan1b import start_hscan1b_policy_service
from garc_eval.psvr_runtime import durable_json

OUT = REPO / "outputs/psvr_autonomous_research/cycle_05_H_SCAN1B"
STAGE2 = REPO / "scripts/run_psvr_core_pilot.py"
LABELS = {m: m for m in ("TB0", "TB1", "TB2", "F00", "F10", "F01", "F11")}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024): h.update(chunk)
    return h.hexdigest()


def load_runtime(raw: Path):
    spec = importlib.util.spec_from_file_location("psvr_hscan1b_stage2_runtime", STAGE2)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    module.METHOD_LABELS = LABELS; module.start_pilot_policy_service = start_hscan1b_policy_service
    module.OUT = OUT; module.RAW = raw; module.TABLES = OUT / "tables"; module.REPORTS = OUT / "reports"
    return module


def prepare(runtime) -> tuple[dict, dict[str, float]]:
    task_path = OUT / "TASK_MANIFEST.json"; deadline_path = OUT / "DEADLINE_MANIFEST.json"
    prereg_path = OUT / "PREREGISTRATION.json"
    task = json.loads(task_path.read_text()); deadline = json.loads(deadline_path.read_text())
    prior_config = json.loads((REPO / "outputs/psvr_autonomous_research/stage_4_scan_component_ablation/resolved_config.json").read_text())
    config = {"experiment_id": "psvr_H_SCAN1B_revision0", "benchmark_id": task["task"]["benchmark_id"],
              "runtime_identity": prior_config["runtime_identity"], "runtime_identity_hash": task["runtime_identity_hash"],
              "deadlines_seconds": deadline["deadlines_seconds"], "methods": LABELS,
              "coverage_debt_parameters": {"lambda": 0.5, "beta": 0.25, "revision": 0},
              "batch_size": 4, "proxy_observation": task["frozen_shared_system"]["proxy"],
              "oracle": task["frozen_shared_system"]["physical_oracle"],
              "materializer": task["frozen_shared_system"]["K3"],
              "snapshot_checkpoint": task["frozen_shared_system"]["snapshot_checkpoints"],
              "heldout_opened": False, "evidence_scope": task["scope"],
              "frozen_input_hashes": {p.name: sha256(p) for p in (task_path, deadline_path, prereg_path)},
              "implementation_hashes": {"runner": sha256(Path(__file__)),
                  "policy": sha256(SRC / "garc_eval/psvr_hscan1b/policy_service.py"),
                  "stage2_physical_runtime": sha256(STAGE2), "deadline_runtime": sha256(runtime.HDS_PATH),
                  "proxy_profiler": sha256(runtime.PROFILER_PATH), "materializer_evaluator": sha256(runtime.MATERIALIZER)}}
    path = OUT / "resolved_config.json"
    if path.exists() and json.loads(path.read_text()) != config: raise RuntimeError("resolved config changed")
    if not path.exists(): durable_json(path, config)
    state = json.loads((REPO / "outputs/psvr_autonomous_research/RESEARCH_STATE.json").read_text())
    durable_json(OUT / "environment.json", {"hardware": task["hardware"], "runtime_identity_hash": task["runtime_identity_hash"],
        "python": sys.version, "nvidia_smi": subprocess.run(["nvidia-smi", "--query-gpu=name,uuid,driver_version", "--format=csv,noheader"], text=True, capture_output=True, check=False).stdout.strip()})
    (OUT / "git_commit.txt").write_text(str(state.get("git_commit", "UNKNOWN")) + "\n")
    return config, dict(deadline["deadlines_seconds"])


def attempted(raw: Path, method: str, deadline: str, replicate: int) -> bool:
    root = raw / f"{method}__{deadline}__replicate_{replicate:02d}"
    return any(root.glob("attempt_*/complete.json")) or any(root.glob("attempt_*/failed.json"))


def physical_count() -> int:
    return sum(1 for _ in OUT.glob("raw_*/*/attempt_*/complete.json")) + sum(1 for _ in OUT.glob("raw_*/*/attempt_*/failed.json"))


def execute(phase: str) -> None:
    raw = OUT / ("raw_tie" if phase == "tie" else "raw_factorial")
    runtime = load_runtime(raw); config, deadlines = prepare(runtime)
    if json.loads((OUT / "CORRECTNESS_REPORT.json").read_text()).get("gate") != "PASS":
        raise RuntimeError("correctness gate failed")
    if phase == "factorial":
        tie = json.loads((OUT / "TIE_GATE_DECISION.json").read_text())
        if tie.get("decision") not in ("STRONG", "WEAK"):
            raise RuntimeError("factorial not authorized by tie gate")
    methods = ("TB0", "TB1", "TB2") if phase == "tie" else ("F00", "F10", "F01", "F11")
    deadline_names = ("T_transition",) if phase == "tie" else ("T_transition", "T_high")
    jobs = [(m, d, deadlines[d], r) for m in methods for d in deadline_names for r in range(3)]
    hds = runtime.load_module(f"psvr_hscan1b_hds_{phase}", runtime.HDS_PATH)
    profiler = runtime.load_module(f"psvr_hscan1b_profiler_{phase}", runtime.PROFILER_PATH)
    for method, deadline_name, deadline, replicate in jobs:
        if attempted(raw, method, deadline_name, replicate): continue
        if physical_count() >= 33: raise RuntimeError("H-SCAN1B physical cap reached")
        runtime.run_one(method, deadline_name, deadline, replicate, config, hds, profiler)
    rows = [json.loads(p.read_text()) for p in raw.glob("*/attempt_*/complete.json")]
    failures = list(raw.glob("*/attempt_*/failed.json"))
    summary = {"phase": phase, "expected": len(jobs), "completed": len(rows), "failures": len(failures),
               "deadline_misses": sum(not r["deadline_met"] for r in rows),
               "cache_replays": sum(r["cache_replay_calls"] for r in rows),
               "future_proxy_accesses": sum(r["future_proxy_accesses"] for r in rows),
               "visibility_violations": sum(r["candidate_observation_violations"] for r in rows),
               "complete_snapshots": sum(Path(r["final_snapshot_path"]).exists() for r in rows),
               "physical_count_total": physical_count()}
    durable_json(OUT / f"{phase.upper()}_PHYSICAL_AUDIT.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("phase", choices=("tie", "factorial")); execute(p.parse_args().phase)
