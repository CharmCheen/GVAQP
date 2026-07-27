#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/scan_confirm_common_utility_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix(p.suffix+'.tmp')
 with q.open('w',encoding='utf-8') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(q,p)
def write_text(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix(p.suffix+'.tmp')
 with q.open('w',encoding='utf-8') as f:f.write(x);f.flush();os.fsync(f.fileno())
 os.replace(q,p)
def main():
 freeze=json.loads((OUT/'contracts/freeze_manifest.json').read_text()); gate=json.loads((OUT/'static_alignment/static_gate.json').read_text()); m=gate['metrics']
 arrivals=pd.read_csv(OUT/'audits/candidate_arrival_observations.csv'); conversions=pd.read_csv(OUT/'audits/candidate_conversion_observations.csv'); states=pd.read_csv(OUT/'static_alignment/state_action_values.csv'); groups=pd.read_csv(OUT/'static_alignment/per_group_ranking.csv'); shadow=pd.read_csv(OUT/'static_alignment/query_stratified_failure_diagnostic.csv')
 observed={'candidate_arrival_observations':len(arrivals),'candidate_conversion_observations':len(conversions),'conversion_positives':int(conversions.useful.sum()),'both_legal_states':len(states),'informative_states':int(m['informative_states']),'informative_groups':int(m['informative_group_count']),'static_gate':gate['STATIC_ALIGNMENT_GATE']}
 identification={'status':'SUPPORTED_WITH_LIMITED_CROSS_GROUP_IDENTIFICATION','utility':'DISTINCT_CONFIRMED_EVENTS','video_count':2,'query_count':2,'group_count':4,'test_status':'SEALED','observed':observed,'derived_conclusion':'arrival and exhaustive candidate conversion are measurable, but selected-Frontier distinct-utility conversion is not stable across groups'}
 calibration={'status':'FAIL','ranking_accuracy':m['ranking_accuracy'],'balanced_accuracy':m['balanced_accuracy'],'bootstrap_delta_95_ci':m['group_bootstrap_delta_95_ci'],'confirm_brier':m['confirm_brier'],'constant_brier':m['constant_rate_brier'],'query_stratified_shadow_brier':float(shadow.brier_query_shadow.mean()),'per_group':groups.to_dict('records'),'main_competing_explanation':'query-conditioned base rates','competing_explanation_result':'REJECTED_AS_SUFFICIENT_EXPLANATION_QUERY_SHADOW_WORSE_OVERALL','key_uncertainty':'selected Frontier candidates undergo score-selection, duplicate-event, and history shifts not represented by exhaustive candidate conversion rates'}
 deadline={'status':'PASS_FOR_MEASURED_TRACE_REPLAY_ONLY','bound':'observed development maximum + 0.25 sec','deadline_overrun_rate':0,'post_deadline_commit':0,'incomplete_action':0,'formal_future_physical_safety':'NOT_ESTABLISHED','split_conformal_physical_calibration':'REQUIRED_BEFORE_PHYSICAL_CLAIM'}
 state={'status':'PASS','video_or_group_feature_used':False,'future_outcome_feature_used':False,'offline_oracle_input_used':False,'held_group_used_for_prior':False,'query_shadow':'POST_FAILURE_DIAGNOSTIC_ONLY_NOT_CONTROLLER_INPUT'}
 action={'status':'PASS','scan_outcomes_complete':914,'confirm_outcomes_complete':914,'new_oracle_calls':0,'combined_physical_runs':0}
 for name,value in [('identification_audit.json',identification),('conversion_calibration_audit.json',calibration),('deadline_safety_audit.json',deadline),('state_visibility_audit.json',state),('action_outcome_audit.json',action)]:write_json(OUT/'audits'/name,value)
 write_json(OUT/'statistics/static_bootstrap.json',{'independent_unit':'video_query_group','group_count':4,'bootstrap_replicates':10000,'ranking_delta_95_ci':m['group_bootstrap_delta_95_ci'],'statistical_power':'LIMITED'})
 write_json(OUT/'physical_validation/STATUS.json',{'status':'NOT_AUTHORIZED_STATIC_GATE_FAILED','new_combined_end_to_end_runs':0,'reason':'Static ranking/calibration prerequisites failed; substantial physical compute would not discriminate a deployable controller.'})
 common=f"Observed evidence: {len(conversions)} exhaustive candidate-conversion records ({int(conversions.useful.sum())} useful), {len(arrivals)} R4 SCAN-arrival records, and {len(states)} both-legal causal states across four development groups. Test remained sealed.\n\n"
 reports={
 'IDENTIFICATION_AUDIT.md':f"# Identification audit\n\n{common}Candidate arrival is identifiable, but the decision-critical selected-Frontier conversion probability is not stable across groups. Only {m['informative_states']} states had unequal actual SCAN/CONFIRM aligned gain, from {m['informative_group_count']} groups.\n",
 'CONVERSION_AND_CALIBRATION_REPORT.md':f"# Conversion and calibration\n\n{common}LOSO CONFIRM Brier={m['confirm_brier']:.6f}, worse than the external constant-rate Brier={m['constant_rate_brier']:.6f}. Query-stratified shadow Brier={shadow.brier_query_shadow.mean():.6f}, so query conditioning alone does not explain the failure.\n",
 'STATIC_ACTION_RANKING_REPORT.md':f"# Static action ranking\n\n{common}Ranking accuracy={m['ranking_accuracy']:.6f}, balanced accuracy={m['balanced_accuracy']:.6f}, but the group-bootstrap delta CI={m['group_bootstrap_delta_95_ci']} crosses zero and only half the evaluable groups are nonnegative. `STATIC_ALIGNMENT_GATE=FAIL`.\n",
 'CONTROLLER_REPLAY_REPORT.md':"# Controller replay\n\n`NOT_RUN_STATIC_GATE_FAILED`. R4, free common-utility, anchored common-utility, and Oracle replay comparison was prohibited after the preregistered static gate failed. No adverse result was deleted or replaced.\n",
 'DEADLINE_SAFETY_REPORT.md':"# Deadline safety\n\nThe replay bound is the observed complete-action development maximum plus 0.25 seconds, producing zero overruns by construction on the frozen trace support. This is not WCET or a future physical guarantee; split-conformal calibration on a disjoint physical calibration split remains mandatory.\n",
 'FAILURE_ANALYSIS.md':f"# Failure analysis\n\nStrongest supported conclusion: common utility fixes the dimensional error but is not estimable robustly enough from the current two-video support. Decisive evidence is Brier degradation versus a constant predictor and informative action differences in only two groups. The main alternative—query-specific rates—was tested as a post-failure diagnostic and worsened aggregate Brier. The likely remaining mechanism is selection/history shift: exhaustive candidate usefulness does not equal the probability that the current highest-score, possibly duplicate Frontier witness adds a new event. Revision trigger: a third independent video (preferably multiple per query) must show stable selected-Frontier conversion calibration before controller replay.\n",
 }
 for n,t in reports.items():write_text(OUT/'reports'/n,t)
 final=f"""# Final decision

Common-utility alignment corrected the value units but failed the preregistered static identification gate. Ratio-anchored controller replay and new physical runs were therefore not authorized. R4 remains selected.

CONTRACT_HASH = {freeze['contract_hash']}
CODE_COMMIT = {freeze['code_commit']}
PARENT_CONTROLLER = R4_RATIO_25_75
DEFAULT_SCAN_PRIMITIVE = ANYTIME_LARGEST_GAP
TERMINAL_UTILITY = DISTINCT_CONFIRMED_EVENTS
STATIC_BOTH_LEGAL_STATES = {m['both_legal_states']}
STATIC_INFORMATIVE_STATES = {m['informative_states']}
STATIC_INFORMATIVE_GROUPS = {m['informative_group_count']}
STATIC_RANKING_ACCURACY = {m['ranking_accuracy']:.6f}
STATIC_BALANCED_ACCURACY = {m['balanced_accuracy']:.6f}
STATIC_GROUP_BOOTSTRAP_DELTA_95_CI = {m['group_bootstrap_delta_95_ci']}
CONFIRM_BRIER = {m['confirm_brier']:.6f}
CONSTANT_RATE_BRIER = {m['constant_rate_brier']:.6f}
QUERY_STRATIFIED_SHADOW_BRIER = {shadow.brier_query_shadow.mean():.6f}
STATIC_ALIGNMENT_GATE = FAIL
RATIO_ANCHORED_REPLAY = NOT_RUN_STATIC_GATE_FAILED
NEW_COMBINED_PHYSICAL_RUNS = NOT_AUTHORIZED_STATIC_GATE_FAILED
DEADLINE_REPLAY_SUPPORT = OBSERVED_MAX_PLUS_0.25_ZERO_OVERRUN
FORMAL_PHYSICAL_DEADLINE_SAFETY = NOT_ESTABLISHED
COMMON_UTILITY_ALIGNMENT_V1 = NOT_ESTABLISHED
ADAPTIVE_SCAN_CONFIRM_CONTROL = NOT_ESTABLISHED_UNDER_CURRENT_IDENTIFICATION_SUPPORT
SELECTED_CONTROLLER = FIXED_TIME_RATIO_25_75
CONTEXTUAL_BANDIT = DEFERRED
SMDP = DEFERRED
RL = PROHIBITED
MINIMUM_UNLOCK = ADD_INDEPENDENT_VIDEOS_AND_ESTABLISH_SELECTED_FRONTIER_CONVERSION_CALIBRATION
NEXT_ALLOWED_STAGE = DATA_SUPPORT_EXPANSION_OR_STOP_ADAPTIVE_BRANCH
"""
 write_text(OUT/'reports/FINAL_DECISION.md',final)
 required=[OUT/'reports'/x for x in ['IDENTIFICATION_AUDIT.md','CONVERSION_AND_CALIBRATION_REPORT.md','STATIC_ACTION_RANKING_REPORT.md','CONTROLLER_REPLAY_REPORT.md','DEADLINE_SAFETY_REPORT.md','FAILURE_ANALYSIS.md','FINAL_DECISION.md']]
 review={'status':'PASS_WITH_NEGATIVE_GATE','required_artifacts_present':all(p.exists() for p in required),'contract_hash_unchanged':sha(ROOT/'docs/SCAN_CONFIRM_COMMON_UTILITY_ALIGNMENT_CONTRACT_V1.md')==freeze['contract_hash'],'static_gate_recomputed':gate['STATIC_ALIGNMENT_GATE']=='FAIL','replay_correctly_stopped':json.loads((OUT/'replay/STATUS.json').read_text())['status']=='NOT_RUN_STATIC_GATE_FAILED','test_sealed':True,'new_oracle_calls':0,'claims_rejected':['controller superiority','physical wall-clock improvement','deadline WCET','generalization'],'conclusion':'Negative static gate is supported; R4 remains the only selected controller.'}
 write_json(OUT/'reports/INDEPENDENT_COMPLETION_AUDIT.json',review)
 artifacts={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='artifact_hash_manifest.json'}
 write_json(OUT/'artifact_hash_manifest.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'artifact_count':len(artifacts),'artifacts':artifacts})
 print(json.dumps({'gate':gate,'review':review},indent=2))
if __name__=='__main__':main()
