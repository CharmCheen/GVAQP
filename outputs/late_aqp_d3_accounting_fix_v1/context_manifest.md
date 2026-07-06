# Context Manifest — D3 Chunk-Bandit Accounting Fix v1

## 任务目标
修复 `discovery_d3_chunk_bandit` 的 queried-state accounting bug，并重新评估 repair 在 D3 chunk-bandit backbone 上的真实边际价值。

## 复用的既有实现
- `outputs/late_aqp_event_diverse_discovery_v1/run_event_diverse_discovery.py`
  - segment 定义、grid 构建、metric 计算、实验循环
- `outputs/late_aqp_core_halo_attribution_v1/run_attribution_analysis.py`
  - Core/Halo release (`perform_guards`, `compute_guard_need`)
  - LATE-AQP v1 流程（audit/repair/discovery/guard）
- `outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py`
  - B7 chunk-bandit、`merge_bins`、metric 计算
- `outputs/late_aqp_repair_negative_diagnosis_v1/repair_diagnosis_call_log.csv`
  - 用于 original D3-core 的 duplicate call 对比

## 新增/修改内容
- `run_d3_accounting_fix.py`：新脚本，仅修改 D3 chunk-bandit discovery 的 accounting 逻辑。
- `discovery_d3_chunk_bandit_fixed`：正确初始化 `queried` 状态，避免重复查询。

## 约束遵守情况
- 未调用 GPU/VLM/API，未生成新标签。
- 未修改 repair trigger、repair expansion、Core/Halo release。
- 未修改 prior score、budget grid、90/90 阈值。
- 未引入新算法机制或 D4/D5。
- 未覆盖旧输出。

## 关键发现预览
1. **Bug 已修复**：`duplicate_query_after_audit_repair_count` 降为 0；总重复调用从 original D3-core 的 11.21 次/ trial 降至 fixed 的 0.51 次/ trial。
2. **Performance**：D3-core-fixed 在 1/6 segment 上优于 original D3-core，在 1/6 segment 上优于 D3-norepair，未能在任何 segment 上优于 B7-core。
3. **Budget diversion**：修复后 0% 的 repair call 抢占更高 theta 的 chunk；剩余差距不是由 budget diversion 造成。
4. **结论**：repair 在 accounting 修复后为 **neutral**；推荐继续采用 D3-norepair / chunk-bandit core 路线，或考虑 audit/estimator 方向。
