# AGENTS.md — SQ-CRAQ 项目约定

> 这份文件是给 Codex（以及其他遵循 AGENTS.md 规范的 agent）的持久性上下文，
> 每次任务开始前会被自动读取。只写"不写就大概率会猜错"的内容，
> 通用的工程建议不放这里。任务级别的具体要做什么，见每次单独下发的 prompt。

## 项目是什么

长视频语义事件查询（AQP）研究项目，代号 SQ-CRAQ。核心目标：用低成本信号
在长视频里生成候选事件区间，用有限的 oracle（VLM/人工）预算审计和修复候选，
最终返回高 recall、高 precision 的事件片段。当前阶段目标是**跑出好的经验
recall/precision，不追求正式统计证书（formal guarantee）**。

## 当前主线（mainline）

LATE-AQP frontier（limited-oracle 严格重放下，对全-VLM 评估参考做对照），
由 `outputs/late_aqp_*` 系列的 13 个实验组成（见 `EXPERIMENT_REGISTRY.csv`），
覆盖从 frozen v1 cross-segment 验证 → 严格 limited-oracle frontier → 上游发现重设计
（D1/D2/D3/D3-norepair）→ D3 accounting 修复 → 跨视频验证 → 冷启动失败诊断与重设计
（v2 / hybrid，均失败）→ algorithm v3 审计/修复工具设计 → H7 校准包。

- **默认 selector**：`score_topk` + temporal NMS + duration cap。CILS 只能以
  ablation/独立对照的形式存在（见下"非负例"）。
- **默认 release module**：Core/Halo release（boundary guard `MAX_GUARDS_PER_SIDE=3`，
  core = positive selected + positive guard bins，halo 仅作诊断）。这是一个
  **generic post-processing gain**，不是 LATE-AQP 特有优势。
- **最强经验 baseline**（posthoc_eval）：**B7-core**（B7 chunk-bandit +
  temporal expansion + Core/Halo）。新发现策略应以此为对照目标。
- **最强 strict-replay 替代**：**D3-norepair-core**（chunk-bandit Thompson sampling、
  无 repair、Core/Halo release）。当比较不允许用 `event_id` 做选择时使用。
- **下一优先级方向**：**EC-AQP**（Event-Coverage AQP）— 见 `TASK_QUEUE.yaml` 的 T010。
  设计目标是从 per-interval precision/recall 转向 reference event set 上的
  event-coverage mass，并加 residual missing-mass 估计器。

## 非负例（Never）

```text
- 不要把 CILS 设为默认 selector。默认 selector 固定是
  score_topk + temporal NMS + duration cap。CILS 只能以 ablation/独立对照
  的形式存在。除非某次任务明确要求"重新评估 CILS 是否该转正"，
  否则不要改动这个默认值，也不要因为它"看起来更精细"就顺手换上去。

- 不要主动补全或"修复" certificate 相关的统计量
  （r_upper 作为有效上界、γ_lower、置信区间、sample-splitting 证明等）。
  如果代码里已经有这些字段的占位符或历史实现，除非任务明确要求，
  否则不要动它们，也不要认为它们"没写完"而去补充统计推导。

- 任何标记为 probe_set_v1（或未来标记为"独立探针集/frozen eval set"）
  的数据，只能用于只读评估，不能用于调参、选阈值、驱动任何 repair 或
  selector 的决策。如果某次任务的实现方式导致这批数据被用来调参了，
  停下来，在交付说明里明确指出这个问题，不要悄悄绕过。

- outside-envelope audit 产生的样本，如果被用来驱动 repair 决策，
  就不能同时被当作证明"repair 有效"的评估依据。决策用的样本和
  评估用的样本必须是不同批次，这条不是可选优化项，是硬约束。

- 不要宣称"LATE-AQP 击败 B7-core"或类似性能优势。当前 LATE 变体
  （D1/D2/D3/D3-norepair）均未在 B_90/90 上达到 strictly lower than B7-core。
  B7-core + Core/Halo 与 LATE-AQP-core 在 90/90 frontier 上是同位的。
  来源：outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md Q4。

- 不要把 Core/Halo 当作 LATE-AQP 特有优势。它是 generic post-processing gain；
  B6-core 和 B7-core 在同样 segment 上达到 90/90。
  来源：outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md。

- 不要在没有先修 D3 accounting bug 的情况下，从 pre-fix 数据推出
  "repair is net-negative" 这类结论。bug 已修
  （outputs/late_aqp_d3_accounting_fix_v1/），post-fix 结果是 neutral
  （D3-core-fixed 不比 D3-norepair-core 更好），不是 net-negative。
```

## 数据 / 来源标注规则

