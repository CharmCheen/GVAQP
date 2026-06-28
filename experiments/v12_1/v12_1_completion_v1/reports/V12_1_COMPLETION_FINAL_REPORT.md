# V12.1 Completion Report

## 1. Goal

Complete remaining V12.1 CASQ / G-ClipAQP tasks as far as current local data and compute allow.

## 2. Protocol Path

`/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md`

## 3. Starting State

Micro-CASQ v0 had `23` eligible positives and `51` eligible negatives. Nexar external-label mapping remains UNRELIABLE. Nexar candidate feasibility v2 remains CANDIDATE_STILL_TOO_WEAK.

## 4. Section-by-Section Completion Matrix

See `reports/V12_1_COMPLETION_MATRIX.md`.

## 5. Micro-CASQ v0 Attrition

See `reports/MICRO_CASQ_V0_ATTRITION_AND_YIELD_REPORT.md`.

## 6. Targeted Expansion

Selected `300` expansion samples. Feasibility materializable count: `103`.

## 7. 32B Oracle Expansion Adjudication

Completed `99` successful expansion 32B calls and `4` not-run errors. All expansion labels are 32B-oracle-relative, not human truth.

nvidia-smi monitoring observed Python GPU compute app `True` on `NVIDIA A100-SXM4-80GB` with max memory `64695` MiB, mean utilization `53.974`%, and max utilization `100`%. GPU utilization was bursty under one-second sampling.

## 8. Micro-CASQ 32B-Oracle v1 Benchmark

Eligible positives: `38`. Eligible negatives: `131`. Decision: `MICRO_CASQ_BENCHMARK_DECISION: READY_FOR_CANDIDATE_FEASIBILITY`.

## 9. Candidate Feasibility

Decision: `MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE`. If run, this is candidate-signal feasibility over an adjudicated sampled benchmark, not full-video retrieval.

## 10. Representation Candidate Availability

REPRESENTATION_CANDIDATE_NOT_AVAILABLE unless local assets are later provided. No embedding model was downloaded or run.

## 11. Selectivity Stratification

See `reports/MICRO_CASQ_V1_SELECTIVITY_STRATIFICATION_REPORT.md`.

## 12. Certificate Simulation

Decision: `MICRO_CASQ_CERTIFICATE_DECISION: UNDERPOWERED`. The certificate simulation used the reserved certification pool after candidate feasibility passed. A skipped, underpowered, or vacuous certificate is not certified.

## 13. Claim Scope

All Micro-CASQ labels are 32B-oracle-relative, not human truth. Nexar-derived labels remain noisy external labels. Claims are limited to this sampled Micro-CASQ benchmark and must not be generalized to all driving video.

## 14. What Is Complete

Completion matrix, v0 attrition analysis, targeted expansion selection, feasibility checks, bounded GPU-monitored 32B expansion adjudication, v1 benchmark construction, representation availability reporting, selectivity reporting, and certificate gating.

Engineering GO/NO-GO interpretation: WEAK GO for candidate feasibility; NO-GO for non-vacuous certificate claims until the reserved certification pool is expanded.

## 15. What Remains Blocked

A non-vacuous certificate remains blocked by the underpowered reserved certification pool.

## 16. Risks and Limitations

The benchmark is sampled from prior candidates, not full-video retrieval. Old labels are provenance only and not gold. Event boundaries are used only for oracle-relative evaluation, not candidate generation. No human-truth claim is made.

## 17. Next Action

Expand or rebalance the reserved certification pool so it contains at least 30 eligible oracle-positive events, then rerun certificate simulation without retuning on the reserved pool.

## 18. Final Decision

V12_1_COMPLETION_DECISION: NO_CERTIFICATE_YET
