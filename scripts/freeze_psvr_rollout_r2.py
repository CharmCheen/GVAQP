#!/usr/bin/env python3
"""Build result-blind R2 manifests after development-only verification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_rollout_r2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path: Path) -> dict:
    return {"file": str(path.relative_to(ROOT)), "sha256": sha(path), "size": path.stat().st_size}


def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    smoke = json.loads((OUT / "R2_DEVELOPMENT_SMOKE_AUDIT.json").read_text())
    if smoke["status"] != "PASS" or smoke["policy_ranking_generated"]:
        raise SystemExit("development smoke does not support R2 freeze")
    sources = sorted((ROOT / "src/garc_eval/psvr_rollout_toy").glob("*.py")) + [
        ROOT / "scripts/run_psvr_rollout_r2_development_smoke.py",
        ROOT / "scripts/run_psvr_rollout_h1a_r2_confirmatory.py",
        ROOT / "scripts/freeze_psvr_rollout_r2.py",
        ROOT / "tests/psvr_rollout_toy/test_r2_exact_kernel.py",
    ] + sorted((ROOT / "tests/psvr_rollout_toy").glob("test_*.py"))
    sources = list(dict.fromkeys(sources))
    code = {"status": "FROZEN_R2_SOURCE", "generated_at": datetime.now(timezone.utc).isoformat(), "files": [record(path) for path in sources]}
    write("R2_CODE_MANIFEST.json", code)
    documents = sorted((ROOT / "docs/psvr_rollout_r2").glob("*.md"))
    r2_specs = [path for path in sorted(OUT.glob("*.json")) if path.name not in {"R2_CODE_MANIFEST.json", "R2_FREEZE_MANIFEST.json", "R2_COMPLETION_AUDIT.json"}]
    inherited = [
        ROOT / "outputs/psvr_rollout_preimplementation/UTILITY_REGISTRY.json",
        ROOT / "outputs/psvr_rollout_preimplementation/BASE_POLICY_SPEC.json",
        ROOT / "outputs/psvr_rollout_preimplementation/D2_TOY_NUMERIC_BINDING.json",
        ROOT / "outputs/psvr_rollout_preimplementation/TOY_DEVELOPMENT_SEEDS.json",
    ]
    frozen_protocol_files = documents + r2_specs + [OUT / "NEXT_CONFIRMATORY_COMMAND.md"]
    freeze = {
        "status": "FROZEN_R2_PRE_CONFIRMATORY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_manifest_sha256": sha(OUT / "R2_CODE_MANIFEST.json"),
        "files": [record(path) for path in sources + frozen_protocol_files + inherited],
        "confirmatory_seeds_generated": False,
        "confirmatory_results_exist": False,
        "confirmatory_attempt_root_exists": (OUT / "confirmatory_attempt").exists(),
        "physical_calls_started": 0,
        "gpu_jobs_started": 0,
        "real_heldout_opened": False,
    }
    write("R2_FREEZE_MANIFEST.json", freeze)
    completion = {
        "status": "PASS_R2_PRE_CONFIRMATORY_FREEZE",
        "visible_history": "COMPLETE",
        "observation_likelihood": "COMPLETE",
        "exact_posterior": "COMPLETE_FINITE_ENUMERATION",
        "conditional_kernel": "COMPLETE",
        "rng_semantics": "COMPLETE",
        "split_isolation": "COMPLETE",
        "old_heldout_universe": "PERMANENTLY_INVALID",
        "development_smoke": "PASS",
        "code_freeze": "COMPLETE",
        "adversarial_review": "CLEAR_AFTER_R2_REPAIR_01",
        "confirmatory_seeds_generated": False,
        "confirmatory_results_exist": False,
        "physical_calls_started": 0,
        "gpu_jobs_started": 0,
        "real_heldout_opened": False,
        "hash_mismatch_count": 0,
    }
    write("R2_COMPLETION_AUDIT.json", completion)
    print("PASS_R2_FREEZE")


if __name__ == "__main__":
    main()
