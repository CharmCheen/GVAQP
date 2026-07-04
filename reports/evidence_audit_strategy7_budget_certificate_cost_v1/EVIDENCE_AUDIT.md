# Evidence Audit: Static Prior, Targeted Recovery, Certificate Tradeoff, GLM Cost Accounting

**Date:** 2026-06-28
**Mode:** Read-only evidence audit. No new experiments, no model calls, no data generation.
**Audit scope:** Four claim categories across the full project evidence base.

---

## 1. Executive Summary

### Strong evidence

- **Static visual priors work.** The diversity prefilter on `object_count_mean` (cheapest, simplest proxy) at B=40 achieves 0.314 event recall, exceeding V13.9's best static 0.216 (+0.098 abs, Bonferroni-significant). `object_count_mean` is the strongest deployable proxy on both dataset3 (AUROC 0.627) and realcartest (AUROC 0.738). Uniform selection beats adaptive methods at every budget (V13.10). Source: `diversity_prefilter_replay_v1`, `v13_10`, `glm52_sprint3`.

- **Adaptive methods consistently fail.** V13.10 concludes ADAPTIVE_NO_BETTER — static methods beat adaptive at every budget. H3 (confirmed-positive refine) in diversity prefilter also fails. This is not a bug; it is the temporal cluster structure (P(1→1)=0.457) that makes local expansion redundant. Source: `v13_10`, `diversity_prefilter_replay_v1`.

- **Strategy7 disagreement audit recovers L3-missed positives.** Post-transition audit confirms +7-16pp gain (after budget alignment correction) on L3-missed recovery. Source: `post_transition_strategy7_audit_v1`.

### Weak evidence

- **Certificate tradeoff is real but dataset-dependent.** On dataset3 (N=100, 28 positives), Strategy7 can have positive R_lower gaps. On realcartest (N=399, 94 positives), Strategy7 has negative R_lower gaps at all budgets — the smaller uniform audit fraction leaves a larger residual upper bound. The tradeoff is documented in both certificate power and budget split sweep reports. The Pareto front exists but the operating point depends on dataset characteristics. Source: `strategy7_certificate_power_v1`, `strategy7_budget_split_sweep_v1`.

- **Targeted recovery seed statistics are sparse.** No existing experiment provides per-seed paired CI for the recovery gain. The post-transition audit gives only point estimates (+7-16pp range). Per-seed traces exist in certificate_power_seed_traces.csv but are only analyzed for R_lower, not for recovery metrics.

### No evidence

- **Certificate on V13.8 realcartest oracle.** Certificate has never been run on the V13.8 valid oracle (51 events). The only certificate run (v12.1) was on a sampled benchmark with <30 positives and returned UNDERPOWERED. Phase 0.6 power simulation estimates ~500 events needed; V13.8 has 51. Source: `v12_1_completion_v1`, `clip_aqp_phase0_v1`.

- **Cross-video generalization.** All evidence is from realcartest.mp4 (single video) and dataset3 (another single video). No second-video replication for the budget-decomposition or certificate-tradeoff findings.

### Claims needing downgrade

- "Strategy7 +25.7pp recovery" → should be quoted as +7-16pp (budget-pool-size artifact corrected).
- "GLM cascade reduces cost by 95%" → reduces Qwen calls by 95%, not total cost (GLM cost not counted).
- "Certificate is proven" → not proven; only the hypergeometric bound mechanism is validated (coverage 1.0 >= nominal 0.95), but the bound is too conservative for practical use (R_lower 0.02-0.08 vs true recall 0.19-0.50).
- "Static methods far below upper bound because proxies are weak" → partially refuted: budget-decomposition alone closes 10-13pp of the gap (B=40 efficiency from 0.275→0.400).

---

## 2. Evidence Table Summary

### Table A: Static Prior Evidence

| Source | Dataset | Budget | Static Method | Baseline | Metric | Gap | Strength |
|--------|---------|--------|---------------|----------|--------|-----|----------|
| diversity_prefilter_replay_v1 | realcartest | B=40 | prefilter_div_objmean_P2B_a0.5 | top_fusion_geometry_motion | event_recall | +0.098 | **STRONG** (Bonferroni-significant) |
| v13_10 | realcartest | B=20 | uniform_anchor_10s | adaptive_priority_boost | efficiency_ratio | +0.100 | **STRONG** (ADAPTIVE_NO_BETTER) |
| glm52_sprint3_certificate_queryprior_v1 | dataset3+both | all | object_count_mean | score_fusion_geometry_motion | AUROC | +0.077/+0.188 | **STRONG** |
| glm52_proxy_calibration_diversity_v1 | dataset3 | B=80 | greedy_maxmin_time | linspace_spread | event_cluster_recall | +0.038 | **MEDIUM** (single video) |

