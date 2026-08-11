#!/usr/bin/env python3
"""Freeze the seven preselected cost-only continuation pairs; no inference."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s'
SRC=RUN/'counterfactual_probe_v1'; OUT=RUN/'counterfactual_continuation_v1'
FOLLOW=(('B_DECISION_009',{'kind':'SCAN','target':26}),('B_DECISION_011',{'kind':'SCAN','target':37}),('B_DECISION_011',{'kind':'VERIFY','target':266}),('B_DECISION_023',{'kind':'SCAN','target':29}),('B_DECISION_025',{'kind':'SCAN','target':34}),('B_DECISION_025',{'kind':'VERIFY','target':159}),('B_DECISION_035',{'kind':'SCAN','target':8}))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def main():
 if OUT.exists() and any(OUT.iterdir()): raise RuntimeError('refusing to overwrite continuation namespace')
 source_plan=json.loads((SRC/'COUNTERFACTUAL_BRANCH_PROBE_PLAN.json').read_text()); by_id={x['state_id']:x for x in source_plan['states']}
 pairs=[]
 for i,(state_id,treatment) in enumerate(FOLLOW,1):
  state=by_id[state_id]
  if treatment not in state['alternatives']: raise RuntimeError(f'not frozen cost-only branch: {state_id} {treatment}')
  pairs.append({'pair_id':f'PAIR_{i:02d}_{state_id}_{treatment["kind"]}_{treatment["target"]}','state_id':state_id,'parent_state_sha256':state['state_snapshot_sha256'],'state_snapshot':state['state_snapshot'],'initial_legal_actions':state['legal_actions'],'control_action':state['parent_b_action'],'treatment_action':treatment})
 contract={'schema_version':'COUNTERFACTUAL_CONTINUATION_PROBE_CONTRACT_V1','protocol_class':'EXPLORATORY_SEQUENTIAL_COST_TO_UTILITY_CONTINUATION','selection_basis':'FOLLOW_UP_OF_PREVIOUSLY_OBSERVED_COST_ONLY_BRANCHES','confirmatory':False,'execution_authorized':False,'source_sha256':'4cef5c884ac879fd00bcc7962707b5f0f5e6dec6ac97e5ec8d247561ce2ec1c6','parent_b_trace_sha256':sha(RUN/'B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.trace.json'),'source_probe_hashes':{'contract':sha(SRC/'COUNTERFACTUAL_BRANCH_PROBE_CONTRACT.json'),'plan':sha(SRC/'COUNTERFACTUAL_BRANCH_PROBE_PLAN.json'),'results':sha(SRC/'COUNTERFACTUAL_BRANCH_PROBE_RESULTS.json')},'oracle':'Qwen3-VL-8B-Instruct BF16','gpu_allocation':[1],'scan':'deterministic OpenCV frame-difference proxy','continuation_policy':'temporal-bisection fixed SCAN1:VERIFY1','max_additional_completed_actions':6,'max_continuation_physical_seconds':60.0,'absolute_deadline_seconds':300.0,'completion_semantics':'logical_start + measured_physical_cost','admission_semantics':'exploratory_start_before_deadline','runtime_convention':'CAUSALLY_EQUIVALENT_LOGICAL_STATE_WITH_NORMALIZED_MODEL_RESIDENT_GPU1_RUNTIME','reference_prohibited_during_runtime':True}
 contract['contract_sha256']=canonical(contract)
 plan={'schema_version':'COUNTERFACTUAL_CONTINUATION_PROBE_PLAN_V1','contract_sha256':contract['contract_sha256'],'pair_count':len(pairs),'maximum_new_scan_actions':98,'maximum_new_verify_calls':98,'pairs':pairs}; plan['plan_sha256']=canonical(plan)
 write(OUT/'CONTINUATION_PROBE_CONTRACT.json',contract);write(OUT/'CONTINUATION_PROBE_PLAN.json',plan)
 (OUT/'CONTINUATION_PROBE_PLAN.md').write_text('# Bounded continuation plan\n\nFrozen before semantic execution: seven paired, fixed-B continuations.\n')
 print(json.dumps({'states':len(pairs),'contract_sha256':contract['contract_sha256'],'plan_sha256':plan['plan_sha256'],'oracle_calls_max':98},indent=2))
if __name__=='__main__': main()
