# ANY operator semantics v2

For half-open target interval `B=[start,end)`, raw ANY is `POSITIVE`, `NEGATIVE`
or `UNKNOWN`. Ground truth is positive iff at least one unique canonical anchor
is inside B; support overlap with an anchor outside B is not positive.

Pruning is allowed only for a parsed `NEGATIVE` with `abstain=false`,
`complete_target_audited=true`, complete/non-truncated target context,
high confidence, valid provenance and no parser/runtime error. Every other raw
outcome maps to effective `UNKNOWN` and must split to children or use frozen
10-second unit fallback. UNKNOWN is charged and never pruned.

The synthetic feasible-region derivation freezes minimum effective sensitivity
1.00, minimum effective specificity 0.99, maximum effective false negatives 0,
and maximum UNKNOWN rate 0 for a formal ANY GO. These values are not weakened
to fit the physical call budget.
