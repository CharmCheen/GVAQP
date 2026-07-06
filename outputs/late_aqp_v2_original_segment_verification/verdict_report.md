# Verdict Report — Frozen-LATE-AQP-v2 on Original Failure Segments

## Core questions

### (a) B=10/20 improvement vs v1 per segment

| Segment | Budget | v1 mean | v1 std | v2 mean | v2 std | Δ (v2-v1) | Δ > v1 std? |
|---------|--------|---------|--------|---------|--------|-----------|-------------|
| realcartest_0_1570 | 10 | 0.125 | 0.000 | 0.125 | 0.000 | 0.000 | No |
| realcartest_0_1570 | 20 | 0.250 | 0.079 | 0.375 | 0.000 | 0.125 | Yes |
| realcartest_2000_3200 | 10 | 0.300 | 0.067 | 0.333 | 0.000 | 0.033 | No |
| realcartest_2000_3200 | 20 | 0.467 | 0.067 | 0.500 | 0.000 | 0.033 | No |
| realcartest_3200_3830 | 10 | 0.250 | 0.000 | 0.250 | 0.000 | 0.000 | No |
| realcartest_3200_3830 | 20 | 0.450 | 0.100 | 0.500 | 0.000 | 0.050 | No |

Interpretation: Only **realcartest_0_1570 at B=20** shows a substantive (above seed-noise) improvement. No segment improves at **both** B=10 and B=20.

### (b) cold_start_fallback trigger activation

**All B≤20 trials activated cold_start_fallback: Yes** (audit_calls=0, repair_calls=0, discovery_calls=budget in every B≤20 trial). v2 is *not* silently falling back to the v1 path; the difference is that v1 spends some calls on stochastic audit/repair while v2 spends the entire budget on deterministic discovery.

### (c) High-budget (B=40/80/120) regression

No v2 drop exceeds the v1 within-seed standard deviation at B=40/80/120. See `high_budget_regression_check.md` for the full table.

## Low-budget (B=10/20) per-segment improvement (duplicate of core question a)

| Segment | Budget | v1 mean | v1 std | v2 mean | v2 std | Δ | Δ > v1 std? |
|---------|--------|---------|--------|---------|--------|---|-------------|
| realcartest_0_1570 | 10 | 0.125 | 0.000 | 0.125 | 0.000 | 0.000 | No |
| realcartest_0_1570 | 20 | 0.250 | 0.079 | 0.375 | 0.000 | 0.125 | Yes |
| realcartest_2000_3200 | 10 | 0.300 | 0.067 | 0.333 | 0.000 | 0.033 | No |
| realcartest_2000_3200 | 20 | 0.467 | 0.067 | 0.500 | 0.000 | 0.033 | No |
| realcartest_3200_3830 | 10 | 0.250 | 0.000 | 0.250 | 0.000 | 0.000 | No |
| realcartest_3200_3830 | 20 | 0.450 | 0.100 | 0.500 | 0.000 | 0.050 | No |

Segments with substantive improvement at **both** B=10 and B=20: **0/3**

## High-budget (B=40/80/120) regression

No regression exceeds v1 within-seed standard deviation at B=40/80/120.

## Verdict

**FAIL**: cold_start_fallback is activated but does not substantively improve B=10/20 long-event recall on at least 2 of the 3 original failure segments. The low-budget problem remains unresolved.
