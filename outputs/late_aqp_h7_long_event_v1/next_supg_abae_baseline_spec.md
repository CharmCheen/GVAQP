# Next SUPG/ABae Baseline Specification

This document specifies the SUPG-style and ABae-style baselines to be implemented
in a future round. They are **not** implemented here.

## SUPG-style defensive sampling baseline

### Input
- Same 10s atomic grid with prior scores (`atomic_grid_10s.csv`).
- Same reference events and budgets.

### Method
1. Rank bins by `prior_score_max`.
2. With probability `p`, sample from the prior-biased distribution
   (proportional to prior score).
3. With probability `1-p`, sample uniformly at random (defensive sampling).
4. Continue until budget B is exhausted.
5. Return all sampled positive bins as discovered events.

### Parameters
- `p` ∈ {0.5, 0.7, 0.9}
- Report results for each p; do not select p based on test performance.

### Outputs
- event-level recall
- selected precision
- discovered positive temporal mass
- false-positive duration

### Budget alignment
- Same as B6/B7/Ours: exactly B oracle calls.

## ABae-style stratified estimator baseline

### Input
- Same 10s atomic grid with prior scores.

### Method
1. Divide bins into prior-score strata (e.g., quartiles).
2. Allocate a pilot sample across strata proportionally to stratum size.
3. Estimate stratum positive rates.
4. Allocate remaining budget to strata with highest estimated positive rate.
5. Estimate total positive temporal mass from the stratified sample.

### Parameters
- Number of strata: {4, 5}
- Pilot fraction: {0.2, 0.3}

### Outputs
- estimated positive mass
- mass-estimation error vs reference
- discovered events
- event-level recall

### Notes
- ABae does **not** perform temporal expansion or repair.
- It is included to test whether simple stratified estimation explains Ours-full's
  mass-recovery performance.

## H3/H4 status

- H3 (SUPG-style) and H4 (ABae-style) remain **not verified** until these baselines
  are run.
- Do not claim Ours defeats them in the current report.
