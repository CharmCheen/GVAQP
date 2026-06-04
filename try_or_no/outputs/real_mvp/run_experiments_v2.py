"""
PHASE 3-5 (v2): Fixed SUPG-style experiments.

Key fix: importance sampling uses replace=True (matching SUPG), and the
recall selector works on the full sample (with duplicates), not deduplicated.
"""

import pandas as pd
import numpy as np
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
FRAME_TABLE_PATH = os.path.join(OUTPUT_DIR, 'frame_query_table.csv')
SEEDS = [42, 123, 456, 789, 101112]
BUDGETS_FRAC = [0.01, 0.02, 0.05, 0.10, 0.20]
K = 3
TAU = 30
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


def importance_sample_sorted(proxy_sorted, budget, rng, mixing_eps=0.10):
    """
    Importance sample from sorted proxy array.
    Returns indices into the sorted array (0..n-1).
    Uses replace=True matching SUPG's ImportanceSampler.
    """
    n = len(proxy_sorted)
    weights = np.sqrt(np.maximum(proxy_sorted, 1e-10))
    scaled = weights / weights.sum()
    uniform = np.ones(n) / n
    mixed = scaled * (1 - mixing_eps) + uniform * mixing_eps
    return rng.choice(n, size=budget, replace=True, p=mixed)


def run_supg_recall(df, budget, min_recall, seed):
    """
    SUPG-style recall target. Matches RecallSelector logic.

    Key: works on sorted-by-proxy indices, samples with replacement,
    uses masses (basep/weight) for reweighting.
    """
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values

    # Sort by proxy descending
    sort_idx = np.argsort(proxy)[::-1]
    proxy_sorted = proxy[sort_idx]
    labels_sorted = labels[sort_idx]

    # Importance sample from sorted array
    s_ranks = np.sort(importance_sample_sorted(proxy_sorted, budget, rng))
    s_labels = labels_sorted[s_ranks]

    # Compute weights (matching SUPG)
    weights = np.sqrt(np.maximum(proxy_sorted, 1e-10))
    weights = weights / weights.sum()
    uniform_prob = 1.0 / n
    mixed_weights = weights * 0.9 + uniform_prob * 0.1
    s_weights = mixed_weights[s_ranks]
    x_basep = np.repeat(uniform_prob, n)
    s_basep = x_basep[s_ranks]
    s_masses = s_basep / s_weights

    # Find threshold for recall target
    tot_pos_mass = np.sum(s_masses * s_labels)
    target_mass = min_recall * tot_pos_mass

    cum_mass = 0
    t_s_idx = budget  # default: return everything
    for i in range(budget):
        cum_mass += s_labels[i] * s_masses[i]
        if cum_mass >= target_mass:
            t_s_idx = i
            break

    # The threshold rank in the sorted array
    t_u_idx = s_ranks[t_s_idx]

    # Use sampling bounds for confidence adjustment (SUPG style)
    x_ranks = np.arange(n)
    s_ind_l = np.arange(budget) <= t_s_idx
    s_ind_r = np.arange(budget) > t_s_idx

    bounder = SamplingBounds(delta=DELTA / 2)
    _, s_left_ub = bounder.calc_bounds(
        fx=s_labels * s_masses * s_ind_l,
    )
    s_right_lb, _ = bounder.calc_bounds(
        fx=s_labels * s_masses * s_ind_r,
    )

    rc = s_left_ub / (s_left_ub + s_right_lb) if (s_left_ub + s_right_lb) > 0 else 1.0

    if rc >= 1.0:
        # Return all
        selected = np.arange(n)
    else:
        # Adjust threshold
        cum_mass = 0
        t_adj_s_idx = budget - 1
        for i in range(budget):
            if s_labels[i]:
                cum_mass += s_masses[i]
            if cum_mass >= rc * tot_pos_mass:
                t_adj_s_idx = i
                break
        t_adj_u_idx = s_ranks[t_adj_s_idx]

        # Return all items with rank <= threshold, union with sampled positives
        set_ids = np.arange(t_adj_u_idx + 1)
        pos_sampled = s_ranks[s_labels > 0]
        selected = np.unique(np.concatenate([set_ids, pos_sampled]))

    actual_labels = labels[sort_idx[selected]]
    actual_recall = actual_labels.sum() / labels.sum() if labels.sum() > 0 else 0
    actual_precision = actual_labels.sum() / len(selected) if len(selected) > 0 else 0

    return {
        'method': 'supg_importance_recall',
        'budget_frac': budget / n,
        'budget': budget,
        'seed': seed,
        'actual_oracle_calls': budget,
        'returned_set_size': len(selected),
        'actual_recall': actual_recall,
        'actual_precision': actual_precision,
        'target_recall': min_recall,
        'target_precision': None,
        'violation': actual_recall < min_recall,
    }


