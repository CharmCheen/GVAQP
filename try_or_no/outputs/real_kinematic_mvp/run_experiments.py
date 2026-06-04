"""
Run kinematic AQP experiments on UA-DETRAC real data.

Implements baselines B0-B9 and evaluates clip-level metrics.
"""

import pandas as pd
import numpy as np
import os
import json
from collections import defaultdict

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACK_TABLE_PATH = os.path.join(OUTPUT_DIR, 'kinematic_query_table.csv')
CLIPS_PATH = os.path.join(OUTPUT_DIR, 'ground_truth_clips.jsonl')
SEEDS = [42, 123, 456, 789, 101112]
BUDGETS_FRAC = [0.01, 0.02, 0.05, 0.10, 0.20]
TAU_VALUES = [5, 10, 20, 30]


# ============================================================
# Baselines
# ============================================================

def baseline_naive_oracle(track_data, query_col, tau, seed):
    """B0: Use oracle at every frame. Upper bound quality, full cost."""
    labels = track_data[query_col].values
    n = len(labels)
    return {
        'method': 'naive_oracle',
        'predicted_labels': labels.copy(),
        'oracle_calls': n,
        'oracle_call_ratio': 1.0,
    }


def baseline_fixed_rate_oracle(track_data, query_col, tau, seed, k=5):
    """B1: Observe oracle every k frames, hold last value."""
    rng = np.random.RandomState(seed)
    labels = track_data[query_col].values
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    for i in range(0, n, k):
        predicted[i] = labels[i]
        oracle_calls += 1
        # Hold for frames between oracle calls
        for j in range(i + 1, min(i + k, n)):
            predicted[j] = labels[i]

    return {
        'method': f'fixed_rate_k{k}',
        'predicted_labels': predicted,
        'oracle_calls': oracle_calls,
        'oracle_call_ratio': oracle_calls / n,
    }


def baseline_linear_interpolation(track_data, query_col, tau, seed, k=5):
    """B2: Observe oracle at sampled frames, interpolate between."""
    labels = track_data[query_col].values
    cx = track_data['center_x'].values
    cy = track_data['center_y'].values
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    # Sample oracle at fixed intervals
    sample_points = list(range(0, n, k))
    if sample_points[-1] != n - 1:
        sample_points.append(n - 1)

    oracle_calls = len(sample_points)

    # Interpolate labels between sample points
    for idx in range(len(sample_points) - 1):
        start = sample_points[idx]
        end = sample_points[idx + 1]
        start_label = labels[start]
        end_label = labels[end]

        # If both endpoints agree, fill with that value
        if start_label == end_label:
            predicted[start:end + 1] = start_label
        else:
            # Transition at midpoint
            mid = (start + end) // 2
            predicted[start:mid + 1] = start_label
            predicted[mid + 1:end + 1] = end_label

    return {
        'method': f'linear_interp_k{k}',
        'predicted_labels': predicted,
        'oracle_calls': oracle_calls,
        'oracle_call_ratio': oracle_calls / n,
    }


def baseline_constant_velocity(track_data, query_col, tau, seed, k=5):
    """B3: Use last observed state + velocity to extrapolate."""
    labels = track_data[query_col].values
    cx = track_data['center_x'].values
    cy = track_data['center_y'].values
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    # Define front region bounds
    front_x_min, front_x_max = 192, 768
    front_y_min, front_y_max = 0, 459

    last_oracle_idx = 0
    predicted[0] = labels[0]
    oracle_calls = 1

    for i in range(1, n):
        if i - last_oracle_idx >= k:
            # Time for oracle call
            predicted[i] = labels[i]
            oracle_calls += 1
            last_oracle_idx = i
        else:
            # Extrapolate from last oracle
            dt = i - last_oracle_idx
            if query_col == 'in_front_label':
                # Extrapolate position
                vx = track_data['vx'].values[last_oracle_idx]
                vy = track_data['vy'].values[last_oracle_idx]
                pred_cx = cx[last_oracle_idx] + vx * dt
                pred_cy = cy[last_oracle_idx] + vy * dt
                # Check if in front region
                in_front = (front_x_min <= pred_cx <= front_x_max and
                           front_y_min <= pred_cy <= front_y_max)
                predicted[i] = 1 if in_front else 0
            else:
                # For in_image, hold last value (conservative)
                predicted[i] = labels[last_oracle_idx]

    return {
        'method': f'const_vel_k{k}',
        'predicted_labels': predicted,
        'oracle_calls': oracle_calls,
        'oracle_call_ratio': oracle_calls / n,
    }


