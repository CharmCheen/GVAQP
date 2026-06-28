# GPU Device Diagnostic Report

This diagnostic explicitly verifies the actual Qwen3-VL-32B model parameter devices after loading. It does not rely only on successful model loading.

- Diagnostic status: `GPU_VERIFIED`
- Reason: `inspected model parameters are on CUDA and no CPU/disk offload was detected`

| check | value |
| --- | --- |
| python_executable | /qiuyeqing/tools/miniconda3/envs/garc/bin/python |
| torch_version | 2.12.0+cu126 |
| transformers_version | 5.10.0.dev0 |
| CUDA_VISIBLE_DEVICES | 0 |
| torch_cuda_is_available | True |
| torch_cuda_device_count | 1 |
| torch_cuda_get_device_name_0 | NVIDIA A100-SXM4-80GB |
| torch_cuda_mem_get_info_0 | free=78.836GiB total=79.251GiB |
| nvidia_smi | Mon Jun 22 14:39:03 2026       <br>+-----------------------------------------------------------------------------------------+<br>| NVIDIA-SMI 580.65.06              Driver Version: 580.65.06      CUDA Version: 13.0     |<br>+-----------------------------------------+------------------------+----------------------+<br>| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |<br>| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |<br>|                                         |                        |               MIG M. |<br>|=========================================+========================+======================|<br>|   0  NVIDIA A100-SXM4-80GB          On  |   00000000:E1:00.0 Off |                    0 |<br>| N/A   34C    P0             87W /  400W |     425MiB /  81920MiB |      0%      Default |<br>|                                         |                        |             Disabled |<br>+-----------------------------------------+------------------------+----------------------+<br><br>+-----------------------------------------------------------------------------------------+<br>| Processes:                                                                              |<br>|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |<br>|        ID   ID                                                               Usage      |<br>|=========================================================================================|<br>|    0   N/A  N/A           15845      C   python                                  416MiB |<br>+-----------------------------------------------------------------------------------------+ |
| gpu_memory_allocated_before_loading_gb | 0.000 |
| gpu_memory_reserved_before_loading_gb | 0.000 |
| model_name | Qwen3-VL-32B-Instruct |
| model_dir | /qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct |
| model_load_seconds | 80.132 |
| model_dtype | torch.bfloat16 |
| hf_device_map | {} |
| inspected_parameter_names | ["model.visual.patch_embed.proj.weight", "model.visual.patch_embed.proj.bias", "model.visual.pos_embed.weight", "model.visual.blocks.0.norm1.weight", "model.visual.blocks.0.norm1.bias", "model.visual.blocks.0.norm2.weight", "model.visual.blocks.0.norm2.bias", "model.visual.blocks.0.attn.qkv.weight", "model.visual.blocks.0.attn.qkv.bias", "model.visual.blocks.0.attn.proj.weight", "model.visual.blocks.0.attn.proj.bias", "model.visual.blocks.0.mlp.linear_fc1.weight"] |
| inspected_parameter_devices | ["cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0", "cuda:0"] |
| next_model_parameters_device | cuda:0 |
| gpu_memory_allocated_after_loading_gb | 62.133 |
| gpu_memory_reserved_after_loading_gb | 62.139 |
| gpu_peak_memory_allocated_after_loading_gb | 62.133 |
| cpu_only_fallback_occurred | False |
| gpu_device_diagnostic_decision | GPU_VERIFIED |
| gpu_device_diagnostic_reason | inspected model parameters are on CUDA and no CPU/disk offload was detected |

MICRO_CASQ_32B_ORACLE_DECISION: GPU_VERIFIED
