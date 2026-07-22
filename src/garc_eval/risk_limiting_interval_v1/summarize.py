#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'DARE_AQP_Experiment_v1').is_dir())
OUT=ROOT/'DARE_AQP_Experiment_v1/outputs/risk_limiting_interval_pruning_feasibility_v1'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
sources=[
'DARE_AQP_Experiment_v1/docs/GATE_B_PROTOCOL.md','DARE_AQP_Experiment_v1/scripts/run_gate_b.py','DARE_AQP_Experiment_v1/src/dare_aqp/audit.py',
'DARE_AQP_Experiment_v1/outputs/gate_b/REPORT.md','DARE_AQP_Experiment_v1/outputs/gate_a_final/FINAL_DECISION.json',
'DARE_AQP_Experiment_v1/outputs/gate_a_final/REPORT.md','DARE_AQP_Experiment_v1/config/gate_c0.json',
'DARE_AQP_Experiment_v1/docs/INTERVAL_ORACLE_CONTRACT.md','DARE_AQP_Experiment_v1/src/dare_aqp/interval_ceiling.py',
'DARE_AQP_Experiment_v1/outputs/gate_c0/break_even.csv','DARE_AQP_Experiment_v1/outputs/gate_c0/cost_curves.csv',
'DARE_AQP_Experiment_v1/outputs/gate_c0/query_traces.csv','DARE_AQP_Experiment_v1/outputs/gate_c0_interval_contract_amendment_v1/derivation/ANY_ERROR_INJECTION_GRID.csv',
'DARE_AQP_Experiment_v1/outputs/gate_c0_interval_contract_amendment_v1/contract/C0_PHYSICAL_INTERVAL_OPERATOR_CONTRACT_v2.json',
'DARE_AQP_Experiment_v1/outputs/gate_c0_interval_contract_amendment_v1/power/SAMPLE_SIZE_DERIVATION.md',
'garc_eval/risk_limiting_interval_v1/simulate.py']
inputs=['data/realcam/long_video_data/long_video_dataset3.mp4',
'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv',
'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/event_reference.csv',
'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/benchmark/adapter_units.csv']
(OUT/'config').mkdir(parents=True,exist_ok=True)
pd.DataFrame([{'path':p,'sha256':sha(ROOT/p)} for p in sources]).to_csv(OUT/'config/SOURCE_MANIFEST.csv',index=False)
pd.DataFrame([{'path':p,'sha256':sha(ROOT/p)} for p in inputs]).to_csv(OUT/'config/INPUT_MANIFEST.csv',index=False)
d=pd.read_csv(OUT/'simulations/RISK_LIMITING_GRID.csv')
# Hard-pruning diagnostic is the zero-audit execution; no statistical certificate.
b1=d[(d.variant=='B2_SRS')&(d.audit_fraction==0)].drop_duplicates(['sensitivity','specificity','unknown_rate','placement','cost_family'])
b1.to_csv(OUT/'simulations/B1_HARD_PRUNING_DIAGNOSTIC.csv',index=False)
random=d[(d.placement=='independent')&d.joint_pass]
random.to_csv(OUT/'feasible_region/RANDOM_ONLY_FEASIBLE_REGION.csv',index=False)
costdom=d[d.recall_pass&d.coverage_pass&(d.certify_rate>=.9)&~d.cost_pass]
confd=d[d.cost_pass&d.recall_pass&d.coverage_pass&(d.certify_rate<.9)]
costdom.to_csv(OUT/'feasible_region/COST_DOMINANT_FAILURE_REGION.csv',index=False)
confd.to_csv(OUT/'feasible_region/CONFIDENCE_DOMINANT_FAILURE_REGION.csv',index=False)
summary=d.groupby('variant').agg(ht_bias_abs_median=('ht_bias_mean',lambda x:x.abs().median()),
 ht_bias_abs_max_positive_audit=('ht_bias_mean',lambda x:x[d.loc[x.index,'audit_fraction']>0].abs().max()),
 ht_error_variance_median=('ht_error_variance','median'),ht_error_variance_max=('ht_error_variance','max'),
 empirical_coverage_min=('empirical_coverage','min'),bound_width_median=('bound_width_mean','median'),
 failure_probability_max=('failure_probability','max'),certify_rate_max=('certify_rate','max')).reset_index()
summary.to_csv(OUT/'estimators/ESTIMATOR_SUMMARY.csv',index=False)
pd.DataFrame([{'fact':'B5 exact ANY constant cost','value':243,'dense_ratio':243/347,'passes':False},
 {'fact':'joint passing cells','value':int(d.joint_pass.sum()),'dense_ratio':'','passes':False},
 {'fact':'random-only passing cells','value':len(random),'dense_ratio':'','passes':False},
 {'fact':'robust passing configurations','value':int(pd.read_csv(OUT/'feasible_region/ROBUST_FEASIBLE_REGION.csv').robust_feasible.sum()),'dense_ratio':'','passes':False},
 {'fact':'minimum empirical coverage','value':float(d.empirical_coverage.min()),'dense_ratio':'','passes':True}]).to_csv(OUT/'diagnostics/DECISION_FACTS.csv',index=False)
manifest={'experiment_id':'risk_limiting_interval_pruning_feasibility_v1','status':'RISK_LIMITING_INTERVAL_NO_GO',
 'physical_vlm_calls':0,'random_seeds_per_stochastic_cell':500,'grid_rows':len(d),'joint_passing_cells':int(d.joint_pass.sum()),
 'robust_feasible':False,'event_recall_target':.8,'confidence_target':.95,'maximum_dense_ratio':.7}
(OUT/'EXPERIMENT_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
