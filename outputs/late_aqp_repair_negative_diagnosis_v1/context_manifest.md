# Context Manifest — Repair Negative Diagnosis v1

## 任务目标
诊断 chunk-bandit discovery（D3）上 repair 净负效果的原因，并确认 D3-norepair-core-chunk120 与 B6-core 是否为同一方法。

## 复用的既有实现
- `outputs/late_aqp_event_diverse_discovery_v1/run_event_diverse_discovery.py`
  - segment 定义、grid 构建、D3 chunk-bandit discovery、`run_discovery_then_core_halo`
- `outputs/late_aqp_core_halo_attribution_v1/run_attribution_analysis.py`
  - Core/Halo release (`perform_guards`, `compute_guard_need`, `MAX_GUARDS_PER_SIDE=3`)
  - LATE-AQP v1 流程（audit/repair/discovery/guard）
- `outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py`
  - B6/B7 chunk-bandit、`merge_bins`、metric 计算
- `outputs/late_aqp_event_diverse_discovery_v1/event_diverse_frontier_raw.csv`
  - 用于 D3-norepair vs B6-core 的数值身份核对

## 新增内容
- `run_diagnosis.py`：诊断脚本，仅添加日志，不修改算法逻辑。
- 对 D3-core-chunk120 和 D3-norepair-core-chunk120 做了 instrumented replay（复用既有 label，无新 oracle 调用）。

## 约束遵守情况
- 未调用 GPU/VLM/API，未生成新标签。
- 未修改 chunk-bandit discovery、repair 机制、Core/Halo release 的逻辑。
- 未使用 event_id/GT label 做运行时决策。
- 诊断同时报告了 repair 带来正面贡献和负面贡献的 case。

## 关键发现预览
1. D3-norepair-core-chunk120 与 B6-core **不是**同一方法（singleton counting 不同）。
2. D3-core 的 chunk-bandit discovery 函数 `discovery_d3_chunk_bandit` **忽略 `queried` 参数**，导致：
   - repair/audit calls 未被计入 bandit 状态；
   - discovery 重复查询已被 audit/repair 查询过的 bin，造成预算浪费。
3. 在记录的 38 次 repair calls 中，25 次（65.8%）发生在存在更高 theta chunk 时，存在预算转移。
4. 主要结论是：**这是一个可修复的实现 bug，不是 repair 机制设计问题**；应在修复后重新评估 repair 的真实边际价值。
