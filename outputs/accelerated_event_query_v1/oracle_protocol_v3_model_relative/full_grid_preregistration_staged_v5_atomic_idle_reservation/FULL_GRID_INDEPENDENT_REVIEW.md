# Full-Grid V5 Independent Adversarial Review

**Decision: `GO_TO_REQUEST_FULL_GRID_APPROVAL`**

## Reviewed identity

- Source commit: `2934df88e8cc32a39f88da94b5d12bf9d132d40e`
- Execution seal SHA-256: `8f1884ac84609aab86e726c5c2caf2c4c2739329fed89f7f0db8e5af1b9ac184`
- Review bundle SHA-256: `eb5e2e64a20c7a0e0aa69a173fd1e9bd21c06e55a4f696475dcf1de1a4e48d21`

All identities match the reviewed files and current tracked source.

## Decisive findings

### Atomic idle lease

Independent CPU-only fault injection verified:

- A three-second loaded-worker idle gap is transactionally rejected before:
  - the next `reserve_call`;
  - worker-session close;
  - process-exit acceptance.
- Each rejection produced global `STOPPED` state with `cost_envelope_exceeded`; the target transition was not accepted.
- Exactly two seconds passed at all three boundaries.
- Coordinator state freezes the two-second wall lease as exactly four GPU-seconds.
- The analyzer requires this four-GPU-second value and is bound to the sealed coordinator, runner, and analyzer sources.
- The supervisor remains an early detector, but a missed poll cannot convert an over-limit gap into a successful ledger transition.
- The independent eight-second emergency reservation remains active while a worker is loaded and covers the frozen supervisor-poll/termination failure path.

The maximum successful-run idle-gap count is exactly:

```text
1475 calls + 2 terminal/load gaps × 3 workers = 1481
```

Therefore:

```text
2 × (1475 × 66 + 3 × 30 + 1481 × 2) / 3600
= 55.778888888888886 A100 GPU-hours
```

This is a valid upper bound for any successful complete run and remains below the 56-hour fresh envelope.

### Runtime stage decomposition

Direct reconstruction from all 473 completed records, all three incomplete pre-inference records, the authenticated global ledger, attempt ledgers, raw outputs, and the frozen tokenizer reproduced:

```text
concurrent 192-token inference upper       58.42139303322995
maximum incomplete pre-inference            3.567687389
maximum post-inference/pre-persistence       0.591471108826295
maximum post-persistence coordinator tail   0.58028415037316
──────────────────────────────────────────────────────────
governing floor                            63.160835681429404
66-second margin                            2.839164318570596
```

No stage receives an unsupported concurrency speedup credit.

## Additional verification

- Exactly 1,475 unique units and 30,932 frame occurrences.
- Static, mutually exclusive shards:
  - DALI: 567 calls on `[2,6]`
  - HANGZHOU: 561 calls on `[3,5]`
  - WUHAN: 347 calls on `[1,7]`
- Tail units were independently re-decoded from source video and exactly matched their frozen timestamps and RGB hashes:
  - `DALI_u0566`: 12 frames
  - `HANGZHOU_u0560`: 2 frames
  - `WUHAN_u0346`: 6 frames
- Three model loads, zero reloads, zero retries, no dynamic reassignment.
- Direct concurrent cost estimates reproduce exactly:
  - point estimate: `18.835258254316113 A100 GPU-hours`
  - 95% upper estimate: `23.135512147972786 A100 GPU-hours`
- Historical conservative usage plus the fresh envelope reproduces:
  - `6.697182287098888 + 56 = 62.69718228709889 < 64`
- All 26 review artifacts, 30 seal artifacts, 11 source bindings, and 29 preregistration bindings authenticate.
- Historical evidence authenticates recursively:
  - immediate: 14 control artifacts plus 473 raw outputs;
  - nested: 11 control artifacts plus 136 raw outputs.
- All 473 immediate historical raw outputs pass self-hash and strict reparse verification.
- `158 passed` in the complete CPU-only test suite.
- Live fault injection passed 12/12 cases.
- A fresh complete mock traversed all 1,475 units, produced 2,964 global-ledger events, passed analyzer authentication with no errors, produced deterministic K3 output, exercised the finalizer success path, and performed no formal publication.
- Partial results cannot publish formal labels or K3 references.
- Unknown and parse-failure semantics, frozen K3 merging, diagnostic-text independence, and evaluator/runtime label isolation remain intact.
- No V5 execution root, formal raw output, approval artifact, release artifact, or V5 model process exists.

No package or source file was modified, and no GPU inference was performed during this review.
