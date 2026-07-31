# Independent Adversarial Review — Fresh Call-Reservation V2 Full-Grid Candidate

Decision: `GO_TO_REQUEST_FULL_GRID_APPROVAL`

- Source commit: `11803cff8968dbf5f52f15275a0f96f6b3d1e2b9`
- Exact execution seal SHA-256: `2189d821eba4b0e0022da4f0a1113e51ed2128351def12c4e310ffd36569c9ee`
- Exact review bundle SHA-256: `f69eb4c7bef9aef89653875909d2003c92b009ba6c0e6e6cedbcbc80771e7983`

The prior failed execution is authenticated revision evidence only. All 147
nested bindings—11 control/package artifacts and 136 raw outputs—match their
frozen byte sizes and SHA-256 hashes. Its hash-chained ledgers contain exactly
137 call reservations, 136 completions, one model load, and one global
fail-stop. All 136 preserved raw outputs independently reparse as strict `ok`;
their unit IDs exactly match the completed-call set. `DALI_u0136` is the sole
uncertain attempted unit and has no raw output. No formal unit-label table, K3
reference, or release pointer was produced.

The revised reservation derivation is reproducible from those physical
records. Frozen-processor token reconstruction gives 76–143 decoded tokens
across 136 observations. All OLS, residual, overhead, and Bonferroni values
recompute exactly. The 1,475-comparison familywise total upper bound is
32.263113577202205 seconds; the sealed 35-second reservation leaves
2.736886422797795 seconds of margin. The full reservation arithmetic is
28.74388888888889 A100 GPU-hours within the 29.0 fresh-run envelope. The prior
conservative usage upper bound is 1.4443878765527778 A100 GPU-hours, making the
prior-plus-fresh authorized upper bound 30.444387876552778, below the separately
authorized 64.0 A100 GPU-hours. The derivation contains runtime and token-count
fields only—no labels, confidence, evidence, parsed content, or raw text.

The unit, frame, processed-input, worker-schedule, tail-processor, and
tail-unit artifacts are byte-identical to the previously accepted candidate.
They preserve 1,475 unique units, 30,932 frame occurrences, disjoint
567/561/347 worker shards, frozen GPU pairs `(2,6)`, `(3,5)`, and `(1,7)`,
and legal 12/2/6-frame truncated tails without padding or duplication.

Seal, bundle, preregistration, runner, supervisor, analyzer, and finalizer
bindings validate against the exact source commit. Analyzer, finalizer, and
dry-run paths all use the revised 29.0 A100 GPU-hour envelope. The sealed dry
audit records exactly 1,475 mock calls, three mock model loads, all 11 fault
injections passing, deterministic K3 output, and zero formal publication. The
sealed full test audit records 153 passed and zero failed; an independent
focused rerun of 55 manifest, control, supervisor, publication, hiding,
sampling, decision, and determinism tests also passed.

The old compute approval is rejected by the revised validator. A new approval
must bind this exact seal, review bundle, final package manifest, 1,475 calls,
29.0 A100 GPU-hour envelope, fresh execution root, three loads, zero reloads,
zero retries within the fresh seal, deliberate re-execution from unit zero,
and no reuse of prior labels. Any changed binding or pre-existing execution
root fails closed.

At review time the fresh execution root, compute-approval artifact, model
process, formal raw output, and formal reference artifacts were absent. The
35-second bound remains a prospective fail-stop reservation rather than a
guarantee of individual latency; any exceedance makes the run incomplete and
cannot authorize partial publication.

This decision authorizes only requesting explicit approval for the exact fresh
full-grid execution. It does not authorize execution itself, downstream work,
representative adequacy claims, human-semantic accuracy claims, or controller
claims.
