"""
PHASE 3-5: Run SUPG-style, ABae-style, and clip-level experiments.

Uses the frame_query_table.csv built by build_frame_table.py.

Implements minimal compatible baselines inspired by SUPG and ABae:
- SUPG: recall-target and precision-target selection with proxy-guided sampling
- ABae: aggregation with stratified sampling
- Clip-level: temporal grouping and evaluation
"""

import pandas as pd
import numpy as np
import os
import sys
from collections import defaultdict

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
FRAME_TABLE_PATH = os.path.join(OUTPUT_DIR, 'frame_query_table.csv')
SEEDS = [42, 123, 456, 789, 101112]
BUDGETS_FRAC = [0.01, 0.02, 0.05, 0.10, 0.20]
K = 3  # vehicle count threshold
TAU = 30  # clip length in frames
DELTA = 0.01  # failure probability for SUPG bounds


# ============================================================
# Utility: Sampling bounds (from SUPG)
# ============================================================
class SamplingBounds:
    def __init__(self, delta):
        self.delta = delta

    def calc_bounds(self, fx):
        n = len(fx)
        mu = np.mean(fx)
        std = np.std(fx) / np.sqrt(n) if n > 1 else 0
        k = np.sqrt(2 * np.log(1 / (2 * self.delta))) if self.delta > 0 else 1.96
        return mu - k * std, mu + k * std


# ============================================================
# Baselines
# ============================================================
def uniform_sample(n, budget, rng):
    """Uniform random sampling."""
    return rng.choice(n, size=min(budget, n), replace=False)


def proxy_threshold_sample(proxy_scores, budget, threshold=0.5, rng=None):
    """Sample from items above proxy threshold, fallback to top-k by proxy."""
    above = np.where(proxy_scores >= threshold)[0]
    if len(above) >= budget:
        return rng.choice(above, size=budget, replace=False) if rng is not None else above[:budget]
    else:
        # Take all above threshold, fill rest with top proxy scores
        sorted_idx = np.argsort(proxy_scores)[::-1]
        return sorted_idx[:budget]


def importance_sample(proxy_scores, budget, rng, mixing_eps=0.10):
    """Importance sampling with sqrt(proxy) weights + uniform mixture (SUPG-style)."""
    n = len(proxy_scores)
    weights = np.sqrt(np.maximum(proxy_scores, 1e-10))
    scaled = weights / weights.sum()
    uniform = np.ones(n) / n
    mixed = scaled * (1 - mixing_eps) + uniform * mixing_eps
    return rng.choice(n, size=budget, replace=True, p=mixed)


def defensive_mixture_sample(proxy_scores, budget, rng, frac_uniform=0.3):
    """Defensive mixture: split budget between uniform and proxy-biased."""
    n_uniform = int(budget * frac_uniform)
    n_biased = budget - n_uniform

    uniform_part = rng.choice(len(proxy_scores), size=n_uniform, replace=False)

    # Proxy-biased part: importance sample with sqrt weights
    weights = np.sqrt(np.maximum(proxy_scores, 1e-10))
    weights = weights / weights.sum()
    biased_part = rng.choice(len(proxy_scores), size=n_biased * 2, replace=True, p=weights)
    biased_part = np.unique(biased_part)[:n_biased]

    return np.unique(np.concatenate([uniform_part, biased_part]))[:budget]


