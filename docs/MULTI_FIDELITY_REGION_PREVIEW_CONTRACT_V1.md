继续在以下仓库中工作：

```bash
cd /qiuyeqing/llama_prl/G-ARC
```

你现在作为本项目的自主研究工程师和受约束实验负责人，执行下一阶段：

```text
MULTI_FIDELITY_REGION_PREVIEW_OBSERVABILITY_AUDIT_V1
```

本阶段的目标不是直接设计新的 SCAN scheduler，而是回答一个前置问题：

> 在显式计入 preview 全量运行成本后，低帧率语义检测或稀疏运动 preview，能否稳定预测 macro-region 的剩余不同事件价值，并在相同总 wall-clock budget 下产生非负的净事件收益？

你可以在冻结实验空间内自主实现、运行、修复、消融和筛选 preview 方案，但不能重新定义研究问题、标签、主指标、成功条件或 claim scope。

---

# 1. 当前权威研究状态

以下结论已经冻结，不得重新解释：

```text
SCAN_HEADROOM =
LARGE_UNDER_FULL_INFORMATION

P0_FRAMESTAT_REGION_VALUE =
NOT_ESTABLISHED

P0_FIXED_FIDELITY_PROXY_TUNING =
CLOSED

GEOMETRIC_COVERAGE =
SAFE_FALLBACK_BUT_NOT_EVENT_OPTIMAL

LOCAL_TRIGGER_REFINEMENT =
NOT_STABLE

PATH_COST_AS_PRIMARY_SIGNAL =
NOT_SUPPORTED_UNDER_CONTROLLED_WARM

ONE_STEP_ALLOCATOR =
BLOCKED

GUARDED_MARGINAL_SCAN =
STOPPED

RL_BANDIT_MDP_SMDP =
PROHIBITED

NEXT_RESEARCH_STAGE =
MULTI_FIDELITY_PREVIEW_OBSERVABILITY_AUDIT
```

不得重新调 P0 framestat，不得在 P0 上增加更复杂 scheduler。

---

# 2. 首先创建并冻结合同

创建：

```text
docs/MULTI_FIDELITY_REGION_PREVIEW_CONTRACT_V1.md
```

合同必须写入本 Prompt 中的全部：

* 研究问题；
* preview 配置；
  -合法 feature；
  -禁止 feature；
  -标签；
  -主指标；
  -成本口径；
  -模型搜索空间；
  -搜索预算；
  -探索性 Gate；
  -停止条件；
  -claim scope；
  -必交产物。

训练或查看指标前，生成：

```text
contract_hash
code_commit
parent_asset_hashes
environment_lock
```

后续不得静默修改合同。

只允许一次受控工程修复周期，且不得借修复修改科学语义。

---

# 3. 自动定位并继承权威资产

主动定位并复用现有冻结资产：

```text
完整视频时间轴
10 秒 microchunk manifests
macro-region 构造代码
full-context Oracle pseudo-reference
reference event boundaries
full-scan exposure ceiling
visible-subset replay
candidate-event mapping
controlled-warm runtime traces
P0 MRPO 结果
最强 coverage baseline
offline full-information upper bound
```

优先参考：

```text
outputs/macro_region_proxy_optimization_v1/
outputs/scan_optimization_headroom_audit_v1/
benchmarks/partial_scan_pilot_v1/
benchmarks/partial_scan_pilot_v2/
```

不得重新构建或修改 reference，不得修改 event-exposure rule。

若多个资产版本冲突，使用 immutable manifest、最终审计报告和哈希链指向的权威版本，不得根据指标选择版本。

---

# 4. 数据角色

当前已物化的两个完整视频仅用于：

```text
DESIGN_ROLE =
EXPLORATORY_MECHANISM_SEARCH
```

不得形成正式模型选择或泛化结论。

冻结：

