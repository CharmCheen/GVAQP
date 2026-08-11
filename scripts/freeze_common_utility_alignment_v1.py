#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,platform,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy,pandas,yaml
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/scan_confirm_common_utility_v1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix(p.suffix+'.tmp')
 with q.open('w',encoding='utf-8') as f: json.dump(x,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
 os.replace(q,p)
def main():
 assets=[ROOT/'docs/SCAN_CONFIRM_COMMON_UTILITY_ALIGNMENT_CONTRACT_V1.md',ROOT/'outputs/scan_confirm_decision_v1/reports/FINAL_DECISION.md',ROOT/'outputs/scan_confirm_decision_v1/fixed_ratio_baselines/selected_controller.json',ROOT/'outputs/scan_confirm_decision_v1/contracts/freeze_manifest.json',ROOT/'configs/safe_coverage_scan.yaml',ROOT/'outputs/psvr_two_video_loop/dev_benchmark_v1/TASK_MANIFEST.json',ROOT/'outputs/psvr_two_video_loop/final_proxy/FINAL_PROXY_CONFIG.json',ROOT/'outputs/psvr_two_video_loop/state/FRONTIER_CAPACITY_FREEZE.json']+sorted((ROOT/'src/garc_eval/scan_confirm_controller').glob('*.py'))+[ROOT/'scripts/run_common_utility_alignment_v1.py',ROOT/'scripts/freeze_common_utility_alignment_v1.py']
 hashes={str(p.relative_to(ROOT)):sha(p) for p in assets}; contract=ROOT/'docs/SCAN_CONFIRM_COMMON_UTILITY_ALIGNMENT_CONTRACT_V1.md'
 git=['git',f'--git-dir={ROOT/".git"}',f'--work-tree={ROOT}']; commit=subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip()
 env={'created_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'numpy':numpy.__version__,'pandas':pandas.__version__,'pyyaml':yaml.__version__,'new_oracle_calls':0}
 write(OUT/'environment_lock.json',env); write(OUT/'code_version.json',{'code_commit':commit,'worktree_dirty':bool(subprocess.check_output(git+['status','--porcelain'],text=True).strip())})
 manifest={'status':'FROZEN_BEFORE_STATIC_ALIGNMENT_AUDIT','created_utc':env['created_utc'],'contract_hash':sha(contract),'code_commit':commit,'asset_manifest_hash':canon(hashes),'environment_lock_hash':sha(OUT/'environment_lock.json'),'parent_decision_hash':sha(ROOT/'outputs/scan_confirm_decision_v1/reports/FINAL_DECISION.md'),'selected_controller_hash':sha(ROOT/'outputs/scan_confirm_decision_v1/fixed_ratio_baselines/selected_controller.json'),'common_utility_code_hash':canon({k:v for k,v in hashes.items() if 'common_utility' in k}),'frontier_contract_hash':json.loads((ROOT/'outputs/scan_confirm_decision_v1/contracts/freeze_manifest.json').read_text())['frontier_contract_hash'],'assets':hashes}
 write(OUT/'contracts/freeze_manifest.json',manifest); write(OUT/'repair_log.json',{'max_repair_cycles':1,'repairs':[]})
 fields=['remaining_budget_sec','coverage_fraction','maximum_unobserved_gap_sec','scan_actions_completed','scan_time_spent_sec','frontier_size','frontier_score_min','frontier_score_median','frontier_score_max','frontier_score_quantiles','frontier_score_bucket_counts','oldest_candidate_age_sec','newest_candidate_age_sec','novel_candidate_clusters_observed','confirmed_distinct_utility_count','recent_scan_novel_yield','recent_scan_zero_yield_streak','recent_confirm_success_rate','recent_confirm_new_utility_rate','recent_confirm_zero_yield_streak','estimated_scan_cost_sec','estimated_confirm_cost_sec','actions_completed','unused_budget_sec']
 write(OUT/'contracts/public_state_schema.json',{'title':'COMMON_UTILITY_PUBLIC_STATE_V1','additionalProperties':False,'required':fields,'forbidden':['video_id','group_id','filename','reference_events','future_candidates','future_outcomes','future_costs','offline_oracle_order','held_out_result'],'new_aggregate_field':{'frontier_score_bucket_counts':{'LOW':'integer','MEDIUM':'integer','HIGH':'integer'}}})
 write(OUT/'contracts/deadline_bound.json',{'method':'Q0.99_PLUS_SAFETY','safety_delta':'max(0.25, observed_max-Q0.99+0.25)','effective_replay_bound':'observed_development_max_plus_0.25_sec','physical_claim':'NOT_AUTHORIZED_WITHOUT_SPLIT_CONFORMAL_CALIBRATION'})
 write(OUT/'contracts/r4_freeze.json',{'controller':'R4_RATIO_25_75','scan_time_share':.25,'confirm_time_share':.75,'ratio_basis':'cumulative_realized_complete_action_time','status':'PRODUCTION_DEFAULT_AND_STRONG_BASELINE'})
 print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
