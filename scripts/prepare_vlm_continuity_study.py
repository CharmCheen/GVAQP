#!/usr/bin/env python3
"""Freeze the independent blinded VLM continuity-study contract before runs."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
HUMAN=ROOT/"outputs/human_continuity_validation_v1"
OUT=ROOT/"outputs/vlm_continuity_validation_v1"
MODEL=Path("/root/.cache/huggingface/hub/models--HuggingFaceTB--SmolVLM2-500M-Video-Instruct/snapshots/7b375e1b73b11138ff12fe22c8f2822d8fe03467")
RUNNER=ROOT/"scripts/run_vlm_continuity_judge.py"


def sha(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()


def canonical(v: Any) -> bytes: return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def chash(v: Any) -> str: return hashlib.sha256(canonical(v)).hexdigest()
def write_json(path: Path,v: Any) -> None: path.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()): raise RuntimeError(f"refusing to overwrite existing study: {OUT}")
    cases_path=HUMAN/"annotation_package/PRIMARY_BLINDED_CASES.json"
    state=json.loads((HUMAN/"HUMAN_CONTINUITY_STATE.json").read_text())
    if state.get("human_labels_observed") != 0 or (HUMAN/"HUMAN_LABELS_PRIMARY_FROZEN.csv").exists(): raise RuntimeError("human benchmark is no longer zero-label; do not create VLM study")
    source=json.loads(cases_path.read_text()); cases=source["cases"]
    if len(cases)!=40 or len({x["case_id"] for x in cases})!=40: raise RuntimeError("requires the exact frozen 40-case human primary set")
    if not MODEL.is_dir() or not (MODEL/"model.safetensors").is_file(): raise RuntimeError("cached non-Qwen judge unavailable")
    public_root=HUMAN/"annotation_package"; blind=[]
    for x in cases:
        clips=[]
        for c in x["clips"]:
            p=public_root/c["path"]
            if not p.is_file(): raise RuntimeError(f"blinded clip missing: {p}")
            clips.append({**c,"sha256":sha(p)})
        blind.append({"case_id":x["case_id"],"query_id":x["query_id"],"query_text":x["query_text"],"clips":clips,"display":x["display"],"input_clip_hash":chash(clips)})
    prompt="""You are an independent video-continuity judge. You will receive a driving-video context containing neutral markers A and B, plus a semantic query. Judge the visible driving semantics, not merely temporal distance. Return exactly one JSON object with no markdown or extra text:
{"label":"SAME_EVENT"|"DIFFERENT_EVENTS"|"ANCHOR_INVALID"|"UNCERTAIN","confidence":0.0,"brief_rationale":"one short sentence"}

Definitions:
- SAME_EVENT: both A and B satisfy the query and belong to one continuing semantic episode; a short occlusion, observation gap, or intensity change can still be continuous.
- DIFFERENT_EVENTS: both satisfy the query, but the earlier episode has ended and B is another independent episode.
- ANCHOR_INVALID: at least one marked anchor itself does not satisfy the query.
- UNCERTAIN: visible evidence is insufficient for a reliable judgment.

