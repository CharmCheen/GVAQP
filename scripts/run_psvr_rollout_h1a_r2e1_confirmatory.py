#!/usr/bin/env python3
"""E1 one-shot coordinator; seed generation occurs only under explicit flag."""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
from garc_eval.psvr_rollout_toy.r2e1_execution import METHOD_IDS, atomic_json, completion_eligible, execute_identity, export_derived_layer, initialize_once, latest_states, load_ledger, publish_decision_bundle, sha
from garc_eval.psvr_rollout_toy.r2e1_gate import emit_frozen_decision_branch, evaluate_frozen_gate
from garc_eval.psvr_rollout_toy.r2e1_verifier import verify_attempt
from garc_eval.psvr_rollout_toy.r2_splits import LEGACY_HELDOUT, LEGACY_HELDOUT_SHA256

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/psvr_rollout_r2e1"

def parser():
    p=argparse.ArgumentParser(description="H-ROLLOUT1A-R2 E1 recoverable one-shot coordinator")
    p.add_argument("--preregistration",type=Path,default=ROOT/"outputs/psvr_rollout_r2/H_ROLLOUT1A_R2_PREREGISTRATION.json")
    p.add_argument("--freeze-manifest",type=Path,default=OUT/"E1_FREEZE_MANIFEST.json")
    p.add_argument("--output-root",type=Path,default=OUT/"confirmatory_attempt")
    p.add_argument("--generate-and-run-confirmatory",action="store_true")
    p.add_argument("--resume",action="store_true")
    return p

def verify_e1_freeze(path: Path) -> dict:
    manifest=json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_E1_EXECUTION_PROTOCOL":
        raise RuntimeError("E1 freeze manifest is not final")
    bad=[]
    for row in manifest["files"]:
        candidate=ROOT/row["file"]
        observed=hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else None
        if observed != row["sha256"]: bad.append(row["file"])
    if bad: raise RuntimeError(f"E1 freeze hash mismatch: {bad}")
    return manifest

def main():
    a=parser().parse_args()
    r2_freeze=ROOT/"outputs/psvr_rollout_r2/R2_FREEZE_MANIFEST.json"
    canonical_prereg=ROOT/"outputs/psvr_rollout_r2/H_ROLLOUT1A_R2_PREREGISTRATION.json"
    canonical_root=OUT/"confirmatory_attempt"
    if not a.generate_and_run_confirmatory and not a.resume:
        raise SystemExit("refusing confirmatory state creation without --generate-and-run-confirmatory")
    if a.preregistration.resolve()!=canonical_prereg.resolve():
        raise SystemExit("only the E1-bound canonical R2 preregistration is accepted")
    if a.output_root.resolve()!=canonical_root.resolve():
        raise SystemExit("only the E1-bound canonical confirmatory attempt root is accepted")
    e1_freeze=verify_e1_freeze(a.freeze_manifest)
    r2=json.loads(r2_freeze.read_text(encoding="utf-8"))
    if r2.get("status")!="FROZEN_R2_PRE_CONFIRMATORY": raise SystemExit("R2 freeze is not execution-authorized")
    r2_bad=[]
    for row in r2["files"]:
        path=ROOT/row["file"]
        if not path.is_file() or sha(path)!=row["sha256"]: r2_bad.append(row["file"])
    if r2_bad: raise SystemExit(f"R2 freeze hash mismatch: {r2_bad}")
    if LEGACY_HELDOUT.exists() and sha(LEGACY_HELDOUT)!=LEGACY_HELDOUT_SHA256:
        raise SystemExit("legacy contaminated universe hash unexpectedly changed")
    bound_prereg=next((row for row in r2["files"] if row["file"]==str(canonical_prereg.relative_to(ROOT))),None)
    if bound_prereg is None or sha(canonical_prereg)!=bound_prereg["sha256"]: raise SystemExit("canonical preregistration is not R2 freeze-bound")
    if a.resume:
        if not a.output_root.exists(): raise SystemExit("cannot resume a nonexistent attempt root")
        if (a.output_root/"CONFIRMATORY_COMPLETION_MARKER.json").exists():
            raise SystemExit("completed attempt is immutable and cannot be resumed")
    else:
        initialize_once(a.output_root,r2_freeze,a.preregistration)
    sealed=json.loads((a.output_root/"sealed_seed_manifest.json").read_text())
    hashes={"r2_freeze":sha(r2_freeze),"preregistration":sha(a.preregistration),"e1_freeze":sha(a.freeze_manifest),"e1_protocol_amendment":sha(OUT/"E1_PROTOCOL_AMENDMENT.json")}
    latest=latest_states(load_ledger(a.output_root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl"))
    for index,seed in enumerate(sealed["episode_seeds"]):
        for method in METHOD_IDS:
            row=latest[(f"confirmatory-{index:04d}",method)]
            if row["state"] in {"COMMITTED","RECOVERY_COMMITTED","FAILED_DETERMINISTIC"}: continue
            execute_identity(a.output_root,index,seed,method,hashes,recovery=a.resume)
    export_derived_layer(a.output_root)
    verifier=verify_attempt(a.output_root)
    gate=evaluate_frozen_gate(verifier["recomputed_metrics"]) if verifier["status"]=="PASS" else {"integrity":"FAIL","reason":"independent raw verifier failed"}
    decision=emit_frozen_decision_branch(gate)
    published=publish_decision_bundle(a.output_root,verifier,gate,decision)
    verifier=published["CONFIRMATORY_INDEPENDENT_VERIFICATION.json"]
    decision=published["CONFIRMATORY_DECISION_BRANCH.json"]
    if verifier["status"] != "PASS":
        raise SystemExit("E1_EXECUTION_COMPLETE_BUT_INDEPENDENT_VERIFIER_FAILED")
    if not completion_eligible(a.output_root):
        raise SystemExit("E1_EXECUTION_INCOMPLETE_LEDGER_NOT_TERMINAL")
    atomic_json(a.output_root/"CONFIRMATORY_COMPLETION_MARKER.json",{"status":"COMPLETE_INDEPENDENTLY_VERIFIED","r2_freeze_sha256":sha(r2_freeze),"e1_freeze_sha256":sha(a.freeze_manifest),"preregistration_sha256":sha(a.preregistration),"independent_verification_sha256":sha(a.output_root/"CONFIRMATORY_DECISION_BUNDLE/CONFIRMATORY_INDEPENDENT_VERIFICATION.json"),"decision_sha256":sha(a.output_root/"CONFIRMATORY_DECISION_BUNDLE/CONFIRMATORY_DECISION_BRANCH.json")})
    print("E1_EXECUTION_COMPLETE_INDEPENDENTLY_VERIFIED")
if __name__=="__main__": main()
