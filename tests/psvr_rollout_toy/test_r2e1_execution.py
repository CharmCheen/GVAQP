import json
from pathlib import Path

from garc_eval.psvr_rollout_toy.r2e1_execution import METHOD_IDS, append_ledger, derive_raw_results, execute_identity, export_derived_layer, initialize_once, load_ledger, latest_states, precheck, publish_decision_bundle
from garc_eval.psvr_rollout_toy.r2e1_verifier import recompute, verify_attempt


ROOT=Path(__file__).resolve().parents[2]
R2_FREEZE=ROOT/"outputs/psvr_rollout_r2/R2_FREEZE_MANIFEST.json"
PREREG=ROOT/"outputs/psvr_rollout_r2/H_ROLLOUT1A_R2_PREREGISTRATION.json"

def test_e1_clean_precheck_and_fixture_ledger(tmp_path):
    root=tmp_path/"fixture_attempt"
    assert precheck(root,R2_FREEZE,PREREG)["ok"]
    commitment=initialize_once(root,R2_FREEZE,PREREG)
    assert commitment["count"]==512
    assert not precheck(root,R2_FREEZE,PREREG)["ok"]
    rows=load_ledger(root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl")
    assert len(rows)==512*len(METHOD_IDS)
    assert len(latest_states(rows))==len(rows)
    assert {row["state"] for row in rows}=={"PREPARED"}
    assert (root/"CONFIRMATORY_SEED_COMMITMENT.json").is_file()

def test_committed_identity_is_not_overwritten_and_raw_is_derived(tmp_path):
    root=tmp_path/"fixture_attempt"; initialize_once(root,R2_FREEZE,PREREG)
    seed=json.loads((root/"sealed_seed_manifest.json").read_text())["episode_seeds"][0]
    hashes={"fixture":"yes"}
    first=execute_identity(root,0,seed,"B1_SHIELDED_PI0",hashes)
    again=execute_identity(root,0,seed,"B1_SHIELDED_PI0",hashes)
    assert first==again
    rows=derive_raw_results(root)
    assert len(rows)==1 and rows[0]["method_id"]=="B1_SHIELDED_PI0"
    assert export_derived_layer(root)["raw"]==1
    assert export_derived_layer(root)["raw"]==1  # published bundle is immutable and reusable on resume
    assert (root/"CONFIRMATORY_DERIVED_BUNDLE"/"CONFIRMATORY_RAW_RESULTS.csv").is_file()
    trace=next((root/"CONFIRMATORY_RAW_TRACES").glob("*.json"))
    assert recompute(trace)["primary_utility"]==rows[0]["primary_utility"]

def test_independent_verifier_reads_complete_fixture_raw_layer(tmp_path):
    root=tmp_path/"development_fixture"; ledger=root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl"
    for method in METHOD_IDS:
        append_ledger(ledger,{"episode_public_id":"confirmatory-0000","sealed_seed_hash":"fixture","method_id":method,"state":"PREPARED","attempt_ordinal":0,"timestamp":"fixture","raw_trace_path":None,"raw_trace_sha256":None,"failure_class":None,"recovery_status":"NONE"})
    for method in METHOD_IDS:
        execute_identity(root,0,101,method,{"fixture":"development-only"})
    report=verify_attempt(root, allow_fixture=True)
    assert report["status"]=="PASS"
    assert report["derived_outputs_read"] is False
    assert len(report["recomputed_metrics"])==len(METHOD_IDS)

def test_atomic_raw_trace_is_reconciled_without_rerun_after_interruption(tmp_path):
    root=tmp_path/"fixture_attempt"; initialize_once(root,R2_FREEZE,PREREG)
    seed=json.loads((root/"sealed_seed_manifest.json").read_text())["episode_seeds"][0]
    committed=execute_identity(root,0,seed,"B1_SHIELDED_PI0",{"fixture":"yes"})
    append_ledger(root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl",{**committed,"state":"STARTED","raw_trace_path":None,"raw_trace_sha256":None,"recovery_status":"SIMULATED_CRASH_AFTER_TRACE"})
    reconciled=execute_identity(root,0,seed,"B1_SHIELDED_PI0",{"fixture":"yes"},recovery=True)
    assert reconciled["state"]=="RECOVERY_COMMITTED"
    assert reconciled["recovery_status"]=="RECONCILED_ATOMIC_RAW_TRACE"

def test_decision_bundle_is_immutable_and_reused_after_interruption(tmp_path):
    root=tmp_path/"fixture_attempt"
    first=publish_decision_bundle(root,{"status":"PASS"},{"integrity":"PASS"},{"final_branch":"REJECT"})
    second=publish_decision_bundle(root,{"status":"DIFFERENT"},{"integrity":"FAIL"},{"final_branch":"BLOCKED"})
    assert first==second
    assert (root/"CONFIRMATORY_DECISION_BUNDLE"/"CONFIRMATORY_DECISION_BRANCH.json").is_file()
