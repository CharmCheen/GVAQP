# Real Video SUPG-style CSV Report


## 1. Purpose

This pipeline converts a real video into per-frame proxy/oracle records.
The **proxy** is a cheap YOLO model (YOLOv8n, 6.3 MB).
The **oracle** is a stronger YOLO model (YOLOv8x, 131 MB) used as **pseudo-oracle**, not human ground truth.

This CSV is a preliminary real-video input table for later SUPG/ARC/G-ARC experiments.
It is **not** an ARC reproduction and **not** a G-ARC guarantee.

## 2. Data Provenance

| Item | Value |
|------|-------|
| Video path | `/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4` |
| Processed frames | 200 |
| Frame stride | 1 |
| FPS | 24.00 |
| Duration | 3987.1s |
| Frame dimensions | 1920x1080 |
| Proxy model | `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt` |
| Oracle model | `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt` |
| Vehicle classes | ['car', 'bus', 'truck', 'motorcycle'] |
| Confidence threshold | 0.25 |
| Image size | 640 |
| Device | cuda:0 |
| Runtime | 11.1s |
| Processing FPS | 18.1 |

## 3. CSV Schema

Each row is one processed frame. Key columns:

| Column | Description |
|--------|-------------|
| `id` | Frame index (= `frame_idx`), used as SUPG row ID |
| `frame_idx` | Original video frame index |
| `processed_idx` | Sequential processed frame index |
| `timestamp_sec` | Frame timestamp in seconds |
| `proxy_vehicle_count` | Number of vehicle detections by proxy model |
| `oracle_vehicle_count` | Number of vehicle detections by oracle model |
| `proxy_score` | `proxy_vehicle_count + 0.01 * proxy_vehicle_conf_sum` |
| `oracle_score` | `oracle_vehicle_count + 0.01 * oracle_vehicle_conf_sum` |
| `proxy_score_supg` | Same as `proxy_score`, for SUPG compatibility |
| `proxy_positive_K{K}` | 1 if `proxy_vehicle_count >= K`, else 0 |
| `oracle_positive_K{K}` | 1 if `oracle_vehicle_count >= K`, else 0 |
| `label_K{K}` | Same as `oracle_positive_K{K}`, used as pseudo-label |

## 4. K Statistics

| K | Oracle Pos Count | Oracle Pos Rate | Proxy Pos Count | Proxy Pos Rate |
|---|-----------------|-----------------|-----------------|----------------|
| 5 | 54 | 0.2700 | 54 | 0.2700 |
| 10 | 53 | 0.2650 | 19 | 0.0950 |
| 20 | 0 | 0.0000 | 0 | 0.0000 |

## 5. Proxy/Oracle Agreement

Frame-level agreement between proxy and oracle positive labels:

| K | TP | FP | FN | TN | Precision | Recall | F1 |
|---|----|----|----|----|-----------|--------|----|
| 5 | 54 | 0 | 0 | 146 | 1.0000 | 1.0000 | 1.0000 |
| 10 | 19 | 0 | 34 | 147 | 1.0000 | 0.3585 | 0.5278 |
| 20 | 0 | 0 | 0 | 200 | 0.0000 | 0.0000 | 0.0000 |

## 6. Clip Statistics

Clips are maximal runs of consecutive positive frames. A clip requires length >= tau frames.

### tau=20, IoU threshold theta=0.5

| K | Oracle Clips | Proxy Clips | Clip Recall | Clip Precision | mIoU |
|---|-------------|-------------|-------------|----------------|------|
| 5 | 1 | 1 | 1.0000 | 1.0000 | 1.0000 |
| 10 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 |
| 20 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |

### tau=30, IoU threshold theta=0.5

| K | Oracle Clips | Proxy Clips | Clip Recall | Clip Precision | mIoU |
|---|-------------|-------------|-------------|----------------|------|
| 5 | 1 | 1 | 1.0000 | 1.0000 | 1.0000 |
| 10 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 |
| 20 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |

## 7. Limitations

1. **Oracle is YOLO pseudo-oracle**, not human ground truth. YOLOv8x is stronger than YOLOv8n but still a neural network with its own biases.
2. **Architecture bias**: Both models are YOLOv8 — they share backbone architecture. Proxy/oracle disagreements may underestimate true error rates.
3. **No ARC reproduction**: This pipeline does not implement ARC or any adaptive resource allocation algorithm.
4. **No G-ARC guarantee**: This CSV is an input table. It does not demonstrate G-ARC effectiveness.
5. **COCO classes only**: Both models use COCO-pretrained weights (80 classes). Non-COCO vehicle types will not be detected.
6. **No tracking**: This is frame-level detection only. Clip statistics are derived from consecutive frame thresholds, not multi-object tracking.
7. **K values are arbitrary**: The choice of K (5, 10, 20) is for exploration. Optimal K depends on the video scene and application.
