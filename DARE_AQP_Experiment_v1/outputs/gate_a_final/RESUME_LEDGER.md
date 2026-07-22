# Gate A resume ledger

- Recovery audit UTC: 2026-07-11
- GPU: NVIDIA A100-SXM4-80GB, 81920 MiB total and 81920 MiB free at audit
- Driver / reported CUDA: 580.65.06 / 13.0
- PyTorch / runtime CUDA: 2.12.0+cu126 / 12.6
- Frozen CLIP: `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`
- Frozen X-CLIP: `microsoft/xclip-base-patch32@a2e27a78a2b5d802e894b8a1ef14f3a8ce490963`
- Cache at recovery: neither frozen snapshot was present.
- Required files: exactly those recorded by `model_file_manifest.csv` (model config,
  processor config, tokenizer files, and one checkpoint representation per model).
- Video SHA256: `bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610`
- Frozen config SHA256: `7f4add37fc3746bc5dbaf70ab38b16880cfabdb449713b2d4db7068e35b5160f`
- Duplicate-process audit: no Gate A/CLIP/X-CLIP GPU process and no pre-existing
  tmux/screen session was found. `tmux` was installed because neither persistence
  mechanism was initially available.
- Acquisition command: `python DARE_AQP_Experiment_v1/scripts/acquire_gate_a_models.py`
- Acquisition initially failed twice before download (wrong tmux working directory,
  then wrong base interpreter without SOCKS support); the logged exact `garc`
  interpreter retry completed all 16 required files. No model substitution occurred.
- Pre-execution equivalence smoke: CLIP absolute logit error `0.0`; X-CLIP
  video-conditioned decomposition absolute logit error `0.0` against each model's
  frozen full forward on unit 0.
- Exact formal resume command: `/qiuyeqing/tools/miniconda3/envs/garc/bin/python
  DARE_AQP_Experiment_v1/scripts/run_gate_a_inference.py --device cuda --execute
  --output DARE_AQP_Experiment_v1/outputs/gate_a_final`
- Persistent execution wrapper: `tmux attach -t dare_gate_a`; stdout/stderr is
  persisted in `outputs/gate_a_final/logs/formal_inference.log`.
