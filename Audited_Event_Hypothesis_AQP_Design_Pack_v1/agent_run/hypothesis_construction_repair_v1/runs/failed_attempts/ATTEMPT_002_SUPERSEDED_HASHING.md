# Superseded Attempt 002 — Counterfactual Hashing

- Completed manifests before interruption: H1 B=5/10/20/50/80/100 and H2 B=5/10/20/50.
- Reason for interruption: profiling showed that full canonical hashes were computed for every ephemeral positive/negative branch although no simulated hash is persisted or used as a cache key.
- Repair: hash committed states only; simulated state contents remain immutable and unchanged.
- Equivalence check: independently rerun H2 B=10 produced identical selected units, action types, and scores at absolute tolerance `1e-14` against the preserved partial trace.
- Action: restart all 24 runs from empty histories and overwrite canonical formal paths; this note preserves the superseded attempt's provenance.
