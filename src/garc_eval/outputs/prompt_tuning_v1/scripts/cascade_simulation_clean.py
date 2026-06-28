#!/usr/bin/env python3
"""
Clean-pool cascade simulation: N=100 (tuning overlap removed).
Runs all 7 strategies at B=20,30,40,60,80,100 on clean pool.
Also produces relative-budget alignment and cluster/singleton metrics.
"""
import os, sys, json, warnings
import pandas as pd, numpy as np
from collections import defaultdict

warnings.filterwarnings('ignore')

OUTDIR = '/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/prompt_tuning_v1/heldout_cascade_eval_v1'
CANON_CSV = '/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv'


def load_clean_pool():
    """Load clean pool from saved anchor IDs + merge proxy features."""
    anchor_ids = pd.read_csv(f'{OUTDIR}/clean_pool_anchor_ids.csv')
    pilot = pd.read_csv(f'{OUTDIR}/tables/glm_v1_pilot_123_outputs.csv')
    df = pilot[pilot['anchor_id'].isin(anchor_ids['anchor_id'])].copy()

    # Merge canonical features
    canon = pd.read_csv(CANON_CSV)
    canon_cols = ['anchor_id', 'center_time_s', 'object_count_mean',
                  'score_fusion_geometry_motion', 'score_yolo_count',
                  'motion_energy_mean', 'event_cluster_id']
    canon_sub = canon[canon_cols].copy()
    canon_sub = canon_sub.rename(columns={'event_cluster_id': 'canon_cluster_id'})
    df = df.merge(canon_sub, on='anchor_id', how='left', suffixes=('', '_canon'))

    # Use canonical cluster_id if pilot one is -1 or NaN
    mask = (df['event_cluster_id'] < 0) | df['event_cluster_id'].isna()
    df.loc[mask, 'event_cluster_id'] = df.loc[mask, 'canon_cluster_id']

    # Cold-block flag
    df = df.sort_values('center_time_s')
    time_diffs = df['center_time_s'].diff().abs()
    gap_threshold = time_diffs.quantile(0.9)
    df['is_cold_block'] = (time_diffs > gap_threshold).astype(bool)
    df.loc[df.index[0], 'is_cold_block'] = True

    # L3 rank by proxy score
    proxy_col = 'object_count_mean'
    if df[proxy_col].isna().all():
        proxy_col = 'score_fusion_geometry_motion'
    col_min = df[proxy_col].min()
    if pd.isna(col_min):
        col_min = 0.0
    df[proxy_col] = df[proxy_col].fillna(col_min - 0.1)
    df['l3_rank'] = df[proxy_col].rank(ascending=False, method='first').astype(int)

    # GLM confidence
    has_conf = 'glm_confidence' in df.columns and df['glm_confidence'].notna().any()
    if not has_conf:
        df['glm_confidence'] = np.where(df['glm_pred'] == 'positive', 0.8,
                               np.where(df['glm_pred'] == 'negative', 0.2, 0.5))
    df['glm_confidence'] = df['glm_confidence'].fillna(0.5)

    return df


# ── Strategy implementations (identical to original) ──
def strat_l3_baseline(df, B, seed):
    ranked = df.sort_values('l3_rank')
    return set(ranked.head(B).index), 0

def strat_glm_pos_only(df, B, seed):
    glm_pos = df[df['glm_pred'] == 'positive']
    orig_count = len(glm_pos)
    if len(glm_pos) > B:
        glm_pos = glm_pos.sort_values('glm_confidence', ascending=False).head(B)
    return set(glm_pos.index), max(0, orig_count - B)

def strat_glm_pos_unc(df, B, seed):
    candidates = df[df['glm_pred'].isin(['positive', 'uncertain'])]
    orig_count = len(candidates)
    if len(candidates) > B:
        candidates = candidates.sort_values('glm_confidence', ascending=False).head(B)
    return set(candidates.index), max(0, orig_count - B)

