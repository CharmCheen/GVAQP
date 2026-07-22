# Final Proxy Specification

## Deployable Proxy
- Detector: YOLOv8n
- Weights: /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt
- SHA-256: f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36
- Resolution: 640
- Sample FPS: 5
- Tracker: ByteTrack (Simple IoU + Kalman)
- Event Head: RULE_BASELINE
- Feature Schema: PROXY_FEATURES_V1
- Confidence Threshold: 0.25
- NMS IoU: 0.45

## Cost Profile
- Model FPS: 128
- P50 latency: 7.9 ms
- GPU-seconds/video-hour (5fps): 140.1

## Evidence Quality
- Target: SINGLE_VIDEO_ONLY
- Human annotations: NONE
- Oracle labels: frozen PSVR benchmark reference (347 units, 26 events)
- DrivingDojo training: tag-based weak proxy labels (32 clips)
