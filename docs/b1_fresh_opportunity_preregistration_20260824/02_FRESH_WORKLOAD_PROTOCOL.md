# Fresh workload protocol

## B1a minimum discriminating set

- Exactly 3 continuous videos.
- Three distinct source assets and recording sessions; no shared parent or
  technical derivative.
- Each video must be at least 720 seconds, at least 720p, and decodable without
  continuity gaps in the selected intervals.
- Selection uses provenance and metadata only. No target-query outcomes,
  detector scores, event-centered previews, or semantic inspection.
- All 6 frozen queries run on every video: 18 video-query workloads.

## Deterministic intervals

- Cost-only calibration interval: `[0, 60)` seconds.
- Analysis interval length: 600 seconds.
- `analysis_start = 60 + floor((duration_seconds - 660) / 2)`.
- Analysis regions are consecutive non-overlapping 10-second intervals.
- The calibration interval is excluded from every utility result.

If decoding or continuity fails, exclude the video before semantic execution
and replace it with the next provenance-eligible source in the frozen intake
order. The reason and failed hash remain in the exclusion ledger.

## Independence and consumption

The following IDs and any byte-identical or parent/derivative assets are
ineligible: `DALI`, `HANGZHOU`, `WUHAN`, `GUANGZHOU`,
`long_video_dataset3`, `杭州`, `杭州YouTube`, `驾驶-大理`, and all six T2
video-query workloads.

After binding, all three B1a videos become consumed for mechanism selection.
They cannot serve as B1b confirmation videos.

## B1b is not pre-authorized

Only a B1a PASS may justify freezing a larger confirmatory set. B1b requires at
least six additional independent videos and a separate authorization.
