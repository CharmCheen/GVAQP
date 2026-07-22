# Research state

## Current objective

Build and freeze an independently adjudicated, exhaustive held-out
`enter_ego_path` event reference and a later <=100-call physical test plan,
without using EVENT_ENUMERATE or VERA to label it.

## Established findings

- The designated raw input directory was absent at `2026-07-12T13:20:49Z`.
- Therefore zero held-out files and zero candidate videos were available.
- The strict benchmark video exists and has SHA256
  `bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610`;
  it is forbidden as held-out evidence.
- Physical VLM calls in this task equal zero.

## Active hypotheses

- A future new video population may satisfy independence and processor-media
  compatibility. Untested until input arrives.
- Such a population may support exhaustive independent human review with
  adequate agreement. Untested.

## Rejected hypotheses

- The current workspace already contains input at the designated held-out raw
  path. Rejected by direct filesystem inspection.

## Important failure / lesson

Absence of video input is upstream of every semantic and physical gate.
Creating packet, reference, or sample artifacts now would imply evidence that
does not exist.

## Unresolved uncertainties

Video provenance, disjointness, FPS/timestamp compatibility, event content,
annotation agreement, and adjudication quality are all unresolved.

## Next highest-value action

Supply provenance-documented, byte-disjoint raw videos at
`data/realcam/heldout_v1/raw/`, then repeat Phase 0 inventory and hash checks.
