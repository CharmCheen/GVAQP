# Real model setup

Use the existing `.venv`, then set external cache paths. Run `python scripts/download_runtime_models.py --dry-run` before downloading. The fixed VLM revision is recorded in `configs/runtime_models.yaml`; no model substitution or quantization is enabled. Run `CUDA_VISIBLE_DEVICES=0 python scripts/smoke_test_real_yolo.py`, followed by the VLM and pipeline scripts after the complete snapshot is present.