```text
DESIGN_VIDEO_COUNT = 2

FORMAL_VALIDATION_REQUIREMENT =
AT_LEAST_4_NEW_INDEPENDENT_COMPLETE_VIDEOS

FORMAL_TEST =
SEALED_AND_UNUSED
```

若仓库中不存在至少四个新增独立 validation 视频：

```text
FORMAL_STATIC_RANKING_GATE =
BLOCKED_INSUFFICIENT_VALIDATION_VIDEOS
```

但必须完成所有两视频 exploratory 工作。

---

# 5. 研究对象与标签

将视频划分为冻结 macro-regions：

```text
MACRO_REGION_LENGTH_CANDIDATES =
40s
60s
90s
120s
```

只能在两个 design 视频上选择一次 macro-region 长度，选择后冻结。

每个 reference event 按时间中点唯一映射到一个 macro-region：

[
t_k^{mid}
=========

\frac{t_k^{start}+t_k^{end}}{2}
]

[
region(E_k)=M_j
]

不得让同一事件在多个 region 重复计数。

主事件宇宙：

```text
EXPOSABLE_UNDER_FULL_SCAN_REFERENCE_EVENTS
```

同时报告：

```text
ALL_REFERENCE_EVENTS
UNEXPOSABLE_REFERENCE_EVENTS
FULL_SCAN_EXPOSURE_CEILING
```

构造：

### Binary label

[
Y_M^{binary}
============

\mathbf 1[Y_M^{count}>0]
]

### Count label

[
Y_M^{count}
===========

#{\text{该 region 中可由 full SCAN 暴露的不同 pseudo-reference events}}
]

所有报告必须注明：

```text
EVENT_CLAIM_SCOPE =
RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE
```

不得称为人工 ground truth。

---

# 6. Preview 配置

本轮只允许以下四个固定配置族：

```text
P0 =
EXISTING_FRAMESTAT_BASELINE

P1_L =
LOW_RATE_LOW_RESOLUTION_DETECTOR
TARGET_RATE_APPROX_0_2_FPS

P1_M =
SAME_DETECTOR
TARGET_RATE_APPROX_0_5_FPS

P2 =
SPARSE_LOW_COST_MOTION_PREVIEW
TARGET_RATE_APPROX_1_FPS
```

P3 融合仅在 P1 和 P2 至少各有一个配置通过单独信号 Gate 后允许：

```text
P3 =
SELECTED_P1_PLUS_P2
```

不得一开始实现 P3。

## P1 要求

允许：

* 冻结轻量 detector；
* 低采样率；
* 低分辨率；
* detection only；
* 目标数量和类别组成；
* bbox 尺寸与空间位置；
* center occupancy；
* detection burst；
* 目标尺度变化；
* 时间聚合统计。

禁止：

* 使用 high-fidelity SCAN detection cache；
* full-rate ByteTrack；
* full-rate tracking；
* P1/P2 历史失败分支中的复杂轨迹链；
* Oracle 或 reference 信息。

## P2 要求

允许：

* 低率帧差；
* 稀疏运动强度；
* 横向/纵向运动统计；
* motion burst；
* active-area ratio；
* scene-change；
* 低成本方向直方图；
* 合法压缩域 motion 信息。

禁止：

* 完整高质量 optical flow；
* SLAM；
  -深度视觉里程计；
  -车道恢复；
  -YOLOP；
  -高保真相机运动补偿链。

## Preview 成本

完整 preview 必须覆盖整条视频时间轴，并显式付费。

记录：

```text
decode_time_sec
model_time_sec
feature_time_sec
total_wallclock_sec
seconds_per_video_hour
peak_cpu_memory
peak_gpu_memory
determinism
missingness
```

计算：

[
preview_cost_ratio
==================

\frac{C_{\mathrm{preview}}}
{C_{\mathrm{full\ SCAN}}}
]

硬 Gate：

```text
MAX_PREVIEW_COST_RATIO = 0.10
```

