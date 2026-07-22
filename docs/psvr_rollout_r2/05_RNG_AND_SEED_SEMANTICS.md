# RNG and seed semantics

R2 freezes `FIXTURE_RNG`, `DEVELOPMENT_EXECUTION_RNG`,
`DEVELOPMENT_PLANNING_RNG`, `CONFIRMATORY_EXECUTION_RNG`, and
`CONFIRMATORY_PLANNING_RNG`. Each stream is HKDF-SHA256 derived and then uses
SplitMix64; no global mutable RNG exists. Seeds, state and tape position are
evaluator-private. Exact R2 M1 has no sampling RNG dependence; future
approximation keys are namespace, opaque episode id, decision, posterior world,
branch action, transition and variable family.
