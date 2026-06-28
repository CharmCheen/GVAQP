# Preflight Report

Generated: `2026-06-22T14:40:51Z`

This preflight checks inputs, local 32B model availability, GPU visibility, and media tooling. It does not run candidate generation, YOLO, embeddings, training, or dataset download.

| check | passed | detail |
| --- | --- | --- |
| casq_v12_1_exists | True | /qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md |
| required_inputs_exist | True |  |
| sample_feasibility_exists | True | test_vlm/outputs/micro_casq_adjudication_package_v0/tables/micro_casq_sample_feasibility_v0.csv |
| materializable_samples_exist | True | 153 |
| nvidia_smi_available | True | NVIDIA A100-SXM4-80GB |
| gpu_count_positive | True | 1 |
| model_dir_exists | True | /qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct |
| model_index_exists | True | models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct/model.safetensors.index.json |
| ffmpeg_available | True | /qiuyeqing/tools/miniconda3/envs/garc/bin/ffmpeg |
| python_module_torch | True | available |
| python_module_transformers | True | available |
| python_module_qwen_vl_utils | True | available |
| python_module_cv2 | True | available |

- Protocol path used: `/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md`
- Materializable samples found: `153`
- GPU name: `NVIDIA A100-SXM4-80GB`
