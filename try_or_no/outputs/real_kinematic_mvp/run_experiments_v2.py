"""
Run kinematic AQP experiments on UA-DETRAC real data (v2).

Fixed query_impact method + count-based query.
"""

import pandas as pd
import numpy as np
import os
import json

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACK_TABLE_PATH = os.path.join(OUTPUT_DIR, 'kinematic_query_table.csv')
COUNT_TABLE_PATH = os.path.join(OUTPUT_DIR, 'frame_count_table.csv')
CLIPS_PATH = os.path.join(OUTPUT_DIR, 'ground_truth_clips.jsonl')
SEEDS = [42, 123, 456, 789, 101112]
TAU_VALUES = [5, 10, 20, 30]


# ============================================================
# Baselines
# ============================================================

def B0_naive_oracle(labels, cx=None, cy=None, area=None, tau=10, seed=42):
    """B0: Oracle at every frame."""
    return labels.copy(), len(labels)


def B1_fixed_rate(labels, cx, cy, area, tau, seed, k=5):
    """B1: Oracle every k frames, hold last value."""
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0
    for i in range(n):
        if i % k == 0:
            predicted[i] = labels[i]
            oracle_calls += 1
        else:
            predicted[i] = predicted[i - 1] if i > 0 else labels[0]
    return predicted, oracle_calls


def B2_linear_interp(labels, cx, cy, area, tau, seed, k=5):
    """B2: Oracle at sampled frames, linear interpolation."""
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0
    sample_pts = list(range(0, n, k))
    if sample_pts[-1] != n - 1:
        sample_pts.append(n - 1)
    oracle_calls = len(sample_pts)

    for idx in range(len(sample_pts) - 1):
        s, e = sample_pts[idx], sample_pts[idx + 1]
        sl, el = labels[s], labels[e]
        if sl == el:
            predicted[s:e + 1] = sl
        else:
            mid = (s + e) // 2
            predicted[s:mid + 1] = sl
            predicted[mid + 1:e + 1] = el
    return predicted, oracle_calls


def B3_const_vel(labels, cx, cy, area, tau, seed, k=5):
    """B3: Constant velocity extrapolation."""
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0
    last_oracle = 0
    predicted[0] = labels[0]
    oracle_calls = 1

    front_x_min, front_x_max = 192, 768
    min_area = 500

    for i in range(1, n):
        if i - last_oracle >= k:
            predicted[i] = labels[i]
            oracle_calls += 1
            last_oracle = i
        else:
            dt = i - last_oracle
            vx_val = cx[i] - cx[i - 1] if i > 0 else 0
            pred_x = cx[last_oracle] + vx_val * dt
            if area is not None:
                in_region = (front_x_min <= pred_x <= front_x_max) and (area[last_oracle] >= min_area)
            else:
                in_region = front_x_min <= pred_x <= front_x_max
            predicted[i] = 1 if in_region else 0
    return predicted, oracle_calls


def B4_kalman_fixed(labels, cx, cy, area, tau, seed, k=5):
    """B4: Kalman prediction, fixed-interval oracle."""
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    Q, R = 10.0, 50.0
    F = np.array([[1, 1], [0, 1]])
    H = np.array([[1, 0]])
    Q_mat = np.eye(2) * Q
    R_mat = np.array([[R]])

    state = np.array([cx[0], 0.0])
    cov = np.eye(2) * 100
    predicted[0] = labels[0]
    oracle_calls = 1
    last_oracle = 0

    front_x_min, front_x_max = 192, 768

    for i in range(1, n):
        state_pred = F @ state
        cov_pred = F @ cov @ F.T + Q_mat
        if i - last_oracle >= k:
            z = np.array([cx[i]])
            y = z - H @ state_pred
            S = H @ cov_pred @ H.T + R_mat
            K = cov_pred @ H.T @ np.linalg.inv(S)
            state = state_pred + (K @ y).flatten()
            cov = (np.eye(2) - K @ H) @ cov_pred
            predicted[i] = labels[i]
            oracle_calls += 1
            last_oracle = i
        else:
            state = state_pred
            cov = cov_pred
            pred_x = state[0]
            predicted[i] = 1 if front_x_min <= pred_x <= front_x_max else 0
    return predicted, oracle_calls


