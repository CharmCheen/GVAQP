# Accelerated Event Query V1 — Run Status

Overall status: `IN_PROGRESS`

Current research-loop decision: `CONTINUE`

Terminal decision: `NOT_YET_JUSTIFIED`

## Objective

Under the same hard deadline and event-precision requirement, determine whether causal dynamic SCAN/VERIFY allocation returns more K3-reconstructed driver-response events and returns them earlier than the best fixed or two-stage policy.

## Established findings

- Three real videos are present, decodable, and content-hash frozen: Dali, Hangzhou, Wuhan.
- The existing center10 unit semantics can be reused, yielding 1,475 non-overlapping units.
- Existing Dali/Wuhan operational labels are not semantically interchangeable with the new query.
- Prior 32B A100 execution is feasible only as a two-GPU BF16-dequantized path and is fallible.
- Prior binary-SMDP headroom evidence remains insufficient: one approximate SCAN-better state, no VERIFY-better states, four ties, and incomplete/unsafe cost support.
- New event/K3/matching/state-boundary/oracle-schema unit tests: 18 passed with `PYTHONPATH=src pytest -q tests/accelerated_event_query`.

## Active hypotheses

- H1: the frozen 32B prompt yields stable enough operational labels.
- H2: frozen YOLO candidates plus K3 have adequate event-recall ceiling.
- H3: event-calibration verification exposes safe cross-video binary switching headroom.

## Failed/rejected paths retained

- Old-query labels as new-query truth: rejected for semantic mismatch.
- Immediate learned controller: rejected until oracle, scan-ceiling, and safety gates pass.
- Historical Q90 dynamic-oracle gain: retained but invalid for the new safety contract because it admitted overruns.

## Artifacts completed this cycle

- `docs/ACCELERATED_EVENT_QUERY_CONTRACT_V1.md`
- `docs/ACCELERATED_EVENT_QUERY_REPORT_V1.md`
- `docs/ACCELERATED_EVENT_QUERY_NEXT_DECISION.md`
- frozen query/oracle/K3/matching config and prompt
- three-video identity manifest
- incremental event K3, event matcher, causal state schema, and targeted tests

## Missing decision-critical evidence

- H1 cross-video stability/parse preflight (30-call workload preregistered: 24 identical-input calls plus six 2 fps/4 fps sensitivity calls; all three shards pass validate-only preflight; physical calls not yet authorized/run)
- complete new-query 32B oracle with raw output retention
- operational reference events
- full YOLO scan and K3 event-recall ceiling
- independent cost-calibration safety gate
- label-hiding replay and dynamic headroom
- state models, closed-loop evaluation, and ablations (correctly not run yet)

## Next action

Run the deterministic freeze materializer, preregister the H1 sample without reading its new-query outcomes, and request approval before launching the substantial 32B oracle workload.
