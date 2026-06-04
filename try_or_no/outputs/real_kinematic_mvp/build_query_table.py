"""
Build kinematic query table from UA-DETRAC annotations.

Extracts per-track bounding box annotations from the UA-DETRAC zip,
defines 2D fallback queries, and builds a compact query table.

Output: kinematic_query_table.csv with per-track-frame records.
"""

import pandas as pd
import numpy as np
import zipfile
import io
import os
import json

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
UA_DETRAC_ZIP = "/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/ua_detrac_training_set.zip"
SEED = 42

# Image dimensions (UA-DETRAC)
IMG_W = 960
IMG_H = 540

# Front-region definition (center 60% of image width, top 80%)
FRONT_X_MIN = int(IMG_W * 0.20)
FRONT_X_MAX = int(IMG_W * 0.80)
FRONT_Y_MIN = 0
FRONT_Y_MAX = int(IMG_H * 0.85)

# Minimum bbox area to count as "visible" (not tiny/occluded)
MIN_BBOX_AREA = 500


def extract_all_annotations(zip_path):
    """Extract all annotation CSVs from the UA-DETRAC zip."""
    all_records = []

    with zipfile.ZipFile(zip_path, 'r') as zf:
        ann_files = [n for n in zf.namelist() if n.endswith('annotations.csv')]
        print(f"Found {len(ann_files)} annotation files")

        for ann_file in ann_files:
            seq_name = ann_file.split('/')[0]
            content = zf.read(ann_file).decode('utf-8')
            df = pd.read_csv(io.StringIO(content))

            if 'filename' not in df.columns or 'target_id' not in df.columns:
                continue

            # Extract frame number from filename
            df['frame_num'] = df['filename'].str.extract(r'(\d+)').astype(int)
            df['video_id'] = seq_name

            # Compute bbox properties
            df['bbox_w'] = df['xmax'] - df['xmin']
            df['bbox_h'] = df['ymax'] - df['ymin']
            df['bbox_area'] = df['bbox_w'] * df['bbox_h']
            df['center_x'] = (df['xmin'] + df['xmax']) / 2
            df['center_y'] = (df['ymin'] + df['ymax']) / 2

            all_records.append(df)

    result = pd.concat(all_records, ignore_index=True)
    print(f"Total records: {len(result)}")
    print(f"Videos: {result['video_id'].nunique()}")
    print(f"Unique tracks (target_id > 0): {(result['target_id'] > 0).sum()}")
    return result


def define_queries(df):
    """
    Define 2D fallback queries from bounding box annotations.

    Q1: in_image — target has bbox with area >= MIN_BBOX_AREA
    Q2: in_front_region — target center is in the front region
    Q3: count_at_least_K — at least K vehicles in frame

    Also computes per-track state: center_x, center_y, bbox_area (for Kalman).
    """
    # Filter to tracked objects (target_id > 0)
    tracked = df[df['target_id'] > 0].copy()

    # Q1: in_image label
    tracked['in_image_label'] = (tracked['bbox_area'] >= MIN_BBOX_AREA).astype(int)

    # Q2: in_front_region label
    tracked['in_front_label'] = (
        (tracked['center_x'] >= FRONT_X_MIN) &
        (tracked['center_x'] <= FRONT_X_MAX) &
        (tracked['center_y'] >= FRONT_Y_MIN) &
        (tracked['center_y'] <= FRONT_Y_MAX) &
        (tracked['bbox_area'] >= MIN_BBOX_AREA)
    ).astype(int)

    # Per-frame vehicle counts
    frame_counts = tracked.groupby(['video_id', 'frame_num']).size().reset_index(name='vehicle_count')

    return tracked, frame_counts


def build_track_table(tracked):
    """
    Build per-track-frame table with state and labels.

    Each row is one (track, frame) pair with:
    - track state (center_x, center_y, bbox_area)
    - oracle labels (in_image, in_front)
    """
    records = []
    global_id = 0

    for (vid, tid), group in tracked.groupby(['video_id', 'target_id']):
        group = group.sort_values('frame_num')

        # Compute velocities (frame-to-frame differences)
        cx = group['center_x'].values
        cy = group['center_y'].values
        area = group['bbox_area'].values

        vx = np.diff(cx, prepend=cx[0])
        vy = np.diff(cy, prepend=cy[0])
        v_area = np.diff(area, prepend=area[0])

        for i, (_, row) in enumerate(group.iterrows()):
            records.append({
                'id': global_id,
                'video_id': vid,
                'track_id': tid,
                'frame_num': int(row['frame_num']),
                'timestamp': round(row['frame_num'] / 25.0, 4),  # 25 FPS
                'center_x': row['center_x'],
                'center_y': row['center_y'],
                'bbox_area': row['bbox_area'],
                'bbox_w': row['bbox_w'],
                'bbox_h': row['bbox_h'],
                'vx': vx[i],
                'vy': vy[i],
                'v_area': v_area[i],
                'in_image_label': int(row['in_image_label']),
                'in_front_label': int(row['in_front_label']),
            })
            global_id += 1

    return pd.DataFrame(records)


