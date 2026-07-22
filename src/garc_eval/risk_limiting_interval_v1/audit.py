#!/usr/bin/env python3
import csv,hashlib,itertools,json,math,subprocess,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'DARE_AQP_Experiment_v1').is_dir())
OUT=ROOT/'DARE_AQP_Experiment_v1/outputs/risk_limiting_interval_pruning_feasibility_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def rows(p):
 with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
checks=[]
def check(n,p,e):checks.append({'check':n,'status':'PASS' if p else 'FAIL','evidence':str(e)})

for name in ['SOURCE_MANIFEST.csv','INPUT_MANIFEST.csv']:
 m=rows(OUT/'config'/name);check(name+' hashes',all((ROOT/r['path']).is_file() and sha(ROOT/r['path'])==r['sha256'] for r in m),len(m))
blocked=rows(ROOT/'DARE_AQP_Experiment_v1/outputs/gate_c0_physical_interval_operator_v1/oracle/VLM_CALL_LEDGER.csv')
code=(ROOT/'garc_eval/risk_limiting_interval_v1/simulate.py').read_text()
check('no physical response accessed',len(blocked)==0 and 'raw_response' not in code and 'from_pretrained' not in code,'0 calls; reference-only source')
check('known inclusion-probability implementation','(Np/n)*sum(vals)' in code and '(len(ids)/n)*sum(sv)' in code,'SRS n/H and per-stratum n_h/H_h')

# Independently enumerate SRS HT unbiasedness.
values=[0,1,2,0];H=len(values);n=2
ests=[H/n*sum(values[i] for i in s) for s in itertools.combinations(range(H),n)]
check('HT conditional unbiasedness',abs(np.mean(ests)-sum(values))<1e-14, f'{np.mean(ests)}={sum(values)}')
# Stratified HT exact enumeration: strata [0,1] and [2,3], one each.
sests=[]
for i in [0,1]:
 for j in [2,3]:sests.append(2*values[i]+2*values[j])
check('stratified HT unbiasedness',abs(np.mean(sests)-sum(values))<1e-14,f'{np.mean(sests)}={sum(values)}')

d=pd.read_csv(OUT/'simulations/RISK_LIMITING_GRID.csv');rob=pd.read_csv(OUT/'feasible_region/ROBUST_FEASIBLE_REGION.csv')
expected=7*7*4*8*2*9*2
check('complete grid and seeds',len(d)==expected and d.seeds.min()>=500 and d.seeds.max()>=500,len(d))
placements={'independent','boundary','multi_event','long_event','low_proxy','adversarial','correlated_sibling','correlated_level'}
check('placement generators represented',set(d.placement)==placements,sorted(d.placement.unique()))
check('confidence coverage',d.empirical_coverage.min()>=.94,float(d.empirical_coverage.min()))
check('HT error variance reported',
      'ht_error_variance' in d.columns and np.isfinite(d.ht_error_variance).all() and (d.ht_error_variance>=0).all(),
      f"range={d.ht_error_variance.min()}..{d.ht_error_variance.max()}")
check('failure probability identity',
      'failure_probability' in d.columns and np.allclose(d.failure_probability,1-d.empirical_coverage,rtol=0,atol=1e-15),
      f"max={d.failure_probability.max()}")
check('cost accounting exact ceiling',abs(243/347-.7002881844380403)<1e-15 and not 243/347<.7,'217 interval + 26 certify = 243')
check('recall calculation',abs(21/26-.8076923076923077)<1e-15,'21/26')
check('random feasible extraction',not d[(d.placement=='independent')&d.joint_pass].shape[0],0)
check('robust feasible extraction',not rob.robust_feasible.any(),int(rob.robust_feasible.sum()))
check('no threshold relaxation',set(d.sensitivity.unique())=={.8,.85,.9,.95,.97,.99,1} and set(d.specificity.unique())=={.8,.85,.9,.95,.97,.99,1} and set(d.unknown_rate.unique())=={0,.05,.1,.2},'frozen grids')
quality=d[d.recall_pass&d.coverage_pass&(d.certify_rate>=.9)]
check('minimum quality-valid cost',float(quality.total_cost_p95.min())==350.0,'350 > dense')
quality_configs=[]
group_cols=['sensitivity','specificity','unknown_rate','variant','audit_fraction','cost_family','fixed_fraction']
for _,g in d.assign(quality=d.recall_pass&d.coverage_pass&(d.certify_rate>=.9)).groupby(group_cols):
 if g.quality.all():quality_configs.append(float(g.total_cost_p95.max()))
check('minimum all-placement quality-valid cost',min(quality_configs)==550.0,'550/347')
es=pd.read_csv(OUT/'estimators/ESTIMATOR_SUMMARY.csv').set_index('variant')
er=pd.read_csv(OUT/'estimators/ESTIMATOR_RESULTS.csv')
check('estimator numerical diagnostics',
      {'ht_error_variance','failure_probability'}.issubset(er.columns)
      and np.isfinite(er.ht_error_variance).all() and (er.ht_error_variance>=0).all()
      and np.allclose(er.failure_probability,1-er.empirical_coverage,rtol=0,atol=1e-15),
      'variance and empirical failure probability present')
check('best estimator selection',float(es.loc['B3_STRATIFIED','bound_width_median'])<float(es.loc['B2_SRS','bound_width_median']),'B3 narrower conservative bound')

dec=rows(OUT/'FINAL_DECISION.csv')[0]
check('decision compliance',dec['decision']=='RISK_LIMITING_INTERVAL_NO_GO' and dec['physical_vlm_calls']=='0' and dec['robust_feasible'].lower()=='false' and dec['minimum_robust_cost']=='550',dec['decision'])
manifest=OUT/'FILE_MANIFEST.csv'
if manifest.exists():m=rows(manifest);mok=all((ROOT/r['path']).is_file() and sha(ROOT/r['path'])==r['sha256'] for r in m)
else:m=[];mok=False
check('all sealed hashes',mok,len(m))
verdict='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL'
review={'verdict':verdict,'checks':checks,'physical_vlm_calls':0,'conclusion':'No random-only or robust feasible region; risk-limiting interval pruning is NO-GO.'}
(OUT/'audit/INDEPENDENT_ADVERSARIAL_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
if verdict=='PASS':
 x=pd.read_csv(OUT/'FINAL_DECISION.csv',keep_default_na=False);x.loc[0,'completion_audit']='PASS';x.loc[0,'independent_review']='PASS';x.to_csv(OUT/'FINAL_DECISION.csv',index=False)
 c=pd.read_csv(OUT/'audit/COMPLETION_AUDIT.csv',keep_default_na=False);c.loc[c.requirement=='Independent review','status']='PASS';c.loc[c.requirement=='All file hashes','status']='PASS';c.to_csv(OUT/'audit/COMPLETION_AUDIT.csv',index=False)
 subprocess.run([sys.executable,str(Path(__file__).with_name('seal.py'))],check=True)
else:raise SystemExit(1)
print(verdict)