def run_supg_precision(df, budget, min_precision, seed):
    """SUPG-style precision target. Matches ImportancePrecisionSelector logic."""
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values

    sort_idx = np.argsort(proxy)[::-1]
    proxy_sorted = proxy[sort_idx]
    labels_sorted = labels[sort_idx]

    weights = np.sqrt(np.maximum(proxy_sorted, 1e-10))
    weights = weights / weights.sum()
    uniform_prob = 1.0 / n
    mixed_weights = weights * 0.9 + uniform_prob * 0.1

    s_ranks = np.sort(importance_sample_sorted(proxy_sorted, budget, rng))
    s_labels = labels_sorted[s_ranks]
    s_weights = mixed_weights[s_ranks]
    s_basep = np.repeat(uniform_prob, budget)
    s_masses = s_basep / s_weights

    start_samp = min(100, budget // 4)
    step_size = max(1, budget // 20)
    T = 1 + 2 * (budget - start_samp) // step_size

    allowed = [0]
    for s_idx in range(start_samp, budget, step_size):
        cur_u_idx = s_ranks[s_idx]
        # Compute precision lower bound over items up to this rank
        cur_subsample = s_ranks[:s_idx + 1]
        cur_labels = s_labels[:s_idx + 1]
        cur_masses = s_masses[:s_idx + 1]

        bounder = SamplingBounds(delta=DELTA / T)
        pos_rank_lb, pos_rank_ub = bounder.calc_bounds(
            fx=cur_labels * cur_masses,
        )
        prec_lb = pos_rank_lb
        if prec_lb > min_precision:
            allowed.append(cur_u_idx)

    # Return all items with rank <= last allowed
    set_inds = np.arange(allowed[-1] + 1)
    # Also include sampled positives
    pos_sampled = s_ranks[s_labels > 0]
    selected = np.unique(np.concatenate([set_inds, pos_sampled]))

    actual_labels = labels[sort_idx[selected]]
    actual_recall = actual_labels.sum() / labels.sum() if labels.sum() > 0 else 0
    actual_precision = actual_labels.sum() / len(selected) if len(selected) > 0 else 0

    return {
        'method': 'supg_importance_precision',
        'budget_frac': budget / n,
        'budget': budget,
        'seed': seed,
        'actual_oracle_calls': budget,
        'returned_set_size': len(selected),
        'actual_recall': actual_recall,
        'actual_precision': actual_precision,
        'target_recall': None,
        'target_precision': min_precision,
        'violation': actual_precision < min_precision,
    }


def run_uniform(df, budget, seed):
    rng = np.random.RandomState(seed)
    n = len(df)
    labels = df['label'].values
    selected = rng.choice(n, size=min(budget, n), replace=False)
    actual = labels[selected]
    return {
        'method': 'uniform', 'budget_frac': budget / n, 'budget': budget, 'seed': seed,
        'actual_oracle_calls': budget, 'returned_set_size': len(selected),
        'actual_recall': actual.sum() / labels.sum() if labels.sum() > 0 else 0,
        'actual_precision': actual.sum() / len(selected) if len(selected) > 0 else 0,
        'target_recall': None, 'target_precision': None, 'violation': False,
    }


def run_proxy_threshold(df, budget, seed):
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values
    sort_idx = np.argsort(proxy)[::-1]
    selected = sort_idx[:budget]
    actual = labels[selected]
    return {
        'method': 'proxy_threshold', 'budget_frac': budget / n, 'budget': budget, 'seed': seed,
        'actual_oracle_calls': budget, 'returned_set_size': len(selected),
        'actual_recall': actual.sum() / labels.sum() if labels.sum() > 0 else 0,
        'actual_precision': actual.sum() / len(selected) if len(selected) > 0 else 0,
        'target_recall': None, 'target_precision': None, 'violation': False,
    }


def run_importance(df, budget, seed):
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values
    weights = np.sqrt(np.maximum(proxy, 1e-10))
    weights = weights / weights.sum()
    uniform = np.ones(n) / n
    mixed = weights * 0.9 + uniform * 0.1
    selected = rng.choice(n, size=budget, replace=True, p=mixed)
    selected = np.unique(selected)
    actual = labels[selected]
    return {
        'method': 'importance_sampling', 'budget_frac': budget / n, 'budget': budget, 'seed': seed,
        'actual_oracle_calls': len(selected), 'returned_set_size': len(selected),
        'actual_recall': actual.sum() / labels.sum() if labels.sum() > 0 else 0,
        'actual_precision': actual.sum() / len(selected) if len(selected) > 0 else 0,
        'target_recall': None, 'target_precision': None, 'violation': False,
    }


def run_defensive(df, budget, seed):
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values
    n_uni = int(budget * 0.3)
    n_biased = budget - n_uni
    uni_part = rng.choice(n, size=n_uni, replace=False)
    weights = np.sqrt(np.maximum(proxy, 1e-10))
    weights = weights / weights.sum()
    biased_part = rng.choice(n, size=n_biased, replace=True, p=weights)
    biased_part = np.unique(biased_part)[:n_biased]
    selected = np.unique(np.concatenate([uni_part, biased_part]))[:budget]
    actual = labels[selected]
    return {
        'method': 'defensive_mixture', 'budget_frac': budget / n, 'budget': budget, 'seed': seed,
        'actual_oracle_calls': len(selected), 'returned_set_size': len(selected),
        'actual_recall': actual.sum() / labels.sum() if labels.sum() > 0 else 0,
        'actual_precision': actual.sum() / len(selected) if len(selected) > 0 else 0,
        'target_recall': None, 'target_precision': None, 'violation': False,
    }


def run_abae_agg(df, budget, seed, n_strata=5):
    """ABae-style aggregation: AVG(vehicle_count_gt) WHERE vehicle_count >= K."""
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values
    stats = df['vehicle_count_gt'].values.astype(float)

    exact_avg = stats[labels > 0].mean() if labels.sum() > 0 else 0
    exact_count = labels.sum()

    # Uniform
    uni_sel = rng.choice(n, size=budget, replace=False)
    uni_pos = labels[uni_sel] > 0
    uni_avg = stats[uni_sel][uni_pos].mean() if uni_pos.sum() > 0 else 0

    # Stratified (ABae-style)
    sort_idx = np.argsort(proxy)
    strata = np.array_split(sort_idx, n_strata)
    pilot_per = max(1, budget // (2 * n_strata))
    phase2 = budget - pilot_per * n_strata

    stratum_pos_rates = []
    stratum_pos_stds = []
    pilot_samples = []

    for s_idx, stratum in enumerate(strata):
        p_idx = rng.choice(stratum, size=min(pilot_per, len(stratum)), replace=False)
        p_labels = labels[p_idx]
        p_stats = stats[p_idx]
        pos_rate = p_labels.mean()
        pos_std = p_stats[p_labels > 0].std() if p_labels.sum() > 1 else 0
        stratum_pos_rates.append(pos_rate)
        stratum_pos_stds.append(pos_std)
        pilot_samples.append(p_idx)

    weights = np.array([np.sqrt(max(p, 1e-10)) * s for p, s in zip(stratum_pos_rates, stratum_pos_stds)])
    if weights.sum() > 0:
        alloc = np.floor(phase2 * weights / weights.sum()).astype(int)
    else:
        alloc = np.ones(n_strata, dtype=int) * (phase2 // n_strata)

    all_idx = []
    for s_idx, stratum in enumerate(strata):
        alloc_s = min(alloc[s_idx], len(stratum))
        if alloc_s > 0:
            p2 = rng.choice(stratum, size=alloc_s, replace=False)
        else:
            p2 = np.array([], dtype=int)
        combined = np.unique(np.concatenate([pilot_samples[s_idx], p2]))
        all_idx.extend(combined.tolist())

    all_idx = np.array(all_idx)
    strat_labels = labels[all_idx]
    strat_stats = stats[all_idx]
    strat_pos = strat_labels > 0

    # Weighted estimate
    strat_est = []
    strat_w = []
    for s_idx, stratum in enumerate(strata):
        s_in = np.intersect1d(all_idx, stratum)
        if len(s_in) > 0:
            sl = labels[s_in]
            ss = stats[s_in]
            sp = sl > 0
            if sp.sum() > 0:
                strat_est.append(ss[sp].mean())
                strat_w.append(sp.mean())
            else:
                strat_est.append(0)
                strat_w.append(0)

    strat_avg = sum(e * w for e, w in zip(strat_est, strat_w)) / sum(strat_w) if sum(strat_w) > 0 else 0

    results = []
    for method, avg in [('uniform', uni_avg), ('stratified', strat_avg)]:
        results.append({
            'method': method, 'query': 'AVG(vehicle_count_gt) WHERE vehicle_count >= K',
            'budget_frac': budget / n, 'budget': budget, 'seed': seed,
            'estimate': avg, 'exact': exact_avg,
            'abs_error': abs(avg - exact_avg),
            'rel_error': abs(avg - exact_avg) / exact_avg if exact_avg > 0 else 0,
            'exact_count': exact_count,
        })
    return results


def build_clips(df, tau=TAU):
    clips = []
    for vid, group in df.groupby('video_id'):
        group = group.sort_values('frame_id').reset_index(drop=True)
        for start in range(0, len(group), tau):
            end = min(start + tau, len(group))
            clip = group.iloc[start:end]
            labels = clip['label'].values
            clips.append({
                'clip_id': len(clips), 'video_id': vid,
                'frame_ids': clip['id'].values.tolist(),
                'clip_label': 1 if labels.mean() >= 0.5 else 0,
                'n_frames': len(clip),
            })
    return pd.DataFrame(clips)


def eval_clip(clips_df, selected_ids, method, budget, seed, n):
    sel_set = set(selected_ids.tolist())
    tp = fp = fn = 0
    ious = []
    for _, clip in clips_df.iterrows():
        clip_ids = set(clip['frame_ids'])
        hit = clip_ids & sel_set
        pred = len(hit) > 0
        actual = clip['clip_label'] == 1
        if pred and actual:
            tp += 1
            ious.append(len(hit) / len(clip_ids))
        elif pred and not actual:
            fp += 1
        elif not pred and actual:
            fn += 1
    return {
        'method': method, 'budget_frac': len(selected_ids) / n, 'budget': budget, 'seed': seed,
        'clip_recall': tp / (tp + fn) if (tp + fn) > 0 else 0,
        'clip_precision': tp / (tp + fp) if (tp + fp) > 0 else 0,
        'mean_iou': np.mean(ious) if ious else 0,
    }


def main():
    print("=" * 60)
    print("Running real-data AQP experiments (v2 - fixed)")
    print("=" * 60)

    df = pd.read_csv(FRAME_TABLE_PATH)
    n = len(df)
    print(f"Loaded {n} records, positive rate: {df['label'].mean():.4f}")

    # PHASE 3: SUPG-style
    print("\n--- SUPG-style experiments ---")
    supg_results = []
    for bf in BUDGETS_FRAC:
        budget = int(n * bf)
        for seed in SEEDS:
            supg_results.append(run_uniform(df, budget, seed))
            supg_results.append(run_proxy_threshold(df, budget, seed))
            supg_results.append(run_importance(df, budget, seed))
            supg_results.append(run_defensive(df, budget, seed))
            supg_results.append(run_supg_recall(df, budget, min_recall=0.9, seed=seed))
            supg_results.append(run_supg_precision(df, budget, min_precision=0.8, seed=seed))

    supg_df = pd.DataFrame(supg_results)
    supg_df.to_csv(os.path.join(OUTPUT_DIR, 'supg_style_metrics.csv'), index=False)

    # Summary
    for method in supg_df['method'].unique():
        m = supg_df[supg_df['method'] == method]
        print(f"\n{method}:")
        for bf in BUDGETS_FRAC:
            mb = m[m['budget_frac'].round(4) == round(bf, 4)]
            if len(mb) > 0:
                print(f"  {bf:.0%}: recall={mb['actual_recall'].mean():.4f}±{mb['actual_recall'].std():.4f} "
                      f"prec={mb['actual_precision'].mean():.4f} "
                      f"set_size={mb['returned_set_size'].mean():.0f} "
                      f"violation={mb['violation'].mean():.2f}")

    # PHASE 4: ABae-style
    print("\n--- ABae-style experiments ---")
    abae_results = []
    for bf in BUDGETS_FRAC:
        budget = int(n * bf)
        for seed in SEEDS:
            abae_results.extend(run_abae_agg(df, budget, seed))

    abae_df = pd.DataFrame(abae_results)
    abae_df.to_csv(os.path.join(OUTPUT_DIR, 'abae_style_metrics.csv'), index=False)

    abae_df['sq_error'] = abae_df['abs_error'] ** 2
    print("\nABae MSE:")
    print(abae_df.groupby(['method', 'budget_frac'])['sq_error'].mean().unstack().round(6))

    # PHASE 5: Clip-level
    print("\n--- Clip-level experiments ---")
    clips_df = build_clips(df)
    print(f"Built {len(clips_df)} clips, {clips_df['clip_label'].sum()} positive")

    clip_results = []
    for bf in BUDGETS_FRAC:
        budget = int(n * bf)
        for seed in SEEDS:
            rng = np.random.RandomState(seed)
            proxy = df['proxy_score'].values

            # Uniform
            sel = rng.choice(n, size=budget, replace=False)
            clip_results.append(eval_clip(clips_df, df['id'].values[sel], 'uniform', budget, seed, n))

            # Proxy threshold
            sort_idx = np.argsort(proxy)[::-1]
            clip_results.append(eval_clip(clips_df, df['id'].values[sort_idx[:budget]], 'proxy_threshold', budget, seed, n))

            # Importance
            weights = np.sqrt(np.maximum(proxy, 1e-10))
            weights = weights / weights.sum()
            mixed = weights * 0.9 + (1.0/n) * 0.1
            sel = rng.choice(n, size=budget, replace=True, p=mixed)
            sel = np.unique(sel)
            clip_results.append(eval_clip(clips_df, df['id'].values[sel], 'importance_sampling', budget, seed, n))

    clip_df = pd.DataFrame(clip_results)
    clip_df.to_csv(os.path.join(OUTPUT_DIR, 'clip_metrics.csv'), index=False)

    print("\nClip metrics:")
    print(clip_df.groupby(['method', 'budget_frac'])['clip_recall'].mean().unstack().round(4))

    print("\nDone!")


if __name__ == '__main__':
    main()
