# Selected-Frontier Input Unblock Protocol V1

Status: `FROZEN_NON_SEMANTIC_INPUT_PIPELINE`

This protocol does not modify the frozen selected-Frontier calibration
contract or any research gate. It may add exactly three new independent,
complete driving-video sources to the one preliminary source (`杭州.mp4`). It
must not read semantic references, event counts, candidate outputs, or
selected-Frontier outcomes, and it must not train C0-C4.

## Discovery and immutable ordering

New files are accepted only from
`data/realcam/selected_frontier_calibration_inputs/`. HDD/HSD files, if
legitimately obtained, may be placed below `hdd/` or `hsd/` within that root.
Every media byte identity is appended to
`candidate_registration_ledger.jsonl` before validation. Its immutable order
is `(sidecar registration_utc, filename, sha256)`; an absent or invalid
registration timestamp is still registered but fails provenance. A changed
file is a new byte identity and never overwrites the prior record.

The first three candidates in frozen order that pass every gate occupy slots
`ADDITIONAL_1..3`. Later passing files are reserves. A slot may advance to the
next candidate only when its earlier candidate has a recorded technical or
provenance failure. Semantic density, event count, calibration behavior, and
selected-Frontier outcome are forbidden replacement reasons.

## Per-asset gates

Every candidate must pass all of:

1. container duration at least 1,200 seconds;
2. complete sequential video decode with zero decoder errors;
3. continuous packet timestamps, monotonic presentation time, no unexplained
   gap over `max(2 seconds, 10 × median positive packet step)`, and decoded
   duration consistent with the container;
4. twelve deterministic random seeks derived from the file SHA-256;
5. unique, nonempty `capture_session_id`;
6. a SHA-256-bound provenance declaration whose declared hash equals the file;
7. original continuous capture, no known parent/derivation, no event-centered
   collection, and no use of target-event information for selection;
8. no exact duplicate, shared capture session, parent relation, or detected
   overlapping content with V0, V1, `杭州.mp4`, or another candidate.

Content independence uses exact hashes plus deterministic time-distributed
frame perceptual hashes. A detected aligned or offset-consistent overlap is a
failure. Absence of a detected match is only supporting evidence; provenance
is still required.

## Permanent records and stopping

All failed checks are appended to `eligibility_failure_ledger.jsonl`; reruns
may add evidence but never delete a failure. The seven requested reports are
regenerated from the immutable ledgers and current technical evidence.

`INPUT_GATE=PASS` only when exactly three additional candidates occupy the
three slots, producing four qualifying new independent sources in total.
Otherwise:

```text
INPUT_GATE = BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS
SELECTED_FRONTIER_DATASET = NOT_BUILT
CALIBRATION_MODELS = NOT_RUN
```