def baseline_kalman_fixed(track_data, query_col, tau, seed, k=5):
    """B4: Kalman prediction with fixed-interval oracle calls."""
    labels = track_data[query_col].values
    cx = track_data['center_x'].values
    cy = track_data['center_y'].values
    area = track_data['bbox_area'].values
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    # Simple 1D Kalman for center_x, center_y, area
    # State: [pos, vel]
    # Measurement: pos
    Q = 10.0  # process noise
    R = 50.0  # measurement noise

    front_x_min, front_x_max = 192, 768
    front_y_min, front_y_max = 0, 459
    min_area = 500

    for dim_data, dim_name in [(cx, 'x'), (cy, 'y'), (area, 'area')]:
        pass  # We'll do a simplified version below

    # Simplified: use position + velocity Kalman for center_x
    # State: [x, vx]
    F = np.array([[1, 1], [0, 1]])  # transition
    H = np.array([[1, 0]])  # observation
    Q_mat = np.eye(2) * Q
    R_mat = np.array([[R]])

    state = np.array([cx[0], 0.0])
    cov = np.eye(2) * 100

    last_oracle_idx = 0
    predicted[0] = labels[0]
    oracle_calls = 1

    for i in range(1, n):
        # Predict
        state_pred = F @ state
        cov_pred = F @ cov @ F.T + Q_mat

        if i - last_oracle_idx >= k:
            # Oracle call: update with measurement
            z = np.array([cx[i]])
            y = z - H @ state_pred
            S = H @ cov_pred @ H.T + R_mat
            K = cov_pred @ H.T @ np.linalg.inv(S)
            state = state_pred + (K @ y).flatten()
            cov = (np.eye(2) - K @ H) @ cov_pred
            predicted[i] = labels[i]
            oracle_calls += 1
            last_oracle_idx = i
        else:
            # Predict only
            state = state_pred
            cov = cov_pred
            # Use predicted position to determine label
            pred_x = state[0]
            if query_col == 'in_front_label':
                pred_cy = cy[last_oracle_idx] + (i - last_oracle_idx) * track_data['vy'].values[last_oracle_idx]
                in_front = (front_x_min <= pred_x <= front_x_max and
                           front_y_min <= pred_cy <= front_y_max)
                predicted[i] = 1 if in_front else 0
            else:
                # For in_image, check if predicted position is in image
                in_image = (0 <= pred_x <= 960 and area[last_oracle_idx] >= min_area)
                predicted[i] = 1 if in_image else 0

    return {
        'method': f'kalman_fixed_k{k}',
        'predicted_labels': predicted,
        'oracle_calls': oracle_calls,
        'oracle_call_ratio': oracle_calls / n,
    }


