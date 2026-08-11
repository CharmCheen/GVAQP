# Upstream Oracle V3 failure audit

Observed outcome: `STOPPED / cost_envelope_exceeded`.

The sealed staged full-grid completed 136 DALI units. `DALI_u0136` was reserved
but did not receive a terminal completion record. The coordinator recorded a
23.754265-second elapsed call against the sealed 23.579961-second per-call
limit, exceeding it by 0.174304 seconds. It appended `GLOBAL_FAIL_STOP`, wrote
`GLOBAL_FAIL_STOP_INTENT.json`, terminated the DALI worker, and never activated
the HANGZHOU or WUHAN workers. No full-grid process remains.

This was a correct fail-closed safety action and negative evidence about the
cost contract: the hard reservation did not cover the observed tail. It is not
evidence that the global 19.4 A100-hour authorization was consumed; the
trigger was the sealed per-call bound. Partial actual GPU time was about
5,142.25 GPU-seconds when state stopped, but that incomplete value is not a new
safety bound.

Label-blind profiling of the 136 completed call records gives mean 18.782775 s,
p50 18.761514 s, p90 20.711090 s, p95 22.030782 s, p99 22.723631 s, and maximum
23.304528 s. The failed in-flight call crossed the limit at 23.754265 s. Thus
the seal was not merely below the prior completed maximum; it lacked support
for a later unseen tail. These same-run observations may diagnose the failure
but cannot calibrate and validate a replacement bound on the same sample.

The frozen decision mapping ranks a cost/runtime failure as
`FULL_GRID_ABORTED_RUNTIME`, above the generic incomplete-evidence mapping.
The formal finalizer has not published an authoritative decision artifact, so
this audit reports the deterministic mapping rather than impersonating the
finalizer. In either case, the failure policy forbids a formal unit-label table,
K3 relation, reference release, downstream access, retry, or continuation
under the same approval. The 136 partial records were not inspected.

Scientific consequence: V3 SCAN coverage, V3 multi-fidelity VERIFY, physical
controller headroom, closed loop, and native/controlled ARC comparisons cannot
be run. The minimum recovery is not threshold tuning downstream; it is an
independently reviewed complete-path cost diagnosis followed by a new seal and
explicit new execution/retry authority, with the existing failed attempt
preserved.

A subsequent uncommitted recovery draft was inspected but is not ready to
reseal. Its new runner constants are not propagated into the dry-run,
analyzer/finalizer or current tests; it does not bind cumulative authorization
or a new experiment ID; and its re-tokenized response-length calibration needs
measurement and post-outcome-adaptation review. See
`RECOVERY_DRAFT_AUDIT.md`.