Frozen semantic query:
{QUERY}
"""
    model_hash=sha(MODEL/"model.safetensors")
    protocol={
      "protocol_id":"INDEPENDENT_VLM_EVENT_CONTINUITY_SANITY_V1",
      "protocol_type":"POST_P0_BLINDED_VLM_SEMANTIC_SANITY_STUDY",
      "created_at_utc":datetime.now(timezone.utc).isoformat(),"protocol_frozen":True,
      "study_design":"SINGLE_JUDGE","judge_independence_level":"CROSS_FAMILY",
      "judge_a":{"model_id":"HuggingFaceTB/SmolVLM2-500M-Video-Instruct","model_family":"HuggingFace SmolVLM (Idefics/Llama-derived; non-Qwen)","revision":"7b375e1b73b11138ff12fe22c8f2822d8fe03467","local_snapshot":str(MODEL),"model_weight_sha256":model_hash,"architecture":"SmolVLMForConditionalGeneration","limitations":"500M local video VLM: independent family but weaker than a large external judge; evidence is a blinded VLM sanity check, not human ground truth."},
      "source_human_benchmark":{"primary_cases_path":str(cases_path.relative_to(ROOT)),"primary_cases_sha256":sha(cases_path),"human_state_sha256":sha(HUMAN/"HUMAN_CONTINUITY_STATE.json"),"human_labels_observed_at_freeze":0,"human_protocol_modified":False},
      "input_contract":{"case_count":40,"case_hash":chash(blind),"annotation_package_root":str(public_root),"same_blinded_clips":True,"hidden_method_metadata_visible_to_judge":False,"frame_construction":"For each full-context MP4: 8 uniform frames plus one midpoint frame for each detected neutral A/B marker; for any long-context A/B detail MP4: 4 uniform frames. At most 18 images, ordered only by public clip order. No hidden timestamps/method fields are read."},
      "judge_prompt":prompt,"judge_prompt_hash":hashlib.sha256(prompt.encode()).hexdigest(),
      "generation":{"do_sample":False,"temperature":0,"max_new_tokens":180,"schema_labels":["SAME_EVENT","DIFFERENT_EVENTS","ANCHOR_INVALID","UNCERTAIN"],"repeat_semantic_query":False},
      "runtime":{"cuda_visible_devices":"0","dtype":"bfloat16","local_files_only":True,"single_gpu_serial":True},
      "analysis_contract":{"read_hidden_predictions_only_after":"JUDGE_A_LABELS.csv hash freeze at 40/40","primary":"accuracy C1-C0 on SAME/DIFFERENT eligible labels","secondary":"K3-C1, boundary metrics, population weighted descriptive results, paired bootstrap 10000 resamples seed 20260811","decision_rules":{"inconclusive_if_any":["eligible_cases < 28","paired_bootstrap_95pct_CI_width_C1_minus_C0 > 0.40"],"supports_gap_only_if_all":["not inconclusive","C1_minus_C0 >= 0.10","positive direction in at least two videos with at least five eligible cases","K3_minus_C1 < 0.10"],"supports_full_K3_if_all":["not inconclusive","K3_minus_C1 >= 0.10","positive direction in at least two videos with at least five eligible cases"],"otherwise":"NO_VLM_SUPPORT"}},
      "code":{"runner_path":str(RUNNER.relative_to(ROOT)),"runner_sha256":sha(RUNNER),"prepare_path":str(Path(__file__).relative_to(ROOT)),"prepare_sha256":sha(Path(__file__))},
      "source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
    }
    protocol["protocol_hash"]=chash({k:v for k,v in protocol.items() if k not in {"created_at_utc","protocol_hash"}})
    OUT.mkdir(parents=True)
    write_json(OUT/"BLINDED_INPUT_CASES.json",{"annotation_package_root":str(public_root),"case_count":40,"cases":blind,"input_hash":chash(blind)})
    write_json(OUT/"VLM_JUDGE_PROTOCOL.json",protocol)
    (OUT/"PROTOCOL_HASH.txt").write_text(protocol["protocol_hash"]+"\n",encoding="utf-8")
    (OUT/"VLM_CONTINUITY_PREREGISTRATION.md").write_text(f"""# Independent VLM Event-Continuity Sanity Study\n\nProtocol: `{protocol['protocol_hash']}`. This is a post-P0 blinded **VLM** semantic sanity study, never human validation or ground truth. It reuses the exact frozen 40-case human primary set without modifying it. Human labels observed at this freeze: **0**.\n\nJudge A is `{protocol['judge_a']['model_id']}` at cached revision `{protocol['judge_a']['revision']}`, a non-Qwen model family. The model receives only public blind IDs, query text, rendered A/B-marked clips, and the neutral label definitions. C0/C1/K3 predictions, strata, reference events, and P0 outcomes are not in the judge input.\n\nOne deterministic response is recorded per case. All 40 labels and raw logs are hash-frozen before hidden predictions may be joined. This study supplies independent cross-model semantic sanity evidence; it cannot replace future real-human validation.\n""",encoding="utf-8")
    (OUT/"JUDGE_MODEL_AUDIT.md").write_text(f"""# Judge Model Audit\n\n## Selected\n\n- Judge A: `{protocol['judge_a']['model_id']}` (`SmolVLMForConditionalGeneration`), revision `{protocol['judge_a']['revision']}`.\n- Weight SHA256: `{model_hash}`.\n- Family relationship to original Qwen3-VL-32B model-relative reference: **CROSS_FAMILY**.\n- Local artifact: fully cached 2.03GB `model.safetensors`; CUDA A100 hardware is available.\n\n## Alternatives audited\n\n- Local Qwen3-VL-8B is runnable but is Qwen family and was not used as a consensus judge, to avoid obscuring the cross-family interpretation.\n- No second cached cross-family video-generative VLM was found. The protocol therefore freezes a single cross-family judge rather than delaying the study or fabricating a dual design.\n\n## Evidence limitation\n\nThis 500M VLM is materially smaller than the original reference oracle. It is independent-family, blinded semantic corroboration only; it is not human ground truth and cannot settle all circularity concerns.\n""",encoding="utf-8")
    state={"status":"PROTOCOL_FROZEN","protocol_hash":protocol["protocol_hash"],"judge_models":[protocol["judge_a"]["model_id"]],"independence_level":"CROSS_FAMILY","cases_total":40,"judge_a_completed":0,"judge_b_completed":0,"labels_frozen":False,"analysis_complete":False,"primary_decision":None,"paper_mainline_after_vlm":None,"human_validation_status":"PENDING_UNMODIFIED"}
    write_json(OUT/"VLM_CONTINUITY_STATE.json",state)
    print(json.dumps({"status":"PROTOCOL_FROZEN","protocol_hash":protocol["protocol_hash"],"cases":40,"judge":"SmolVLM2-500M-Video-Instruct"},sort_keys=True))

if __name__=="__main__": main()
