#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os, sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from garc_eval.scan_confirm_controller.action import Action
from garc_eval.scan_confirm_controller.common_utility import (
    AlignmentObservations, CommonUtilityModel, SafeTraceReplayEnvironment,
    actual_common_values, collect_alignment_observations, congestion_bucket,
    predicted_common_values, score_bucket,
)
from garc_eval.scan_confirm_controller.common_utility_controller import FreeCommonUtilityController, RatioAnchoredCommonUtilityController
from garc_eval.scan_confirm_controller.fixed_ratio import FixedPolicyController
from garc_eval.scan_confirm_controller.offline_oracle import one_step_action_oracle

OUT=ROOT/'outputs/scan_confirm_common_utility_v1'; TASKS=['V0_Q1','V0_Q2','V1_Q1','V1_Q2']; BUDGETS=[30.,60.,120.,240.]

def write_json(path:Path,value:Any):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w',encoding='utf-8') as f: json.dump(value,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)
def write_csv(path:Path,frame:pd.DataFrame):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w',encoding='utf-8',newline='') as f: frame.to_csv(f,index=False); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)

def serialize_observations(obs:list[AlignmentObservations]):
 arrivals=pd.DataFrame([r for x in obs for r in x.arrivals]); conversions=pd.DataFrame([r for x in obs for r in x.conversions])
 write_csv(OUT/'audits/candidate_arrival_observations.csv',arrivals); write_csv(OUT/'audits/candidate_conversion_observations.csv',conversions)

def static_audit(obs:list[AlignmentObservations])->dict[str,Any]:
 rows=[]; support=[]
 for held in TASKS:
  external=[x for x in obs if x.task_id!=held]; model=CommonUtilityModel(external)
  env=SafeTraceReplayEnvironment(held,240.); policy=FixedPolicyController('R4_RATIO_25_75',0); policy.reset(240.,env.public_state())
  external_conversions=[r for x in external for r in x.conversions]
  for name in ('LOW','MEDIUM','HIGH'):
   support.append({'held_task':held,'score_bucket':name,'external_conversion_support':sum(r['score_bucket']==name for r in external_conversions),'external_positive_support':sum(r['score_bucket']==name and r['useful'] for r in external_conversions)})
  while True:
   state=env.public_state(); decision=policy.choose_action(state); action=Action(decision['action'])
   scan_legal=state['estimated_scan_cost_sec']<=state['remaining_budget_sec']; confirm_legal=state['frontier_size']>0 and state['estimated_confirm_cost_sec']<=state['remaining_budget_sec']
   if scan_legal and confirm_legal:
    predicted=predicted_common_values(env,model); actual=actual_common_values(env); best=env.frontier.best(); congestion=congestion_bucket(state['frontier_size']); sb=score_bucket(best.score)
    p=predicted['predicted_confirm_value']; y=actual['actual_confirm_value']; constant=model.constant_conversion_rate()
    if predicted['uvps_scan']>predicted['uvps_confirm']: pred_action='SCAN'
    elif predicted['uvps_confirm']>predicted['uvps_scan']: pred_action='CONFIRM'
    else: pred_action='TIE'
    if actual['actual_scan_value']>actual['actual_confirm_value']: actual_action='SCAN'
    elif actual['actual_confirm_value']>actual['actual_scan_value']: actual_action='CONFIRM'
    else: actual_action='TIE'
    rows.append({'task_id':held,'elapsed_sec':env.elapsed,'remaining_budget_sec':state['remaining_budget_sec'],'coverage_fraction':state['coverage_fraction'],'frontier_size':state['frontier_size'],'score_bucket':sb,'congestion_bucket':congestion,**predicted,**actual,'predicted_action':pred_action,'actual_action':actual_action,'confirm_brier':(p-y)**2,'constant_brier':(constant-y)**2})
   if action is Action.STOP: break
   before_units={r.unit_id for r in env.frontier.rows()}; before=dict(state); result=env.step(action)
   if not result.completed: break
   if action is Action.SCAN:
    counts={'LOW':0,'MEDIUM':0,'HIGH':0}
    for candidate in env.frontier.rows():
     if candidate.unit_id not in before_units: counts[score_bucket(candidate.score)]+=1
    model.observe_scan({'coverage_bucket':'LOW' if before['coverage_fraction']<1/3 else 'MEDIUM' if before['coverage_fraction']<2/3 else 'HIGH','congestion_bucket':congestion_bucket(before['frontier_size']),**{f'arrivals_{k}':v for k,v in counts.items()}})
   elif result.score_bucket:
    model.observe_confirm(result.score_bucket,congestion_bucket(before['frontier_size']),result.new_distinct_utility)
   policy.observe(result)
  
 frame=pd.DataFrame(rows); write_csv(OUT/'static_alignment/state_action_values.csv',frame); write_csv(OUT/'audits/estimator_support.csv',pd.DataFrame(support))
 informative=frame.query("actual_action!='TIE'").copy()
 informative['ranking_credit']=np.where(informative.predicted_action=='TIE',.5,(informative.predicted_action==informative.actual_action).astype(float))
 group=informative.groupby('task_id',as_index=False).agg(informative_states=('ranking_credit','size'),ranking_accuracy=('ranking_credit','mean')) if len(informative) else pd.DataFrame(columns=['task_id','informative_states','ranking_accuracy'])
 write_csv(OUT/'static_alignment/per_group_ranking.csv',group)
 accuracy=float(informative.ranking_credit.mean()) if len(informative) else float('nan')
 # Balanced accuracy, with tie credit 0.5.
 recalls=[]
 for label in ('SCAN','CONFIRM'):
  part=informative.query('actual_action==@label'); recalls.append(float(part.ranking_credit.mean()) if len(part) else float('nan'))
 balanced=float(np.nanmean(recalls)) if any(np.isfinite(recalls)) else float('nan')
 group_deltas=(group.ranking_accuracy-.5).to_numpy(dtype=float); rng=np.random.default_rng(20260726)
 boot=np.asarray([rng.choice(group_deltas,len(group_deltas),replace=True).mean() for _ in range(10000)]) if len(group_deltas) else np.asarray([np.nan])
 encountered=set(frame.score_bucket); supported={(r['score_bucket']) for r in support if r['external_conversion_support']>=5}
 metrics={'both_legal_states':len(frame),'informative_states':len(informative),'informative_group_count':int((group.informative_states>0).sum()) if len(group) else 0,'ranking_accuracy':accuracy,'balanced_accuracy':balanced,'ranking_delta_over_chance':accuracy-.5 if np.isfinite(accuracy) else None,'group_nonnegative_rate':float((group.ranking_accuracy>=.5).mean()) if len(group) else 0.,'group_bootstrap_delta_95_ci':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))] if len(group_deltas) else [None,None],'confirm_brier':float(frame.confirm_brier.mean()) if len(frame) else None,'constant_rate_brier':float(frame.constant_brier.mean()) if len(frame) else None,'predicted_scan_optimal_states':int((frame.predicted_action=='SCAN').sum()),'predicted_confirm_optimal_states':int((frame.predicted_action=='CONFIRM').sum()),'predicted_tie_states':int((frame.predicted_action=='TIE').sum()),'unsupported_encountered_score_buckets':sorted(encountered-supported)}
 gates={'1_support':metrics['informative_states']>=20 and metrics['informative_group_count']>=3,'2_accuracy':bool(np.isfinite(accuracy) and accuracy>.5 and accuracy-.5>0),'3_group_direction':metrics['group_nonnegative_rate']>=2/3,'4_brier':metrics['confirm_brier'] is not None and metrics['confirm_brier']<metrics['constant_rate_brier'],'5_support_and_leakage':not metrics['unsupported_encountered_score_buckets'],'6_both_actions_predicted':metrics['predicted_scan_optimal_states']>0 and metrics['predicted_confirm_optimal_states']>0}
 decision={'STATIC_ALIGNMENT_GATE':'PASS' if all(gates.values()) else 'FAIL','metrics':metrics,'gates':gates}
 write_json(OUT/'static_alignment/static_gate.json',decision); return decision

