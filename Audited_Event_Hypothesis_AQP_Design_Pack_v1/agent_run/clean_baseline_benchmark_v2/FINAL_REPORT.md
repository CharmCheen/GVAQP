# Clean Baseline Benchmark v2 — Provenance-Blocked Final Report

## Final decision

`BENCHMARK_V2_INCOMPLETE_NOT_READY_FOR_BCM`.

The completed computations (one fresh unit-346 call, 1,476 clean runs, metrics and replay audits) remain valid experimental artifacts, but the benchmark cannot be frozen under the strict cache rule. Generation-time model/processor/video-processor/package/full-generation hashes are unresolved for 346 reused legacy responses; strict cache-identity equivalence is unproven.

Resolution requires requerying units 0–345 under the frozen v2 configuration (347 total physical calls), or an explicit protocol amendment accepting lineage-equivalent legacy cache reuse. BCM was not implemented or run.

## Superseded pre-review report

# Clean Baseline Benchmark v2 Final Report

## Strongest supported conclusion

`BENCHMARK_V2_FROZEN_READY_FOR_BCM`. Benchmark `cbbv2_79b484f79b5c4d5edc45` is a content-bound remediation of parent `cbbv1_c2e246d1504d9d8a80b2`. It uses MP4 format duration 3462.930499 s, 347 units, one new physical VLM call for unit 346, and 346 exactly frame/content-equivalent reused raw responses.

## Decisive evidence

- Unit 346 changed from stale interval `[3457.866, 3462.866]` / 11 frames to authoritative `[3457.93, 3462.93]` / 10 frames.
- Raw response changed (`7aaca546…6021c6` -> `3d1d148d…05c29`), while parsed label remained `negative` and boundaries remained null.
- The event reference was reconstructed from all v2 observations; all 27 semantic rows are unchanged.
- All 1,464 baseline and 12 current-method runs were regenerated from empty state; expected/missing/unexpected/duplicate mismatches are zero.
- Completion audit PASS=True; compatibility=True; logical calls=64614; physical oracle-build calls=1.

## Results

- Best native baseline: `B5_ARC_native/arc_refinement_th0.4_native` AUC=0.384577.
- Best controlled baseline: `B1_top_proxy/top_proxy_controlled_bridge_safe` AUC=0.343979.
- Current M1 K3 bridge-safe AUC=0.377194.

## Competing explanation and limitation

The unchanged official results are explained by the unchanged parsed unit-346 outcome, not by result reuse; v2 acquisitions were rerun and unit-346 query impacts are enumerated in `analysis/unit346_query_impact.csv`. The reference remains VLM-defined pseudo-oracle on one video, not human ground truth. The frozen processor emits its historical missing-video-metadata fps warning for explicitly pre-sampled frames; changing that behavior would change oracle semantics and was therefore not done.

## Decision

The benchmark is ready for a separate BCM task. BCM implementation, ceilings, canonical runs, and ablations were not performed here.
