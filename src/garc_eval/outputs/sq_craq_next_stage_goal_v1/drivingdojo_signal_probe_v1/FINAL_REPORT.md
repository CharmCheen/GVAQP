# DrivingDojo Signal Probe V1

## Answers

1. DrivingDojo's role is signal-design support for SQ-CRAQ, not the final AQP benchmark.
2. It is not a final benchmark because current claims remain VLM-oracle-relative and interval-reference limited; DrivingDojo should help design answer-compatible cheap signals.
3. Needed fields/labels: video id, clip boundaries, object tracks, bbox center/area trajectories, interaction labels or reviewable event intervals, and grouped source-video metadata.
4. Next probe: 200-500 clips, dry-run manifest first, then use existing local features if available.
5. Do not directly full-download or full-run YOLO because the current bottleneck is method/reference qualification, and heavy perception runs need explicit authorization.

Local DrivingDojo roots found: `1`.
