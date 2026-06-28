#!/usr/bin/env python3
"""Phase 5: Qwen3-VL-32B smoke test or load historical reference."""
import os, sys, yaml, json, time, pandas as pd, numpy as np, torch, gc
from PIL import Image

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"

with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)
with open(f"{ROOT}/config/decoding_config.yaml") as f:
    dec_cfg = yaml.safe_load(f)

MODEL_PATH = paths["qwen32b"]
MANIFEST = f"{ROOT}/inputs/sample_manifest_smoke.csv"
OUT_DIR = f"{ROOT}/raw_outputs/qwen32b/smoke"
os.makedirs(OUT_DIR, exist_ok=True)

CANON_TABLE = paths["canonical_table"]
canon = pd.read_csv(CANON_TABLE)
canon["oracle_label"] = canon["oracle_label"].fillna(canon.get("label", ""))

# Load prompt
with open(f"{ROOT}/config/oracle_prompt_v1.md") as f:
    PROMPT_TEXT = f.read()

# Load manifest
df = pd.read_csv(MANIFEST)
print(f"Loaded {len(df)} samples for Qwen smoke test")

# Try to load Qwen3-VL-32B model
model = None
processor = None
qwen_loaded = False
load_error = None

print(f"\nAttempting to load Qwen3-VL-32B from {MODEL_PATH}...")
try:
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
    t0 = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto",
        trust_remote_code=True, local_files_only=True)
    processor = AutoProcessor.from_pretrained(
        MODEL_PATH, trust_remote_code=True, local_files_only=True)
    print(f"Qwen3-VL-32B loaded in {time.time()-t0:.0f}s")
    print(f"Device: {model.device}")
    qwen_loaded = True
except Exception as e:
    load_error = str(e)
    print(f"Could not load Qwen3-VL-32B: {e}")
    print("Falling back to historical reference labels from canonical table.")

# Track mode
mode_info = {
    "qwen_rerun_available": qwen_loaded,
    "qwen_reference_mode": "paired_rerun" if qwen_loaded else "historical",
    "load_error": load_error,
    "note": ""
}

if qwen_loaded:
    # Run Qwen on same contact sheets
    results = []
    for i, (_, row) in enumerate(df.iterrows()):
        aid = row["anchor_id"]
        cs_path = row["contact_sheet_path"]
        print(f"\n[{i+1}/{len(df)}] {aid}")

        if not os.path.isfile(cs_path):
            print(f"  Contact sheet not found: {cs_path}")
            results.append({"anchor_id": aid, "parse_status": "contact_sheet_missing", "runtime_seconds": None})
            continue

        try:
            image = Image.open(cs_path).convert("RGB")
            messages = [
                {"role": "user", "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": PROMPT_TEXT}
                ]}
            ]
            text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[text], images=[image], padding=True, return_tensors="pt")
            inputs = {k: v.to(model.device) for k, v in inputs.items()}

            torch.cuda.synchronize()
            t1 = time.time()
            with torch.no_grad():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=dec_cfg["max_new_tokens"],
                    temperature=dec_cfg["temperature"],
                    do_sample=dec_cfg["do_sample"],
                    top_p=dec_cfg["top_p"],
                )
            torch.cuda.synchronize()
            runtime = time.time() - t1

            generated_trimmed = generated_ids[0][len(inputs["input_ids"][0]):]
            output_text = processor.decode(generated_trimmed, skip_special_tokens=True)

            peak_mem = torch.cuda.max_memory_allocated(0) / (1024**3)
            print(f"  Latency: {runtime:.1f}s, Peak mem: {peak_mem:.1f} GB")
            print(f"  Output: {output_text[:150]}...")

            raw_out = {
                "anchor_id": aid,
                "model": "Qwen3-VL-32B",
                "prompt_text": PROMPT_TEXT,
                "raw_output": output_text,
                "runtime_seconds": round(runtime, 3),
                "peak_gpu_memory_gb": round(peak_mem, 3),
                "parse_status": "raw_saved",
                "temperature": dec_cfg["temperature"],
                "max_new_tokens": dec_cfg["max_new_tokens"],
            }
            with open(f"{OUT_DIR}/{aid}.json", "w") as f:
                json.dump(raw_out, f, indent=2, ensure_ascii=False)

            results.append({
                "anchor_id": aid,
                "runtime_seconds": round(runtime, 3),
                "peak_gpu_memory_gb": round(peak_mem, 3),
                "raw_output_path": f"{OUT_DIR}/{aid}.json",
                "parse_status": "raw_saved",
            })

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "anchor_id": aid,
                "runtime_seconds": None,
                "peak_gpu_memory_gb": round(torch.cuda.max_memory_allocated(0)/(1024**3), 3) if torch.cuda.is_available() else None,
                "error": str(e),
                "parse_status": "inference_failed",
            })

        gc.collect()
        torch.cuda.empty_cache()

    res_df = pd.DataFrame(results)
    res_df.to_csv(f"{ROOT}/tables/qwen32b_smoke_results.csv", index=False)
    print(f"\nQwen smoke test complete. {len(results)} samples processed.")
    print(f"Successful: {(res_df['parse_status']=='raw_saved').sum()}/{len(res_df)}")
    print(f"Mean latency: {res_df['runtime_seconds'].dropna().mean():.1f}s")

else:
    # Load historical references
    print("\nLoading historical reference labels from canonical table.")
    results = []
    for _, row in df.iterrows():
        aid = row["anchor_id"]
        match = canon[canon["anchor_id"] == aid]
        if len(match) == 0:
            print(f"  WARNING: {aid} not found in canonical table")
            results.append({"anchor_id": aid, "parse_status": "reference_not_found"})
            continue
        ref = match.iloc[0]
        results.append({
            "anchor_id": aid,
            "reference_label": str(ref.get("oracle_label", ref.get("label", ""))),
            "reference_is_positive": bool(ref["is_positive"]),
            "parse_status": "historical_reference",
        })
        print(f"  {aid}: label={ref.get('oracle_label', ref.get('label', '?'))}, positive={ref['is_positive']}")

    res_df = pd.DataFrame(results)
    res_df.to_csv(f"{ROOT}/tables/qwen32b_smoke_results.csv", index=False)
    print(f"\nLoaded {len(results)} historical references.")
    mode_info["note"] = "Qwen3-VL-32B rerun not available; using historical canonical table labels as reference."

# Save mode info
with open(f"{ROOT}/logs/qwen_reference_mode.json", "w") as f:
    json.dump(mode_info, f, indent=2)

print(f"\nQwen reference mode: {mode_info['qwen_reference_mode']}")
if not qwen_loaded:
    print("QWEN32B_RERUN_NOT_AVAILABLE_USED_HISTORICAL_REFERENCE")