def strat_glm_pos_unc_plus_l3_neg(df, B, seed):
    pos_unc = df[df['glm_pred'].isin(['positive', 'uncertain'])]
    orig_count = len(pos_unc)
    if len(pos_unc) >= B:
        pos_unc = pos_unc.sort_values('glm_confidence', ascending=False).head(B)
        return set(pos_unc.index), max(0, orig_count - B)
    selected = set(pos_unc.index)
    remaining = B - len(pos_unc)
    glm_neg = df[(df['glm_pred'] == 'negative') & (~df.index.isin(selected))]
    if len(glm_neg) > 0:
        glm_neg = glm_neg.sort_values('l3_rank')
        selected.update(glm_neg.head(remaining).index)
    return selected, 0

def strat_glm_pos_unc_plus_disagreement(df, B, seed):
    pos_unc = df[df['glm_pred'].isin(['positive', 'uncertain'])]
    orig_count = len(pos_unc)
    if len(pos_unc) >= B:
        pos_unc = pos_unc.sort_values('glm_confidence', ascending=False).head(B)
        return set(pos_unc.index), max(0, orig_count - B)
    selected = set(pos_unc.index)
    remaining = B - len(pos_unc)
    rest = df[~df.index.isin(selected)].copy()
    l3_pct = rest['l3_rank'] / rest['l3_rank'].max()
    rest['disagreement_score'] = np.where(
        rest['glm_pred'] == 'negative', l3_pct, 1.0 - l3_pct)
    rest = rest.sort_values('disagreement_score', ascending=True)
    selected.update(rest.head(remaining).index)
    return selected, 0

def strat_l3_plus_uniform_audit(df, B, seed):
    rng = np.random.RandomState(seed)
    exploit_b = max(1, int(0.7 * B))
    audit_b = B - exploit_b
    ranked = df.sort_values('l3_rank')
    exploit = set(ranked.head(exploit_b).index)
    remaining_idx = list(set(df.index) - exploit)
    if len(remaining_idx) > 0 and audit_b > 0:
        audit_idx = rng.choice(remaining_idx, min(audit_b, len(remaining_idx)), replace=False)
        exploit.update(audit_idx)
    return exploit, 0

def strat_l3_plus_glm_disag_audit(df, B, seed):
    rng = np.random.RandomState(seed)
    exploit_b = max(1, int(0.7 * B))
    audit_b = B - exploit_b
    ranked = df.sort_values('l3_rank')
    exploit = set(ranked.head(exploit_b).index)
    remaining = df[~df.index.isin(exploit)].copy()
    l3_pct_rem = remaining['l3_rank'] / remaining['l3_rank'].max()
    remaining['disagreement_score'] = np.where(
        remaining['glm_pred'] == 'negative', l3_pct_rem, 1.0 - l3_pct_rem)
    remaining = remaining.sort_values('disagreement_score', ascending=True)
    exploit.update(set(remaining.head(audit_b).index))
    return exploit, 0

STRATEGIES = {
    '1_L3_baseline': strat_l3_baseline,
    '2_GLM_positive_only': strat_glm_pos_only,
    '3_GLM_pos_uncertain': strat_glm_pos_unc,
    '4_GLM_pos_unc_plus_L3_neg': strat_glm_pos_unc_plus_l3_neg,
    '5_GLM_pos_unc_plus_disagreement': strat_glm_pos_unc_plus_disagreement,
    '6_L3_plus_uniform_audit': strat_l3_plus_uniform_audit,
    '7_L3_plus_GLM_disagreement_audit': strat_l3_plus_glm_disag_audit,
}


