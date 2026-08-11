#!/usr/bin/env python3
"""Post-release QA for frozen scan tables; never opens semantic artifacts."""
from __future__ import annotations
import json, math
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/v3_scan_proxy_preregistration_v1'
def main():
 p=json.loads((OUT/'FROZEN_V3_SCAN_PROXY_PROTOCOL.json').read_text()); out=[]
 for vid,n in [('DALI',567),('HANGZHOU',561),('WUHAN',347)]:
  d=OUT/'frozen_tables'/vid;c=pq.read_table(d/'candidate_table.parquet').to_pylist();q=pq.read_table(d/'proxy_table.parquet').to_pylist()
  assert len(c)==len(q)==n; assert len({x['candidate_id'] for x in c})==n==len({x['candidate_id'] for x in q})
  assert all(x['start_sec']<x['end_sec'] and x['candidate_id']==f"{vid}::{x['source_unit_ids'][0]}" for x in c)
  assert all(x['protocol_hash']==p['protocol_hash'] and all(math.isfinite(float(x[k])) for k in ['max_conf','conf_sum','proxy_score']) and int(x['det_count'])>=0 for x in q)
  out.append({'video_id':vid,'candidate_rows':len(c),'proxy_rows':len(q),'unique_ids':n,'finite_proxy_values':True,'protocol_hash_match':True,'status':'PASS'})
 result={'status':'PASS_NO_SEMANTIC_INPUT','protocol_hash':p['protocol_hash'],'videos':out};(OUT/'SCAN_POST_RELEASE_QA.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
