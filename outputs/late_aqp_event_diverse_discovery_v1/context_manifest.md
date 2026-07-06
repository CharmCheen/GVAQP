# Context Manifest — Upstream Event-Diverse Discovery Redesign (v2)

**BASE_SEARCH_ROOT**: `/qiuyeqing/llama_prl/G-ARC`

**Date generated**: 2026-07-06

This document records the Context Assembly required by the task prompt. All items below were located by reading actual files; no paths or implementation details were assumed.

---

## 2.1 既有产出定位

### A) limited-oracle frontier
- **实际路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_limited_oracle_frontier_v1/`
- **状态**: 已确认
- **关键文件**: `README.md`, `FINAL_REPORT.md`, `limited_oracle_frontier_raw.csv`, `b90_90_by_segment.csv`, `precision_recall_frontier.csv`, `budget_grid.md`, `failure_taxonomy.csv`, `oracle_usage_report.md`
- **使用的 budget grid**: `RATIO_GRID=[0.05,0.10,0.20,0.30,0.40,0.50,0.75,1.00]` + `ABSOLUTE_GRID=[5,10,20,40,60,80,100,120]`，合并后 clip 到 `[1,N]`。
  - realcartest_0_1570 (N=157): `[5,8,10,16,20,31,40,47,60,63,78,80,100,118,120,157]`
  - realcartest_2000_3200 (N=120): `[5,6,10,12,20,24,36,40,48,60,80,90,100,120]`
  - realcartest_3200_3830 (N=63): `[3,5,6,10,13,19,20,25,32,40,47,60,63]`
- **Segment 列表**: `realcartest_0_1570`, `realcartest_2000_3200`, `realcartest_3200_3830`
- **Seed 数量**: 5 (`SEEDS=[0,1,2,3,4]`, `RANDOM_SEED_BASE=20260705`)
- **声称的关键结论**: 没有任何方法在 `<=30%` budget ratio 下达到 90/90；LATE-AQP-core 与 B7-core 在 B_90/90 上互有胜负（realcartest_3200_3830 段 LATE 落后）；低预算失败以 `discovery_miss` 为主；Core/Halo 是通用后处理增益。
- **与背景一致性核对**: 与任务第 0 节背景描述一致。

### B) cross-video frontier
- **实际路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_cross_video_frontier_v1/`
- **状态**: 已确认
- **关键文件**: `README.md`, `FINAL_REPORT.md`, `cross_video_frontier_raw.csv`, `cross_video_b90_90.csv`, `cross_video_precision_recall_frontier.csv`, `budget_grid.md`, `cross_video_failure_taxonomy.csv`, `cross_video_oracle_usage_report.md`
- **使用的 budget grid**: 同上 RATIO_GRID + ABSOLUTE_GRID。
  - dataset3_0_1200 (N=120): `[5,6,10,12,20,24,36,40,48,60,80,90,100,120]`
  - dataset3_1200_2400 (N=120): 同上
  - dataset3_2400_3462 (N=107): `[5,10,11,20,21,32,40,43,54,60,80,100,107]`
- **Segment 列表**: `dataset3_0_1200`, `dataset3_1200_2400`, `dataset3_2400_3462`
- **Seed 数量**: 5（与 A 相同）
- **声称的关键结论**: dataset3 上同样没有任何方法在 `<=30%` budget ratio 下达到 90/90；LATE-AQP-core 在 `dataset3_2400_3462` 段 B_90/90 输于 B7-core；低预算失败仍以 `discovery_miss` 为主。
- **与背景一致性核对**: 与任务第 0 节背景描述一致。

### C) core/halo attribution
- **实际路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_core_halo_attribution_v1/`
- **状态**: 已确认
- **关键文件**: `README.md`, `core_halo_attribution_summary.md`, `guard_efficiency_report.md`, `b6_b7_core_diagnostic_results.csv`, `core_halo_tradeoff.csv`, `core_halo_tradeoff_report.md`, `hardest_segment_casebook.md`
- **使用的 budget grid**: `[5,10,20,40,60,80,100,120]`
- **Segment 列表**: `realcartest_0_1570`, `realcartest_2000_3200`, `realcartest_3200_3830`
- **Seed 数量**: 5
- **声称的关键结论**: B6-core/B7-core 与 LATE-AQP-core 在可到达 90/90 的 segment 上完全相同；在 `realcartest_3200_3830` 上 B7-core 以 B=60 击败 LATE 的 B=80；guard 平均占预算 29.6%，B<=20 时占 41.4%。
- **与背景一致性核对**: 与任务第 0 节背景描述一致。

---

## 2.2 既有代码实现定位

### B6（chunk-level Thompson sampling baseline）
- **文件路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py`
- **函数名**: `run_b6(grid, budget, chunk_size_s, rng)`
- **位置**: 第 296–326 行
- **关键逻辑**: 时间轴切 chunk（chunk_size_s=120 s，bins_per_chunk=12），每 chunk 维护 `n_c` 采样次数与 `discovered_events`（以 `event_id` 计数 singleton）。Thompson sampling 用 `rng.gamma(shape=N1_c+0.1, scale=1/(n_c+1))` 选 chunk，再在 chunk 内随机选一个未采样 bin。
- **状态**: 已确认
- **与背景/文字描述的差异**: B6 实现依赖 `get_event_at_bin` 返回的 `event_id` 来更新 chunk 级别的 singleton 计数。该实现确实使用了 `event_id`，与前序报告中的 `posthoc_eval` 分类一致；若按严格 replay 标准则存在 label leakage，需在新实验中继承该分类。

