# Micro-CASQ 32B-Oracle v0 Summary

- Output directory: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/micro_casq_32b_oracle_v0`
- Protocol path used: `/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md`
- Model name: `Qwen3-VL-32B-Instruct`
- GPU name: `NVIDIA A100-SXM4-80GB`
- Probe status: `success`
- Selected materializable count: `153`
- Processed count: `149`
- Positive / negative / abstain counts: `31` / `112` / `6`
- Eligible oracle_positive count: `23`
- Eligible oracle_negative count: `51`
- Excluded count: `79`
- Needs human sanity check count: `73`
- Final decision: `MICRO_CASQ_32B_ORACLE_DECISION: NEED_MORE_POSITIVES`
- Final report path: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/micro_casq_32b_oracle_v0/reports/MICRO_CASQ_32B_ORACLE_V0_REPORT.md`
- Benchmark path: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/micro_casq_32b_oracle_v0/benchmark/micro_casq_32b_oracle_v0_benchmark.csv`
- Human sanity audit queue path: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/micro_casq_32b_oracle_v0/review_exports/micro_casq_32b_oracle_human_sanity_audit_queue.csv`
- Next recommended action: Repair sample selection/materialization and expand adjudication because too few eligible oracle positives exist.

- NVIDIA-SMI monitoring: Python GPU process observed `True`, max GPU memory `64695` MiB, max GPU utilization `79`%.
