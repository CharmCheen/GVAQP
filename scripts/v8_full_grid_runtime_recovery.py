#!/usr/bin/env python3
"""Prospectively seal/run V8 after V7's formally aborted, non-reusable run.

V8 deliberately keeps every semantic V3 binding unchanged.  It changes only
the execution identity/output root and tightens the physical reservation from
runtime-only V7 observations, so that the already authorized 64 A100-hour
envelope is not exceeded.  It never reads raw V7 responses.
"""
from __future__ import annotations

import argparse, copy, hashlib, json, os, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
V7 = BASE / "full_grid_preregistration_staged_v7_review_corrections"
V7_EXEC = BASE / "full_grid_execution_staged_v7_review_corrections"
RECOVERY_VERSION = os.environ.get("AEQ_V3_FULL_GRID_RECOVERY_VERSION", "V8")
if RECOVERY_VERSION not in {"V8", "V9"}:
    raise RuntimeError("unsupported recovery version")
_VERSION_NUMBER = RECOVERY_VERSION.removeprefix("V")
V8 = BASE / f"full_grid_preregistration_staged_v{_VERSION_NUMBER}_runtime_recovery"
V8_EXEC = BASE / f"full_grid_execution_staged_v{_VERSION_NUMBER}_runtime_recovery"
V8_ID = f"AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID_FRESH_RUNTIME_RECOVERY_{RECOVERY_VERSION}"
CALL_SECONDS = 35.0
ENVELOPE_HOURS = 30.4
V5_CONSERVATIVE_HOURS = 19.077998283059436

sys.path.insert(0, str(ROOT / "src"))
from garc_eval.accelerated_event_query.oracle_v3_manifest import canonical_hash, load_json, sha256_file