def baseline_kalman_uncertainty(track_data, query_col, tau, seed, uncertainty_thresh=50.0):
    """B5: Kalman prediction, trigger oracle when uncertainty exceeds threshold."""
    labels = track_data[query_col].values
    cx = track_data['center_x'].values
    cy = track_data['center_y'].values
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    Q = 10.0
    R = 50.0
    F = np.array([[1, 1], [0, 1]])
    H = np.array([[1, 0]])
    Q_mat = np.eye(2) * Q
    R_mat = np.array([[R]])

    state = np.array([cx[0], 0.0])
    cov = np.eye(2) * 100
    predicted[0] = labels[0]
    oracle_calls = 1

    front_x_min, front_x_max = 192, 768
    front_y_min, front_y_max = 0, 459

    for i in range(1, n):
        state_pred = F @ state
        cov_pred = F @ cov @ F.T + Q_mat

        # Check uncertainty
        uncertainty = np.sqrt(cov_pred[0, 0])

        if uncertainty > uncertainty_thresh:
            # High uncertainty: call oracle
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
            if query_col == 'in_front_label':
                pred_cy = cy[0]  # simplified
                in_front = (front_x_min <= pred_x <= front_x_max)
                predicted[i] = 1 if in_front else 0
            else:
                predicted[i] = 1 if 0 <= pred_x <= 960 else 0

    return {
        'method': f'kalman_uncertainty_t{int(uncertainty_thresh)}',
        'predicted_labels': predicted,
        'oracle_calls': oracle_calls,
        'oracle_call_ratio': oracle_calls / n,
    }


def baseline_boundary_only(track_data, query_col, tau, seed, margin=20.0):
    """B6: Trigger oracle when predicted state is near predicate boundary."""
    labels = track_data[query_col].values
    cx = track_data['center_x'].values
    cy = track_data['center_y'].values
    area = track_data['bbox_area'].values
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    front_x_min, front_x_max = 192, 768
    front_y_min, front_y_max = 0, 459
    min_area = 500

    # Simple extrapolation state
    last_cx = cx[0]
    last_cy = cy[0]
    last_vx = 0
    last_vy = 0
    predicted[0] = labels[0]
    oracle_calls = 1

    for i in range(1, n):
        # Extrapolate
        pred_cx = last_cx + last_vx
        pred_cy = last_cy + last_vy

        near_boundary = False
        if query_col == 'in_front_label':
            # Check if near front-region boundary
            dist_to_boundary = min(
                abs(pred_cx - front_x_min), abs(pred_cx - front_x_max),
                abs(pred_cy - front_y_min), abs(pred_cy - front_y_max)
            )
            near_boundary = dist_to_boundary < margin
        else:
            # Check if near image boundary
            dist_to_boundary = min(
                pred_cx, abs(pred_cx - 960),
                pred_cy, abs(pred_cy - 540)
            )
            near_boundary = dist_to_boundary < margin or area[i] < min_area * 2

        if near_boundary:
            # Call oracle
            predicted[i] = labels[i]
            oracle_calls += 1
            last_cx = cx[i]
            last_cy = cy[i]
            if i > 0:
                last_vx = cx[i] - cx[i - 1]
                last_vy = cy[i] - cy[i - 1]
        else:
            # Extrapolate
            predicted[i] = predicted[i - 1] if i > 0 else labels[0]
            last_cx = pred_cx
            last_cy = pred_cy

    return {
        'method': f'boundary_only_m{int(margin)}',
        'predicted_labels': predicted,
        'oracle_calls': oracle_calls,
        'oracle_call_ratio': oracle_calls / n,
    }


