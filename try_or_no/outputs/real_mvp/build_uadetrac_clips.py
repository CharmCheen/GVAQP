"""
Extract UA-DETRAC annotations from zip and build clip-level frame table.

UA-DETRAC has 60 video sequences with per-frame bounding box annotations.
Each sequence is a natural "clip" for our experiments.

We extract:
- per-frame vehicle counts (ground truth)
- per-clip labels (vehicle_count >= K)
- synthetic proxy scores

Output: uadetrac_frame_table.csv and uadetrac_clip_table.csv
"""

import pandas as pd
import numpy as np
import zipfile
import os
import io
import re

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
UA_DETRAC_ZIP = "/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/ua_detrac_training_set.zip"
K = 3
SEED = 42


def extract_annotations_from_zip(zip_path):
    """Extract all annotation CSVs from the UA-DETRAC zip."""
    all_frames = []

    with zipfile.ZipFile(zip_path, 'r') as zf:
        ann_files = [n for n in zf.namelist() if n.endswith('annotations.csv')]
        print(f"Found {len(ann_files)} annotation files")

        for ann_file in ann_files:
            # Extract sequence name (e.g., "detrac_1_MVI_20011")
            seq_name = ann_file.split('/')[0]

            content = zf.read(ann_file).decode('utf-8')
            df = pd.read_csv(io.StringIO(content))

            # Count vehicles per frame
            if 'filename' in df.columns and 'class' in df.columns:
                vehicle_counts = df.groupby('filename').size().reset_index(name='vehicle_count')
                vehicle_counts['video_id'] = seq_name
                vehicle_counts = vehicle_counts.rename(columns={'filename': 'frame_id'})
                all_frames.append(vehicle_counts)

    if not all_frames:
        print("ERROR: No annotations found!")
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    return result


def build_uadetrac_tables():
    """Build UA-DETRAC frame and clip tables."""
    print("=" * 60)
    print("Building UA-DETRAC clip tables")
    print("=" * 60)

    # Extract annotations
    frames_df = extract_annotations_from_zip(UA_DETRAC_ZIP)
    if len(frames_df) == 0:
        print("No data extracted. Exiting.")
        return

    print(f"Extracted {len(frames_df)} frames from {frames_df['video_id'].nunique()} videos")

    # Sort by video and frame
    frames_df = frames_df.sort_values(['video_id', 'frame_id']).reset_index(drop=True)
    frames_df['id'] = range(len(frames_df))

    # Derive oracle labels
    frames_df['label'] = (frames_df['vehicle_count_gt' if 'vehicle_count_gt' in frames_df.columns
                           else 'vehicle_count'] >= K).astype(int)

    # Rename if needed
    if 'vehicle_count' in frames_df.columns and 'vehicle_count_gt' not in frames_df.columns:
        frames_df = frames_df.rename(columns={'vehicle_count': 'vehicle_count_gt'})

    # Create synthetic proxy scores (same strategy as BDD100K)
    rng = np.random.RandomState(SEED)
    gt_counts = frames_df['vehicle_count_gt'].values.astype(float)
    detection_rate = 0.70
    noise_std = 1.5
    proxy_counts = gt_counts * detection_rate + rng.normal(0, noise_std, len(gt_counts))
    proxy_counts = np.maximum(proxy_counts, 0)

    log_proxy = np.log1p(proxy_counts)
    proxy_score = (log_proxy - log_proxy.min()) / (log_proxy.max() - log_proxy.min() + 1e-8)

    frames_df['vehicle_count_proxy'] = np.round(proxy_counts).astype(int)
    frames_df['proxy_score'] = proxy_score

    # Save frame table
    frame_cols = ['id', 'video_id', 'frame_id', 'label', 'proxy_score',
                  'vehicle_count_gt', 'vehicle_count_proxy']
    frames_out = frames_df[frame_cols]
    frame_path = os.path.join(OUTPUT_DIR, 'uadetrac_frame_table.csv')
    frames_out.to_csv(frame_path, index=False)
    print(f"Frame table saved: {frame_path}")

    # Build clip table: each video sequence is a clip
    clips = []
    for vid, group in frames_df.groupby('video_id'):
        group = group.sort_values('frame_id')
        labels = group['label'].values
        clip_label = 1 if labels.mean() >= 0.5 else 0

        clips.append({
            'clip_id': len(clips),
            'video_id': vid,
            'start_frame': group['frame_id'].iloc[0],
            'end_frame': group['frame_id'].iloc[-1],
            'n_frames': len(group),
            'clip_label': clip_label,
            'positive_frame_frac': labels.mean(),
            'mean_vehicle_count': group['vehicle_count_gt'].mean(),
        })

    clips_df = pd.DataFrame(clips)
    clip_path = os.path.join(OUTPUT_DIR, 'uadetrac_clip_table.csv')
    clips_df.to_csv(clip_path, index=False)
    print(f"Clip table saved: {clip_path}")

    # Summary
    print(f"\nSummary:")
    print(f"  Videos: {len(clips_df)}")
    print(f"  Total frames: {len(frames_df)}")
    print(f"  Positive clips (>= 50% frames with >= {K} vehicles): {clips_df['clip_label'].sum()}")
    print(f"  Frame positive rate: {frames_df['label'].mean():.4f}")
    print(f"  Mean vehicle count: {frames_df['vehicle_count_gt'].mean():.2f}")
    print(f"\n  Proxy type: SYNTHETIC (subsampled gt + Gaussian noise)")

    return frames_df, clips_df


if __name__ == '__main__':
    build_uadetrac_tables()