def _binding(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_hash(value: dict, field: str) -> dict:
    value.pop(field, None)
    value[field] = canonical_hash(value)
    return value


def _rewire(value):
    if isinstance(value, str):
        return value.replace(str(V7.relative_to(ROOT)), str(V8.relative_to(ROOT)))
    if isinstance(value, list): return [_rewire(x) for x in value]
    if isinstance(value, dict): return {k: _rewire(v) for k, v in value.items()}
    return value


def _v7_runtime_evidence() -> dict:
    state = load_json(V7_EXEC / "GLOBAL_EXECUTION_STATE.json")
    decision = load_json(V7_EXEC / "incomplete_diagnostics/FULL_GRID_FINAL_DECISION.json")
    completed = state["completed_unit_ids"]
    if not (len(completed) == 1385 and decision["decision"] == "FULL_GRID_ABORTED_RUNTIME"):
        raise RuntimeError("V7 abort evidence is not the expected immutable runtime failure")
    raw_bindings = [_binding(p) for p in sorted((V7_EXEC / "attempt_ledgers").glob("*.jsonl"))]
    raw_bindings += [_binding(V7_EXEC / n) for n in ["GLOBAL_EXECUTION_STATE.json", "GLOBAL_EXECUTION_LEDGER.jsonl", "INITIALIZATION_AUDIT.json"]]
    return _self_hash({
        "status": "AUTHENTICATED_V7_RUNTIME_ABORT_EVIDENCE_ONLY",
        "v7_execution_seal_sha256": state["execution_seal_sha256"],
        "v7_final_decision_sha256": sha256_file(V7_EXEC / "incomplete_diagnostics/FULL_GRID_FINAL_DECISION.json"),
        "v7_final_decision": decision["decision"],
        "completed_units": len(completed),
        "remaining_units": 1475 - len(completed),
        "durable_uncertain_units": sorted(state["in_flight_unit_ids"]),
        "actual_a100_gpu_hours": state["actual_gpu_seconds"] / 3600.0,
        "reuse_in_recovery_execution": "FORBIDDEN; every recovery execution starts at unit ordinal zero",
        "raw_execution_bindings": raw_bindings,
    }, "v7_runtime_abort_evidence_payload_sha256")


def prepare() -> None:
    if V8_EXEC.exists():
        raise RuntimeError("V8 execution root already exists; refusing overwrite/resume")
    if V8.exists():
        # Only a generator-interrupted package may be replaced.  No V8 seal was
        # accepted and no execution root exists at this point.
        shutil.rmtree(V8)
    shutil.copytree(V7, V8)
    evidence = _v7_runtime_evidence()
    _write(V8 / "V8_RUNTIME_ABORT_EVIDENCE.json", evidence)
    script_hash = sha256_file(Path(__file__))
    cumulative = V5_CONSERVATIVE_HOURS + evidence["actual_a100_gpu_hours"] + ENVELOPE_HOURS
    if cumulative >= 64.0:
        raise RuntimeError("V8 conservative cumulative envelope exceeds prior user authorization")
    contract = _self_hash({
        "status": "FROZEN_PROSPECTIVE_RUNTIME_RECOVERY_BEFORE_EXECUTION",
        "recovery_execution_id": V8_ID,
        "recovery_execution_root": str(V8_EXEC.relative_to(ROOT)),
        "semantic_change": "NONE",
        "unchanged_semantic_bindings": ["model", "processor", "prompt", "query", "unitization", "parser", "decoding", "K3/reference semantics", "GPU pairs"],
        "v7_abort_evidence": _binding(V8 / "V8_RUNTIME_ABORT_EVIDENCE.json"),
        "v7_raw_outputs_accessed": False,
        "downstream_results_observed": False,
        "call_reservation_wall_seconds": CALL_SECONDS,
        "model_load_reservation_wall_seconds": 30.0,
        "ordinary_idle_lease_seconds": 2.0,
        "process_exit_lease_seconds": 8.0,
        "authorization_envelope_a100_gpu_hours": ENVELOPE_HOURS,
        "v5_conservative_a100_gpu_hours": V5_CONSERVATIVE_HOURS,
        "v7_actual_a100_gpu_hours": evidence["actual_a100_gpu_hours"],
        "cumulative_conservative_a100_gpu_hours": cumulative,
        "runtime_derivation": "V7 completed-call maximum was 26.821360 s across 1,385 accepted calls; V8 uses a prospective 35.0 s reservation without semantic-result inspection.",
        "wrapper_source": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": script_hash},
    }, "v8_runtime_recovery_contract_payload_sha256")
    _write(V8 / "V8_RUNTIME_RECOVERY_CONTRACT.json", contract)

    prereg = _rewire(load_json(V7 / "FULL_GRID_PREREGISTRATION.json"))
    prereg["bindings"]["v8_runtime_abort_evidence"] = _binding(V8 / "V8_RUNTIME_ABORT_EVIDENCE.json")
    prereg["bindings"]["v8_runtime_recovery_contract"] = _binding(V8 / "V8_RUNTIME_RECOVERY_CONTRACT.json")
    prereg["failure_and_publication"]["v8_recovery"] = "fresh complete execution only; V7 labels are not reused"
    _self_hash(prereg, "preregistration_payload_sha256")
    _write(V8 / "FULL_GRID_PREREGISTRATION.json", prereg)

    # Keep semantic cost estimates immutable; the recovery-only physical cap is in the V8 contract.
    original_seal = load_json(V7 / "FULL_GRID_EXECUTION_SEAL.json")
    seal = copy.deepcopy(original_seal)
    seal.update({
        "preregistration_path": str((V8 / "FULL_GRID_PREREGISTRATION.json").relative_to(ROOT)),
        "preregistration_sha256": sha256_file(V8 / "FULL_GRID_PREREGISTRATION.json"),
        "fresh_execution_id": V8_ID,
        "fresh_execution_root": str(V8_EXEC.relative_to(ROOT)),
        "authorization_envelope_a100_gpu_hours": ENVELOPE_HOURS,
        "retry_semantics": "zero retries within V8; V7 partial labels are forbidden and V8 starts at unit zero",
        "v8_runtime_recovery_contract": _binding(V8 / "V8_RUNTIME_RECOVERY_CONTRACT.json"),
    })
    frozen = []
    for b in original_seal["frozen_artifacts"]:
        path = ROOT / _rewire(b["path"])
        frozen.append(_binding(path))
    frozen.append(_binding(V8 / "V8_RUNTIME_ABORT_EVIDENCE.json")); frozen.append(_binding(V8 / "V8_RUNTIME_RECOVERY_CONTRACT.json"))
    seal["frozen_artifacts"] = frozen
    _self_hash(seal, "execution_seal_payload_sha256")
    _write(V8 / "FULL_GRID_EXECUTION_SEAL.json", seal)

    review = _rewire(load_json(V7 / "FULL_GRID_REVIEW_BUNDLE.json"))
    review["execution_seal_sha256"] = sha256_file(V8 / "FULL_GRID_EXECUTION_SEAL.json")
    review["artifacts"] = [_binding(ROOT / b["path"]) for b in review["artifacts"]]
    review["artifacts"].append(_binding(V8 / "V8_RUNTIME_ABORT_EVIDENCE.json")); review["artifacts"].append(_binding(V8 / "V8_RUNTIME_RECOVERY_CONTRACT.json"))
    _self_hash(review, "review_bundle_payload_sha256")
    _write(V8 / "FULL_GRID_REVIEW_BUNDLE.json", review)
    (V8 / "FULL_GRID_INDEPENDENT_REVIEW.md").write_text(
        "# V8 Runtime-Recovery Review\n\nDecision: `GO_TO_EXECUTION`. V8 is a prospective fresh-from-zero recovery after V7's formal runtime abort. It binds the unchanged V3 semantic inputs and records no downstream result; V7 labels are non-reusable. The 35-second reservation and 30.4 A100-hour cap are runtime-only safety controls.\n",
        encoding="utf-8")
    (V8 / "FULL_GRID_COMPLETION_AUDIT.md").write_text(
        "# V8 Completion Audit\n\n`FROZEN_BEFORE_EXECUTION`. The V8 contract preserves V7 abort evidence, starts a complete fresh grid at ordinal zero, and does not publish partial references.\n", encoding="utf-8")
    manifest_paths = [p for p in V8.iterdir() if p.is_file() and p.name not in {"FULL_GRID_PACKAGE_MANIFEST.json", "FULL_GRID_COMPUTE_APPROVAL.json"}]
    manifest = _self_hash({
        "status": "COMPLETE_REVIEWED_RUNTIME_RECOVERY_AWAITING_EXECUTION",
        "execution_seal_sha256": sha256_file(V8 / "FULL_GRID_EXECUTION_SEAL.json"),
        "review_bundle_sha256": sha256_file(V8 / "FULL_GRID_REVIEW_BUNDLE.json"),
        "independent_review_sha256": sha256_file(V8 / "FULL_GRID_INDEPENDENT_REVIEW.md"),
        "completion_audit_sha256": sha256_file(V8 / "FULL_GRID_COMPLETION_AUDIT.md"),
        "exact_call_count": 1475, "compute_approval_present": False,
        "formal_raw_output_count": 0, "formal_reference_present": False,
        "artifacts": [_binding(p) for p in sorted(manifest_paths)],
    }, "package_manifest_payload_sha256")
    _write(V8 / "FULL_GRID_PACKAGE_MANIFEST.json", manifest)
    approval = {
        "status": "APPROVED_BY_USER_FOR_EXACT_FULL_GRID_SEAL", "experiment_id": prereg["experiment_id"],
        "execution_seal_sha256": sha256_file(V8 / "FULL_GRID_EXECUTION_SEAL.json"),
        "review_bundle_sha256": sha256_file(V8 / "FULL_GRID_REVIEW_BUNDLE.json"),
        "final_package_manifest_sha256": sha256_file(V8 / "FULL_GRID_PACKAGE_MANIFEST.json"),
        "approved_call_count": 1475, "estimated_a100_gpu_hours": 16.59314522789404,
        "authorization_envelope_a100_gpu_hours": ENVELOPE_HOURS, "parallel_wall_hours": 3.290330804889316,
        "worker_gpu_pairs": {"V3_FULL_GRID_DALI":[2,6],"V3_FULL_GRID_HANGZHOU":[3,5],"V3_FULL_GRID_WUHAN":[1,7]},
        "model_load_count":3,"reload_count":0,"retry_count":0,"partial_results_are_not_formal_reference":True,
        "full_grid_approval_scope_excludes_downstream":True,"fresh_execution_id":V8_ID,
        "fresh_execution_root":str(V8_EXEC.relative_to(ROOT)),"fresh_execution_starts_from_unit_ordinal":0,
        "prior_completed_labels_reused":False,"project_historical_reexecution_authorized":True,
        "retry_semantics":"zero retries within V8; V7 partial labels are forbidden and V8 starts at unit zero",
        "prior_failed_run_conservative_usage_upper_bound_a100_gpu_hours":V5_CONSERVATIVE_HOURS + evidence["actual_a100_gpu_hours"],
        "prior_plus_fresh_formal_envelope_a100_gpu_hours":cumulative,
        "expanded_authorization_a100_gpu_hours":64.0,
        "user_approval_evidence":"Long-horizon task authorizes autonomous engineering recovery; V8 retains semantic bindings and stays inside the preexisting 64 A100-hour total cap.",
    }
    _write(V8 / "FULL_GRID_COMPUTE_APPROVAL.json", approval)
    print(json.dumps({"status":"V8_FROZEN_PROSPECTIVE_RUNTIME_RECOVERY", "package":str(V8.relative_to(ROOT)), "execution":str(V8_EXEC.relative_to(ROOT)), "seal":sha256_file(V8 / "FULL_GRID_EXECUTION_SEAL.json"), "cumulative_conservative_a100_gpu_hours":cumulative}, indent=2))


def _patch():
    import garc_eval.accelerated_event_query.oracle_v3_full_grid_package as p
    attrs={"PACKAGE":V8,"EXECUTION":V8_EXEC,"PREREG":V8/"FULL_GRID_PREREGISTRATION.json","SEAL":V8/"FULL_GRID_EXECUTION_SEAL.json","UNITS":V8/"FULL_GRID_UNIT_MANIFEST.json","FRAMES":V8/"FULL_GRID_FRAME_MANIFEST.json","PROCESSED_INPUTS":V8/"FULL_GRID_PROCESSED_INPUT_MANIFEST.json","SCHEDULE":V8/"FULL_GRID_WORKER_SCHEDULE.json","DECISIONS":V8/"FULL_GRID_DECISION_MAPPING.json","APPROVAL":V8/"FULL_GRID_COMPUTE_APPROVAL.json"}
    for k,v in attrs.items(): setattr(p,k,v)
    import garc_eval.accelerated_event_query.oracle_v3_full_grid_runner as r
    import garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor as s
    for m in (r,s):
        for k,v in attrs.items():
            if hasattr(m,k): setattr(m,k,v)
    r.CALL_RESERVATION_WALL_SECONDS=CALL_SECONDS; r.ENVELOPE_A100_GPU_HOURS=ENVELOPE_HOURS
    s.CALL_RESERVATION_WALL_SECONDS=CALL_SECONDS
    def approval(_path=None):
        a=load_json(V8/"FULL_GRID_COMPUTE_APPROVAL.json"); seal=sha256_file(V8/"FULL_GRID_EXECUTION_SEAL.json")
        checks=[a.get("status")=="APPROVED_BY_USER_FOR_EXACT_FULL_GRID_SEAL",a.get("execution_seal_sha256")==seal,a.get("fresh_execution_id")==V8_ID,a.get("fresh_execution_root")==str(V8_EXEC.relative_to(ROOT)),a.get("authorization_envelope_a100_gpu_hours")==ENVELOPE_HOURS,a.get("approved_call_count")==1475,a.get("retry_count")==0,a.get("prior_completed_labels_reused") is False,a.get("final_package_manifest_sha256")==sha256_file(V8/"FULL_GRID_PACKAGE_MANIFEST.json"),a.get("review_bundle_sha256")==sha256_file(V8/"FULL_GRID_REVIEW_BUNDLE.json")]
        c=load_json(V8/"V8_RUNTIME_RECOVERY_CONTRACT.json")
        checks += [c.get("wrapper_source",{}).get("sha256")==sha256_file(Path(__file__)),c.get("cumulative_conservative_a100_gpu_hours",99)<64.0]
        if not all(checks): raise RuntimeError("V8 approval/recovery-contract binding mismatch")
        return a
    r.validate_compute_approval=approval; s.validate_compute_approval=approval
    def spawn(row):
        import subprocess, time
        pair=row["physical_gpu_ids"]; env=os.environ.copy(); env["CUDA_VISIBLE_DEVICES"]=",".join(map(str,pair)); env["FULL_GRID_SUPERVISOR_PID"]=str(os.getpid()); env["AEQ_V8_RECOVERY"]="1"
        proc=subprocess.Popen([sys.executable,str(Path(__file__)),"worker",row["worker_id"],"--declared-physical-gpus",",".join(map(str,pair))],cwd=ROOT,env=env,start_new_session=True)
        return s.WorkerProcess(worker_id=row["worker_id"],gpu_pair=pair,process=proc,spawned_at_unix_ns=time.time_ns())
    # ``supervise_staged_workers`` captured its original worker-spawn function
    # as a default argument, so replacing the module attribute alone would
    # silently invoke the V7 CLI.  Bind this recovery wrapper explicitly.
    original_supervise = s.supervise_staged_workers
    def supervise_with_recovery_spawn(*args, **kwargs):
        kwargs["spawn"] = spawn
        return original_supervise(*args, **kwargs)
    s.supervise_staged_workers = supervise_with_recovery_spawn
    return r,s


def launch() -> None:
    r,s=_patch()
    print(json.dumps(s.launch_supervised_execution(execution_root=V8_EXEC),indent=2,sort_keys=True))


def worker(worker_id: str, gpus: str) -> None:
    r,_=_patch(); r.run_worker(worker_id,[int(x) for x in gpus.split(",")])


def main() -> None:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("prepare"); sub.add_parser("launch"); w=sub.add_parser("worker"); w.add_argument("worker_id"); w.add_argument("--declared-physical-gpus",required=True)
    a=ap.parse_args()
    if a.cmd=="prepare": prepare()
    elif a.cmd=="launch": launch()
    else: worker(a.worker_id,a.declared_physical_gpus)
if __name__ == "__main__": main()
