#!/usr/bin/env python3
"""Create contact sheet from extracted 30s frames using PIL."""
import glob
import os
from PIL import Image

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1"
frames_dir = f"{ROOT}/contact_sheets/frames_30s"
out_path = f"{ROOT}/contact_sheets/realcartest_contact_sheet_30s.jpg"

frames = sorted(glob.glob(f"{frames_dir}/frame_*.jpg"))
print(f"Found {len(frames)} frames")

# Use up to 132 frames, 12 cols x 11 rows
use_frames = frames[:132]
cols = 12
rows = (len(use_frames) + cols - 1) // cols

thumb_w, thumb_h = 160, 90
canvas_w = cols * (thumb_w + 2)
canvas_h = rows * (thumb_h + 2)

canvas = Image.new("RGB", (canvas_w, canvas_h), (30, 30, 30))

for i, fpath in enumerate(use_frames):
    row = i // cols
    col = i % cols
    x = col * (thumb_w + 2)
    y = row * (thumb_h + 2)
    try:
        img = Image.open(fpath).resize((thumb_w, thumb_h), Image.LANCZOS)
        canvas.paste(img, (x, y))
    except Exception as e:
        print(f"  Error on {fpath}: {e}")

canvas.save(out_path, quality=85)
print(f"Contact sheet saved: {out_path} ({canvas_w}x{canvas_h})")
