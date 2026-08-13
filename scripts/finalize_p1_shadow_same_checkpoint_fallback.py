#!/usr/bin/env python3
"""Freeze same-checkpoint independent-session fallback after judge feasibility failures."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/p1_shadow_vlm_direct_reference_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def chash(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def main():
 pth=OUT/'SHADOW_PROTOCOL.json'; p=json.loads(pth.read_text())
 if p.get('fallback_id'): raise RuntimeError('fallback already frozen')
 archive=OUT/'FAILED_32B_PREFLIGHT'; archive.mkdir(exist_ok=False)
 raw=OUT/'VLM_B_RAW.jsonl'
 if raw.exists(): raw.rename(archive/raw.name)
 log=OUT/'VLM_B_RUN.log'
 if log.exists(): log.rename(archive/log.name)
 prior=p['annotators']['VLM_B']; old=p['protocol_hash']
 p['annotators']['VLM_B']={**p['annotators']['VLM_A'],'model':'Qwen/Qwen3-VL-8B-Instruct independent session B','session_prompt_variant':'B'}
 p['independence']='same frozen Qwen3-VL-8B checkpoint; fully separate session and raw log; B never reads A; B uses a separately frozen semantically equivalent prompt ordering'
 p['prompt_template_b']="""Act as an independent blinded event annotator for chronological frames sampled from one raw driving-video window, spanning ABS_START to ABS_END seconds. Use only the frozen query below. Return exactly one compact JSON object, no markdown or commentary: {\"events\":[{\"start_offset_sec\":0.0,\"end_offset_sec\":0.0,\"boundary_ambiguous\":false,\"semantic_ambiguous\":false,\"notes\":\"brief visible evidence\"}]}. Times are offsets within [0, WINDOW_DURATION]. Use {\"events\":[]} if absent. Annotate maximal semantic occurrences, never a fixed gap. Clip an event crossing the window edge and mark its boundary ambiguous. Judge visible semantics only.\n\nFROZEN QUERY:\nQUERY_TEXT\n"""
 p['fallback_id']='SAME_CHECKPOINT_INDEPENDENT_SESSION_FALLBACK'
 p['fallback_reason']='Cross-family SmolVLM2 failed context/schema feasibility; Qwen32 generated valid-looking but repeatedly overlong truncated JSON under the frozen cap. User protocol explicitly permits same-checkpoint independent sessions. Both failed streams are excluded.'
 p['prior_vlm_b_32b']=prior; p['prior_protocol_hash_32b']=old; p['fallback_at_utc']=datetime.now(timezone.utc).isoformat()
 p['protocol_hash']=chash({k:v for k,v in p.items() if k not in {'created_at_utc','amended_at_utc','fallback_at_utc','protocol_hash'}})
 pth.write_text(json.dumps(p,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
 state=json.loads((OUT/'SHADOW_STATE.json').read_text()); state.update({'status':'SAME_CHECKPOINT_FALLBACK_FROZEN','protocol_hash':p['protocol_hash'],'vlm_b_complete':False,'vlm_b_independence':'SAME_CHECKPOINT_INDEPENDENT_SESSION_PROMPT','p2_authorized':False}); (OUT/'SHADOW_STATE.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
 (OUT/'VLM_ANNOTATOR_FEASIBILITY_AUDIT.md').write_text('# VLM annotator feasibility audit\n\n- SmolVLM2-500M cross-family attempt: failed context/schema feasibility; excluded.\n- Qwen3-VL-32B attempt: overlong JSON truncation under frozen generation cap; excluded.\n- Final VLM_A/VLM_B: same Qwen3-VL-8B checkpoint, fully independent sessions and separately frozen prompt orderings, as permitted by the shadow protocol request. This weakens independence and is a major interpretive confound.\n')
 print(json.dumps({'status':'SAME_CHECKPOINT_FALLBACK_FROZEN','protocol_hash':p['protocol_hash']}))
if __name__=='__main__': main()
