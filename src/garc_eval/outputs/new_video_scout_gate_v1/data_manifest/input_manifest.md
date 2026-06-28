# Input Manifest — P0 New-Video Scout Gate

## Videos under scout screening (newly downloaded continuous driving footage)

| video_id | path | size | role |
|---|---|---|---|
| dataset2 | `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset2.mp4` | 1.16 GB | scout candidate |
| dataset3 | `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4` | 1.18 GB | scout candidate |

## Reference video (NOT modified, NOT re-run; for schema/criteria calibration only)

| video_id | path | role |
|---|---|---|
| realcartest | `/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4` | V13.8 reference (1920x1080 24fps 66.5min, 51 stitched VLM events, proxy AUC ~0.74) |

## Cheap signal sources

- ffprobe / ffmpeg (metadata) — live subprocess call
- cv2.VideoCapture (sequential single-pass frame read) — motion energy @ 2fps + midpoint frame stash
- YOLOv8n (`models/yolo/yolov8n.pt`) — 1 midpoint frame per 5s window, batched on A800 GPU
- PIL / cv2 montage — 1 frame per 60s contact sheet

## Forbidden in this task (enforced)

- No VLM / LLM oracle calls (no Qwen3-VL, no 32B, no 8B)
- No semantic event label generation
- No interpretation of proxy high-score windows as real events
- No use of conservative VLM full-scan labels for ranking / candidate construction

## Output CSV schema (V13.5 superset)

`tables/window_features_<video_id>.csv` — 5s-window coarse proxy features.
First 18 columns match V13.5 `proxy_features_5s.csv` exactly; 6 extra scout
columns appended (`person_count, bicycle_count, motorcycle_count,
near_ego_vehicle_count, bbox_cx_std, lateral_presence_count`).

## Leakage / misuse note

These scout features are cheap-proxy-only. They MUST NOT be used as oracle
labels, MUST NOT be described as real risk-event ground truth, and (per AQP
policy) conservative VLM labels — if ever produced later — must not be used for
ranking, candidate cluster construction, hyperparameter selection, or learned
proxy training. The scout output is a candidate-generator instance + a
non-degeneracy screen, nothing more.