def B5_kalman_uncertainty(labels, cx, cy, area, tau, seed, thresh=50.0):
    """B5: Kalman, trigger when uncertainty > threshold."""
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    Q, R = 10.0, 50.0
    F = np.array([[1, 1], [0, 1]])
    H = np.array([[1, 0]])
    Q_mat = np.eye(2) * Q
    R_mat = np.array([[R]])

    state = np.array([cx[0], 0.0])
    cov = np.eye(2) * 100
    predicted[0] = labels[0]
    oracle_calls = 1

    front_x_min, front_x_max = 192, 768

    for i in range(1, n):
        state_pred = F @ state
        cov_pred = F @ cov @ F.T + Q_mat
        uncertainty = np.sqrt(cov_pred[0, 0])
        if uncertainty > thresh:
            z = np.array([cx[i]])
            y = z - H @ state_pred
            S = H @ cov_pred @ H.T + R_mat
            K = cov_pred @ H.T @ np.linalg.inv(S)
            state = state_pred + (K @ y).flatten()
            cov = (np.eye(2) - K @ H) @ cov_pred
            predicted[i] = labels[i]
            oracle_calls += 1
        else:
            state = state_pred
            cov = cov_pred
            pred_x = state[0]
            predicted[i] = 1 if front_x_min <= pred_x <= front_x_max else 0
    return predicted, oracle_calls


def B6_boundary_only(labels, cx, cy, area, tau, seed, margin=20.0):
    """B6: Trigger when near spatial boundary."""
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    front_x_min, front_x_max = 192, 768
    min_area = 500
    last_cx, last_cy = cx[0], cy[0]
    last_vx, last_vy = 0.0, 0.0
    predicted[0] = labels[0]
    oracle_calls = 1

    for i in range(1, n):
        pred_cx = last_cx + last_vx
        pred_cy = last_cy + last_vy

        near_boundary = False
        dist_to_boundary = min(
            abs(pred_cx - front_x_min), abs(pred_cx - front_x_max),
            abs(pred_cy), abs(pred_cy - 459)
        )
        near_boundary = dist_to_boundary < margin
        if area is not None and area[i] < min_area * 2:
            near_boundary = True

        if near_boundary:
            predicted[i] = labels[i]
            oracle_calls += 1
            last_cx, last_cy = cx[i], cy[i]
            last_vx = cx[i] - cx[i - 1] if i > 0 else 0
            last_vy = cy[i] - cy[i - 1] if i > 0 else 0
        else:
            predicted[i] = predicted[i - 1] if i > 0 else labels[0]
            last_cx, last_cy = pred_cx, pred_cy
    return predicted, oracle_calls


def B7_query_impact(labels, cx, cy, area, tau, seed, margin=30.0, oracle_gap=3):
    """B7: Query-impact-aware triggering (v2).

    Trigger oracle when:
    1. Near spatial boundary (within margin) OR
    2. Haven't called oracle for `oracle_gap` frames (temporal staleness) OR
    3. Predicted label disagrees with extrapolated label

    But skip if last oracle was very recent (within 2 frames) and not near boundary.
    """
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    front_x_min, front_x_max = 192, 768
    min_area = 500
    last_cx, last_cy = cx[0], cy[0]
    last_vx, last_vy = 0.0, 0.0
    predicted[0] = labels[0]
    oracle_calls = 1
    last_oracle = 0

    for i in range(1, n):
        pred_cx = last_cx + last_vx
        pred_cy = last_cy + last_vy
        frames_since_oracle = i - last_oracle

        # Check boundary proximity
        dist_to_boundary = min(
            abs(pred_cx - front_x_min), abs(pred_cx - front_x_max),
            abs(pred_cy), abs(pred_cy - 459)
        )
        near_boundary = dist_to_boundary < margin
        if area is not None and area[i] < min_area * 2:
            near_boundary = True

        # Check temporal staleness
        stale = frames_since_oracle >= oracle_gap

        # Check prediction confidence (disagreement between hold and extrapolate)
        hold_label = predicted[i - 1]
        extrap_label = 1 if (front_x_min <= pred_cx <= front_x_max) else 0
        disagree = (hold_label != extrap_label)

        # Trigger logic: call oracle if near boundary OR stale OR disagree
        # But skip if very recent oracle and not near boundary
        should_call = near_boundary or stale or disagree
        if frames_since_oracle <= 2 and not near_boundary:
            should_call = False

        if should_call:
            predicted[i] = labels[i]
            oracle_calls += 1
            last_oracle = i
            last_cx, last_cy = cx[i], cy[i]
            last_vx = cx[i] - cx[i - 1] if i > 0 else 0
            last_vy = cy[i] - cy[i - 1] if i > 0 else 0
        else:
            predicted[i] = predicted[i - 1]
            last_cx, last_cy = pred_cx, pred_cy
    return predicted, oracle_calls


