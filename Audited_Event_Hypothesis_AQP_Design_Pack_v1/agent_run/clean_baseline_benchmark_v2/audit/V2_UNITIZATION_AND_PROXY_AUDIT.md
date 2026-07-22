# Benchmark v2 Unitization and Public-Proxy Audit

Status: `PASS_RETAIN_V1_PUBLIC_INPUTS`

## Authoritative convention

- Duration source: MP4 `format.duration` from ffprobe.
- Exact source duration: `3462.930499` seconds.
- Serialized unit-grid duration: `3462.930` seconds.
- Final unit: `unit_id=346`, interval `[3457.930,3462.930]`.
- Unit count: 347.

## Evidence

The retained clean precompute metadata at
`benchmark/proxy_precompute/full/video_metadata.json` records
`duration_seconds=3462.930499`.  Its anchor builder takes that format duration,
clips the final center-10 anchor to it, and emits the exact final interval above.

The v1 frozen unit table has physical SHA256
`50e8c454d8de02c89c2ffd6ff9fada134d9c566366e3132ad22518ebe495faa4`.
The retained center-10 anchor grid has SHA256
`8d652d0aaa5659466af6b0c8baf755e384e70b28e43081de69893460a9bfc716`.
The copy retained in v2 has the same hash.

Phase-0 exact-code frame replay found identical frozen/cache frame indices and
RGB contents for units 0–345 and isolated the sole mismatch to unit 346.  Thus
the public unit/proxy convention itself is already the required MP4
format-duration convention; changing it would reintroduce inconsistency.

## Decision

Retain all 347 public units and compatible cheap proxies.  Do not recompute or
change public inputs.  Replace only the oracle input/response for unit 346.

No oracle labels or evaluator-only fields are present in the retained
center-10 grid or proxy features.  The final v2 planner tables are rebuilt with
v2 benchmark lineage and separately checked for forbidden fields before
baseline execution.

## Source lineage

- Producer:
  `outputs/video_feature_precompute_v1/scripts/precompute_video_features.py`
- Producer SHA256:
  `0a878d23c5f0500160e098a517142e38ab67f83c0fff25a1c1667094a73ca69e`
- Video SHA256:
  `bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610`
- Phase-0 comparison:
  `../bcm_aqp_experiment_v1/audit/oracle_cache_interval_audit.csv`

This audit authorizes retention of public inputs only.  It does not authorize
reuse of v1 selections, traces, segments, matches, metrics, rankings, or
aggregates.
