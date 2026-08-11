# Runtime model contract

The frozen physical runtime contract is YOLOv8n (`yolov8n.pt`, SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`) plus Qwen3-VL-32B-Instruct. The VLM prompt is byte-preserved in `configs/prompts/confirm_visual.yaml`; the parser preserves the source's permissive `label`/`confidence` status policy.

Set `GARC_YOLO_MODEL`, `GARC_VLM_MODEL`, `HF_HOME`, and `GARC_MODEL_CACHE` to external, writable paths. The source absolute paths are not used by runtime code.