超过 10% full-SCAN 成本的配置不得成为主候选。

---

# 7. 合法 feature universe

最多八个 feature families：

```text
F1_OBJECT_OCCUPANCY
F2_CLASS_COMPOSITION
F3_BBOX_GEOMETRY
F4_LOW_COST_MOTION_AND_CHANGE
F5_TEMPORAL_AGGREGATION
F6_SCENE_DIVERSITY_AND_NOVELTY
F7_PREVIEW_ONLY_WEAK_QUERY_TRIGGERS
F8_SUPPORT_AND_RELIABILITY
```

允许的聚合：

```text
mean
max
top-k mean
quantiles
variance
temporal slope
burst count
change-point count
early/middle/late contrast
feature diversity
valid-sample fraction
missingness indicators
```

禁止输入：

```text
video_id
session_id
source_id
filename
absolute region index
normalized absolute time
reference event count
reference event ID
candidate-event mapping
full-SCAN detection/track/candidate features
offline greedy rank
future reward
future cost
test split
method result
```

`time-index-only` 只能作为负对照，不能进入主模型。

为所有 feature 生成 legality audit：

```text
feature_name
feature_family
source_preview
runtime_visibility
cost
missingness
uses_reference
uses_full_scan
uses_future_information
legality_status
```

发现泄漏立即删除并记录，不得替换成近似泄漏字段。

---

# 8. 模型空间与自主搜索权限

允许模型：

```text
HEURISTIC_SCORE
LOGISTIC_REGRESSION
POISSON_REGRESSION
NEGATIVE_BINOMIAL
SHALLOW_LIGHTGBM
```

LightGBM 约束：

```text
max_depth <= 4
num_leaves <= 15
min_child_samples >= 10
n_estimators <= 300
```

禁止：

```text
TCN
GRU
LSTM
Transformer
large neural networks
foundation-model preview
RL
Bandit
MDP
SMDP
```

搜索预算：

```text
MAX_PREVIEW_OPERATOR_CONFIGS = 4
MAX_FEATURE_FAMILIES = 8
MAX_MODEL_FAMILIES = 5
MAX_PRIMARY_CONFIGS = 50
MAX_REPAIR_CYCLES = 1
```

Codex 可以自主：

* 构造合法 preview feature；
* 选择 design-only macro-region length；
* 比较合法聚合；
* 调允许范围内的超参数；
* 做 feature-family ablation；
* 做成本敏感性；
* 做 nested leave-one-video-out；
* 分析错误 regions；
* 提出候选假设。

Codex 不可以：

* 修改 label；
* 修改 reference；
* 修改主指标；
* 修改预算；
* 删除不利视频；
* 修改 baseline；
* 增加搜索预算；
* 根据某个视频结果修改 preview；
* 将候选假设自动升级为主线。

如果 Logistic 与复杂模型的 `Recall@20%` 差异小于 0.02，选择 Logistic 并停止复杂模型搜索。

---

# 9. Baselines 与 Controls

必须运行：

```text
B0_RANDOM_COST_MATCHED
B1_CONSTANT_GLOBAL_RATE
B2_REGION_COST_ONLY
B3_TIME_INDEX_ONLY
B4_BEST_P0_FRAMESTAT
B5_BEST_UNIVARIATE_PREVIEW_FEATURE
B6_STRONGEST_GEOMETRIC_COVERAGE_REGION_ORDER
B7_SHUFFLED_LABEL
B8_SHUFFLED_REGION_SCORE
B9_OFFLINE_FULL_INFORMATION_REGION_ORDER
```

其中：

```text
B9 =
EVALUATOR_ONLY_UPPER_BOUND
```

不得进入模型输入或部署候选。

Random 至少：

```text
100 FIXED SEEDS
```

---

# 10. 主指标

主指标：

```text
Distinct-Event Recall@Top-20%-Region-Cost
```

