# GLM Cost Accounting Audit

**Date:** 2026-06-28 (read-only evidence audit)
**Scope:** Determine whether GLM (GLM-4.1V / GLM-4.6V) calls are counted in the AQP budget formula.

## Evidence Sources

- `src/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1/reports/GLM41V_QWEN32B_ORACLE_COMPARISON.md`
- `src/garc_eval/outputs/glm52_sprint3_certificate_queryprior_v1/reports/SPRINT3_SUMMARY.md`
- `src/garc_eval/outputs/glm52_proxy_calibration_diversity_v1/reports/GLM52_PROXY_CALIBRATION_DIVERSITY_FINAL_REPORT.md`
- `src/garc_eval/outputs/strategy7_certificate_power_v1/reports/STRATEGY7_CERTIFICATE_POWER_REPORT.md`
- `src/garc_eval/outputs/strategy7_budget_split_sweep_v1/reports/STRATEGY7_BUDGET_SPLIT_SWEEP_REPORT.md`
- `src/garc_eval/outputs/post_transition_strategy7_audit_v1/FINAL_SUMMARY.md`
- `test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/` (V13.9 budget definitions)
- `test_vlm/outputs/v13_10/reports/V13_10_REPORT.md`

---

## Question 1: Current budget formula — which calls are counted?

**Answer:** The budget `B` counts only **Qwen3-VL-32B oracle calls**.

Evidence:
- V13.9 methods: `proxy_top-B → oracle examines exactly those B`. Budget = number of anchors sent to the oracle (Qwen3-VL-32B).
- V13.10: `OracleBest@B = min(B,51)/51`, where the 51 is the number of Qwen-identified events.
- Strategy7/gLM experiments: All reports explicitly state "no Qwen, GLM, YOLO" were run. The budget `B` refers to Qwen oracle calls in simulation.
- The certificate power report: budget B = Qwen calls to the oracle. "Only the final uniform random audit is used for the exact residual hypergeometric bound."
- Budget split sweep: `requested_B` and `effective_B` refer to total oracle call budget, with `exploit_n` (L3 proxy-top), `targeted_audit_n` (disagreement audit), and `random_audit_n` (uniform random) summing to B.

**Conclusion: Only Qwen oracle calls are counted in B.**

---

## Question 2: Qwen/oracle calls — are they counted in budget?

**Answer: Yes.** Every Qwen call is counted as 1 unit in budget B.

Evidence: All V13 experiments (V13.5 through V13.10) explicitly define B as the number of Qwen3-VL-32B calls. The diversity prefilter replay uses this same convention. Strategy7 certificate power and budget split sweep both model B as total oracle calls.

---

## Question 3: GLM calls — are they counted in budget?

**Answer: No.** GLM-4.1V calls are NOT counted in the AQP budget formula in any existing experiment.

Evidence:
- The GLM-4.1V pilot (106 paired samples) was an offline comparison study, not an online query execution.
- In the Strategy7 pipeline, the disagreement signal between L3 (YOLO-based static proxy) and an auxiliary model (which could be GLM) is used as a signal, but the GLM calls themselves are not budgeted.
- The post-transition audit states: "No new model called (no VLM, no Qwen, no GLM, no GPT, no YOLO rerun, no CLIP, no motion proxy)."
- The strategy7 certificate power report input audit shows `glm_counts` as pre-existing label metadata, not as online calls.

**Critical gap**: If GLM calls were part of the online query path (i.e., every query requires GLM disagreement scoring), the true cost would be B_Qwen + B_GLM. Since GLM is currently offline/materialized, this has not been an issue. But in a deployable pipeline, GLM calls would need to be counted.

---

## Question 4: GLM — run on full pool, residual pool, or sampled pool?

**Answer:** GLM-4.1V was run on a **sampled pool** — specifically 106 of 347 anchors from dataset3 (the "paired" evaluation set).

