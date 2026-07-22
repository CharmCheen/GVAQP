#!/usr/bin/env python3
"""Validate H1B implementation-only assets; never creates episodes or seeds."""
from __future__ import annotations
import hashlib, importlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/psvr_rollout_r2b_impl"

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    checks=[]; failures=[]
    base=ROOT/"outputs/psvr_rollout_r2b/H1B_PREREGISTRATION_FREEZE_MANIFEST.json"
    a1=ROOT/"outputs/psvr_rollout_r2b/H1B_EXECUTION_SEMANTICS_A1_FREEZE_MANIFEST.json"
    a2=ROOT/"outputs/psvr_rollout_r2b/H1B_EXECUTION_SEMANTICS_A2_FREEZE_MANIFEST.json"
    a3=ROOT/"outputs/psvr_rollout_r2b/H1B_CHAIN_INTEGRITY_A3.json"
    chain=json.loads(a3.read_text())
    for label,path,key in (("base",base,"base_preregistration_freeze_sha256"),("a1",a1,"a1_freeze_sha256"),("a2",a2,"a2_freeze_sha256")):
        ok=sha(path)==chain[key]; checks.append({"check":f"{label}_binding","pass":ok}); failures.extend([] if ok else [label])
    for module in ("garc_eval.psvr_rollout_h1b", "garc_eval.psvr_rollout_h1b.approximate_rollout", "garc_eval.psvr_rollout_h1b.error_operators"):
        try: importlib.import_module(module); ok=True
        except Exception: ok=False
        checks.append({"check":f"import:{module}","pass":ok}); failures.extend([] if ok else [module])
    forbidden=("run_h1b_development.py","run_h1b_confirmatory.py","generate_h1b_seeds.py")
    present=[name for name in forbidden if (ROOT/"scripts"/name).exists()]
    checks.append({"check":"no_h1b_runner_scripts","pass":not present}); failures.extend(present)
    print(json.dumps({"status":"PASS" if not failures else "FAIL","checks":checks,"violations":failures,"creates_seed_or_episode":False},sort_keys=True))
    raise SystemExit(bool(failures))

if __name__=="__main__": main()
