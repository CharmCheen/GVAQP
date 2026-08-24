# ExSample-EndToEnd-Adapted Killer Protocol

## Purpose

This is the decisive CPU-only baseline test for the remaining DATB-SV algorithmic
claim. It adapts ExSample's published Gamma Thompson chunk sampler to the shared
causal SCAN/VERIFY executor. It is not claimed to reproduce ExSample's original
GPU implementation.

## Frozen adaptation

- Each temporal chunk is an arm.
- The posterior sample is `Gamma(N_new + 0.1, rate=n + 1)` as in ExSample.
- A selected chunk chooses an unscanned cell by maximin/random+ temporal spacing.
- The selected cell must execute shared SCAN and then shared VERIFY.
- Posterior reward is the count of newly committed distinct events after VERIFY.
- No proxy score, future label, exhaustive reference, or trained model enters the
  chunk choice.
- Primary baseline is the predeclared envelope over chunk counts `{3, 6, 12}`.

## Design

Use the V3 generator and deterministic holdout seeds. Unlike the fractional H2
screen, run all three deadline levels for each of the 324 `A x B x C x D x E`
workloads. This yields 972 workload-deadline points per seed.

## Frozen SESOI

DATB passes this synthetic killer only if:

1. median relative anytime-AUC gain over the ExSample envelope is at least 5%;
2. more than half of workload-seed groups have at least one additional committed
   event at two adjacent deadlines;
3. mean DATB-minus-ExSample AUC is non-negative at cost ratio 30.

Failure retires the current DATB algorithmic contribution. Passing would still be
only synthetic qualification and would not bypass natural corpus, C3 cost, or
human MEC gates.

Primary source: https://arxiv.org/abs/2005.09141

