#!/usr/bin/env python3
"""Build the zero-call amendment contract and exact confidence tables."""

import hashlib,json,math
from pathlib import Path
import pandas as pd

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'DARE_AQP_Experiment_v1').is_dir())
OUT=ROOT/'DARE_AQP_Experiment_v1/outputs/gate_c0_interval_contract_amendment_v1'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

sources=[
'DARE_AQP_Experiment_v1/README.md','DARE_AQP_Experiment_v1/RESEARCH_STATE.md','DARE_AQP_Experiment_v1/docs/ROADMAP_AND_GATES.md',
'DARE_AQP_Experiment_v1/docs/INDEPENDENT_REVIEW.md','DARE_AQP_Experiment_v1/outputs/gate_b/REPORT.md',
'DARE_AQP_Experiment_v1/outputs/gate_a_final/REPORT.md','DARE_AQP_Experiment_v1/config/gate_c0.json',
'DARE_AQP_Experiment_v1/docs/GATE_C0_PROTOCOL.md','DARE_AQP_Experiment_v1/docs/INTERVAL_ORACLE_CONTRACT.md',
'DARE_AQP_Experiment_v1/src/dare_aqp/interval_ceiling.py','DARE_AQP_Experiment_v1/outputs/gate_c0/break_even.csv',
'DARE_AQP_Experiment_v1/outputs/gate_c0/query_traces.csv','DARE_AQP_Experiment_v1/outputs/gate_c0_physical_interval_operator_v1/FINAL_REPORT.md',
'DARE_AQP_Experiment_v1/outputs/gate_c0_physical_interval_operator_v1/audit/C0_CONTRACT_RECOVERY.md']
inputs=['data/realcam/long_video_data/long_video_dataset3.mp4',
'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv',
'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/event_reference.csv']
(OUT/'config').mkdir(parents=True,exist_ok=True); (OUT/'power').mkdir(parents=True,exist_ok=True)
pd.DataFrame([{'path':p,'sha256':sha(ROOT/p)} for p in sources]).to_csv(OUT/'config/SOURCE_MANIFEST.csv',index=False)
pd.DataFrame([{'path':p,'sha256':sha(ROOT/p)} for p in inputs]).to_csv(OUT/'config/INPUT_MANIFEST.csv',index=False)

# Exact one-sided 95% CP lower bound with k=n successes is alpha^(1/n).
bounds=[]
for n in [16,24,32,48,64,80,96,120,148,149,160,299]:
    bounds.append({'independent_trials':n,'observed_failures':0,'one_sided_confidence':.95,
                   'clopper_pearson_lower':.05**(1/n)})
pd.DataFrame(bounds).to_csv(OUT/'power/ACHIEVABLE_CONFIDENCE_BOUNDS.csv',index=False)
requirements=[]
for threshold in [.95,.98,.99,1.0]:
    n=None if threshold==1 else math.ceil(math.log(.05)/math.log(threshold))
    requirements.append({'estimand':'effective_sensitivity','threshold':threshold,'zero_failure_independent_n_required':n if n else 'INFINITE'})
    requirements.append({'estimand':'effective_specificity','threshold':threshold,'zero_failure_independent_n_required':n if n else 'INFINITE'})
pd.DataFrame(requirements).to_csv(OUT/'power/SAMPLE_SIZE_PLAN.csv',index=False)
pd.DataFrame([
 {'component':'COUNT_LOCALIZE primary independent intervals','calls':96,'independent_semantic_intervals':96,'note':'64 positive / 32 empty target'},
 {'component':'ANY-only matched subset','calls':24,'independent_semantic_intervals':0,'note':'same intervals; operator comparison only'},
 {'component':'deterministic repeats','calls':12,'independent_semantic_intervals':0,'note':'stability only'},
 {'component':'matched 10-second timing','calls':16,'independent_semantic_intervals':0,'note':'cost only'},
 {'component':'retry reserve','calls':12,'independent_semantic_intervals':0,'note':'at most one retry; global reserve'},
 {'component':'TOTAL CAP','calls':160,'independent_semantic_intervals':96,'note':'cannot validate threshold 1.00 or 0.99'}]).to_csv(OUT/'power/CALL_BUDGET_PLAN.csv',index=False)

contract={
 'contract_id':'C0_PHYSICAL_INTERVAL_OPERATOR_CONTRACT_v2', 'parent_decision':'INTERVAL_OPERATOR_CONTRACT_BLOCKED',
 'governing_recall_target':.8,'governing_event_f1_target':None,'maximum_dense_cost_ratio':.7,'dense_cost':347,
 'any_states':['POSITIVE','NEGATIVE','UNKNOWN'],
 'pruning_rule':'only high-confidence complete valid non-abstaining NEGATIVE; all else UNKNOWN fallback',
 'minimum_effective_any_sensitivity':1.0,'minimum_effective_any_specificity':.99,
 'maximum_effective_any_false_negatives':0,'maximum_unknown_rate':0.0,
 'per_length_requirements':'same thresholds at every tested length','boundary_requirements':'zero false negatives',
 'confidence_method':'one-sided 95% Clopper-Pearson','count_role':'COUNT_PRIORITY_ONLY',
 'count_not_required_for_go':True,'minimum_count_exact_accuracy':None,'maximum_count_mae':None,
 'maximum_count_undercount_rate':None,'multi_event_undercount_rule':'diagnostic; never prune',
 'count_improvement_requirement':'not gating; report versus ANY-only',
 'abstain_failure_accounting':'charged; denominator retained; UNKNOWN safe fallback',
 'retry_policy':{'per_attempt_max_retries':1,'global_retry_reserve':12,'absolute_physical_call_cap':160},
 'sample_matrix':{'primary':96,'any_subset':24,'repeat_calls':12,'unit_timing':16,'retry_reserve':12,
                  'independent_positive_planned':64,'independent_negative_planned':32},
 'sample_size_feasible':False,
 'infeasibility_reason':'sensitivity 1.00 cannot be validated by a finite binomial sample; 0.99 would require 299 independent positives and specificity 0.99 another 299 negatives',
 'cost_break_even_rule':'total physical-equivalent cost / 347 < 0.7; no unmeasured p50/p95 substitution',
 'later_decisions':['COUNT_GUIDED_INTERVAL_GO','ANY_HIERARCHICAL_GO','INTERVAL_OPERATOR_NO_GO','INTERVAL_OPERATOR_GPU_BLOCKED','INTERVAL_OPERATOR_INCOMPLETE'],
 'decision_precedence':['INTERVAL_OPERATOR_GPU_BLOCKED','INTERVAL_OPERATOR_INCOMPLETE',
                        'INTERVAL_OPERATOR_NO_GO','COUNT_GUIDED_INTERVAL_GO','ANY_HIERARCHICAL_GO'],
 'physical_vlm_calls_observed':0
}
contract['contract_hash_sha256']=canonical(contract)
(OUT/'contract').mkdir(parents=True,exist_ok=True)
(OUT/'contract/C0_PHYSICAL_INTERVAL_OPERATOR_CONTRACT_v2.json').write_text(json.dumps(contract,indent=2)+'\n')
(OUT/'CONTRACT_MANIFEST.json').write_text(json.dumps({'contract_id':contract['contract_id'],'contract_hash_sha256':contract['contract_hash_sha256'],
 'contract_file_sha256':sha(OUT/'contract/C0_PHYSICAL_INTERVAL_OPERATOR_CONTRACT_v2.json'),'physical_vlm_calls':0},indent=2)+'\n')
print(contract['contract_hash_sha256'])
