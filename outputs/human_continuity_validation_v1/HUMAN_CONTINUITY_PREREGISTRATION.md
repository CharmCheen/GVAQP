# Human Event-Continuity Preregistration

Protocol: `06deda4503981179bdd2bc9157f94f80c104dcc7fffb5e866da4fd10325716ac`

This is a **POST-P0 INDEPENDENT HUMAN VALIDATION**, not a pre-P0 preregistration. Existing model-relative P0 results have been observed; human continuity labels observed before this freeze: **NO**; benchmark tuned using human labels: **NO**.

The population is every consecutive pair of frozen full-grid VLM-positive anchors within DALI, HANGZHOU, and WUHAN. The hidden table records C0/C1/K3 predictions only for sampling/analysis. Human participants receive no reference events, method IDs/predictions, selector identity, F1, or P0 results.

The fixed primary workload is `40` blinded cases and the fixed reserve is `20` cases. The reserve is locked unless the primary result meets the predeclared `INCONCLUSIVE_PRIMARY` condition. Sampling is seeded `20260811`, stratified by actual prediction pattern and source video, and records inclusion probabilities/weights. The clip rule retains the full intervening interval; long intervals use low-FPS full context plus A/B detail clips rather than deleting the middle.

No materializer parameter, selector, VLM label, reference event, or query wording may be changed. The primary contrast is C1−C0 human continuity accuracy; K3−C1 is secondary. `ANCHOR_INVALID` and `UNCERTAIN` are reported separately and are not coerced into a split label.