def B8_count_fixed_rate(counts, K, tau, seed, k=5):
    """B8: Count-based query with fixed-rate oracle."""
    n = len(counts)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0
    for i in range(n):
        if i % k == 0:
            predicted[i] = 1 if counts[i] >= K else 0
            oracle_calls += 1
        else:
            predicted[i] = predicted[i - 1] if i > 0 else (1 if counts[0] >= K else 0)
    return predicted, oracle_calls


def B8_count_query_impact(counts, K, tau, seed, oracle_gap=3):
    """B8: Count-based query with query-impact-aware triggering."""
    n = len(counts)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0
    last_oracle = 0
    predicted[0] = 1 if counts[0] >= K else 0
    oracle_calls = 1

    for i in range(1, n):
        frames_since_oracle = i - last_oracle
        stale = frames_since_oracle >= oracle_gap

        # Check if near count boundary
        last_count = counts[last_oracle]
        near_count_boundary = abs(last_count - K) <= 2

        should_call = stale or near_count_boundary
        if frames_since_oracle <= 1 and not near_count_boundary:
            should_call = False

        if should_call:
            predicted[i] = 1 if counts[i] >= K else 0
            oracle_calls += 1
            last_oracle = i
        else:
            predicted[i] = predicted[i - 1]
    return predicted, oracle_calls


# ============================================================
# Clip construction and metrics
# ============================================================

def construct_clips_from_labels(labels, tau):
    """Construct clips from binary labels (runs of 1s >= tau)."""
    clips = []
    in_run = False
    run_start = 0
    run_length = 0
    for i, label in enumerate(labels):
        if label == 1:
            if not in_run:
                run_start = i
                run_length = 1
                in_run = True
            else:
                run_length += 1
        else:
            if in_run and run_length >= tau:
                clips.append((run_start, run_start + run_length - 1, run_length))
            in_run = False
            run_length = 0
    if in_run and run_length >= tau:
        clips.append((run_start, run_start + run_length - 1, run_length))
    return clips


