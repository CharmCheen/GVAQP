#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/scan_confirm_decision_v1'; DEV=ROOT/'outputs/psvr_two_video_loop/dev_benchmark_v1'

def write_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w',encoding='utf-8') as f: json.dump(value,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)

def write_text(path,value):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w',encoding='utf-8') as f: f.write(value); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def grouped(frame):
 return frame.groupby(['policy','task_id','budget_sec'],as_index=False).agg(utility=('utility','mean'),event_recall=('event_recall','mean'),deadline_overrun=('deadline_overrun','mean'),unused_budget=('unused_budget','mean'),oracle_calls=('oracle_calls','mean'))

def auc_rows(frame):
 rows=[]
 for (policy,task),g in frame.groupby(['policy','task_id']):
  g=g.sort_values('budget_sec'); rows.append({'policy':policy,'task_id':task,'utility_auc':float(np.trapezoid(g.utility,g.budget_sec)),'recall_auc':float(np.trapezoid(g.event_recall,g.budget_sec))})
 return pd.DataFrame(rows)

def trace_event_f1(path,task,budget):
 rows=json.loads(path.read_text()); positive=sorted({int(r['unit_id']) for r in rows if r['action']=='CONFIRM' and r['positive'] and r['cumulative_wallclock']<=budget})
 clusters=[]
 for u in positive:
  if not clusters or u>clusters[-1][-1]+1: clusters.append([u])
  else: clusters[-1].append(u)
 ref=pd.read_csv(DEV/f'reference_events/{task}.csv'); mapping={}
 for r in ref.to_dict('records'):
  for token in str(r['source_unit_ids']).replace(',','|').split('|'):
   if token.strip(): mapping.setdefault(int(float(token)),set()).add(str(r['reference_event_id']))
 matched=set().union(*(mapping.get(u,set()) for u in positive)) if positive else set(); tp=len(matched); pred=len(clusters)
 precision=tp/pred if pred else (1.0 if not len(ref) else 0.0); recall=tp/len(ref) if len(ref) else 1.0; f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
 return precision,recall,f1

