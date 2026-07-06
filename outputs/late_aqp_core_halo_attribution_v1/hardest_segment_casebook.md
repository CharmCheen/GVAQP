# Hardest Segment Casebook — realcartest_0_1570

Analysis at B=120. Events not covered by LATE-AQP-core majority of seeds.

| event_id | type | duration | inside_E0 | hit_B6 | hit_B7 | hit_halo | reason | dist_to_core | dist_to_halo |
|----------|------|----------|-----------|--------|--------|----------|--------|--------------|--------------|
| realcartest_event_0001 | point_anchor | 0.7 | False | False | False | False | upstream_discovery_miss | 0.0 | 0.0 |
| realcartest_event_0002 | point_anchor | 0.2 | False | True | True | False | upstream_discovery_miss | 90.6 | 10.6 |
| realcartest_event_0003 | point_anchor | 0.5 | False | True | True | False | upstream_discovery_miss | 110.8 | 30.8 |
| realcartest_event_0011 | point_anchor | 0.7 | False | True | False | False | upstream_discovery_miss | 59.6 | 9.6 |

## Summary

- upstream_discovery_miss: 4 events

Interpretation:
- `release_too_conservative`: event was found by LATE-AQP's discovery/repair (in halo) but discarded by the strict core release.
- `upstream_discovery_miss`: event was never selected by LATE-AQP's discovery/repair; fixing release alone cannot recover it.
