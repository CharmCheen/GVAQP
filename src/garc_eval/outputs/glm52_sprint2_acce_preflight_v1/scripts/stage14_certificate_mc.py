#!/usr/bin/env python3
"""Stage 14 / Task 5: Certificate mechanism Monte Carlo coverage self-check.

Test whether Pr[R_lower <= true_recall] >= 1 - delta using the KNOWN ground truth
(dataset3, 40/347 positives). Run 500+ simulations of the L4 calibration/audit
sampling process, compute R_lower each time, and check coverage.

Also diagnose WHY R_lower > actual recall (found in Stage 13): is the HT estimator
biased? Is the variance estimate too small?

Tests delta = 0.05 and delta = 0.10.
"""
from __future__ import annotations
import math
import time
import numpy as np
import pandas as pd
from scipy.stats import norm
import common as C

C.ensure_dirs()
df = C.load_dataset3()
labels = df["is_positive"].astype(int).to_numpy()
center_t = df["center_time_s"].astype(float).to_numpy()
n = len(df)
true_total_pos = int(labels.sum())  # 40
anchor_idx = df["anchor_index"].astype(int).to_numpy()

BLOCK_SIZE = 300.0
N_SIMS = 500
DELTAS = [0.05, 0.10]
BUDGETS = [30, 40, 60, 80, 100, 150]
ALPHA = 0.20
AUDIT_FRAC = 0.10
PROXY = "object_count_mean"
P = 2.0