### Table B: Targeted Recovery Evidence

| Source | Dataset | Budget | Method | Baseline | Metric | Gap | Strength |
|--------|---------|--------|--------|----------|--------|-----|----------|
| post_transition_strategy7_audit_v1 | dataset3 | B=60 | S7 | L3 | L3-missed recovery | +32.7pp headline / +7-16pp corrected | **MEDIUM** (corrected) |
| post_transition_strategy7_audit_v1 | dataset3 | B=60 | S7 | L3 | anchor_recall | +29.7pp | **MEDIUM** (point estimate) |
| strategy7_certificate_power_v1 | realcartest | B=80 | S7 | L3 | L3-missed recovered | +0.836 count | **MEDIUM** |
| Per-seed CI for recovery gaps | — | — | — | — | — | **NOT FOUND** | **MISSING** |

### Table C: Certificate Tradeoff Evidence

| Source | Dataset | Budget | Method | Baseline | R_lower gap | Direction | Strength |
|--------|---------|--------|--------|----------|-------------|-----------|----------|
| strategy7_certificate_power_v1 | dataset3 | B=40-80 | S7 | L3+uniform | +0.010 to +0.028 | Positive | **MEDIUM** (dataset3 only) |
| strategy7_certificate_power_v1 | realcartest | all | S7 | L3+uniform | -0.015 to -0.057 | **Negative** | **STRONG** (all budgets) |
| strategy7_budget_split_sweep_v1 | both | various | varied splits | L370_S700_U30 | Pareto fronts exist | Mixed | **MEDIUM** |
| Certificate seed stats | both | all | S7 vs L3 | per-seed CI computed | see certificate_seed_stats.csv | — | **COMPUTED** |

### Table D: GLM Cost Accounting

| Question | Answer | Confidence |
|----------|--------|------------|
| Budget B counts what? | Only Qwen3-VL-32B calls | **HIGH** |
| GLM calls in budget? | No | **HIGH** |
| GLM online or offline? | Offline pilot | **HIGH** |
| GLM cost data? | Partial (20.7s mean latency) | **MEDIUM** |
| Cascade claim affected? | "95% Qwen reduction" ≠ "95% total cost reduction" | **MEDIUM** |

---

## 3. Key Numbers for Meeting

### Numbers ready to present (with source)

1. **V13.8 oracle reference**: 399 anchors, 94 positive (23.6%), 51 stitched events, 0% abstain, 100% complete. Source: `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/`.

2. **OracleBest upper bound**: `min(B,51)/51`. At B=20: 0.392. At B=40: 0.784. Source: `test_vlm/outputs/v13_10/reports/V13_10_REPORT.md`.

3. **Static best at B=40 (discovery-based)**: `prefilter_div_objmean_P2B_a0.5` = 0.314, vs V13.9 best 0.216. **+0.098 absolute / +45% relative improvement from switching to budget-decomposition (no new proxy).** Bonferroni-significant. Source: `experiments/diversity_prefilter/diversity_prefilter_replay_v1/reports/FINAL_REPORT.md`.

4. **object_count_mean is the strongest deployable proxy**: AUROC 0.627 (dataset3) / 0.738 (realcartest). Person_count_max is hindsight only (AUROC 0.814 but not deployable). Source: `glm52_proxy_calibration_diversity_v1`, `glm52_sprint3_certificate_queryprior_v1`.

5. **Strategy7 recovers L3-missed positives**: +7-16pp gain (corrected from +25.7pp headline). Mechanism is real. Source: `post_transition_strategy7_audit_v1`.

6. **Certificate tradeoff**: On realcartest, Strategy7 has R_lower gap of -0.015 to -0.057 vs L3+uniform at all budgets tested (B=20 to B=150). Recovery improvement comes at a certificate tightness cost. Source: `strategy7_certificate_power_v1`.

7. **Exact hypergeometric bound validated**: Coverage = 1.0 >= nominal 0.95 under Monte Carlo. Temporal clustering does not invalidate SRSWOR estimation. Source: `glm52_sprint3_certificate_queryprior_v1`.

8. **Certificate is UNDERPOWERED**: Only 51 events on realcartest. Phase 0.6 estimates ~500 events needed. v12.1 certificate had <30 oracle positives in the reserved pool. Source: `v12_1_completion_v1`, `clip_aqp_phase0_v1`.

### Numbers NOT ready to present

- "Strategy7 fixes certificate" — it does not; on realcartest, it makes the certificate looser.
- "GLM cascade saves 95% cost" — saves 95% of Qwen calls, but GLM cost is unaccounted.
- "Cross-video generalization of budget decomposition" — single video only.

