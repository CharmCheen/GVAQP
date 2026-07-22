#!/usr/bin/env python3
"""IC1 public, non-confirmatory full-horizon development runner."""
from __future__ import annotations

import argparse, gzip, hashlib, json, os, resource, time
from pathlib import Path

from garc_eval.psvr_rollout_h1b.development import METHODS, PUBLIC_SEEDS
from garc_eval.psvr_rollout_h1b.exact_reference import ExactReferenceEvaluator
from garc_eval.psvr_rollout_h1b.ic1 import ContinuationReturnCache, canonical_identity, execute_full_horizon, identity_hash

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/psvr_rollout_r2b_ic1'
ATTEMPT=OUT/'development_attempt_v9'

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic_gzip(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    with gzip.open(temporary, 'wt', encoding='utf-8', mtime=0) if False else gzip.open(temporary, 'wt', encoding='utf-8') as handle:
        json.dump(value, handle, sort_keys=True, separators=(',',':')); handle.write('\n')
    with temporary.open('rb') as handle: os.fsync(handle.fileno())
    os.replace(temporary,path)
def append(path: Path, row: dict) -> None:
    with path.open('a',encoding='utf-8') as handle:
        handle.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n'); handle.flush(); os.fsync(handle.fileno())
def latest(path: Path) -> dict[str,dict]:
    answer={}
    if path.exists():
        for line in path.read_text().splitlines():
            row=json.loads(line); answer[row['identity_hash']]=row
    return answer
def direction(form: str) -> str:
    return {'systematic_optimism':'OPTIMISTIC','systematic_pessimism':'PESSIMISTIC','independent_variance':'STOCHASTIC','state_dependent_calibration':'STATE_DEPENDENT'}[form]
def fallback(method: str) -> str:
    return {'B1_SHIELDED_PI0':'BASELINE','APPROX_NO_FALLBACK':'NONE','APPROX_POINT_ESTIMATE_FALLBACK':'POINT','APPROX_LCB_FALLBACK':'LCB','APPROX_PLANNING_ADMISSION_LCB':'LCB_ADMISSION'}[method]
def source_hashes() -> dict[str,str]:
    files=['outputs/psvr_rollout_r2b/H1B_PREREGISTRATION_FREEZE_MANIFEST.json','outputs/psvr_rollout_r2b/H1B_EXECUTION_SEMANTICS_A1_FREEZE_MANIFEST.json','outputs/psvr_rollout_r2b/H1B_EXECUTION_SEMANTICS_A2_FREEZE_MANIFEST.json','outputs/psvr_rollout_r2b/H1B_CHAIN_INTEGRITY_A3.json','outputs/psvr_rollout_r2b/H1B_EXECUTION_READY_RESULT_BLIND_FREEZE_MANIFEST.json','outputs/psvr_rollout_r2b_impl/H1B_IMPLEMENTATION_FREEZE_MANIFEST.json','outputs/psvr_rollout_r2b_dev/H1B_DEVELOPMENT_COVERAGE_MATRIX.json','outputs/psvr_rollout_r2b_dev/H1B_DEVELOPMENT_UNIVERSE_SPEC.json','outputs/psvr_rollout_r2b_ic1/IC1_REPAIR3_IMPLEMENTATION_MANIFEST.json','src/garc_eval/psvr_rollout_h1b/ic1.py','src/garc_eval/psvr_rollout_h1b/exact_reference.py','scripts/run_psvr_rollout_h1b_ic1_development.py']
    return {str(Path(name)):sha(ROOT/name) for name in files}
def identity_anchors() -> dict[str,str]:
    return {
        'canonical_spec_hash': sha(ROOT/'outputs/psvr_rollout_r2b/H1B_EXECUTION_READY_RESULT_BLIND_FREEZE_MANIFEST.json'),
        'implementation_hash': sha(OUT/'IC1_REPAIR3_IMPLEMENTATION_MANIFEST.json'),
        'development_universe_hash': sha(ROOT/'outputs/psvr_rollout_r2b_dev/H1B_DEVELOPMENT_UNIVERSE_SPEC.json'),
    }
def universe() -> list[dict]:
    rows=json.loads((ROOT/'outputs/psvr_rollout_r2b_dev/H1B_DEVELOPMENT_COVERAGE_MATRIX.json').read_text())['rows']
    # Legacy set-cover rows did not exercise independent variance,
    # state-dependent calibration, or magnitude 0.20.  These fixed,
    # result-blind extension rows complete axis coverage without changing a
    # frozen scientific cell or adapting to any development result.
    rows += [
        {'configuration_id':'ic1-cfg-13','budget_id':'b-4x4','error_target_id':'scan_candidate_yield','error_form':'independent_variance','error_magnitude':0.20,'planning_cost_id':'p-0'},
        {'configuration_id':'ic1-cfg-14','budget_id':'b-16x16','error_target_id':'confirm_positive_probability','error_form':'state_dependent_calibration','error_magnitude':0.20,'planning_cost_id':'p-2'},
        {'configuration_id':'ic1-cfg-15','budget_id':'b-64x64','error_target_id':'novelty_duplicate_probability','error_form':'independent_variance','error_magnitude':0.10,'planning_cost_id':'p-5'},
        {'configuration_id':'ic1-cfg-16','budget_id':'b-256x256','error_target_id':'grouping_transition','error_form':'state_dependent_calibration','error_magnitude':0.10,'planning_cost_id':'p-10'},
        {'configuration_id':'ic1-cfg-17','budget_id':'b-4x4','error_target_id':'action_duration','error_form':'independent_variance','error_magnitude':0.05,'planning_cost_id':'p-20'},
        {'configuration_id':'ic1-cfg-18','budget_id':'b-16x16','error_target_id':'materialization_success','error_form':'state_dependent_calibration','error_magnitude':0.05,'planning_cost_id':'p-2'},
    ]
    result=[]
    for episode_index in range(len(PUBLIC_SEEDS)):
        for config in rows:
            for method in METHODS:
                identity={'development_episode_id':f'development-{episode_index:04d}','configuration_id':config['configuration_id'],'method_id':method,'posterior_budget_id':'posterior-'+config['budget_id'].removeprefix('b-').split('x')[0],'trajectory_budget_id':'trajectory-'+config['budget_id'].removeprefix('b-').split('x')[1],'error_target':config['error_target_id'],'error_form':config['error_form'],'error_magnitude':config['error_magnitude'],'error_direction':direction(config['error_form']),'planning_cost_id':config['planning_cost_id'],'fallback_variant':fallback(method),'attempt_ordinal':0,**identity_anchors()}
                result.append(canonical_identity(identity))
    unique={identity_hash(row) for row in result}
    if len(unique)!=len(result): raise ValueError('duplicate-canonical-development-identity')
    return sorted(result,key=identity_hash)
def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument('--development-only',action='store_true'); parser.add_argument('--resume',action='store_true'); parser.add_argument('--limit',type=int); parser.add_argument('--shard-count',type=int,default=1); parser.add_argument('--shard-index',type=int,default=0); args=parser.parse_args()
    if not args.development_only: raise SystemExit('requires --development-only')
    gate_status=OUT/'IC1_GATE_STATUS.md'
    if gate_status.exists() and 'H1B_DEVELOPMENT_GATE = BLOCKED_' in gate_status.read_text():
        raise SystemExit('development execution disabled: frozen generative-transition semantics require result-blind clarification')
    if ATTEMPT.exists() and not args.resume: raise SystemExit('IC1 development attempt exists; use --resume')
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count: raise SystemExit('invalid deterministic shard')
    ATTEMPT.mkdir(parents=True,exist_ok=True); ledger=ATTEMPT/'DEVELOPMENT_ATTEMPT_LEDGER.jsonl'; sources=source_hashes(); all_items=universe(); items=[item for item in all_items if int(identity_hash(item),16) % args.shard_count == args.shard_index]; prior=latest(ledger); evaluator=ExactReferenceEvaluator(); continuation_cache=ContinuationReturnCache(); started=time.perf_counter()
    for identity in items[:args.limit] if args.limit else items:
        key=identity_hash(identity); current=prior.get(key)
        if current and current['state'] in {'COMMITTED','RECOVERY_COMMITTED'}: continue
        trace_path=ATTEMPT/'compact_evidence'/f'{key}.json.gz'; exact_path=ATTEMPT/'exact_sidecars'/f'{key}.json.gz'
        if trace_path.exists() and exact_path.exists():
            append(ledger,{'identity':identity,'identity_hash':key,'state':'RECOVERY_COMMITTED','attempt_ordinal':(current or identity)['attempt_ordinal']+1,'evidence_path':str(trace_path.relative_to(ATTEMPT)),'evidence_sha256':sha(trace_path),'exact_sidecar_path':str(exact_path.relative_to(ATTEMPT)),'exact_sidecar_sha256':sha(exact_path),'source_hashes':sources,'non_confirmatory':True}); continue
        append(ledger,{'identity':identity,'identity_hash':key,'state':'STARTED','attempt_ordinal':(current or identity)['attempt_ordinal']+1,'source_hashes':sources,'non_confirmatory':True})
        try:
            seed=PUBLIC_SEEDS[int(identity['development_episode_id'].rsplit('-',1)[1])]
            result=execute_full_horizon(identity,seed,evaluator,continuation_cache)
            evidence={**result.trace,'label':'DEBUG_ONLY_NOT_FOR_SCIENTIFIC_USE','non_confirmatory':True,'source_hashes':sources}
            atomic_gzip(trace_path,evidence); atomic_gzip(exact_path,{'identity_hash':key,'records':result.evaluator,'non_confirmatory':True})
            append(ledger,{'identity':identity,'identity_hash':key,'state':'COMMITTED','attempt_ordinal':(current or identity)['attempt_ordinal']+1,'evidence_path':str(trace_path.relative_to(ATTEMPT)),'evidence_sha256':sha(trace_path),'exact_sidecar_path':str(exact_path.relative_to(ATTEMPT)),'exact_sidecar_sha256':sha(exact_path),'source_hashes':sources,'non_confirmatory':True})
        except Exception as error:
            append(ledger,{'identity':identity,'identity_hash':key,'state':'FAILED_DETERMINISTIC','attempt_ordinal':(current or identity)['attempt_ordinal']+1,'failure_type':type(error).__name__,'failure_message':str(error),'source_hashes':sources,'non_confirmatory':True})
    elapsed=time.perf_counter()-started
    (ATTEMPT/'RUN_RESOURCE_SAMPLE.json').write_text(json.dumps({'wall_seconds':elapsed,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'compressed_evidence_bytes':sum(path.stat().st_size for path in ATTEMPT.rglob('*.json.gz')),'continuation_return_cache':continuation_cache.snapshot(),'exact_reference_cache':evaluator.cache_snapshot()},sort_keys=True,indent=2)+'\n')
    rows=latest(ledger); print(json.dumps({'status':'DEVELOPMENT_SHARD_COMPLETE','shard_count':args.shard_count,'shard_index':args.shard_index,'expected_shard_identities':len(items),'universe_identities':len(all_items),'committed_seen':sum(row['state'] in {'COMMITTED','RECOVERY_COMMITTED'} for row in rows.values()),'failed_seen':sum(row['state'].startswith('FAILED') for row in rows.values()),'non_confirmatory':True},sort_keys=True))
if __name__=='__main__': main()
