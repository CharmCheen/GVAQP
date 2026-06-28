#!/usr/bin/env python3
"""
Phase 3: Cascade simulation — No new Qwen/GLM calls.
Replays budget allocation strategies using existing GLM outputs and Qwen reference.
"""
import os, sys, json, argparse, warnings
import pandas as pd, numpy as np
from collections import defaultdict

warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = f'{ROOT}/heldout_cascade_eval_v1'

# ── Data loading ──────────────────────────────────────────
def load_data():
    pilot_csv = f'{OUTDIR}/tables/glm_v1_pilot_123_outputs.csv'
    canon_csv = '/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv'

    df = pd.read_csv(pilot_csv)
    canon = pd.read_csv(canon_csv)
    canon_cols = ['anchor_id', 'center_time_s', 'object_count_mean', 'score_fusion_geometry_motion',
                  'score_yolo_count', 'motion_energy_mean', 'score_motion', 'event_cluster_id']
    canon_sub = canon[canon_cols].copy()
    canon_sub = canon_sub.rename(columns={'event_cluster_id': 'canon_cluster_id'})

    df = df.merge(canon_sub, on='anchor_id', how='left', suffixes=('', '_canon'))

    # Use canonical cluster_id if pilot one is -1
    mask = (df['event_cluster_id'] < 0) | df['event_cluster_id'].isna()
    df.loc[mask, 'event_cluster_id'] = df.loc[mask, 'canon_cluster_id']

    # Derive cold-block flag: anchors with large temporal gaps
    df = df.sort_values('center_time_s')
    time_diffs = df['center_time_s'].diff().abs()
    gap_threshold = time_diffs.quantile(0.9)
    df['is_cold_block'] = (time_diffs > gap_threshold).astype(bool)
    df.loc[df.index[0], 'is_cold_block'] = True  # first anchor is cold block start

    # L3 rank: descending by object_count_mean (best single-feature proxy, AUC 0.738)
    proxy_col = 'object_count_mean'
    if df[proxy_col].isna().all():
        proxy_col = 'score_fusion_geometry_motion'
    if df[proxy_col].isna().all():
        proxy_col = 'score_yolo_count'

    # Fill remaining NaN with minimum value minus small offset
    col_min = df[proxy_col].min()
    if pd.isna(col_min):
        col_min = 0.0
    df[proxy_col] = df[proxy_col].fillna(col_min - 0.1)

    df['l3_rank'] = df[proxy_col].rank(ascending=False, method='first').astype(int)

    # GLM confidence: use existing if has non-NaN values, else derive from label
    has_conf = 'glm_confidence' in df.columns and df['glm_confidence'].notna().any()
    if not has_conf:
        df['glm_confidence'] = np.where(df['glm_pred'] == 'positive', 0.8,
                               np.where(df['glm_pred'] == 'negative', 0.2, 0.5))
    df['glm_confidence'] = df['glm_confidence'].fillna(0.5)

    print(f'Proxy column: {proxy_col}')
    print(f'  NaN count: {df[proxy_col].isna().sum()}')
    print(f'  Min: {df[proxy_col].min():.2f}, Max: {df[proxy_col].max():.2f}')

    return df


# ── Strategy implementations ──────────────────────────────
def strategy_l3_baseline(df, B, seed):
    """Strategy 1: L3 top-B by proxy score."""
    rng = np.random.RandomState(seed)
    ranked = df.sort_values('l3_rank')
    return set(ranked.head(B).index)

def strategy_glm_positive_only(df, B, seed):
    """Strategy 2: Only GLM positive -> Qwen. Truncate to B by confidence."""
    glm_pos = df[df['glm_pred'] == 'positive']
    if len(glm_pos) > B:
        glm_pos = glm_pos.sort_values('glm_confidence', ascending=False).head(B)
    return set(glm_pos.index), len(glm_pos) if len(df[df['glm_pred'] == 'positive']) > B else 0

def strategy_glm_pos_uncertain(df, B, seed):
    """Strategy 3: GLM positive + uncertain -> Qwen. Truncate to B by confidence."""
    candidates = df[df['glm_pred'].isin(['positive', 'uncertain'])]
    total_candidates = len(candidates)
    if len(candidates) > B:
        candidates = candidates.sort_values('glm_confidence', ascending=False).head(B)
    truncated = total_candidates - B if total_candidates > B else 0
    return set(candidates.index), max(0, truncated)