def evaluate(df, selected):
    sel = df.loc[list(selected)]
    n_sel = len(sel)
    tp = int(sel['is_positive'].sum())
    total_pos = int(df['is_positive'].sum())
    total_neg = int((~df['is_positive']).sum())
    recall = tp / total_pos if total_pos > 0 else 0.0
    precision = tp / n_sel if n_sel > 0 else 0.0
    f1 = 2*recall*precision/(recall+precision) if (recall+precision) > 0 else 0.0

    pos_clusters = set(df[df['is_positive']]['event_cluster_id'].dropna().unique())
    pos_clusters.discard(-1)
    pos_clusters.discard(-1.0)
    sel_clusters = set(sel[sel['is_positive']]['event_cluster_id'].dropna().unique())
    sel_clusters.discard(-1)
    sel_clusters.discard(-1.0)
    cluster_recall = len(sel_clusters & pos_clusters) / len(pos_clusters) if len(pos_clusters) > 0 else 0.0

    singleton_pos = df[(df['is_positive']) & (df['is_singleton_cluster'] == True)]
    singleton_clusters = set(singleton_pos['event_cluster_id'].dropna().unique())
    singleton_clusters.discard(-1)
    singleton_clusters.discard(-1.0)
    sel_singleton = set(sel[(sel['is_positive']) & (sel['is_singleton_cluster'] == True)]['event_cluster_id'].dropna().unique())
    sel_singleton.discard(-1)
    sel_singleton.discard(-1.0)
    singleton_recall = len(sel_singleton & singleton_clusters) / len(singleton_clusters) if len(singleton_clusters) > 0 else 0.0

    glm_fn_lost = int(df[(df['glm_pred'] == 'negative') & (df['is_positive']) & (~df.index.isin(selected))].shape[0])

    return {
        'n_selected': n_sel, 'tp': tp,
        'recall': recall, 'precision': precision, 'f1': f1,
        'cluster_recall': cluster_recall, 'singleton_recall': singleton_recall,
        'glm_fn_lost': glm_fn_lost,
    }


if __name__ == '__main__':
    df = load_clean_pool()
    N = len(df)
    n_pos = int(df['is_positive'].sum())
    print(f'Clean pool: N={N}, pos={n_pos}, neg={N-n_pos}')

    budgets = [20, 30, 40, 60, 80, 100]
    n_seeds = 500

    results = []
    for sname, strat_fn in STRATEGIES.items():
        print(f'\nStrategy: {sname}')
        for B in budgets:
            if B > N:
                print(f'  B={B}: SKIP (B > N={N})')
                continue
            agg = defaultdict(list)
            for seed in range(n_seeds):
                selected, truncated = strat_fn(df, B, seed)
                m = evaluate(df, selected)
                m['truncated_count'] = truncated
                for k, v in m.items():
                    agg[k].append(v)

            row = {
                'strategy': sname, 'B': B, 'n_seeds': n_seeds,
                'N_candidate_pool': N,
                'mean_recall': round(np.mean(agg['recall']), 6),
                'std_recall': round(np.std(agg['recall']), 6),
                'mean_tp': round(np.mean(agg['tp']), 2),
                'mean_precision': round(np.mean(agg['precision']), 6),
                'std_precision': round(np.std(agg['precision']), 6),
                'mean_f1': round(np.mean(agg['f1']), 6),
                'mean_cluster_recall': round(np.mean(agg['cluster_recall']), 6),
                'std_cluster_recall': round(np.std(agg['cluster_recall']), 6),
                'mean_singleton_recall': round(np.mean(agg['singleton_recall']), 6),
                'std_singleton_recall': round(np.std(agg['singleton_recall']), 6),
                'mean_glm_fn_lost': round(np.mean(agg['glm_fn_lost']), 2),
                'mean_truncated_count': round(np.mean(agg['truncated_count']), 2),
            }
            results.append(row)
            print(f'  B={B}: recall={row["mean_recall"]:.3f} tp={row["mean_tp"]:.1f}/{n_pos} '
                  f'clust={row["mean_cluster_recall"]:.3f} sing={row["mean_singleton_recall"]:.3f} '
                  f'prec={row["mean_precision"]:.3f}')

    results_df = pd.DataFrame(results)
    out_csv = f'{OUTDIR}/tables/cascade_simulation_results_clean.csv'
    results_df.to_csv(out_csv, index=False)
    print(f'\nSaved: {out_csv}')
