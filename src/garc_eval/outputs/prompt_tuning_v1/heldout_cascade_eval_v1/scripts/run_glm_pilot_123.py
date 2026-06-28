#!/usr/bin/env python3
"""
Phase 2: Run GLM-4.1V with frozen BEST_glm_final.md on 123 pilot samples.
Compares against existing Qwen reference from old pilot.
Usage: python3 run_glm_pilot_123.py
"""
import os, sys, yaml, json, time, re, argparse
import pandas as pd, numpy as np, torch
from PIL import Image
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUNING_ROOT = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/prompt_tuning_v1'
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


def has_think_tags(raw):
    return '<think>' in raw or '<thought>' in raw or '<｜end▁of▁thinking｜>' in raw


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompt', default=f'{TUNING_ROOT}/prompts/BEST_glm_final.md')
    parser.add_argument('--output-dir', default=f'{ROOT}/raw_outputs/glm_v1_pilot_123')
    parser.add_argument('--table-out', default=f'{ROOT}/tables/glm_v1_pilot_123_outputs.csv')
    parser.add_argument('--report-out', default=f'{ROOT}/reports/BEST_PROMPT_PILOT_REPORT.md')
    parser.add_argument('--max-tokens', type=int, default=2048)
    parser.add_argument('--skip-existing', action='store_true', default=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.table_out), exist_ok=True)

    # Load Qwen reference from old pilot
    paired_df = pd.read_csv(f'{PILOT_ROOT}/tables/paired_predictions.csv')
    print(f'Qwen reference: {len(paired_df)} entries loaded')

    # Load prompt
    with open(args.prompt) as f:
        prompt_text = f.read()
    print(f'Prompt: {args.prompt}')

    # Filter to entries with contact sheets and Qwen labels
    valid = []
    for _, row in paired_df.iterrows():
        aid = row['anchor_id']
        cs_path = f'{PILOT_ROOT}/inputs/contact_sheets/{aid}.jpg'
        if os.path.isfile(cs_path) and pd.notna(row.get('qwen_label')):
            valid.append(row)
    print(f'Valid entries (contact sheet + Qwen label): {len(valid)}')

    # Load model
    print(f'\nLoading GLM-4.1V...')
    t0 = time.time()
    from transformers import Glm4vForConditionalGeneration, Glm4vProcessor
    model_path = paths['glm41v']
    model = Glm4vForConditionalGeneration.from_pretrained(
        model_path, torch_dtype=torch.bfloat16, device_map='auto', local_files_only=True)
    processor = Glm4vProcessor.from_pretrained(model_path, local_files_only=True)
    print(f'Loaded in {time.time()-t0:.0f}s, GPU mem: {torch.cuda.memory_allocated(0)/1024**3:.1f} GB\n')

    rows = []
    n_total = len(valid)

    for i, row in enumerate(valid):
        aid = row['anchor_id']
        qwen_label = str(row['qwen_label']).strip().lower() if pd.notna(row.get('qwen_label')) else 'unknown'
        gt = 'positive' if row.get('is_positive') == 'True' or row.get('is_positive') == True else 'negative'
        is_pos = row.get('is_positive') == 'True' or row.get('is_positive') == True
        cluster_id = row.get('event_cluster_id', -1)
        is_singleton = row.get('is_singleton_cluster', False)
        proxy_score = row.get('proxy_score', float('nan'))
        object_count_mean = row.get('object_count_mean', float('nan'))
        cs_path = f'{PILOT_ROOT}/inputs/contact_sheets/{aid}.jpg'

        # Check if already done
        out_json = f'{args.output_dir}/{aid}.json'
        if args.skip_existing and os.path.isfile(out_json):
            with open(out_json) as f:
                cached = json.load(f)
            pred = cached.get('parsed', {}).get('event_label', 'parse_error')
            latency = cached.get('latency_s', 0)
            output_tokens = cached.get('output_tokens', 0)
            raw = cached.get('raw_output', '')
            has_think = cached.get('has_think', False)
            confidence = cached.get('parsed', {}).get('confidence')
            actor_type = cached.get('parsed', {}).get('primary_actor_type')
            interaction_type = cached.get('parsed', {}).get('interaction_type')
            ego_relevant = cached.get('parsed', {}).get('ego_relevant')
            print(f'  [{i+1}/{n_total}] {aid}: (cached) gt={gt} pred={pred}')
        else:
            if not os.path.isfile(cs_path):
                print(f'  [{i+1}/{n_total}] {aid}: MISSING contact sheet')
                pred = 'parse_error'
                latency = 0
                output_tokens = 0
                raw = ''
                has_think = False
                confidence = None
                actor_type = None
                interaction_type = None
                ego_relevant = None
            else:
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
                confidence = parsed.get('confidence')
                has_think = has_think_tags(raw)
                actor_type = parsed.get('primary_actor_type')
                interaction_type = parsed.get('interaction_type')
                ego_relevant = parsed.get('ego_relevant')

                with open(out_json, 'w') as f:
                    json.dump({
                        'anchor_id': aid, 'prompt': 'BEST_glm_final',
                        'raw_output': raw, 'parsed': parsed,
                        'latency_s': latency, 'output_tokens': output_tokens,
                        'has_think': has_think, 'max_new_tokens': args.max_tokens
                    }, f, indent=2)

                sym = '✓' if pred == gt else ('?' if pred in ('uncertain', 'parse_error') else '✗')
                print(f'  [{i+1}/{n_total}] {aid}: gt={gt} pred={pred} {sym} ({latency:.1f}s, {output_tokens} tok)')

        rows.append({
            'anchor_id': aid,
            'is_positive': is_pos,
            'qwen_label': qwen_label,
            'event_cluster_id': cluster_id,
            'is_singleton_cluster': is_singleton,
            'proxy_score': proxy_score,
            'object_count_mean': object_count_mean,
            'glm_pred': pred,
            'glm_confidence': confidence,
            'glm_actor_type': actor_type,
            'glm_interaction_type': interaction_type,
            'glm_ego_relevant': ego_relevant,
            'latency_s': round(latency, 3),
            'output_tokens': output_tokens,
            'has_think': has_think,
        })

    # Save outputs table
    df_out = pd.DataFrame(rows)
    df_out.to_csv(args.table_out, index=False)
    print(f'\nSaved: {args.table_out} ({len(df_out)} rows)')

    # ============ COMPUTE METRICS ============
    n = len(df_out)
    valid_mask = df_out['glm_pred'] != 'parse_error'
    n_valid = valid_mask.sum()
    n_pos = df_out['is_positive'].sum()
    n_neg = n - n_pos

    tp = sum(df_out['is_positive'] & (df_out['glm_pred'] == 'positive'))
    fp = sum(~df_out['is_positive'] & (df_out['glm_pred'] == 'positive'))
    tn = sum(~df_out['is_positive'] & (df_out['glm_pred'] == 'negative'))
    fn = sum(df_out['is_positive'] & (df_out['glm_pred'] == 'negative'))
    tp_unc = sum(df_out['is_positive'] & (df_out['glm_pred'] == 'uncertain'))
    tn_unc = sum(~df_out['is_positive'] & (df_out['glm_pred'] == 'uncertain'))
    parse_err = sum(df_out['glm_pred'] == 'parse_error')

    glm_pos = sum(df_out['glm_pred'] == 'positive')
    glm_neg = sum(df_out['glm_pred'] == 'negative')
    glm_unc = sum(df_out['glm_pred'] == 'uncertain')

    print(f'\n=== 123-PILOT RESULTS ===')
    print(f'Total: {n}, Valid: {n_valid}, Parse errors: {parse_err}')
    print(f'Qwen reference: {n_pos} pos, {n_neg} neg')
    print(f'GLM: {glm_pos} pos, {glm_neg} neg, {glm_unc} uncertain')

    # Hard-set metrics (uncertain = negative)
    fn_hard = fn + tp_unc
    recall_hard = tp / n_pos if n_pos > 0 else 0
    precision_hard = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1_hard = 2 * recall_hard * precision_hard / (recall_hard + precision_hard) if (recall_hard + precision_hard) > 0 else 0

    # Soft recall (positive + uncertain covers Qwen-positives)
    covered_pos = tp + tp_unc
    recall_soft = covered_pos / n_pos if n_pos > 0 else 0

    # Qwen-positive rate by GLM bin
    for bin_name, mask in [('positive', df_out['glm_pred']=='positive'),
                            ('uncertain', df_out['glm_pred']=='uncertain'),
                            ('negative', df_out['glm_pred']=='negative')]:
        in_bin = mask.sum()
        pos_in_bin = (mask & df_out['is_positive']).sum()
        print(f'  GLM {bin_name}: {in_bin} clips, {pos_in_bin} Qwen-pos ({pos_in_bin/in_bin:.1%} pos rate)' if in_bin > 0 else f'  GLM {bin_name}: 0 clips')

    # Latency
    lats = df_out[df_out['latency_s'] > 0]['latency_s']
    print(f'\nLatency: avg={lats.mean():.1f}s p50={lats.quantile(0.5):.1f}s p95={lats.quantile(0.95):.1f}s')
    print(f'Output tokens: avg={df_out[df_out["output_tokens"]>0]["output_tokens"].mean():.0f}')
    print(f'Hit max_tokens ({args.max_tokens}): {sum(df_out["output_tokens"] >= args.max_tokens)}')

    # Cluster recall
    clusters = df_out[df_out['event_cluster_id'] >= 0]['event_cluster_id'].unique()
    n_clusters = len(clusters)
    clusters_covered = 0
    singleton_clusters = []
    for cid in clusters:
        cluster_mask = df_out['event_cluster_id'] == cid
        is_singleton = df_out[cluster_mask]['is_singleton_cluster'].iloc[0]
        if is_singleton:
            singleton_clusters.append(cid)
        any_hit = df_out[cluster_mask & (df_out['glm_pred'].isin(['positive', 'uncertain']))].shape[0] > 0
        if any_hit:
            clusters_covered += 1
    n_singleton = len(singleton_clusters)
    singleton_hit = sum(1 for cid in singleton_clusters
                        if df_out[(df_out['event_cluster_id']==cid) & (df_out['glm_pred'].isin(['positive', 'uncertain']))].shape[0] > 0)

    print(f'\nEvent clusters: {n_clusters} total, {n_singleton} singleton')
    print(f'Cluster recall (GLM pos+unc): {clusters_covered}/{n_clusters} = {clusters_covered/n_clusters:.3f}' if n_clusters > 0 else '')
    print(f'Singleton recall: {singleton_hit}/{n_singleton} = {singleton_hit/n_singleton:.3f}' if n_singleton > 0 else '')

    # Per-bin analysis
    # Low proxy singletons in GLM negative
    if 'proxy_score' in df_out.columns:
        df_valid = df_out[valid_mask].copy()
        proxy_median = df_valid['proxy_score'].median()
        low_proxy_fn = sum(df_valid['is_positive'] & (df_valid['glm_pred']=='negative') & (df_valid['proxy_score'] < proxy_median))
        print(f'\nQwen-pos in GLM neg with low proxy (<{proxy_median:.2f}): {low_proxy_fn}')

    # ============ WRITE REPORT ============
    report = f"""# GLM-4.1V (BEST prompt) on 123-Sample Pilot — Held-Out Validation

**Date**: 2026-06-26
**GLM prompt**: BEST_glm_final.md (v1_lower_threshold, tuning F1=0.706 on GLM test set)
**Qwen reference**: Old pilot (oracle_prompt_v1.md = Qwen v0_original), 123 contact sheets
**Status**: Held-out — GLM was NOT tuned on these samples. Qwen reference reused from old pilot.

---

## 1. Summary Metrics

| Metric | Value |
|--------|-------|
| Samples | {n} |
| Valid (GLM parsed) | {n_valid} ({n_valid/n:.1%}) |
| Parse errors | {parse_err} ({parse_err/n:.1%}) |
| Qwen reference positives | {n_pos} |
| Qwen reference negatives | {n_neg} |

## 2. Confusion Matrix (GLM vs Qwen Reference)

| GLM → / Qwen ↓ | positive | negative | uncertain | parse_error |
|-----------------|----------|----------|-----------|-------------|
| positive ({n_pos}) | {tp} | {fn} | {tp_unc} | — |
| negative ({n_neg}) | {fp} | {tn} | {tn_unc} | — |

## 3. A. Balanced / Hard-Set Metrics

| Metric | Value |
|--------|-------|
| GLM positive rate | {glm_pos/n:.1%} ({glm_pos}/{n}) |
| GLM negative rate | {glm_neg/n:.1%} ({glm_neg}/{n}) |
| GLM uncertain rate | {glm_unc/n:.1%} ({glm_unc}/{n}) |
| Recall (positive only) | {recall_hard:.1%} ({tp}/{n_pos}) |
| Precision (positive only) | {precision_hard:.1%} ({tp}/{tp+fp}) |
| F1 (positive only) | {f1_hard:.3f} |
| False positive rate (on negatives) | {fp/n_neg:.1%} ({fp}/{n_neg}) |

## 4. B. AQP / Cascade-Relevant Metrics

| Metric | Value |
|--------|-------|
| GLM pos+unc recall of Qwen-pos | {recall_soft:.1%} ({covered_pos}/{n_pos}) |
| Qwen-positives in GLM negative | {fn} |
| GLM negative false-negative rate | {fn/n_pos:.1%} |
| Qwen positive rate in GLM positive bin | {(tp/(tp+fp) if tp+fp>0 else 0):.1%} |
| Qwen positive rate in GLM uncertain bin | {(tp_unc/(tp_unc+tn_unc) if tp_unc+tn_unc>0 else 0):.1%} |
| Qwen positive rate in GLM negative bin | {(fn/(fn+tn) if fn+tn>0 else 0):.1%} |

## 5. Latency and Cost

| Metric | Value |
|--------|-------|
| Avg latency | {lats.mean():.1f}s |
| P50 latency | {lats.quantile(0.5):.1f}s |
| P95 latency | {lats.quantile(0.95):.1f}s |
| Avg output tokens | {df_out[df_out['output_tokens']>0]['output_tokens'].mean():.0f} |
| Hit max_tokens ({args.max_tokens}) | {sum(df_out['output_tokens'] >= args.max_tokens)} |
| Peak GPU memory | ~19.2 GB |

## 6. Event-Cluster Analysis

| Metric | Value |
|--------|-------|
| Event clusters | {n_clusters} |
| Singleton clusters | {n_singleton} |
| Cluster recall (GLM pos+unc) | {clusters_covered}/{n_clusters} = {clusters_covered/n_clusters:.3f} |
| Singleton recall | {singleton_hit}/{n_singleton} = {singleton_hit/n_singleton:.3f} |

## 7. Phase 2 Decision

"""

    # Decision logic
    if recall_soft >= 0.85 and fn <= max(3, n_pos * 0.15):
        decision = 'GLM_ROUTER_CANDIDATE'
        rationale = 'High Qwen-positive recall, few missed in GLM negative'
    elif precision_hard >= 0.7 and recall_soft < 0.85:
        decision = 'GLM_BOOSTER_ONLY'
        rationale = 'High precision but insufficient recall for routing'
    elif recall_soft >= 0.5:
        decision = 'GLM_DISAGREEMENT_SIGNAL_ONLY'
        rationale = 'GLM/Qwen disagreement enriches missed positives but recall insufficient'
    else:
        decision = 'GLM_NOT_USEFUL'
        rationale = 'Held-out performance significantly worse than tuning'

    report += f"**DECISION: {decision}**\n\n"
    report += f"**Rationale**: {rationale}\n\n"

    report += f"""
## 8. Key Observations

- GLM positive rate: {glm_pos/n:.1%} vs Qwen positive rate: {n_pos/n:.1%}
- GLM uncertain rate: {glm_unc/n:.1%} — {'high enough to be useful for triage' if glm_unc/n > 0.05 else 'too low for meaningful triage'}
- Qwen-positives in GLM negative: {fn} ({fn/n_pos:.1%} of all positives)
- Parse error rate: {parse_err/n:.1%}
- GLM latency: {lats.mean():.1f}s avg vs Qwen ~12s avg (from old pilot)

## 9. Limitations

1. Qwen reference uses OLD prompt (oracle_prompt_v1.md, v0_original), not BEST_qwen_final.md
2. Qwen v0 is known to have high false-positive rate (~80%)
3. Some Qwen reference "positives" may be false positives
4. No human adjudication
5. Single video (dataset3)

---

*Generated by run_glm_pilot_123.py on {time.strftime('%Y-%m-%d %H:%M')}*
"""
    with open(args.report_out, 'w') as f:
        f.write(report)
    print(f'Saved: {args.report_out}')

    # Save metrics
    metrics = {
        'n': n, 'n_valid': n_valid, 'n_pos': n_pos, 'n_neg': n_neg,
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn, 'tp_unc': tp_unc, 'tn_unc': tn_unc,
        'parse_err': parse_err, 'glm_pos': glm_pos, 'glm_neg': glm_neg, 'glm_unc': glm_unc,
        'recall_hard': recall_hard, 'precision_hard': precision_hard, 'f1_hard': f1_hard,
        'recall_soft': recall_soft, 'avg_latency': lats.mean() if len(lats) > 0 else 0,
        'p50_latency': lats.quantile(0.5) if len(lats) > 0 else 0,
        'p95_latency': lats.quantile(0.95) if len(lats) > 0 else 0,
        'cluster_recall': clusters_covered / n_clusters if n_clusters > 0 else 0,
        'singleton_recall': singleton_hit / n_singleton if n_singleton > 0 else 0,
        'decision': decision,
        'rationale': rationale,
    }
    with open(f'{ROOT}/tables/glm_v1_pilot_123_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f'\nDone. Total time: {time.time()-t0:.0f}s')
    print(f'Decision: {decision}')
