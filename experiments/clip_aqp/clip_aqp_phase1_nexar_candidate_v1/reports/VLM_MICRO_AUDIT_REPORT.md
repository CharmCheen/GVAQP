# VLM Micro-Audit Report

- model_name: Qwen3-VL-32B-Instruct
- quantization: none
- dtype: torch.bfloat16
- device_name: NVIDIA H20-3e
- num_gpus: 1
- fps: n/a_explicit_nframes
- frames_per_clip: 6
- max_pixels_or_resolution: video_preprocessor default longest_edge=25165824; source clips 1280x720
- preprocessing note: inference used explicit pre-sampled video frames (`nframes=6`) on 5-second clips; Qwen3-VL logged a timestamp fallback to fps=24 because video metadata was not passed through, but frame sampling was bounded by `nframes`.
- peak_gpu_memory_observed: allocated=63.243GiB; reserved=63.568GiB
- calls_completed / calls_planned: 100 / 100
- max_total_vlm_calls: 100
- max_calls_per_video: 2
- clip_length_seconds: 5.000
- positive agreement: 0.160
- random-negative estimated miss rate: 0.020
- abstain rate: 0.000
- boundary error if available: not evaluated; oracle prompt returns clip-level event presence, not temporal boundaries
- failure reason: 

EXTERNAL_LABEL_AUDIT_RESULT: UNRELIABLE

## Status Counts

| status | count |
|---|---:|
| ok | 100 |
