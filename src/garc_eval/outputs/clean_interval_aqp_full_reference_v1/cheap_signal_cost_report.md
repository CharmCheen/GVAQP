# Cheap Signal Cost Report

Input detections: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/realcartest_proxy_materialization_v1/tables/raw_yolo_detections_realcartest_2fps.csv`.

Detection source: cached YOLOv8n 2fps detections from the local realcartest proxy materialization.

Rows read in selected segment: 14703 detections over 2400 sampled frames.

Signal materialization runtime in this run: 29.036s CPU wall time.

Tracking: simple class-aware IoU tracking at 2fps, no external tracker dependency.

Optical flow: downgraded to detection-derived `optical_flow_burst` because this clean AQP run avoids
expensive video-frame processing. This is recorded as an engineering limitation, not a research claim.
