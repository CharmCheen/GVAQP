# Bandit Accounting Integrity Check

## Code-level finding

`discovery_d3_chunk_bandit` in `run_event_diverse_discovery.py` initializes `sampled`, `n_c`, and `N1_c` from scratch and **does not use the `queried` argument**.

Consequences:

1. **Repair/audit calls are not reflected in the bandit state.** The bandit thinks these chunks have never been sampled, so its posterior (theta) is wrong when it later makes discovery decisions.
2. **Discovery may re-query bins already queried by audit/repair.** Because `queried` is ignored, the same bin can be counted multiple times against the budget while providing no new information.
3. **The diagnostic `discovery_calls` count overstates real exploration.** Some discovery 'calls' are duplicates of earlier audit/repair/guard calls.

## Quantification from logged trials

- D3-core trials: total duplicate calls = 1095, duplicate discovery calls = 981
- D3-norepair trials: total duplicate calls = 244, duplicate discovery calls = 191
- D3-core mean duplicate calls per trial = 24.33
- D3-norepair mean duplicate calls per trial = 5.42

## Verdict

**Accounting integrity is violated in D3-core.** The bug is that the chunk-bandit discovery function ignores the `queried` set. This is a low-level implementation error, not a design flaw in the repair mechanism itself. It should be fixed before drawing conclusions about repair's true marginal value.
