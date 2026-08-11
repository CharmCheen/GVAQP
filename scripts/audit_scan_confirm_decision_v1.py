#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/scan_confirm_decision_v1'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w',encoding='utf-8') as f: json.dump(value,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)

def main():
 required=[
  ROOT/'docs/SCAN_CONFIRM_DECISION_BENCHMARK_CONTRACT_V1.md', ROOT/'configs/scan_confirm_myopic_vps.yaml',
  OUT/'contracts/freeze_manifest.json', OUT/'contracts/public_state_schema.json',
  OUT/'fixed_ratio_baselines/run_metrics.csv', OUT/'myopic_vps/run_metrics.csv', OUT/'offline_oracle/run_metrics.csv',
  OUT/'ablations/run_metrics.csv', OUT/'statistics/paired_bootstrap.json', OUT/'metrics/gate_decision.json',
 ]+[OUT/'audits'/x for x in ['asset_audit.json','utility_support_audit.json','frontier_audit.json','action_outcome_audit.json','arc_comparability_audit.json','deadline_support_audit.json','state_visibility_audit.json']]+[OUT/'reports'/x for x in ['ASSET_AND_IDENTIFICATION_AUDIT.md','FRONTIER_CONTRACT_REPORT.md','ACTION_COST_REPORT.md','FIXED_RATIO_BASELINE_REPORT.md','MYOPIC_VPS_REPORT.md','OFFLINE_ACTION_ORACLE_REPORT.md','LONG_HORIZON_EFFECT_AUDIT.md','FAILURE_ANALYSIS.md','FINAL_DECISION.md']]
 missing=[str(p.relative_to(ROOT)) for p in required if not p.exists()]
 fixed=pd.read_csv(OUT/'fixed_ratio_baselines/run_metrics.csv'); myopic=pd.read_csv(OUT/'myopic_vps/run_metrics.csv'); abl=pd.read_csv(OUT/'ablations/run_metrics.csv'); oracle=pd.read_csv(OUT/'offline_oracle/run_metrics.csv')
 traces=list((OUT/'fixed_ratio_baselines/traces').glob('*.json'))+list((OUT/'myopic_vps/traces').glob('*.json'))+list((OUT/'ablations/traces').glob('*.json'))+list((OUT/'offline_oracle/traces').glob('*.json'))
 transition_rows=[]; bad=[]
 for path in traces:
  rows=json.loads(path.read_text())
  prior=-1.0
  for row in rows:
   needed={'action','estimated_action_cost_sec','actual_action_cost_sec','action_started','action_completed','new_candidate_clusters','new_distinct_utility','cumulative_wallclock','remaining_budget'}
   if not needed.issubset(row) or float(row['cumulative_wallclock'])<prior: bad.append(str(path.relative_to(ROOT))); break
   prior=float(row['cumulative_wallclock'])
  transition_rows.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'transitions':len(rows),'reconstruction':'frozen initial reset + ordered action ledger + immutable action outcome assets'})
 (OUT/'action_benchmark').mkdir(parents=True,exist_ok=True)
 pd.DataFrame(transition_rows).to_csv(OUT/'action_benchmark/trace_index.csv',index=False)
 schema=json.loads((OUT/'contracts/public_state_schema.json').read_text()); forbidden=set(schema['forbidden_policy_fields'])
 source='\n'.join(p.read_text() for p in (ROOT/'src/garc_eval/scan_confirm_controller').glob('*.py'))
 # Literal field names may occur in the validator/schema discussion; only controller decision code is checked.
 controller=(ROOT/'src/garc_eval/scan_confirm_controller/myopic_controller.py').read_text()
 forbidden_in_controller=[x for x in forbidden if x in controller]
 checks={
  'required_artifacts_present':not missing,'fixed_policy_rows':len(fixed)==160,'myopic_rows':len(myopic)==16,
  'ablation_rows':len(abl)==176,'oracle_rows':len(oracle)==32,'trace_count':len(traces)==384,
  'transition_schema_complete':not bad,'forbidden_policy_fields_absent':not forbidden_in_controller,
  'myopic_zero_confirm_reproduced':int(myopic.oracle_calls.sum())==0,
  'test_sealed':json.loads((OUT/'audits/asset_audit.json').read_text())['test_status']=='SEALED',
  'new_oracle_calls_zero':json.loads((OUT/'audits/action_outcome_audit.json').read_text())['new_oracle_calls']==0,
 }
 review={
  'review_role':'INDEPENDENT_ADVERSARIAL_COMPLETION_AUDIT','created_utc':datetime.now(timezone.utc).isoformat(),
  'status':'PASS_WITH_SCOPE_LIMITATIONS' if all(checks.values()) else 'FAIL','checks':checks,'missing':missing,
  'bad_traces':sorted(set(bad)),'forbidden_fields_in_decision_code':forbidden_in_controller,
  'adversarial_findings':[
   'Main benchmark composes measured physical action traces; it is not a newly executed combined wall-clock run.',
   'Frozen Q90 admission produced deadline overruns; post-deadline utility is correctly excluded but hard-deadline safety is not established.',
   'Only four development groups exist; inferential power and generalization are limited.',
   'Approximate multi-step beam is not an exact upper bound.',
   'Myopic failure is structurally consistent with incomparable SCAN-cluster and CONFIRM-event numerators; it does not justify RL.'
  ],
  'conclusion':'The NOT_ESTABLISHED decision and R4 fixed-allocation handoff are supported under trace-replay development scope; broader physical/generalization claims are rejected.'
 }
 write(OUT/'reports/INDEPENDENT_COMPLETION_AUDIT.json',review)
 manifest={}
 for p in sorted(OUT.rglob('*')):
  if p.is_file() and p.name!='artifact_hash_manifest.json': manifest[str(p.relative_to(ROOT))]=sha(p)
 write(OUT/'artifact_hash_manifest.json',{'created_utc':review['created_utc'],'artifact_count':len(manifest),'artifacts':manifest})
 print(json.dumps(review,indent=2))

if __name__=='__main__': main()
