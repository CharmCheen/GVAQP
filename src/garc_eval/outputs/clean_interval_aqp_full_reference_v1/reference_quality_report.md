# Reference Quality Report

Reference type: VLM-defined pseudo-oracle, not human ground truth.

Mini-universe units: 600 2s base units.

Positive base units: 80 (0.133).

Reference events: 20.

Anchor labels clipped into the segment: 120.

Raw VLM outputs copied or indexed: 120.

Limitations:

- Boundary resolution inherits V13.8 center10 oracle behavior and event stitching.
- The first-stage universe selection used existing pseudo-oracle labels for curation, so this is a
  clean mini-universe experiment, not an unbiased prevalence estimate.
- These labels are oracle-relative only and must not be described as human truth.
