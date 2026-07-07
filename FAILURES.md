# Failures And Warnings

> This file lists the routes that have been tried and either **failed** or **landed as neutral**. It does not list the routes that are still in progress. Do not re-attempt a failed route without a new reason and a new mechanism; document the new reason in the corresponding `outputs/late_aqp_*/` directory.

## Failed Routes (do not repeat without a new mechanism)

### Phase 3 fixed cheap-signal selector → NEGATIVE

- **Status**: completed negative diagnostic.
- **Symptom**: at B=40, uniform_random averaged 0.153 event_recall_iou_0_3 across 50 seeds, while the best deterministic cheap-signal selector (`existing_signal`, `track_interaction`, `inside_outside`, `simple_fused`) reached 0.050.
- **Source**: `outputs/agent_loop_v1/phase3_selector_smoke_v1/phase3_selector_smoke_report.md` and `selector_budget_summary.csv`.
- **Implication**: deterministic ranking on the current cheap-signal features does not convert signal diagnostics into better budgeted return-set coverage. The next step is objective redesign (T010, EC-AQP), not a different ranking function on the same features.

### Frozen-LATE-AQP-v2 cold_start_fallback on the original failure segments → FAIL

- **Status**: split-validated, not re-validated on the original failure segments.
- **Symptom**: on the three original realcartest failure segments at B=10/20, v2's substantive improvement over v1 is **0/3 segments at both B=10 and B=20**; only `realcartest_0_1570` at B=20 shows a single above-noise improvement.
- **Source**: `outputs/late_aqp_v2_original_segment_verification/verdict_report.md`.
- **Implication**: the v2 audit-schedule tweak is not a low-budget fix on the original problem. The original low-budget failure could not be re-tested because the original realcartest footage is no longer available (`outputs/late_aqp_low_budget_fix_v1/README.md` "Caution").

### hybrid_coldstart (r=0.5) → FAIL

- **Status**: failed route.
- **Symptom**: 0/3 segments with substantive improvement at both B=10 and B=20 across r ∈ {0.3, 0.5, 0.7}; v2_hybrid mean recall is >= B6 in only 3/6 segment-budget combinations.
- **Source**: `outputs/late_aqp_hybrid_coldstart_v1/verdict_report.md`.
- **Implication**: blending exploration and exploitation in the cold-start phase does not fix the low-budget problem on the original failure segments.

### D1 / D2 / D3 discovery policies vs B7-core on B_90/90 → NO STABLE WIN

- **Status**: no LATE variant beats B7-core on B_90/90.
- **Symptom**:
  - D1 best (radius20): lower B_90/90 than D0 on 2/6 segments, never strictly lower than B7-core.
  - D2 best (q20-smass-rhighest): lower B_90/90 than D0 on 1/6 segments, never strictly lower than B7-core.
  - D3 best (chunk120): lower B_90/90 than D0 on 1/6 segments, never strictly lower than B7-core.
  - D3-norepair best (chunk120): lower B_90/90 than D0 on 3/6 segments, never strictly lower than B7-core.
- **Source**: `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` Q1/Q4.
- **Implication**: the "performance advantage" route for the LATE discovery policies is not established. Do not run another sweep along the D1/D2/D3 axes as the next step.

### Core/Halo as a LATE-AQP-specific advantage → NEUTRAL (it is generic)

- **Status**: Core/Halo gain is generic, not LATE-specific.
- **Symptom**: B6-core and B7-core reach 90/90 on the same segments as LATE-AQP-core. On `realcartest_3200_3830`, B6-core and B7-core reach 90/90 at B=60 vs LATE-AQP-core at B=80. Mean guard overhead for LATE-AQP-core: 29.6% of budget (41.4% at B<=20).
- **Source**: `outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md`; `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` Q10; `outputs/late_aqp_cross_video_frontier_v1/FINAL_REPORT.md` Q8.
- **Implication**: treat Core/Halo as a generic release module, not a LATE-AQP win.

