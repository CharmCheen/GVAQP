#!/usr/bin/env python3
"""Independent raw-trace verifier for the public non-confirmatory H1B run."""
from __future__ import annotations
import csv, json
from pathlib import Path
from garc_eval.psvr_rollout_h1b.advantage import paired_advantage
from garc_eval.psvr_rollout_h1b.development import METHODS, PUBLIC_SEEDS, latest, sha
from garc_eval.psvr_rollout_h1b.uncertainty import paired_lcb_95

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/psvr_rollout_r2b_dev'
ATTEMPT=OUT/'development_attempt_repair2'

def write_csv(name, rows):
    fields=sorted({key for row in rows for key in row}) or ['label','non_confirmatory']
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(rows)

def time_weighted(timeline, stop):
    points=sorted((int(x['tick']),float(x['utility'])) for x in timeline)
    if not points or points[0][0]!=0 or points[-1][0]>stop: raise ValueError('invalid utility timeline')
    value=points[0][1]; previous=0; area=0.0
    for tick,next_value in points[1:]:
        area += value*(tick-previous); previous=tick; value=next_value
    area += value*(stop-previous)
    return area / stop if stop else value

def main():
    ledger=ATTEMPT/'DEVELOPMENT_ATTEMPT_LEDGER.jsonl'; errors=[]
    if not ledger.is_file(): errors.append('missing-ledger'); rows={}
    else: rows=latest(ledger)
    matrix=json.loads((OUT/'H1B_DEVELOPMENT_COVERAGE_MATRIX.json').read_text())['rows']
    hashes={'implementation_freeze':sha(ROOT/'outputs/psvr_rollout_r2b_impl/H1B_IMPLEMENTATION_FREEZE_MANIFEST.json'),'coverage_matrix':sha(OUT/'H1B_DEVELOPMENT_COVERAGE_MATRIX.json'),'seed_registry':sha(OUT/'H1B_DEVELOPMENT_SEED_REGISTRY.json')}
    expected_keys={(f'development-{i:04d}',cfg['configuration_id'],method) for i in range(len(PUBLIC_SEEDS)) for cfg in matrix for method in METHODS}
    if set(rows)!=expected_keys: errors.append('identity-universe-mismatch')
    derived=[]; overrides=[]; failures=[]; action_agreement=[]; regrets=[]
    for key,row in sorted(rows.items()):
        if row['state'] not in {'COMMITTED','RECOVERY_COMMITTED'}:
            errors.append(f'nonterminal:{key}'); failures.append({'label':'DEBUG_ONLY_NOT_FOR_SCIENTIFIC_USE','non_confirmatory':True,'identity':str(key),'state':row['state']}); continue
        if row.get('source_config_hashes')!=hashes: errors.append(f'freeze-hash:{key}'); continue
        path=ATTEMPT/(row.get('raw_trace_path') or '')
        if not path.is_file() or sha(path)!=row.get('raw_trace_sha256'): errors.append(f'raw-hash:{key}'); continue
        raw=json.loads(path.read_text()); trace=raw.get('trace',{})
        immutable_identity=('development_episode_id','configuration_id','method_id','budget_id','error_target_id','planning_cost_id','source_config_hashes')
        if raw.get('non_confirmatory') is not True or raw.get('label')!='DEBUG_ONLY_NOT_FOR_SCIENTIFIC_USE' or any(raw.get('identity',{}).get(field)!=row.get(field) for field in immutable_identity):
            errors.append(f'identity-contract:{key}')
        if raw.get('source_config_hashes')!=hashes: errors.append(f'raw-freeze-hash:{key}')
        if any(token in json.dumps(trace).lower() for token in ('exact_action','exact_q','future_truth','latent_world')): errors.append(f'exact-boundary:{key}')
        try:
            utility=time_weighted(raw['utility_timeline'],int(raw['stop_time']))
        except Exception: errors.append(f'utility-timeline:{key}'); utility=None
        recomputed={}
        for action,vectors in trace.get('paired_sample_vectors',{}).items():
            estimate=paired_advantage(tuple(vectors['action_returns']),tuple(vectors['base_returns']))
            recomputed[action]=(estimate.mean,paired_lcb_95(estimate),len(estimate.samples))
            if abs(float(trace['paired_advantages'].get(action,0))-estimate.mean)>1e-12 or abs(float(trace['lcbs'].get(action,0))-paired_lcb_95(estimate))>1e-12:
                errors.append(f'paired-recompute:{key}:{action}')
        if set(recomputed)!=set(trace.get('paired_advantages',{})): errors.append(f'paired-vector-universe:{key}')
        if int(trace.get('sample_count',0)) and any(n!=int(trace['sample_count']) for _,_,n in recomputed.values()): errors.append(f'budget-cardinality:{key}')
        if int(trace.get('post_planning_remaining_time',-1))<0: errors.append(f'negative-horizon:{key}')
        common={'label':'DEBUG_ONLY_NOT_FOR_SCIENTIFIC_USE','non_confirmatory':True,'development_episode_id':key[0],'configuration_id':key[1],'method_id':key[2]}
        derived.append({**common,'planning_time':trace.get('planning_time'),'remaining_after_planning':trace.get('post_planning_remaining_time'),'time_weighted_utility':utility,'stop_time':raw.get('stop_time'),'selected_action':trace.get('selected_action')})
        overrides.append({**common,'planning_admitted':trace.get('planning_admitted'),'fallback_reason':trace.get('fallback_reason'),'selected_action':trace.get('selected_action'),'base_action':trace.get('base_action')})
        action_agreement.append({**common,'agreement_reference':'NOT_COMPUTED_NO_EVALUATOR_ONLY_REFERENCE_ARTIFACT','selected_action':trace.get('selected_action')})
        regrets.append({**common,'regret_reference':'NOT_COMPUTED_NO_EVALUATOR_ONLY_REFERENCE_ARTIFACT'})
    raw_files=list((ATTEMPT/'DEVELOPMENT_RAW_TRACES').glob('*.json')) if (ATTEMPT/'DEVELOPMENT_RAW_TRACES').is_dir() else []
    if len(raw_files)!=len(rows): errors.append('ledger-raw-count-mismatch')
    if list(ATTEMPT.rglob('*.tmp')): errors.append('partial-raw-artifact')
    # A direct source scan is an additional guard: the approximate planner must
    # not import or name the exact reference evaluator.
    planner=(ROOT/'src/garc_eval/psvr_rollout_h1b/approximate_rollout.py').read_text().lower()
    if 'exact_reference' in planner or 'exactconditionalrollout' in planner: errors.append('planner-exact-import')
    write_csv('DEVELOPMENT_RAW_RESULTS.csv',derived)
    write_csv('DEVELOPMENT_ACTION_AGREEMENT.csv',action_agreement)
    write_csv('DEVELOPMENT_REGRET_DIAGNOSTICS.csv',regrets)
    write_csv('DEVELOPMENT_OVERRIDE_DIAGNOSTICS.csv',overrides)
    write_csv('DEVELOPMENT_RESOURCE_TIMINGS.csv',derived)
    write_csv('DEVELOPMENT_FAILURES.csv',failures)
    report={'status':'PASS' if not errors else 'FAIL','expected_identities':len(expected_keys),'latest_identities':len(rows),'committed_identities':sum(r.get('state') in {'COMMITTED','RECOVERY_COMMITTED'} for r in rows.values()),'error_count':len(errors),'errors':errors,'independent_recomputation':'paired means/LCBs and time-weighted utility from immutable raw traces','derived_outputs_read':False,'non_confirmatory':True,'action_agreement_status':'NOT_COMPUTED_NO_EVALUATOR_ONLY_REFERENCE_ARTIFACT','regret_status':'NOT_COMPUTED_NO_EVALUATOR_ONLY_REFERENCE_ARTIFACT'}
    (OUT/'H1B_DEVELOPMENT_INDEPENDENT_VERIFICATION.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps(report,sort_keys=True)); raise SystemExit(bool(errors))
if __name__=='__main__': main()
