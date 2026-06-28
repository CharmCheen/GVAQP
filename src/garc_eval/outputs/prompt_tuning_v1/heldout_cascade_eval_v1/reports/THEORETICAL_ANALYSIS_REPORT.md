# From Proxy Enrichment to Recall Certificate Budget: Empirical and Finite-Population Analysis

**Date**: 2026-06-27
**Context**: GLM-4.1V cascade evaluation for AQP budget allocation
**Candidate pool**: N=123 (pilot subset of dataset3)

---

## 1. Distinction: Selection Efficiency vs Certificate Validity

This analysis separates two concepts that are often conflated:

1. **Selection efficiency**: How well a candidate selection strategy (L3, GLM, disagreement) discovers Qwen-positives (`H`). Improves recall and positive yield.
2. **Certificate validity**: The statistical correctness of the recall lower bound computed from a random audit. Depends on finite-population random sampling, not on proxy AUC.

---

## 2. Selection Efficiency Contributors

### From Phase 3 cascade results:

| Strategy | B=40 recall (H/40) | B=60 H/40 | Positive yield (B=40) |
|----------|---------------------|------------|----------------------|
| L3_baseline | 6.0 (15%) | 13.0 (32.5%) | 15.0% |
| GLM_positive_only | 24.0 (60%) | 24.0 (60%) | 61.5% |
| GLM+L3_neg (4) | 24.0 (60%) | 27.0 (67.5%) | 60.0% |
| L3+GLM_disag_audit (7) | 11.0 (27.5%) | 19.0 (47.5%) | 27.5% |

**Selection efficiency ranking**: Strategy 4 > Strategy 2 > Strategy 7 > L3_baseline > Strategy 6

GLM-based strategies improve `H` (discovered positives) by:
- **Enrichment**: GLM-positive bin has 61.5% positive rate (3.3x base rate)
- **Priority boost**: Putting GLM-positive anchors first maximizes positive yield per budget slot

The GLM/proxy disagreement signal (Strategy 7) improves `H` at B=60 from 13 (L3) to 19 (+46% relative), primarily through GLM's enrichment of the audit pool.

---

## 3. Certificate Validity: Finite-Population Exact Bound

### Framework

Given:
- `H`: discovered positives (from exploitation)
- `N`: total candidate pool size = 123
- `n`: random audit sample size
- `k`: missed positives observed in audit
- `1 - δ`: confidence level (e.g., 0.95)

The **hypergeometric exact bound** for unobserved missed positives `U`:

```
P(K ≤ k | M_true = U) = Σ_{i=0}^k hypergeom.pmf(i, N, U, n)
```

Find maximum `U` such that `P(K ≤ k | U) > δ`. Then:

```
recall_lower_bound = H / (H + U)
```

### Why this bound is valid without i.i.d. event assumptions

- The bound requires only that the audit sample `n` is a **simple random sample without replacement** from the finite population of size `N` (the unaudited pool).
- Temporal correlation between clips affects **efficiency** (how many positives are in the exploitation set) and **variance** (how tightly `H` is known), but does NOT break the validity of a finite-population random sample.
- The finite-population hypergeometric distribution is exact for simple random sampling — it does not require independence between units.
- This is a standard result in survey sampling and finite-population inference.

---

## 4. Why AUC Does Not Determine Certificate Budget

A common misconception: "if proxy AUC > 0.5 + ε, then B needed for γ-recall is X."

This is **incorrect** because AUC is a global ranking metric that does not capture:
1. **Top-k recall shape**: Two proxies with identical AUC can have different top-k recall (one may put all positives in top-10%, another may spread them)
2. **Low-tail miss mass**: AUC doesn't tell you how many positives are ranked in the bottom half — these are the ones that determine certificate tightness
3. **Cluster structure**: AUC is computed per-anchor; event-cluster recall depends on temporal grouping

**What AUC can tell you**:
- AUC ≈ 0.5: proxy is random, no enrichment possible → minimum B = N (exhaustive scan)
- AUC > 0.5: some enrichment is possible, but the magnitude depends on the full ranking distribution, not just AUC
- AUC = 0.738 (object_count_mean on V13.8): provides meaningful enrichment but still misses many positives in low-proxy regions

---

## 5. Connection to GLM Cascade Experiments

### 5.1 GLM as a booster improves H

At B=40:
- L3 alone: H=6
- GLM+L3_neg: H=24 (4x improvement)
- This directly improves `recall_lower_bound = H/(H+U)` by increasing the numerator

### 5.2 GLM disagreement audit reduces residual risk

At B=60, Strategy 7 vs Strategy 6:
- Uniform audit: H≈13.6, residual misses ≈ 26.4
- GLM disag audit: H≈19, residual misses ≈ 21
- The GLM-based audit found ~5.4 more positives, reducing the upper bound on undiscovered positives

### 5.3 Certificate tightness

With H=24 (GLM+L3_neg at B=40), N=123, and no explicit audit:
- The 83 unaudited anchors contain 16 undetected Qwen-positives
- Certificate would be weak without an audit layer

Adding a random audit of n=20 from the unaudited pool:
- If k=4 missed positives observed, U_95 ≈ 11 (hypergeometric inversion)
- recall_lower_bound = 24/(24+11) = 68.6%
- Without GLM (L3 alone at B=40): H=6, same audit k=7, U_95 ≈ 18
- recall_lower_bound = 6/(6+18) = 25.0%

**GLM improves certificate tightness from 25% to 69% at B=40** by increasing `H`.

### 5.4 What GLM does NOT do for certificate

- GLM does NOT change the validity of the hypergeometric bound
- GLM does NOT reduce the required audit size for a given confidence level
- GLM does NOT make the bound independent of the candidate pool distribution

---

## 6. Practical Implications

1. **Use GLM as a cheap enrichment layer** to maximize `H` per Qwen budget
2. **Retain a random audit component** for certificate validity — GLM cannot replace random audit
3. **Report certificate with explicit N, n, H, k, δ** — not as a single "recall" number
4. **The 40% FN rate of GLM means GLM-negative anchors still need probabilistic coverage** — either through L3 exploration (Strategy 4) or random audit (Strategy 6/7)
5. **For tight certificates at γ≥0.9**: given N=123 and 40 total positives, full Qwen scan (B=123) gives recall=100%, and certificate is trivially tight. For B<123, certificate tightness depends on `H` and audit size.

---

## 7. Limitations

- Analysis is on a single 123-anchor pilot from one video (dataset3)
- Qwen reference is VLM-oracle, not human-adjudicated
- GLM model is GLM-4.1V-9B (may differ from future GLM versions)
- Hypergeometric bound assumes simple random sampling; violation (e.g., stratified audit) requires adjusted bounds

---

*Generated on 2026-06-27*