按 region score 从高到低选择完整 region，累计 high-fidelity region SCAN cost，直到达到：

[
0.20\times C_{\mathrm{all\ regions}}
]

规则：

* 不允许部分选择 region；
* 下一 region 超预算时停止；
* 报告实际使用的 cost fraction；
* 主指标分母为全部 exposable residual distinct events。

同时计算 cost-matched random enrichment：

[
Enrichment@20%
==============

\frac{Recall@20%*{\mathrm{model}}}
{\mathbb E[Recall@20%*{\mathrm{random}}]}
]

不得假设 random recall 等于 20%。

---

# 11. 次指标

必须报告：

```text
Recall@10%-Region-Cost
Recall@30%-Region-Cost
Region-Ranking Event-Recall AUC
Binary AUPRC
Binary Brier Score
Count MAE
Spearman rank correlation
Nested leave-one-video-out metrics
Per-video direction
Leave-best-region-out
Best-region contribution ratio
Preview cost ratio
Net Event Yield after Preview Cost
```

---

# 12. 成本调整后的净事件收益

在冻结总 wall-clock budget (B) 下：

```text
支付完整 preview 实际成本
→ 用剩余预算按 region rank 执行 frozen high-fidelity scan
→ region 内使用冻结几何顺序
→ 计算首次暴露的不同 pseudo-reference events
→ 与相同总预算 strongest coverage baseline 比较
```

定义：

[
\Delta U_B
==========

## U_{\mathrm{preview\ ranker}}(B)

U_{\mathrm{coverage}}(B)
]

至少评价：

```text
60 seconds
20% full-SCAN cost
30% full-SCAN cost
```

若某预算小于 preview 成本：

```text
BUDGET_CELL = INFEASIBLE_PREVIEW_COST
```

不得伪造为零收益。

---

# 13. 执行 Phase

## Phase 0：只读资产与标签审计

回答：

```text
完整视频数量
每个视频时长
microchunk 数
各 macro-region 长度的 region 数
每个视频 exposable event 数
binary positive-region rate
count distribution
preview operator 可执行性
full-SCAN 成本
reference completeness
```

不得训练。

## Phase 1：Preview observability 与成本

实际运行 P0、P1-L、P1-M、P2。

每个配置至少重复两次，验证：

```text
feature hash stability
output determinism
missingness
runtime
cost ratio
full timeline coverage
```

## Phase 2：Univariate headroom

每个合法 feature 单独排序，计算：

```text
Recall@10/20/30
Enrichment
AUC
per-video direction
cost
```

若所有单特征均无信号，仍允许简单组合，但禁止扩大模型族。

## Phase 3：Simple-model search

在合同搜索预算内自主搜索。

必须使用 nested leave-one-video-out，防止 macro-region length、feature schema 和超参数在 held-out 视频上选择。

## Phase 4：探索性 Gate

当前两个视频只能输出：

```text
CANDIDATE_MULTI_FIDELITY_PROXY_HYPOTHESIS
```

或：

```text
MULTI_FIDELITY_PREVIEW_SIGNAL = NOT_ESTABLISHED
```

不得输出正式模型选择。

## Phase 5：Formal validation

只有存在至少四个新增独立 validation 视频才运行。

否则：

```text
FORMAL_STATIC_RANKING_GATE =
BLOCKED_INSUFFICIENT_VALIDATION_VIDEOS
```

## Phase 6：Allocator

本阶段禁止实现。

只有未来 formal Static Ranking Gate 通过，才允许另立合同研究 one-step allocator。

---

# 14. 探索性 Gate

一个 preview candidate 只有同时满足以下条件，才可保留为候选假设：

```text
Recall@20% >= 0.40 on both design videos
Enrichment > 1.5 on both design videos
Nested LOVO Recall@20 > P0 on both videos
Nested LOVO AUC > 0.55 on both videos
beats shuffled score on both videos
beats time-index on macro-average
preview cost ratio <= 0.10
net event yield >= 0 on both videos
at least one frozen budget has net yield > 0 on both videos
leave-best-region-out direction remains nonnegative
```

