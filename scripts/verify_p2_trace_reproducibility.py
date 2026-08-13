#!/usr/bin/env python3
"""Independent deterministic-order reconstruction for P2 legal traces."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_p2_query_policy_novelty_killer as p2

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/p2_query_policy_novelty_killer_v1'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
 p2.load_protocol(); recorded=pd.read_csv(OUT/'TRACE_MANIFEST.csv'); candidates=p2.candidates(); labels=p2.labels_by_query();
 orderers={'UniformTemporal':lambda f:p2.dyadic_order(f),'StaticProxyRank':lambda f:sorted(range(len(f)),key=lambda i:(-float(f.iloc[i].proxy_score),int(f.iloc[i].candidate_order),str(f.iloc[i].candidate_id))),'CoverageFirst':lambda f:p2.farthest_order(f),'ProxyTemporalCoverage_L025':lambda f:p2.proxy_coverage_order(f,.25),'ProxyTemporalCoverage_L050':lambda f:p2.proxy_coverage_order(f,.5),'ProxyTemporalCoverage_L075':lambda f:p2.proxy_coverage_order(f,.75)}
 rows=[]
 for r in recorded[recorded.legal_policy].itertuples():
  frame=candidates[(r.video_id,r.proxy_family)]; ids=frame.iloc[orderers[r.policy](frame)[:r.budget]].unit_id.astype(str).tolist(); h=digest({'policy':r.policy,'video':r.video_id,'query':r.query_id,'proxy':r.proxy_family,'ids':ids}); rows.append({'video_id':r.video_id,'query_id':r.query_id,'proxy_family':r.proxy_family,'policy':r.policy,'budget':r.budget,'recorded_trace_hash':r.trace_hash,'reconstructed_trace_hash':h,'hash_identical':h==r.trace_hash})
 result=pd.DataFrame(rows);result.to_csv(OUT/'TRACE_REPRODUCIBILITY.csv',index=False)
 if not result.hash_identical.all():raise RuntimeError('P2 trace reconstruction mismatch')
 print(json.dumps({'status':'PASS','trace_rows':len(result),'hash_identical':bool(result.hash_identical.all())},sort_keys=True))
if __name__=='__main__':main()
