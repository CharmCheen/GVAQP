# Nexar Candidate Feasibility Report

## 1. Goal

Evaluate whether practical video-content candidate generators can produce high-recall returned clips on the Nexar derived-boundary benchmark after the Nexar videos were expected to be available.

## 2. Why this follows Phase 1.3

Phase 1.3 found candidate quality to be the main bottleneck. This run starts with the required video access gate before any candidate generation, because candidate recall and certificate results would be uninterpretable if the Nexar-200 videos cannot be mapped and read.

## 3. Video access and mapping

- Manifest rows: `400`
- `.mp4` files found under `videos_hf`: `287`
- Mapped manifest rows: `76`
- Readable manifest rows: `76`
- Readable fraction: `0.1900`
- Required readable fraction: `0.8000`

Readability by manifest label:

| label | rows | mapped | readable | readable_fraction |
| --- | --- | --- | --- | --- |
| normal | 200 | 76 | 76 | 0.38 |
| positive | 200 | 0 | 0 | 0 |

Full mapping table: `tables/nexar_video_mapping.csv`.
Full readability table: `tables/nexar_video_readability.csv`.

## 4. Subset construction

The requested Stage A and Stage B subset tables were written, but both are marked with readability status. Candidate generation was not run because the access gate failed.

- Stage A rows requested: `100`
- Stage A readable rows: `25`
- Stage B rows requested: `400`
- Stage B readable rows: `76`

## 5. Frame extraction

Not run. The required `tables/nexar_frame_index.csv` schema-only file was written. Extracting frames from a partial, label-skewed subset would violate the staged evaluation gate.

## 6. Candidate generators

Not run because fewer than 80% of Nexar-200 manifest videos were readable. Schema-only candidate CSVs were written under `candidates/` with `stage_not_run_*` names to document the fail-closed state.

## 7. Leakage controls

The mapping/readability gate used filenames, basenames, relative paths, file existence, file size, ffprobe/OpenCV duration, and first-frame readability only. It did not use `event_start`, `event_end`, `event_moment`, or `alert_time` for generation, ranking, threshold tuning, or window selection. No practical candidate rows were generated, and all candidate-stage outputs remain empty.

## 8. Candidate recall vs budget

Not run. `tables/nexar_candidate_eval_results.csv` is schema-only because the video access gate failed before frame extraction or candidate generation.

## 9. Runtime / GPU usage

- GPU visible: `True`
- GPU used: `False`
- GPU model: `NVIDIA A800-SXM4-80GB`
- Runtime seconds for access audit: `9.062`
- Frames processed: `0`
- Videos processed for candidate generation: `0`
- Throughput fps: `not applicable`

## 10. Certificate results for promising candidates

Not run. No candidate reached the evaluation stage, so there were no promising candidates to certify. `tables/nexar_candidate_certificate_results.csv` is schema-only.

## 11. Limitations of derived boundaries

The Nexar event intervals are derived from metadata and are not human-adjudicated event boundaries. Even if videos were complete, results would be pseudo-oracle/derived-boundary evaluation, not human ground truth.

## 12. Recommendation

Repair or complete the local Nexar video mirror so that at least 80% of the 400 manifest rows are mapped and readable. The current `videos_hf` tree is heavily incomplete for this benchmark, with positive videos absent from the mapped readable set.

NEXAR_CANDIDATE_DECISION: VIDEO_MAPPING_OR_READABILITY_FAILED
