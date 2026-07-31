from pathlib import Path
import os
import time
import torch

def load_yolo(model_path=None):
    from ultralytics import YOLO
    path = Path(model_path or os.environ["GARC_YOLO_MODEL"]).expanduser()
    return YOLO(str(path)), path

def infer_frame(model, frame, device="cuda:0", **overrides):
    cfg = {"imgsz": 640, "conf": 0.25, "iou": 0.45, "classes": [0, 1, 2, 3, 5, 7], "verbose": False}
    cfg.update(overrides)
    if torch.cuda.is_available(): torch.cuda.synchronize()
    t0 = time.perf_counter()
    result = model.predict(frame, device=device, **cfg)[0]
    if torch.cuda.is_available(): torch.cuda.synchronize()
    rows = []
    if result.boxes is not None:
        for box in result.boxes:
            rows.append({"xyxy": box.xyxy[0].detach().cpu().tolist(), "confidence": float(box.conf[0].detach().cpu()), "class_id": int(box.cls[0].detach().cpu())})
    return {"detections": rows, "latency_sec": time.perf_counter() - t0, "schema": "garc_yolo_detection_v1"}