def strategy_glm_pos_unc_plus_l3_neg(df, B, seed):
    """Strategy 4: GLM positive+uncertain first, remaining budget to L3 top negative."""
    rng = np.random.RandomState(seed)
    pos_unc = df[df['glm_pred'].isin(['positive', 'uncertain'])]
    total_pos_unc = len(pos_unc)
    if len(pos_unc) >= B:
        pos_unc = pos_unc.sort_values('glm_confidence', ascending=False).head(B)
        truncated = total_pos_unc - B
        return set(pos_unc.index), max(0, truncated)

    selected = set(pos_unc.index)
    remaining_budget = B - len(pos_unc)
    glm_neg = df[(df['glm_pred'] == 'negative') & (~df.index.isin(selected))]
    if len(glm_neg) > 0:
        glm_neg = glm_neg.sort_values('l3_rank')
        extra = glm_neg.head(remaining_budget)
        selected.update(extra.index)
    return selected, 0

def strategy_glm_pos_unc_plus_disagreement(df, B, seed):
    """Strategy 5: GLM positive+uncertain first, remaining budget to disagreement regions."""
    pos_unc = df[df['glm_pred'].isin(['positive', 'uncertain'])]
    total_pos_unc = len(pos_unc)
    if len(pos_unc) >= B:
        pos_unc = pos_unc.sort_values('glm_confidence', ascending=False).head(B)
        truncated = total_pos_unc - B
        return set(pos_unc.index), max(0, truncated)

    selected = set(pos_unc.index)
    remaining_budget = B - len(pos_unc)

    # Disagreement regions: L3 high + GLM negative, OR L3 low + GLM positive/uncertain
    # Already have pos_unc. Now take L3-high + GLM-negative
    rest = df[~df.index.isin(selected)]
    rest = rest.copy()

    # Compute disagreement score: L3 rank percentile (low=good) + GLM negative flag
    l3_pct = rest['l3_rank'] / rest['l3_rank'].max()
    rest['disagreement_score'] = np.where(
        rest['glm_pred'] == 'negative',
        l3_pct,  # L3 high (low percentile = good) + GLM negative
        1.0 - l3_pct  # GLM positive/uncertain with L3 low
    )
    rest = rest.sort_values('disagreement_score', ascending=True)
    extra = rest.head(remaining_budget)
    selected.update(extra.index)
    return selected, 0

def strategy_l3_plus_uniform_audit(df, B, seed):
    """Strategy 6: L3 exploitation (0.7*B) + uniform audit (0.3*B)."""
    rng = np.random.RandomState(seed)
    exploit_b = max(1, int(0.7 * B))
    audit_b = B - exploit_b

    ranked = df.sort_values('l3_rank')
    exploit = set(ranked.head(exploit_b).index)

    remaining_idx = list(set(df.index) - exploit)
    if len(remaining_idx) > 0:
        audit_idx = rng.choice(remaining_idx, min(audit_b, len(remaining_idx)), replace=False)
        exploit.update(audit_idx)
    return exploit

def strategy_l3_plus_glm_disagreement_audit(df, B, seed):
    """Strategy 7: L3 exploitation (0.7*B) + GLM/proxy disagreement audit (0.3*B)."""
    rng = np.random.RandomState(seed)
    exploit_b = max(1, int(0.7 * B))
    audit_b = B - exploit_b

    ranked = df.sort_values('l3_rank')
    exploit = set(ranked.head(exploit_b).index)

    remaining = df[~df.index.isin(exploit)].copy()
    # Disagreement: L3 high + GLM negative, or L3 low + GLM positive
    l3_pct_rem = remaining['l3_rank'] / remaining['l3_rank'].max()
    remaining['disagreement_score'] = np.where(
        remaining['glm_pred'] == 'negative',
        l3_pct_rem,
        1.0 - l3_pct_rem
    )
    remaining = remaining.sort_values('disagreement_score', ascending=True)
    audit_set = set(remaining.head(audit_b).index)
    exploit.update(audit_set)
    return exploit


