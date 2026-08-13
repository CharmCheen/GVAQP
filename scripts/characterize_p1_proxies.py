#!/usr/bin/env python3
"""Post-freeze characterization of the two P1 natural cheap proxies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/gvaqp_long_horizon_p1_p3_v1"
QWEN=OUT/"qwen32_oracle"; QT=QWEN/"P1_QWEN32_UNIT_OUTCOMES.parquet"; QC=QWEN/"P1_QWEN32_ORACLE_COMPLETION.json"
V10=ROOT/"outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet"
PB=OUT/"proxy_b_kinematic/PROXY_B_KINEMATIC_SCORES.parquet"
SCAN=ROOT/"outputs/v3_scan_proxy_preregistration_v1/frozen_tables"
PROTOCOL=OUT/"P1_PROXY_CHARACTERIZATION_PROTOCOL.json"

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()
def freeze():
 if PROTOCOL.exists():raise RuntimeError("proxy-characterization protocol already frozen")
 p={"protocol_id":"P1_TWO_NATURAL_PROXY_CHARACTERIZATION_V1","status":"FROZEN_BEFORE_SECOND_QUERY_PROXY_CHARACTERIZATION","queries":{"Q_DRIVER_RESPONSE_V1":"released V10 Qwen32 unit outcomes","Q_VULNERABLE_ROAD_USER_CONFLICT_V1":"P1 frozen Qwen32 full-grid unit outcomes"},"proxies":{"Proxy_A":"released YOLOv8n object/motion score","Proxy_B":"frozen optical-flow/visual-dynamics score"},"metrics":["AUPRC","Recall@5","Recall@10","Recall@20","Recall@50","Recall@80","Recall@100","Spearman proxy-score vs binary outcome","per-video score distribution","Proxy A-vs-B rank Spearman"],"rules":{"positive":"label == relevant","unknown_and_parse_failure":"retained as non-positive for descriptive ranking characterization and counted/reported separately","no_tuning":"metrics are characterization only; no model, threshold, trace, or human-reference change is permitted"},"inputs":{"proxy_b_sha256":sha(PB),"original_outcomes_sha256":sha(V10),"second_query_protocol_sha256":sha(QWEN/"P1_QWEN32_ORACLE_PROTOCOL.json")},"code":{"path":str(Path(__file__).relative_to(ROOT)),"sha256":sha(Path(__file__))}}
 p["protocol_hash"]=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(",",":")).encode()).hexdigest();PROTOCOL.write_text(json.dumps(p,indent=2,sort_keys=True)+"\n");print(json.dumps({"status":"FROZEN","protocol_hash":p["protocol_hash"]},sort_keys=True))
def a_scores():
 frames=[]
 for v in ("DALI","HANGZHOU","WUHAN"):
  a=pd.read_parquet(SCAN/v/"proxy_table.parquet")[["video_id","candidate_id","proxy_score"]].rename(columns={"proxy_score":"proxy_a_score"})
  c=pd.read_parquet(SCAN/v/"candidate_table.parquet")[["video_id","candidate_id","source_unit_ids"]];c["unit_id"]=c.source_unit_ids.map(lambda x:x[0]);frames.append(a.merge(c[["video_id","candidate_id","unit_id"]],on=["video_id","candidate_id"],validate="one_to_one"))
 return pd.concat(frames,ignore_index=True)
def outcomes():
 old=pd.read_parquet(V10)[["video_id","unit_id","authoritative_label"]].rename(columns={"authoritative_label":"label"});old["query_id"]="Q_DRIVER_RESPONSE_V1"
 if not QT.exists() or not QC.exists():raise RuntimeError("P1 Qwen32 second-query release unavailable")
 c=json.loads(QC.read_text())
 if c.get("status")!="COMPLETE" or c.get("units")!=1475 or c.get("table_sha256")!=sha(QT):raise RuntimeError("P1 Qwen32 release incomplete/invalid")
 new=pd.read_parquet(QT)[["video_id","unit_id","label"]];new["query_id"]="Q_VULNERABLE_ROAD_USER_CONFLICT_V1"
 return pd.concat([old,new],ignore_index=True)
def run():
 p=json.loads(PROTOCOL.read_text());
 if p["protocol_hash"]!=hashlib.sha256(json.dumps({k:v for k,v in p.items() if k!="protocol_hash"},sort_keys=True,separators=(",",":")).encode()).hexdigest():raise RuntimeError("characterization protocol hash mismatch")
 a=a_scores();b=pd.read_parquet(PB)[["video_id","unit_id","proxy_score"]].rename(columns={"proxy_score":"proxy_b_score"});x=a.merge(b,on=["video_id","unit_id"],validate="one_to_one").merge(outcomes(),on=["video_id","unit_id"],validate="one_to_many");x["positive"]=(x.label=="relevant").astype(int)
 rows=[];dist=[]
 for (q,v),g in x.groupby(["query_id","video_id"]):
  for name,col in (("Proxy A YOLOv8n object/motion","proxy_a_score"),("Proxy B optical-flow visual dynamics","proxy_b_score")):
   if g.positive.sum()==0:ap=float("nan")
   else:ap=float(average_precision_score(g.positive,g[col]))
   rho=float(spearmanr(g[col],g.positive).statistic) if g[col].nunique()>1 else float("nan")
   rows.append({"query_id":q,"video_id":v,"proxy_family":name,"metric":"AUPRC","value":ap,"positive_units":int(g.positive.sum()),"unknown_or_parse_units":int(g.label.isin(["unknown","parse_failure"]).sum()),"label_rank_spearman":rho})
   for k in (5,10,20,50,80,100):rows.append({"query_id":q,"video_id":v,"proxy_family":name,"metric":f"Recall@{k}","value":float(g.nlargest(k,col).positive.sum()/g.positive.sum()) if g.positive.sum() else float("nan"),"positive_units":int(g.positive.sum()),"unknown_or_parse_units":int(g.label.isin(["unknown","parse_failure"]).sum()),"label_rank_spearman":rho})
   dist.append({"query_id":q,"video_id":v,"proxy_family":name,"n":len(g),"score_min":float(g[col].min()),"score_q25":float(g[col].quantile(.25)),"score_median":float(g[col].median()),"score_q75":float(g[col].quantile(.75)),"score_max":float(g[col].max()),"score_mean":float(g[col].mean()),"score_std":float(g[col].std())})
  rows.append({"query_id":q,"video_id":v,"proxy_family":"Proxy A vs Proxy B","metric":"Rank Spearman","value":float(spearmanr(g.proxy_a_score,g.proxy_b_score).statistic),"positive_units":int(g.positive.sum()),"unknown_or_parse_units":int(g.label.isin(["unknown","parse_failure"]).sum()),"label_rank_spearman":float("nan")})
 pd.DataFrame(rows).to_csv(OUT/"P1_PROXY_CHARACTERIZATION.csv",index=False);pd.DataFrame(dist).to_csv(OUT/"P1_PROXY_SCORE_DISTRIBUTIONS.csv",index=False)
 report="# P1 two-natural-proxy characterization\n\nThis post-freeze descriptive audit reports AUPRC, Recall@K, score/label rank correlation, score distributions, and cross-proxy rank correlation for both frozen query outcomes. It does not tune either proxy or select traces.\n\n"+pd.DataFrame(rows).query("metric == 'AUPRC'").to_markdown(index=False)+"\n"
 (OUT/"P1_PROXY_CHARACTERIZATION_REPORT.md").write_text(report)
 print(json.dumps({"status":"COMPLETE","rows":len(rows),"output":str(OUT)},sort_keys=True))
if __name__=="__main__":
 import argparse
 z=argparse.ArgumentParser();z.add_argument("command",choices=("freeze","run"));a=z.parse_args();freeze() if a.command=="freeze" else run()
