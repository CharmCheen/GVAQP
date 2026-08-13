#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/p1_shadow_vlm_direct_reference_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 protocol=json.loads((OUT/'SHADOW_PROTOCOL.json').read_text()); cases=json.loads((OUT/'BLINDED_CASES.json').read_text()); import math
 expected=sum(math.ceil(c['duration_sec']/protocol['windowing']['stride_sec']) for c in cases)
 for a in ('VLM_A','VLM_B'):
  rows=[]
  base=OUT/f'{a}_RAW.jsonl'
  if base.exists():rows += [json.loads(x) for x in base.read_text().splitlines() if x.strip()]
  for p in sorted(OUT.glob(f'{a}_RAW_SHARD*.jsonl')):rows += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
  by={x['window_id']:x for x in rows};
  if len(by)!=expected:raise RuntimeError(f'{a} incomplete unique windows {len(by)}/{expected}')
  ordered=sorted(by.values(),key=lambda x:(x['case_id'],x['window_index']))
  base.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in ordered))
 state=json.loads((OUT/'SHADOW_STATE.json').read_text());state.update({'vlm_a_complete':True,'vlm_b_complete':True,'vlm_a_raw_sha256':sha(OUT/'VLM_A_RAW.jsonl'),'vlm_b_raw_sha256':sha(OUT/'VLM_B_RAW.jsonl'),'status':'BOTH_VLM_ANNOTATIONS_COMPLETE'});(OUT/'SHADOW_STATE.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':state['status'],'windows_per_annotator':expected}))
if __name__=='__main__':main()
