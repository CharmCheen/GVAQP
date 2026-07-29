# Research State

## Current objective

Determine whether a two-stage VLM protocol can produce a calibrated,
extensible safety-event pseudo-reference before changing any online SCAN
component.

## Established findings

- The frozen v1 task is `TARGET_VEHICLE_CUT_IN`, not general danger detection.
- Its prompt, parser, finalize step, candidate generator, matcher, and benchmark
  contract all enforce that narrow semantics.
- The existing v1 reference is not human adjudicated; 405/405 raw reported
  events have high confidence and no ambiguous event was emitted.
- An unrelated `partial_scan_pilot_v2` already exists for application protocol
  and runtime-accounting repair, so this reference pilot must remain separate.

## Active hypotheses

- H1: a single broad prompt can discover and adjudicate general hazards with
  adequate recall and hard-negative precision.
- H2: separating high-recall discovery from proposal-local adjudication yields
  better auditability and calibration than a single prompt.
- H3: correlated errors from using the same VLM in both stages prevent the
  two-stage protocol from reaching the human-calibrated gate.

## Rejected direction

Directly replacing the frozen v1 cut-in prompt is rejected because it creates
semantic mismatch with the frozen parser, reference schema, online candidate
generator, matcher, and benchmark contract.

## Unresolved uncertainty

Independent, selection-safe pools for longitudinal conflict, vulnerable-road-
user crossing, road hazard, and intersection conflict have not yet been
established. No VLM or human pilot should launch until those pools and the gate
thresholds are frozen.

The CPU-only sample audit selected 30 blinded legacy windows: 10 legacy cut-in
positives, 5 cross-context hard negatives, 5 boundary cases, and 10 controls.
These are currently selection-metadata rows rather than executable samples:
the two v1 manifests point to an old `/qiuyeqing/llama_prl/G-ARC` workspace and
neither source video is present in this checkout. The audit therefore blocks on
both missing source bytes and missing independent pools for four general-hazard
strata. This is an evidence gap, not a negative result about the prompt.

The repository also contains Nexar collision/near-collision metadata manifests,
but the referenced local video bytes are absent in this checkout and the
derived event tags are not human adjudicated. They therefore do not close the
four missing semantic-pool requirements.

## Next highest-value action

Build the blinded sample-availability audit from existing read-only evidence.
If all required strata become available, freeze thresholds and run the smallest
Stage A/Stage B/human comparison capable of rejecting H1 or H2.
