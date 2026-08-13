# P2 baseline definitions

- **UniformTemporal**: deterministic nested dyadic temporal ordering, no proxy.
- **StaticProxyRank**: descending frozen proxy score.
- **CoverageFirst**: deterministic farthest-first temporal coverage, no proxy.
- **Proxy+TemporalCoverage**: score `(1-lambda)*normalized_proxy + lambda*minimum normalized temporal distance to already selected timestamps`; fixed λ={0.25,0.50,0.75}, all reported, with λ=0.50 canonical.
- **Offline oracle diagnostic**: full-label/full-reference greedy coverage upper diagnostic only; never a legal policy or winner.

All legal methods are nested query-count prefixes and read no semantic outcome during ordering.
