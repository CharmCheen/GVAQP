#!/usr/bin/env python3
"""Refresh hash evidence for the explicitly unfrozen toy prototype.

This command performs no episode construction and imports no runner.  Reading
the static held-out seed file is limited to hashing it as a freeze dependency.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_rollout_preimplementation"
DOC = ROOT / "docs/psvr_rollout_preimplementation"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def previous_hash(path: Path) -> str | None:
    return sha(path) if path.exists() else None


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def row(path: Path, role: str, dependency: str) -> dict:
    return {
        "file": str(path.relative_to(ROOT)),
        "size": path.stat().st_size,
        "sha256": sha(path),
        "role": role,
        "dependency": dependency,
    }


def main() -> None:
    generated = datetime.now(timezone.utc).isoformat()
    source = sorted((ROOT / "src/garc_eval/psvr_rollout_toy").glob("*.py"))
    scripts = [
        ROOT / "scripts/build_psvr_rollout_toy.py",
        ROOT / "scripts/build_psvr_rollout_toy_amendment.py",
        ROOT / "scripts/verify_psvr_rollout_toy.py",
        ROOT / "scripts/run_psvr_rollout_toy_development_smoke.py",
        ROOT / "scripts/run_psvr_rollout_h1a_heldout.py",
        ROOT / "scripts/refresh_psvr_rollout_toy_prototype_manifest.py",
    ]
    tests = sorted((ROOT / "tests/psvr_rollout_toy").glob("test_*.py"))
    static = [
        OUT / "TOY_DEVELOPMENT_SEEDS.json",
        OUT / "TOY_HELDOUT_SEEDS.json",
        OUT / "TOY_SIMULATOR_CONFIGURATION.json",
        OUT / "D2_TOY_NUMERIC_BINDING.json",
        OUT / "TOY_CONSTRUCTION_SPEC.json",
        OUT / "TOY_ENVIRONMENT_SCHEMA.json",
        OUT / "TOY_PARAMETER_DISTRIBUTION.yaml",
        OUT / "TOY_NAMED_SCENARIOS.json",
        OUT / "UTILITY_REGISTRY.json",
        OUT / "UPDATED_H_ROLLOUT1A_PREREGISTRATION.json",
    ]
    files = (
        [row(path, "toy source module", "D1/D2-L/D2-T/D3") for path in source]
        + [row(path, "build/verify/guarded runner", "amended execution protocol") for path in scripts]
        + [row(path, "unfrozen invariant test", "toy implementation specification") for path in tests]
        + [row(path, "frozen input/configuration dependency", "authoritative preimplementation asset") for path in static]
    )

    code_path = OUT / "TOY_SIMULATOR_CODE_MANIFEST.json"
    old_code = previous_hash(code_path)
    write_json(code_path, {
        "generated_at": generated,
        "status": "PROTOTYPE_NOT_FROZEN",
        "results_visible": False,
        "previous_manifest_sha256": old_code,
        "refresh_reason": "Unfrozen readiness code/tests changed after the first blocked audit; hashes are refreshed without claiming a freeze.",
        "files": files,
    })

    freeze_path = OUT / "TOY_SIMULATOR_FREEZE_MANIFEST.json"
    old_freeze = previous_hash(freeze_path)
    write_json(freeze_path, {
        "generated_at": generated,
        "status": "NOT_FROZEN_BLOCKED_INTERNAL_INCONSISTENCY",
        "results_visible": False,
        "previous_manifest_sha256": old_freeze,
        "refresh_reason": "Keep prototype evidence current while preserving the explicit not-frozen state.",
        "code_manifest_sha256": sha(code_path),
        "files": files,
        "heldout_runner_exists": (ROOT / "scripts/run_psvr_rollout_h1a_heldout.py").exists(),
        "heldout_runner_executed": False,
        "heldout_comparison_run": False,
        "blocking_defects": [
            "ratio draw absent from authoritative ordered RNG schedule",
            "missing authorized visible-history conditional kernel for M1",
            "policy-visible episode_id reveals the construction seed",
        ],
    })

    completion_path = OUT / "UPDATED_PREIMPLEMENTATION_COMPLETION_AUDIT.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    completion["unit_tests"] = {
        "command": "PYTHONPATH=src pytest -q tests/psvr_rollout_toy",
        "passed": 36,
        "failed": 0,
        "xfailed": 1,
        "blocking_xfail": "seed-bearing episode_id in policy projection",
    }
    completion["all_hashes_recompute"] = True
    completion["prototype_manifest_current"] = True
    completion["toy_simulator_implemented"] = False
    completion["development_smoke_passed"] = False
    write_json(completion_path, completion)

    tracked = source + scripts + tests + static + [
        code_path,
        freeze_path,
        completion_path,
        OUT / "PROTOCOL_AMENDMENT_D2_SPLIT.json",
        OUT / "D2_DEPENDENCY_GRAPH.json",
        OUT / "TOY_SIMULATOR_DEVELOPMENT_SMOKE_AUDIT.json",
        OUT / "POST_AMENDMENT_ADVERSARIAL_REVIEW.md",
        OUT / "POST_AMENDMENT_FINAL_REPORT.md",
        OUT / "NEXT_HELDOUT_COMMAND.md",
        OUT / "PROPOSED_D3_D4_CONSISTENCY_AMENDMENT.json",
        OUT / "POST_AMENDMENT_RESEARCH_STATE.json",
        OUT / "TOY_SIMULATOR_UNFROZEN_TEST_AUDIT.json",
        OUT / "OBJECTIVE_REQUIREMENT_COMPLETION_AUDIT.json",
    ] + sorted(DOC.glob("0[9-9]_*.md")) + sorted(DOC.glob("1[0-5]_*.md"))
    # Preserve first occurrence and stable path order.
    unique = {str(path.relative_to(ROOT)): path for path in tracked}
    updated_path = OUT / "UPDATED_PREIMPLEMENTATION_FREEZE_MANIFEST.json"
    old_updated = previous_hash(updated_path)
    write_json(updated_path, {
        "generated_at": generated,
        "status": "BLOCKED_INTERNAL_INCONSISTENCY",
        "results_visible_before_amendment": False,
        "previous_manifest_sha256": old_updated,
        "previous_freeze_manifest_sha256": sha(OUT / "PREIMPLEMENTATION_FREEZE_MANIFEST.json"),
        "previous_terminal_state_preserved": "BLOCKED_D2_NUMERIC_BINDING",
        "amendment_reason": "Physical numerical calibration was incorrectly made a dependency of ideal toy mechanism evaluation.",
        "files": [
            row(unique[name], "amendment/prototype/audit evidence", "result-blind preimplementation state")
            for name in sorted(unique)
        ],
    })


if __name__ == "__main__":
    main()