# ── Evaluation ────────────────────────────────────────────
def evaluate_selection(df, selected_indices):
    """Compute all metrics for a selection."""
    sel = df.loc[list(selected_indices)]
    n_selected = len(sel)

    tp = int(sel['is_positive'].sum())
    fp = n_selected - tp
    total_pos = int(df['is_positive'].sum())
    total_neg = int((~df['is_positive']).sum())

    recall = tp / total_pos if total_pos > 0 else 0.0
    precision = tp / n_selected if n_selected > 0 else 0.0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0.0

    # Event-cluster recall
    pos_clusters = set(df[df['is_positive']]['event_cluster_id'].dropna().unique())
    pos_clusters.discard(-1)
    sel_clusters = set(sel[sel['is_positive']]['event_cluster_id'].dropna().unique())
    sel_clusters.discard(-1)
    cluster_recall = len(sel_clusters & pos_clusters) / len(pos_clusters) if len(pos_clusters) > 0 else 0.0

    # Singleton recall
    singleton_pos = df[(df['is_positive']) & (df['is_singleton_cluster'] == True)]
    singleton_clusters = set(singleton_pos['event_cluster_id'].dropna().unique())
    singleton_clusters.discard(-1)
    sel_singleton_clusters = set(sel[(sel['is_positive']) & (sel['is_singleton_cluster'] == True)]['event_cluster_id'].dropna().unique())
    sel_singleton_clusters.discard(-1)
    singleton_recall = len(sel_singleton_clusters & singleton_clusters) / len(singleton_clusters) if len(singleton_clusters) > 0 else 0.0

    # Cold-block recall
    cold_pos = df[(df['is_positive']) & (df['is_cold_block'] == True)]
    cold_recall = cold_pos[lambda x: x.index.isin(selected_indices)].shape[0] / cold_pos.shape[0] if cold_pos.shape[0] > 0 else 0.0

    # Qwen-positive recall retained by GLM gate (for cascade strategies)
    glm_gate_pos = df[(df['glm_pred'].isin(['positive', 'uncertain'])) & (df['is_positive'])]
    glm_gate_covered = glm_gate_pos[lambda x: x.index.isin(selected_indices)].shape[0]
    glm_gate_recall = glm_gate_covered / total_pos if total_pos > 0 else 0.0

    # GLM false-negative loss (Qwen-pos in GLM neg that weren't selected)
    glm_fn = df[(df['glm_pred'] == 'negative') & (df['is_positive'])]
    glm_fn_lost = glm_fn[lambda x: ~x.index.isin(selected_indices)].shape[0]

    # Positive yield per Qwen call
    yield_per_call = tp / n_selected if n_selected > 0 else 0.0

    # Audit hit rate (for audit strategies)
    audit_pool = df[~df.index.isin(selected_indices)]
    audit_pos_count = int(audit_pool['is_positive'].sum()) if len(audit_pool) > 0 else 0
    # For the strategies with audit: positives in audit portion
    if 'audit' in str(selected_indices):  # hacky, but fine
        pass

    return {
        'n_selected': n_selected,
        'tp': tp, 'fp': fp,
        'recall': recall,
        'precision': precision,
        'f1': f1,
        'cluster_recall': cluster_recall,
        'singleton_recall': singleton_recall,
        'cold_block_recall': cold_recall,
        'glm_gate_recall': glm_gate_recall,
        'glm_fn_lost': glm_fn_lost,
        'pos_yield': yield_per_call,
    }


# ── Hypergeometric lower bound ───────────────────────────
def hypergeometric_lower_bound(H, N, n, k, delta=0.05):
    """
    Finite-population exact bound via hypergeometric inversion.
    H: discovered positives in exploited pool
    N: total pool size
    n: random audit sample size
    k: observed missed positives in audit
    delta: confidence level (lower bound = 1-delta confidence)
    Returns: recall_lower_bound
    """
    from scipy.stats import hypergeom
    # H + k are observed positives, U is upper bound on missed positives in unaudited pool
    # We invert: find U_max s.t. observing ≤ k misses is consistent with H_true = H + U
    unaudited = N - n
    observed_missed = k

    # Simple approach: use hypergeometric CI via Clopper-Pearson-like inversion
    # P(M <= k | M_true = m) = sum_{i=0}^k hypergeom.pmf(i, N, m, n)
    U = 0
    for U_guess in range(observed_missed, unaudited + 1):
        prob = hypergeom.cdf(observed_missed, N, U_guess, n)
        if prob > delta:
            U = U_guess
            break
    else:
        U = unaudited

    recall_lb = H / (H + U) if (H + U) > 0 else 1.0
    return recall_lb, U


