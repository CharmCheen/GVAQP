#!/usr/bin/env python3
"""Offline-only deadline-safe paired continuation evaluation."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUN=ROOT/'outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s';OUT=RUN/'counterfactual_continuation_v1'
import sys;sys.path.insert(0,str(ROOT/'src'))
from rc_sem.exploratory_gate_o import event_groups,event_recall,event_f1,right_continuous_auc
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summary(x,ref):
 initial=tuple(tuple(a) for a in x['initial_event_relation']); events=event_groups(i for i,v in ref.items() if v=='positive');pts_r=[(0.,event_recall(initial,events))];pts_f=[(0.,event_f1(initial,events))];first=None;final=initial
 for a in x['actions']:
  t=a['completion_seconds']-x['initial_elapsed_seconds']
  if a['completion_seconds']<=min(300,x['initial_elapsed_seconds']+60):
   final=tuple(tuple(g) for g in a['event_relation_after']);pts_r.append((t,event_recall(final,events)));pts_f.append((t,event_f1(final,events)))
   if len(final)>len(initial) and first is None:first=t
 horizon=min(60.,300-x['initial_elapsed_seconds']);pts_r=[z for z in pts_r if z[0]<=horizon];pts_f=[z for z in pts_f if z[0]<=horizon];cost=sum(a['physical_cost_seconds'] for a in x['actions']);return {'cost':cost,'actions_completed':len(x['actions']),'events_gained':len(final)-len(initial),'first_event_time':first,'recall_auc':right_continuous_auc(pts_r,horizon),'f1_auc':right_continuous_auc(pts_f,horizon),'stop_reason':x['stop_reason']}
def main():
 plan=json.loads((OUT/'CONTINUATION_PROBE_PLAN.json').read_text());ref={int(k):v['label'] for k,v in json.loads((RUN/'reference_labels.json').read_text()).items()};rows=[]
 for p in plan['pairs']:
  c=json.loads((OUT/'pairs'/p['pair_id']/'control.json').read_text());t=json.loads((OUT/'pairs'/p['pair_id']/'treatment.json').read_text());a,b=summary(c,ref),summary(t,ref)
  if b['events_gained']>a['events_gained'] or (b['events_gained']==a['events_gained'] and b['first_event_time'] is not None and (a['first_event_time'] is None or b['first_event_time']<a['first_event_time']) and b['recall_auc']>a['recall_auc']):cl='CONVERTED_HEADROOM'
  elif b['events_gained']<a['events_gained'] or b['recall_auc']<a['recall_auc']:cl='WORSE'
  elif b['cost']<a['cost']:cl='COST_SAVING_ONLY'
  else:cl='DISSIPATED'
  rows.append({'pair_id':p['pair_id'],'state_id':p['state_id'],'control_action':p['control_action'],'treatment_action':p['treatment_action'],'control':a,'treatment':b,'delta':{'cost':b['cost']-a['cost'],'events':b['events_gained']-a['events_gained'],'recall_auc':b['recall_auc']-a['recall_auc'],'f1_auc':b['f1_auc']-a['f1_auc']},'classification':cl})
 counts={k:sum(r['classification']==k for r in rows) for k in ('CONVERTED_HEADROOM','COST_SAVING_ONLY','DISSIPATED','WORSE','INVALID_PAIR')};decision='REACHABLE_COST_TO_UTILITY_CONVERSION_POSITIVE' if counts['CONVERTED_HEADROOM']>=2 else 'REACHABLE_COST_TO_UTILITY_CONVERSION_INCONCLUSIVE' if counts['CONVERTED_HEADROOM'] else 'NO_REACHABLE_COST_TO_UTILITY_CONVERSION';next_step={'REACHABLE_COST_TO_UTILITY_CONVERSION_POSITIVE':'PROCEED_TO_FORMAL_GATE_H_DESIGN','REACHABLE_COST_TO_UTILITY_CONVERSION_INCONCLUSIVE':'DO_NOT_IMPLEMENT_MAB_YET','NO_REACHABLE_COST_TO_UTILITY_CONVERSION':'STOP_MAB_ROUTE_FOR_CURRENT_GUANGZHOU_REGIME'}[decision]
 output={'rows':rows,'counts':counts,'conversion_rate':counts['CONVERTED_HEADROOM']/len(rows),'decision':decision,'next_step':next_step,'total_scan_actions':sum(a['action_type']=='SCAN' for p in plan['pairs'] for arm in ('control','treatment') for a in json.loads((OUT/'pairs'/p['pair_id']/f'{arm}.json').read_text())['actions']),'total_verify_calls':sum(a['action_type']=='VERIFY' for p in plan['pairs'] for arm in ('control','treatment') for a in json.loads((OUT/'pairs'/p['pair_id']/f'{arm}.json').read_text())['actions']),'integrity':{'B_trace':sha(RUN/'B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.trace.json'),'deadline_safe':sha(RUN/'RESULTS_DEADLINE_SAFE.json'),'H0':sha(RUN/'H0_CAUSAL_REACHABILITY_AUDIT.json')}}
 (OUT/'CONTINUATION_PROBE_RESULTS.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n');(OUT/'INTEGRITY.json').write_text(json.dumps(output['integrity'],indent=2,sort_keys=True)+'\n');print(json.dumps({'decision':decision,'counts':counts,'scan':output['total_scan_actions'],'verify':output['total_verify_calls']},indent=2))
if __name__=='__main__':main()
