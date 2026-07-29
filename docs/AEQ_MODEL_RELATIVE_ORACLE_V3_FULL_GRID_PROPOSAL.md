# AEQ Model-Relative Oracle V3 Full-Grid Proposal

Status:
`PROPOSAL_REVISION_2_AWAITING_INDEPENDENT_REREVIEW_NOT_PREREGISTERED_NOT_AUTHORIZED`

The 11-call V3 preflight passed. This document proposes—but does not authorize
or execute—the complete 1,475-unit model-relative labeling run.

## Exact proposed workload

| Video | Calls | GPU pair | Estimated wall time | Estimated A100 GPU-hours |
|---|---:|---|---:|---:|
| DALI | 567 | `(1,2)` | 3.093 h | 6.186 |
| HANGZHOU | 561 | `(3,5)` | 3.061 h | 6.121 |
| WUHAN | 347 | `(6,7)` | 1.895 h | 3.790 |
| Total | 1,475 | 6 A100s | about 3.1 h parallel | 16.097 |

The estimate uses the ten physical 2-fps V3 calls: 18.0865 seconds mean
inference and 19.6077 seconds mean total call time excluding model load. Three
observed loads totaled 53.4468 seconds. A 19.4 A100 GPU-hour planning envelope
is the conservative upward rounding of the direct 20% result, 19.3165. It
grants no retry, reload, or additional-call authority.

The frozen unit grid contains 567 DALI, 561 HANGZHOU, and 347 WUHAN units. The
1,472 full units use endpoint-inclusive 2-fps sampling. The final units are
5.535, 0.566, and 2.930 seconds; the current exact sampler rejects these
non-half-second durations. Before sealing, implement and test this explicit
rule only for truncated final units: take exact targets `k/2` that do not exceed
the real duration, never synthesize/repeat frames or round beyond video end,
and retain the true unit end only for K3 boundaries. This yields proposed final
counts 12/2/6 and an estimated 30,932 total frame occurrences. The exact decoded
manifest—not this arithmetic estimate—must become the execution authority.

## Resume and failure semantics

- Retry budget remains zero.
- The plan allows exactly three checkpoint loads—one uninterrupted process per
  video shard—and zero reloads. There is no post-load process restart or resume
  under the original approval.
- Failure semantics are global fail-stop: if any shard records a generation
  failure, uncertain interruption, post-load process fault, cost-shield breach,
  or integrity mismatch, all shards stop issuing new `INFERENCE_STARTED`
  events. Calls already started may finish and are preserved.
- A later continuation requires a new seal and approval. It may reuse
  authenticated accepted records and propose calls with no durable start; an
  uncertain started call is not eligible unless the new approval explicitly
  authorizes that retry.
- A hash-chained load/call cost ledger and pre-start reservation shield must
  forbid any start whose sealed reservation exceeds the 19.4-hour ceiling.
- `unknown` and `parse_failure` are preserved without relabeling or
  regeneration. Unknown may bridge only under the frozen one-gap rule;
  parse failure is an indeterminate K3 barrier.

## Outputs and K3 schedule

Raw, parsed, and attempt-ledger outputs are sharded by video. Only after all
1,475 call slots have authenticated accepted raw/parse outcomes, with no
missing, generation-failed, or uncertain unit, K3 orders units by video/start,
materializes each video independently with parameter hash `7906ab2d…`, checks
reverse-order equality, and emits:

```text
full_grid/unit_labels.parquet
full_grid/oracle_coverage_report.json
full_grid/k3_operational_event_relation.parquet
```

VLM evidence timing never enters event boundaries.

The three files above are atomically published only on a complete finalizer
decision. An interrupted or failed run may write explicitly `INCOMPLETE`
diagnostics under `full_grid/incomplete_diagnostics/`, but it publishes no
authoritative unit-label table or EventRelation and cannot be used downstream.

## Integrity and label hiding

Before execution, a new package must bind the exact 1,475-call and decoded-frame
manifests, all source/model/protocol hashes, three session-bound ledgers, raw and
parsed paths, analyzer/finalizer, expected 5,900 success events, the global
fail-stop coordinator, exactly-three-load/cost ledger, atomic complete/
incomplete publication mapping, and zero-retry policy. It requires a new
execution seal, independent GO, and exact user approval.

The truncated-final-unit sampler and its no-overrun/count tests are a hard
prerequisite. Until implemented and independently reviewed, the proposal is not
ready for preregistration or a compute request.

The current `ModelRelativeLabelStore.controller_view()` is not a sufficient
security boundary: it returns labels for caller-supplied IDs. The exhaustive
store must instead be evaluator/reference-only. A separate capability may
reveal a label to controller state only after an authenticated durable VERIFY
completion for that exact unit; arbitrary ID requests must fail closed. With
public observations and causally revealed VERIFY history fixed, permuting all
unrevealed/future oracle labels and reference events must leave both controller
state and its next action unchanged. The full-grid run itself instantiates no
controller.

## Stop boundary

This revised proposal grants no authority to freeze expanded inputs, load the model,
execute any of the 1,475 calls, retry a failure, or begin YOLO/replay/headroom/
controller work. The next permissible action is independent review of this
proposal, followed by a user decision on whether to prepare an exact full-grid
preregistration and seal.