# ── Main simulation ───────────────────────────────────────
STRATEGIES = {
    '1_L3_baseline': (strategy_l3_baseline, False),
    '2_GLM_positive_only': (strategy_glm_positive_only, True),
    '3_GLM_pos_uncertain': (strategy_glm_pos_uncertain, True),
    '4_GLM_pos_unc_plus_L3_neg': (strategy_glm_pos_unc_plus_l3_neg, True),
    '5_GLM_pos_unc_plus_disagreement': (strategy_glm_pos_unc_plus_disagreement, True),
    '6_L3_plus_uniform_audit': (strategy_l3_plus_uniform_audit, False),
    '7_L3_plus_GLM_disagreement_audit': (strategy_l3_plus_glm_disagreement_audit, False),
}


def run_simulation(df, budgets, n_seeds=500):
    results = []

    for sname, (strat_fn, uses_glm) in STRATEGIES.items():
        print(f'\nStrategy: {sname}')
        for B in budgets:
            if B > len(df):
                print(f'  B={B}: SKIP (B > N={len(df)})')
                continue
            metrics_agg = defaultdict(list)
            for seed in range(n_seeds):
                if uses_glm:
                    selected, truncated = strat_fn(df, B, seed)
                else:
                    selected = strat_fn(df, B, seed)
                    truncated = 0

                m = evaluate_selection(df, selected)
                m['truncated_count'] = truncated
                for k, v in m.items():
                    metrics_agg[k].append(v)

            # Aggregate
            row = {
                'strategy': sname,
                'B': B,
                'n_seeds': n_seeds,
                'N_candidate_pool': len(df),
                'mean_recall': np.mean(metrics_agg['recall']),
                'std_recall': np.std(metrics_agg['recall']),
                'mean_precision': np.mean(metrics_agg['precision']),
                'std_precision': np.std(metrics_agg['precision']),
                'mean_f1': np.mean(metrics_agg['f1']),
                'std_f1': np.std(metrics_agg['f1']),
                'mean_cluster_recall': np.mean(metrics_agg['cluster_recall']),
                'std_cluster_recall': np.std(metrics_agg['cluster_recall']),
                'mean_singleton_recall': np.mean(metrics_agg['singleton_recall']),
                'std_singleton_recall': np.std(metrics_agg['singleton_recall']),
                'mean_cold_block_recall': np.mean(metrics_agg['cold_block_recall']),
                'std_cold_block_recall': np.std(metrics_agg['cold_block_recall']),
                'mean_glm_gate_recall': np.mean(metrics_agg['glm_gate_recall']),
                'std_glm_gate_recall': np.std(metrics_agg['glm_gate_recall']),
                'mean_glm_fn_lost': np.mean(metrics_agg['glm_fn_lost']),
                'std_glm_fn_lost': np.std(metrics_agg['glm_fn_lost']),
                'mean_pos_yield': np.mean(metrics_agg['pos_yield']),
                'std_pos_yield': np.std(metrics_agg['pos_yield']),
                'mean_truncated_count': np.mean(metrics_agg['truncated_count']) if 'truncated_count' in metrics_agg else 0,
            }
            results.append(row)
            print(f'  B={B}: recall={row["mean_recall"]:.3f}±{row["std_recall"]:.3f} '
                  f'clust_rec={row["mean_cluster_recall"]:.3f} '
                  f'sing_rec={row["mean_singleton_recall"]:.3f} '
                  f'prec={row["mean_precision"]:.3f}')

    return pd.DataFrame(results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-seeds', type=int, default=500)
    parser.add_argument('--output-dir', default=OUTDIR)
    args = parser.parse_args()

    print('Loading data...')
    df = load_data()
    print(f'Candidate pool: N={len(df)}, positives={df["is_positive"].sum()}, '
          f'clusters={len(df[df["event_cluster_id"]>=0]["event_cluster_id"].unique())}')

    # Budget points: only those ≤ N
    all_budgets = [30, 40, 60, 80, 100, 150]
    budgets = [b for b in all_budgets if b <= len(df)]
    skipped = [b for b in all_budgets if b > len(df)]
    if skipped:
        print(f'Skipped budgets (B > N={len(df)}): {skipped}')

    print(f'Budgets: {budgets}')
    print(f'Seeds: {args.n_seeds}')
    print(f'N_pos = {df["is_positive"].sum()}, N_neg = {(~df["is_positive"]).sum()}')

    results_df = run_simulation(df, budgets, args.n_seeds)
    results_df = results_df.round(6)

    out_csv = f'{args.output_dir}/tables/cascade_simulation_results.csv'
    results_df.to_csv(out_csv, index=False)
    print(f'\nSaved: {out_csv}')
    print(results_df.to_string())
