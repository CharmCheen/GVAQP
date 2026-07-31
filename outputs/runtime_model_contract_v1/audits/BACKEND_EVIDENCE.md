# Backend evidence

Formal source uses `Qwen3VLForConditionalGeneration.from_pretrained`, `AutoProcessor`, `torch.bfloat16`, `device_map=auto`, `trust_remote_code=True`, greedy generation, and `max_new_tokens=256`. Visual messages use RGB PIL video frames at 2 FPS.

YOLO uses Ultralytics `YOLO(path).predict(imgsz=640, conf=0.25, iou=0.45, device="cuda")` with classes `[0,1,2,3,5,7]`.
