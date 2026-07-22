#!/usr/bin/env python3
"""Development-only H1B smoke runner; no confirmatory flags or imports."""
from __future__ import annotations
import argparse,hashlib,json,resource,time
from pathlib import Path
from garc_eval.psvr_rollout_h1b.development import METHODS,PUBLIC_SEEDS,append,execute,latest,sha
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/psvr_rollout_r2b_dev'; ATTEMPT=OUT/'development_attempt_repair2'
def main():
 p=argparse.ArgumentParser(); p.add_argument('--development-only',action='store_true'); p.add_argument('--resume',action='store_true'); a=p.parse_args()
 if not a.development_only: raise SystemExit('requires --development-only')
 if ATTEMPT.exists() and not a.resume: raise SystemExit('development attempt exists; use --resume')
 ATTEMPT.mkdir(parents=True,exist_ok=True); ledger=ATTEMPT/'DEVELOPMENT_ATTEMPT_LEDGER.jsonl'
 matrix=json.loads((OUT/'H1B_DEVELOPMENT_COVERAGE_MATRIX.json').read_text())['rows']; hashes={'implementation_freeze':sha(ROOT/'outputs/psvr_rollout_r2b_impl/H1B_IMPLEMENTATION_FREEZE_MANIFEST.json'),'coverage_matrix':sha(OUT/'H1B_DEVELOPMENT_COVERAGE_MATRIX.json'),'seed_registry':sha(OUT/'H1B_DEVELOPMENT_SEED_REGISTRY.json')}
 if not ledger.exists():
  for i,_ in enumerate(PUBLIC_SEEDS):
   for cfg in matrix:
    for method in METHODS: append(ledger,{'development_episode_id':f'development-{i:04d}','configuration_id':cfg['configuration_id'],'method_id':method,'budget_id':cfg['budget_id'],'error_target_id':cfg['error_target_id'],'planning_cost_id':cfg['planning_cost_id'],'attempt_ordinal':0,'state':'PREPARED','raw_trace_path':None,'raw_trace_sha256':None,'source_config_hashes':hashes})
 start=time.perf_counter(); rows=latest(ledger)
 for key,row in sorted(rows.items()):
  if row['state'] in {'COMMITTED','RECOVERY_COMMITTED'}: continue
  if row.get('source_config_hashes') != hashes: raise SystemExit(f'freeze hash mismatch for {key}')
  trace_path=ATTEMPT/'DEVELOPMENT_RAW_TRACES'/f"{row['development_episode_id']}__{row['configuration_id']}__{row['method_id']}.json"
  # A crash after atomic raw publication but before COMMITTED is recovered
  # without executing the identity a second time.
  if trace_path.exists():
   append(ledger,{**row,'state':'RECOVERY_COMMITTED','attempt_ordinal':row['attempt_ordinal']+1,'raw_trace_path':str(trace_path.relative_to(ATTEMPT)),'raw_trace_sha256':sha(trace_path)})
   continue
  append(ledger,{**row,'state':'RECOVERY_STARTED' if a.resume else 'STARTED','attempt_ordinal':row['attempt_ordinal']+1})
  try:
   item=execute(row,ATTEMPT,hashes); append(ledger,{**row,'state':'RECOVERY_COMMITTED' if a.resume else 'COMMITTED','attempt_ordinal':row['attempt_ordinal']+1,'raw_trace_path':item['path'],'raw_trace_sha256':item['sha256']})
  except Exception as exc:
   append(ledger,{**row,'state':'FAILED_DETERMINISTIC','attempt_ordinal':row['attempt_ordinal']+1,'failure_type':type(exc).__name__,'failure_message':str(exc)})
 end=time.perf_counter(); rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 (ATTEMPT/'RUN_RESOURCE_SAMPLE.json').write_text(json.dumps({'wall_seconds':end-start,'peak_rss_kib':rss},sort_keys=True)+'\n')
 print(json.dumps({'status':'DEVELOPMENT_SMOKE_COMPLETE','seconds':end-start,'peak_rss_kib':rss,'non_confirmatory':True}))
if __name__=='__main__': main()