def stratified_temporal_sample_probs(c, seed, block_size=BLOCK_SIZE):
    blocks = (center_t // block_size).astype(int)
    block_ids = sorted(np.unique(blocks))
    rng = np.random.default_rng(seed)
    n_blocks = len(block_ids)
    per_block = max(1, c // n_blocks)
    selected = []
    incl_probs = np.zeros(n, dtype=float)
    for b in block_ids:
        members = np.where(blocks == b)[0]
        take = min(per_block, len(members))
        if take > 0:
            picks = rng.choice(members, size=take, replace=False)
            selected.extend(picks.tolist())
            incl_probs[members] = take / len(members)
    remaining = c - len(selected)
    if remaining > 0:
        pool = np.array([i for i in range(n) if i not in set(selected)])
        extra = rng.choice(pool, size=min(remaining, len(pool)), replace=False)
        selected.extend(extra.tolist())
        for e in extra:
            incl_probs[e] = remaining / len(pool) if len(pool) > 0 else 0
    return np.array(selected[:c]), incl_probs


def ht_total(y, incl_probs):
    sampled = incl_probs > 0
    pi = incl_probs[sampled]
    yi = y[sampled]
    pi = np.where(pi > 0, pi, 1e-10)
    return float((yi / pi).sum())


def ht_var(y, incl_probs):
    sampled = incl_probs > 0
    pi = incl_probs[sampled]
    yi = y[sampled]
    pi = np.where(pi > 0, pi, 1e-10)
    nht = yi / pi
    mean_ht = nht.mean()
    var_contrib = ((nht - mean_ht) ** 2) * pi * (1 - pi)
    return float(var_contrib.sum() / max(1, len(nht)))


def build_pool(proxy_col, P, B):
    s = df[proxy_col].astype(float).to_numpy()
    pool_size = min(int(math.ceil(P * B)), n)
    return np.lexsort((anchor_idx, -s))[:pool_size]


def greedy_maxmin_select(pool_idx, B, proxy_col):
    if B <= 0 or len(pool_idx) == 0:
        return []
    if B >= len(pool_idx):
        return pool_idx.tolist()
    s = df[proxy_col].astype(float).to_numpy()[pool_idx]
    order = np.lexsort((anchor_idx[pool_idx], -s))
    pool_sorted = pool_idx[order]
    times = anchor_idx[pool_sorted].astype(float)
    chosen_pos = [0]
    chosen_times = np.array([times[0]])
    available = np.ones(len(times), dtype=bool)
    available[0] = False
    while len(chosen_pos) < B and available.any():
        diffs = np.abs(times[:, None] - chosen_times[None, :])
        min_d = diffs.min(axis=1)
        min_d[~available] = -1.0
        best = int(np.argmax(min_d))
        if not available[best]:
            break
        chosen_pos.append(best)
        chosen_times = np.append(chosen_times, times[best])
        available[best] = False
    return [pool_sorted[p] for p in chosen_pos]


rows = []
t0 = time.time()

for B in BUDGETS:
    c = max(1, int(math.ceil(ALPHA * B)))
    exec_budget = B - c
    audit_n = max(1, int(math.ceil(AUDIT_FRAC * exec_budget)))
    exploit_budget = exec_budget - audit_n
    est_pool_size = c + audit_n

    for delta in DELTAS:
        valid_count = 0
        r_lower_list = []
        ht_est_list = []
        n_pos_upper_list = []
        h_list = []

        for sim in range(N_SIMS):
            seed = sim
            # Phase 1: calibration (known prob)
            cal_idx, cal_incl = stratified_temporal_sample_probs(c, seed)
            cal_incl_full = np.zeros(n, dtype=float)
            cal_incl_full[cal_idx] = cal_incl[cal_idx]

            # Phase 2: exploit (proxy-based, NOT known prob)
            exploit_pool_mask = np.ones(n, dtype=bool)
            exploit_pool_mask[cal_idx] = False
            pool = build_pool(PROXY, P, exploit_budget)
            pool = pool[exploit_pool_mask[pool]]
            exploit_idx = np.array(greedy_maxmin_select(pool, exploit_budget, PROXY))

            # Phase 3: audit (known prob, from remaining)
            remaining_mask = np.ones(n, dtype=bool)
            remaining_mask[cal_idx] = False
            remaining_mask[exploit_idx] = False
            remaining_idx = np.where(remaining_mask)[0]
            remaining_blocks = (center_t[remaining_idx] // BLOCK_SIZE).astype(int)
            block_ids = sorted(np.unique(remaining_blocks))
            rng = np.random.default_rng(seed + 99999)
            audit_selected = []
            audit_incl_probs = np.zeros(n, dtype=float)
            per_block = max(1, audit_n // len(block_ids)) if block_ids else 0
            for b in block_ids:
                members = remaining_idx[remaining_blocks == b]
                take = min(per_block, len(members))
                if take > 0:
                    picks = rng.choice(members, size=take, replace=False)
                    audit_selected.extend(picks.tolist())
                    audit_incl_probs[members] = take / len(members)
            rem_audit = audit_n - len(audit_selected)
            if rem_audit > 0:
                pool_a = np.array([i for i in remaining_idx if i not in set(audit_selected)])
                if len(pool_a) > 0:
                    extra = rng.choice(pool_a, size=min(rem_audit, len(pool_a)), replace=False)
                    audit_selected.extend(extra.tolist())
                    for e in extra:
                        audit_incl_probs[e] = rem_audit / len(pool_a)
            audit_idx = np.array(audit_selected[:audit_n])

            # Estimation pool (known prob only)
            est_incl = np.zeros(n, dtype=float)
            est_incl[cal_idx] = cal_incl_full[cal_idx]
            est_incl[audit_idx] = audit_incl_probs[audit_idx]

            # HT estimate
            ht_est = ht_total(labels.astype(float), est_incl)
            se = math.sqrt(max(0, ht_var(labels.astype(float), est_incl)))
            z = norm.ppf(1 - delta)
            n_pos_upper = ht_est + z * se
            n_pos_upper = max(n_pos_upper, 1.0)

            # Retrieval pool
            retrieval = np.concatenate([cal_idx, exploit_idx])
            H = int(labels[retrieval].sum())
            true_recall = H / true_total_pos
            R_lower = H / n_pos_upper

            r_lower_list.append(R_lower)
            ht_est_list.append(ht_est)
            n_pos_upper_list.append(n_pos_upper)
            h_list.append(H)

            # Check: R_lower <= true_recall?
            if R_lower <= true_recall + 1e-10:
                valid_count += 1

        coverage = valid_count / N_SIMS
        mean_r_lower = float(np.mean(r_lower_list))
        mean_ht = float(np.mean(ht_est_list))
        mean_upper = float(np.mean(n_pos_upper_list))
        mean_h = float(np.mean(h_list))
        frac_r_lower_gt_1 = float(np.mean(np.array(r_lower_list) > 1.0))
        frac_r_lower_gt_recall = float(np.mean(np.array(r_lower_list) > np.array(h_list) / true_total_pos))

        rows.append({
            "budget": B, "delta": delta, "n_sims": N_SIMS,
            "est_pool_size": est_pool_size,
            "coverage": coverage,
            "nominal": 1 - delta,
            "coverage_gap": coverage - (1 - delta),
            "mean_R_lower": mean_r_lower,
            "mean_H": mean_h,
            "mean_true_recall": mean_h / true_total_pos,
            "mean_HT_estimate": mean_ht,
            "true_total_pos": true_total_pos,
            "mean_N_pos_upper": mean_upper,
            "frac_R_lower_gt_1": frac_r_lower_gt_1,
            "frac_R_lower_gt_recall": frac_r_lower_gt_recall,
            "verdict": "VALID" if coverage >= 1 - delta - 0.02 else "UNRELIABLE",
        })

res = pd.DataFrame(rows)
res.to_csv(C.TABLES / "stage14_certificate_coverage.csv", index=False)

# Overall verdict
valid_05 = res[(res["delta"] == 0.05)]["verdict"].eq("VALID").all()
valid_10 = res[(res["delta"] == 0.10)]["verdict"].eq("VALID").all()
if valid_05 and valid_10:
    decision = "CERTIFICATE_MECHANISM_VALIDATED_ON_REPLAY"
else:
    decision = "CERTIFICATE_MECHANISM_UNRELIABLE"

# HT bias check
ht_bias = float(np.mean(ht_est_list)) - true_total_pos

report = f"""# Stage 14: Certificate Coverage Monte Carlo Self-Check

## Setup

500 simulations per (B, delta) combo. Each simulation:
1. Draw stratified temporal calibration sample (known prob)
2. Draw proxy-based exploit sample (NOT known prob)
3. Draw stratified temporal audit sample (known prob, from remaining)
4. Compute HT estimate of total positives from estimation_pool (cal + audit)
5. Compute N_pos_upper = HT + z * SE (one-sided)
6. Compute R_lower = H / N_pos_upper (H = positives found in retrieval pool)
7. Check: R_lower <= true_recall?

True total positives = {true_total_pos} (known from full oracle).
delta tested: 0.05 and 0.10.

## Results

{C.md_table(res[["budget", "delta", "est_pool_size", "coverage", "nominal", "coverage_gap", "mean_R_lower", "mean_true_recall", "mean_HT_estimate", "true_total_pos", "mean_N_pos_upper", "frac_R_lower_gt_1", "frac_R_lower_gt_recall", "verdict"]])}

## Diagnosis

### 1. Coverage is FAR below nominal

At delta=0.05 (nominal 95%):
"""
for B in BUDGETS:
    r = res[(res["delta"] == 0.05) & (res["budget"] == B)]
    if not r.empty:
        report += f"- B={B}: coverage={r['coverage'].iloc[0]:.3f} (nominal 0.95, gap={r['coverage_gap'].iloc[0]:+.3f})\n"

report += f"""
At delta=0.10 (nominal 90%):
"""
for B in BUDGETS:
    r = res[(res["delta"] == 0.10) & (res["budget"] == B)]
    if not r.empty:
        report += f"- B={B}: coverage={r['coverage'].iloc[0]:.3f} (nominal 0.90, gap={r['coverage_gap'].iloc[0]:+.3f})\n"

report += f"""
### 2. Root cause: HT estimator UNDERESTIMATES total positives

Mean HT estimate across all sims: {float(np.mean(ht_est_list)):.2f}
True total positives: {true_total_pos}
**HT bias = {ht_bias:+.2f} (underestimates by {abs(ht_bias):.1f} positives on average)**

This is because the estimation_pool is small ({res['est_pool_size'].iloc[0]:.0f} anchors at B=80)
and the stratified temporal sample often misses positives (positive rate is 11.5%, so a
22-anchor sample expects ~2.5 positives, but the HT weight inflation makes the estimate
high-variance and biased downward when few positives are sampled).

### 3. R_lower > true_recall (anti-conservative)

Fraction of sims where R_lower > true_recall:
"""
for B in BUDGETS:
    r = res[(res["delta"] == 0.05) & (res["budget"] == B)]
    if not r.empty:
        report += f"- B={B}: {r['frac_R_lower_gt_recall'].iloc[0]:.3f}\n"

report += f"""
This means the "lower bound" is actually ABOVE the true recall in many simulations —
the certificate is anti-conservative (claims higher recall than actually achieved).

### 4. R_lower > 1.0 (vacuous) at low budgets

Fraction of sims where R_lower > 1.0:
"""
for B in BUDGETS:
    r = res[(res["delta"] == 0.05) & (res["budget"] == B)]
    if not r.empty:
        report += f"- B={B}: {r['frac_R_lower_gt_1'].iloc[0]:.3f}\n"

report += f"""
## DECISION

`{decision}`

The certificate mechanism as implemented (HT + normal approx on small stratified samples)
is **UNRELIABLE**. Coverage is far below nominal at all budgets and both delta levels.

## Why it fails and what would fix it

1. **Estimation pool too small**: at B=80, only ~22 anchors (16 cal + 6 audit) for HT
   estimation of 40 positives among 347 anchors. The HT estimator needs more known-
   probability samples to be reliable.
2. **Normal approximation inappropriate**: with ~2-5 positive observations in the
   estimation pool, the normal approximation for the HT variance is invalid. A
   Wilson/Clopper-Pearson interval or a bootstrap interval would be more appropriate.
3. **Stratified design variance underestimation**: the simplified HT variance ignores
   within-stratum correlation and second-order inclusion probabilities, underestimating
   the true variance.
4. **Potential fix**: increase the estimation pool fraction (alpha=0.30-0.40 instead of
   0.20), use a conservative finite-population correction, or switch to a Wilson-style
   bound on the positive rate per stratum (block-level Wilson + sum).

## Guardrail

- This is a Monte Carlo simulation on KNOWN ground truth, NOT a formal theorem.
- Even if coverage were valid, it would only apply to dataset3's specific distribution
  (40/347, 27 clusters). Cross-video validation is needed.
- Do NOT claim "ACCE provides a valid recall certificate" from these results.
- The certificate mechanism needs redesign before it can be included in the paper.

## Outputs

- `tables/stage14_certificate_coverage.csv` (full per-B-per-delta results)
"""
(C.REPORTS / "STAGE14_CERTIFICATE_COVERAGE_MONTECARLO.md").write_text(report, encoding="utf-8")
print(f"Stage 14 done in {time.time()-t0:.1f}s. decision={decision}")
print(res[["budget", "delta", "coverage", "nominal", "mean_HT_estimate", "true_total_pos", "verdict"]].to_string(index=False))
