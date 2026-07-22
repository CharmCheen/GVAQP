BENCHMARK_SOURCE:
    /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4

BASELINE_EXECUTION:
    CLEAN_RERUN_FROM_FROZEN_INPUTS

RESULT_SCOPE:
    SINGLE_VIDEO_TEMPORAL_HOLDOUT_DIAGNOSTIC

# Clean Baseline Benchmark v1 Final Report

## Required answers

1. **本轮 baseline 是否全部由指定 MP4 重新运行？** 是。unit/proxy 由该 MP4 本轮重建，所有 acquisition policy 从空状态按 frozen budgets 重新执行；没有复制任何旧 selected/query set、segment、metric、aggregate CSV、排名或 threshold winner。
2. **复用了哪些旧数据？** 仅复用 347 个满足同视频区间、Qwen3-VL-32B 路径/config lineage、prompt hash 和 parser version 条件的原始 VLM response cache（297 full scan + 50 P1）。物理 VLM calls=0；每个 run 的 logical oracle calls 仍完整计费。旧方法结果复用数=0。
3. **benchmark 是否可复现？** 是，benchmark_id=`cbbv1_c2e246d1504d9d8a80b2`；输入、代码、模型 manifest、prompt、budget、evaluator 和 matching hashes 均已冻结。sanity failures=0。
4. **trace 是否足以支持未来 materializer replay？** 是。`materializer_replay_comparison.csv` 对每条 controlled trace 以 original K3 与 K3-bridge-safe 双重重放，且不新增 acquisition/VLM call。
5. **当前方法相对哪个 baseline 有优势？** AUC 审计中 best repository baseline 为 `baseline/B5_ARC_native/arc_refinement_th0.4_native`；K3-bridge-safe 的方向性结论为 `WEAK GO`，AUC delta=-0.007383。
6. **优势在哪些 budget/指标？** event-F1 wins=[50, 80, 100], ties=[], losses=[5, 10, 20]。完整 precision/recall/tIoU/returned-seconds delta 在 `comparisons/method_vs_baseline_by_budget.csv`。
7. **是否有 precision 或 review-cost 代价？** 逐 budget 数据如下；不得只以 F1 隐藏代价：

|   budget |   current_precision |   baseline_precision |   current_cost |   baseline_cost |
|---------:|--------------------:|---------------------:|---------------:|----------------:|
|        5 |            0        |             0.25498  |              0 |            1886 |
|       10 |            1        |             0.261882 |             20 |            1862 |
|       20 |            1        |             0.267385 |             30 |            1830 |
|       50 |            0.875    |             0.293701 |             80 |            1714 |
|       80 |            0.909091 |             0.981818 |            110 |              92 |
|      100 |            0.916667 |             0.90343  |            130 |             112 |

8. **结论是 human-GT 还是 oracle-relative？** `VLM_DEFINED_PSEUDO_ORACLE`，不是 human ground truth；单视频结果不支持泛化或最终安全保证。
9. **缺少哪些重要 baseline？** ARC original guarantee、SUPG original guarantee 均无法在本任务的 event-set/finite-budget adapter 中保留，明确标为 `ADAPTED_NO_ORIGINAL_GUARANTEE`。M2 未有 frozen config；relation M3/M4 因 relation oracle gate 未通过而未运行。没有伪造这些结果。
10. **下次修改当前方法后如何比较？** 先运行兼容性验证，再用 frozen inputs/oracle 执行新 planner：

```bash
PACK=Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1
python "$PACK/scripts/validate_benchmark_compatibility.py" --new-manifest /path/to/new_run_manifest.json
python "$PACK/scripts/replay_baseline_acquisition.py" --trace "$PACK/baselines/controlled_track/B1_top_proxy/top_proxy_controlled_bridge_safe/seed_000/budget_20/action_trace.csv" --materializer k3_bridge_safe --output-dir /tmp/replay_b1_b20
```

## Baseline coverage

- B0 uniform/random: 100 repeats per budget with mean/std/95% CI.
- B1 top-proxy and B2 component-first: deterministic clean reruns.
- B3 ARC-adapted controlled and B5 ARC-native: repository ARC implementation, dev-frozen threshold 0.4.
- B4 SUPG-adapted: all-selected and confirmed-only, native and controlled.
- B6 ABae diagnostic: stratified repository adapter, native and controlled.

## Failures and scope impact

| method                | variant     |   seed | budget   | track          | exception                                                           |   traceback | missing_dependency          | affects_best_available_baseline   |
|:----------------------|:------------|-------:|:---------|:---------------|:--------------------------------------------------------------------|------------:|:----------------------------|:----------------------------------|
| M2_coverage_variant   | not_run     |      0 | all      | current_method | No frozen coverage variant in docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md |         nan | frozen method specification | False                             |
| M3_relation_heuristic | gate_failed |      0 | all      | current_method | Relation oracle table absent; relation gate did not pass            |         nan | relation oracle             | False                             |
| M4_relation_adaptive  | gate_failed |      0 | all      | current_method | Relation oracle table absent; relation gate did not pass            |         nan | relation oracle             | False                             |

## Decision

`WEAK GO` — this is a directional, oracle-relative decision on one long video. It is not a human-GT or cross-video claim.
