#!/usr/bin/env python3
"""Phase 6: Parse and compare smoke test results."""
import os, sys, yaml, json, re, pandas as pd, numpy as np

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"

with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)

GLM_DIR = f"{ROOT}/raw_outputs/glm41v/smoke"
QEN_DIR = f"{ROOT}/raw_outputs/qwen32b/smoke"
MANIFEST = f"{ROOT}/inputs/sample_manifest_smoke.csv"

# Load manifests
manifest = pd.read_csv(MANIFEST)
print(f"Manifest: {len(manifest)} samples")

# Load Qwen reference mode
with open(f"{ROOT}/logs/qwen_reference_mode.json") as f:
    qwen_mode = json.load(f)
print(f"Qwen mode: {qwen_mode['qwen_reference_mode']}")

# Load Qwen smoke results
qwen_res = pd.read_csv(f"{ROOT}/tables/qwen32b_smoke_results.csv")
print(f"Qwen results: {len(qwen_res)} entries")

def strip_think_tags(text):
    """Remove <think>...</think> and <answer>...</answer> blocks from model output."""
    if not text:
        return text
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'</?answer>' , '', text, flags=re.DOTALL).strip()
    text = re.sub(r'<\|im_end\|>.*$', '', text, flags=re.DOTALL).strip()
    return text

def parse_json_from_text(text):
    """Extract JSON object from model output."""
    if not text or not isinstance(text, str):
        return None, "empty_output"
    text = text.strip()
    # Strip think tags first (GLM-4.1V often outputs these)
    text = strip_think_tags(text)
    # Try direct JSON parse
    try:
        return json.loads(text), "ok"
    except json.JSONDecodeError:
        pass
    # Find outermost JSON object: first { to last matching }
    stack = []
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if start == -1:
                start = i
            stack.append(i)
        elif ch == '}':
            if stack:
                stack.pop()
                if not stack and start >= 0:
                    try:
                        return json.loads(text[start:i+1]), "brace_matched"
                    except json.JSONDecodeError:
                        pass
    return None, "parse_failed"

# Parse GLM outputs
glm_records = []
for _, row in manifest.iterrows():
    aid = row["anchor_id"]
    json_path = f"{GLM_DIR}/{aid}.json"
    if not os.path.isfile(json_path):
        glm_records.append({"anchor_id": aid, "parse_status": "no_raw_output", "parsed": None})
        continue
    with open(json_path) as f:
        raw = json.load(f)
    parsed, parse_status = parse_json_from_text(raw.get("raw_output", ""))
    glm_records.append({
        "anchor_id": aid,
        "parsed": parsed,
        "parse_status": parse_status,
        "raw_output": raw.get("raw_output", ""),
        "runtime_seconds": raw.get("runtime_seconds"),
        "peak_gpu_memory_gb": raw.get("peak_gpu_memory_gb"),
    })

glm_df = pd.DataFrame(glm_records)
glm_parse_ok = (glm_df["parse_status"].isin(["ok", "regex_extracted"])).sum()
glm_parse_fail = len(glm_df) - glm_parse_ok
print(f"\nGLM parse: {glm_parse_ok}/{len(glm_df)} OK, {glm_parse_fail} failed")

# Build comparison table
qwen_ref = {}
for _, row in qwen_res.iterrows():
    qwen_ref[row["anchor_id"]] = row

comparison_rows = []
for _, mrow in manifest.iterrows():
    aid = mrow["anchor_id"]
    glm_match = glm_df[glm_df["anchor_id"] == aid]
    glm_parsed = glm_match.iloc[0]["parsed"] if len(glm_match) > 0 else None
    glm_status = glm_match.iloc[0]["parse_status"] if len(glm_match) > 0 else "missing"

    glm_label = None
    if glm_parsed and isinstance(glm_parsed, dict):
        glm_label = glm_parsed.get("event_label", str(glm_parsed.get("label", ""))).lower()

    # Qwen reference
    qr = qwen_ref.get(aid, {})
    qwen_label = None
    if qwen_mode["qwen_reference_mode"] == "paired_rerun":
        qwen_raw_path = f"{QEN_DIR}/{aid}.json"
        qwen_raw = ""
        if os.path.isfile(qwen_raw_path):
            with open(qwen_raw_path) as _f:
                qwen_raw = json.load(_f).get("raw_output", "")
        qwen_parsed, _ = parse_json_from_text(qwen_raw)
        if qwen_parsed and isinstance(qwen_parsed, dict):
            qwen_label = qwen_parsed.get("event_label", "").lower()
    else:
        # Historical reference
        qwen_label = str(qr.get("reference_label", "")).lower() if pd.notna(qr.get("reference_label")) else ""

    ref_pos = mrow["is_positive"]
    ref_label = "positive" if ref_pos else "negative"

    comparison_rows.append({
        "anchor_id": aid,
        "sample_type": mrow["sample_type"],
        "reference_label": ref_label,
        "reference_is_positive": ref_pos,
        "glm_parse_status": glm_status,
        "glm_label": glm_label,
        "qwen_label": qwen_label,
        "glm_runtime_s": glm_match.iloc[0]["runtime_seconds"] if len(glm_match) > 0 else None,
        "glm_peak_mem_gb": glm_match.iloc[0]["peak_gpu_memory_gb"] if len(glm_match) > 0 else None,
    })

