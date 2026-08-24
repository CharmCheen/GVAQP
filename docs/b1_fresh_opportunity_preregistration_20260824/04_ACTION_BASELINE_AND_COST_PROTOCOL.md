# Action, baseline, and cost protocol

## Bound action substrate

Use `src/garc/endogenous_contract.py`. SCAN is query-conditioned and may emit
0-N raw candidates. The eligible set is deterministically capped at two per
10-second region by descending frozen proxy score, then candidate ID. No
candidate is synthesized when the raw set is empty.

Candidate VERIFY and DirectVerify use the same frozen semantic verifier,
prompt family, decoding parameters, failure handling, and local-relation
schema. DirectVerify receives the whole 10-second region; candidate VERIFY
receives only its exposed interval.

## Primary fixed policies

| ID | Rule |
|---|---|
| `DV_CHRONOLOGICAL` | DirectVerify regions in chronological order. |
| `DV_TEMPORAL_BISECTION` | DirectVerify the frozen temporal-bisection order. |
| `SCAN_THEN_PROXY_GREEDY` | Scan all regions chronologically, then verify exposed candidates by proxy score. |
| `FIXED_1S_1V` | Alternate one chronological SCAN and one highest-score legal candidate VERIFY. |
| `FIXED_1S_3V` | One SCAN followed by up to three legal candidate VERIFY actions. |
| `FIXED_3S_1V` | Three SCAN actions followed by one legal candidate VERIFY. |

No policy may use reference events, future candidates, verifier outputs not yet
returned, per-workload hyperparameters, or a query-specific policy table.
Legacy ExSample may appear only as secondary evidence after an exact common-
executor parity audit. Current DATB is excluded because it is closed.

## Exhaustive hidden reference

DirectVerify all 60 analysis regions for every video-query pair. Materialize
local relations with the same frozen evaluator. This reference is evaluation-
only. Candidate-VERIFY relations absent from the exhaustive reference are
reported as verifier disagreement and receive no primary utility credit.

## Physical cost calibration

Run each action type on the excluded 60-second calibration interval. Persist
only wall-clock duration, failure code, hardware/software fingerprint, and a
hash of discarded semantic output. No semantic content or candidate score from
calibration may be opened before protocol binding.

Let `m_DV` be the pooled median successful DirectVerify duration after the
calibration freeze. Exact deadlines in seconds are frozen once as
`10*m_DV`, `20*m_DV`, and `40*m_DV`. All reported curves use seconds; the
multipliers are deadline-construction rules, not an oracle-call cost metric.

Every policy pays measured SCAN, candidate-VERIFY, DirectVerify, materializer,
and commit time. Failed actions consume their measured duration and return no
relation. Deadline-crossing actions cannot mutate state.
