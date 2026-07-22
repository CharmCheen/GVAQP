# Research state

## Objective

Measure whether physical multi-resolution ANY/COUNT queries are accurate and
cheap enough to preserve the conditional C0 acceleration ceiling.

## Established findings

- Exact C0 cost semantics and thresholds are reproducible.
- Physical accuracy thresholds are absent from all governing C0 sources.
- An A100 and the exact strict 32B VLM are available, so compute is not the
  blocker.
- No new physical call was spent and no prompt/sample was exposed to results.

## Active hypotheses

- Real interval cost may be dominated by fixed preprocessing/model overhead.
- ANY false negatives or COUNT undercount may invalidate hierarchical pruning.

Neither hypothesis was tested because a compliant decision rule is missing.

## Decision and next action

`INTERVAL_OPERATOR_CONTRACT_BLOCKED`. Preregister the missing numerical accuracy
and abstention gates before constructing the physical matrix or making call 1.
