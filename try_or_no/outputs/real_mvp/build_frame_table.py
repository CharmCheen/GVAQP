"""
PHASE 1-2: Build frame query table from BDD100K annotations.

Reads BDD100K object detection annotations, computes per-frame vehicle counts,
derives oracle labels (count(vehicle) >= K), and creates synthetic proxy scores.

Output: frame_query_table.csv with columns:
  id, video_id, frame_id, label, proxy_score, vehicle_count_gt, vehicle_count_proxy
"""

import pandas as pd
import numpy as np
import os
import sys

# === Configuration ===
K = 3  # threshold for label = 1[count(vehicle) >= K]
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
BDD_CSV = "/qiuyeqing/llama_prl/G-ARC/data/bdd100k/bdd100k/bdd100k.csv"
SEED = 42

# Vehicle classes in BDD100K
VEHICLE_CLASSES = {'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'rider', 'train', 'trailer', 'other vehicle'}


def load_bdd100k_annotations(csv_path):
    """Load BDD100K annotations and compute per-image vehicle counts."""
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} annotations across {df['image_path'].nunique()} images")

    # Filter to vehicle classes
    vehicles = df[df['class_name'].isin(VEHICLE_CLASSES)]

    # Count vehicles per image
    vehicle_counts = vehicles.groupby('image_path').size().reset_index(name='vehicle_count_gt')

    # Some images may have 0 vehicles
    all_images = df[['image_path']].drop_duplicates()
    vehicle_counts = all_images.merge(vehicle_counts, on='image_path', how='left')
    vehicle_counts['vehicle_count_gt'] = vehicle_counts['vehicle_count_gt'].fillna(0).astype(int)

    # Extract video_id from image path (BDD100K images are named like b1c66a42-6f7d68ca.jpg)
    vehicle_counts['video_id'] = vehicle_counts['image_path'].apply(
        lambda x: x.split('/')[-1].split('-')[0] if '-' in x.split('/')[-1] else 'unknown'
    )
    vehicle_counts['frame_id'] = vehicle_counts['image_path'].apply(
        lambda x: x.split('/')[-1].replace('.jpg', '')
    )

    return vehicle_counts


def derive_oracle_labels(vehicle_counts, K):
    """Derive oracle labels: 1 if vehicle_count >= K, else 0."""
    vehicle_counts['label'] = (vehicle_counts['vehicle_count_gt'] >= K).astype(int)
    return vehicle_counts


def create_proxy_scores(vehicle_counts, seed=SEED):
    """
    Create synthetic proxy scores.

    IMPORTANT: These are SYNTHETIC proxies over real labels.
    We simulate a noisy detector by:
    1. Subsampling annotations (simulating missed detections)
    2. Adding Gaussian noise to the count
    3. Converting to a [0,1] score

    This is NOT a real model proxy. It is clearly marked as synthetic.
    """
    rng = np.random.RandomState(seed)
    n = len(vehicle_counts)
    gt_counts = vehicle_counts['vehicle_count_gt'].values.astype(float)

    # Strategy: subsample gt counts + noise
    # Simulate ~70% detection rate with noise
    detection_rate = 0.70
    noise_std = 2.0

    proxy_counts = gt_counts * detection_rate + rng.normal(0, noise_std, n)
    proxy_counts = np.maximum(proxy_counts, 0)  # no negative counts

    # Normalize to [0, 1] using sigmoid-like transform
    # Use log(count + 1) to handle the heavy tail
    log_proxy = np.log1p(proxy_counts)
    log_gt = np.log1p(gt_counts)

    # Min-max normalize within the dataset
    proxy_score = (log_proxy - log_proxy.min()) / (log_proxy.max() - log_proxy.min() + 1e-8)

    vehicle_counts['vehicle_count_proxy'] = np.round(proxy_counts).astype(int)
    vehicle_counts['proxy_score'] = proxy_score

    return vehicle_counts


def build_frame_table():
    """Build the complete frame query table."""
    print("=" * 60)
    print("Building frame query table from BDD100K")
    print("=" * 60)

    # Load data
    vehicle_counts = load_bdd100k_annotations(BDD_CSV)

    # Derive oracle labels
    vehicle_counts = derive_oracle_labels(vehicle_counts, K)

    # Create proxy scores
    vehicle_counts = create_proxy_scores(vehicle_counts)

    # Assign sequential IDs
    vehicle_counts = vehicle_counts.sort_values('image_path').reset_index(drop=True)
    vehicle_counts['id'] = range(len(vehicle_counts))

    # Select output columns
    output_cols = ['id', 'video_id', 'frame_id', 'label', 'proxy_score',
                   'vehicle_count_gt', 'vehicle_count_proxy']
    result = vehicle_counts[output_cols]

    # Save
    output_path = os.path.join(OUTPUT_DIR, 'frame_query_table.csv')
    result.to_csv(output_path, index=False)

    # Print summary
    print(f"\nFrame query table saved to: {output_path}")
    print(f"Total records: {len(result)}")
    print(f"Positive labels (vehicle_count >= {K}): {result['label'].sum()}")
    print(f"Negative labels: {(result['label'] == 0).sum()}")
    print(f"Positive rate: {result['label'].mean():.4f}")
    print(f"\nVehicle count distribution:")
    print(result['vehicle_count_gt'].describe())
    print(f"\nProxy score distribution:")
    print(result['proxy_score'].describe())
    print(f"\nProxy type: SYNTHETIC (subsampled gt + Gaussian noise, detection_rate=0.70)")
    print(f"  This is NOT a real model proxy. It simulates a noisy detector.")

    return result


if __name__ == '__main__':
    build_frame_table()
