# Oracle provenance audit

Classification for canonical `test.mov`: `UNKNOWN` / zero target-predicate VLM
observations.

Recovered Qwen3-VL evidence comprises 399 10-second observations
(94 positive, 305 negative) and
51 merged VEPC events, all with `video_id=realcartest` on a roughly
3987-second source. The raw-response paths exist for
399/399 observations. The VLM
discovery report explicitly classifies `test` (43 seconds) and
`realcartest_5k` (208 seconds) as different videos with no VEPC reference.

The only exhaustive table directly naming `test.mov` has 1775 rows and
was produced by YOLOv8x without a language prompt; its predicate is vehicle
count >= K, not `enter_ego_path`. It cannot be relabeled as a VLM VEPC oracle.
No human-ground-truth or real-world-semantic claim is made.
