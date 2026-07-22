# Held-out media recovery amendment

Recorded after the method/protocol freeze and before held-out CLIP inference.

The frozen protocol identified overlapping five-second retained clips as the reconstruction source. A subsequent filesystem audit found a stronger artifact: 398 contiguous, ten-second `realcartest` scene windows under `experiments/roadclip_budget_v2/roadclip_budget_v2/scene_windows/`. Windows 200 through 319 exactly cover the frozen absolute interval `[2000, 3200)`.

Held-out CLIP inference will therefore decode the center frame at relative time 5.0 seconds from each exact ten-second scene window. This changes only media recovery fidelity. It does not change the held-out interval, query, model, unit grid, QTPC radius, ranking rule, budgets, materializer, metric, or decision rule. The original frozen protocol file is intentionally left unchanged so its pre-inference hash remains auditable.

The scorer must emit a per-unit mapping with source path, SHA-256, requested relative timestamp, decoded frame count, and CLIP checkpoint hash.
