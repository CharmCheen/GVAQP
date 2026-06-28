#!/usr/bin/env python3
"""Phase 7b: Qwen3-VL-32B paired test or load historical reference."""
import os, sys, yaml, json, time, pandas as pd, numpy as np, torch, gc
from PIL import Image

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"

with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)
with open(f"{ROOT}/config/decoding_config.yaml") as f:
    dec_cfg = yaml.safe_load(f)

MODEL_PATH = paths["qwen32b"]
MANIFEST = f"{ROOT}/inputs/sample_manifest_paired.csv"
OUT_DIR = f"{ROOT}/raw_outputs/qwen32b/paired"
os.makedirs(OUT_DIR, exist_ok=True)

CANON_TABLE = paths["canonical_table"]
canon = pd.read_csv(CANON_TABLE)
canon["oracle_label"] = canon["oracle_label"].fillna(canon.get("label", ""))

with open(f"{ROOT}/config/oracle_prompt_v1.md") as f:
    PROMPT_TEXT = f.read()

# Check reference mode
with open(f"{ROOT}/logs/qwen_reference_mode.json") as f:
    qwen_mode = json.load(f)

qwen_loaded = qwen_mode.get("qwen_rerun_available", False)
print(f"Qwen reference mode: {qwen_mode['qwen_reference_mode']}")

df = pd.read_csv(MANIFEST)

if qwen_loaded:
    # Check already complete
    existing_ids = set()
    for fname in os.listdir(OUT_DIR):
        if fname.endswith(".json"):
            existing_ids.add(fname.replace(".json", ""))
    print(f"Already completed Qwen paired: {len(existing_ids)}")

    pending = df[~df["anchor_id"].isin(existing_ids)]
    print(f"Pending: {len(pending)}/{len(df)}")

    if len(pending) == 0:
        print("All Qwen paired samples already processed.")
        sys.exit(0)

    # Load model
    print(f"\nLoading Qwen3-VL-32B from {MODEL_PATH}...")
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
    t0 = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto",
        trust_remote_code=True, local_files_only=True)
    processor = AutoProcessor.from_pretrained(
        MODEL_PATH, trust_remote_code=True, local_files_only=True)
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
                "model": "Qwen3-VL-32B",
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
            print(f"  Latency: {runtime:.1f}s, Mem: {peak_mem:.1f}GB")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"anchor_id": aid, "runtime_seconds": None, "parse_status": f"inference_failed: {e}"})

        gc.collect()
        torch.cuda.empty_cache()

    res_df = pd.DataFrame(results)
    res_df.to_csv(f"{ROOT}/tables/qwen32b_paired_results.csv", index=False)
    print(f"\nQwen paired test complete.")

else:
    # Load historical references for the paired manifest
    print("\nLoading historical reference labels for paired manifest.")
    results = []
    for _, row in df.iterrows():
        aid = row["anchor_id"]
        match = canon[canon["anchor_id"] == aid]
        if len(match) == 0:
            results.append({"anchor_id": aid, "parse_status": "reference_not_found"})
            continue
        ref = match.iloc[0]
        results.append({
            "anchor_id": aid,
            "reference_label": str(ref.get("oracle_label", ref.get("label", ""))),
            "reference_is_positive": bool(ref["is_positive"]),
            "parse_status": "historical_reference",
        })

    res_df = pd.DataFrame(results)
    res_df.to_csv(f"{ROOT}/tables/qwen32b_paired_results.csv", index=False)
    print(f"Loaded {len(results)} historical references for paired manifest.")
