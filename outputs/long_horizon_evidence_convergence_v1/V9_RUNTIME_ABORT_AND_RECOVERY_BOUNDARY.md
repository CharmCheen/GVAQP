# V9 Runtime Abort and Recovery Boundary

## Verified fact

The sealed V9 execution has a formal terminal decision of
`FULL_GRID_ABORTED_RUNTIME`:

- execution seal: `57538d23ecfce5df23c58ba471e7efce206df4fb60f1dd226b549773e4233f9e`
- decision payload: `8a38030a859c388906cff7adf499c330d8684485f7c99ceb09737e084c964c89`
- V9 completed units: `1454 / 1475`
- V9 remaining units: `21 / 1475`, all `DALI_u0546` through `DALI_u0566`
- HANGZHOU and WUHAN missing units: `0`
- formal reference release: `null`

This audit deliberately does not inspect, summarize, or use any semantic
labels from the incomplete raw outputs.

## Direct cause

The durable V9 global ledger records the stop intent:

```text
loaded_worker_idle:V3_FULL_GRID_DALI:elapsed=2.197192:limit=2.000000
```

The frozen V9 failure policy makes an ordinary loaded-worker idle gap greater
than two seconds a global fail-stop.  The implementation records that class of
failure under the formal trigger name `cost_envelope_exceeded`; that name must
not be misreported as proof that actual GPU residency reached the 30.4 A100
GPU-hour envelope.  The terminal state instead records 54,571.732831550034
GPU-seconds (15.158814675430564 A100 GPU-hours).

## Why the incomplete records cannot become a reference

The sealed failure policy says that any missing, failed, uncertain, extra,
retried, unauthenticated, or cost-invalid run is incomplete and emits no
formal unit-label table or K3 relation.  It also prohibits reusing the
immediate prior run's completed labels in a fresh recovery.  The formal
finalizer enforced this rule and published no `FORMAL_REFERENCE_RELEASE.json`.

Consequently the 1,454 V9 raw records cannot be used for the V3 evaluation
reference, candidate calibration, K0/K3 comparison, selector comparison, or
event-level metric.

## Recovery feasibility under the existing authorization

The existing V9 approval authorizes the exact V9 fresh full-grid seal only and
uses the project-wide 64 A100 GPU-hour cap.  Its already-accounted conservative
usage before a new recovery is:

| Account | A100 GPU-hours |
| --- | ---: |
| Prior V5 conservative evidence + V7 actual, as bound by V9 approval | 33.49235846097388 |
| V9 actual runtime residency | 15.158814675430564 |
| Total before any V10 | 48.651173136404445 |
| Remaining within 64 | 15.348826863595553 |

The sealed full-grid point estimate is 16.59314522789404 A100 GPU-hours.  A
descriptive extrapolation of the V9 *runtime*, not its semantic output,
projects 15.377752163865257 A100 GPU-hours for another complete fresh grid.
Even that non-hard projection exceeds the remaining cap by
0.028925300269703413 hours.  It cannot lawfully justify a new hard execution
envelope, and the frozen failure policy requires a fresh-from-zero grid rather
than a 21-unit tail retry.

## Consequence

`P0_MATERIALIZER_VALIDATION_READY = NO`.

The three scan/proxy tables remain prospectively frozen and valid, but there
are zero formally released model-relative V3 references.  No P0 metric has
been run or observed.

## Minimum new authority required

Before another oracle call, the user must authorize a **new prospective V10
fresh-from-zero full-grid execution** with:

1. unchanged semantic V3 bindings (model, processor, prompt, query,
   unitization, parser, decoding, K3 reference semantics, and sealed GPU
   topology);
2. a new runtime-only contract that addresses the observed 2-second idle-lease
   failure without changing semantic behavior; and
3. enough additional A100 GPU-hour authorization to set a defensible
   fresh-grid hard envelope.  Reusing the existing 16.59314522789404-hour
   estimate would require an overall cap of at least
   65.24431836429849 A100 GPU-hours before any safety margin.

No V10 package, source modification, or inference has been created from this
audit.
