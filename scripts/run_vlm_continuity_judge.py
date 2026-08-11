#!/usr/bin/env python3
"""Run the frozen blinded 40-case VLM continuity study.

This runner sees only ``BLINDED_INPUT_CASES.json`` plus its frozen protocol.
It deliberately never opens the human hidden sample manifest, the model-
relative relation, or C0/C1/K3 predictions.  Raw per-case outputs checkpoint
immediately; the public judge-label CSV is emitted only after all 40 terminal
semantic judgements have been recorded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/vlm_continuity_validation_v1"
VALID = {"SAME_EVENT", "DIFFERENT_EVENTS", "ANCHOR_INVALID", "UNCERTAIN"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()


def parse_response(raw: str) -> tuple[str | None, float | None, str, str]:
    """Parse once; never prompt again to chase a preferred semantic label."""
    clean = raw.strip()
    candidate = clean
    code = re.search(r"\{.*\}", clean, re.S)
    if code:
        candidate = code.group(0)
    try:
        obj = json.loads(candidate)
        label = str(obj.get("label", "")).upper()
        if label in VALID:
            confidence = obj.get("confidence")
            try: confidence = float(confidence)
            except (TypeError, ValueError): confidence = None
            rationale = str(obj.get("brief_rationale", "")).strip()
            return label, confidence, rationale, "JSON_SCHEMA_VALID"
    except json.JSONDecodeError:
        pass
    found = re.findall(r"\b(SAME_EVENT|DIFFERENT_EVENTS|ANCHOR_INVALID|UNCERTAIN)\b", clean.upper())
    if len(set(found)) == 1:
        return found[0], None, "", "LABEL_TOKEN_RECOVERED"
    return None, None, "", "PARSE_FAILURE"


def marker_kind(frame: np.ndarray) -> str | None:
    """Read only neutral A/B overlays from blinded clips, never hidden times."""
    roi = frame[18:60, 18:60]
    b, g, r = (float(x) for x in roi.reshape(-1, 3).mean(axis=0))
    if r > 100 and g > 100 and b < 130: return "A"
    if b > 100 and g > 100 and r < 130: return "B"
    return None


def read_frames(path: Path, uniform_n: int, require_markers: bool) -> list[Image.Image]:
    cap = cv2.VideoCapture(str(path))
    try:
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if n <= 0: raise RuntimeError(f"cannot decode video: {path}")
        picks = {int(round(x)) for x in np.linspace(0, n - 1, min(uniform_n, n))}
        # Scan every frame on short/high-FPS clips and every source frame on
        # 1-FPS long context; overlays occur for entire 10s anchor intervals.
        a_ix: list[int] = []; b_ix: list[int] = []
        all_frames: dict[int, np.ndarray] = {}
        for i in range(n):
            ok, frame = cap.read()
            if not ok: break
            if i in picks or require_markers:
                all_frames[i] = frame
            if require_markers:
                kind = marker_kind(frame)
                if kind == "A": a_ix.append(i)
                elif kind == "B": b_ix.append(i)
        if not all_frames: raise RuntimeError(f"no decodable frames: {path}")
        for marked in (a_ix, b_ix):
            if marked: picks.add(marked[len(marked)//2])
        # Some long-case detail clips intentionally contain only A or B.  The
        # full context still supplies both markers, so no label semantics are
        # inferred from their absence in a detail clip.
        images=[]
        for i in sorted(picks):
            frame=all_frames.get(i)
            if frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, i); ok, frame=cap.read()
                if not ok: continue
            images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        if not images: raise RuntimeError(f"frame selection failed: {path}")
        return images
    finally:
        cap.release()


def images_for_case(case: dict[str, Any], input_root: Path) -> list[Image.Image]:
    images=[]
    for clip in case["clips"]:
        path=input_root / clip["path"]
        if clip["kind"] == "full_context":
            images.extend(read_frames(path, uniform_n=8, require_markers=True))
        else:
            images.extend(read_frames(path, uniform_n=4, require_markers=False))
    # The frozen protocol sets a hard input cap that preserves contextual
    # uniform frames and neutral anchor overlays without consuming all video
    # frames or consulting hidden source metadata.
    return images[:18]


def completed(raw_path: Path) -> dict[str, dict[str, Any]]:
    done={}
    if not raw_path.exists(): return done
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        x=json.loads(line)
        if x.get("terminal") and x.get("case_id"): done[x["case_id"]]=x
    return done


def freeze_labels(cases: list[dict[str, Any]], raw: dict[str, dict[str, Any]]) -> None:
    path=OUT/"JUDGE_A_LABELS.csv"
    if path.exists(): return
    if set(raw) != {x["case_id"] for x in cases}: raise RuntimeError("not all cases terminal")
    rows=[]
    for c in cases:
        r=raw[c["case_id"]]
        rows.append({"case_id":c["case_id"],"label":r["label"],"confidence":r.get("confidence"),"brief_rationale":r.get("brief_rationale",""),"parse_status":r["parse_status"],"raw_output_sha256":r["raw_output_sha256"],"input_clip_hash":c["input_clip_hash"],"completed_at":r["completed_at"]})
    fields=list(rows[0])
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    (OUT/"JUDGE_A_LABELS_HASH.txt").write_text(sha(path)+"\n",encoding="utf-8")
    state=load_json(OUT/"VLM_CONTINUITY_STATE.json")
    state.update({"judge_a_completed":len(rows),"labels_frozen":True,"judge_a_labels_hash":sha(path),"status":"LABELS_FROZEN_AWAITING_ANALYSIS"})
    (OUT/"VLM_CONTINUITY_STATE.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--resume",action="store_true"); args=ap.parse_args()
    protocol=load_json(OUT/"VLM_JUDGE_PROTOCOL.json")
    if not protocol.get("protocol_frozen"): raise RuntimeError("protocol must be frozen before judgment")
    input_doc=load_json(OUT/"BLINDED_INPUT_CASES.json"); cases=input_doc["cases"]
    if len(cases)!=40 or len({x["case_id"] for x in cases})!=40: raise RuntimeError("requires exactly frozen 40 primary cases")
    if (OUT/"JUDGE_A_LABELS.csv").exists():
        print("JUDGE_A_LABELS_ALREADY_FROZEN"); return
    raw_path=OUT/"JUDGE_A_RAW.jsonl"; done=completed(raw_path)
    model_spec=protocol["judge_a"]
    model_path=Path(model_spec["local_snapshot"])
    if not model_path.is_dir() or sha(model_path/"model.safetensors") != model_spec["model_weight_sha256"]: raise RuntimeError("frozen judge model unavailable or hash mismatch")
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", protocol["runtime"]["cuda_visible_devices"])
    if not torch.cuda.is_available(): raise RuntimeError("CUDA is required by frozen runtime")
    processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
    model=AutoModelForImageTextToText.from_pretrained(model_path,torch_dtype=torch.bfloat16,local_files_only=True)
    model.to("cuda:0"); model.eval()
    prompt=protocol["judge_prompt"]
    input_root=Path(input_doc["annotation_package_root"])
    state=load_json(OUT/"VLM_CONTINUITY_STATE.json")
    for i,case in enumerate(cases,1):
        if case["case_id"] in done: continue
        attempt=0
        while True:
            try:
                images=images_for_case(case,input_root)
                content=[{"type":"image"} for _ in images]+[{"type":"text","text":prompt.replace("{QUERY}",case["query_text"])}]
                messages=[{"role":"user","content":content}]
                rendered=processor.apply_chat_template(messages,add_generation_prompt=True)
                inputs=processor(text=rendered,images=images,return_tensors="pt",padding=True).to("cuda:0")
                with torch.inference_mode():
                    ids=model.generate(**inputs,max_new_tokens=protocol["generation"]["max_new_tokens"],do_sample=False,use_cache=True)
                generated=ids[:,inputs.input_ids.shape[1]:]
                raw=processor.batch_decode(generated,skip_special_tokens=True)[0]
                label,confidence,rationale,parse_status=parse_response(raw)
                if label is None:
                    # A model response is still a terminal semantic attempt;
                    # it is not silently re-run and is explicitly retained.
                    label="UNCERTAIN"
                    parse_status="PARSE_FAILURE_COERCED_TO_UNCERTAIN"
                record={"case_id":case["case_id"],"terminal":True,"attempt":attempt+1,"completed_at":now(),"raw_response":raw,"raw_output_sha256":hashlib.sha256(raw.encode()).hexdigest(),"label":label,"confidence":confidence,"brief_rationale":rationale,"parse_status":parse_status,"model_weight_sha256":model_spec["model_weight_sha256"],"prompt_hash":protocol["judge_prompt_hash"],"input_clip_hash":case["input_clip_hash"],"image_count":len(images)}
                append_jsonl(raw_path,record); done[case["case_id"]]=record
                state.update({"judge_a_completed":len(done),"status":"JUDGE_A_RUNNING"})
                (OUT/"VLM_CONTINUITY_STATE.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
                print(f"JUDGE_A_PROGRESS {len(done)}/40")
                break
            except (RuntimeError, OSError, cv2.error) as exc:
                attempt+=1
                append_jsonl(OUT/"JUDGE_A_INFRA_RETRIES.jsonl",{"case_id":case["case_id"],"attempt":attempt,"timestamp":now(),"failure_type":type(exc).__name__,"message":str(exc)[:500]})
                torch.cuda.empty_cache()
                if attempt >= 3: raise RuntimeError(f"infrastructure retry limit for {case['case_id']}: {exc}") from exc
                time.sleep(2)
    freeze_labels(cases,done)
    print("JUDGE_A_LABELS_FROZEN")


if __name__ == "__main__": main()
