#!/usr/bin/env python3
"""Resumable P1 semantic-oracle acquisition using local Qwen3-VL-32B.

This produces model-relative unit outcomes for the *new*, frozen second query.
It is not a human reference, a cheap proxy, or an event materializer.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle"
PROMPT = BASE / "Q_VULNERABLE_ROAD_USER_CONFLICT_V1.txt"
PROTOCOL = BASE / "P1_QWEN32_ORACLE_PROTOCOL.json"
RAW = BASE / "raw"
TABLE = BASE / "P1_QWEN32_UNIT_OUTCOMES.parquet"
MODEL = ROOT / "models/Qwen3-VL-32B-Instruct-FP8"
VIDEOS = {"DALI": ROOT / "data/realcam/dali.mp4", "HANGZHOU": ROOT / "data/realcam/hangzhou.mp4", "WUHAN": ROOT / "data/realcam/wuhan.mp4"}
SCAN = ROOT / "outputs/v3_scan_proxy_preregistration_v1/frozen_tables"
QUERY = "Q_VULNERABLE_ROAD_USER_CONFLICT_V1"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def model_manifest() -> tuple[list[dict], str]:
    rows = [{"file": p.name, "sha256": sha(p), "size_bytes": p.stat().st_size} for p in sorted(MODEL.iterdir()) if p.is_file()]
    if not any(x["file"].endswith(".safetensors") for x in rows):
        raise RuntimeError("Qwen3-VL-32B safetensors unavailable")
    return rows, canonical(rows)


def units() -> list[dict]:
    out = []
    for video in VIDEOS:
        c = pd.read_parquet(SCAN / video / "candidate_table.parquet").sort_values("candidate_order")
        for r in c.to_dict("records"):
            source = list(r["source_unit_ids"])
            if len(source) != 1:
                raise RuntimeError("P1 retains one-unit candidate semantics")
            out.append({"video_id": video, "candidate_id": r["candidate_id"], "unit_id": source[0], "start_time": float(r["start_sec"]), "end_time": float(r["end_sec"]), "candidate_order": int(r["candidate_order"])})
    if len(out) != 1475 or len({x["unit_id"] for x in out}) != 1475:
        raise RuntimeError(f"expected released 1475-unit universe, got {len(out)}")
    return out


def freeze() -> None:
    if PROTOCOL.exists():
        raise RuntimeError("oracle protocol already frozen")
    if any(RAW.glob("*.json")) or TABLE.exists():
        raise RuntimeError("refusing to freeze after outcome artifacts exist")
    if os.environ.get("CUDA_VISIBLE_DEVICES") not in {"0,1", None}:
        raise RuntimeError("use exactly physical GPUs 0,1 for the frozen Qwen32 profile")
    for p in [PROMPT, MODEL, *VIDEOS.values()]:
        if not p.exists(): raise RuntimeError(f"missing bound input: {p}")
    files, model_hash = model_manifest()
    u = units()
    payload = {
        "protocol_id": "P1_QWEN3_VL_32B_SECOND_QUERY_FULL_GRID_V1", "status": "FROZEN_BEFORE_OUTCOMES",
        "query_id": QUERY, "prompt_path": str(PROMPT.relative_to(ROOT)), "prompt_sha256": sha(PROMPT),
        "model": {"name": "Qwen3-VL-32B-Instruct-FP8", "path": str(MODEL.relative_to(ROOT)), "file_manifest": files, "content_hash": model_hash, "dtype": "bfloat16", "device_map": "balanced", "physical_gpus": [0,1]},
        "unit_universe": {"count": len(u), "sha256": canonical(u), "candidate_semantics": "released one V3 candidate per 10-second unit", "sampling_fps": 2.0},
        "source_videos": {v: {"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for v,p in VIDEOS.items()},
        "generation": {"do_sample": False, "max_new_tokens": 180, "seed": 20260812, "local_files_only": True},
        "outputs": {"raw_per_unit": "JSON", "outcome_table": "Parquet", "parse_failure_policy": "retain parse_failure; never silently coerce to negative"},
        "role_boundary": "Qwen32 supplies model-relative semantic unit outcomes only. Independent human temporal events remain P1 primary reference; a separate cheap natural Proxy B is still required.",
        "code": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha(Path(__file__))},
    }
    payload["protocol_hash"] = canonical(payload)
    BASE.mkdir(parents=True, exist_ok=True); RAW.mkdir(exist_ok=True)
    PROTOCOL.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status":"FROZEN", "calls":len(u), "protocol_hash":payload["protocol_hash"]}, sort_keys=True))


def load_protocol() -> dict:
    p=json.loads(PROTOCOL.read_text())
    if p.get("protocol_hash") != canonical({k:v for k,v in p.items() if k != "protocol_hash"}): raise RuntimeError("protocol hash mismatch")
    if p["code"]["sha256"] != sha(Path(__file__)): raise RuntimeError("runner changed after freeze")
    if p["prompt_sha256"] != sha(PROMPT): raise RuntimeError("prompt changed after freeze")
    files,h=model_manifest()
    if h != p["model"]["content_hash"] or files != p["model"]["file_manifest"]: raise RuntimeError("model changed after freeze")
    if p["unit_universe"]["sha256"] != canonical(units()): raise RuntimeError("unit universe changed after freeze")
    return p


def frames(video: Path, start: float, end: float, fps: float) -> list[np.ndarray]:
    cap=cv2.VideoCapture(str(video)); native=float(cap.get(cv2.CAP_PROP_FPS)); count=max(1, int(round((end-start)*fps)))
    times=[start+(i+.5)*(end-start)/count for i in range(count)]; result=[]
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t*1000); ok, frame=cap.read()
        if not ok: cap.release(); raise RuntimeError(f"decode failure at {t}s")
        result.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
    cap.release()
    if native <= 0: raise RuntimeError("invalid video FPS")
    return result


def parse(raw: str) -> tuple[str,str,str,str]:
    try:
        o=json.loads(raw)
        if set(o) != {"label","confidence","evidence"}: raise ValueError("schema")
        if o["label"] not in {"relevant","not_relevant","unknown"}: raise ValueError("label")
        if o["confidence"] not in {"high","medium","low"} or not isinstance(o["evidence"],str) or not o["evidence"].strip(): raise ValueError("content")
        return o["label"],o["confidence"],o["evidence"],"OK"
    except Exception as e: return "parse_failure","",str(e),"PARSE_FAILURE"


def run(limit: int | None) -> None:
    p=load_protocol()
    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "0,1" or torch.cuda.device_count()!=2: raise RuntimeError("set CUDA_VISIBLE_DEVICES=0,1")
    random.seed(20260812); np.random.seed(20260812); torch.manual_seed(20260812); torch.cuda.manual_seed_all(20260812)
    completed={x.stem for x in RAW.glob("*.json")}
    todo=[x for x in units() if x["unit_id"] not in completed]
    if limit is not None: todo=todo[:limit]
    print(json.dumps({"status":"START", "remaining_total":1475-len(completed), "this_run":len(todo)}, sort_keys=True), flush=True)
    model=Qwen3VLForConditionalGeneration.from_pretrained(MODEL,dtype=torch.bfloat16,device_map="balanced",trust_remote_code=True,local_files_only=True); model.to(dtype=torch.bfloat16); model.eval()
    processor=AutoProcessor.from_pretrained(MODEL,trust_remote_code=True,local_files_only=True); prompt=PROMPT.read_text()
    for i,u in enumerate(todo,1):
        started=time.perf_counter(); imgs=frames(VIDEOS[u["video_id"]],u["start_time"],u["end_time"],2.0); pil=[Image.fromarray(x) for x in imgs]
        messages=[{"role":"user","content":[{"type":"video","video":pil,"fps":2.0},{"type":"text","text":prompt}]}]
        text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        image_inputs,video_inputs,video_kwargs=process_vision_info(messages,return_video_kwargs=True,return_video_metadata=True)
        vt=[x[0] for x in video_inputs]; vm=[x[1] for x in video_inputs]
        inputs=processor(text=[text],images=image_inputs,videos=vt,video_metadata=vm,padding=True,return_tensors="pt",**video_kwargs).to(model.device)
        with torch.no_grad(): gen=model.generate(**inputs,do_sample=False,max_new_tokens=180)
        raw=processor.batch_decode([o[len(a):] for a,o in zip(inputs.input_ids,gen)],skip_special_tokens=True)[0]
        label,conf,evidence,status=parse(raw)
        record={**u,"query_id":QUERY,"label":label,"confidence":conf,"evidence":evidence,"parse_status":status,"raw":raw,"raw_sha256":hashlib.sha256(raw.encode()).hexdigest(),"elapsed_sec":time.perf_counter()-started,"protocol_hash":p["protocol_hash"]}
        target=RAW/f'{u["unit_id"]}.json'; tmp=target.with_suffix(".tmp"); tmp.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n"); tmp.replace(target)
        if i % 10 == 0 or i == len(todo): print(json.dumps({"status":"PROGRESS","run_completed":i,"remaining_after":1475-len(completed)-i,"unit_id":u["unit_id"],"elapsed_sec":round(record["elapsed_sec"],3)},sort_keys=True),flush=True)
        del inputs,gen,imgs,pil,image_inputs,video_inputs,vt,vm,messages; gc.collect(); torch.cuda.empty_cache()
    all_records=[]
    for u in units():
        f=RAW/f'{u["unit_id"]}.json'
        if f.exists(): all_records.append(json.loads(f.read_text()))
    if len(all_records)==1475:
        pd.DataFrame(all_records).sort_values(["video_id","candidate_order"]).to_parquet(TABLE,index=False)
        (BASE/"P1_QWEN32_ORACLE_COMPLETION.json").write_text(json.dumps({"status":"COMPLETE","units":1475,"parse_status_counts":pd.DataFrame(all_records).parse_status.value_counts().to_dict(),"table_sha256":sha(TABLE),"protocol_hash":p["protocol_hash"]},indent=2,sort_keys=True)+"\n")
        print(json.dumps({"status":"COMPLETE","units":1475,"table":str(TABLE)},sort_keys=True))
    else: print(json.dumps({"status":"PARTIAL","completed":len(all_records),"required":1475},sort_keys=True))


if __name__ == "__main__":
    a=argparse.ArgumentParser(); a.add_argument("command",choices=("freeze","run")); a.add_argument("--limit",type=int); z=a.parse_args()
    freeze() if z.command=="freeze" else run(z.limit)