### B7（B6 + simple temporal expansion）
- **文件路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py`
- **函数名**: `run_b7(grid, budget, chunk_size_s, k, rng)`
- **位置**: 第 329–394 行
- **关键逻辑**: 与 B6 相同的 chunk-bandit 选 bin；当选中 bin 为 positive 时，向左右邻域扩展最多 `k=3` 个 bin，直到两侧连续 k 个 bin 均为 negative 或预算耗尽。扩展时同样用 `event_id` 更新 chunk 计数。
- **状态**: 已确认
- **与背景/文字描述的差异**: 同 B6，使用 `event_id` 计数；扩展逻辑依赖 `get_label_at_bin`（即 oracle label）决定停止条件，这是允许的 runtime oracle feedback。

### Core/Halo release 实现
- **文件路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_core_halo_attribution_v1/run_attribution_analysis.py`
- **函数/类**: `perform_guards`, `compute_guard_need`, `run_b6_b7_core_halo`, `run_late_aqp_core_halo`
- **位置**: 第 95–228 行、第 250–357 行
- **关键逻辑**:
  - `MAX_GUARDS_PER_SIDE = 3`
  - Guard 只作用于包含至少一个 positive selected bin 的 interval。
  - 每侧最多向外扩展 3 个 bin；遇到 negative bin 立即停止。
  - Core = positive selected bins + 扩展中发现的 positive guard bins。
  - Halo = candidate intervals 中未被纳入 core 的部分（negative selected bins 等）。
  - Budget 迭代：先估计 `guard_need`，再调整 `discovery_budget`，保证 `discovery_budget + guard_need <= remaining_total_budget`。
- **状态**: 已确认
- **与背景/文字描述的差异**: 无显著差异；与 `core_halo_design.md` 描述一致。

### 当前 LATE discovery ledger 实现
- **文件路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_core_halo_attribution_v1/run_attribution_analysis.py`
- **函数名**: `run_discovery(grid, budget, queried)`（第 244–247 行）
- **关键逻辑**: 按 `prior_score_max` 降序选择未查询的 bin；即 pure prior-ranked discovery。
- **状态**: 已确认
- **与背景/文字描述的差异**: 无显著差异。该函数即为 LATE-D0-core 的 discovery 部分。

### 当前 LATE repair 机制实现
- **文件路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_core_halo_attribution_v1/run_attribution_analysis.py`
- **位置**: `run_late_aqp_core_halo` 函数内第 304–321 行
- **关键逻辑**:
  - 触发条件：`outside_positives` 非空且 `remaining = budget - audit_calls > 0`。
  - 对每个 outside positive seed，向其左右最近邻 bin（`seed-1`, `seed+1`）生成 repair action。
  - action 按 seed 的 `prior_score_max` 降序排序。
  - 依次消耗剩余 budget，将未查询的邻 bin 加入 `selected`。
- **状态**: 已确认
- **与背景/文字描述的差异**: 无显著差异。repair 不依赖 `event_id`，只依赖 outside audit 返回的 positive label 与 prior score。

