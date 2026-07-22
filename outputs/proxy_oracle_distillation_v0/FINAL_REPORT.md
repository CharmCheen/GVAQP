# H-PROXY1U / H-DISTILL1 Final Report

## Status
- **H-PROXY1U**: SELECT_YOLOV8N
- **H-DISTILL1**: ACCEPT

## Selected Front-End
**YOLOv8n + ByteTrack + motion proxy**

## Selected Event Head
**LightGBM**

## Key Metrics
| Metric | Value |
|--------|-------|
| DrivingDojo Test AUPRC (LightGBM) | 0.3598 |
| Target Unit AUPRC | 0.1189 |
| Target Candidate Recall@20 | 0.0769 |
| Target Unique Event Recall@20 | 0.0769 |
| Human Annotations Used | False |

## Limitations
- DrivingDojo training labels are tag-based weak proxies, NOT oracle-verified
- Target oracle labels are from PSVR benchmark (frozen reference, not re-run)
- No human detection/tracking/lane ground truth
- Single target video (long_video_dataset3)
- Feature extraction on DrivingDojo uses ~5fps sampling

## Next Steps
1. If oracle distillation accepted: run frozen Qwen3-VL oracle on ALL DrivingDojo clips to replace weak tag-based labels
2. Retrain LightGBM with oracle-verified labels
3. If H-PROXY1U = SELECT_YOLOP_640 and H-DISTILL1 = ACCEPT: proceed to PSVR integration