通过：

```text
MULTI_FIDELITY_PREVIEW_SIGNAL =
CANDIDATE_HYPOTHESIS

ONE_STEP_ALLOCATOR =
BLOCKED_PENDING_FORMAL_VALIDATION
```

失败：

```text
MULTI_FIDELITY_PREVIEW_SIGNAL =
NOT_ESTABLISHED

REGION_DIRECTED_SCAN =
CLOSED_UNDER_CURRENT_VISIBLE_SIGNALS
```

---

# 15. Formal Gate

只有至少四个新增独立 validation 视频时运行。

必须满足：

```text
Macro Recall@20% >= 0.50
Macro Enrichment@20% >= 2.5
Recall@20% >= 0.40 on majority of videos
nonnegative enrichment on >=75% videos
beats heuristic, shuffled and time-index controls
leave-best-video-out delta > 0
best-video contribution < 0.50
best-region contribution < 0.50
preview cost ratio <= 0.10
net event yield > strongest coverage baseline
low-budget prefixes not systematically worse
```

通过：

```text
REGION_VALUE_PROXY_SIGNAL = ESTABLISHED
ONE_STEP_ALLOCATOR = ALLOWED
```

失败：

```text
REGION_VALUE_PROXY_SIGNAL = NOT_ESTABLISHED
MULTI_FIDELITY_PREVIEW_TUNING = STOP
NEXT_STAGE = NEW_POLICY_VISIBLE_SIGNAL_OR_SAFE_COVERAGE_BASELINE
```

---

# 16. 停止规则

立即停止该配置或分支，如果：

```text
preview cost ratio > 0.10
feature leakage detected
所有模型 Recall@20% < 0.40
没有模型在两个 design 视频上都超过 P0
改进只发生在一个视频
收益由单一 region 驱动
净事件收益在任一 design 视频始终为负
复杂模型没有稳定超过 Logistic
需要修改 label/reference/budget/metric 才能改善
搜索预算耗尽
```

不得继续尝试直到偶然得到高分。

---

# 17. 受控修复

只允许一次受控修复周期，且仅限：

```text
路径错误
schema 错误
preview 实现 bug
时间边界 bug
成本记账 bug
cache 损坏
数值稳定性
确定性问题
```

禁止借修复：

```text
修改 label
修改 reference
修改主指标
修改 Gate
增加模型
增加 preview 配置
删除不利视频
```

修复必须记录：

```text
issue
root cause
affected artifacts
before hash
after hash
experiments rerun
claim impact
```

---

# 18. 失败分析

必须生成：

```text
高分无事件 regions
低分高事件 regions
跨视频冲突
feature missingness
time-index confounding
preview cost decomposition
single-region contribution
offline-oracle missed-headroom decomposition
P0 vs P1/P2 disagreement
model vs heuristic disagreement
```

所有新方向只能标记：

```text
CANDIDATE_HYPOTHESIS
```

不得自动升级。

---

# 19. 必交产物

生成：