### D3-core vs D3-norepair-core (pre-fix) → repair was net-negative BUT contaminated

- **Status**: original conclusion contaminated by an accounting bug; post-fix result is **neutral, not net-negative**.
- **Symptom (pre-fix)**: 981 discovery calls in D3-core re-queried bins already queried by audit/repair. Repair was associated with fewer unique events on 2/3 chunk configurations.
- **Symptom (post-fix)**: D3-core-fixed is not consistently better than D3-norepair-core on B_90/90. Repair marginal value on chunk-bandit is non-positive or zero.
- **Source**: `outputs/late_aqp_repair_negative_diagnosis_v1/FINAL_DIAGNOSIS.md`; `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md`; `outputs/late_aqp_event_diverse_discovery_v1/repair_marginal_value_report.md`.
- **Implication**: do not derive a "repair is net-negative" conclusion from the pre-fix data; use the post-fix D3-norepair-core as the strict-replay baseline.

### Any method reaching 90/90 at <=30% budget ratio → NO

- **Status**: negative.
- **Symptom**: on realcartest and dataset3, no method reaches 90/90 at <=30% budget ratio. Best low-budget recall under P>=0.9 within the low-budget envelope averages LATE-core 0.25, B7-core 0.21, B6-core 0.11.
- **Source**: `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` Q5/Q9; `outputs/late_aqp_cross_video_frontier_v1/FINAL_REPORT.md` Q3/Q7.
- **Implication**: "low-budget 90/90" is the open frontier; EC-AQP is the candidate answer.

### Outside-envelope audit samples double-counted as evaluation → label-isolation risk

- **Status**: B6/B7/B6-core/B7-core are `posthoc_eval`; only LATE-AQP-core and D3-norepair-core are `strict_replay`.
- **Symptom**: B6/B7 use per-bin `event_id` for adaptive chunk counting, which is not available in a true limited-oracle setting.
- **Source**: `outputs/late_aqp_limited_oracle_frontier_v1/oracle_replay_isolation_audit.md`; `outputs/late_aqp_limited_oracle_frontier_v1/method_inventory.md`.
- **Implication**: when comparing LATE-AQP-core to B7-core, label the comparison track. Do not claim "LATE-AQP beats B7-core" without that label.

### V3 audit-schedule and repair-utility designs → MODEST only

- **Status**: modest improvements only; no utility dominates both recall and precision.
- **Symptom**: best long-event recall@20 is V3_two_phase = 0.517 (vs V2_static25 = 0.417). Best long-event recall@40 is U1_leakage_density = 0.750. No audit-schedule / repair-utility combination wins both metrics. Repair trace `source_action` lineage is not fully logged in the v3 replay.
- **Source**: `outputs/late_aqp_algorithm_v3_oracle_relative/FINAL_REPORT.md` Q4/Q5.
- **Implication**: the v3 ideas are candidates for re-evaluation under strict replay, not established wins.

## Diagnosed-But-Not-Failed (B-verdict candidates; ablation-only paths)

> These routes are **not failed.** Each is a feasibility diagnostic that landed
> as conditional-positive (B-verdict). They are flagged here so future agents do
> not re-derive them from scratch, and **do not** quietly elevate them to
> default selector without explicit authorization.

### DR / AIPW audit-correction feasibility → CONDITIONAL (targeted weak-proxy only)

