# Why exact unit audit approaches dense scan

## Setup

After discovery, let `N` candidate anchor units remain and let `R` of them be
residual canonical anchors.  A fixed audit samples `n` units uniformly without
replacement.  If it sees `X=x`, Gate B inverts the hypergeometric lower tail to
obtain an exact one-sided upper confidence bound `U_R(x)`.

If `D` events are already certified and the audit has not added events, an 80%
recall lower bound requires

```text
U_R <= floor(D * (1 - 0.8) / 0.8) = floor(D / 4).
```

Thus even `D=20` permits at most five residual events in the upper bound.

## Zero-hit necessary audit size

Suppose the audit observes zero anchors.  To rule out `u+1` residual anchors
at failure probability `delta`, it is necessary and sufficient for the exact
lower-tail test that

```text
C(N-u-1, n) / C(N, n) < delta.
```

The left side is the probability of missing all `u+1` anchors when sampling
`n` units.  For sparse events and small allowed `u`, it decreases slowly;
therefore a distribution-free certificate must inspect a large fraction of
the finite population unless discovery has already certified nearly all
events.

## What this does and does not prove

This identity explains the Gate B behavior and is exact for the registered
binary-anchor/SRSWOR design.  It is not a universal lower bound for every
adaptive audit, prior-dependent method, interval operator, or approximate
oracle.  Cluster/group queries escape the premise because one response can
exclude multiple anchor units simultaneously.

The scientific implication is conditional:

> If attainable unit ranking cannot discover nearly all events, changing the
> physical query operator is more promising than adding another ranking
> heuristic.

