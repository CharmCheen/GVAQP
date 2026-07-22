#!/usr/bin/env python3
"""Independent IC1 verifier: checks persisted compact evidence only.

It intentionally never invokes the production executor, paired model, exact
reference evaluator, or planner aggregation path.  The independent verifier
recomputes each stored transition commitment and every paired statistic from
the compact evidence itself.
"""
from __future__ import annotations
import gzip, hashlib, json
import argparse
from pathlib import Path
from garc_eval.psvr_rollout_h1b.independent_verifier import verify_episode_evidence
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/psvr_rollout_r2b_ic1'
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path:Path)->dict:
    with gzip.open(path,'rt',encoding='utf-8') as handle:return json.load(handle)
def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument('--shard-count',type=int,default=1); parser.add_argument('--shard-index',type=int,default=0); parser.add_argument('--attempt',default='development_attempt_v9'); args=parser.parse_args()
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count: raise SystemExit('invalid deterministic shard')
    attempt=OUT/args.attempt
    ledger=attempt/'DEVELOPMENT_ATTEMPT_LEDGER.jsonl'; latest={}
    errors=[]; recomputed=0; agreement=[]; regrets=[]
    if not ledger.exists(): errors.append('missing-ledger')
    else:
        for line in ledger.read_text().splitlines():
            row=json.loads(line); latest[row['identity_hash']]=row
    for key,row in sorted(latest.items()):
        if int(key,16) % args.shard_count != args.shard_index: continue
        if row['state'] not in {'COMMITTED','RECOVERY_COMMITTED'}: errors.append(f'nonterminal:{key}'); continue
        evidence_path=attempt/row['evidence_path']; sidecar_path=attempt/row['exact_sidecar_path']
        if not evidence_path.exists() or sha(evidence_path)!=row['evidence_sha256']: errors.append(f'evidence-hash:{key}'); continue
        if not sidecar_path.exists() or sha(sidecar_path)!=row['exact_sidecar_sha256']: errors.append(f'sidecar-hash:{key}'); continue
        evidence, sidecar=load(evidence_path),load(sidecar_path)
        identity=row['identity']
        canonical_identity_hash=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if canonical_identity_hash!=key or evidence.get('identity_hash')!=key: errors.append(f'identity:{key}'); continue
        committed_payload={k:v for k,v in evidence.items() if k not in {'raw_evidence_commitment','label','non_confirmatory','source_hashes'}}
        if evidence.get('raw_evidence_commitment') != hashlib.sha256(json.dumps(committed_payload,sort_keys=True,separators=(',',':')).encode()).hexdigest(): errors.append(f'commitment:{key}')
        recomputed+=1
        report=verify_episode_evidence(evidence)
        if not evidence.get('decisions'):
            errors.append(f'missing-lossless-evidence:{key}')
        errors.extend(f'replay-mismatch:{key}:{error}' for error in report['errors'])
        # The exact sidecar is evaluator output, not verifier truth.  Its
        # independent check is structural: every execution decision has one
        # matching evaluator record and no planner data is imported to create it.
        if len(sidecar.get('records',[])) != len(evidence.get('decisions',[])):
            errors.append(f'exact-sidecar-cardinality:{key}')
        for record in sidecar.get('records',[]):
            selected=record['approximate_selected_action']; exact=record['exact_action']; values=record['exact_q']; agreement.append(selected==exact); regrets.append(values[exact]-values.get(selected,values[exact]))
    report={'status':'PASS' if not errors else 'FAIL','shard_count':args.shard_count,'shard_index':args.shard_index,'independent_replays':recomputed,'error_count':len(errors),'errors':errors,'full_horizon_verified':not any(error.startswith('replay-mismatch') for error in errors),'exact_evaluator_verified':not any('exact-sidecar' in error for error in errors),'action_agreement_count':sum(agreement),'action_agreement_total':len(agreement),'paired_regret_sum':sum(regrets),'paired_regret_count':len(regrets),'compact_evidence_only':True,'non_confirmatory':True,'production_execution_imported':False}
    destination=OUT/('IC1_DEVELOPMENT_INDEPENDENT_VERIFICATION.json' if args.shard_count==1 else f'IC1_DEVELOPMENT_INDEPENDENT_VERIFICATION_SHARD_{args.shard_index}.json')
    destination.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n'); print(json.dumps(report,sort_keys=True)); raise SystemExit(bool(errors))
if __name__=='__main__':main()