def compute_metrics(predicted, oracle, gt_clips, tau):
    """Compute all metrics."""
    n = len(oracle)
    # Frame-level
    tp_f = np.sum((predicted == 1) & (oracle == 1))
    fp_f = np.sum((predicted == 1) & (oracle == 0))
    fn_f = np.sum((predicted == 0) & (oracle == 1))
    tn_f = np.sum((predicted == 0) & (oracle == 0))
    frame_prec = tp_f / (tp_f + fp_f) if (tp_f + fp_f) > 0 else 0
    frame_rec = tp_f / (tp_f + fn_f) if (tp_f + fn_f) > 0 else 0
    frame_fpr = fp_f / (fp_f + tn_f) if (fp_f + tn_f) > 0 else 0
    frame_fnr = fn_f / (fn_f + tp_f) if (fn_f + tp_f) > 0 else 0

    # Clip-level
    pred_clips = construct_clips_from_labels(predicted, tau)
    tp_c = 0
    ious = []
    start_errs = []
    end_errs = []

    for ps, pe, pd_ in pred_clips:
        best_iou = 0
        best_gt = None
        for gs, ge, gd in gt_clips:
            inter = max(0, min(pe, ge) - max(ps, gs) + 1)
            union = max(pe, ge) - min(ps, gs) + 1
            iou = inter / union if union > 0 else 0
            if iou > best_iou:
                best_iou = iou
                best_gt = (gs, ge, gd)
        if best_iou > 0.3:
            tp_c += 1
            ious.append(best_iou)
            if best_gt:
                start_errs.append(abs(ps - best_gt[0]))
                end_errs.append(abs(pe - best_gt[1]))

    fp_c = len(pred_clips) - tp_c
    fn_c = len(gt_clips) - tp_c
    clip_prec = tp_c / len(pred_clips) if pred_clips else 0
    clip_rec = tp_c / len(gt_clips) if gt_clips else 0
    clip_f1 = 2 * clip_prec * clip_rec / (clip_prec + clip_rec) if (clip_prec + clip_rec) > 0 else 0

    # Fragmentation
    frag = 0
    for gs, ge, gd in gt_clips:
        overlapping = [p for p in pred_clips if p[0] <= ge and p[1] >= gs]
        if len(overlapping) > 1:
            frag += len(overlapping) - 1

    return {
        'frame_precision': frame_prec,
        'frame_recall': frame_rec,
        'frame_fpr': frame_fpr,
        'frame_fnr': frame_fnr,
        'clip_precision': clip_prec,
        'clip_recall': clip_rec,
        'clip_f1': clip_f1,
        'mean_iou': np.mean(ious) if ious else 0,
        'mean_start_error': np.mean(start_errs) if start_errs else 0,
        'mean_end_error': np.mean(end_errs) if end_errs else 0,
        'fragmentation_rate': frag / len(gt_clips) if gt_clips else 0,
        'n_predicted_clips': len(pred_clips),
        'n_gt_clips': len(gt_clips),
        'n_matched_clips': tp_c,
    }


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("Running kinematic AQP experiments (v2)")
    print("=" * 60)

    track_table = pd.read_csv(TRACK_TABLE_PATH)
    count_table = pd.read_csv(COUNT_TABLE_PATH)
    clips_df = pd.read_json(CLIPS_PATH, lines=True)

    # Sample 100 long tracks
    track_lengths = track_table.groupby(['video_id', 'track_id']).size()
    long_tracks = track_lengths[track_lengths >= 30].reset_index()
    long_tracks.columns = ['video_id', 'track_id', 'length']
    rng = np.random.RandomState(SEEDS[0])
    if len(long_tracks) > 100:
        sampled = long_tracks.sample(n=100, random_state=rng)
    else:
        sampled = long_tracks
    track_keys = set(zip(sampled['video_id'], sampled['track_id']))

    print(f"Using {len(sampled)} tracks")

    all_results = []

    # Track-level queries
    for query_col, query_name in [('in_image_label', 'in_image'), ('in_front_label', 'in_front')]:
        print(f"\nQuery: {query_name}")

        for tau in TAU_VALUES:
            tau_clips = clips_df[(clips_df['query'] == query_name) & (clips_df['tau'] == tau)]

            for (vid, tid), group in track_table.groupby(['video_id', 'track_id']):
                if (vid, tid) not in track_keys:
                    continue
                group = group.sort_values('frame_num').reset_index(drop=True)
                n = len(group)
                if n < tau:
                    continue

                labels = group[query_col].values
                cx = group['center_x'].values
                cy = group['center_y'].values
                area = group['bbox_area'].values

                # Get GT clips with local indices
                track_clips_raw = tau_clips[
                    (tau_clips['video_id'] == vid) & (tau_clips['track_id'] == tid)
                ]
                id_to_local = {row['id']: idx for idx, row in group.iterrows()}
                gt_clips = []
                for _, clip in track_clips_raw.iterrows():
                    ls = id_to_local.get(clip['start_idx'])
                    le = id_to_local.get(clip['end_idx'])
                    if ls is not None and le is not None:
                        gt_clips.append((int(ls), int(le), clip['duration']))

                for seed in SEEDS:
                    methods = [
                        ('naive_oracle', B0_naive_oracle(labels, cx, cy, area, tau, seed)),
                        ('fixed_rate_k2', B1_fixed_rate(labels, cx, cy, area, tau, seed, k=2)),
                        ('fixed_rate_k5', B1_fixed_rate(labels, cx, cy, area, tau, seed, k=5)),
                        ('fixed_rate_k10', B1_fixed_rate(labels, cx, cy, area, tau, seed, k=10)),
                        ('fixed_rate_k20', B1_fixed_rate(labels, cx, cy, area, tau, seed, k=20)),
                        ('linear_interp_k5', B2_linear_interp(labels, cx, cy, area, tau, seed, k=5)),
                        ('linear_interp_k10', B2_linear_interp(labels, cx, cy, area, tau, seed, k=10)),
                        ('linear_interp_k20', B2_linear_interp(labels, cx, cy, area, tau, seed, k=20)),
                        ('const_vel_k5', B3_const_vel(labels, cx, cy, area, tau, seed, k=5)),
                        ('const_vel_k10', B3_const_vel(labels, cx, cy, area, tau, seed, k=10)),
                        ('kalman_fixed_k5', B4_kalman_fixed(labels, cx, cy, area, tau, seed, k=5)),
                        ('kalman_fixed_k10', B4_kalman_fixed(labels, cx, cy, area, tau, seed, k=10)),
                        ('kalman_uncertainty_t20', B5_kalman_uncertainty(labels, cx, cy, area, tau, seed, thresh=20)),
                        ('kalman_uncertainty_t50', B5_kalman_uncertainty(labels, cx, cy, area, tau, seed, thresh=50)),
                        ('kalman_uncertainty_t100', B5_kalman_uncertainty(labels, cx, cy, area, tau, seed, thresh=100)),
                        ('boundary_only_m10', B6_boundary_only(labels, cx, cy, area, tau, seed, margin=10)),
                        ('boundary_only_m20', B6_boundary_only(labels, cx, cy, area, tau, seed, margin=20)),
                        ('boundary_only_m50', B6_boundary_only(labels, cx, cy, area, tau, seed, margin=50)),
                        ('query_impact_m20_g3', B7_query_impact(labels, cx, cy, area, tau, seed, margin=20, oracle_gap=3)),
                        ('query_impact_m20_g5', B7_query_impact(labels, cx, cy, area, tau, seed, margin=20, oracle_gap=5)),
                        ('query_impact_m30_g3', B7_query_impact(labels, cx, cy, area, tau, seed, margin=30, oracle_gap=3)),
                        ('query_impact_m30_g5', B7_query_impact(labels, cx, cy, area, tau, seed, margin=30, oracle_gap=5)),
                        ('query_impact_m50_g5', B7_query_impact(labels, cx, cy, area, tau, seed, margin=50, oracle_gap=5)),
                    ]

                    for method_name, (predicted, oracle_calls) in methods:
                        metrics = compute_metrics(predicted, labels, gt_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau,
                            'video_id': vid, 'track_id': tid, 'seed': seed,
                            'track_length': n,
                            'gt_positive_rate': labels.mean(),
                            'method': method_name,
                            'oracle_calls': oracle_calls,
                            'oracle_call_ratio': oracle_calls / n,
                            **metrics,
                        })

    # Frame-count query (count >= K for tau frames)
    print("\nQuery: count_ge_K")
    for K in [3, 5]:
        for tau in [10, 20]:
            # Build count-based clips
            for vid, vgroup in count_table.groupby('video_id'):
                vgroup = vgroup.sort_values('frame_num').reset_index(drop=True)
                counts = vgroup['vehicle_count'].values
                count_labels = (counts >= K).astype(int)
                gt_clips = construct_clips_from_labels(count_labels, tau)
                n = len(counts)

                for seed in SEEDS:
                    for k in [2, 5, 10, 20]:
                        predicted, oracle_calls = B8_count_fixed_rate(counts, K, tau, seed, k=k)
                        metrics = compute_metrics(predicted, count_labels, gt_clips, tau)
                        all_results.append({
                            'query': f'count_ge_{K}', 'tau': tau,
                            'video_id': vid, 'track_id': -1, 'seed': seed,
                            'track_length': n,
                            'gt_positive_rate': count_labels.mean(),
                            'method': f'fixed_rate_k{k}',
                            'oracle_calls': oracle_calls,
                            'oracle_call_ratio': oracle_calls / n,
                            **metrics,
                        })

                    for gap in [3, 5, 10]:
                        predicted, oracle_calls = B8_count_query_impact(counts, K, tau, seed, oracle_gap=gap)
                        metrics = compute_metrics(predicted, count_labels, gt_clips, tau)
                        all_results.append({
                            'query': f'count_ge_{K}', 'tau': tau,
                            'video_id': vid, 'track_id': -1, 'seed': seed,
                            'track_length': n,
                            'gt_positive_rate': count_labels.mean(),
                            'method': f'query_impact_g{gap}',
                            'oracle_calls': oracle_calls,
                            'oracle_call_ratio': oracle_calls / n,
                            **metrics,
                        })

    # Save results
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(os.path.join(OUTPUT_DIR, 'metrics.csv'), index=False)
    print(f"\nSaved metrics: {len(results_df)} rows")

    # Generate summaries
    generate_summaries(results_df)


