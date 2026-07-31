# FULL_GRID_INDEPENDENT_REVIEW

**Decision: `REVISE_FULL_GRID_PREREGISTRATION`**

Reviewed identities:

- Source commit: `d6de2ca9d2cc0fbaa473a22e19fc377e726be06f`
- Execution seal SHA-256: `ca10897d0ca4ac6870b7db2a3b5d5ba383c5d2639ab49426f1f60c9d8580c3a9`
- Review bundle SHA-256: `8371100d8294da90e902cfbee6bc8a24f1574410fd9529700a0b8f5ab33190d8`

## Verified evidence

- Exactly 1,475 unique units; no shard overlap or omission.
- Frozen worker counts are 567/561/347 on static GPU pairs `[2,6]`, `[3,5]`, and `[1,7]`.
- Tail units contain exactly 12/2/6 real frames without padding or duplication.
- Three model loads, zero reloads, zero retries, and no dynamic reassignment are preregistered.
- All manifest, analyzer, finalizer, runner, processor, schedule, and nested historical-evidence bindings validate.
- Recursive authentication covers 487 immediate and 147 nested bindings; the nested-mutation test fails closed.
- All 473 preserved historical raw outputs pass self-hash and strict reparse checks.
- The direct concurrent estimate recomputes exactly:
  - point estimate: `18.835258254316113 A100 GPU-hours`
  - 95% upper estimate: `23.135512147972786 A100 GPU-hours`
- `154 passed` in the CPU-only test suite.
- The dry-run artifact records 1,475 mock calls, three mock loads, deterministic K3 output, and 11/11 fault injections.
- Partial-publication blocking, unknown/parse-failure semantics, K3 determinism, and evaluator/runtime label isolation are covered.
- No V4 execution root, formal raw output, approval artifact, or model process exists.

## Blocking findings

### 1. The 2-second idle lease is not an atomic hard bound

The claimed idle-inclusive bound of `55.778888888888886 A100 GPU-hours` assumes every loaded-worker idle gap is limited to two seconds. The transaction coordinator actually enforces an eight-second emergency reservation; the two-second rule exists only in polling supervisor logic.

A CPU-only transaction test created a three-second idle interval and then reserved the next unit before the supervisor could observe the violation. The coordinator remained `READY`, accepted the reservation, and charged six GPU-seconds of idle time.

Therefore, a successful ledger can exceed the two-second assumption, so neither the stated hard bound nor the 56-hour envelope is currently proven.

Required revision:

- Enforce the two-second lease atomically inside the coordinator at the next reservation/session/process-exit transition.
- Add a regression test in which supervisor polling misses an over-limit gap.
- Recompute and reseal the idle-inclusive bound and cumulative authorization bound.

### 2. The evidence-complete runtime floor omits a completed processing stage

The frozen floor is calculated as:

```text
58.42139303322995
+ 3.567687389
+ 0.09937976270346383
= 62.08846018493341 seconds
```

This includes scaled inference, the longest incomplete pre-inference interval, and post-persistence overhead, but omits completed post-inference/pre-persistence work.

The largest directly observed residual is:

```text
0.12836038128246785 seconds
```

Consequently, the directly supported stage-complete floor is at least:

```text
62.21682056621588 seconds
```

The 66-second lease remains above this corrected floor, but the frozen floor and stated margin are inaccurate.

Required revision:

- Include the post-inference/pre-persistence stage explicitly.
- Recompute the lease margin and all dependent cost claims.
- Regenerate the affected preregistration artifacts, execution seal, and review bundle.

No full-grid execution or approval request should proceed until both corrections are implemented, tested, frozen, and independently re-reviewed. No files were modified and no GPU inference was performed during this review.