comp = pd.DataFrame(comparison_rows)

# Compute metrics
n_total = len(comp)
n_glm_parsed = comp["glm_parse_status"].isin(["ok", "regex_extracted"]).sum()
n_qwen_parsed = comp["qwen_label"].notna().sum()
agreement = (comp["glm_label"] == comp["qwen_label"]).sum()
# Positive recall vs Qwen
qwen_pos = comp[comp["qwen_label"] == "positive"]
glm_pos_on_qwen_pos = (qwen_pos["glm_label"] == "positive").sum()
pos_recall = glm_pos_on_qwen_pos / len(qwen_pos) if len(qwen_pos) > 0 else None
# Agreement among parsed
parsed_mask = comp["glm_parse_status"].isin(["ok", "regex_extracted"])
parsed_comp = comp[parsed_mask]
parsed_agree = (parsed_comp["glm_label"] == parsed_comp["qwen_label"]).sum()
parsed_agree_rate = parsed_agree / len(parsed_comp) if len(parsed_comp) > 0 else 0

print(f"\n{'='*60}")
print(f"Smoke Comparison Results")
print(f"{'='*60}")
print(f"Total samples: {n_total}")
print(f"GLM parsed OK: {n_glm_parsed}/{n_total}")
print(f"Qwen parsed OK: {n_qwen_parsed}/{n_total}")
print(f"Agreement (all): {agreement}/{n_total} ({100*agreement/n_total:.1f}%)")
print(f"Agreement (parsed): {parsed_agree}/{len(parsed_comp)} ({100*parsed_agree_rate:.1f}%)")
if len(qwen_pos) > 0:
    print(f"Qwen positives: {len(qwen_pos)}")
    print(f"GLM positive recall vs Qwen: {glm_pos_on_qwen_pos}/{len(qwen_pos)} ({100*pos_recall:.1f}%)")
if len(glm_match) > 0 and glm_match.iloc[0]["runtime_seconds"] is not None:
    mean_lat = comp["glm_runtime_s"].dropna().mean()
    print(f"GLM mean latency: {mean_lat:.2f}s")

# Check smoke continue conditions
glm_parse_ok_count = (comp["glm_parse_status"].isin(["ok", "regex_extracted"])).sum()
glm_has_latency = comp["glm_runtime_s"].notna().any()
systematic_fail = glm_parse_ok_count < 10
gpu_oom = any("OOM" in str(s) for s in comp["glm_parse_status"].tolist()) if "glm_parse_status" in comp.columns else False

smoke_continue = (glm_parse_ok_count >= 10) and glm_has_latency and not systematic_fail and not gpu_oom

print(f"\nSmoke continue conditions:")
print(f"  GLM parse >= 10/12: {glm_parse_ok_count}/12 {'PASS' if glm_parse_ok_count >= 10 else 'FAIL'}")
print(f"  GLM mean latency recorded: {'PASS' if glm_has_latency else 'FAIL'}")
print(f"  No systematic JSON failure: {'PASS' if not systematic_fail else 'FAIL'}")
print(f"  No GPU OOM: {'PASS' if not gpu_oom else 'FAIL'}")
print(f"\nSmoke check: {'PASS - CONTINUE TO PAIRED TEST' if smoke_continue else 'FAIL - STOP'}")

# Save comparison
comp.to_csv(f"{ROOT}/tables/smoke_comparison.csv", index=False)

# Save smoke decision
smoke_decision = {
    "smoke_continue": smoke_continue,
    "n_total": n_total,
    "n_glm_parsed": n_glm_parsed,
    "glm_parse_ok_count": glm_parse_ok_count,
    "glm_has_latency": bool(glm_has_latency),
    "agreement_parsed": parsed_agree,
    "agreement_parsed_rate": round(parsed_agree_rate, 3),
    "glm_positive_recall_vs_qwen": round(float(pos_recall), 3) if pos_recall is not None else None,
    "glm_positive_recall_vs_qwen_raw": float(pos_recall) if pos_recall is not None else None,
    "decision": "CONTINUE_TO_PAIRED" if smoke_continue else "GLM41V_SMOKE_FAILED",
}
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)

with open(f"{ROOT}/logs/smoke_decision.json", "w") as f:
    json.dump(smoke_decision, f, indent=2, cls=NumpyEncoder)

if not smoke_continue:
    print(f"\nDECISION: GLM41V_SMOKE_FAILED")
else:
    print(f"\nDECISION: CONTINUE_TO_PAIRED")
