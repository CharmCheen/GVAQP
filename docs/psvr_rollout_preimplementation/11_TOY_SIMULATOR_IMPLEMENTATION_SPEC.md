# Toy simulator implementation specification

The prototype separates immutable latent Episode/Event/Witness objects from a
narrow VisibleState; implements atomic SCAN/CONFIRM/STOP transitions, exact
D1 trace recomputation, SplitMix64, grouping, shielded pi0, and frozen simple
policy interfaces.

It is deliberately not frozen. Four decision-critical inputs are missing or
contradictory in the authoritative D3/D4 assets:

1. `ratio_draw` is defined but absent from the ordered RNG draw schedule.
2. grouping is scheduled after all future witnesses exist, while SCAN must
   update a non-anticipatory frontier incrementally.
3. realized costs are lazy ledger-order draws, making a fixed seed's potential
   action costs policy-dependent without a cross-policy coupling rule.
4. M1 requires an exact visible-history conditional expectation, but no belief
   state, observation likelihood, or conditional transition sampler is frozen.

Using the realized latent episode for M1 would make it clairvoyant and collapse
the distinction from C0. The evaluator therefore fails closed with
`BLOCKED_INTERNAL_INCONSISTENCY`.

