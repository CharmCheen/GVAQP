#!/usr/bin/env python3
"""Phase 3: Extract frames and build contact sheets for all samples."""
import os, sys, yaml, cv2, numpy as np, pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"

with open(f"{ROOT}/config/run_config.yaml") as f:
    cfg = yaml.safe_load(f)
with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)

VIDEO_PATH = paths["source_video"]
CONTACT_DIR = f"{ROOT}/inputs/contact_sheets"
os.makedirs(CONTACT_DIR, exist_ok=True)

N_FRAMES = cfg["n_contact_sheet_frames"]
TIMESTAMPS = cfg["contact_sheet_timestamps_s"]
GRID_COLS = cfg["contact_sheet_grid_cols"]
CELL_W, CELL_H = 480, 270
LABEL_H = 24

# Open video for metadata
cap = cv2.VideoCapture(VIDEO_PATH)
video_fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration_s = total_frames / video_fps if video_fps > 0 else 0
cap.release()
print(f"Video: {VIDEO_PATH}")
print(f"  FPS: {video_fps:.2f}, Duration: {duration_s:.1f}s, Frames: {total_frames}")

def extract_frame_at_time(time_s):
    """Extract a single frame at given time."""
    cap = cv2.VideoCapture(VIDEO_PATH)
    frame_idx = int(time_s * video_fps)
    frame_idx = max(0, min(frame_idx, total_frames - 1))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    if ret:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return None

def build_contact_sheet(anchor_id, start_time_s, end_time_s, out_path):
    """Extract frames and build a contact sheet image."""
    clip_start = max(0.0, start_time_s)
    clip_end = min(duration_s, end_time_s)
    clip_dur = clip_end - clip_start

    actual_ts = []
    for t_rel in TIMESTAMPS:
        if t_rel > clip_dur:
            t = clip_start + clip_dur * 0.95
        else:
            t = clip_start + t_rel
        actual_ts.append(round(t, 2))

    frames = []
    for t in actual_ts:
        frame = extract_frame_at_time(t)
        if frame is None:
            frame = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)
        frames.append(frame)

    n_rows = (N_FRAMES + GRID_COLS - 1) // GRID_COLS
    grid_w = GRID_COLS * CELL_W
    grid_h = n_rows * (CELL_H + LABEL_H)

    sheet = Image.new("RGB", (grid_w, grid_h), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        font = ImageFont.load_default()

    for i, (frame_arr, ts) in enumerate(zip(frames, actual_ts)):
        row = i // GRID_COLS
        col = i % GRID_COLS
        x = col * CELL_W
        y = row * (CELL_H + LABEL_H)

        frame_pil = Image.fromarray(frame_arr).resize((CELL_W, CELL_H), Image.LANCZOS)
        sheet.paste(frame_pil, (x, y))
        label = f"{ts:.1f}s"
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        lx = x + (CELL_W - tw) // 2
        ly = y + CELL_H + 2
        draw.text((lx, ly), label, fill=(200, 200, 200), font=font)

    sheet.save(out_path, quality=92)
    return out_path, actual_ts

# Process smoke manifest
for manifest_name in ["sample_manifest_smoke", "sample_manifest_paired"]:
    csv_path = f"{ROOT}/inputs/{manifest_name}.csv"
    if not os.path.isfile(csv_path):
        print(f"Manifest not found: {csv_path}")
        continue

    df = pd.read_csv(csv_path)
    timestamps = []
    for _, row in df.iterrows():
        aid = row["anchor_id"]
        start = row["start_time_s"]
        end = row["end_time_s"]
        out_path = f"{CONTACT_DIR}/{aid}.jpg"
        if os.path.isfile(out_path):
            timestamps.append(",".join(map(str, eval(str(row.get("actual_timestamps", "[]")) or "[]"))))
            continue
        _, actual_ts = build_contact_sheet(aid, start, end, out_path)
        timestamps.append(",".join(map(str, actual_ts)))
        sys.stdout.write(f"\r{manifest_name}: {aid}")
        sys.stdout.flush()
    print(f"\n{manifest_name}: {len(df)} contact sheets built")

# Update manifests with contact_sheet_path
for manifest_name in ["sample_manifest_smoke", "sample_manifest_paired"]:
    csv_path = f"{ROOT}/inputs/{manifest_name}.csv"
    df = pd.read_csv(csv_path)
    df["contact_sheet_path"] = df["anchor_id"].apply(lambda aid: f"{CONTACT_DIR}/{aid}.jpg")
    df["actual_timestamps"] = ""
    df.to_csv(csv_path, index=False)

print("\nContact sheet construction complete.")
print(f"Contact sheets in: {CONTACT_DIR}")