- **Status**: feasibility-only, not implemented; Gate A=PASS, Gate B=CONDITIONAL, Gate C=PASS (borderline).
- **Symptom**: with the **deployable** per-stratum-LOO p_model, DR delivers ≥20% RMSE reduction vs model-only on **1/6** segments (dataset3_0_1200); beats ABae-residual-strict on 2/6. The aggregate "≥4/6 PASS" only emerges when crediting a **raw-minmax strawman** p_model, which is a deliberately miscalibrated baseline. The honest call is Gate B = CONDITIONAL, not PASS.
- **Prior forced-exploration routes are failed/neutral** (v2 `cold_start_fallback`, `hybrid_coldstart`, D3-core repair-vs-norepair-neutral). The **only** meaningful difference between EventLift-DR and those priors is the **dual-use audit correction** term (`Σ (y − p_model) / π`), where the same audit sample yields both positive recovery and bias correction. That is conceptual differentiation, NOT empirically validated outcome.
- **Source**: `outputs/eventlift_dr_feasibility/dr_gate_summary.csv`; `PROXY_BIAS_DR_FEASIBILITY.md`; `EXPERIMENT_REGISTRY.csv` entries `proxy_bias_dr_feasibility_v1`, `eventlift_full_benchmark_v1`.
- **Implication**: do NOT implement EventLift-DR globally. Do NOT replace the default `score_topk + temporal NMS + duration cap` selector. A targeted ablation on dataset3_0_1200 (optionally dataset3_1200_2400) with p_model = `per_stratum_loo` only, audit-share ∈ {0.10, 0.20} only, audit-sample-disjoint-from-discovery-discovery, is the smallest non-trivial next step (T023) — but only with explicit human authorization. DR/AIPW is a known estimator family; no "novel statistical invention" claim.

### HTS-AQP Phase 0 feasibility → CONDITIONAL (sparse-segment only)

- **Status**: God's-eye upper-bound simulation only; not implemented; not a real algorithm prototype.
- **Symptom**: deterministic coarse-to-fine descent (perfect oracle knowledge) at b=4 yields savings-vs-flat-scan: dataset3_0_1200 +59.2%, dataset3_1200_2400 +30.8%, dataset3_2400_3462 +33.6%, realcartest_3200_3830 +22.2%, realcartest_0_1570 +10.8%, **realcartest_2000_3200 −0.8%**. With b=2, realcartest_2000_3200 regresses **−20.8%** vs flat scan (coarse-positive saturation: at 26.7% positive density, almost every coarse node is positive → no pruning → tree overhead dominates). HTS full-coverage call count at b=4 = 49–171 calls/segment; no strict_replay baseline reaches that coverage at any available budget, so an equal-coverage oracle-call ratio is unavailable — Phase 0 reports coverage multiplicative gap (HTS finds all 6 of 6 events on dataset3_0_1200 where the best existing strict-replay baseline finds 1 of 6 at the same call budget).
- **Q5 verdict**: **B (weakly feasible / segment-dependent)**. Adopted explicit ratio threshold: A requires ratio < 0.5 on ≥4/6 segments AND no b=4 regression > 5%; Phase 0 fails both halves. The honest statement is that HTS is **qualitatively different on sparse segments but not cheaper in equal-coverage call count** (because baselines never reach that coverage).
- **Source**: `outputs/hts_aqp_phase0_feasibility/` (context_manifest.md, coarse_to_fine_call_count_by_segment.csv, comparison_vs_existing_baselines.csv, HTS_PHASE0_FEASIBILITY_REPORT.md); `HTS_AQP_DESIGN.md`; `EXPERIMENT_REGISTRY.csv` entry `hts_aqp_phase0_feasibility`.
- **Implication**: do NOT implement HTS-Discover (Phase 1) yet. Required before any Phase 1 implementation: (1) b ∈ {2,4,8} sensitivity analysis; (2) `k0` (prior pseudo-count) sensitivity analysis; (3) **hybrid fallback for high-density (>20% positive) segments** — without this, a real Phase-1 algorithm will reproduce the realcartest_2000_3200 b=2 regression; (4) explicit-intent coverage convention switch from Phase 0's `any-overlap` to IoU ≥ 0.3 (per `run_eventlift_full_benchmark_v1.py:38`) for any actual evaluation. HTS is **not** a novel search paradigm (hierarchical multi-resolution search is standard); the candidate-novel element is the application to event-level AQP. Coarse-oracle-VLM-reliability assumption (real VLM coarse-window judgment vs strict-replay OR aggregation) is **not validated** and must be flagged as future work. Next step is task T024 (design-only) with explicit human authorization.

