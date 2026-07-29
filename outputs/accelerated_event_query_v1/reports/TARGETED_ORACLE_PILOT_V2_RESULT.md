# Targeted Operational-Oracle Pilot V2 Result

Decision: `REVISE_ORACLE_PROTOCOL`

## Decisive evidence

- Exact execution completed: 32/32 authorized calls across DALI/HANGZHOU/WUHAN at 10/11/11, on disjoint physical GPU pairs `(1,2)`, `(3,5)`, `(6,7)`.
- Integrity passed: 32 PREPARED, 32 INFERENCE_STARTED, 32 INFERENCE_COMPLETED, and 32 ACCEPTED events; zero retry, failed-generation, uncertain, extra, or missing calls.
- Reproducibility passed: 12/12 same-process pairs and all three cross-replica anchor observations matched in metadata identity, actual processed-tensor hash, and exact raw response.
- Class support passed: base consensus contained four `relevant` and eight `not_relevant` clips, with each class represented across all three videos.
- Numeric gate failed: strict parse success was 31/32 (`0.96875`) rather than `1.0`. `DALI_u0548_fps4_sensitivity` described a `17.0–20.0` event inside a 10-second relative-time input and was correctly retained as `invalid_relevant_boundary` / `parse_failure`.
- Systematic semantic screen failed: decided-polarity contradictions occurred for `DALI_u0555`, `HANGZHOU_u0234`, and `WUHAN_u0217`, spanning all three videos.
- Independent grounding failed: only 2/4 unique positive claims were supported. The WUHAN claim falsely asserted a red transition at 6.0 seconds although the exact earlier frames were already red. The HANGZHOU claim treated a left-turn red signal as straight-ahead red while the straight arrow remained green and the crosswalk was empty.

## Cost and provenance

- Inference: 790.671 seconds total, equivalent to 0.439262 A100 GPU-hours because each call used two GPUs.
- Model loading: 46.063 seconds across three shard loads.
- Raw physical labels: 23 `not_relevant`, eight `relevant`, one `parse_failure`; these are operational-oracle outputs, not human truth.
- Execution seal: `58f84d2ce389aa3cf8122137911b0ec8429d6db80d84766afd88ee870b6b7576`.
- Evidence manifest: `PILOT_EVIDENCE_MANIFEST_V2.json`, SHA-256 `4004381894457d20163db2badfe615e19469b7b8d79c01817288a7226fc1e093`.

## Interpretation

The checkpoint/runtime path is highly deterministic, but the frozen response-required protocol is not adequate for reference construction. The strongest competing explanation is reviewer fallibility on sparse frames; it cannot explain the impossible timestamp coordinates, and two positive claims were contradicted by directly visible signal state and lane attribution.

This result does not support a representative audit or any full-grid/downstream claim. The approved compute scope is exhausted. No additional oracle, YOLO, replay, headroom, or controller work is authorized.
