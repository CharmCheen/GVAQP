# PROVENANCE.md — ERAEA CPU novelty gate v1

Date: 2026-08-14. CPU-only macOS checkout. No GPU, no model inference, no
downloads, no human labels read, no project state files modified.

## Inputs (frozen repository artifacts)
- Q_VULNERABLE full 1475-unit semantic table (reconstructed from
  qwen32_oracle/raw/*.json; validated 252/252 vs P2 TRACE_MANIFEST).
- Proxy A scores (reconstructed from v3 raw_unit_detections.jsonl with the
  frozen scoring function; validated 1e-9 vs PROXY_REGIME_MANIFEST R0).
- frozen_unit_grid_v1.csv (10s grid), P2 TRACE_MANIFEST.csv (baseline anchor:
  top_proxy/uniform/coverage_first curves verified byte-identical).
- MATERIALIZER: C1 gap-only (frozen semantics); K0 single-span; C3
  gap+duration-cap+negative-barrier as the K3-like variant (the real K3
  adapter requires the absent FINAL_UNIT_REFERENCE parquet; C3 is the frozen
  Stage-0 lineage variant used in the mechanism ablation, disclosed as
  K3-like approximation in all outputs).
- Evaluator: strict-overlap 1:1 matching vs the full-grid C1 model-relative
  reference (55/50/32 events for DALI/HANGZHOU/WUHAN).

## Scope declarations (hard)
- FIXED_CANDIDATE_REPLAY only. MODEL_RELATIVE_DIAGNOSTIC only.
  BLOCKED_HUMAN_REFERENCE (0 labels).
- Abstract query-count budgets (5..100); no wall-clock claim.
- Statistical unit: video x query. Seeds only for stochastic-policy
  Monte-Carlo variance (3 seeds averaged per policy-budget).

## Methods in BASELINE_MATRIX (shared universe/state/cost/evaluator)
uniform, stratified, top_proxy, temporal_coverage, new_component, mmr
(frozen P1 formula, lambda=0.5), facility-location greedy, exsample-like
(Beta-Thompson), seiden_ucb (50s region UCB), relation_greedy (visible R4,
top-50 proxy candidates), yield_greedy_oracle (full-info upper), relation_ts /
yield_ts (Bayesian logistic TS, Laplace), oracle1 (one-step Delta1),
oracle2 (depth-2). Deterministic methods seed=0; stochastic averaged over 3
seeds.

## Outputs (all in outputs/eraea_cpu_novelty_gate_v1/)
- BASELINE_MATRIX.csv (270 rows = 3 clusters x 15 policies x 6 budgets)
- EQUAL_YIELD_PAIRS.parquet + EQUAL_YIELD_REPORT.md
- GENERIC_COMPARISON.csv, NOVELTY_GATE_METRICS.json
- MATERIALIZER_DECOUPLING.csv + MATERIALIZER_SENSITIVITY.md
- REWARD_MINIMALITY_REPORT.md
- DEVIATION_AUDIT.parquet
- FINAL_DECISION.md, PROVENANCE.md, REPRODUCE.sh
- HUMAN_REFERENCE_READINESS.md (parallel human-reference task)

## Known limitations
- Q_DRIVER not included (full grid unrecoverable locally; union labels only).
- exsample/seiden/facility are "like" implementations (no canonical frozen
  reference for their exact form); MMR uses the repository-frozen formula.
- C3 approximates K3; the true K3 adapter cannot run without the absent
  parquet substrate.
- 3 seeds for stochastic policies; 50 seeds were used in the preceding MAB
  gate (different experiment, see outputs/mab_cpu_gate_v1/).
