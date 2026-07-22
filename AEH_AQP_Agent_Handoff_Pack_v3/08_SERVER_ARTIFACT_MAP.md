# Server Artifact Map

## Project and data

```text
Project root:
/qiuyeqing/llama_prl/G-ARC

Video:
/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4

Models:
/qiuyeqing/llama_prl/G-ARC/models/vlm
/qiuyeqing/llama_prl/G-ARC/models/yolo

Evaluation/adapted code:
/qiuyeqing/llama_prl/G-ARC/garc_eval

Reference repositories:
/qiuyeqing/llama_prl/G-ARC/refe_repos/ARC-main
/qiuyeqing/llama_prl/G-ARC/refe_repos/abae
/qiuyeqing/llama_prl/G-ARC/refe_repos/adapter
/qiuyeqing/llama_prl/G-ARC/refe_repos/supg
```

## Governing documents on server

```text
/qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1
/qiuyeqing/llama_prl/G-ARC/BCM_AQP_MATHEMATICAL_REFERENCE.md
```

The server mathematical reference may contain later corrections. Hash and compare it with the copy in this pack before using either.

## Authoritative experiment order

1. `clean_baseline_benchmark_v2_strict`
2. `bcm_aqp_experiment_v2`
3. `hypothesis_construction_repair_v1`
4. `candidate_outcome_calibration_gate_v1`
5. `algorithmic_mechanism_viability_gate_v1`

All are under:

```text
/qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run
```

## Files to read in every completed experiment

Prefer, in order:

```text
FINAL_DECISION.csv
FINAL_REPORT.md or reports/FINAL_REPORT.md
RESEARCH_STATE.md when present
EXPERIMENT_MANIFEST.json / BENCHMARK_MANIFEST.json
audit/INDEPENDENT_ADVERSARIAL_REVIEW.*
completion_audit.csv
FILE_MANIFEST.csv
REPRODUCTION.md
```

Then inspect primitive traces/segments/metrics, not only aggregate tables.

## Frozen test boundary

Planner-public and evaluator-only paths should be taken from strict benchmark `NEXT_BCM_TASK_CONTEXT.md` where available. Never infer the boundary from filenames alone.

## Legacy and failed attempts

Old v1, failed v2 and Phase-0 blocker packages are provenance history. They may be read for diagnosis but cannot contribute oracle responses, selection traces or metrics to strict v2 experiments.

