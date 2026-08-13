#!/usr/bin/env python3
"""Verify every P1 Qwen32 raw record and the derived outcome release."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle"
PROTOCOL=BASE/"P1_QWEN32_ORACLE_PROTOCOL.json"; RAW=BASE/"raw"; TABLE=BASE/"P1_QWEN32_UNIT_OUTCOMES.parquet"; COMPLETE=BASE/"P1_QWEN32_ORACLE_COMPLETION.json"
SCAN=ROOT/"outputs/v3_scan_proxy_preregistration_v1/frozen_tables"

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()
def ch(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def units():
 rows=[]
 for video in ("DALI","HANGZHOU","WUHAN"):
  for r in pd.read_parquet(SCAN/video/"candidate_table.parquet").sort_values("candidate_order").to_dict("records"):
   rows.append({"video_id":video,"candidate_id":r["candidate_id"],"unit_id":r["source_unit_ids"][0],"start_time":float(r["start_sec"]),"end_time":float(r["end_sec"]),"candidate_order":int(r["candidate_order"])})
 return rows
def main():
 p=json.loads(PROTOCOL.read_text())
 expected={r["unit_id"]:r for r in units()}
 errors=[]; records=[]
 for f in RAW.glob("*.json"):
  try:
   r=json.loads(f.read_text());u=expected.get(r.get("unit_id"))
   if u is None or f.stem!=r["unit_id"]:raise ValueError("unknown/misnamed unit")
   for k in ("video_id","candidate_id","start_time","end_time","candidate_order"):
    if r.get(k)!=u[k]:raise ValueError(f"identity mismatch {k}")
   if r.get("query_id")!=p["query_id"] or r.get("protocol_hash")!=p["protocol_hash"]:raise ValueError("query/protocol mismatch")
   if r.get("label") not in {"relevant","not_relevant","unknown","parse_failure"}:raise ValueError("bad label")
   if r.get("parse_status") not in {"OK","PARSE_FAILURE"}:raise ValueError("bad parse status")
   if r.get("parse_status")=="OK":
    raw=json.loads(r["raw"])
    if set(raw)!={"label","confidence","evidence"} or raw["label"]!=r["label"] or raw["confidence"]!=r["confidence"] or raw["evidence"]!=r["evidence"]:raise ValueError("raw/parsed mismatch")
   if hashlib.sha256(r.get("raw","").encode()).hexdigest()!=r.get("raw_sha256"):raise ValueError("raw hash mismatch")
   records.append(r)
  except Exception as e:errors.append({"file":f.name,"error":str(e)})
 ids={r["unit_id"] for r in records}; missing=sorted(set(expected)-ids); duplicate=len(records)-len(ids)
 complete=len(records)==1475 and not errors and not missing and duplicate==0
 report={"status":"PASS" if complete else "PARTIAL_OR_FAIL","expected_units":1475,"valid_records":len(records),"missing_units":len(missing),"duplicate_records":duplicate,"invalid_records":len(errors),"protocol_hash":p["protocol_hash"],"raw_record_set_sha256":ch(sorted((r["unit_id"],r["raw_sha256"]) for r in records)),"sample_missing_units":missing[:20],"errors":errors[:20]}
 if complete:
  if not TABLE.exists() or not COMPLETE.exists():report["status"]="FAIL_DERIVED_RELEASE_MISSING"
  else:
   c=json.loads(COMPLETE.read_text());df=pd.read_parquet(TABLE)
   report["derived_table_rows"]=len(df);report["derived_table_sha256"]=sha(TABLE);report["completion_table_sha256"]=c.get("table_sha256")
   keycols=["unit_id","video_id","candidate_id","start_time","end_time","candidate_order","query_id","label","confidence","parse_status","raw_sha256","protocol_hash"]
   rawdf=pd.DataFrame(records)[keycols].sort_values("unit_id").reset_index(drop=True);tab=df[keycols].sort_values("unit_id").reset_index(drop=True)
   report["derived_row_identity_matches_raw"]=rawdf.equals(tab)
   if not (c.get("status")=="COMPLETE" and c.get("units")==1475 and c.get("table_sha256")==sha(TABLE) and len(df)==1475 and report["derived_row_identity_matches_raw"]):report["status"]="FAIL_DERIVED_RELEASE_INVALID"
 out=BASE/"P1_QWEN32_ORACLE_VERIFICATION.json";out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