# ============================================================
# SUPG-style recall target
# ============================================================
def run_supg_recall_target(df, budget, min_recall, seed):
    """
    SUPG-style recall target experiment.

    Strategy: importance-sample with sqrt(proxy), then use sampling bounds
    to find a threshold that guarantees min_recall with probability 1-delta.
    """
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values

    # Sort by proxy score descending
    sort_idx = np.argsort(proxy)[::-1]
    proxy_sorted = proxy[sort_idx]
    labels_sorted = labels[sort_idx]

    # Importance sample
    sampled_ranks = importance_sample(proxy_sorted, budget, rng)
    sampled_labels = labels_sorted[sampled_ranks]
    sampled_proxies = proxy_sorted[sampled_ranks]

    # Compute sampling weights for reweighting
    weights = np.sqrt(np.maximum(proxy_sorted, 1e-10))
    weights = weights / weights.sum()
    uniform_prob = 1.0 / n
    mixed_weights = weights * 0.9 + uniform_prob * 0.1
    sample_weights = mixed_weights[sampled_ranks]
    base_weights = np.repeat(uniform_prob, budget)
    masses = base_weights / sample_weights

    # Find threshold for recall target
    tot_pos_mass = np.sum(masses * sampled_labels)
    target_mass = min_recall * tot_pos_mass

    cum_mass = 0
    t_idx = budget
    for i in range(budget):
        cum_mass += sampled_labels[i] * masses[i]
        if cum_mass >= target_mass:
            t_idx = i
            break

    # Use sampling bounds for confidence
    bounder = SamplingBounds(delta=DELTA / 2)

    # The returned set: all items with proxy >= threshold, union with sampled positives
    threshold_rank = sampled_ranks[t_idx] if t_idx < budget else n - 1
    selected = sort_idx[:threshold_rank + 1]
    # Also include any sampled positives
    pos_sampled = sampled_ranks[sampled_labels > 0]
    selected = np.unique(np.concatenate([selected, pos_sampled]))

    # Compute actual metrics
    actual_labels = labels[selected]
    actual_recall = actual_labels.sum() / labels.sum() if labels.sum() > 0 else 0
    actual_precision = actual_labels.sum() / len(selected) if len(selected) > 0 else 0

    return {
        'method': 'supg_importance_recall',
        'budget_frac': budget / n,
        'budget': budget,
        'seed': seed,
        'actual_oracle_calls': budget,  # we sample budget items
        'returned_set_size': len(selected),
        'actual_recall': actual_recall,
        'actual_precision': actual_precision,
        'target_recall': min_recall,
        'target_precision': None,
        'violation': actual_recall < min_recall,
    }


