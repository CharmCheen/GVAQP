# M0 Shared Causal Execution Contract

## Status after CPU tests

`M0_PASS_FOR_CPU_REPLAY_CONTRACT`

The authorized focused suite passed all 15 tests. This status is limited to the
execution contract and does not advance an algorithmic-effect gate.

## Purpose

`M0` replaces policy-specific evaluators with one causal execution path. A policy
may choose only an action. It may not define candidate visibility, action cost,
oracle semantics, event materialization, deadline handling, or utility.

## Frozen execution boundary

The shared engine enforces:

- a candidate is unavailable until its temporal cell has been scanned;
- every scanned cell retains a low-priority fallback candidate;
- SCAN cost may depend on the previously scanned cell and therefore charges
  random seek/decode order explicitly;
- VERIFY uses a fixed 10-second primary window;
- the oracle returns zero or more structured `EventRelation` records;
- event identity uses the sorted participant-track tuple and a temporal gap of at
  most 10 seconds;
- deadline-crossing actions are rejected before any state mutation;
- durable event output, normalized anytime distinct-event AUC, and terminal event
  recall are computed by the shared engine;
- identical action traces must produce exactly identical trace, materialization,
  and utility outputs.

## Deliberate limitations

This is an execution contract, not claim-grade evidence. It does not call a VLM,
measure C3 GPU cost, recover old provenance, or establish DATB-SV superiority.
The current materializer conservatively attaches a bridging relation to one
already committed event instead of retroactively deleting durable event IDs.
Human MEC remains the external-validity endpoint.

The initial policy adapters are deterministic CPU controls. `ExSample-EndToEnd`,
the complete DSL candidate planner, and the claim-grade workload adapter remain
required before `T2` can support algorithmic comparisons.

## T2 gate

`T2` may start only when:

1. `T0` is recorded without using unrecoverable physical claims.
2. M0 unit tests pass.
3. Identity-trace policy/baseline parity passes exactly.
4. Existing-corpus inputs are adapted without bypassing causal exposure.
5. All compared policies use this same executor and cost tier label.
