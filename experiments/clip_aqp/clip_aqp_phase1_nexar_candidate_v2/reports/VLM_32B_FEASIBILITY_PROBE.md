# VLM 32B Feasibility Probe

- model_name: Qwen3-VL-32B-Instruct
- device_name: NVIDIA H20-3e
- num_gpus: 1
- quantization: none
- dtype: torch.bfloat16
- fps: n/a_explicit_nframes
- frames_per_clip: 6
- clip_length_seconds: 5.000
- max_pixels_or_resolution: video_preprocessor default longest_edge=25165824; source clips 1280x720
- preprocessing note: inference used explicit pre-sampled video frames (`nframes=6`) on 5-second clips; Qwen3-VL logged a timestamp fallback to fps=24 because video metadata was not passed through, but frame sampling was bounded by `nframes`.
- peak_gpu_memory_observed: allocated=63.243GiB; reserved=63.568GiB
- runtime_seconds: 309.414
- success_or_failure: success
- error_message: 
- probe_clip_path: /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1/audit_clips/vlm_micro_audit/near_00179_derived_event_start_000_s000016467ms.mp4
