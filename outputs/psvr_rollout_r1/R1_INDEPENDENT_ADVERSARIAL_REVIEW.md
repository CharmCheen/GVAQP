# Independent adversarial review — R1 blocked-state assessment

Scope: read-only review of frozen D3/D4 assets and the current toy source. No
runner, policy comparison, confirmatory seed generation, or held-out seed read
was performed by this review.

## Finding

`BLOCKING_DEFECT = SCIENTIFIC_SPEC_CONFLICT`.

The frozen D4 requires a visible-history conditional expectation for M1, with
each candidate followed by the same pi0 continuation to the full horizon. D3
defines a complete seeded latent episode and evaluator truth, but not a
visible-history observation likelihood, posterior state, conditional sampler,
or visibility classification for seed/split/RNG state. The bound preregistration
and implementation specification identify the same missing kernel.

The proposed amendment itself says these choices are not uniquely recoverable
and requires explicit authorization before D3/D4 are reissued and rehashed.
Implementing a sampler now would choose a probability model and information
structure. A realized-episode clone is prohibited leakage/C0 collapse; exposing
the seed or full parameters also changes the information structure.

## Decision

Do not apply the otherwise direct `VisibleState.episode_id` repair in isolation;
it cannot establish a conforming R1 experiment while the M1 semantics are
undefined. Do not create split loaders, a one-shot runner, an R1 preregistration,
or a code freeze that would imply the missing scientific decision was resolved.

Required next authority: a result-blind D3/D4 consistency amendment freezing a
Bayesian visible-history kernel, observation likelihood/posterior, independent
future response-tape streams, ordered RNG semantics, and visibility boundary;
then independent conformance verification.