```text
docs/MULTI_FIDELITY_REGION_PREVIEW_CONTRACT_V1.md

outputs/multi_fidelity_region_preview_v1/
    contracts/
        frozen_contract.json
        preview_contracts/
        feature_contract.json
        metric_contract.json
        search_budget.json

    audits/
        asset_audit.json
        label_audit.json
        feature_legality_audit.json
        preview_cost_audit.json
        determinism_audit.json
        leakage_audit.json
        completion_matrix.md

    preview/
        p0/
        p1_l/
        p1_m/
        p2/
        runtime_samples/

    features/
        region_features.parquet
        feature_schema.json

    labels/
        region_binary_labels.parquet
        region_count_labels.parquet
        event_region_map.parquet

    experiments/
        univariate/
        models/
        controls/
        ablations/
        macro_region_sensitivity/

    predictions/
        nested_lovo_predictions.parquet
        region_scores.parquet

    metrics/
        ranking_metrics.json
        cost_adjusted_metrics.json
        net_event_yield_budget_grid.csv
        per_video_metrics.csv
        per_region_metrics.csv
        random_baseline_distribution.json

    reports/
        PHASE0_ASSET_AND_LABEL_AUDIT.md
        PREVIEW_OBSERVABILITY_REPORT.md
        UNIVARIATE_HEADROOM_REPORT.md
        SIMPLE_MODEL_SEARCH_REPORT.md
        FEATURE_ABLATION_REPORT.md
        COST_ADJUSTED_RANKING_REPORT.md
        FAILURE_ANALYSIS.md
        FINAL_PREVIEW_DECISION.md

    repair_log.json
    environment_lock.json
    code_version.json
    artifact_hash_manifest.json
```

---

# 20. 最终决策格式

`FINAL_PREVIEW_DECISION.md` 必须以以下字段结束：

```text
CONTRACT_HASH =
CODE_COMMIT =

VIDEO_COUNT =
DESIGN_VIDEO_COUNT =
VALIDATION_VIDEO_COUNT =
TEST_VIDEO_COUNT =

REFERENCE_TYPE =
REFERENCE_COMPLETENESS_STATUS =
EVENT_CLAIM_SCOPE =

P0_STATUS =

P1_L_OPERATOR =
P1_L_COST_RATIO =
P1_L_GATE =

P1_M_OPERATOR =
P1_M_COST_RATIO =
P1_M_GATE =

P2_OPERATOR =
P2_COST_RATIO =
P2_GATE =

P3_STATUS =
NOT_IMPLEMENTED
OR
IMPLEMENTED_AFTER_COMPONENT_GATES

SELECTED_PREVIEW_CANDIDATE =
NONE
OR
P1_L
OR
P1_M
OR
P2
OR
P3

MACRO_REGION_LENGTH =
FEATURE_SCHEMA_HASH =
MODEL_FAMILY =
MODEL_CONFIG_HASH =

PRIMARY_RECALL_AT_20 =
PRIMARY_ENRICHMENT_AT_20 =
NESTED_LOVO_RECALL_AT_20 =
NESTED_LOVO_AUC =
PREVIEW_COST_RATIO =
NET_EVENT_YIELD =
CROSS_VIDEO_DIRECTION =
LEAVE_BEST_REGION_OUT =
BEST_REGION_CONTRIBUTION =

EXPLORATORY_GATE =
FORMAL_STATIC_RANKING_GATE =
MULTI_FIDELITY_PREVIEW_SIGNAL =

SELECTED_PROXY_STATUS =
CANDIDATE_HYPOTHESIS
OR
NOT_ESTABLISHED
OR
FORMALLY_SELECTED

ONE_STEP_ALLOCATOR_STATUS =
BLOCKED
OR
ALLOWED

GUARDED_MARGINAL_STATUS =
STOPPED

FORMAL_METHOD_RANKING =
BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION

NEXT_ALLOWED_STAGE =
```

---

# 21. 执行纪律

不要只写合同或代码后停止。

必须实际完成所有当前合法的：

```text
资产审计
preview 实现
preview 全量运行
成本测量
确定性复测
feature 合法性审计
univariate 搜索
simple-model 搜索
controls
nested LOVO
feature ablation
成本调整后的净收益评价
失败分析
最终决策
artifact hash
独立 completion audit
回归测试
```

若 formal validation 因视频不足被阻断，完成全部 exploratory 工作后停止，不得降低正式 Gate。

不得实现 one-step allocator、contiguous batching、Guarded Marginal、RL、Bandit、SMDP 或 CONFIRM。

最终结论必须由冻结 Gate 自动产生，不得自行选择更有利的解释。