Evidence:
- GLM-4.1V pilot: 123 total samples drawn (40 reference positives + hard negatives + random negatives), of which 106 parsed successfully.
- The comparison was a paired rerun: both GLM and Qwen saw the same contact sheets.
- GLM was NOT run on the full candidate pool in any experiment visible in the outputs.

In the Strategy7 pipeline, the disagreement audit signal is simulated from existing labels, not from online GLM execution. The `glm_counts` in the input manifest show pre-existing labels used for evaluation only.

---

## Question 5: GLM — online query path or offline/materialized signal?

**Answer: Offline/materialized.** GLM evaluation was performed as a separate pilot study, not as part of the online AQP query path.

Evidence:
- GLM-4.1V pilot output: "This pilot evaluates GLM-4.1V as a candidate cheaper oracle approximation or cascade router."
- The experiment was a one-time paired comparison, producing cached disagreement labels.
- Strategy7 experiments explicitly state they use existing GLM labels for the disagreement signal — not that they call GLM at query time.
- All post-transition strategy7 and certificate experiments explicitly declare "no new model calls."

**If GLM disagreement were deployed as the online disagreement signal**, it would be online and would need budget accounting. Currently it is not.

---

## Question 6: GLM call count, runtime, GPU time — exists?

**Answer: Partially.** The GLM-4.1V pilot reports latency and GPU memory:

| Metric | GLM-4.1V |
|--------|----------|
| Mean latency | 20.7s |
| P50 latency | 18.638s |
| P95 latency | 33.8s |
| Peak GPU memory | 19.555 GB |
| GPU | A800-SXM4-80GB |

But there is no equivalent Qwen-32B per-call latency reported for comparison (only total wall time for 399 calls: ~74 min on A800).

No systematic GLM call count, runtime log, or cost extrapolation exists beyond the pilot.

---

## Question 7: If GLM costs not counted — which conclusions need rewriting?

**If GLM calls were added to the online budget**, the following would need revision:

### Conclusions potentially affected:

| Claim / Conclusion | Risk | Severity |
|--------------------|------|----------|
| Strategy7 +7-16pp gain on L3-missed positives | LOW (GLM is preprocessing, not per-query) | Low — GLM cost is amortized/offline. |
| Strategy7 certificate power (R_lower gaps) | MEDIUM — if GLM disagreement audit consumes budget but is not counted, the true B_effective is higher than stated | Medium |
| "Budget decomposition works at B=40" (diversity prefilter) | NONE — diversity prefilter uses only YOLO + Qwen, no GLM | Not affected |
| "Certificate tradeoff: more S7 → less uniform → looser bound" | LOW — same reasoning applies regardless of whether S7 audit uses GLM; the split fractions need redefinition | Low |
| "GLM cascade reduces Qwen calls by 95%" | MAJOR — this claim explicitly depends on adding GLM cost | High — If GLM cost is counted, the 95% Qwen reduction may not translate to 95% total cost reduction. |
| "object_count_mean is the strongest deployable proxy" | NONE — no GLM involved | Not affected |

### Need to check for this specific reference

The most important finding: the glm41v report "Cascade P2 Qwen call reduction 95%" is a **cost-to-Qwen reduction**, not a **total budget reduction**. If GLM calls are equally expensive (20.7s mean latency vs Qwen's ~11s), the cost savings are half the headline.

**Recommendation**: Rewrite any GLM cascade claim as "reduces Qwen32B calls by X%" not "reduces total cost by X%" unless GLM cost is separately accounted.

---

## Summary

| Question | Answer |
|----------|--------|
| 1. What does budget B count? | Only Qwen3-VL-32B oracle calls |
| 2. Qwen calls in budget? | Yes, every Qwen call is 1 unit of B |
| 3. GLM calls in budget? | No — GLM is offline/materialized, not counted |
| 4. GLM runs on which pool? | Sampled pool (106/347 anchors) |
| 5. GLM online or offline? | Offline pilot study |
| 6. GLM cost data exists? | Partial: mean 20.7s latency, 19.5GB GPU memory |
| 7. Which conclusions need rewriting? | GLM cascade cost reduction claims (if any present themselves as total cost savings) |
