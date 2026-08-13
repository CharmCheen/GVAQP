#!/usr/bin/env python3
"""Read-only cluster-level P2 statistics over frozen P2 replay outputs."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/p2_query_policy_novelty_killer_v1'
PAIR=OUT/'PAIRWISE_POLICY_EFFECTS.csv'; ANY=OUT/'ANYTIME_METRICS.csv'; PROTOCOL=OUT/'P2_PROTOCOL.json'

def sha(p:Path)->str:
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def main():
 for p in (PAIR,ANY,PROTOCOL):
  if not p.exists():raise RuntimeError(f'missing frozen P2 input: {p}')
 pair=pd.read_csv(PAIR); anym=pd.read_csv(ANY)
 # P2's preregistered canonical final-b100 comparison; proxy cells collapse to
 # medians within a video-query before resampling.
 final=pair[pair.budget==100].groupby(['video_id','query_id'],sort=True).agg(delta_F1=('Delta_F1_Generic_minus_Static','median'),delta_EventRecall=('Delta_EventRecall_Generic_minus_Static','median')).reset_index()
 a=anym.pivot(index=['video_id','query_id','proxy_family'],columns='policy',values='AnytimeAUC_F1').reset_index(); a['delta_AnytimeAUC']=a.ProxyTemporalCoverage_L050-a.StaticProxyRank
 auc=a.groupby(['video_id','query_id'],sort=True).delta_AnytimeAUC.median().reset_index()
 x=final.merge(auc,on=['video_id','query_id'],validate='one_to_one')
 if len(x)!=6:raise RuntimeError('expected six video-query clusters')
 rng=np.random.default_rng(20260813); rec=[]
 for r in range(10_000):
  draw=x.iloc[rng.integers(0,len(x),len(x))]
  for metric in ('delta_F1','delta_EventRecall','delta_AnytimeAUC'):rec.append({'replicate':r,'metric':metric,'median':float(draw[metric].median()),'mean':float(draw[metric].mean())})
 boot=pd.DataFrame(rec);boot.to_csv(OUT/'CLUSTER_BOOTSTRAP.csv',index=False)
 summary={}
 for metric,g in boot.groupby('metric',sort=True):
  threshold=.01 if metric=='delta_AnytimeAUC' else .02
  summary[metric]={'observed_median':float(x[metric].median()),'ci95_median':[float(z) for z in np.quantile(g['median'],[.025,.975])],'bootstrap_probability_median_ge_practical_threshold':float((g['median']>=threshold).mean())}
 rows=[]
 for v in sorted(x.video_id.unique()):
  z=x[x.video_id!=v];rows.append({'split':'LOVO','heldout':v,**{f'median_{c}':float(z[c].median()) for c in ('delta_F1','delta_EventRecall','delta_AnytimeAUC')}})
 for r in x.itertuples():
  z=x[~((x.video_id==r.video_id)&(x.query_id==r.query_id))];rows.append({'split':'LOVQ','heldout':f'{r.video_id}::{r.query_id}',**{f'median_{c}':float(z[c].median()) for c in ('delta_F1','delta_EventRecall','delta_AnytimeAUC')}})
 leave=pd.DataFrame(rows);leave.to_csv(OUT/'CLUSTER_LEAVEOUT.csv',index=False)
 binding={'status':'COMPLETE_READ_ONLY_CLUSTER_STATISTICS','protocol_hash':json.loads(PROTOCOL.read_text())['protocol_hash'],'input_hashes':{PAIR.name:sha(PAIR),ANY.name:sha(ANY)},'code_sha256':sha(Path(__file__)),'cluster_count':len(x),'bootstrap_resamples':10000,'seed':20260813,'summary':summary}
 (OUT/'CLUSTER_STATISTICS_MANIFEST.json').write_text(json.dumps(binding,indent=2,sort_keys=True)+'\n')
 (OUT/'CLUSTER_STATISTICAL_ANALYSIS.md').write_text('# Cluster statistical analysis\n\nThe video-query cluster is the statistical unit. Proxy cells are median-collapsed within each cluster before the 10,000-replicate bootstrap and leave-out analyses. No budget cells, traces, or proxy rows are resampled independently. This is a read-only analysis of P2 cached replay outputs.\n\n```json\n'+json.dumps(summary,indent=2,sort_keys=True)+'\n```\n')
 print(json.dumps({'status':binding['status'],'clusters':len(x),'summary':summary},sort_keys=True))
if __name__=='__main__':main()