```text
任何 recall/precision/AUC 类数字，必须标注数据来源，例如：
  "center10_vlm_oracle_events" / "reference_events" /
  "probe_set_v1_vlm_oracle_reference" /
  "6_event_reference" / "expanded_reference" / "probe_set_v1"
不要写成裸的 "recall = 0.8"，必须带来源标签。
如果不同数据源上结论不一致，如实并列展示，不要挑好看的那个报告。

并标注 track：
  - strict_replay：LATE-AQP-core、D3-norepair-core（选择阶段不使用 event_id）
  - posthoc_eval：B6 / B7 / B6-core / B7-core（选择阶段使用 event_id）
来源：outputs/late_aqp_limited_oracle_frontier_v1/oracle_replay_isolation_audit.md。

不要使用以下措辞：
  - "true recall" / "ground truth recall" / "human ground truth recall"
  - "formal guarantee" / "certificate" / "statistical bound"
  - "signal X is significantly better than signal Y"（在 probe_v1 7-positive 范围上）
  - "expanded_reference validates the signal"（expanded_reference 为空）
  - "current probe media covers the full 66-minute realcartest video"（realcartest.mp4 缺失）
  - "any method reaches 90/90 at <=30% budget ratio"（在 realcartest / dataset3 上没有）
```

## VLM / GPU / 标注权限

```text
- 没有显式授权，不要跑 VLM / API / YOLO / GPU 推理。
  这适用于所有未来工作，包括 EC-AQP 原型。
- 不要下载数据集。
- 当前已有的 VLM 标注（oracle-relative，不是人标）：
  - outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv
    （local Qwen3-VL-32B，25/25 解析，7 oracle-positive）
  - outputs/late_aqp_low_budget_fix_v1/new_labels/
    （realcartest_5k 上的 VLM 标注，仅用于 v2 tuning）
  - center10_vlm_oracle_events.csv（realcartest 段）
  - reference_events.csv（dev 段）
  - dataset3_full_center10_parsed.csv（dataset3 段）
  这些都不可用于"ground truth recall"类陈述。
- H7 人工标注包已就绪（outputs/late_aqp_h7_long_event_v1/），
  但需要显式授权才能开始。
- probe_v2 扩展（T007/T008）已 block，等用户决策；不在主线上。
```

## 大型产物（large artifact）警告

```text
- 4 个 >100MB 的 CSV 当前被 git 追踪，总量约 1.4 GB：
  - src/garc_eval/outputs/cils_empty_return_root_cause_audit_v1/cils_rejection_trace.csv（610M）
  - src/garc_eval/outputs/cils_calibration_repair_smoke_v1/smoke_candidate_p_answer.csv（481M）
  - src/garc_eval/outputs/cils_calibration_repair_replay_v1/candidate_p_answer_by_policy.csv（187M）
  - src/garc_eval/outputs/synthetic_cheap_signal_downstream_validation_v1/synthetic_signal_candidates.csv（115M）
  完整清单和推荐动作见 outputs/state_sync_late_aqp_v1/large_artifact_manifest.md。
  在用户做"保留 / gitignore / 外置"决策前，不要动这些文件。
- LFS hook 已装但 git-lfs 不在 PATH 上。这些大文件目前以 plain blob 存在 git 历史中。
- try_or_no/videos/realcartest.mp4 缺失；不要尝试补齐。
- models/、data/、datasets/ 已在 .gitignore 中（不被追踪）。
- .mp4 / .png / .jpg / .pt / .npy / .tar 等大文件后缀已在 .gitignore 中。
```

## 目录与命名约定

```text
实验产出统一放在形如：
  outputs/<experiment_name>_v<N>/
  内含 FINAL_REPORT.md（人类可读总结）+ 原始数据/中间产物

新实验如果是已有实验的迭代版本，版本号递增（_v1 → _v2），
不要覆盖旧版本目录，旧版本保留作为对照。

agent loop state 文档（包括本文件）应在每次状态变更时更新。
- PROJECT_STATE.md：当前阶段、active conclusions、可用数据、时间轴
- HANDOFF.md：当前 safe state、待人工/无计算可做事项、最新重要产出、do-not-repeat
- TASK_QUEUE.yaml：任务列表，T010 是当前 active/highest
- CLAIMS_LEDGER.md：可以/不可以/待验证三类声明
- FAILURES.md：已尝试且失败/中性的路径
- EXPERIMENT_REGISTRY.csv：所有已注册的实验
- outputs/state_sync_late_aqp_v1/large_artifact_manifest.md：>50MB 产物清单
```

<!-- TODO（人工填写，Codex 不要猜）：
  - 实际的 lint / test / build 命令是什么
  - cheap feature 计算 / candidate lattice 生成的代码具体在哪个模块
  - VLM 调用是走 API 还是本地部署，配置在哪
  - EC-AQP 原型代码在哪个模块
  这几项我目前不确定具体路径和命令，写错了比不写更糟，
  请在首次使用前手动补上，避免 Codex 凭空猜测命令名或路径。
-->

## 不确定时怎么办

```text
遇到本文件或任务 prompt 都没覆盖的情况：
  - 需要一个具体阈值/采样参数：选合理默认值，在交付报告里写清楚假设和理由。
  - 找不到某个提到的已有模块/路径：先搜索确认是否改名/移动，
    确认不存在再新建，并在交付说明里注明。
  - 发现某个既有结论（比如"CILS value-add = neutral"）可能因为新证据
    需要重新评估：如实报告新证据，不要自己下结论说"应该翻案"，
    这类路线级判断留给人做决定。
  - 在 outputs/late_aqp_* 中找不到完整 lineage（source_action 多数为
    unknown_not_logged）：这是已知缺口，不要在没补 lineage 的情况下
    做因果归因。
```
