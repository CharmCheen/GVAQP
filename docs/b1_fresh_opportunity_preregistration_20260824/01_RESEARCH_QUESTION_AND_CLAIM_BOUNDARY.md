# Research question and claim boundary

## Primary question

Across three independent, previously unseen continuous videos and six frozen
open-semantic queries, does a faithful query-conditioned SCAN substrate create
natural candidate exposure that yields higher model-relative anytime event
recall under measured common wall-clock deadlines than DirectVerify-only
schedules?

## Competing hypotheses

- `H_B1A`: at least one fixed scan-enabled policy has a replicated, material
  advantage over the best DirectVerify-only policy.
- `H0_SIMPLE`: DirectVerify-only or another single global fixed policy captures
  essentially all utility.
- `H0_DEGENERATE`: SCAN produces nearly universal exposure, almost no exposure,
  or no meaningful candidate-dependent capability.
- `H0_ORACLE_SELECTION`: apparent opportunity exists only after choosing a
  different policy per workload with outcome knowledge.

## Evidence class

Natural video, fixed-model-relative semantic reference. No human reference is
used. An exhaustive DirectVerify pass with the same frozen verifier defines the
reference event set and is hidden from policies.

Consequently, a PASS supports only a bounded model-relative B1 opportunity. It
cannot establish human utility, semantic truth, real deployment prevalence, or
an adaptive algorithm.
