# C0 contract recovery

## Terminal finding

`INTERVAL_OPERATOR_CONTRACT_BLOCKED`.

The exact cached C0 contract is recoverable for operator semantics, cost and
routing geometry:

- intervals are half-open contiguous ranges of frozen 10-second units;
- `ANY_EVENT(B)` means at least one unique canonical anchor in `B`;
- `COUNT_EVENTS(B)` is the number of unique canonical anchors in `B` and exact
  counts conserve across a binary split;
- recall targets are 0.8, 0.9 and 1.0;
- dense cost is 347; a cost cell passes only below 0.7 dense;
- the strong-ceiling criterion requires a fixed-cost fraction no greater than
  0.75; COUNT multipliers are 1.0, 1.25 and 2.0;
- the primary exact ceiling is count-guided, 80% recall, COUNT x1.25.

The physical accuracy decision contract is not recoverable. Neither
`config/gate_c0.json`, `docs/GATE_C0_PROTOCOL.md`,
`docs/INTERVAL_ORACLE_CONTRACT.md`, the C0 report/tables, nor the independent
C0 review specifies a numerical minimum for ANY sensitivity/specificity, a
maximum ANY false-negative count, a minimum COUNT exact accuracy, a maximum
COUNT MAE, or a maximum COUNT undercount rate. The existing contract explicitly
assumes exact operators and identifies real accuracy as unknown.

The new task requires ANY/COUNT to pass “the frozen C0 thresholds” and orders a
hard stop when decision thresholds cannot be recovered. Inventing thresholds
now would change the gate after authorization and make GO/NO-GO dependent on an
unregistered judgment. Therefore sampling, prompt freezing, model loading and
physical inference did not begin.

## Competing explanation considered

The 0.8 recall target is an algorithm-level event-recall target, not an operator
sensitivity threshold. Treating it as one would silently conflate two different
estimands and still leave specificity, false-negative count and COUNT undercount
undefined. The 0.7 and 0.75 thresholds are cost/ceiling thresholds, not accuracy
thresholds.

## Required unblock action

Before any physical call, preregister numerical ANY and COUNT accuracy gates,
including the allowed false-negative and undercount behavior and how abstentions
are scored. This must be an external protocol decision, not selected using this
video's physical interval outputs.