def baseline_query_impact_aware(track_data, query_col, tau, seed, margin=20.0, uncertainty_thresh=30.0):
    """B7: Query-impact-aware triggering.

    Trigger oracle only when:
    1. Uncertainty overlaps predicate boundary AND
    2. The ambiguity could change clip construction (near clip start/end/duration-critical)
    """
    labels = track_data[query_col].values
    cx = track_data['center_x'].values
    cy = track_data['center_y'].values
    area = track_data['bbox_area'].values
    n = len(labels)
    predicted = np.zeros(n, dtype=int)
    oracle_calls = 0

    front_x_min, front_x_max = 192, 768
    front_y_min, front_y_max = 0, 459
    min_area = 500

    # State tracking
    last_cx = cx[0]
    last_cy = cy[0]
    last_vx = 0
    last_vy = 0
    predicted[0] = labels[0]
    oracle_calls = 1

    # Track current run length of positive predictions
    current_run = 1 if labels[0] == 1 else 0

    for i in range(1, n):
        # Extrapolate
        pred_cx = last_cx + last_vx
        pred_cy = last_cy + last_vy

        # Check boundary proximity
        near_boundary = False
        if query_col == 'in_front_label':
            dist_to_boundary = min(
                abs(pred_cx - front_x_min), abs(pred_cx - front_x_max),
                abs(pred_cy - front_y_min), abs(pred_cy - front_y_max)
            )
            near_boundary = dist_to_boundary < margin
        else:
            dist_to_boundary = min(pred_cx, abs(pred_cx - 960), pred_cy, abs(pred_cy - 540))
            near_boundary = dist_to_boundary < margin or area[i] < min_area * 2

        # Check if near clip-critical region
        # Clip-critical: current run length is close to tau (start or end of potential clip)
        clip_critical = False
        for tau_val in TAU_VALUES:
            if abs(current_run - tau_val) <= 2 or current_run == tau_val - 1:
                clip_critical = True
                break
            if current_run == 1 or current_run == 0:
                clip_critical = True  # Near potential clip start
                break

        # Trigger oracle only if both conditions met
        if near_boundary and clip_critical:
            predicted[i] = labels[i]
            oracle_calls += 1
            last_cx = cx[i]
            last_cy = cy[i]
            if i > 0:
                last_vx = cx[i] - cx[i - 1]
                last_vy = cy[i] - cy[i - 1]
        else:
            predicted[i] = predicted[i - 1] if i > 0 else labels[0]
            last_cx = pred_cx
            last_cy = pred_cy

        # Update run length
        if predicted[i] == 1:
            current_run += 1
        else:
            current_run = 0

    return {
        'method': f'query_impact_m{int(margin)}',
        'predicted_labels': predicted,
        'oracle_calls': oracle_calls,
        'oracle_call_ratio': oracle_calls / n,
    }


# ============================================================
# Metrics
# ============================================================

