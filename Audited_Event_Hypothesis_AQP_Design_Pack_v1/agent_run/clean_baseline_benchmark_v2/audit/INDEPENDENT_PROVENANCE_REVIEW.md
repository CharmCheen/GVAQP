# Independent Provenance Review

Status: **BLOCKING**

The independent reviewer confirmed the unit-346 repair, run completion, metric
recomputation, and the corrected self-excluding file manifest. It found one
decision-critical provenance defect:

- Phase 0 established that the legacy responses did not preserve complete
  generation-time model-weight, package, processor, video-processor, and full
  generation-configuration hashes.
- The v2 builder computed hashes from the current checkpoint/configuration and
  stamped them into all 347 identities.
- For units 0--345, reuse was actually gated by frame-index/content equivalence,
  current path/config lineage, and the legacy raw-envelope hash. It did not
  cryptographically establish that every current configuration hash equalled
  its generation-time value.

Therefore the 346 reused entries do not satisfy the strict “all fields match”
reuse rule as written. Current path/config lineage is supporting evidence, not
an observed historical content identity.

Required resolution is one of:

1. requery units 0--345 under the frozen v2 configuration, preserving the
   current unit-346 call and raising total physical VLM calls to 347; or
2. obtain an explicit protocol amendment accepting lineage-equivalent legacy
   responses when generation-time hashes are unavailable.

The reviewer also noted that the initial semantic snapshot named the whole
`BENCHMARK_MANIFEST.json` as immutable although the specification permits that
manifest to receive additive execution results. The benchmark ID still
recomputes from its unchanged `compatibility` payload, but the snapshot wording
must be corrected in any completed re-freeze to protect the immutable
compatibility payload rather than the mutable result envelope.

Until resolved, benchmark v2 is not frozen and is not ready for BCM.
