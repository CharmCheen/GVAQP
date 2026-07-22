#!/usr/bin/env python3
"""Execute the preregistered H-SCAN1A smoke and formal physical matrix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from garc_eval.psvr_hscan1a import start_hscan1a_policy_service
from garc_eval.psvr_runtime import durable_json

OUT = REPO / "outputs/psvr_autonomous_research/stage_4_scan_component_ablation"
SMOKE_RAW = OUT / "raw_smoke"; MATRIX_RAW = OUT / "raw_matrix"
STAGE2_RUNNER = REPO / "scripts/run_psvr_core_pilot.py"
METHODS = ("D0", "D1", "D2", "D3")
LABELS = {"D0": "D0 Fixed Coverage", "D1": "D1 Full Composite",
          "D2": "D2 Structural Only", "D3": "D3 Observed Proxy Only"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_stage2(raw: Path):
    spec = importlib.util.spec_from_file_location("psvr_hscan1a_stage2_runtime", STAGE2_RUNNER)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    module.METHOD_LABELS = LABELS; module.start_pilot_policy_service = start_hscan1a_policy_service
    module.OUT = OUT; module.RAW = raw; module.TABLES = OUT / "tables"; module.REPORTS = OUT / "reports"
    return module


def prepare(stage2) -> tuple[dict, dict[str, float]]:
    for directory in (SMOKE_RAW, MATRIX_RAW, OUT / "tables", OUT / "plots", OUT / "reports"):
        directory.mkdir(parents=True, exist_ok=True)
    task_path = OUT / "TASK_MANIFEST.json"; deadline_path = OUT / "DEADLINE_MANIFEST.json"
    components_path = OUT / "COMPONENT_DECOMPOSITION.json"; prereg_path = OUT / "PREREGISTRATION.json"
    task = json.loads(task_path.read_text()); deadline = json.loads(deadline_path.read_text())
    stage3 = json.loads((REPO / "outputs/psvr_autonomous_research/stage_3_factorization/DEV_TASK_MANIFEST.json").read_text())
    config = {"experiment_id": "psvr_H_SCAN1A_revision0", "benchmark_id": task["task"]["benchmark_id"],
              "runtime_identity": stage3["runtime_identity"], "runtime_identity_hash": task["runtime_identity_hash"],
              "deadlines_seconds": deadline["deadlines_seconds"], "methods": LABELS,
              "coverage_debt_parameters": {"lambda": 0.5, "beta": 0.25, "revision": 0},
              "batch_size": 4, "proxy_observation": task["frozen_shared_system"]["proxy"],
              "oracle": task["frozen_shared_system"]["physical_oracle"],
              "materializer": task["frozen_shared_system"]["K3"],
              "snapshot_checkpoint": task["frozen_shared_system"]["snapshot_checkpoints"],
              "heldout_opened": False, "evidence_scope": task["scope"],
              "frozen_input_hashes": {"TASK_MANIFEST.json": sha256(task_path),
                                      "DEADLINE_MANIFEST.json": sha256(deadline_path),
                                      "COMPONENT_DECOMPOSITION.json": sha256(components_path),
                                      "PREREGISTRATION.json": sha256(prereg_path)},
              "implementation_hashes": {"runner": sha256(Path(__file__)),
                                         "policy": sha256(SRC / "garc_eval/psvr_hscan1a/policy_service.py"),
                                         "stage2_physical_runtime": sha256(STAGE2_RUNNER),
                                         "deadline_runtime": sha256(stage2.HDS_PATH),
                                         "proxy_profiler": sha256(stage2.PROFILER_PATH),
                                         "materializer_evaluator": sha256(stage2.MATERIALIZER)}}
    path = OUT / "resolved_config.json"
    if path.exists() and json.loads(path.read_text()) != config:
        raise RuntimeError("H-SCAN1A resolved config changed after freeze")
    if not path.exists():
        durable_json(path, config)
    state = json.loads((REPO / "outputs/psvr_autonomous_research/RESEARCH_STATE.json").read_text())
    durable_json(OUT / "environment.json", {"hardware": task["hardware"],
                                             "runtime_identity_hash": task["runtime_identity_hash"],
                                             "python": sys.version,
                                             "nvidia_smi": subprocess.run(["nvidia-smi", "--query-gpu=name,uuid,driver_version", "--format=csv,noheader"], text=True, capture_output=True, check=False).stdout.strip()})
    (OUT / "git_commit.txt").write_text(str(state.get("git_commit", "UNKNOWN")) + "\n")
    (OUT / "commands.sh").write_text("#!/usr/bin/env bash\nPYTHONPATH=src pytest -q tests/psvr_runtime\nPYTHONPATH=src python scripts/verify_psvr_hscan1a.py\npython scripts/run_psvr_hscan1a.py smoke\nPYTHONPATH=src python scripts/verify_psvr_hscan1a.py\npython scripts/run_psvr_hscan1a.py matrix\npython scripts/evaluate_psvr_hscan1a.py\n")
    return config, dict(deadline["deadlines_seconds"])


def attempted(raw: Path, method: str, deadline: str, replicate: int) -> bool:
    root = raw / f"{method}__{deadline}__replicate_{replicate:02d}"
    return any(root.glob("attempt_*/complete.json")) or any(root.glob("attempt_*/failed.json"))


def physical_count() -> int:
    count = sum(1 for _ in OUT.glob("raw_*/*/attempt_*/complete.json"))
    for path in OUT.glob("raw_*/*/attempt_*/failed.json"):
        count += json.loads(path.read_text()).get("run_elapsed_seconds") is not None
    return count


def execute(phase: str) -> None:
    raw = SMOKE_RAW if phase == "smoke" else MATRIX_RAW
    stage2 = load_stage2(raw); config, deadlines = prepare(stage2)
    if phase == "matrix":
        smoke = json.loads((OUT / "SMOKE_REPORT.json").read_text())
        equivalence = json.loads((OUT / "FULL_EQUIVALENCE_REPORT.json").read_text())
        if smoke.get("decision") != "VALID" or equivalence.get("gate") != "PASS" or not equivalence.get("physical_smoke_prefix_equivalent"):
            raise RuntimeError("smoke/equivalence gate is not valid")
    hds = stage2.load_module(f"psvr_hscan1a_hds_{phase}", stage2.HDS_PATH)
    profiler = stage2.load_module(f"psvr_hscan1a_profiler_{phase}", stage2.PROFILER_PATH)
    jobs = ([(method, "T_transition", deadlines["T_transition"], 0) for method in METHODS]
            if phase == "smoke" else
            [(method, deadline, deadlines[deadline], replicate) for method in METHODS
             for deadline in ("T_transition", "T_high") for replicate in range(3)])
    for method, deadline_name, deadline, replicate in jobs:
        if attempted(raw, method, deadline_name, replicate):
            continue
        if physical_count() >= 28:
            raise RuntimeError("H-SCAN1A physical cap 28 reached")
        stage2.run_one(method, deadline_name, deadline, replicate, config, hds, profiler)
    rows = [json.loads(path.read_text()) for path in raw.glob("*/attempt_*/complete.json")]
    failures = list(raw.glob("*/attempt_*/failed.json"))
    summary = {"phase": phase, "expected": len(jobs), "completed": len(rows), "failures": len(failures),
               "deadline_misses": sum(not row["deadline_met"] for row in rows),
               "cache_replays": sum(row["cache_replay_calls"] for row in rows),
               "future_proxy_accesses": sum(row["future_proxy_accesses"] for row in rows),
               "visibility_violations": sum(row["candidate_observation_violations"] for row in rows),
               "complete_snapshots": sum(Path(row["final_snapshot_path"]).exists() for row in rows),
               "physical_count_total": physical_count()}
    if phase == "smoke":
        summary["decision"] = "VALID" if all([len(rows) == 4, not failures,
                                                summary["deadline_misses"] == 0,
                                                summary["cache_replays"] == 0,
                                                summary["future_proxy_accesses"] == 0,
                                                summary["visibility_violations"] == 0,
                                                summary["complete_snapshots"] == 4]) else "INVALID"
        durable_json(OUT / "SMOKE_REPORT.json", summary)
    else:
        durable_json(OUT / "PHYSICAL_RUN_AUDIT.json", summary)
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("phase", choices=("smoke", "matrix")); args = parser.parse_args()
    execute(args.phase)


if __name__ == "__main__":
    main()
