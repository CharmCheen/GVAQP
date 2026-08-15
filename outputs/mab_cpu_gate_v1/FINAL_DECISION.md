# CPU-only MAB Gate Final Decision

## 1. Final Route
**GO_RELATION_GREEDY_ONLY (action-space headroom exists: ACTION_SPACE_GO, context learnability: INCONCLUSIVE_CONTEXT (LOVO headroom recovered 0.3184), lookahead: MYOPIC_CONTEXTUAL_MAB_IS_ADEQUATE; closed-loop contextual TS does not beat deterministic relation greedy: MAB_NOT_CORE (mean closed-loop TS gain < 0.01 or directionally unstable); granularity FIXED_GRANULARITY_ONLY + BLOCKED_GPU_MULTIGRANULARITY)**

## 2. Four Decisive Numbers
- G_granularity = NOT_ESTIMABLE (semantic); geometric 0.0 vs 10s-quantized reference
- G_oracle = 0.474
- rho_0.02 = 0.5897435897435898
- G_lookahead = 0.0

## 3. Context Predictability
- Headroom recovered = 0.3184
- Leave-one-video result: [
 {
  "heldout_video": "DALI",
  "mean_selected_regret": 0.01891,
  "n_test_rows": 18720,
  "n_train_states": 37440,
  "oracle_gain_mean": 0.0245,
  "pairwise_accuracy": 0.2143,
  "spearman": -0.1703
 },
 {
  "heldout_video": "HANGZHOU",
  "mean_selected_regret": 0.0103,
  "n_test_rows": 18720,
  "n_train_states": 37440,
  "oracle_gain_mean": 0.02528,
  "pairwise_accuracy": 0.2314,
  "spearman": 
- Main predictive features: visible proxy score/rank, temporal geometry
  (new-component gain, merge risk, distances), remaining budget fraction
- Main failure features: Proxy B (unavailable), boundary uncertainty
  (not discriminative on the 10s grid)

## 4. MAB Necessity (relation-aware TS vs deterministic greedy)
- budget 5: TS minus relation-greedy per cluster = {'DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0048, 'HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0222, 'WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': -0.0181}; mean = 0.0029
- budget 10: TS minus relation-greedy per cluster = {'DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0043, 'HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0135, 'WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0018}; mean = 0.0065
- budget 20: TS minus relation-greedy per cluster = {'DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0116, 'HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0003, 'WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0032}; mean = 0.005
- budget 50: TS minus relation-greedy per cluster = {'DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.0408, 'HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': -0.0038, 'WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': -0.01}; mean = 0.009
- budget 80: TS minus relation-greedy per cluster = {'DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.033, 'HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': -0.0009, 'WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': -0.0136}; mean = 0.0062
- budget 100: TS minus relation-greedy per cluster = {'DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': 0.016, 'HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': -0.0001, 'WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1': -0.0154}; mean = 0.0002

Verdict: **MAB_NOT_CORE (mean closed-loop TS gain < 0.01 or directionally unstable)**

## 5. Supported Claims
- In the FIXED_CANDIDATE_REPLAY substrate (Q_VULNERABLE, 3 videos, model-relative
  full-grid C1 reference, abstract budgets 5..100), the VERIFY-selection action
  space contains non-trivial oracle headroom: G_oracle 0.474, rho_0.02
  0.5897435897435898, 0 harmful action rate at 0.02.
- Policy-visible features (proxy + temporal geometry) carry measurable signal:
  LOVO headroom recovered 0.3184.
- Myopic (one-step) oracle is adequate at low budgets (G_lookahead 0.0).
- C1 materializer + strict-overlap matching reproduce the frozen P2 manifest
  exactly (252/252), so the engine is faithful to the frozen pipeline.
- Fine-grained (5s) PROXY-level evidence exists for WUHAN and covers 32/32
  reference events geometrically; no 5s semantic quality exists (granularity
  gate BLOCKED_GPU_MULTIGRANULARITY).

## 6. Unsupported Claims
- real endogenous SCAN / natural candidate exposure recovery: NOT supported
  (fixed precomputed universe only).
- actual 2s/5s/10s VLM quality differences: NOT supported (no cached
  multi-granularity semantic outcomes; reference is 10s-quantized).
- human event superiority / independent reference value: NOT supported
  (BLOCKED_INDEPENDENT_REFERENCE; 0 human labels).
- cross-domain generalization: NOT supported (3 videos, 2 queries, model-relative).
- Proxy B feature robustness: NOT supported (Proxy B per-unit scores absent).
- wall-clock deadline behavior: NOT supported (abstract budgets only).

## 7. Exact Next GPU Experiment (justified only if this headroom must be
   pursued on a faithful substrate)
- What to generate: fine-grained (2s/5s) semantic verifier outcomes on the
  same 3-video x 2-query grid (e.g., Qwen3-VL-32B on 2s/5s clips), plus Proxy B
  per-unit scores; then rerun phases 1-3 at G2/G5 granularities.
- Stride/context configs: G10 (current), G5, G2, G2-C5, G2-C10.
- Frozen models/configs: the existing Qwen32 oracle protocol, V3 proxy,
  Proxy B kinematic protocol (all hash-recorded).
- Minimum scale: 3 videos x 2 queries x 40 units per granularity
  (1475 x 3 granularities) + 2 independent annotations for the human reference.
- Which CPU gate justifies the GPU cost: the CPU gate shows real VERIFY-selection
  headroom (rho_0.02 0.5897435897435898) and learnability (headroom recovered
  0.3184) in the fixed-universe setting, so the remaining unknown is whether
  finer granularity/endogenous sensing changes the answer — a GPU question.

## 8. Reproduction
- Exact commands: `bash scripts/mab_cpu_gate/REPRODUCE.sh` (venv per header).
- Output paths: outputs/mab_cpu_gate_v1/ (all files listed in PROVENANCE.md).
- Test results:

- Known limitations: see PROVENANCE.md scope declarations; Q_DRIVER rows are
  diagnostic-only; Proxy B features absent; abstract costs only.
