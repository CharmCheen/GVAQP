# VLM 32B GPU-Verified Probe

This probe runs one target clip interval after forced CUDA model loading and verifies that model parameters are on CUDA before full-loop resume.

| model_name | device_name | num_gpus | dtype | quantization | frames_per_clip_or_fps | resolution_or_max_pixels | runtime_seconds | model_load_seconds | peak_gpu_memory_observed | model_parameter_device | gpu_memory_allocated_before_inference_gb | gpu_memory_allocated_after_inference_gb | gpu_memory_reserved_after_inference_gb | device_status | success_or_failure | error_message |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3-VL-32B-Instruct | NVIDIA A100-SXM4-80GB | 1 | torch.bfloat16 | none | 1.0 | 230400 | 27.153 | 99.777 | 62.59 | cuda:0 | 62.133 | 62.141 | 62.67 | gpu_verified | success |  |
