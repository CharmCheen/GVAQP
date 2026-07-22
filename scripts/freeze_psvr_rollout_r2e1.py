#!/usr/bin/env python3
"""Freeze only the R2-E1 execution protocol; never starts confirmatory execution."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/psvr_rollout_r2e1"

FILES=(
    "docs/psvr_rollout_r2e1/00_E1_AUTHORITY_AND_SCOPE.md",
    "docs/psvr_rollout_r2e1/01_CONFIRMATORY_ARTIFACT_CONTRACT.md",
    "docs/psvr_rollout_r2e1/02_ATTEMPT_LEDGER_AND_RESUME_PROTOCOL.md",
    "docs/psvr_rollout_r2e1/03_INDEPENDENT_VERIFICATION_PROTOCOL.md",
    "docs/psvr_rollout_r2e1/04_GATE_AND_DECISION_PROTOCOL.md",
    "docs/psvr_rollout_r2e1/05_E1_EXECUTION_PROTOCOL.md",
    "docs/psvr_rollout_r2e1/06_E1_DESIGN_DECISION_LEDGER.md",
    "src/garc_eval/psvr_rollout_toy/r2e1_execution.py",
    "src/garc_eval/psvr_rollout_toy/r2e1_verifier.py",
    "src/garc_eval/psvr_rollout_toy/r2e1_gate.py",
    "scripts/run_psvr_rollout_h1a_r2e1_confirmatory.py",
    "scripts/verify_psvr_rollout_h1a_r2_confirmatory.py",
    "scripts/run_psvr_rollout_r2e1_development_validation.py",
    "scripts/freeze_psvr_rollout_r2e1.py",
    "tests/psvr_rollout_toy/test_r2e1_execution.py",
    "outputs/psvr_rollout_r2e1/E1_PROTOCOL_AMENDMENT.json",
    "outputs/psvr_rollout_r2e1/E1_SCIENTIFIC_SPEC_DIFF_AUDIT.json",
    "outputs/psvr_rollout_r2e1/E1_ARTIFACT_SCHEMA_REGISTRY.json",
    "outputs/psvr_rollout_r2e1/E1_ATTEMPT_LEDGER_SCHEMA.json",
    "outputs/psvr_rollout_r2e1/E1_VERIFIER_SPEC.json",
    "outputs/psvr_rollout_r2e1/E1_GATE_DECISION_SPEC.json",
    "outputs/psvr_rollout_r2e1/E1_DEVELOPMENT_VALIDATION_AUDIT.json",
)

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path: Path, value: dict) -> None:
    temporary=path.with_name(path.name+".tmp")
    temporary.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    temporary.replace(path)

def main() -> None:
    audit=json.loads((OUT/"E1_DEVELOPMENT_VALIDATION_AUDIT.json").read_text())
    if audit.get("status")!="PASS" or (OUT/"confirmatory_attempt").exists():
        raise SystemExit("refusing freeze: validation failed or confirmatory attempt root exists")
    absent=[name for name in FILES if not (ROOT/name).is_file()]
    if absent: raise SystemExit(f"missing E1 freeze inputs: {absent}")
    manifest={"status":"FROZEN_E1_EXECUTION_PROTOCOL","scope":"execution protocol only; scientific R2 core inherited unchanged","confirmatory_attempt_root_created":False,"files":[{"file":name,"sha256":sha(ROOT/name)} for name in FILES],"r2_freeze_sha256":sha(ROOT/"outputs/psvr_rollout_r2/R2_FREEZE_MANIFEST.json"),"r2_preregistration_sha256":sha(ROOT/"outputs/psvr_rollout_r2/H_ROLLOUT1A_R2_PREREGISTRATION.json"),"created_at":datetime.now(timezone.utc).isoformat()}
    write(OUT/"E1_CODE_MANIFEST.json",manifest)
    write(OUT/"E1_FREEZE_MANIFEST.json",manifest)
    print("E1_FREEZE_COMPLETE_NO_CONFIRMATORY_STATE_CREATED")

if __name__=="__main__": main()
