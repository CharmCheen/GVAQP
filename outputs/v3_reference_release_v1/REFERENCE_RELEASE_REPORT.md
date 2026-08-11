# V3 Full-Grid Reference Release Report

## Decision

`PAUSED_INPUT_REQUIRED`.

## What was already present?

The three preregistered independent sources are frozen: DALI (567 units), HANGZHOU (561), and WUHAN (347).  The V7 full-grid protocol, Qwen3-VL-32B checkpoint binding, prompt, unit grid, parser, K3 configuration, unit/frame/processed-input manifests, sealed staged launcher, and user compute approval are present.

The prior V5 run retained 1084 raw completed records, but it fail-stopped after 1086 attempted units.  V7 explicitly declares those labels nonreusable and requires a fresh execution from ordinal zero.

## What was incomplete?

No V7 fresh execution root, formal unit-label table, authenticated full-grid manifest, K3 reference relation, finalizer release, V3 candidate table, or V3 proxy table exists.  `scan_candidates/STATUS.md` is `NOT_RUN — FROZEN_SCAN_EXECUTION_PENDING`.

## What was reused?

No semantic labels were reused: `REUSED_UNITS = 0`, as required by the V7 preregistration.  Prior V5 raw records remain evidence only and were not promoted to reference labels.

## What required new inference?

The sealed V7 workload requires 1,475 fresh oracle calls.  It cannot be started in this checkout because the frozen processor environment does not match: expected `{'numpy': '2.4.6', 'opencv': '4.13.0', 'pillow': '12.1.1', 'python': '3.13.2', 'qwen_vl_utils': '0.0.14', 'torch': '2.10.0+cu129', 'transformers': '5.9.0'}`, observed `{'python': '3.13.2', 'numpy': '2.2.6', 'opencv': '5.0.0', 'pillow': '12.1.1', 'torch': '2.10.0+cu129', 'transformers': '5.5.4'}`.  This is a pre-inference fail-closed validation error, not a semantic result.

## Is reference construction frozen?

The recovered protocol and binding hashes are in `FROZEN_REFERENCE_PROTOCOL.json`; it is recovered but not executable in the present runtime.  No reference labels or K3 relation were created, so no evaluation substrate has been frozen.

## Leakage / circularity risk

No downstream F1, selector ranking, K0/K3 comparison, or materializer failure case was inspected or used.  The future reference relation is model-relative and uses K3 solely as the frozen evaluator-side reference relation; method-side K3 outputs must remain separately named.  Candidate/proxy visibility cannot pass because their tables do not exist.

## Independent sources

DALI, HANGZHOU, and WUHAN are distinct frozen source videos under the V7 manifest.  Their source identity is available, but none is released for controlled evaluation.

## Can P0 materializer validation now legally run?

`NO`.  It lacks complete formal model-relative labels/reference relations and a frozen common V3 candidate/proxy universe.

## Minimum required action

Restore the exact frozen processor runtime identity (Python is already compatible; install/use the bound `transformers==5.9.0`, `opencv==4.13.0`, and `numpy==2.4.6` environment without changing the sealed source/model/prompt), then execute the already approved V7 full grid.  Separately provide or authorize the already-pending frozen V3 scan/proxy candidate execution and its preregistered configuration; no selector experiment may start before both substrates release.
