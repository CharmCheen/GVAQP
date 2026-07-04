# probe_set_v1

Purpose: independent Layer 0 probe set for read-only evaluation of SQ-CRAQ v2 and later stages.

Hard restriction: rows marked `probe_set_v1` must not be used for tuning, threshold selection,
selector choice, repair decisions, or candidate generation. They are a frozen evaluation-only
readout once annotated.

Sampling:
- Rule: equal-interval time grid, independent of candidate lattice, envelope, and prior review queues.
- Target count: `25`.
- Clip duration: `10.0` seconds.
- Requested video path exists: `False`.
- Video source used: `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4`.
- Video source status: `fallback_dataset3_with_reference_absolute_offset`.
- Local-to-media offset seconds: `2000.0`.
- Media duration seconds: `3462.930`.
- Available logical duration seconds: `1462.930`.

Outputs:
- `probe_set_manifest.csv`: media/export manifest.
- `probe_set_review_sheet.csv`: empty annotation sheet.
- `probe_media/clips`, `probe_media/centers`, `probe_media/sheets`: exported review media.

No VLM, oracle, detector, candidate lattice, or envelope logic was run to construct this probe set.