def generate_summaries(results_df):
    """Print and save summaries."""

    # Per-method summary
    method_summary = results_df.groupby(['query', 'tau', 'method']).agg({
        'clip_f1': ['mean', 'std'],
        'clip_recall': 'mean',
        'clip_precision': 'mean',
        'frame_recall': 'mean',
        'frame_precision': 'mean',
        'oracle_call_ratio': 'mean',
        'fragmentation_rate': 'mean',
        'mean_iou': 'mean',
    }).round(4)
    method_summary.columns = ['_'.join(col) for col in method_summary.columns]
    method_summary.to_csv(os.path.join(OUTPUT_DIR, 'per_method_summary.csv'))

    # Per-query summary
    query_summary = results_df.groupby(['query', 'method']).agg({
        'clip_f1': 'mean',
        'clip_recall': 'mean',
        'oracle_call_ratio': 'mean',
    }).round(4)
    query_summary.to_csv(os.path.join(OUTPUT_DIR, 'per_query_summary.csv'))

    # Key comparison
    print("\n" + "=" * 70)
    print("KEY COMPARISON: Methods ranked by Clip F1")
    print("=" * 70)

    for query in ['in_front', 'in_image', 'count_ge_3', 'count_ge_5']:
        for tau in [10, 20]:
            subset = results_df[(results_df['query'] == query) & (results_df['tau'] == tau)]
            if len(subset) == 0:
                continue

            print(f"\n--- Query={query}, tau={tau} ---")
            print(f"{'Method':<30} {'ClipF1':>8} {'ClipRec':>8} {'FrameRec':>9} {'Oracle%':>8} {'Frag':>6}")
            print("-" * 75)

            method_stats = subset.groupby('method').agg({
                'clip_f1': 'mean',
                'clip_recall': 'mean',
                'frame_recall': 'mean',
                'oracle_call_ratio': 'mean',
                'fragmentation_rate': 'mean',
            }).sort_values('clip_f1', ascending=False)

            for method, row in method_stats.iterrows():
                print(f"{method:<30} {row['clip_f1']:>8.4f} {row['clip_recall']:>8.4f} "
                      f"{row['frame_recall']:>9.4f} {row['oracle_call_ratio']:>8.4f} {row['fragmentation_rate']:>6.4f}")

    # Cost-quality tradeoff
    print("\n" + "=" * 70)
    print("COST-QUALITY TRADEOFF: Best F1 at each oracle budget level")
    print("=" * 70)

    for query in ['in_front', 'count_ge_3']:
        subset = results_df[results_df['query'] == query]
        if len(subset) == 0:
            continue

        print(f"\n--- Query={query}, tau=10 ---")
        s = subset[subset['tau'] == 10]
        # Bin by oracle_call_ratio
        s = s.copy()
        s['oracle_bin'] = pd.cut(s['oracle_call_ratio'], bins=[0, 0.05, 0.10, 0.20, 0.50, 1.01], labels=['0-5%', '5-10%', '10-20%', '20-50%', '50-100%'])
        pivot = s.groupby(['oracle_bin', 'method'])['clip_f1'].mean().reset_index()
        best_per_bin = pivot.loc[pivot.groupby('oracle_bin')['clip_f1'].idxmax()]
        print(best_per_bin.to_string(index=False))


if __name__ == '__main__':
    main()
