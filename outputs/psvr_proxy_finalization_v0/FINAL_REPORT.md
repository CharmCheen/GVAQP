# PSVR Proxy Finalization — Final Report

## Decision: SELECT_YOLOV8

### Selected Front-End
**YOLOV8**

| Field | Value |
|-------|-------|
| Detector | YOLOv8n |
| Resolution | 640 |
| Event Head | RULE_BASELINE |
| Model Path | /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt |
| Model SHA-256 | f59b3d833e2ff32e194b5bb8e08d211d... |
| Sample FPS | 5 |
| GPU-seconds/video-hour | 140.1 |
| End-to-end P95 | 8.2 ms |

### Offline Metrics (Winner)
- Unit AUPRC: 0.1150
- Unique Event Units@20: 3

### Limitations
- Single video only (long_video_dataset3)
- No human annotations
- Held-out not opened
- Not paper-ready (requires multi-video validation)
- Proxy score uses simple count+confidence rule (not full LightGBM track features on target)

### Next Steps
1. Integrate frozen proxy into PSVR runtime
2. Run neutral-scheduler PSVR physical pilot
3. Validate proxy value gate
4. Continue autonomous research (currently PAUSED_INPUT_REQUIRED for multi-video)