def compute_clip_metrics(predicted_labels, oracle_labels, clips_subset, tau):
    """Compute clip-level metrics from predicted vs oracle labels."""
    n = len(oracle_labels)

    # Frame-level predicate metrics
    tp_frame = np.sum((predicted_labels == 1) & (oracle_labels == 1))
    fp_frame = np.sum((predicted_labels == 1) & (oracle_labels == 0))
    fn_frame = np.sum((predicted_labels == 0) & (oracle_labels == 1))
    tn_frame = np.sum((predicted_labels == 0) & (oracle_labels == 0))

    frame_precision = tp_frame / (tp_frame + fp_frame) if (tp_frame + fp_frame) > 0 else 0
    frame_recall = tp_frame / (tp_frame + fn_frame) if (tp_frame + fn_frame) > 0 else 0
    frame_fpr = fp_frame / (fp_frame + tn_frame) if (fp_frame + tn_frame) > 0 else 0
    frame_fnr = fn_frame / (fn_frame + tp_frame) if (fn_frame + tp_frame) > 0 else 0

    # Construct predicted clips from predicted labels
    predicted_clips = []
    in_run = False
    run_start = 0
    run_length = 0

    for i, label in enumerate(predicted_labels):
        if label == 1:
            if not in_run:
                run_start = i
                run_length = 1
                in_run = True
            else:
                run_length += 1
        else:
            if in_run and run_length >= tau:
                predicted_clips.append((run_start, run_start + run_length - 1, run_length))
            in_run = False
            run_length = 0

    if in_run and run_length >= tau:
        predicted_clips.append((run_start, run_start + run_length - 1, run_length))

    # Match predicted clips to ground truth clips (using local indices)
    gt_clips = []
    for _, clip in clips_subset.iterrows():
        if 'local_start' in clip and pd.notna(clip.get('local_start')):
            gt_clips.append((int(clip['local_start']), int(clip['local_end']), clip['duration']))
        else:
            gt_clips.append((clip['start_idx'], clip['end_idx'], clip['duration']))

    # Compute IoU-based matching
    tp_clip = 0
    ious = []
    start_errors = []
    end_errors = []

    for pred_start, pred_end, pred_dur in predicted_clips:
        best_iou = 0
        best_gt = None
        for gt_start, gt_end, gt_dur in gt_clips:
            intersection = max(0, min(pred_end, gt_end) - max(pred_start, gt_start) + 1)
            union = max(pred_end, gt_end) - min(pred_start, gt_start) + 1
            iou = intersection / union if union > 0 else 0
            if iou > best_iou:
                best_iou = iou
                best_gt = (gt_start, gt_end, gt_dur)

        if best_iou > 0.3:  # IoU threshold
            tp_clip += 1
            ious.append(best_iou)
            if best_gt:
                start_errors.append(abs(pred_start - best_gt[0]))
                end_errors.append(abs(pred_end - best_gt[1]))

    fp_clip = len(predicted_clips) - tp_clip
    fn_clip = len(gt_clips) - tp_clip

    clip_precision = tp_clip / len(predicted_clips) if predicted_clips else 0
    clip_recall = tp_clip / len(gt_clips) if gt_clips else 0
    clip_f1 = 2 * clip_precision * clip_recall / (clip_precision + clip_recall) if (clip_precision + clip_recall) > 0 else 0

    # Fragmentation: predicted clips that split a single GT clip
    fragmentation = 0
    for gt_start, gt_end, gt_dur in gt_clips:
        overlapping = [p for p in predicted_clips if p[0] <= gt_end and p[1] >= gt_start]
        if len(overlapping) > 1:
            fragmentation += len(overlapping) - 1

    return {
        'frame_precision': frame_precision,
        'frame_recall': frame_recall,
        'frame_fpr': frame_fpr,
        'frame_fnr': frame_fnr,
        'clip_precision': clip_precision,
        'clip_recall': clip_recall,
        'clip_f1': clip_f1,
        'mean_iou': np.mean(ious) if ious else 0,
        'mean_start_error': np.mean(start_errors) if start_errors else 0,
        'mean_end_error': np.mean(end_errors) if end_errors else 0,
        'fragmentation_rate': fragmentation / len(gt_clips) if gt_clips else 0,
        'n_predicted_clips': len(predicted_clips),
        'n_gt_clips': len(gt_clips),
        'n_matched_clips': tp_clip,
    }


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("Running kinematic AQP experiments on UA-DETRAC")
    print("=" * 60)

    # Load data
    track_table = pd.read_csv(TRACK_TABLE_PATH)
    clips_df = pd.read_json(CLIPS_PATH, lines=True)

    print(f"Track table: {len(track_table)} records")
    print(f"Clips: {len(clips_df)} total")

    # Limit to a manageable subset for initial experiments
    # Use tracks with at least 30 frames
    track_lengths = track_table.groupby(['video_id', 'track_id']).size()
    long_tracks = track_lengths[track_lengths >= 30].reset_index()
    long_tracks.columns = ['video_id', 'track_id', 'length']
    print(f"Tracks with >= 30 frames: {len(long_tracks)}")

    # Sample tracks for faster experimentation (use all if < 100)
    if len(long_tracks) > 100:
        rng = np.random.RandomState(SEEDS[0])
        sampled = long_tracks.sample(n=100, random_state=rng)
    else:
        sampled = long_tracks

    print(f"Using {len(sampled)} tracks for experiments")

    # Filter track table to sampled tracks
    track_keys = set(zip(sampled['video_id'], sampled['track_id']))
    track_table_filtered = track_table[
        track_table.apply(lambda r: (r['video_id'], r['track_id']) in track_keys, axis=1)
    ].copy()

    # All results
    all_results = []

    # Run experiments for each query
    for query_col, query_name in [('in_image_label', 'in_image'), ('in_front_label', 'in_front')]:
        print(f"\n{'=' * 60}")
        print(f"Query: {query_name} (column: {query_col})")
        print(f"{'=' * 60}")

        for tau in TAU_VALUES:
            # Get relevant clips
            tau_clips = clips_df[(clips_df['query'] == query_name) & (clips_df['tau'] == tau)]

            for (vid, tid), group in track_table_filtered.groupby(['video_id', 'track_id']):
                group = group.sort_values('frame_num').reset_index(drop=True)
                n = len(group)

                if n < tau:
                    continue

                oracle_labels = group[query_col].values
                gt_positive_rate = oracle_labels.mean()

                # Get clips for this track and remap to local indices
                track_clips = tau_clips[
                    (tau_clips['video_id'] == vid) & (tau_clips['track_id'] == tid)
                ].copy()
                # Create id-to-local mapping
                id_to_local = {row['id']: idx for idx, row in group.iterrows()}
                if len(track_clips) > 0:
                    track_clips['local_start'] = track_clips['start_idx'].map(id_to_local)
                    track_clips['local_end'] = track_clips['end_idx'].map(id_to_local)
                    # Drop clips that couldn't be mapped
                    track_clips = track_clips.dropna(subset=['local_start', 'local_end'])
                    track_clips['local_start'] = track_clips['local_start'].astype(int)
                    track_clips['local_end'] = track_clips['local_end'].astype(int)

                for seed in SEEDS:
                    # B0: Naive oracle
                    result = baseline_naive_oracle(group, query_col, tau, seed)
                    metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                    all_results.append({
                        'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                        'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                        'method': result['method'],
                        'oracle_calls': result['oracle_calls'],
                        'oracle_call_ratio': result['oracle_call_ratio'],
                        **metrics,
                    })

                    # B1: Fixed rate oracle (k=2,5,10,20)
                    for k in [2, 5, 10, 20]:
                        result = baseline_fixed_rate_oracle(group, query_col, tau, seed, k=k)
                        metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                            'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                            'method': result['method'],
                            'oracle_calls': result['oracle_calls'],
                            'oracle_call_ratio': result['oracle_call_ratio'],
                            **metrics,
                        })

                    # B2: Linear interpolation (k=5,10,20)
                    for k in [5, 10, 20]:
                        result = baseline_linear_interpolation(group, query_col, tau, seed, k=k)
                        metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                            'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                            'method': result['method'],
                            'oracle_calls': result['oracle_calls'],
                            'oracle_call_ratio': result['oracle_call_ratio'],
                            **metrics,
                        })

                    # B3: Constant velocity (k=5,10)
                    for k in [5, 10]:
                        result = baseline_constant_velocity(group, query_col, tau, seed, k=k)
                        metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                            'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                            'method': result['method'],
                            'oracle_calls': result['oracle_calls'],
                            'oracle_call_ratio': result['oracle_call_ratio'],
                            **metrics,
                        })

                    # B4: Kalman fixed interval (k=5,10)
                    for k in [5, 10]:
                        result = baseline_kalman_fixed(group, query_col, tau, seed, k=k)
                        metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                            'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                            'method': result['method'],
                            'oracle_calls': result['oracle_calls'],
                            'oracle_call_ratio': result['oracle_call_ratio'],
                            **metrics,
                        })

                    # B5: Kalman uncertainty-only (thresholds 20, 50, 100)
                    for thresh in [20, 50, 100]:
                        result = baseline_kalman_uncertainty(group, query_col, tau, seed, uncertainty_thresh=thresh)
                        metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                            'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                            'method': result['method'],
                            'oracle_calls': result['oracle_calls'],
                            'oracle_call_ratio': result['oracle_call_ratio'],
                            **metrics,
                        })

                    # B6: Boundary-only trigger (margin=10,20,50)
                    for margin in [10, 20, 50]:
                        result = baseline_boundary_only(group, query_col, tau, seed, margin=margin)
                        metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                            'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                            'method': result['method'],
                            'oracle_calls': result['oracle_calls'],
                            'oracle_call_ratio': result['oracle_call_ratio'],
                            **metrics,
                        })

                    # B7: Query-impact-aware trigger (margin=20, uncertainty=30)
                    for margin in [10, 20, 50]:
                        result = baseline_query_impact_aware(group, query_col, tau, seed, margin=margin)
                        metrics = compute_clip_metrics(result['predicted_labels'], oracle_labels, track_clips, tau)
                        all_results.append({
                            'query': query_name, 'tau': tau, 'video_id': vid, 'track_id': tid,
                            'seed': seed, 'track_length': n, 'gt_positive_rate': gt_positive_rate,
                            'method': result['method'],
                            'oracle_calls': result['oracle_calls'],
                            'oracle_call_ratio': result['oracle_call_ratio'],
                            **metrics,
                        })

    # Save results
    results_df = pd.DataFrame(all_results)
    metrics_path = os.path.join(OUTPUT_DIR, 'metrics.csv')
    results_df.to_csv(metrics_path, index=False)
    print(f"\nSaved metrics: {metrics_path} ({len(results_df)} rows)")

    # Generate summaries
    generate_summaries(results_df)


