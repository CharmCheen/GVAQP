# Independent VLM Event-Continuity Sanity Study

Protocol: `b3f0d5c32a415132a3e41438fd735c9a3ea2954636659a2ff720f769e3279645`. This is a post-P0 blinded **VLM** semantic sanity study, never human validation or ground truth. It reuses the exact frozen 40-case human primary set without modifying it. Human labels observed at this freeze: **0**.

Judge A is `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` at cached revision `7b375e1b73b11138ff12fe22c8f2822d8fe03467`, a non-Qwen model family. The model receives only public blind IDs, query text, rendered A/B-marked clips, and the neutral label definitions. C0/C1/K3 predictions, strata, reference events, and P0 outcomes are not in the judge input.

One deterministic response is recorded per case. All 40 labels and raw logs are hash-frozen before hidden predictions may be joined. This study supplies independent cross-model semantic sanity evidence; it cannot replace future real-human validation.
