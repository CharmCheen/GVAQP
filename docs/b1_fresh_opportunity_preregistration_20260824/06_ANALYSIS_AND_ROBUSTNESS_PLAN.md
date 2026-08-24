# Analysis and robustness plan

## Frozen analysis order

1. Validate video hashes, independence, decoding, interval continuity, and
   absence from the consumed-asset ledger.
2. Validate action/evaluator parity and public-state leakage tests.
3. Open cost calibration only; freeze the three exact deadlines in seconds.
4. Execute and freeze exhaustive evaluation references.
5. Execute every fixed policy with the same executor and failure semantics.
6. Produce all workload cells before computing aggregate gates.
7. Apply the B1a decision tree once. No post-result threshold changes.

## Required robustness checks

- Leave-one-video-out fixed-policy selection.
- Per-query and per-video sign table.
- Exact action-cost ledger including failures and deadline rejections.
- Candidate cap sensitivity at 1 and uncapped as diagnostic ablations; neither
  may replace the primary cap of 2.
- Materializer merge-gap sensitivity at 5 and 15 seconds around primary 10;
  primary gate remains 10 seconds.
- Failed verifier action treated as charged/no-relation (primary) and complete-
  case diagnostic; disagreement in verdict triggers `INCONCLUSIVE`.
- Reference disagreement and zero-reference workload audit.

## Leakage and selection audit

The final package must prove that video ordering, exact queries, policy set,
candidate cap, deadlines construction rule, evaluator, and thresholds were
hashed before semantic outcomes. File timestamps alone are insufficient.

## Result-neutral interpretation

- Different best policy identities do not justify adaptation.
- The decisive quantities are gain over the best global fixed policy,
  held-out selection gain, magnitude, and state prevalence.
- A per-workload envelope is an oracle diagnostic.
- B1a cannot establish B2 merely because headroom exists in hindsight.
