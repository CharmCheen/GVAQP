#!/usr/bin/env python3
"""Verify and freeze the B0 CPU-only qualification package."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import py_compile
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "cpu_only_claim_b_restart_20260824"
MANIFEST = PACKAGE / "B0_CPU_FREEZE_MANIFEST.json"
REPORT = PACKAGE / "06_B0_CPU_QUALIFICATION_REPORT.md"

ALLOWLIST = (
    "PROJECT_STATE_OF_TRUTH.md",
    "CLAIM_LEDGER.csv",
    "EXPERIMENT_DECISION_LEDGER.csv",
    "ACTIVE_HYPOTHESES.md",
    "CLOSED_BRANCHES.md",
    "NEXT_STAGE_STATE_MACHINE.md",
    "src/garc/endogenous_contract.py",
    "tests/test_endogenous_contract.py",
    "scripts/freeze_claim_b_cpu_contract.py",
    "scripts/audit_t2_comparator_semantics_cpu.py",
    "outputs/t2_comparator_semantics_cpu_audit_v1/REPORT.md",
    "outputs/t2_comparator_semantics_cpu_audit_v1/SUMMARY.json",
    "docs/cpu_only_claim_b_restart_20260824/00_P0_PIVOT_PACKET.md",
    "docs/cpu_only_claim_b_restart_20260824/01_B0_ACTION_INFORMATION_CONTRACT.md",
    "docs/cpu_only_claim_b_restart_20260824/02_CLAIM_EVIDENCE_MATRIX.csv",
    "docs/cpu_only_claim_b_restart_20260824/03_BASELINE_MATRIX.csv",
    "docs/cpu_only_claim_b_restart_20260824/04_WORKLOAD_SPLIT_AND_CONSUMPTION_RULES.md",
    "docs/cpu_only_claim_b_restart_20260824/05_CPU_EXECUTION_AND_STOP_RULES.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    if MANIFEST.exists() or REPORT.exists():
        raise SystemExit("refusing to overwrite frozen B0 output")
    for relative in ALLOWLIST:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"missing allowlisted file: {relative}")

    ledger_counts = {}
    for relative in ("CLAIM_LEDGER.csv", "EXPERIMENT_DECISION_LEDGER.csv"):
        with (ROOT / relative).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows or any(None in row for row in rows):
            raise SystemExit(f"invalid CSV ledger: {relative}")
        ledger_counts[relative] = len(rows)

    py_compile.compile(str(ROOT / "src/garc/endogenous_contract.py"), doraise=True)
    command = [
        sys.executable, "-m", "pytest", "-q",
        "tests/test_endogenous_contract.py", "tests/test_causal_frontier.py",
    ]
    completed = subprocess.run(
        command, cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": "src"},
        text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stdout + completed.stderr)
    if "26 passed" not in completed.stdout:
        raise SystemExit("unexpected test count; refusing to freeze")

    sys.path.insert(0, str(ROOT / "src"))
    from garc.endogenous_contract import PublicState  # pylint: disable=import-outside-toplevel
    forbidden = ("reference", "truth", "label", "oracle")
    public_fields = tuple(PublicState.__dataclass_fields__)
    leaked = [name for name in public_fields if any(token in name for token in forbidden)]
    if leaked:
        raise SystemExit(f"forbidden public fields: {leaked}")

    manifest = {
        "schema_version": 1,
        "decision": "B0_CPU_INFRASTRUCTURE_QUALIFIED",
        "claim_boundary": "contract qualification only; C-B1 through C-B3 remain not established",
        "execution_class": "CPU_ONLY_SYNTHETIC_AND_READ_ONLY",
        "tests": completed.stdout.strip(),
        "ledger_rows": ledger_counts,
        "public_state_fields": public_fields,
        "forbidden_public_fields": leaked,
        "files": {relative: sha256(ROOT / relative) for relative in ALLOWLIST},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = """# B0 CPU qualification report

## Verdict

`B0_CPU_INFRASTRUCTURE_QUALIFIED`

The reference-blind endogenous executor satisfies the eight frozen B0
invariants. The focused related suite reports **26 passed**. Both canonical CSV
ledgers parse, the module compiles, and the policy-visible schema contains no
reference/truth/label/oracle field.

## What was established

- SCAN returns 0-N candidates with no forced fallback.
- candidate VERIFY is inaccessible before exposure;
- DirectVerify is an independent region action;
- query is policy-visible and can condition candidate generation;
- materialization uses only returned local relations and participant keys;
- one clock rejects deadline-crossing actions without state mutation;
- identical action/evidence traces have exact evaluator parity;
- DirectVerifyUniform and ScanThenProxyGreedy exist as simple CPU baselines.

## What was not established

No new video inference, GPU/VLM/API call, human audit, physical timing, natural
prevalence measurement, policy training, or tuning on the six consumed T2
workloads was performed. Therefore C-B1 natural headroom, C-B2 observability,
C-B3 deployable policy benefit, and human utility all remain **NOT
ESTABLISHED**.

## Next gate

The only scientifically valid next step is to draft and preregister a fresh-
workload/physical-cost protocol. Executing that protocol requires separate
explicit authorization.
"""
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"decision": manifest["decision"], "tests": completed.stdout.strip()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
