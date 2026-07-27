# PSVR development input request

`BENCHMARK_INPUT_POOL = INSUFFICIENT`

## Current valid input

- `long_video_dataset3.mp4`: 3462.93 seconds, 347 frozen 10-second units, stable decode/proxy/oracle evidence.

## Missing input

The development pool needs **1 additional independent source videos**. Existing references to `long_video_dataset2.mp4` and `realcartest.mp4` do not help because their bytes are absent; dataset2 was also later identified as an in-cabin driver-facing view unsuitable for ego-path queries.

## Rejected local candidates

- `realcartest_5k.mp4`: documented first-5000-frame derivative of missing `realcartest.mp4`.
- `test.mov`: existing canonical held-out video, explicitly excluded; its manifest also records only 43.04 seconds.
- Nexar: 604 ffprobe-visible paths / 603 unique clips, 15.00-49.46 seconds; every clip has at most five 10-second units.
- DrivingDojo-mini: local archive contains short image-sequence sessions, not continuous video containers.
- Any clips/reencodes/crops under outputs, experiments, or `datasets/clips`: derivatives, not independent sources.

## Files to provide

- Supported containers: MP4, MOV, MKV, AVI, WebM, or M4V with a normally decodable video stream.
- Recommended minimum duration: **30 minutes**; hard workload screen is 1200 seconds so 29×4 A0 scans do not exhaust the video.
- Prefer forward-facing road views from different capture sessions, with varied scene categories, event layouts, weather/lighting, and traffic density.
- Do not provide crops, reencodes, frame-rate/resolution conversions, overlapping segments, or splits of existing sources.
- Place files in: `/qiuyeqing/llama_prl/G-ARC/data/realcam/psvr_dev_inputs`.

For each `name.mp4`, also provide `name.mp4.source.json` so independence is explicit:

```json
{
  "source_kind": "original_continuous_capture",
  "capture_session_id": "a unique capture/session identifier",
  "known_parent_video": null,
  "known_derivation_operation": null
}
```

The audit rejects a missing/invalid declaration, repeated session identifier, or exact-content duplicate. Query semantics and reference eligibility are assessed only after this source-input gate passes.

No query or algorithm work will resume until this input gate passes. Held-out semantic/reference evaluation remains unopened.

## Resume

```bash
python scripts/audit_psvr_dev_inputs.py
```
