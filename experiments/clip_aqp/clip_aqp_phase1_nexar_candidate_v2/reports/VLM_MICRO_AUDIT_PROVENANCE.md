# VLM Micro-Audit Provenance

The bounded VLM micro-audit was executed under the v1 directory and imported into v2 without rerunning.

## Imported Artifacts

- `audits/vlm_32b_feasibility_probe.csv`
- `reports/VLM_32B_FEASIBILITY_PROBE.md`
- `audits/vlm_micro_audit_samples.csv`
- `audits/vlm_micro_audit_results.csv`
- `reports/VLM_MICRO_AUDIT_REPORT.md`

Source directory:

```text
test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1
```

Destination directory:

```text
test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2
```

## Audit Facts

- planned VLM calls: 100
- completed VLM calls: 100
- near_label samples: 50
- random_negative samples: 50
- max calls per video: 2
- clip length: 5 seconds
- model: Qwen3-VL-32B-Instruct
- GPU: NVIDIA H20-3e
- peak observed memory allocated: 63.243GiB
- peak observed memory reserved: 63.568GiB
- positive agreement: 0.160
- random-negative estimated miss rate: 0.020
- abstain rate: 0.000
- EXTERNAL_LABEL_AUDIT_RESULT: UNRELIABLE

## Interpretation

This provenance repair changes only the output-root organization. It does not rerun VLM, alter samples, alter model outputs, or modify audit metrics.
