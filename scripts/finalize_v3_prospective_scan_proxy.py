#!/usr/bin/env python3
"""Deterministically finalize prospective raw YOLO scans into public tables."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
def sha(p: Path):
 h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
def main():
 p=argparse.ArgumentParser(); p.add_argument('--protocol',required=True); p.add_argument('--video',required=True); p.add_argument('--raw-root',required=True); p.add_argument('--output-root',required=True); a=p.parse_args()
 protocol=json.loads(Path(a.protocol).read_text()); raw=Path(a.raw_root)/a.video/'raw_unit_detections.jsonl'
 rows=[json.loads(x) for x in raw.read_text().splitlines() if x]; rows.sort(key=lambda x:x['unit_id'])
 if len({x['unit_id'] for x in rows})!=len(rows): raise RuntimeError('duplicate unit IDs')
 if any(x['end_sec']<=x['start_sec'] or not all(isinstance(x[k],(int,float)) for k in ['det_count','max_conf','conf_sum']) for x in rows): raise RuntimeError('invalid raw row')
 candidates=[]; proxies=[]
 for order,x in enumerate(rows):
  cid=f"{x['video_id']}::{x['unit_id']}"
  candidates.append({'video_id':x['video_id'],'candidate_id':cid,'start_sec':x['start_sec'],'end_sec':x['end_sec'],'source_unit_ids':[x['unit_id']],'candidate_type':'frozen_v3_unit','candidate_order':order})
  score=.5*min(int(x['det_count']),20)/20.0+.5*float(x['max_conf'])
  proxies.append({'video_id':x['video_id'],'candidate_id':cid,'det_count':int(x['det_count']),'max_conf':float(x['max_conf']),'conf_sum':float(x['conf_sum']),'proxy_score':score,'protocol_hash':protocol['protocol_hash']})
 out=Path(a.output_root)/a.video; out.mkdir(parents=True,exist_ok=True)
 cp=out/'candidate_table.parquet'; pp=out/'proxy_table.parquet'; pq.write_table(pa.Table.from_pylist(candidates),cp,compression='zstd'); pq.write_table(pa.Table.from_pylist(proxies),pp,compression='zstd')
 manifest={'status':'SCAN_PROXY_FINALIZED','video_id':a.video,'protocol_hash':protocol['protocol_hash'],'raw_sha256':sha(raw),'candidate_table_sha256':sha(cp),'proxy_table_sha256':sha(pp),'candidate_rows':len(candidates),'proxy_rows':len(proxies),'completeness_pass':True}
 (out/'SCAN_MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n'); print(json.dumps(manifest,sort_keys=True))
if __name__=='__main__': main()
