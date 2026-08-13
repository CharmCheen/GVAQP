# Frozen temporal-region definition — P1-B v1.2

`number_of_temporal_regions_touched` is the number of maximal connected components of queried candidate units on the released V3 candidate lattice. It is not a count of fixed macro-windows.

- Atomic temporal-region width: 10.0 seconds.
- Origin: video time 0.0 seconds.
- Boundary: half-open `[10k,10(k+1))`; the final partial cell ends at video duration.
- Unit assignment: each released unit has frozen `candidate_order=k` and belongs to exactly atomic cell k.
- Partial boundary: the last shortened unit remains one atomic cell.
- Adjacent queried units: consecutive candidate orders belong to one maximal touched region; a missing order splits regions.
- One queried unit cannot touch multiple geometry regions.
- Duplicates, if present, are removed before component counting.
- Implementation: `temporal_region_count` in `src/garc_eval/p1b_protocol_v1_2.py`.

All 198 memberships and orientations reproduce exactly under this definition. Region size/alignment cannot change after annotation begins.
