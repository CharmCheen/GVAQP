# Visible-history semantics

An evaluator-private world contains workload cell, all region candidates,
grouping labels, Oracle/materialization outcomes, integer action durations and
the execution random tape. Given a world and actions, transitions are
deterministic.

The policy history is `(q, T, a0, o1, ...)`. SCAN observations contain region,
realized tick duration and newly emitted visible candidates; CONFIRM observations
contain selected candidate, duration, visible outcome and durable commit token.
No history object contains a seed, RNG state, latent event id, world id, future
candidate count, future duration, or grouping-correctness label. Aggregated
state is replayed from this history.