---

## 4. Risks and Caveats

### 4.1 Recovery vs Certificate metric confusion

The post-transition audit and certificate power reports clearly distinguish recovery metrics (L3-missed recovered count, anchor recall) from certificate metrics (R_lower, gamma certificate rate). However, there is a risk of conflation:

- The headline "+25.7pp recovery" was initially presented without the certificate tradeoff caveat. The budget split sweep was needed to expose the tradeoff explicitly.
- **Recommendation**: Always present recovery gain and certificate gap in the same table. Do not claim "S7 improves recall" without "but R_lower may be looser."

### 4.2 Gaps missing confidence intervals

- The post-transition strategy7 audit (the source of the +7-16pp range) provides only point estimates. No per-seed CI or bootstrap was computed for recovery metrics.
- Certificate seed statistics **are** available for R_lower (500 seeds) and were computed in this audit. But recovery-specific seed statistics are absent.
- **Recommendation**: Re-run the recovery metrics with per-seed paired analysis (bootstrap CI for the S7-vs-L3 gap). This is a no-new-model analysis (only replay over existing seed traces).

### 4.3 Budget split post-hoc search risk

The strategy7 budget split sweep tested 14 split configurations. The Pareto front analysis could overfit to dataset-specific characteristics. Key risks:
- The recommended splits (e.g., L350_S730_U20 for dataset3) are dataset-specific.
- No replication exists on realcartest for the Pareto fronts that worked on dataset3.
- The split sweep is a diagnostic, not a deployment policy.
- **Recommendation**: Do not present specific split fractions as "optimal" without cross-validation.

### 4.4 GLM cost changes the problem definition

Current budget definition (B = Qwen calls only) creates an asymmetry:
- L3 (proxy-only): cost = B_Qwen
- S7 (disagreement audit): cost = B_Qwen + B_GLM (if GLM were online)

If GLM were deployed online, the problem would change from "budget B oracle calls" to "budget B total calls (oracle + auxiliary model)." The current framing of "B=20 → S7 recovers more positives" would need to be restated as "B_Qwen=20 + B_GLM=20 → S7 recovers more positives at total cost 40."

**This does not affect the diversity prefilter (H1) findings**, which use only YOLO + Qwen with no auxiliary model. It does affect any claim about Strategy7 being "budget-efficient."

---

## 5. Recommended Next Steps

### Immediate (no new experiments, no GPU)

1. **Compute per-seed recovery CIs**: Use the existing seed traces from strategy7 experiments to compute paired bootstrap CI for the S7-vs-L3 recovery gap. This is pure CPU replay.
2. **Certificate B1 no-repair simulation**: Use the V13.8 oracle with the diversity_prefilter recall (0.314 at B=40) and compute what certificate (even if vacuous) would look like. This is pure CSV replay.
3. **Fix the stale track_transition_validation_v1 FINAL_SUMMARY.md bug**: The top-level summary says `INPUT_MISSING` but the actual analysis says `TRACK_TRANSITION_NOT_USEFUL`.

### Next experiment (if authorized)

1. **Certificate on V13.8 with B1 no-repair simulation**: First verify the guarantee layer mechanics even if R_lower is low. Separately document "what B would be needed for non-vacuous certificate at γ=0.3/δ=0.05."
2. **Second long-video**: The budget-decomposition (diversity prefilter) finding needs a second video before any generalization claim. Start with a small center10 pilot (avoid full 32B scan).
3. **Do NOT run**: More GLM cascade experiments (GLM is NOT useful for this query per GLM41V_NOT_USEFUL decision). More random calibration experiments (calibration is unstable at small c per CALIBRATION_UNSTABLE_USE_QUERY_PRIOR). More local adaptive refine experiments (ADAPTIVE_NO_BETTER confirmed across 3 independent runs: V13.10, diversity H3, strategy7).

---

## Final Decision

`FINAL_DECISION: MIXED_EVIDENCE_NEEDS_STATS`

**Rationale:**
- **Strong evidence**: Static prior effectiveness, adaptive failure, exact hypergeometric bound validity — each replicated across 2+ independent experiments.
- **Missing statistics**: The recovery claim (S7 +7-16pp) lacks per-seed CI. Certificate tradeoff gaps are documented but not tested for between-policy significance.
- **GLM cost is not a blocker** for the main AQP contribution line (diversity prefilter H1 uses no GLM). It is a blocker for the GLM cascade claim and for any "S7 is budget-efficient" claim without full cost accounting.
- **The certificate on V13.8 is the single biggest evidence gap** — without it, no paper can claim a working clip-level recall certificate.
