#!/usr/bin/env python3
"""
Fast prompt sweep on small test set.
Usage: python3 prompt_sweep_fast.py <glm|qwen> <prompt_variant>
Runs one variant at a time for fast iteration.
"""
import os, sys, yaml, json, time, re, gc
import pandas as pd, numpy as np, torch
from PIL import Image

ROOT = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/prompt_tuning_v1'
PILOT_ROOT = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1'

with open(f'{PILOT_ROOT}/config/model_paths.yaml') as f:
    paths = yaml.safe_load(f)
with open(f'{PILOT_ROOT}/config/decoding_config.yaml') as f:
    dec_cfg = yaml.safe_load(f)

def parse_label(raw):
    jsons = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw)
    for j_str in reversed(jsons):
        try:
            j = json.loads(j_str)
            if 'event_label' in j:
                return j
        except:
            continue
    ans = re.search(r'<answer>(.*?)</answer>', raw, re.DOTALL)
    if ans:
        jsons2 = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ans.group(1))
        for j_str in reversed(jsons2):
            try:
                j = json.loads(j_str)
                if 'event_label' in j:
                    return j
            except:
                continue
    return {'event_label': 'parse_error'}

def evaluate(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 'positive' and p == 'positive')
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 'negative' and p == 'positive')
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 'negative' and p == 'negative')
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 'positive' and p == 'negative')
    n_pos = sum(1 for t in y_true if t == 'positive')
    n_neg = sum(1 for t in y_true if t == 'negative')
    recall = tp / n_pos if n_pos > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
            'n_pos': n_pos, 'n_neg': n_neg,
            'recall': round(recall, 4), 'precision': round(precision, 4), 'f1': round(f1, 4)}

if __name__ == '__main__':
    model_name = sys.argv[1]  # 'glm' or 'qwen'
    prompt_name = sys.argv[2]  # e.g. 'v1_lower_threshold'

    # Load test set
    if model_name == 'glm':
        test_csv = f'{ROOT}/test_sets/glm_test_small.csv'
        prompt_file = f'{ROOT}/prompts/glm_{prompt_name}.md'
        model_path = paths['glm41v']
    else:
        test_csv = f'{ROOT}/test_sets/qwen_test_small.csv'
        prompt_file = f'{ROOT}/prompts/qwen_{prompt_name}.md'
        model_path = paths['qwen32b']

    with open(prompt_file) as f:
        prompt_text = f.read()
    test_df = pd.read_csv(test_csv)

    print(f'Model: {model_name}, Prompt: {prompt_name}, Test clips: {len(test_df)}')
    print(f'Ground truth distribution: {test_df["ground_truth"].value_counts().to_dict()}')

    # Load model
    print(f'Loading model from {model_path}...')
    t0 = time.time()
    if model_name == 'glm':
        from transformers import Glm4vForConditionalGeneration, Glm4vProcessor
        model = Glm4vForConditionalGeneration.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, device_map='auto', local_files_only=True)
        processor = Glm4vProcessor.from_pretrained(model_path, local_files_only=True)
    else:
        from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, device_map='auto', local_files_only=True)
        processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    print(f'Model loaded in {time.time()-t0:.0f}s, mem: {torch.cuda.memory_allocated(0)/1024**3:.1f} GB')

    # Run inference
    y_true, y_pred, details = [], [], []
    out_dir = f'{ROOT}/raw_outputs/{model_name}/{prompt_name}'
    os.makedirs(out_dir, exist_ok=True)

    for i, (_, row) in enumerate(test_df.iterrows()):
        aid = row['anchor_id']
        gt = row['ground_truth']
        cs_path = f'{PILOT_ROOT}/inputs/contact_sheets/{aid}.jpg'

        if not os.path.isfile(cs_path):
            print(f'  [{i+1}] {aid}: MISSING')
            y_true.append(gt); y_pred.append('parse_error')
            continue

        image = Image.open(cs_path).convert('RGB')
        messages = [{'role': 'user', 'content': [
            {'type': 'image', 'image': image},
            {'type': 'text', 'text': prompt_text}
        ]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], padding=True, return_tensors='pt')
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        torch.cuda.synchronize()
        t1 = time.time()
        with torch.no_grad():
            gen_ids = model.generate(
                **inputs,
                max_new_tokens=2048,
                temperature=dec_cfg['temperature'],
                do_sample=dec_cfg['do_sample'],
                top_p=dec_cfg['top_p'],
            )
        torch.cuda.synchronize()
        runtime = time.time() - t1

        gen_trimmed = gen_ids[0][len(inputs['input_ids'][0]):]
        raw = processor.decode(gen_trimmed, skip_special_tokens=True)
        parsed = parse_label(raw)
        pred = parsed.get('event_label', 'parse_error')

        y_true.append(gt)
        y_pred.append(pred)
        details.append({'anchor_id': aid, 'gt': gt, 'pred': pred, 'runtime': runtime})

        with open(f'{out_dir}/{aid}.json', 'w') as f:
            json.dump({'anchor_id': aid, 'prompt': prompt_name, 'raw_output': raw,
                       'parsed': parsed, 'runtime_seconds': runtime}, f, indent=2)

        sym = '✓' if pred == gt else '✗'
        print(f'  [{i+1}/{len(test_df)}] {aid}: gt={gt} pred={pred} {sym} ({runtime:.1f}s)')

    metrics = evaluate(y_true, y_pred)
    metrics['prompt'] = prompt_name
    metrics['model'] = model_name
    print(f'\n=== RESULT: {model_name} / {prompt_name} ===')
    print(f'Recall: {metrics["recall"]:.3f} ({metrics["tp"]}/{metrics["n_pos"]})')
    print(f'Precision: {metrics["precision"]:.3f} ({metrics["tp"]}/{metrics["tp"]+metrics["fp"]})')
    print(f'F1: {metrics["f1"]:.3f}')
    print(f'TP={metrics["tp"]} FP={metrics["fp"]} TN={metrics["tn"]} FN={metrics["fn"]}')

    # Save
    pd.DataFrame(details).to_csv(f'{ROOT}/tables/{model_name}_{prompt_name}_small.csv', index=False)
    with open(f'{ROOT}/tables/{model_name}_{prompt_name}_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f'\nDone. Total time: {time.time()-t0:.0f}s')