def run_controller(task,budget,name,external):
 env=SafeTraceReplayEnvironment(task,budget); model=CommonUtilityModel(external)
 if name=='R4_FIXED_25_75': controller=FixedPolicyController('R4_RATIO_25_75',0); controller.reset(budget,env.public_state())
 elif name=='FREE_COMMON_UTILITY_MYOPIC': controller=FreeCommonUtilityController(model)
 else: controller=RatioAnchoredCommonUtilityController(model)
 while True:
  before=env.public_state(); before_units={r.unit_id for r in env.frontier.rows()}
  decision=controller.choose_action(before) if name!='R4_FIXED_25_75' else controller.choose_action(before); action=Action(decision['action'])
  if action is Action.STOP: break
  result=env.step(action)
  if not result.completed: break
  if name=='R4_FIXED_25_75': controller.observe(result)
  else: controller.observe(before,before_units,env,result)
 summary=env.summary(name,0); summary['post_deadline_commit']=0; summary['incomplete_action']=0
 return summary,env.ledger

def replay(obs):
 summaries=[]
 for task in TASKS:
  external=[x for x in obs if x.task_id!=task]
  for budget in BUDGETS:
   for name in ('R4_FIXED_25_75','FREE_COMMON_UTILITY_MYOPIC','RATIO_ANCHORED_COMMON_UTILITY'):
    summary,ledger=run_controller(task,budget,name,external); summaries.append(summary); write_json(OUT/'replay/traces'/f'{name}__{task}__B{int(budget)}.json',ledger)
   oracle,ledger=one_step_action_oracle(SafeTraceReplayEnvironment(task,budget)); oracle['post_deadline_commit']=0; oracle['incomplete_action']=0; summaries.append(oracle); write_json(OUT/'replay/traces'/f'OFFLINE_ONE_STEP_ACTION_ORACLE__{task}__B{int(budget)}.json',ledger)
 frame=pd.DataFrame(summaries); write_csv(OUT/'replay/run_metrics.csv',frame); return frame

def main():
 parser=argparse.ArgumentParser(); parser.add_argument('--phase',choices=['static','all'],default='all'); args=parser.parse_args()
 freeze=json.loads((OUT/'contracts/freeze_manifest.json').read_text()); contract=ROOT/'docs/SCAN_CONFIRM_COMMON_UTILITY_ALIGNMENT_CONTRACT_V1.md'
 if hashlib.sha256(contract.read_bytes()).hexdigest()!=freeze['contract_hash']: raise SystemExit('contract changed after freeze')
 obs=[collect_alignment_observations(t) for t in TASKS]; serialize_observations(obs); gate=static_audit(obs)
 if args.phase=='all' and gate['STATIC_ALIGNMENT_GATE']=='PASS': replay(obs)
 else: write_json(OUT/'replay/STATUS.json',{'status':'NOT_RUN_STATIC_GATE_FAILED' if gate['STATIC_ALIGNMENT_GATE']=='FAIL' else 'STATIC_ONLY_REQUESTED'})
 print(json.dumps(gate,indent=2))
if __name__=='__main__': main()
