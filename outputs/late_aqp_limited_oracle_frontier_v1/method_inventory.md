# Method Inventory

| Method | Uses prior | Uses repair | Uses Core/Halo | oracle_adapter calls | Guard in budget | strict_replay | posthoc_eval | Label leakage risk |
|--------|------------|-------------|----------------|----------------------|-----------------|---------------|--------------|---------------------|
| B6 | No | No | No | selected bins | N/A | No | Yes | Uses event_id per chunk |
| B7 | No | No | No | selected bins | N/A | No | Yes | Uses event_id per chunk |
| B6-core | No | No | Yes | selected bins + guards | Yes | No | Yes | Inherited from B6 |
| B7-core | No | No | Yes | selected bins + guards | Yes | No | Yes | Inherited from B7 |
| LATE-AQP-core | Yes | Yes | Yes | audit + discovery + repair + guard | Yes | Yes | No | Low; selection uses labels only |
