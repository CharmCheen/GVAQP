#!/usr/bin/env python3
"""Fail-closed paired continuation runner; never reads evaluator reference."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUN=ROOT/'outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s'; OUT=RUN/'counterfactual_continuation_v1'
import sys; sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'scripts'))
from rc_sem.counterfactual_probe import LogicalSnapshot, public_actions
from rc_sem.exploratory_gate_o import event_groups
from rc_sem.exploratory_h0 import RuntimeAction
from run_counterfactual_branch_probe import Oracle, scan_cell
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n');os.replace(q,p)
def snap(v):
 v=dict(v);v['scan_order']=tuple(v['scan_order']);v['scanned_cells']=tuple(v['scanned_cells']);v['exposed_candidates']=tuple(v['exposed_candidates']);v['attempted_verify_units']=tuple(v['attempted_verify_units']);v['confirmed_positive_units']=tuple(v['confirmed_positive_units']);v['rejected_units']=tuple(v['rejected_units']);v['prior_cost_seconds']=tuple(v['prior_cost_seconds']);v['parent_action']=RuntimeAction(**v['parent_action']);return LogicalSnapshot(**v)
def action(state,act,oracle,fps):
 st=time.perf_counter()
 if act['kind']=='SCAN': outcome=scan_cell(act['target'],fps)
 else: outcome=oracle.verify(act['target'],fps)
 cost=time.perf_counter()-st; return outcome,cost
def mutable(s):
 return {'elapsed':s.elapsed_seconds,'scanned':set(s.scanned_cells),'exposed':{int(x['unit_id']):dict(x) for x in s.exposed_candidates},'attempted':set(s.attempted_verify_units),'positive':set(s.confirmed_positive_units),'rejected':set(s.rejected_units),'order':s.scan_order,'cursor':s.next_scan_index}
def next_b(x):
 scores=x['exposed']; labels=x['attempted']; scan=x['cursor']<len(x['order']); cand=sorted(set(scores)-labels,key=lambda u:(-scores[u]['score'],u))
 if len(x['scanned'])==len(labels) and scan:return {'kind':'SCAN','target':x['order'][x['cursor']]}
 if cand:return {'kind':'VERIFY','target':cand[0]}
 if scan:return {'kind':'SCAN','target':x['order'][x['cursor']]}
 return None
def apply(x,act,out,cost):
 start=x['elapsed'];x['elapsed']+=cost
 if act['kind']=='SCAN':
  x['scanned'].add(act['target']);x['cursor']+=1
  for z in out['exposed']:x['exposed'][int(z['unit_id'])]=z
 else:
  x['attempted'].add(act['target']); (x['positive'] if out['label']=='positive' else x['rejected']).add(act['target'])
 return {'action_type':act['kind'],'target':act['target'],'logical_start_seconds':start,'physical_cost_seconds':cost,'completion_seconds':x['elapsed'],'outcome':out,'event_relation_after':[list(g) for g in event_groups(x['positive'])],'remaining_deadline_seconds':300-x['elapsed']}
def run_arm(pair,arm,oracle,fps):
 s=snap(pair['state_snapshot']); x=mutable(s); act=pair['control_action'] if arm=='control' else pair['treatment_action']; rows=[];out,cost=action(x,act,oracle,fps);rows.append(apply(x,act,out,cost));continuation_cost=0.;additional=0
 while additional<6 and continuation_cost<60 and x['elapsed']<300:
  act=next_b(x)
  if act is None:break
  out,cost=action(x,act,oracle,fps);rows.append(apply(x,act,out,cost));continuation_cost+=cost;additional+=1
 stop='MAX_ADDITIONAL_ACTIONS' if additional>=6 else 'MAX_CONTINUATION_TIME' if continuation_cost>=60 else 'DEADLINE_OR_NO_ACTION'
 return {'pair_id':pair['pair_id'],'state_id':pair['state_id'],'parent_state_sha256':pair['parent_state_sha256'],'arm':arm,'initial_elapsed_seconds':s.elapsed_seconds,'initial_event_relation':[list(g) for g in event_groups(s.confirmed_positive_units)],'initial_legal_actions':pair['initial_legal_actions'],'intervention_action':pair['control_action'] if arm=='control' else pair['treatment_action'],'actions':rows,'additional_actions_completed':additional,'continuation_physical_seconds':continuation_cost,'stop_reason':stop,'full_policy_rerun':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('dry-run','execute'),required=True);a=ap.parse_args();c=json.loads((OUT/'CONTINUATION_PROBE_CONTRACT.json').read_text());p=json.loads((OUT/'CONTINUATION_PROBE_PLAN.json').read_text())
 if p['contract_sha256']!=c['contract_sha256']:raise RuntimeError('contract mismatch')
 for q in p['pairs']:
  s=snap(q['state_snapshot']); legal=[z.__dict__ for z in public_actions(s)]
  if s.sha256()!=q['parent_state_sha256'] or legal!=q['initial_legal_actions'] or q['control_action'] not in legal or q['treatment_action'] not in legal:raise RuntimeError('snapshot/legal mismatch')
 if a.mode=='dry-run':print(json.dumps({'status':'DRY_RUN_PASS_NO_ORACLE_CALLS','pairs':7}));return
 auth=OUT/'EXECUTION_AUTHORIZATION.json'
 if not auth.exists() or not json.loads(auth.read_text()).get('execution_authorized'):raise RuntimeError('fail closed: authorization required')
 if (OUT/'EXECUTION_INDEX.json').exists():raise RuntimeError('refuse overwrite')
 import cv2
 fps=float(cv2.VideoCapture(str(ROOT/'data/realcam/guangzhou.mp4')).get(cv2.CAP_PROP_FPS));oracle=Oracle();entries=[]
 for pair in p['pairs']:
  for arm in ('control','treatment'):
   r=run_arm(pair,arm,oracle,fps);path=OUT/'pairs'/pair['pair_id']/f'{arm}.json';save(path,r);entries.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)})
 save(OUT/'EXECUTION_INDEX.json',{'entries':entries,'full_policy_rerun':False,'mab_implemented':False});print(json.dumps({'status':'COMPLETE','arms':len(entries)}))
if __name__=='__main__':main()
