# Computation optimization

IC1 uses a shared maximal posterior-root schedule, so lower budgets consume exact prefixes. It calculates repeated-trajectory paired sufficient statistics algebraically and validates them against explicit arrays. Exact evaluator caching is restricted to history, remaining horizon, safe set, and kernel identity. Deterministic shards partition canonical hashes and do not affect output identity order.
