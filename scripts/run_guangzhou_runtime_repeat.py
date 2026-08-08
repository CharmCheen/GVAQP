#!/usr/bin/env python3
"""Explicitly non-independent Guangzhou A/B/C runtime repeat."""
from __future__ import annotations
import hashlib, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s'
OUT=ROOT/'outputs/guangzhou_runtime_repeat_v1/repeat_20260808_8b_300s'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if OUT.exists():raise RuntimeError('refuse overwrite')
 spec=importlib.util.spec_from_file_location('base',ROOT/'scripts/run_exploratory_gate_o_guangzhou.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 ref=json.loads((SOURCE/'reference_labels.json').read_text()); labels={int(k):v['label'] for k,v in ref.items()};OUT.mkdir(parents=True)
 (OUT/'REPEAT_CONTRACT.json').write_text(json.dumps({'protocol_class':'EXPLORATORY_GUANGZHOU_RUNTIME_REPEAT','independent_source_replication':False,'source_reference_reused':True,'reference_file_sha256':h(SOURCE/'reference_labels.json'),'source_video_sha256':m.VIDEO_SHA256,'deadline_seconds':300,'policies':list(m.POLICIES),'execution_authorized':True},indent=2)+'\n')
 cap=m.cv2.VideoCapture(str(m.VIDEO));fps=float(cap.get(m.cv2.CAP_PROP_FPS));count=int(m.np.ceil(4238.25/10));cap.release();oracle=m.Oracle(1)
 from rc_sem.exploratory_deadline_evaluation import deadline_safe_summary
 results=[m.run_policy(p,oracle,fps,count,OUT) for p in m.POLICIES]
 results=[{**r,**deadline_safe_summary(json.loads((OUT/f"{r['policy']}.trace.json").read_text()),labels,300.0)} for r in results]
 (OUT/'RESULTS.json').write_text(json.dumps({'scientific_status':'EXPLORATORY_GUANGZHOU_RUNTIME_REPEAT_NOT_INDEPENDENT','results':results},indent=2)+'\n')
 print(json.dumps({'status':'COMPLETE','results':results},indent=2))
if __name__=='__main__':main()