def generate_summaries(results_df):
    """Generate per-query, per-method, per-scene summaries."""

    # Per-method summary (averaged over all seeds, tracks, queries)
    method_summary = results_df.groupby(['query', 'tau', 'method']).agg({
        'clip_recall': ['mean', 'std'],
        'clip_precision': ['mean', 'std'],
        'clip_f1': ['mean', 'std'],
        'mean_iou': 'mean',
        'frame_recall': 'mean',
        'frame_precision': 'mean',
        'oracle_call_ratio': 'mean',
        'fragmentation_rate': 'mean',
        'mean_start_error': 'mean',
        'mean_end_error': 'mean',
    }).round(4)
    method_summary.columns = ['_'.join(col) for col in method_summary.columns]
    method_path = os.path.join(OUTPUT_DIR, 'per_method_summary.csv')
    method_summary.to_csv(method_path)
    print(f"Saved: {method_path}")

    # Per-query summary
    query_summary = results_df.groupby(['query', 'method']).agg({
        'clip_recall': 'mean',
        'clip_f1': 'mean',
        'oracle_call_ratio': 'mean',
    }).round(4)
    query_path = os.path.join(OUTPUT_DIR, 'per_query_summary.csv')
    query_summary.to_csv(query_path)
    print(f"Saved: {query_path}")

    # Per-scene summary (top 10 tracks by length)
    scene_summary = results_df.groupby(['video_id', 'track_id', 'method']).agg({
        'clip_f1': 'mean',
        'oracle_call_ratio': 'mean',
        'track_length': 'first',
    }).round(4)
    scene_path = os.path.join(OUTPUT_DIR, 'per_scene_summary.csv')
    scene_summary.to_csv(scene_path)
    print(f"Saved: {scene_path}")

    # Print key comparison
    print("\n" + "=" * 60)
    print("KEY COMPARISON: Query-Impact-Aware vs Strong Baselines")
    print("=" * 60)

    for query in results_df['query'].unique():
        for tau in [10, 20]:
            subset = results_df[(results_df['query'] == query) & (results_df['tau'] == tau)]
            if len(subset) == 0:
                continue

            print(f"\nQuery={query}, tau={tau}:")
            print(f"{'Method':<35} {'ClipF1':>8} {'ClipRec':>8} {'Oracle%':>8} {'FragRate':>8}")
            print("-" * 75)

            # Group by method and average
            method_stats = subset.groupby('method').agg({
                'clip_f1': 'mean',
                'clip_recall': 'mean',
                'oracle_call_ratio': 'mean',
                'fragmentation_rate': 'mean',
            }).sort_values('clip_f1', ascending=False)

            for method, row in method_stats.head(15).iterrows():
                print(f"{method:<35} {row['clip_f1']:>8.4f} {row['clip_recall']:>8.4f} "
                      f"{row['oracle_call_ratio']:>8.4f} {row['fragmentation_rate']:>8.4f}")


if __name__ == '__main__':
    main()
