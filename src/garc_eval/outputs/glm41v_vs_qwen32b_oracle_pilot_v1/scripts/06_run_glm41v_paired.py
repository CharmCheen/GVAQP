#!/usr/bin/env python3
"""Phase 7: GLM-4.1V paired test (full manifest)."""
import os, sys, yaml, json, time, pandas as pd, numpy as np, torch, gc
from PIL import Image

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"

with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)
with open(f"{ROOT}/config/decoding_config.yaml") as f:
    dec_cfg = yaml.safe_load(f)

MODEL_PATH = paths["glm41v"]
MANIFEST = f"{ROOT}/inputs/sample_manifest_paired.csv"
OUT_DIR = f"{ROOT}/raw_outputs/glm41v/paired"
os.makedirs(OUT_DIR, exist_ok=True)

with open(f"{ROOT}/config/oracle_prompt_v1.md") as f:
    PROMPT_TEXT = f.read()

# Check if already complete
existing_ids = set()
for fname in os.listdir(OUT_DIR):
    if fname.endswith(".json"):
        existing_ids.add(fname.replace(".json", ""))
print(f"Already completed: {len(existing_ids)}")

df = pd.read_csv(MANIFEST)
pending = df[~df["anchor_id"].isin(existing_ids)]
print(f"Pending: {len(pending)}/{len(df)}")

if len(pending) == 0:
    print("All samples already processed. Skipping GLM inference.")
    sys.exit(0)

# Load model
print(f"\nLoading GLM-4.1V from {MODEL_PATH}...")
from transformers import Glm4vForConditionalGeneration, Glm4vProcessor

t0 = time.time()
model = Glm4vForConditionalGeneration.from_pretrained(
    MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto", local_files_only=True)
processor = Glm4vProcessor.from_pretrained(MODEL_PATH, local_files_only=True)
print(f"Model loaded in {time.time()-t0:.0f}s")

results = []
for i, (_, row) in enumerate(pending.iterrows()):
    aid = row["anchor_id"]
    cs_path = row["contact_sheet_path"]
    print(f"\n[{i+1}/{len(pending)}] {aid}")

    if not os.path.isfile(cs_path):
        print(f"  Contact sheet not found")
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

        raw_out = {
            "anchor_id": aid,
            "model": "GLM-4.1V",
            "prompt_text": PROMPT_TEXT,
            "raw_output": output_text,
            "runtime_seconds": round(runtime, 3),
            "peak_gpu_memory_gb": round(peak_mem, 3),
            "parse_status": "raw_saved",
        }
        with open(f"{OUT_DIR}/{aid}.json", "w") as f:
            json.dump(raw_out, f, indent=2, ensure_ascii=False)

        results.append({
            "anchor_id": aid,
            "runtime_seconds": round(runtime, 3),
            "peak_gpu_memory_gb": round(peak_mem, 3),
            "parse_status": "raw_saved",
        })
        print(f"  Latency: {runtime:.1f}s, Mem: {peak_mem:.1f}GB, Output: {output_text[:80]}...")

    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "anchor_id": aid,
            "runtime_seconds": None,
            "parse_status": f"inference_failed: {e}",
        })

    gc.collect()
    torch.cuda.empty_cache()

res_df = pd.DataFrame(results)
res_df.to_csv(f"{ROOT}/tables/glm41v_paired_results.csv", index=False)
print(f"\nGLM paired test complete.")
print(f"Total pending: {len(pending)}")
print(f"Successful: {(res_df['parse_status']=='raw_saved').sum()}")
print(f"Mean latency: {res_df['runtime_seconds'].dropna().mean():.1f}s")
