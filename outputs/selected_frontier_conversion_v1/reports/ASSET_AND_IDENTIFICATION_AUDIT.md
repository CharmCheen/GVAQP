# Asset and identification audit

## Strongest supported conclusion

The Stage-1 benchmark cannot start. The local workspace contains only one preliminary eligible new source group (`杭州.mp4`) against a frozen requirement of four, so three additional independent complete videos are missing.

## Decisive evidence

V0 and V1 are design-only. `杭州YouTube.mp4` has the same duration/frame count as `杭州.mp4` and an exact aligned perceptual-hash match in the prior blind audit, so the Hangzhou pair is one source, not two. The normalized files are derivatives; the transcoded recovery retained only 8.4581% of the timeline. The 1,208-second review clip is explicitly mapped to V0 at offset 2,000 seconds; `test.mov` is the 43-second canonical heldout; and `realcartest_5k` is a documented 208-second derivative. No other inventoried large media file satisfies the gate.

## Competing explanation and uncertainty

The accepted Hangzhou representation is technically executable under prior direct evidence, but its independence from V0/V1 is owner-attested rather than externally verified. Treating it as ineligible would strengthen, not reverse, the blocker (four videos missing instead of three).

## Decision

`INPUT_GATE=BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS`. Dataset construction, C0-C4, calibration metrics, static common-utility analysis, and Ratio-Anchored replay were not run. New Oracle calls: zero.
