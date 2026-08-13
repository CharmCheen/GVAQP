#!/usr/bin/env python3
"""Frozen cheap Proxy B: unit-local optical-flow / visual-change score.

Unlike Proxy A's COCO object detections from one midpoint, this proxy measures
short-window camera/scene dynamics at four samples per released unit. It reads
no query outcome, reference, human label, or P1 method result.
"""
from __future__ import annotations

import argparse, hashlib, json, os
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"outputs/gvaqp_long_horizon_p1_p3_v1/proxy_b_kinematic"
PROTOCOL=BASE/"PROXY_B_PROTOCOL.json"; TABLE=BASE/"PROXY_B_KINEMATIC_SCORES.parquet"
VIDEOS={"DALI":ROOT/"data/realcam/dali.mp4","HANGZHOU":ROOT/"data/realcam/hangzhou.mp4","WUHAN":ROOT/"data/realcam/wuhan.mp4"}
SCAN=ROOT/"outputs/v3_scan_proxy_preregistration_v1/frozen_tables"

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1<<20),b""):h.update(x)
 return h.hexdigest()
def ch(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def units():
 out=[]
 for video in VIDEOS:
  for r in pd.read_parquet(SCAN/video/"candidate_table.parquet").sort_values("candidate_order").to_dict("records"):
   if len(r["source_unit_ids"])!=1:raise RuntimeError("candidate unit semantics mismatch")
   out.append({"video_id":video,"candidate_id":r["candidate_id"],"unit_id":r["source_unit_ids"][0],"candidate_order":int(r["candidate_order"]),"start_sec":float(r["start_sec"]),"end_sec":float(r["end_sec"])})
 if len(out)!=1475:raise RuntimeError("expected 1475 released units")
 return out
def freeze():
 if PROTOCOL.exists():raise RuntimeError("Proxy B protocol already frozen")
 if TABLE.exists():raise RuntimeError("outcome table exists before freeze")
 u=units(); p={"protocol_id":"P1_PROXY_B_KINEMATIC_VISUAL_DYNAMICS_V1","status":"FROZEN_BEFORE_PROXY_SCORES","proxy_family":"PROXY_B_CHEAP_OPTICAL_FLOW_VISUAL_DYNAMICS","role":"natural cheap visual proxy; not semantic oracle or event reference","independence_from_proxy_A":"Proxy A uses YOLOv8n retained COCO detections at one unit midpoint. Proxy B uses grayscale Farneback optical flow and frame-difference statistics at four evenly spaced unit samples, with no detector, text model, or semantic outcome.","unit_universe":{"count":1475,"sha256":ch(u)},"videos":{v:{"path":str(x.relative_to(ROOT)),"sha256":sha(x)} for v,x in VIDEOS.items()},"features":{"flow_median":"median per-pixel Farneback magnitude over three adjacent frame pairs","flow_p90":"90th percentile per-pixel Farneback magnitude pooled over adjacent pairs","difference_mean":"mean absolute grayscale difference over adjacent pairs","score":"rank-normalized mean of flow_median, flow_p90, difference_mean within each video; fixed equal weights"},"sampling":{"samples_per_unit":4,"timestamps":"start + (i+0.5)*(end-start)/4, i=0..3","resize":"320x180 grayscale","opencv":"Farneback fixed parameters pyr_scale=0.5 levels=3 winsize=15 iterations=3 poly_n=5 poly_sigma=1.2 flags=0"},"prohibited_inputs":["semantic oracle labels","human labels","K3/reference events","C1/EventF1","trace feasibility outcomes"],"code":{"path":str(Path(__file__).relative_to(ROOT)),"sha256":sha(Path(__file__))}}
 p["protocol_hash"]=ch(p);BASE.mkdir(parents=True,exist_ok=True);PROTOCOL.write_text(json.dumps(p,indent=2,sort_keys=True)+"\n");print(json.dumps({"status":"FROZEN","protocol_hash":p["protocol_hash"],"units":1475},sort_keys=True))
def load():
 p=json.loads(PROTOCOL.read_text());
 if p["protocol_hash"]!=ch({k:v for k,v in p.items() if k!="protocol_hash"}):raise RuntimeError("protocol hash mismatch")
 if p["code"]["sha256"]!=sha(Path(__file__)):raise RuntimeError("runner changed after freeze")
 if p["unit_universe"]["sha256"]!=ch(units()):raise RuntimeError("unit changed after freeze")
 for v,x in VIDEOS.items():
  if p["videos"][v]["sha256"]!=sha(x):raise RuntimeError("video changed after freeze")
 return p
def get_frame(cap,t):
 cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=cap.read()
 if not ok:raise RuntimeError(f"decode failure at {t}")
 return cv2.resize(cv2.cvtColor(f,cv2.COLOR_BGR2GRAY),(320,180),interpolation=cv2.INTER_AREA)
def run():
 p=load();rows=[]
 for video in VIDEOS:
  cap=cv2.VideoCapture(str(VIDEOS[video]));sub=[x for x in units() if x["video_id"]==video]
  for i,u in enumerate(sub,1):
   ts=[u["start_sec"]+(j+.5)*(u["end_sec"]-u["start_sec"])/4 for j in range(4)];fr=[get_frame(cap,t) for t in ts]
   flows=[];diffs=[]
   for a,b in zip(fr,fr[1:]):
    flow=cv2.calcOpticalFlowFarneback(a,b,None,.5,3,15,3,5,1.2,0);mag=cv2.magnitude(flow[...,0],flow[...,1]);flows.append(mag);diffs.append(float(np.abs(b.astype(np.float32)-a.astype(np.float32)).mean()))
   flat=np.concatenate([x.ravel() for x in flows]);rows.append({**u,"flow_median":float(np.median(flat)),"flow_p90":float(np.quantile(flat,.9)),"difference_mean":float(np.mean(diffs)),"sample_timestamps_json":json.dumps(ts,separators=(",",":")),"protocol_hash":p["protocol_hash"]})
   if i%100==0:print(json.dumps({"status":"PROGRESS","video":video,"completed_video":i},sort_keys=True),flush=True)
  cap.release()
 df=pd.DataFrame(rows)
 for col in ["flow_median","flow_p90","difference_mean"]:df[f"rank_{col}"]=df.groupby("video_id")[col].rank(method="average",pct=True)
 df["proxy_score"]=(df.rank_flow_median+df.rank_flow_p90+df.rank_difference_mean)/3
 df.sort_values(["video_id","candidate_order"]).to_parquet(TABLE,index=False)
 summary={"status":"COMPLETE","units":len(df),"protocol_hash":p["protocol_hash"],"table_sha256":sha(TABLE),"per_video":df.groupby("video_id").proxy_score.agg(["count","min","mean","max"]).round(6).to_dict("index")}
 (BASE/"PROXY_B_COMPLETION.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,sort_keys=True))
if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("command",choices=("freeze","run"));z=a.parse_args();freeze() if z.command=="freeze" else run()
