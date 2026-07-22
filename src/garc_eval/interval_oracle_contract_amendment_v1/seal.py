#!/usr/bin/env python3
import hashlib
from pathlib import Path
import pandas as pd
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'DARE_AQP_Experiment_v1').is_dir())
OUT=ROOT/'DARE_AQP_Experiment_v1/outputs/gate_c0_interval_contract_amendment_v1'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''): h.update(c)
 return h.hexdigest()
rows=[{'path':str(p.relative_to(ROOT)),'size_bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.csv']
pd.DataFrame(rows).to_csv(OUT/'FILE_MANIFEST.csv',index=False)
print(OUT/'FILE_MANIFEST.csv')
