# Micro-CASQ 32B-Oracle v0 Report

## 1. Goal

Construct an oracle-relative Micro-CASQ v0 benchmark from materializable adjudication samples using Qwen3-VL-32B-Instruct as the fixed expensive semantic oracle O.

The initial full-loop attempt was stopped because GPU execution was suspected or unverified. Existing pre-repair raw outputs were preserved and marked as `unverified_gpu_or_cpu_suspected`; final accepted outputs are generated only after explicit GPU diagnostics and GPU-verified probing.

## 2. Protocol Reference

Protocol path read: `/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md`

## 3. Oracle Definition

`O = Qwen3-VL-32B-Instruct` with the fixed `O_enter_ego_path_v0` prompt contract. This benchmark is 32B-oracle-relative. 32B labels are not claimed as human truth or real-world safety ground truth.

## 4. Input Sample Set

Selected materializable samples: `153`. Non-materializable samples remain excluded until sample repair.

## 5. Hardware and Model Environment

GPU: `NVIDIA A100-SXM4-80GB`. Model path: `/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct`. FPS: `1.0`. Max pixels: `230400`. GPU device diagnostics were performed before resume.

## 6. Feasibility Probe

Probe status: `success`. See `tables/vlm_32b_oracle_feasibility_probe.csv` and `tables/vlm_32b_gpu_verified_probe.csv`.

## 7. Prompt Contract

`prompts/o_enter_ego_path_v0_32b_oracle_prompt.txt` and `reports/PROMPT_CONTRACT.md` define the fixed oracle prompt.

## 8. 32B Oracle Adjudication Execution

Processed rows: `149`. Run failures: `4`. Raw GPU-verified model outputs are under `model_outputs/gpu_verified/`. Pre-repair outputs under `model_outputs/` are retained as provenance only unless explicitly rerun.

## 9. Output Validation

Validation passed: `True`. Old labels were retained as provenance only and were not promoted to gold.

## 10. Label and Boundary Summary

Positive / negative / abstain: `31` / `112` / `6`.

## 11. Benchmark Eligibility

Eligible oracle positives: `23`. Eligible oracle negatives: `51`. Excluded: `79`.

## 12. Micro-CASQ 32B-Oracle v0 Benchmark

Benchmark files were written under `benchmark/`. Excluded rows are retained separately and are not used for headline recall/certificate metrics.

## 13. Split Proposal

`benchmark/micro_casq_32b_oracle_v0_split_proposal.csv` proposes candidate-dev, heldout-eval, reserved-certification-pool, and excluded splits. The reserved certification pool must not be used for candidate tuning.

## 14. Human Sanity Audit Queue

Human sanity audit queue rows: `99`. Human sanity audit is recommended for prompt quality and obvious failure analysis, but full human relabeling is not required for oracle-relative CASQ experiments.

## 15. Implications for V12.1 Progress

This run creates a bounded oracle-relative sample for candidate feasibility. It does not establish human ground truth or final G-ARC guarantees.

## 16. Risks and Limitations

- This benchmark is 32B-oracle-relative.
- 32B labels are not claimed as human truth.
- Old labels are provenance only.
- Nexar-derived labels are noisy external labels.
- This run adjudicates only materializable Micro-CASQ samples.
- Non-materializable samples remain excluded until sample repair.
- The stopped pre-repair run had suspected CPU or unverified GPU execution.
- GPU device diagnostics and a GPU-verified probe were performed before the resumed full loop.
- Pre-repair outputs retained in provenance are marked `unverified_gpu_or_cpu_suspected` and are not treated as final GPU-verified accepted outputs.

## 17. Next Action

Repair sample selection/materialization and expand adjudication because too few eligible oracle positives exist.


## NVIDIA-SMI GPU Monitoring

NVIDIA-SMI monitoring was attached while the repaired 32B-oracle run was still active. The compute-app monitor observed Python PID `15996` using about `64686 MiB` on `NVIDIA A100-SXM4-80GB`. The GPU timeseries observed max memory `64695 MiB`, mean utilization `58.297%`, and max utilization `79%`; progress snapshots observed max utilization `80%`.

Interpretation: GPU inference confirmed; GPU memory resident and compute appears bursty / I/O-bound under nvidia-smi sampling. GPU memory was high throughout the monitored window, while utilization included both nonzero bursts and zero-utilization samples, so this is reported as GPU-resident, bursty / I/O-bound inference rather than sustained high utilization. Final successful accepted rows are GPU-backed according to nvidia-smi evidence plus torch/model-device provenance; failed rows remain `not_run_error` and are excluded from benchmark eligibility.

Monitoring limitation: nvidia-smi monitors were attached after the repaired run was already in progress, around the middle of the 153-sample loop; earlier GPU-verified samples rely on torch device diagnostics and raw-output device provenance.

## 18. Final Decision

MICRO_CASQ_32B_ORACLE_DECISION: NEED_MORE_POSITIVES