def build_frame_count_table(frame_counts):
    """Build per-frame vehicle count table for count-based queries."""
    records = []
    global_id = 0

    for _, row in frame_counts.iterrows():
        records.append({
            'id': global_id,
            'video_id': row['video_id'],
            'frame_num': int(row['frame_num']),
            'timestamp': round(row['frame_num'] / 25.0, 4),
            'vehicle_count': int(row['vehicle_count']),
        })
        global_id += 1

    return pd.DataFrame(records)


def construct_ground_truth_clips(track_table, tau_values=[5, 10, 20, 30]):
    """
    Construct ground-truth clips from oracle labels.

    A clip is a contiguous run of frames where the predicate holds for >= tau frames.
    """
    clips = []
    clip_id = 0

    for query_col, query_name in [('in_image_label', 'in_image'), ('in_front_label', 'in_front')]:
        for tau in tau_values:
            for (vid, tid), group in track_table.groupby(['video_id', 'track_id']):
                group = group.sort_values('frame_num')
                labels = group[query_col].values
                frame_nums = group['frame_num'].values

                # Find contiguous runs of 1s
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
                            clips.append({
                                'clip_id': clip_id,
                                'video_id': vid,
                                'track_id': tid,
                                'query': query_name,
                                'tau': tau,
                                'start_frame': int(frame_nums[run_start]),
                                'end_frame': int(frame_nums[run_start + run_length - 1]),
                                'duration': run_length,
                                'start_idx': int(group['id'].iloc[run_start]),
                                'end_idx': int(group['id'].iloc[run_start + run_length - 1]),
                            })
                            clip_id += 1
                        in_run = False
                        run_length = 0

                # Handle run at end
                if in_run and run_length >= tau:
                    clips.append({
                        'clip_id': clip_id,
                        'video_id': vid,
                        'track_id': tid,
                        'query': query_name,
                        'tau': tau,
                        'start_frame': int(frame_nums[run_start]),
                        'end_frame': int(frame_nums[run_start + run_length - 1]),
                        'duration': run_length,
                        'start_idx': int(group['id'].iloc[run_start]),
                        'end_idx': int(group['id'].iloc[run_start + run_length - 1]),
                    })
                    clip_id += 1

    return pd.DataFrame(clips)


def main():
    print("=" * 60)
    print("Building kinematic query table from UA-DETRAC")
    print("=" * 60)

    # Extract annotations
    raw_df = extract_all_annotations(UA_DETRAC_ZIP)

    # Define queries
    tracked, frame_counts = define_queries(raw_df)

    # Build track table
    track_table = build_track_table(tracked)
    print(f"\nTrack table: {len(track_table)} records")
    print(f"  Tracks: {track_table['track_id'].nunique()}")
    print(f"  Videos: {track_table['video_id'].nunique()}")
    print(f"  In-image rate: {track_table['in_image_label'].mean():.4f}")
    print(f"  In-front rate: {track_table['in_front_label'].mean():.4f}")

    # Build frame count table
    count_table = build_frame_count_table(frame_counts)
    print(f"\nFrame count table: {len(count_table)} records")
    print(f"  Mean vehicle count: {count_table['vehicle_count'].mean():.2f}")

    # Construct ground-truth clips
    clips_df = construct_ground_truth_clips(track_table)
    print(f"\nGround-truth clips: {len(clips_df)}")
    for query_name in clips_df['query'].unique():
        for tau in clips_df['tau'].unique():
            n = len(clips_df[(clips_df['query'] == query_name) & (clips_df['tau'] == tau)])
            print(f"  {query_name}, tau={tau}: {n} clips")

    # Save outputs
    track_path = os.path.join(OUTPUT_DIR, 'kinematic_query_table.csv')
    track_table.to_csv(track_path, index=False)
    print(f"\nSaved: {track_path}")

    count_path = os.path.join(OUTPUT_DIR, 'frame_count_table.csv')
    count_table.to_csv(count_path, index=False)
    print(f"Saved: {count_path}")

    clips_path = os.path.join(OUTPUT_DIR, 'ground_truth_clips.jsonl')
    clips_df.to_json(clips_path, orient='records', lines=True)
    print(f"Saved: {clips_path}")

    # Print summary statistics
    print("\n" + "=" * 60)
    print("Summary Statistics")
    print("=" * 60)

    for vid in sorted(track_table['video_id'].unique())[:10]:
        v = track_table[track_table['video_id'] == vid]
        print(f"  {vid}: {len(v)} records, {v['track_id'].nunique()} tracks")
    if track_table['video_id'].nunique() > 10:
        print(f"  ... and {track_table['video_id'].nunique() - 10} more videos")


if __name__ == '__main__':
    main()
