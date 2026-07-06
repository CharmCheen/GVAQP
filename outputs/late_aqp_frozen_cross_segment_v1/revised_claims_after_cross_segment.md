# Revised Claims After Cross-Segment Validation

This document updates the main LATE-AQP empirical claims in light of the frozen cross-segment replay.

## Original Claim

LATE-AQP (Ours) improves long-event recall over uniform and expansion baselines while maintaining comparable duration-weighted precision.

## Revised Claim

Across three held-out segments of `realcartest`, the frozen `Frozen-LATE-AQP-v1` configuration achieves higher macro-averaged long-event recall than both B6 and B7 at 4 of 6 budget points, including B=120 (source: `center10_vlm_oracle_events.csv`).
The average duration-weighted precision drop relative to B7 is at most -0.2 percentage points across budgets (i.e., Ours is at least as precise on average; source: `center10_vlm_oracle_events.csv`).

## Caveats

- The improvement is measured on a single video (`realcartest`) split into non-overlapping windows; generalization to other videos is not established.
- The low-density window (`realcartest_1630_2000`) contains only point-anchor events, so long-event recall cannot be evaluated there.
- All labels come from a single VLM oracle (`center10_vlm_oracle_events.csv`); recall/precision are oracle-relative.
- The repair trace demonstrates the causal mechanism but does not prove that every repair yields a net precision gain.

## What This Does NOT Show

- A formal statistical guarantee (confidence interval, uniform convergence, or certificate).
- Generalization beyond the `realcartest` VLM oracle.
- Optimality of the frozen hyperparameters on other videos or predicates.

## Recommended Follow-up

1. Repeat on a second video (e.g., `Cartest_sim`) with the same frozen config.
2. Add a true low-density long-event segment if one becomes available.
3. Investigate the cases where Ours does not win (see budget curves) to understand failure modes.
