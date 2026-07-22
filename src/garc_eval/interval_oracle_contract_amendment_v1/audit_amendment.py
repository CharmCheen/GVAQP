#!/usr/bin/env python3
"""Independent fail-closed audit of the zero-call contract amendment."""
import csv,hashlib,json,math,subprocess,sys
from pathlib import Path
import pandas as pd
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'DARE_AQP_Experiment_v1').is_dir())
OUT=ROOT/'DARE_AQP_Experiment_v1/outputs/gate_c0_interval_contract_amendment_v1'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def rows(p):
 with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
checks=[]
def check(n,p,e):checks.append({'check':n,'status':'PASS' if p else 'FAIL','evidence':str(e)})

# Inputs and zero-response boundary.
for name in ['SOURCE_MANIFEST.csv','INPUT_MANIFEST.csv']:
 m=rows(OUT/'config'/name); check(name+' hashes',all((ROOT/r['path']).is_file() and sha(ROOT/r['path'])==r['sha256'] for r in m),len(m))
blocked_calls=rows(ROOT/'DARE_AQP_Experiment_v1/outputs/gate_c0_physical_interval_operator_v1/oracle/VLM_CALL_LEDGER.csv')
response_files=[p for p in OUT.rglob('*') if p.is_file() and ('response' in p.name.lower() or 'vlm_call' in p.name.lower())]
check('no physical response exists or accessed',len(blocked_calls)==0 and not response_files,'0 calls; 0 response files')

# Governing targets and derivation grid.
cfg=json.load(open(ROOT/'DARE_AQP_Experiment_v1/config/gate_c0.json'))
check('governing targets',cfg['recall_targets'][0]==.8 and cfg['go_cost_ratio']==.7 and 347==len(pd.read_csv(ROOT/cfg['inputs']['units'])),'recall=.8 cost<.7 dense=347')
grid=pd.read_csv(OUT/'derivation/ANY_ERROR_INJECTION_GRID.csv'); region=pd.read_csv(OUT/'derivation/ANY_FEASIBLE_REGION.csv')
check('ANY grid completeness',len(grid)==8*6*4*3*2 and {'independent','adversarial_multi','adversarial_boundary'}==set(grid.placement),len(grid))
baseline=grid[(grid.effective_sensitivity==1)&(grid.effective_specificity==1)&(grid.unknown_rate==0)&
              (grid.placement=='adversarial_multi')&(grid.fixed_fraction==1)].iloc[0]
check('error simulator exact-baseline reproduction',int(baseline.logical_interval_calls_worst)==201 and
      int(baseline.events_found_worst)==21 and abs(float(baseline.dense_ratio_worst)-222.25/347)<1e-12,
      '201 calls, 21 events, 222.25/347')
adversarial=grid[(grid.effective_sensitivity<1)&(grid.placement=='adversarial_multi')&(grid.fixed_fraction==1)]
check('adversarial false-negative injection active',not adversarial.joint_pass_all_replicates.any(),'all sub-unit sensitivity cells fail')
passing=region[region.all_placements_pass]
check('conservative feasible region',len(passing)==2 and set(passing.effective_sensitivity)=={1.0} and set(passing.unknown_rate)=={0.0} and min(passing.effective_specificity)==.99,passing[['effective_sensitivity','effective_specificity','unknown_rate']].to_dict('records'))
check('threshold direction',not region[(region.effective_sensitivity<1)|(region.effective_specificity<.99)|(region.unknown_rate>0)].all_placements_pass.any(),'no looser passing cell')

# COUNT safety and fallbacks.
contract=json.load(open(OUT/'contract/C0_PHYSICAL_INTERVAL_OPERATOR_CONTRACT_v2.json')); claimed=contract.pop('contract_hash_sha256')
check('contract hash/immutability',canonical(contract)==claimed,claimed)
check('later decision precedence complete',set(contract['later_decisions'])==set(contract['decision_precedence']) and len(contract['decision_precedence'])==5,contract['decision_precedence'])
check('COUNT priority safety',contract['count_role']=='COUNT_PRIORITY_ONLY' and contract['count_not_required_for_go'] and contract['maximum_count_undercount_rate'] is None,'non-pruning optional COUNT')
count_grid=pd.read_csv(OUT/'derivation/COUNT_ERROR_INJECTION_GRID.csv')
check('COUNT grid and recall invariance',len(count_grid)==6*5*5*3 and count_grid.event_recall.nunique()==1 and abs(count_grid.event_recall.iloc[0]-21/26)<1e-12,'450 cells; priority-only recall invariant')
failure=pd.read_csv(OUT/'contract/ABSTAIN_AND_FAILURE_POLICY.csv')
unsafe=failure[(failure.outcome!='valid_negative_high_complete') & (failure.prune.astype(str).str.lower()=='true')]
check('abstain/failure safe fallback',unsafe.empty and set(failure.logical_cost)=={'charge'} and set(failure.physical_cost)=={'charge'},'all charged; only valid high complete negative prunes')

# Exact confidence and call budget.
b=pd.read_csv(OUT/'power/ACHIEVABLE_CONFIDENCE_BOUNDS.csv')
check('exact CP recomputation',all(abs(r.clopper_pearson_lower-.05**(1/int(r.independent_trials)))<1e-14 for r in b.itertuples()),'one-sided 95%')
plan=pd.read_csv(OUT/'power/CALL_BUDGET_PLAN.csv'); total=int(plan[plan.component=='TOTAL CAP'].calls.iloc[0])
check('160-call accounting',total==160 and int(plan.iloc[:-1].calls.sum())==160,total)
check('sample size infeasible',not contract['sample_size_feasible'] and contract['minimum_effective_any_sensitivity']==1.0 and .05**(1/160)<1.0,'finite lower bound <1')

decision=rows(OUT/'FINAL_DECISION.csv')[0]
check('decision compliance',decision['decision']=='CONTRACT_INFEASIBLE_UNDER_160_CALLS' and decision['physical_vlm_calls']=='0' and decision['sample_size_feasible'].lower()=='false',decision['decision'])
manifest=OUT/'FILE_MANIFEST.csv'
if manifest.exists():
 m=rows(manifest); mok=all((ROOT/r['path']).is_file() and sha(ROOT/r['path'])==r['sha256'] for r in m)
else:m=[];mok=False
check('all sealed file hashes',mok,len(m))

verdict='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL'
review={'verdict':verdict,'checks':checks,'physical_vlm_calls':0,'conclusion':'Contract is correctly infeasible under 160 calls; no physical gate is authorized.'}
(OUT/'audit/INDEPENDENT_ADVERSARIAL_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
if verdict=='PASS':
 # Deterministically seal PASS into tabular artifacts.
 d=pd.read_csv(OUT/'FINAL_DECISION.csv',keep_default_na=False); d.loc[0,'independent_review']='PASS'; d.to_csv(OUT/'FINAL_DECISION.csv',index=False)
 c=pd.read_csv(OUT/'audit/COMPLETION_AUDIT.csv',keep_default_na=False); c.loc[c.requirement=='Independent review','status']='PASS'; c.loc[c.requirement=='File hashes','status']='PASS'; c.to_csv(OUT/'audit/COMPLETION_AUDIT.csv',index=False)
 subprocess.run([sys.executable,str(Path(__file__).with_name('seal.py'))],check=True)
else: raise SystemExit(1)
print(verdict)
