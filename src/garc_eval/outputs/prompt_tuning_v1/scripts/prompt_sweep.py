#!/usr/bin/env python3
"""
Prompt sweep: test multiple prompt variants on GLM and Qwen.
GLM test set: 38 clips (19 pos, 19 neg) - mostly missed cases
Qwen test set: 36 clips (2 pos, 34 neg) - mostly false positive cases
"""
import os, sys, yaml, json, time, re, gc, glob
import pandas as pd, numpy as np, torch
from PIL import Image
from datetime import datetime

ROOT = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/prompt_tuning_v1'
PILOT_ROOT = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1'

with open(f'{PILOT_ROOT}/config/model_paths.yaml') as f:
    paths = yaml.safe_load(f)
with open(f'{PILOT_ROOT}/config/decoding_config.yaml') as f:
    dec_cfg = yaml.safe_load(f)

# ============================================================
# Utility: parse JSON from model output
# ============================================================
def parse_label(raw: str) -> dict:
    """Extract event_label from raw model output."""
    # Try to find JSON block
    jsons = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw)
    for j_str in reversed(jsons):
        try:
            j = json.loads(j_str)
            if 'event_label' in j:
                return j
        except:
            continue
    # Try answer tags
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
    """Compute metrics."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 'positive' and p == 'positive')
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 'negative' and p == 'positive')
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 'negative' and p == 'negative')
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 'positive' and p == 'negative')
    n_pos = sum(1 for t in y_true if t == 'positive')
    n_neg = sum(1 for t in y_true if t == 'negative')
    recall = tp / n_pos if n_pos > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return {
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'n_pos': n_pos, 'n_neg': n_neg,
        'recall': round(recall, 4),
        'precision': round(precision, 4),
        'f1': round(f1, 4),
    }

# ============================================================
# GLM runner
# ============================================================
def run_glm(prompt_variants, test_csv):
    """Test GLM with each prompt variant."""
    print('\n' + '='*60)
    print('GLM-4.1V PROMPT SWEEP')
    print('='*60)

    model_path = paths['glm41v']
    print(f'Loading GLM-4.1V from {model_path}...')
    from transformers import Glm4vForConditionalGeneration, Glm4vProcessor
    t0 = time.time()
    model = Glm4vForConditionalGeneration.from_pretrained(
        model_path, torch_dtype=torch.bfloat16, device_map='auto', local_files_only=True)
    processor = Glm4vProcessor.from_pretrained(model_path, local_files_only=True)
    print(f'Model loaded in {time.time()-t0:.0f}s, mem: {torch.cuda.memory_allocated(0)/1024**3:.1f} GB')

    test_df = pd.read_csv(test_csv)
    results_all = []

    for pname, pfile in prompt_variants.items():
        print(f'\n--- Prompt: {pname} ---')
        with open(pfile) as f:
            prompt_text = f.read()

        y_true, y_pred, details = [], [], []
        out_dir = f'{ROOT}/raw_outputs/glm/{pname}'
        os.makedirs(out_dir, exist_ok=True)

        for i, (_, row) in enumerate(test_df.iterrows()):
            aid = row['anchor_id']
            gt = row['ground_truth']
            cs_path = f'{PILOT_ROOT}/inputs/contact_sheets/{aid}.jpg'

            if not os.path.isfile(cs_path):
                print(f'  [{i+1}] {aid}: contact sheet missing')
                y_true.append(gt); y_pred.append('parse_error')
                details.append({'anchor_id': aid, 'gt': gt, 'pred': 'parse_error', 'raw': ''})
                continue

            try:
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
                        max_new_tokens=dec_cfg['max_new_tokens'],
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
                details.append({'anchor_id': aid, 'gt': gt, 'pred': pred, 'raw': raw[:500], 'runtime': runtime})

                # Save raw output
                with open(f'{out_dir}/{aid}.json', 'w') as f:
                    json.dump({'anchor_id': aid, 'model': 'GLM-4.1V', 'prompt': pname,
                               'raw_output': raw, 'parsed': parsed, 'runtime_seconds': runtime}, f, indent=2)

                sym = '✓' if pred == gt else '✗'
                print(f'  [{i+1}/{len(test_df)}] {aid}: gt={gt} pred={pred} {sym} ({runtime:.1f}s)')

            except Exception as e:
                print(f'  [{i+1}] {aid}: ERROR {e}')
                y_true.append(gt); y_pred.append('parse_error')
                details.append({'anchor_id': aid, 'gt': gt, 'pred': 'parse_error', 'raw': str(e)})

        metrics = evaluate(y_true, y_pred)
        metrics['prompt'] = pname
        metrics['model'] = 'GLM-4.1V'
        results_all.append(metrics)
        print(f'\n  Result: recall={metrics["recall"]:.3f} precision={metrics["precision"]:.3f} f1={metrics["f1"]:.3f}')
        print(f'  TP={metrics["tp"]} FP={metrics["fp"]} TN={metrics["tn"]} FN={metrics["fn"]}')

        # Save details
        pd.DataFrame(details).to_csv(f'{ROOT}/tables/glm_{pname}_details.csv', index=False)

        # Free memory between prompts
        gc.collect()
        torch.cuda.empty_cache()

    # Save summary
    summary = pd.DataFrame(results_all)
    summary.to_csv(f'{ROOT}/tables/glm_prompt_sweep.csv', index=False)
    print('\n' + '='*60)
    print('GLM SUMMARY:')
    print(summary[['prompt', 'recall', 'precision', 'f1', 'tp', 'fp', 'tn', 'fn']].to_string(index=False))
    return summary

# ============================================================
# Qwen runner
# ============================================================
def run_qwen(prompt_variants, test_csv):
    """Test Qwen with each prompt variant."""
    print('\n' + '='*60)
    print('Qwen3-VL-32B PROMPT SWEEP')
    print('='*60)

    model_path = paths['qwen32b']
    print(f'Loading Qwen3-VL-32B from {model_path}...')
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
    t0 = time.time()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path, torch_dtype=torch.bfloat16, device_map='auto', local_files_only=True)
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    print(f'Model loaded in {time.time()-t0:.0f}s, mem: {torch.cuda.memory_allocated(0)/1024**3:.1f} GB')

    test_df = pd.read_csv(test_csv)
    results_all = []

    for pname, pfile in prompt_variants.items():
        print(f'\n--- Prompt: {pname} ---')
        with open(pfile) as f:
            prompt_text = f.read()

        y_true, y_pred, details = [], [], []
        out_dir = f'{ROOT}/raw_outputs/qwen/{pname}'
        os.makedirs(out_dir, exist_ok=True)

        for i, (_, row) in enumerate(test_df.iterrows()):
            aid = row['anchor_id']
            gt = row['ground_truth']
            cs_path = f'{PILOT_ROOT}/inputs/contact_sheets/{aid}.jpg'

            if not os.path.isfile(cs_path):
                print(f'  [{i+1}] {aid}: contact sheet missing')
                y_true.append(gt); y_pred.append('parse_error')
                details.append({'anchor_id': aid, 'gt': gt, 'pred': 'parse_error', 'raw': ''})
                continue

            try:
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
                        max_new_tokens=dec_cfg['max_new_tokens'],
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
                details.append({'anchor_id': aid, 'gt': gt, 'pred': pred, 'raw': raw[:500], 'runtime': runtime})

                with open(f'{out_dir}/{aid}.json', 'w') as f:
                    json.dump({'anchor_id': aid, 'model': 'Qwen3-VL-32B', 'prompt': pname,
                               'raw_output': raw, 'parsed': parsed, 'runtime_seconds': runtime}, f, indent=2)

                sym = '✓' if pred == gt else '✗'
                print(f'  [{i+1}/{len(test_df)}] {aid}: gt={gt} pred={pred} {sym} ({runtime:.1f}s)')

            except Exception as e:
                print(f'  [{i+1}] {aid}: ERROR {e}')
                y_true.append(gt); y_pred.append('parse_error')
                details.append({'anchor_id': aid, 'gt': gt, 'pred': 'parse_error', 'raw': str(e)})

        metrics = evaluate(y_true, y_pred)
        metrics['prompt'] = pname
        metrics['model'] = 'Qwen3-VL-32B'
        results_all.append(metrics)
        print(f'\n  Result: recall={metrics["recall"]:.3f} precision={metrics["precision"]:.3f} f1={metrics["f1"]:.3f}')
        print(f'  TP={metrics["tp"]} FP={metrics["fp"]} TN={metrics["tn"]} FN={metrics["fn"]}')

        pd.DataFrame(details).to_csv(f'{ROOT}/tables/qwen_{pname}_details.csv', index=False)
        gc.collect()
        torch.cuda.empty_cache()

    summary = pd.DataFrame(results_all)
    summary.to_csv(f'{ROOT}/tables/qwen_prompt_sweep.csv', index=False)
    print('\n' + '='*60)
    print('QWEN SUMMARY:')
    print(summary[['prompt', 'recall', 'precision', 'f1', 'tp', 'fp', 'tn', 'fn']].to_string(index=False))
    return summary

# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    model = sys.argv[1] if len(sys.argv) > 1 else 'both'

    glm_prompts = {
        'v0_original': f'{ROOT}/prompts/glm_v0_original.md',
        'v1_lower_threshold': f'{ROOT}/prompts/glm_v1_lower_threshold.md',
        'v2_examples': f'{ROOT}/prompts/glm_v2_examples.md',
        'v3_direct': f'{ROOT}/prompts/glm_v3_direct.md',
    }
    qwen_prompts = {
        'v0_original': f'{ROOT}/prompts/qwen_v0_original.md',
        'v1_stricter_spatial': f'{ROOT}/prompts/qwen_v1_stricter_spatial.md',
        'v2_no_false_alarm': f'{ROOT}/prompts/qwen_v2_no_false_alarm.md',
        'v3_two_step': f'{ROOT}/prompts/qwen_v3_two_step.md',
    }

    glm_test = f'{ROOT}/test_sets/glm_test_set.csv'
    qwen_test = f'{ROOT}/test_sets/qwen_test_set.csv'

    print(f'Start time: {datetime.now().isoformat()}')
    print(f'Models to test: {model}')

    if model in ('glm', 'both'):
        glm_summary = run_glm(glm_prompts, glm_test)

    if model in ('qwen', 'both'):
        qwen_summary = run_qwen(qwen_prompts, qwen_test)

    print(f'\nEnd time: {datetime.now().isoformat()}')
