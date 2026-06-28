#!/usr/bin/env python3
"""
Phase 1: Run GLM-4.1V with frozen BEST_glm_final.md on qwen_test_small.csv (held-out gate).
Usage: python3 run_glm_on_qwen_test.py
"""
import os, sys, yaml, json, time, re, argparse
import pandas as pd, numpy as np, torch
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUNING_ROOT = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/prompt_tuning_v1'
PILOT_ROOT = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1'

with open(f'{PILOT_ROOT}/config/model_paths.yaml') as f:
    paths = yaml.safe_load(f)
with open(f'{PILOT_ROOT}/config/decoding_config.yaml') as f:
    dec_cfg = yaml.safe_load(f)

def parse_label(raw):
    """Parse JSON event_label from raw GLM output, handling <think> tags."""
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


def has_think_tags(raw):
    return '<think>' in raw or '<thought>' in raw or '<｜end▁of▁thinking｜>' in raw


def evaluate_confusion(y_true, y_pred, preds_detailed):
    """Full confusion matrix with uncertain handling."""
    n = len(y_true)
    results = {
        'n_samples': n,
        'glm_positive': 0, 'glm_negative': 0, 'glm_uncertain': 0, 'glm_parse_error': 0,
        'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0,
        'tp_unc': 0, 'tn_unc': 0,  # uncertain treated as soft
    }
    for t, p in zip(y_true, y_pred):
        if p == 'positive':
            results['glm_positive'] += 1
            if t == 'positive': results['tp'] += 1
            else: results['fp'] += 1
        elif p == 'negative':
            results['glm_negative'] += 1
            if t == 'positive': results['fn'] += 1
            else: results['tn'] += 1
        elif p == 'uncertain':
            results['glm_uncertain'] += 1
            if t == 'positive': results['tp_unc'] += 1
            else: results['tn_unc'] += 1
        elif p == 'parse_error':
            results['glm_parse_error'] += 1

    n_pos = sum(1 for t in y_true if t == 'positive')
    n_neg = sum(1 for t in y_true if t == 'negative')

    results['n_pos'] = n_pos
    results['n_neg'] = n_neg
    results['glm_positive_rate'] = round(results['glm_positive'] / n, 4) if n > 0 else 0
    results['glm_uncertain_rate'] = round(results['glm_uncertain'] / n, 4) if n > 0 else 0
    results['parse_error_count'] = results['glm_parse_error']

    # Hard-set (uncertain = negative)
    tp_hard = results['tp']
    fp_hard = results['fp']
    fn_hard = results['fn'] + results['tp_unc']
    results['recall_hard'] = round(tp_hard / n_pos, 4) if n_pos > 0 else 0
    results['precision_hard'] = round(tp_hard / (tp_hard + fp_hard), 4) if (tp_hard + fp_hard) > 0 else 0
    results['f1_hard'] = round(2 * results['recall_hard'] * results['precision_hard'] /
                               (results['recall_hard'] + results['precision_hard']), 4) if (results['recall_hard'] + results['precision_hard']) > 0 else 0

    # Soft-set (positive + uncertain catch positives)
    covered_pos = results['tp'] + results['tp_unc']
    results['pos_plus_unc_recall'] = round(covered_pos / n_pos, 4) if n_pos > 0 else 0
    results['fn_strict'] = results['fn']  # GLM negative AND qwen positive (missed)

    # GLM negative中 Qwen-positive 数量
    results['qwen_pos_in_glm_neg'] = results['fn']

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-csv', default=f'{TUNING_ROOT}/test_sets/qwen_test_small.csv')
    parser.add_argument('--prompt', default=f'{TUNING_ROOT}/prompts/BEST_glm_final.md')
    parser.add_argument('--output-dir', default=f'{ROOT}/raw_outputs/glm_v1_on_qwen_test')
    parser.add_argument('--table-out', default=f'{ROOT}/tables/glm_v1_on_qwen_test.csv')
    parser.add_argument('--report-out', default=f'{ROOT}/reports/HEAD_TO_HEAD_GLM_V1_vs_QWEN_V3.md')
    parser.add_argument('--max-tokens', type=int, default=2048)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.table_out), exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    test_df = pd.read_csv(args.test_csv)
    model_path = paths['glm41v']

    with open(args.prompt) as f:
        prompt_text = f.read()

    print(f'=== Phase 1: GLM held-out gate on {len(test_df)} samples ===')
    print(f'Prompt: {args.prompt}')
    print(f'Test CSV: {args.test_csv}')
    print(f'Ground truth: {test_df["ground_truth"].value_counts().to_dict()}')
    print()

    # Load model
    print(f'Loading GLM-4.1V from {model_path}...')
    t0 = time.time()
    from transformers import Glm4vForConditionalGeneration, Glm4vProcessor
    model = Glm4vForConditionalGeneration.from_pretrained(
        model_path, torch_dtype=torch.bfloat16, device_map='auto', local_files_only=True)
    processor = Glm4vProcessor.from_pretrained(model_path, local_files_only=True)
    print(f'Loaded in {time.time()-t0:.0f}s, GPU mem: {torch.cuda.memory_allocated(0)/1024**3:.1f} GB')
    print()

    y_true, y_pred, rows = [], [], []

    for i, (_, row) in enumerate(test_df.iterrows()):
        aid = row['anchor_id']
        gt = row['ground_truth']
        cs_path = f'{PILOT_ROOT}/inputs/contact_sheets/{aid}.jpg'

        if not os.path.isfile(cs_path):
            print(f'  [{i+1}] {aid}: MISSING contact sheet')
            y_true.append(gt)
            y_pred.append('parse_error')
            rows.append({'anchor_id': aid, 'gt': gt, 'pred': 'parse_error',
                        'confidence': None, 'latency_s': 0, 'output_tokens': 0,
                        'has_think': False, 'parse_success': False,
                        'actor_type': None, 'interaction_type': None, 'ego_relevant': None})
            continue

        image = Image.open(cs_path).convert('RGB')
        messages = [{'role': 'user', 'content': [
            {'type': 'image', 'image': image},
            {'type': 'text', 'text': prompt_text}
        ]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], padding=True, return_tensors='pt')
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        input_len = inputs['input_ids'].shape[1]
        torch.cuda.synchronize()
        t1 = time.time()
        with torch.no_grad():
            gen_ids = model.generate(
                **inputs,
                max_new_tokens=args.max_tokens,
                temperature=dec_cfg['temperature'],
                do_sample=dec_cfg['do_sample'],
                top_p=dec_cfg['top_p'],
            )
        torch.cuda.synchronize()
        latency = time.time() - t1

        gen_trimmed = gen_ids[0][input_len:]
        raw = processor.decode(gen_trimmed, skip_special_tokens=True)
        output_tokens = len(gen_trimmed)
        parsed = parse_label(raw)
        pred = parsed.get('event_label', 'parse_error')
        confidence = parsed.get('confidence', None)
        has_think = has_think_tags(raw)

        y_true.append(gt)
        y_pred.append(pred)

        rows.append({
            'anchor_id': aid, 'gt': gt, 'pred': pred,
            'confidence': confidence,
            'latency_s': round(latency, 3),
            'output_tokens': output_tokens,
            'has_think': has_think,
            'parse_success': pred != 'parse_error',
            'actor_type': parsed.get('primary_actor_type'),
            'interaction_type': parsed.get('interaction_type'),
            'ego_relevant': parsed.get('ego_relevant'),
        })

        with open(f'{args.output_dir}/{aid}.json', 'w') as f:
            json.dump({
                'anchor_id': aid, 'prompt': 'BEST_glm_final',
                'raw_output': raw, 'parsed': parsed,
                'latency_s': latency, 'output_tokens': output_tokens,
                'has_think': has_think, 'max_new_tokens': args.max_tokens
            }, f, indent=2)

        sym = '✓' if pred == gt else ('?' if pred in ('uncertain', 'parse_error') else '✗')
        print(f'  [{i+1}/{len(test_df)}] {aid}: gt={gt} pred={pred} {sym} ({latency:.1f}s, {output_tokens} tok)')

    # Evaluate
    metrics = evaluate_confusion(y_true, y_pred, rows)

    # Latency stats
    latencies = [r['latency_s'] for r in rows if r['latency_s'] > 0]
    if latencies:
        metrics['avg_latency_s'] = round(np.mean(latencies), 2)
        metrics['p50_latency_s'] = round(np.percentile(latencies, 50), 2)
        metrics['p95_latency_s'] = round(np.percentile(latencies, 95), 2)
        metrics['min_latency_s'] = round(np.min(latencies), 2)
        metrics['max_latency_s'] = round(np.max(latencies), 2)
    else:
        metrics['avg_latency_s'] = None

    token_counts = [r['output_tokens'] for r in rows if r['output_tokens'] > 0]
    if token_counts:
        metrics['avg_output_tokens'] = round(np.mean(token_counts), 1)
        metrics['p50_output_tokens'] = round(np.percentile(token_counts, 50), 1)
        metrics['p95_output_tokens'] = round(np.percentile(token_counts, 95), 1)

    metrics['has_think_count'] = sum(1 for r in rows if r['has_think'])

    # Save table
    df_out = pd.DataFrame(rows)
    df_out.to_csv(args.table_out, index=False)
    print(f'\nSaved: {args.table_out}')

    # Gate check
    n_pos = metrics['n_pos']
    covered = metrics['pos_plus_unc_recall'] * n_pos
    missed_in_neg = metrics['qwen_pos_in_glm_neg']
    parse_err = metrics['parse_error_count']

    print(f'\n=== GATE CHECK ===')
    print(f'Qwen positives: {n_pos}')
    print(f'GLM positive+uncertain covers: {covered}/{n_pos} ({metrics["pos_plus_unc_recall"]:.1%})')
    print(f'GLM negative contains Qwen-positives: {missed_in_neg}')
    print(f'Parse errors: {parse_err}')
    print(f'Avg latency: {metrics.get("avg_latency_s", "N/A")}s')

    # Rate-based gate (adapts to n_pos)
    recall_rate = covered / n_pos if n_pos > 0 else 0
    precision_hard = metrics['precision_hard']
    if recall_rate >= 0.8 and missed_in_neg <= max(1, n_pos * 0.2) and parse_err <= 1 and precision_hard >= 0.25:
        gate = 'PASS'
    elif recall_rate >= 0.6:
        gate = 'BORDERLINE'
    else:
        gate = 'FAIL'

    print(f'\nGATE: GLM_TEST_GATE_{gate}')

    # Write report
    report = f"""# GLM-4.1V (BEST prompt) vs Qwen3-VL-32B Reference — Held-Out Gate

**Date**: 2026-06-26
**Test set**: qwen_test_small.csv (10 samples: {n_pos} positive, {metrics['n_neg']} negative)
**GLM prompt**: BEST_glm_final.md (v1_lower_threshold, tuning F1=0.706 on GLM test set)
**Status**: Held-out — GLM was NOT tuned on these samples

---

## Confusion Matrix

| GLM → / Qwen ↓ | positive | negative | uncertain | parse_error |
|-----------------|----------|----------|-----------|-------------|
| positive ({n_pos}) | {metrics['tp']} | {metrics['fn']} | {metrics['tp_unc']} | — |
| negative ({metrics['n_neg']}) | {metrics['fp']} | {metrics['tn']} | {metrics['tn_unc']} | — |

## Metrics

| Metric | Value |
|--------|-------|
| GLM positive rate | {metrics['glm_positive_rate']:.1%} |
| GLM negative rate | {round(metrics['glm_negative']/(metrics['n_samples']),1):.1%} |
| GLM uncertain rate | {metrics['glm_uncertain_rate']:.1%} |
| Parse error count | {metrics['parse_error_count']} |
| **Recall (positive only)** | {metrics['recall_hard']:.1%} ({metrics['tp']}/{n_pos}) |
| **Recall (positive+uncertain)** | {metrics['pos_plus_unc_recall']:.1%} ({covered}/{n_pos}) |
| **Qwen-positive in GLM negative** | {metrics['qwen_pos_in_glm_neg']} |
| Precision (positive only) | {metrics['precision_hard']:.1%} |
| F1 (positive only) | {metrics['f1_hard']:.3f} |

## Latency

| Stat | Value |
|------|-------|
| Avg latency | {metrics.get('avg_latency_s', 'N/A')}s |
| P50 latency | {metrics.get('p50_latency_s', 'N/A')}s |
| P95 latency | {metrics.get('p95_latency_s', 'N/A')}s |
| Avg output tokens | {metrics.get('avg_output_tokens', 'N/A')} |
| Contains `think` tags | {metrics['has_think_count']}/{metrics['n_samples']} |

## Per-Sample Details

```
"""
    for r in rows:
        sym = '✓' if r['pred'] == r['gt'] else '✗'
        report += f"  {r['anchor_id']}: gt={r['gt']} pred={r['pred']} conf={r['confidence']} {sym} ({r['latency_s']:.1f}s, {r['output_tokens']} tok)\n"

    report += "```\n\n## Gate Decision\n\n"
    report += f"**GATE: GLM_TEST_GATE_{gate}**\n\n"
    report += f"- Qwen positives covered by GLM positive+uncertain: {covered}/{n_pos}\n"
    report += f"- Qwen-positives missed in GLM negative: {missed_in_neg}\n"
    report += f"- Parse errors: {parse_err}\n"

    if gate == 'PASS':
        report += "\nGate PASS — eligible to proceed to Phase 2 (123-sample pilot).\n"
    elif gate == 'BORDERLINE':
        report += "\nGate BORDERLINE — may proceed with analysis report but risks noted.\n"
    else:
        report += "\nGate FAIL — STOP: do not expand to 123-sample pilot.\n"

    report += f"\nGLM model: {model_path}\n"
    report += f"Contact sheets: {PILOT_ROOT}/inputs/contact_sheets/\n"
    report += f"Raw outputs: {args.output_dir}/\n"

    with open(args.report_out, 'w') as f:
        f.write(report)
    print(f'Saved: {args.report_out}')

    # Save metrics JSON
    with open(f'{ROOT}/tables/glm_v1_on_qwen_test_metrics.json', 'w') as f:
        metrics['gate'] = gate
        json.dump(metrics, f, indent=2)

    print(f'\nDone. Total time: {time.time()-t0:.0f}s')
