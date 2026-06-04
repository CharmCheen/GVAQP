"""
Run SUPG-style experiments with different K thresholds for comparison.
K=3 (94.86% positive) is too easy; K=10 and K=20 give more balanced datasets.
"""

import pandas as pd
import numpy as np
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
FRAME_TABLE_PATH = os.path.join(OUTPUT_DIR, 'frame_query_table.csv')
SEEDS = [42, 123, 456, 789, 101112]
BUDGETS_FRAC = [0.01, 0.02, 0.05, 0.10, 0.20]
DELTA = 0.01


class SamplingBounds:
    def __init__(self, delta):
        self.delta = delta

    def calc_bounds(self, fx):
        n = len(fx)
        mu = np.mean(fx)
        std = np.std(fx) / np.sqrt(n) if n > 1 else 0
        k = np.sqrt(2 * np.log(1 / (2 * self.delta))) if self.delta > 0 else 1.96
        return mu - k * std, mu + k * std


def importance_sample(proxy_scores, budget, rng, mixing_eps=0.10):
    n = len(proxy_scores)
    weights = np.sqrt(np.maximum(proxy_scores, 1e-10))
    scaled = weights / weights.sum()
    uniform = np.ones(n) / n
    mixed = scaled * (1 - mixing_eps) + uniform * mixing_eps
    return rng.choice(n, size=budget, replace=True, p=mixed)


def run_experiment_with_k(df, K, budget, seed):
    """Run one experiment with given K threshold."""
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    gt_counts = df['vehicle_count_gt'].values
    labels = (gt_counts >= K).astype(int)

    sort_idx = np.argsort(proxy)[::-1]
    proxy_sorted = proxy[sort_idx]
    labels_sorted = labels[sort_idx]

    # Importance sample
    sampled_ranks = importance_sample(proxy_sorted, budget, rng)
    sampled_labels = labels_sorted[sampled_ranks]

    # Compute weights
    weights = np.sqrt(np.maximum(proxy_sorted, 1e-10))
    weights = weights / weights.sum()
    uniform_prob = 1.0 / n
    mixed_weights = weights * 0.9 + uniform_prob * 0.1
    sample_weights = mixed_weights[sampled_ranks]
    base_weights = np.repeat(uniform_prob, budget)
    masses = base_weights / sample_weights

    # Recall target method
    tot_pos_mass = np.sum(masses * sampled_labels)
    target_mass = 0.9 * tot_pos_mass
    cum_mass = 0
    t_idx = budget
    for i in range(budget):
        cum_mass += sampled_labels[i] * masses[i]
        if cum_mass >= target_mass:
            t_idx = i
            break
    threshold_rank = sampled_ranks[t_idx] if t_idx < budget else n - 1
    selected_recall = np.unique(np.concatenate([sort_idx[:threshold_rank + 1],
                                                 sampled_ranks[sampled_labels > 0]]))

    # Precision target method
    sampled_proxies = proxy_sorted[sampled_ranks]
    order = np.argsort(-sampled_proxies)
    ordered_labels = sampled_labels[order]
    bounder = SamplingBounds(delta=DELTA)
    allowed = [0]
    start_samp = min(100, budget // 4)
    step_size = max(1, budget // 20)
    for s_idx in range(start_samp, budget, step_size):
        trues = ordered_labels[:s_idx + 1].astype(float)
        _, prec_lb = bounder.calc_bounds(fx=trues)
        if prec_lb > 0.8:
            allowed.append(s_idx)
    if allowed[-1] == 0:
        threshold_rank_p = 0
    else:
        threshold_rank_p = sampled_ranks[order[allowed[-1]]]
    selected_precision = np.unique(np.concatenate([sort_idx[:threshold_rank_p + 1],
                                                    sampled_ranks[sampled_labels > 0]]))

    # Uniform baseline
    uni_sel = rng.choice(n, size=min(budget, n), replace=False)

    # Proxy threshold baseline
    proxy_sel = sort_idx[:budget]

    def compute_metrics(selected, labels):
        actual = labels[selected]
        recall = actual.sum() / labels.sum() if labels.sum() > 0 else 0
        precision = actual.sum() / len(selected) if len(selected) > 0 else 0
        return recall, precision, len(selected)

    r_recall, p_recall, s_recall = compute_metrics(selected_recall, labels)
    r_prec, p_prec, s_prec = compute_metrics(selected_precision, labels)
    r_uni, p_uni, s_uni = compute_metrics(uni_sel, labels)
    r_proxy, p_proxy, s_proxy = compute_metrics(proxy_sel, labels)

    return [
        {'method': 'uniform', 'K': K, 'pos_rate': labels.mean(), 'budget': budget, 'seed': seed,
         'recall': r_uni, 'precision': p_uni, 'set_size': s_uni, 'recall_violation': r_uni < 0.9},
        {'method': 'proxy_threshold', 'K': K, 'pos_rate': labels.mean(), 'budget': budget, 'seed': seed,
         'recall': r_proxy, 'precision': p_proxy, 'set_size': s_proxy, 'recall_violation': r_proxy < 0.9},
        {'method': 'supg_recall', 'K': K, 'pos_rate': labels.mean(), 'budget': budget, 'seed': seed,
         'recall': r_recall, 'precision': p_recall, 'set_size': s_recall, 'recall_violation': r_recall < 0.9},
        {'method': 'supg_precision', 'K': K, 'pos_rate': labels.mean(), 'budget': budget, 'seed': seed,
         'recall': r_prec, 'precision': p_prec, 'set_size': s_prec, 'recall_violation': r_prec < 0.9},
    ]


def main():
    df = pd.read_csv(FRAME_TABLE_PATH)
    n = len(df)

    K_VALUES = [3, 10, 15, 20]
    all_results = []

    for K in K_VALUES:
        pos_rate = (df['vehicle_count_gt'] >= K).mean()
        print(f"\nK={K}: positive rate = {pos_rate:.4f}")

        for budget_frac in BUDGETS_FRAC:
            budget = int(n * budget_frac)
            for seed in SEEDS:
                results = run_experiment_with_k(df, K, budget, seed)
                all_results.extend(results)

    results_df = pd.DataFrame(all_results)
    out_path = os.path.join(OUTPUT_DIR, 'k_sweep_metrics.csv')
    results_df.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    # Summary
    print("\n=== Summary: Recall at 5% budget, target=0.9 ===")
    summary = results_df[results_df['budget'] == int(n * 0.05)].groupby(['K', 'method']).agg({
        'recall': ['mean', 'std'],
        'precision': 'mean',
        'set_size': 'mean',
        'recall_violation': 'mean',
    }).round(4)
    print(summary)


if __name__ == '__main__':
    main()
