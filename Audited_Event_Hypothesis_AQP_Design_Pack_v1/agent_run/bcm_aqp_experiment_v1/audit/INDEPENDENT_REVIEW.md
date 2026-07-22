# Independent Adversarial Review

Review date: 2026-07-10 UTC  
Review mode: read-only source/artifact inspection; no VLM or formal experiment.

## Verdict

The independent reviewer concluded that
`ORACLE_PROVENANCE_BLOCKED_REQUIRES_BENCHMARK_V2` is supported.  The decisive
reason is the primary historical mismatch between the cache request
`[3457.866,3462.866]` and frozen-v1 claim `[3457.93,3462.93]`, plus the recovered
frame-index arithmetic/current exact-code replay showing different sampling
phase and RGB contents.

## Findings and disposition

| Severity | Finding | Disposition |
|---|---|---|
| high | `FINAL_DECISION.csv` lacked `unblock_requirement`. | Fixed: required column and exact benchmark-v2 unblocking action added. |
| high | Experiment manifest lacked Git state, reference hash, prior compatibility, command ledger, timestamps, environment, and skip reasons. | Fixed: all mandatory records added; Git state recovered with a temporary nonpersistent safe-directory config. |
| medium | Reproduction did not regenerate unit-346 query usage. | Fixed: `reproduce_unit346_query_usage.py` and its exact command added. |
| medium | Historical RGB identity wording exceeded available generation-time decoder evidence. | Fixed: reports distinguish primary historical interval/index evidence from current OpenCV 4.13 exact-code RGB replay. |
| low/medium | `raw_response_hash` hashed the JSON envelope, not nested model text. | Fixed: nested response text and JSON envelope now have separate hashes/presence/match fields; 347/347 match for both. |

The reviewer independently verified the theory/code semantics, unit-346 usage
counts, authoritative source hashes, file-manifest entries available at review
time, and duration-field root-cause chain.  All reported deficiencies were
addressed before the final completion audit.