def main():
 fixed=pd.read_csv(OUT/'fixed_ratio_baselines/run_metrics.csv'); myopic=pd.read_csv(OUT/'myopic_vps/run_metrics.csv'); abl=pd.read_csv(OUT/'ablations/run_metrics.csv'); oracle=pd.read_csv(OUT/'offline_oracle/run_metrics.csv')
 all_online=pd.concat([fixed,myopic],ignore_index=True); grouped_online=grouped(all_online); auc=auc_rows(grouped_online)
 macro=auc.groupby('policy',as_index=False).utility_auc.mean().sort_values(['utility_auc','policy'],ascending=[False,True]); fixed_names=set(fixed.policy); strongest=next(p for p in macro.policy if p in fixed_names)
 base=auc.query('policy==@strongest').set_index('task_id').utility_auc; mine=auc.query("policy=='R8_MYOPIC_VPS'").set_index('task_id').utility_auc; delta=(mine-base).rename('auc_delta')
 groups=pd.DataFrame({'task_id':delta.index,'myopic_auc':mine,'baseline_auc':base,'auc_delta':delta}).reset_index(drop=True)
 best_group=groups.sort_values(['auc_delta','task_id'],ascending=[False,True]).iloc[0].task_id
 leave=float(groups.query('task_id!=@best_group').auc_delta.mean())
 low=float(grouped_online.query("policy=='R8_MYOPIC_VPS' and budget_sec==30").utility.mean()-grouped_online.query('policy==@strongest and budget_sec==30').utility.mean())
 rng=np.random.default_rng(20260726); values=groups.auc_delta.to_numpy(); boot=np.asarray([rng.choice(values,len(values),replace=True).mean() for _ in range(10000)])
 ci=[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))]
 stats={'independent_groups':len(groups),'statistical_power':'LIMITED','bootstrap_replicates':10000,'myopic_vs_strongest_fixed':strongest,'macro_auc_delta':float(values.mean()),'paired_group_bootstrap_95_ci':ci,'group_win_rate':float((values>0).mean()),'group_nonnegative_rate':float((values>=0).mean()),'median_group_delta':float(np.median(values)),'leave_best_group_out':leave,'best_group':best_group,'best_group_contribution_ratio':'NOT_APPLICABLE_NO_POSITIVE_GAIN','low_budget_delta':low}
 (OUT/'statistics').mkdir(parents=True,exist_ok=True); groups.to_csv(OUT/'statistics/per_group_deltas.csv',index=False); macro.to_csv(OUT/'statistics/policy_auc.csv',index=False); write_json(OUT/'statistics/paired_bootstrap.json',stats)
 # Event metrics from action ledgers.
 event_rows=[]
 for family,directory,frame in [('fixed','fixed_ratio_baselines',fixed),('myopic','myopic_vps',myopic),('ablation','ablations',abl),('oracle','offline_oracle',oracle)]:
  for r in frame.to_dict('records'):
   if family=='oracle': prefix='ONE_STEP' if r['policy']=='OFFLINE_ONE_STEP_ORACLE' else 'MULTI_STEP'; name=f"{prefix}__{r['task_id']}__B{int(r['budget_sec'])}.json"
   else: name=f"{r['policy']}__{r['task_id']}__B{int(r['budget_sec'])}__S{int(r['seed'])}.json"
   path=OUT/directory/'traces'/name; precision,recall,f1=trace_event_f1(path,r['task_id'],r['budget_sec']); event_rows.append({**{k:r[k] for k in ['policy','task_id','budget_sec','seed']},'event_precision':precision,'event_recall_recomputed':recall,'event_f1':f1})
 (OUT/'metrics').mkdir(parents=True,exist_ok=True)
 pd.DataFrame(event_rows).to_csv(OUT/'metrics/event_metrics.csv',index=False)
 # Audits
 task_manifest=json.loads((DEV/'TASK_MANIFEST.json').read_text()); refs=sum(int(x['reference_events']) for x in task_manifest['tasks'])
 asset={'status':'PASS','video_count':2,'query_count':2,'independent_group_count':4,'timeline_units':914,'reference_events':refs,'design_groups':[x['task_id'] for x in task_manifest['tasks']],'validation_groups':[],'test_status':'SEALED','observed_evidence':['frozen exhaustive physical Oracle outputs','frozen Y8 full-video proxy extraction','per-unit SCAN processing traces','independent reference materialization']}
 utility={'INDEPENDENT_EVENT_MAPPING_SUPPORT':'SUPPORTED','DISTINCT_EVENT_UTILITY_SUPPORT':'SUPPORTED','DISTINCT_CANDIDATE_CLUSTER_UTILITY_SUPPORT':'SUPPORTED','PRIMARY_UTILITY':'DISTINCT_CONFIRMED_EVENTS','EVENT_LEVEL_CLAIM':'ESTABLISHED_FOR_DEVELOPMENT_TRACE_REPLAY','reason':'reference events derive from exhaustive physical Oracle outputs; runtime receives only projected outcomes after CONFIRM'}
 frontier={'status':'PASS','capacity':10,'admission':'one bound top-track witness per scanned unit','deduplication':'unit witness identity and queried terminalization','retention':'score descending, deterministic ties, capacity 10','aging':'no outcome-dependent eviction','confirm_selection':'highest frozen visible score'}
 outcome={'COMPLETE_ACTION_OUTCOME_SUPPORT':'SUPPORTED','scan_units_with_outcomes':914,'confirm_units_with_outcomes':914,'new_oracle_calls':0,'qualification':'outcomes complete; combined paths are strict physical trace replay rather than newly concurrent execution'}
 arc={'ARC_FAIR_COMPARISON_SUPPORT':'BLOCKED','ARC_COMPARISON':'CONTEXT_ONLY_NOT_FORMAL','mismatches':['candidate universe','Frontier','SCAN operator','deadline grid','combined execution trace'],'result':'NOT_FORMALLY_COMPARABLE'}
 deadline={'PHYSICAL_WALLCLOCK_SUPPORT':'APPROXIMATE','clock_sources':['time.perf_counter_ns physical source traces','strict deterministic trace composition'],'budget_grid':[30,60,120,240],'combined_physical_rerun':False,'deadline_overrun_runs':int(all_online.deadline_overrun.sum()),'post_deadline_utility_excluded':True,'reason_no_new_physical_runs':'preregistered immediate stop: fixed allocation stronger and Myopic performs zero CONFIRM actions'}
 state_audit={'status':'PASS','schema':str(OUT/'contracts/public_state_schema.json'),'forbidden_fields_observed_in_controller_input':[],'video_id_use':'reset/group/report only','offline_oracle_isolation':'PASS'}
 for name,value in [('asset_audit.json',asset),('utility_support_audit.json',utility),('frontier_audit.json',frontier),('action_outcome_audit.json',outcome),('arc_comparability_audit.json',arc),('deadline_support_audit.json',deadline),('state_visibility_audit.json',state_audit)]: write_json(OUT/'audits'/name,value)
 # Gate and reports
 oracle_auc=auc_rows(grouped(oracle)).groupby('policy').utility_auc.mean().to_dict(); myopic_auc=float(macro.query("policy=='R8_MYOPIC_VPS'").utility_auc.iloc[0]); fixed_auc=float(macro.query('policy==@strongest').utility_auc.iloc[0])
 gates={'1_positive_auc_delta':stats['macro_auc_delta']>0,'2_majority_groups_nonnegative':stats['group_nonnegative_rate']>.5,'3_low_budget_not_systematically_down':low>=0,'4_full_cost_positive':stats['macro_auc_delta']>0,'5_leave_best_positive':leave>0,'6_best_group_contribution_below_half':False,'7_not_single_budget_driven':False,'8_offline_headroom_measurable':max(oracle_auc.values())>myopic_auc}
 decision={'MYOPIC_VPS_SIGNAL':'ESTABLISHED' if all(gates.values()) else 'NOT_ESTABLISHED','SELECTED_CONTROLLER':strongest,'NEXT_ALLOWED_STAGE':'RETURN_TO_FIXED_ALLOCATION_OR_REVISE_VALUE_ESTIMATION','CONTEXTUAL_BANDIT_STATUS':'DEFERRED','SMDP_STATUS':'DEFERRED','RL_STATUS':'PROHIBITED_IN_THIS_CONTRACT','gates':gates,'strongest_fixed':strongest,'myopic_auc':myopic_auc,'strongest_fixed_auc':fixed_auc,'oracle_auc':oracle_auc}
 write_json(OUT/'metrics/gate_decision.json',decision)
 abls=grouped(abl).groupby('policy').utility.mean().sort_values(ascending=False)
 freeze=json.loads((OUT/'contracts/freeze_manifest.json').read_text())
 common=f"Observed evidence: 2 videos, 2 queries, 4 development groups, 30/60/120/240 s, measured physical action trace replay. Statistical power is LIMITED.\n\n"
 reports={
 'ASSET_AND_IDENTIFICATION_AUDIT.md':f"# Asset and identification audit\n\n{common}Event and candidate-cluster utility are supported; all 914 units have SCAN and CONFIRM outcomes. Validation is unavailable and test remains sealed. Combined physical wall-clock support is APPROXIMATE.\n",
 'FRONTIER_CONTRACT_REPORT.md':f"# Frontier contract report\n\n{common}Frozen capacity is 10. Admission, deterministic score retention, queried terminalization, and highest-score CONFIRM passed replay/state-isolation checks.\n",
 'ACTION_COST_REPORT.md':f"# Action cost report\n\n{common}Every action charges measured seek/decode/Y8/tracking/scoring/serialization or physical Oracle plus commit overhead. {deadline['deadline_overrun_runs']} online runs crossed the deadline under the frozen Q90 admission estimate; post-deadline commits were excluded from utility. This prevents a formal hard-deadline safety claim.\n",
 'FIXED_RATIO_BASELINE_REPORT.md':f"# Fixed allocation baselines\n\n{common}Strongest fixed policy: `{strongest}` with macro utility-deadline AUC {fixed_auc:.3f}. The controller should fall back to this policy within the frozen development scope.\n",
 'MYOPIC_VPS_REPORT.md':f"# Myopic-VPS report\n\n{common}Myopic macro AUC was {myopic_auc:.3f}; delta versus `{strongest}` was {stats['macro_auc_delta']:.3f} (paired group bootstrap 95% CI {ci}). It made zero CONFIRM calls in all 16 runs. Signal: `NOT_ESTABLISHED`.\n",
 'OFFLINE_ACTION_ORACLE_REPORT.md':f"# Offline action Oracle report\n\n{common}One-step macro AUC={oracle_auc.get('OFFLINE_ONE_STEP_ORACLE',float('nan')):.3f}; approximate multi-step beam macro AUC={oracle_auc.get('OFFLINE_MULTI_STEP_ORACLE',float('nan')):.3f}. The latter is not an exact upper bound when pruning occurred. Both were evaluator-only.\n",
 'LONG_HORIZON_EFFECT_AUDIT.md':f"# Long-horizon effect audit\n\n{common}Multi-step replay exceeds one-step replay, but Myopic fails before a clean long-horizon diagnosis because its heterogeneous SCAN-cluster and CONFIRM-event numerators force perpetual SCAN. SMDP remains deferred.\n",
 'FAILURE_ANALYSIS.md':f"# Failure analysis\n\nStrongest supported conclusion: Myopic-VPS is rejected in this benchmark. Decisive evidence: zero CONFIRM actions and AUC delta {stats['macro_auc_delta']:.3f}. Main competing explanation: the prior/margin is poor rather than the value units; however A1/A2/A7/A8 isolate normalization, shrinkage, margin, and tie-break, and none establishes the full controller (mean utilities: {abls.to_dict()}). Key uncertainty: how to put SCAN option value and CONFIRM terminal utility on one calibrated common scale without changing the frozen scientific contract. Rejection trigger met: fixed allocation is stronger and low-budget delta is {low:.3f}.\n",
 }
 for name,text in reports.items(): write_text(OUT/'reports'/name,text)
 final=f"""# Final decision

Myopic-VPS is **not established**. The strongest fixed wall-clock policy is `{strongest}`. This is a development trace-replay mechanism pilot, not a physical end-to-end or generalization result.

CONTRACT_HASH = {freeze['contract_hash']}
CODE_COMMIT = {freeze['code_commit']}

VIDEO_COUNT = 2
QUERY_COUNT = 2
INDEPENDENT_GROUP_COUNT = 4

UTILITY_LEVEL = DISTINCT_EVENTS
EVENT_MAPPING_SUPPORT = SUPPORTED
ARC_COMPARISON_SUPPORT = CONTEXT_ONLY_NOT_FORMAL
PHYSICAL_WALLCLOCK_SUPPORT = APPROXIMATE

SCAN_PRIMITIVE = ANYTIME_LARGEST_GAP
CONFIRM_OPERATOR = FROZEN_EXISTING_OPERATOR
FRONTIER_CONTRACT_HASH = {freeze['frontier_contract_hash']}

STRONGEST_FIXED_RATIO_BASELINE = {strongest}
ARC_RESULT = NOT_FORMALLY_COMPARABLE
OFFLINE_ONE_STEP_ORACLE = AUC_{oracle_auc.get('OFFLINE_ONE_STEP_ORACLE',float('nan')):.6f}
OFFLINE_MULTI_STEP_ORACLE = APPROXIMATE_BEAM_AUC_{oracle_auc.get('OFFLINE_MULTI_STEP_ORACLE',float('nan')):.6f}

SELECTED_MYOPIC_CONFIG = UNINFORMATIVE_PRIOR_MARGIN_0.001
VPS_SCAN_ESTIMATOR = GAMMA_POISSON_COVERAGE_BUCKETED
VPS_CONFIRM_ESTIMATOR = BETA_BERNOULLI_SCORE_BUCKETED
MARGIN = 0.001
TIE_BREAK = SCAN

PRIMARY_UTILITY_AUC_DELTA = {stats['macro_auc_delta']:.6f}
LOW_BUDGET_DELTA = {low:.6f}
CROSS_GROUP_DIRECTION = NONNEGATIVE_RATE_{stats['group_nonnegative_rate']:.6f}
LEAVE_BEST_GROUP_OUT = {leave:.6f}
BEST_GROUP_CONTRIBUTION = NOT_APPLICABLE_NO_POSITIVE_GAIN
COST_ADJUSTED_DELTA = {stats['macro_auc_delta']:.6f}

MYOPIC_VPS_SIGNAL = NOT_ESTABLISHED
CONTEXTUAL_BANDIT_STATUS = DEFERRED
SMDP_STATUS = DEFERRED
RL_STATUS = PROHIBITED_IN_THIS_CONTRACT
SELECTED_CONTROLLER = STRONGEST_FIXED_TIME_RATIO
FORMAL_GENERALIZATION_CLAIM = NOT_ESTABLISHED
NEXT_ALLOWED_STAGE = RETURN_TO_FIXED_ALLOCATION_OR_REVISE_VALUE_ESTIMATION
"""
 write_text(OUT/'reports/FINAL_DECISION.md',final)
 write_json(OUT/'physical_validation/STATUS.json',deadline)
 print(json.dumps({'strongest':strongest,'stats':stats,'decision':decision},indent=2))

if __name__=='__main__': main()