### 去重/事件合并规则
- **文件路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py`
- **函数名**: `merge_bins(grid, bin_indices)`
- **位置**: 第 157–177 行
- **关键逻辑**: 将 bin index 集合排序后，相邻且时间连续的 bin（`abs(b_start - cur_end) < 1e-6`）合并为一个 interval。去重本质上由“选择不重复 bin index”保证；区间合并仅处理连续 bin。
- **状态**: 已确认
- **与背景/文字描述的差异**: 无显式“固定时间距离阈值”去重；合并阈值即 bin 的邻接关系（BIN_SIZE=10 s）。D1/D2/D3 若需要近似去重，应使用同样的 bin-level 邻接逻辑，不引入额外阈值。

### Budget accounting 实现
- **文件路径**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_core_halo_attribution_v1/run_attribution_analysis.py`
- **位置**: `run_late_aqp_core_halo` 第 260–357 行；`run_b6_b7_core_halo` 第 183–228 行
- **关键逻辑**:
  - LATE：分别计数 `audit_calls`, `repair_calls`, `discovery_calls`, `guard_calls`，并计算 `budget_accounting_error = budget - (audit + repair + discovery + guard)`。
  - B6/B7-core：计数 `selection_calls` 与 `guard_calls`，并计算 `budget_accounting_error = budget - (selection + guard)`。
  - 两个实现都通过迭代调整 discovery budget 使得总调用数不超过 budget。
- **状态**: 已确认
- **与背景/文字描述的差异**: 无显著差异。

---

## 2.3 数据路径定位

### realcartest

| 数据项 | 路径 | 状态 | 备注 |
|--------|------|------|------|
| full-VLM evaluation reference (non-dev) | `/qiuyeqing/llama_prl/G-ARC/experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv` | 已确认 | 列名：event_id, video_id, event_start, event_end, event_duration, ... |
| dev segment full-VLM reference | `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv` | 已确认 | 列名：event_id, video_id, t_start, t_end, absolute_t_start, absolute_t_end, duration, event_type, ... |
| dev segment atomic grid | `/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay/atomic_grid_10s.csv` | 已确认 | 列名：bin_id, video_id, t_start, t_end, absolute_t_start, absolute_t_end, label, event_id, boundary_start, boundary_end, prior_score_max, prior_score_mean, ... |
| prior score (RoadClip proxy) | `/qiuyeqing/llama_prl/G-ARC/experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv` | 已确认 | 列名：clip_id, video_id, segment_id, start_time, end_time, score_count, ... |
| atomic bin size | 10.0 s | 已确认 | `BIN_SIZE = 10.0` |
| segment 切分 | realcartest_0_1570: [0, 1570]<br>realcartest_2000_3200: [2000, 3200]<br>realcartest_3200_3830: [3200, 3830] | 已确认 | 来自 `run_attribution_analysis.py` 的 `SEGMENTS` |

### dataset3

| 数据项 | 路径 | 状态 | 备注 |
|--------|------|------|------|
| full-VLM evaluation reference (per-anchor) | `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/oracle_outputs/dataset3_full_center10_parsed.csv` | 已确认 | 列名：anchor_id, video_id, anchor_time, start_time, end_time, duration, label, event_start, event_end, event_start_absolute, event_end_absolute, event_type, ... |
| prior score + anchor 表 | `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv` | 已确认 | 列名：anchor_id, anchor_index, center_time_s, start_time_s, end_time_s, oracle_label, is_positive, event_cluster_id, ..., score_yolo_count, ... |
| atomic bin size | 10.0 s | 已确认 | 与 realcartest 一致，center-10 anchors |
| segment 切分 | dataset3_0_1200: [0, 1200]<br>dataset3_1200_2400: [1200, 2400]<br>dataset3_2400_3462: [2400, 3462.93] | 已确认 | 来自 `run_cross_video_frontier.py` |

---

## 2.4 综合状态

| 关键项 | 状态 |
|--------|------|
| A) limited-oracle frontier | 已确认 |
| B) cross-video frontier | 已确认 |
| C) core/halo attribution | 已确认 |
| B6 实现 | 已确认 |
| B7 实现 | 已确认 |
| Core/Halo 实现 | 已确认 |
| LATE discovery ledger | 已确认 |
| LATE repair 机制 | 已确认 |
| 去重/合并规则 | 已确认 |
| Budget accounting | 已确认 |
| realcartest 数据路径 | 已确认 |
| dataset3 数据路径 | 已确认 |

**结论**: 所有关键项均已确认，未发现未找到项，也未发现与任务背景描述相矛盾的结论。可进入第 3 节及后续步骤。

**需要注意的实现细节**:
1. B6/B7 使用 `event_id` 做 chunk 级别的 singleton 计数，因此在新实验中应继续标记为 `posthoc_eval`，与既有报告保持一致。
2. `merge_bins` 的去重逻辑基于 bin 邻接关系（10 s 连续）；D1/D2/D3 若需要近似去重，应复用同一逻辑，不得引入 event_id 或 GT label。
3. 既有 LATE repair 只对 outside audit positive 的 seed 向左右各扩展 1 个 bin；关闭 repair 时只需跳过该阶段，让 discovery 候选直接进入 release。