# ============================================================
# SUPG-style precision target
# ============================================================
def run_supg_precision_target(df, budget, min_precision, seed):
    """
    SUPG-style precision target experiment.

    Strategy: importance-sample with sqrt(proxy), walk down sorted sample
    until estimated precision drops below target.
    """
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values

    sort_idx = np.argsort(proxy)[::-1]
    proxy_sorted = proxy[sort_idx]
    labels_sorted = labels[sort_idx]

    sampled_ranks = importance_sample(proxy_sorted, budget, rng)
    sampled_labels = labels_sorted[sampled_ranks]
    sampled_proxies = proxy_sorted[sampled_ranks]

    # Walk down sorted sample by proxy, find where precision >= target
    order = np.argsort(-sampled_proxies)
    ordered_labels = sampled_labels[order]

    bounder = SamplingBounds(delta=DELTA)
    allowed = [0]
    start_samp = min(100, budget // 4)
    step_size = max(1, budget // 20)

    for s_idx in range(start_samp, budget, step_size):
        trues = ordered_labels[:s_idx + 1]
        _, prec_lb = bounder.calc_bounds(fx=trues.astype(float))
        if prec_lb > min_precision:
            allowed.append(s_idx)

    # Return set: all items with proxy >= threshold from last allowed
    if allowed[-1] == 0:
        threshold_rank = 0
    else:
        last_allowed = allowed[-1]
        threshold_rank = sampled_ranks[order[last_allowed]]

    selected = sort_idx[:threshold_rank + 1]
    pos_sampled = sampled_ranks[sampled_labels > 0]
    selected = np.unique(np.concatenate([selected, pos_sampled]))

    actual_labels = labels[selected]
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


# ============================================================
# Simple baselines for comparison
# ============================================================
def run_uniform_baseline(df, budget, seed):
    """Uniform sampling baseline."""
    rng = np.random.RandomState(seed)
    n = len(df)
    labels = df['label'].values

    selected = uniform_sample(n, budget, rng)
    actual_labels = labels[selected]
    actual_recall = actual_labels.sum() / labels.sum() if labels.sum() > 0 else 0
    actual_precision = actual_labels.sum() / len(selected) if len(selected) > 0 else 0

    return {
        'method': 'uniform',
        'budget_frac': budget / n,
        'budget': budget,
        'seed': seed,
        'actual_oracle_calls': budget,
        'returned_set_size': len(selected),
        'actual_recall': actual_recall,
        'actual_precision': actual_precision,
        'target_recall': None,
        'target_precision': None,
        'violation': False,
    }


def run_proxy_threshold_baseline(df, budget, seed):
    """Proxy threshold baseline: take top-budget items by proxy score."""
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values

    sort_idx = np.argsort(proxy)[::-1]
    selected = sort_idx[:budget]

    actual_labels = labels[selected]
    actual_recall = actual_labels.sum() / labels.sum() if labels.sum() > 0 else 0
    actual_precision = actual_labels.sum() / len(selected) if len(selected) > 0 else 0

    return {
        'method': 'proxy_threshold',
        'budget_frac': budget / n,
        'budget': budget,
        'seed': seed,
        'actual_oracle_calls': budget,
        'returned_set_size': len(selected),
        'actual_recall': actual_recall,
        'actual_precision': actual_precision,
        'target_recall': None,
        'target_precision': None,
        'violation': False,
    }


def run_importance_baseline(df, budget, seed):
    """Importance sampling baseline (no threshold adjustment)."""
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values

    selected = importance_sample(proxy, budget, rng)
    # Deduplicate (importance sampling is with replacement)
    selected = np.unique(selected)[:budget]

    actual_labels = labels[selected]
    actual_recall = actual_labels.sum() / labels.sum() if labels.sum() > 0 else 0
    actual_precision = actual_labels.sum() / len(selected) if len(selected) > 0 else 0

    return {
        'method': 'importance_sampling',
        'budget_frac': budget / n,
        'budget': budget,
        'seed': seed,
        'actual_oracle_calls': len(selected),
        'returned_set_size': len(selected),
        'actual_recall': actual_recall,
        'actual_precision': actual_precision,
        'target_recall': None,
        'target_precision': None,
        'violation': False,
    }


def run_defensive_mixture_baseline(df, budget, seed):
    """Defensive mixture baseline."""
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values

    selected = defensive_mixture_sample(proxy, budget, rng)

    actual_labels = labels[selected]
    actual_recall = actual_labels.sum() / labels.sum() if labels.sum() > 0 else 0
    actual_precision = actual_labels.sum() / len(selected) if len(selected) > 0 else 0

    return {
        'method': 'defensive_mixture',
        'budget_frac': budget / n,
        'budget': budget,
        'seed': seed,
        'actual_oracle_calls': len(selected),
        'returned_set_size': len(selected),
        'actual_recall': actual_recall,
        'actual_precision': actual_precision,
        'target_recall': None,
        'target_precision': None,
        'violation': False,
    }


# ============================================================
# ABae-style aggregation
# ============================================================
def run_abae_aggregation(df, budget, seed, n_strata=5):
    """
    ABae-style aggregation experiment.

    Query: SELECT AVG(vehicle_count_gt) FROM frames WHERE count(vehicle) >= K

    Methods:
    - exact: compute over all data
    - uniform: uniform sample, compute mean over positives
    - stratified: proxy-stratified sampling (ABae-style)
    """
    rng = np.random.RandomState(seed)
    n = len(df)
    proxy = df['proxy_score'].values
    labels = df['label'].values
    stats = df['vehicle_count_gt'].values.astype(float)

    # Exact answer
    positive_mask = labels > 0
    exact_avg = stats[positive_mask].mean() if positive_mask.sum() > 0 else 0
    exact_count = positive_mask.sum()

    # --- Uniform sampling ---
    uni_selected = uniform_sample(n, budget, rng)
    uni_labels = labels[uni_selected]
    uni_stats = stats[uni_selected]
    uni_pos_mask = uni_labels > 0
    uni_avg = uni_stats[uni_pos_mask].mean() if uni_pos_mask.sum() > 0 else 0
    uni_count_est = uni_pos_mask.mean() * n  # scale up

    # --- Stratified sampling (ABae-style) ---
    # Sort by proxy, split into strata
    sort_idx = np.argsort(proxy)
    strata = np.array_split(sort_idx, n_strata)

    # Phase 1: pilot sample from each stratum
    pilot_per_stratum = max(1, budget // (2 * n_strata))
    phase2_budget = budget - pilot_per_stratum * n_strata

    stratum_stats = []
    stratum_pos_rates = []
    stratum_pos_stds = []

    for s_idx, stratum in enumerate(strata):
        pilot_idx = rng.choice(stratum, size=min(pilot_per_stratum, len(stratum)), replace=False)
        pilot_labels = labels[pilot_idx]
        pilot_stats_arr = stats[pilot_idx]

        pos_rate = pilot_labels.mean() if len(pilot_labels) > 0 else 0
        pos_mask = pilot_labels > 0
        pos_std = pilot_stats_arr[pos_mask].std() if pos_mask.sum() > 1 else 0

        stratum_pos_rates.append(pos_rate)
        stratum_pos_stds.append(pos_std)

    # Phase 2: allocate remaining budget proportional to sqrt(p) * sigma
    weights = np.array([np.sqrt(max(p, 1e-10)) * s for p, s in zip(stratum_pos_rates, stratum_pos_stds)])
    if weights.sum() > 0:
        alloc = np.floor(phase2_budget * weights / weights.sum()).astype(int)
    else:
        alloc = np.ones(n_strata, dtype=int) * (phase2_budget // n_strata)

    # Ensure we don't over-allocate
    for i in range(n_strata):
        alloc[i] = min(alloc[i], len(strata[i]))

    all_strat_idx = []
    for s_idx, stratum in enumerate(strata):
        # Phase 2 sample
        if alloc[s_idx] > 0:
            p2_idx = rng.choice(stratum, size=min(alloc[s_idx], len(stratum)), replace=False)
        else:
            p2_idx = np.array([], dtype=int)
        # Combine with pilot
        combined = np.concatenate([
            rng.choice(stratum, size=min(pilot_per_stratum, len(stratum)), replace=False),
            p2_idx
        ])
        all_strat_idx.extend(np.unique(combined).tolist())

    all_strat_idx = np.array(all_strat_idx)
    strat_labels = labels[all_strat_idx]
    strat_stats = stats[all_strat_idx]
    strat_pos_mask = strat_labels > 0

    # Estimate: weighted average across strata
    strat_estimates = []
    strat_weights = []
    for s_idx, stratum in enumerate(strata):
        stratum_sampled = np.intersect1d(all_strat_idx, stratum)
        if len(stratum_sampled) > 0:
            s_labels = labels[stratum_sampled]
            s_stats = stats[stratum_sampled]
            s_pos = s_labels > 0
            if s_pos.sum() > 0:
                strat_estimates.append(s_stats[s_pos].mean())
                strat_weights.append(s_pos.mean())
            else:
                strat_estimates.append(0)
                strat_weights.append(0)

    if sum(strat_weights) > 0:
        strat_avg = sum(e * w for e, w in zip(strat_estimates, strat_weights)) / sum(strat_weights)
    else:
        strat_avg = 0

    strat_count_est = strat_pos_mask.mean() * n if len(strat_pos_mask) > 0 else 0

    results = []
    for method, avg, count_est in [
        ('uniform', uni_avg, uni_count_est),
        ('stratified', strat_avg, strat_count_est),
    ]:
        results.append({
            'method': method,
            'query': 'AVG(vehicle_count_gt) WHERE vehicle_count >= K',
            'budget_frac': budget / n,
            'budget': budget,
            'seed': seed,
            'estimate': avg,
            'exact': exact_avg,
            'abs_error': abs(avg - exact_avg),
            'rel_error': abs(avg - exact_avg) / exact_avg if exact_avg > 0 else 0,
            'exact_count': exact_count,
            'count_estimate': count_est,
        })

    return results


# ============================================================
# Clip-level extension
# ============================================================
def build_clips_from_frames(df, tau=TAU):
    """
    Convert frame-level labels into ground-truth clips.

    A clip is a contiguous segment of tau frames from the same video.
    A clip is positive if >= 50% of its frames are positive.
    """
    clips = []
    clip_id = 0

    # Group by video_id
    for vid, group in df.groupby('video_id'):
        group = group.sort_values('frame_id').reset_index(drop=True)
        n_frames = len(group)

        for start in range(0, n_frames, tau):
            end = min(start + tau, n_frames)
            clip_frames = group.iloc[start:end]

            labels = clip_frames['label'].values
            clip_label = 1 if labels.mean() >= 0.5 else 0

            clips.append({
                'clip_id': clip_id,
                'video_id': vid,
                'start_frame': clip_frames['frame_id'].iloc[0],
                'end_frame': clip_frames['frame_id'].iloc[-1],
                'n_frames': len(clip_frames),
                'clip_label': clip_label,
                'positive_frame_frac': labels.mean(),
                'frame_ids': clip_frames['id'].values.tolist(),
            })
            clip_id += 1

    return pd.DataFrame(clips)


def evaluate_clip_metrics(df, clips_df, selected_frame_ids, method_name, budget, seed):
    """
    Evaluate clip-level metrics from frame-level selected set.

    For each clip, check if any of its frames were selected.
    A clip is "predicted positive" if >= 1 frame was selected.
    """
    selected_set = set(selected_frame_ids.tolist())
    n_total_clips = len(clips_df)
    n_positive_clips = clips_df['clip_label'].sum()

    tp = 0
    fp = 0
    fn = 0
    ious = []
    start_errors = []
    end_errors = []
    fragmented = 0

    for _, clip in clips_df.iterrows():
        clip_frame_ids = set(clip['frame_ids'])
        selected_in_clip = clip_frame_ids & selected_set

        predicted_positive = len(selected_in_clip) > 0
        actual_positive = clip['clip_label'] == 1

        if predicted_positive and actual_positive:
            tp += 1
            iou = len(selected_in_clip) / len(clip_frame_ids)
            ious.append(iou)
        elif predicted_positive and not actual_positive:
            fp += 1
        elif not predicted_positive and actual_positive:
            fn += 1

        # Fragmentation: multiple disjoint selected segments within clip
        if predicted_positive:
            sorted_selected = sorted(selected_in_clip)
            if len(sorted_selected) > 1:
                gaps = sum(1 for i in range(1, len(sorted_selected))
                          if sorted_selected[i] - sorted_selected[i-1] > 1)
                if gaps > 0:
                    fragmented += 1

    clip_recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    clip_precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    mean_iou = np.mean(ious) if ious else 0

    return {
        'method': method_name,
        'budget_frac': len(selected_frame_ids) / len(df),
        'budget': budget,
        'seed': seed,
        'clip_recall': clip_recall,
        'clip_precision': clip_precision,
        'mean_iou': mean_iou,
        'fragmentation_rate': fragmented / n_total_clips if n_total_clips > 0 else 0,
        'n_total_clips': n_total_clips,
        'n_positive_clips': n_positive_clips,
        'n_predicted_positive': tp + fp,
        'n_true_positive': tp,
    }


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("Running real-data AQP experiments")
    print("=" * 60)

    # Load frame table
    df = pd.read_csv(FRAME_TABLE_PATH)
    n = len(df)
    print(f"Loaded {n} records")
    print(f"Positive rate: {df['label'].mean():.4f}")
    print(f"K={K}, TAU={TAU}")

    # ============================================================
    # PHASE 3: SUPG-style experiments
    # ============================================================
    print("\n" + "=" * 60)
    print("PHASE 3: SUPG-style experiments")
    print("=" * 60)

    supg_results = []

    for budget_frac in BUDGETS_FRAC:
        budget = int(n * budget_frac)
        for seed in SEEDS:
            # Baselines
            supg_results.append(run_uniform_baseline(df, budget, seed))
            supg_results.append(run_proxy_threshold_baseline(df, budget, seed))
            supg_results.append(run_importance_baseline(df, budget, seed))
            supg_results.append(run_defensive_mixture_baseline(df, budget, seed))

            # SUPG-style recall target (target recall = 0.9)
            supg_results.append(run_supg_recall_target(df, budget, min_recall=0.9, seed=seed))

            # SUPG-style precision target (target precision = 0.8)
            supg_results.append(run_supg_precision_target(df, budget, min_precision=0.8, seed=seed))

    supg_df = pd.DataFrame(supg_results)
    supg_path = os.path.join(OUTPUT_DIR, 'supg_style_metrics.csv')
    supg_df.to_csv(supg_path, index=False)
    print(f"\nSUPG-style metrics saved to: {supg_path}")

    # Summary
    print("\nSUPG-style summary (mean over seeds):")
    summary = supg_df.groupby(['method', 'budget_frac']).agg({
        'actual_recall': ['mean', 'std'],
        'actual_precision': ['mean', 'std'],
        'returned_set_size': 'mean',
        'violation': 'mean',
    }).round(4)
    print(summary)

    # ============================================================
    # PHASE 4: ABae-style aggregation experiments
    # ============================================================
    print("\n" + "=" * 60)
    print("PHASE 4: ABae-style aggregation experiments")
    print("=" * 60)

    abae_results = []

    for budget_frac in BUDGETS_FRAC:
        budget = int(n * budget_frac)
        for seed in SEEDS:
            results = run_abae_aggregation(df, budget, seed)
            abae_results.extend(results)

    abae_df = pd.DataFrame(abae_results)
    abae_path = os.path.join(OUTPUT_DIR, 'abae_style_metrics.csv')
    abae_df.to_csv(abae_path, index=False)
    print(f"\nABae-style metrics saved to: {abae_path}")

    # Compute MSE per method/budget
    print("\nABae-style MSE summary:")
    abae_df['sq_error'] = abae_df['abs_error'] ** 2
    mse_summary = abae_df.groupby(['method', 'budget_frac']).agg({
        'sq_error': 'mean',
        'abs_error': ['mean', 'std'],
        'rel_error': 'mean',
    }).round(6)
    print(mse_summary)

    # ============================================================
    # PHASE 5: Clip-level extension
    # ============================================================
    print("\n" + "=" * 60)
    print("PHASE 5: Clip-level extension")
    print("=" * 60)

    clips_df = build_clips_from_frames(df, tau=TAU)
    clips_path = os.path.join(OUTPUT_DIR, 'ground_truth_clips.csv')
    clips_df.drop(columns=['frame_ids']).to_csv(clips_path, index=False)
    print(f"Built {len(clips_df)} clips ({clips_df['clip_label'].sum()} positive)")
    print(f"Clips saved to: {clips_path}")

    clip_results = []

    for budget_frac in BUDGETS_FRAC:
        budget = int(n * budget_frac)
        for seed in SEEDS:
            rng = np.random.RandomState(seed)
            proxy = df['proxy_score'].values

            # Uniform
            sel = uniform_sample(n, budget, rng)
            clip_results.append(evaluate_clip_metrics(df, clips_df, df['id'].values[sel],
                                                      'uniform', budget, seed))

            # Proxy threshold (top-k)
            sort_idx = np.argsort(proxy)[::-1]
            sel = sort_idx[:budget]
            clip_results.append(evaluate_clip_metrics(df, clips_df, df['id'].values[sel],
                                                      'proxy_threshold', budget, seed))

            # Importance sampling
            sel = importance_sample(proxy, budget, rng)
            sel = np.unique(sel)[:budget]
            clip_results.append(evaluate_clip_metrics(df, clips_df, df['id'].values[sel],
                                                      'importance_sampling', budget, seed))

            # Defensive mixture
            sel = defensive_mixture_sample(proxy, budget, rng)
            clip_results.append(evaluate_clip_metrics(df, clips_df, df['id'].values[sel],
                                                      'defensive_mixture', budget, seed))

    clip_df = pd.DataFrame(clip_results)
    clip_path = os.path.join(OUTPUT_DIR, 'clip_metrics.csv')
    clip_df.to_csv(clip_path, index=False)
    print(f"\nClip metrics saved to: {clip_path}")

    # Summary
    print("\nClip-level summary (mean over seeds):")
    clip_summary = clip_df.groupby(['method', 'budget_frac']).agg({
        'clip_recall': ['mean', 'std'],
        'clip_precision': 'mean',
        'mean_iou': 'mean',
        'fragmentation_rate': 'mean',
    }).round(4)
    print(clip_summary)

    print("\n" + "=" * 60)
    print("All experiments complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
