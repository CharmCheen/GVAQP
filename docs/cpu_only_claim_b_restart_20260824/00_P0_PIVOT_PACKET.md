# P0 Claim-B CPU-only pivot packet

## Decision

Retire both current DATB identities. Defer the human route by user scope.
Restart Claim B at substrate qualification, not policy optimization.

The six existing T2 video-query cells are consumed for selection. They may
support read-only diagnosis but cannot tune or confirm a replacement policy.

## Dominant uncertainty

Can the executor represent a real causal frontier in which query-conditioned
SCAN creates zero to many fallible candidates, candidate VERIFY is legal only
after exposure, and DirectVerify remains a distinct action under one clock and
one evaluator?

## Competing explanations

- H1: SCAN creates useful capabilities that DirectVerify cannot cheaply replace.
- H0: DirectVerify or a simple fixed schedule captures all deployable value.
- Contract-null: apparent gain comes from forced fallback candidates, reference
  leakage, unequal clocks, or evaluator differences.

## Scope

This package executes only the CPU contract-null falsification. It makes no
claim about natural opportunity, prevalence, physical cost, human utility,
observability, or deployable policy improvement.

## Stop rule

Any failed contract invariant makes B0 `FAIL` and blocks fresh inference. A B0
`PASS` qualifies infrastructure only and still requires explicit authorization
for fresh or physical sensing.