## Active Warnings (carry-over from previous state)

- `try_or_no/videos/realcartest.mp4` is absent; current probe media uses fallback `data/realcam/long_video_data/long_video_dataset3.mp4`.
- Current `probe_set_v1` covers local `[0.0, 1462.930499]`, not the full 66-minute realcartest video.
- Current cheap-signal features cover local `[0, 1200]`; 5 probe intervals start after local 1200s.
- `auc_best_direction` chooses best direction post hoc for diagnostics and must not be treated as selector tuning.
- Git dubious-ownership protection in this environment: run `git config --global --add safe.directory <repo>` before `git status`.
- `probe_set_v1` signal evaluation is limited to 20/25 probes because current cheap_signal_v2 features cover local `[0, 1200]`; probes 21-25 remain unscored by cheap_signal_v2.
- Probe metrics are VLM-oracle-relative, not human-ground-truth metrics.
- `overlap_group_id` in `interval_features_with_signal_v2.csv` is a single global value, so it is not usable as a return-set diversity cap in the current smoke; the script disables that cap and uses time-IoU NMS.
- Guard overhead is non-trivial: mean 29.6% of total budget for LATE-AQP-core, 41.4% at B<=20. The 3-bins-per-side cap (`MAX_GUARDS_PER_SIDE=3`) is hard-coded; per-interval adaptive cap is **not yet evaluated**.
- Large artifact warning: 4 CSVs in `src/garc_eval/outputs/` total ~1.4 GB and are tracked in git. See `outputs/state_sync_late_aqp_v1/large_artifact_manifest.md` for paths, sizes, and recommendations.
- LFS hook is installed but `git-lfs` is not on the path. Large files in this repo are **not** routed through LFS; they live as plain blobs in git history. See the manifest.

## Resolved Execution Issues

- Round 3 annotation package generation had three transient script errors: f-string expression syntax in HTML assembly, absolute-vs-relative path handling, shell quoting around f-string dictionary access. All three were fixed in the same round; final validation passed with 25 manifest rows, 25 HTML probe sections, zero missing media references.
- D3 chunk-bandit `queried`-state accounting bug: `discovery_d3_chunk_bandit` ignored the `queried` argument, allowing 11.21 mean duplicates per trial. Fixed in `outputs/late_aqp_d3_accounting_fix_v1/`; post-fix duplicate rate is 0.51 per trial (95.4% reduction). Source: `outputs/late_aqp_d3_accounting_fix_v1/bug_fix_summary.md` and `duplicate_call_comparison.csv`.

## Coverage Audit Detail

- `outputs/cheap_signal_v2/probe_feature_coverage_audit.md` confirms 20 probes fully covered by current cheap-signal feature tables and 5 probes with no coverage.
- `outputs/agent_loop_v1/probe_eval_after_vlm_oracle/` contains the small probe metric pass; it is limited to the feature-covered 20-probe scope and must not be treated as a full 25-probe signal validation.
- `outputs/agent_loop_v1/phase3_selector_smoke_v1/` contains the first executable selector/budget smoke; it produced returned interval sets but does not support selector replacement.
- `outputs/late_aqp_event_diverse_discovery_v1/unique_event_coverage.csv` quantifies the upstream discovery miss per method per segment; LATE-D0 misses 19.2 long events in `realcartest_0_1570` vs the best alternative's 8.8, but neither closes the gap to B7-core.
- `outputs/late_aqp_cross_video_frontier_v1/cross_video_failure_taxonomy.csv` shows the failure-taxonomy distribution across both videos; most low-budget failures are discovery misses, with some release-over-conservative cases.
