# Required multivideo validation plan

This plan is prospective and was not executed in this sprint.

1. Freeze a metadata-correct processor contract and verify the exact post-processor indices/timestamps without using event labels.
2. Select at least five long videos spanning prevalence, day/night, weather, traffic density, camera motion, and event duration; keep at least three videos untouched for final testing.
3. Human-adjudicate EventRelations with double annotation and blinded conflict resolution. Preserve the current VLM pseudo-reference as a secondary endpoint.
4. Fit enumeration error/cost profiles only on development videos; freeze DP risk bins, core options, margins, prompts, parser, and dense fallback before test-video inference.
5. Predeclare per-video and macro event precision/recall/F1, GPU seconds, end-to-end wall time, cold-index cost, W=1/10/100 amortization, and failure strata.
6. Run dense, uniform, public proxy, CLIP retrieve-then-ground, MAP/M1, native ARC, ARC+enumeration, SUPG+enumeration, ABae+enumeration, all VERA ablations, and the evaluator-only ceiling under shared hardware accounting.
7. Require recall and F1 >=0.80 and GPU ratio <0.70 on every primary test video or a preregistered conservative macro rule; report all failures and confidence intervals.
8. Repeat the processor/materializer audit from raw frames through final EventRelation, then release manifests and per-call checkpoints.

The first high-information step is a small held-out, metadata-correct operator calibration—not another proxy, ranking model, or merge heuristic.
