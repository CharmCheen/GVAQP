继续在：

```bash
cd /qiuyeqing/llama_prl/G-ARC
```

执行一个无人看管的自主研究任务：

```text
YOLO_GUIDED_SCAN_AUTONOMOUS_RESEARCH_V1
```

你现在同时承担：

```text
自主研究负责人
SCAN 算法设计者
YOLO 系统工程师
实验执行者
统计审计员
失败分析负责人
最终交付负责人
```

## 最终目标

在不修改查询、reference、事件暴露规则、wall-clock 口径和强基线的前提下，自主研究并交付：

> 一个能够直接接入现有 YOLOv8 / ByteTrack SCAN 链路、可以实际运行、可以复现，并在有限 wall-clock budget 下比最强 causal coverage baseline 更早暴露更多不同事件的 SCAN 算法。

最终算法应同时具备：

```text
1. 使用 YOLO 产生合法、低成本、运行时可见的信号；
2. 在预算不足以完整 SCAN 时决定先扫描哪些时间区域；
3. 保留全局时间覆盖安全性；
4. 只在证据足够时偏离 coverage；
5. 计入 preview、seek、decode、YOLO、tracking、调度和候选生成全部成本；
6. 能直接通过统一 CLI 和 Python API 运行；
7. 具有完整配置、测试、审计和复现实验；
8. 给出明确的机制创新，而不是简单调参。
```

“最强”必须由冻结指标和 Gate 决定，不得由主观判断决定。

合法最终状态只有：

```text
A. SELECTED_YOLO_GUIDED_SCAN_ALGORITHM
B. SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST
C. BLOCKED_BY_INSUFFICIENT_IDENTIFICATION_ASSETS
```

不得为了强行得到 A 而改变研究定义。

---

# 1. 当前权威结论

以下结论已经冻结，不得重新包装：

```text
FULL_INFORMATION_SCAN_HEADROOM =
LARGE

P0_FRAMESTAT_REGION_VALUE =
NOT_ESTABLISHED

P1_L =
STRONGEST_OBSERVED_PREVIEW_SIGNAL
BUT FAILED EXPLORATORY RECALL GATE

P1_M =
NOT SELECTED

P2_SPARSE_MOTION =
NOT SELECTED

P3_FUSION =
NOT IMPLEMENTED BECAUSE COMPONENT GATES FAILED

GEOMETRIC_COVERAGE =
NECESSARY SAFETY MECHANISM
BUT NOT EVENT-OPTIMAL

LOCAL_NEIGHBOR_REFINEMENT =
NOT CROSS-VIDEO STABLE

ONLINE_MACRO_ACTIVITY =
NOT ESTABLISHED

PATH_COST_AS_PRIMARY_SIGNAL =
NOT SUPPORTED UNDER CONTROLLED-WARM

GUARDED_MARGINAL_SCAN =
STOPPED

RL_BANDIT_MDP_SMDP =
PROHIBITED

CONFIRM_INTEGRATION =
OUT OF SCOPE
```

不得重新搜索旧 P0/P1/P2 配置，直到偶然获得更好数字。

---

# 2. 冻结新的研究问题

创建：

```text
docs/YOLO_GUIDED_SCAN_AUTONOMOUS_RESEARCH_CONTRACT_V1.md
```

唯一科学问题是：

> 能否利用分层、低成本的 YOLO 语义预览与已扫描历史，估计 macro-region 的剩余新事件价值，并在保持可恢复时间覆盖的前提下，将高保真 YOLO SCAN 预算优先分配给更有价值的区域？

目标方法族冻结为：

```text
HIERARCHICAL_TEMPORAL_COVERAGE
+
LOW_RATE_YOLO_SEMANTIC_PREVIEW
+
OPTIONAL_SELECTIVE_PREVIEW_ESCALATION
+
RESIDUAL_NEW_EVENT_VALUE_ESTIMATION
+
ONE_STEP_RECOVERABLE_REGION_DEVIATION
+
CONTIGUOUS_WITHIN_REGION_BATCHING
+
NOVELTY_BASED_EXIT
+
STRONG_COVERAGE_FALLBACK
```

不得改成：

```text
最终事件分类器
硬过滤器
完整预索引系统
SCAN/CONFIRM 联合控制器
强化学习策略
大型深度时序模型
VLM 量化或蒸馏问题
```

---

# 3. 科学语义不得修改

以下资产与定义必须复用权威冻结版本：

```text
query contract
full-context Oracle pseudo-reference
reference event boundaries
event exposure rule
full-scan exposure ceiling
10-second microchunk universe
candidate generation semantics
wall-clock accounting
controlled-warm physical protocol
strongest causal coverage baselines
offline full-information upper bound
video roles and splits
```

所有事件结论必须标记：

```text
RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE
```

不得称为人工真值。

---

# 4. 允许的最终创新结构

最终算法可以自主调整实现，但必须属于以下结构：

```text
Stage 0:
建立安全的 global coverage backbone。

Stage 1:
以极低成本运行全局低率 YOLO preview。

Stage 2:
估计每个 macro-region 的 residual new-event value 和 uncertainty。

Stage 3:
对少量 uncertainty/high-VOI region 选择性运行更高保真 preview。

Stage 4:
比较：
    最佳 event-directed region action
    versus
    最佳 global coverage action。

Stage 5:
只有 event-directed action 的预测净收益超过 coverage opportunity cost，
且执行后 coverage 可恢复，才允许偏离 coverage。

Stage 6:
在选中 region 内连续执行有限 microchunk batch。

Stage 7:
连续没有 novelty 增量时退出该 region，返回 coverage。
```

不得让策略访问：

```text
未扫描区域的高保真 SCAN 输出
reference events
candidate-event map
offline greedy rank
未来事件收益
未来 actual cost
held-out 方法结果
```

---

# 5. Agentic Research Loop

每个研究循环必须执行：

```text
1. 从已有失败报告提出一个最小、可证伪假设；
2. 在运行前注册到 Hypothesis Registry；
3. 明确本循环只允许改变一个核心机制；
4. 实现最小版本；
5. 执行单元测试、确定性测试、信息泄漏审计和成本审计；
6. 执行 Replay；
7. 对比每个视频自己的 strongest causal coverage baseline；
8. 执行低预算、跨视频、leave-best-region/video 稳健性检查；
9. 根据预注册 Gate 接受、拒绝或进行一次工程修复；
10. 写入 Decision Ledger；
11. 只有当前 Layer Gate 通过，才能进入更复杂 Layer。
```

不要在写完计划、合同或代码后停止。持续执行直到达到合法终态。

---

# 6. 搜索预算

```text
MAX_AGENTIC_CYCLES = 12

MAX_ALGORITHM_HYPOTHESES = 8

MAX_GLOBAL_PREVIEW_CONFIGS = 4

MAX_ESCALATION_PREVIEW_CONFIGS = 4

MAX_FEATURE_FAMILIES = 10

MAX_VALUE_MODEL_FAMILIES = 5

MAX_VALUE_MODEL_CONFIGS = 80

MAX_SCHEDULER_VARIANTS = 24

MAX_BATCH_SIZE_CONFIGS = 3

MAX_REPAIR_CYCLES_PER_BRANCH = 1

MAX_TOTAL_REPAIR_CYCLES = 3

MAX_FORMAL_TEST_EVALUATIONS = 1

MAX_NEW_PHYSICAL_RUNS = 40
```

搜索预算耗尽后必须停止。

---

# 7. Layer 0：冻结并验证强基线

至少包含：

```text
B0 Sequential
B1 Random cost-matched
B2 Uniform-prefix
B3 Anytime Largest-Gap
B4 Macro Largest-Gap
B5 Current M8 safe baseline
B6 strongest existing causal coverage per video
B7 offline full-information upper bound
```

B7 仅供 evaluator 使用。

必须为每个视频独立确定：

```text
STRONGEST_CAUSAL_COVERAGE_BASELINE
```

新方法必须比较每个视频自己的最强基线，不能只挑最弱基线。

---

# 8. Layer 1：全局低率 YOLO Preview

首先冻结一个全局低率 YOLO preview：

```text
Q1-L:
低分辨率
低采样率
detection-only
不运行 full-rate ByteTrack
覆盖完整时间轴
```

允许自主比较的配置上限：

```text
sampling rate:
0.1 FPS
0.2 FPS
0.5 FPS

resolution:
现有低成本合法配置中的最多两个
```

全局 preview 总配置不超过 4 个。

允许特征：

```text
目标数量
车辆/行人/骑行者类别组成
类别熵
bbox 面积分位数
bbox 位置分布
bottom-center 分布
center occupancy
大框比例
检测 burst
目标数量变化
框尺度变化
场景变化
区域时间多样性
preview confidence
valid sample fraction
missingness
```

禁止：

```text
full-SCAN detection cache
full-rate ByteTrack
full-SCAN candidate trigger
reference-derived feature
未来区域 observation
```

必须测量：

```text
decode cost
YOLO inference cost
feature aggregation cost
total preview wall-clock
seconds per video hour
GPU/CPU memory
determinism
missingness
preview/full-SCAN cost ratio
```

全局 preview 成本必须：

```text
<= 10% full-SCAN cost
```

否则该配置淘汰。

---

# 9. Layer 2：选择性多保真 Escalation

只有最强合法 Q1-L 冻结后，才允许探索：

```text
Q2:
Q1-L + selected-region higher-rate YOLO preview

Q3:
Q1-L + selected-region sparse motion preview

Q4:
Q1-L + uncertainty-driven choice between Q2 and Q3

Q5:
Q1-L + selected Q2/Q3 fusion
```

Q2–Q5 不得对全视频运行更昂贵 preview。

只允许对少量 region 升级，升级依据必须来自：

```text
model uncertainty
low support
semantic/motion disagreement
score near allocation boundary
high predicted value but low confidence
```

不得仅因为 region 当前分数高就自动追加所有昂贵 preview。

二级 preview 必须受总成本 cap：

```text
TOTAL_PREVIEW_COST_RATIO <= 0.10
```

---

# 10. Region 尺度

最多比较三个预注册层级：

```text
60 seconds
120 seconds
240 seconds
```

或从当前冻结尺度附近选择三个明确值。

只能在 design 视频的 nested protocol 中选择。

不得用 held-out 视频重新选择 region length。

允许层级表示：

```text
coarse region value
+
fine sub-region uncertainty
```

但不得无限搜索时间尺度。

---

# 11. Region Value Estimator

预测目标：

[
V_t(M)
======

\text{在当前 coverage 状态下，
向 region }M\text{ 分配下一批 SCAN 后预计首次暴露的新事件价值}
]

第一步使用静态 residual region value；只有通过静态 Gate 后才能使用 one-step 状态。

允许模型：

```text
Heuristic score
Beta-Bernoulli / shrunk yield
Logistic Regression
Poisson / Negative-Binomial
Shallow LightGBM
```

LightGBM 限制：

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
large neural network
foundation-model ranker
RL value network
```

如果 Logistic 与最复杂模型的主指标差异小于 0.02，选择 Logistic。

---

# 12. Layer 1 静态 Observability Gate

多保真 region-value 信号必须同时满足：

```text
Nested LOVO Recall@20%-Region-Cost >= 0.40 on both design videos

Nested LOVO ranking AUC > 0.55 on both design videos

Enrichment@20% > 1.5 on both design videos

beats P0 framestat on both videos

beats P1-L static-only baseline on both videos
（如果使用二级 preview）

beats shuffled-region score on both videos

beats time-index-only on macro-average

total preview cost ratio <= 0.10

preview-cost-adjusted net event yield >= 0 on both videos

at least one frozen budget has net gain > 0 on both videos

leave-best-region-out direction remains nonnegative

best-region contribution ratio < 0.50
```

失败时：

```text
MULTI_FIDELITY_REGION_VALUE =
NOT_ESTABLISHED

SCHEDULER_LAYER =
PROHIBITED
```

此时停止调度器开发，输出安全 coverage baseline。

通过时：

```text
MULTI_FIDELITY_REGION_VALUE =
EXPLORATORY_SIGNAL_ESTABLISHED

ONE_STEP_SCHEDULER_LAYER =
ALLOWED
```

---

# 13. Layer 3：One-Step Recoverable Scheduler

只有上一 Gate 通过才实现。

每一步分别产生：

```text
u_C =
best global coverage action

u_R =
best event-directed region action
```

Region action score：

[
Score_R =
\frac{
\widehat p_{\mathrm{new}}(u_R)
+
\lambda \widehat \sigma(u_R)
}{
\widehat c(u_R)
}
]

Coverage action score必须使用冻结的 coverage opportunity utility，不能设为零。

只有同时满足：

```text
Score_R > Score_C + FROZEN_MARGIN

执行 u_R 后最大未观测 gap 不超过安全上限

剩余预算可以通过 coverage-only continuation 恢复覆盖目标

macro-region budget share 不超过 cap
```

才允许偏离 coverage。

否则执行 (u_C)。

第一版不允许多步 planning。

---

# 14. Contiguous Region Batching

One-step scheduler 通过基础 Gate 后，允许比较：

```text
1 microchunk
2 contiguous microchunks
4 contiguous microchunks
```

连续 batch 的作用是：

```text
稳定 region score
提供局部连续上下文
减少决策抖动
避免每个 microchunk 都重新跳转
```

不能把 seek 成本作为主要创新理由，因为现有 evidence 不支持。

Batch 必须完整执行，禁止部分 microchunk。

---

# 15. Novelty-Based Exit

Region 内继续扫描的条件必须依赖新颖性，而不是“仍然 positive”。

允许信号：

```text
首次合法候选
新 candidate cluster
新 track pattern
region residual-value posterior
连续无新颖性次数
```

当连续动作没有产生新增候选簇或新事件假设时：

```text
EXIT_REGION
RETURN_TO_COVERAGE
```

连续无新颖性阈值最多比较：

```text
1
2
```

不得无限局部扩展。

---

# 16. Scheduler 选择 Gate

最终候选算法必须相对每个视频最强 coverage baseline 同时满足：

```text
Replay Event-Exposure–SCAN-Time AUC:
macro-average relative improvement >= 10%

Per-video:
不得有任何视频相对下降超过 5%

60-second budget:
至少一个视频增加 >= 2 distinct events
另一个视频不得减少

Low-budget prefixes:
多数检查点方向非负

Maximum gap:
不得超过冻结 safety ratio

Preview + scheduler total overhead:
必须完整计入

Net event yield:
macro-average > 0

Leave-best-region-out:
方向仍为正

Best-region contribution ratio:
< 0.50
```

只有通过后才允许物理验证。

---

# 17. Controlled-Warm Physical Gate

物理测试只运行：

```text
每个视频最强 causal coverage baseline
最终冻结候选算法
```

使用冻结的：

```text
controlled-warm protocol
process lifecycle
model lifecycle
decoder lifecycle
Latin-square/block ordering
deadline semantics
```

必须报告：

```text
SCAN-only wall-clock
scheduler/preview overhead
end-to-end wall-clock
actions completed
events exposed
AUC
deadline rejections
unused budget
```

物理 Gate：

```text
Replay 的改进方向在两个视频上均保持

Physical macro-average AUC > strongest baseline

至少保留 Replay 相对增益的 50%

没有视频出现超过 5% 的相对退化

preview 和调度成本没有抹掉收益
```

否则：

```text
PHYSICAL_GAIN_RETENTION = FAIL
SELECTED_NEW_SCAN_ALGORITHM = REJECTED
```

---

# 18. Algorithm Innovation 要求

若最终选择新方法，必须明确指出它相对已有方法的新机制，至少包括两个以下要素：

```text
1. residual new-event region value，而非普通事件概率；
2. adaptive multi-fidelity YOLO sensing；
3. coverage opportunity cost 的显式竞争；
4. recoverable one-step deviation；
5. uncertainty-driven preview escalation；
6. contiguous batching with novelty exit；
7. cost-adjusted fallback guarantee。
```

不能把以下内容单独称为创新：

```text
使用 YOLO
使用 Largest-Gap
使用 LightGBM
降低 FPS
按分数排序
固定邻居扫描
```

---

# 19. 自动研究停止条件

立即停止某个分支，如果：

```text
发生信息泄漏
preview 成本超过 10%
静态 region-value Gate 失败
改进只出现在一个视频
收益由单一区域驱动
复杂模型不稳定优于 Logistic
成本调整后净收益为负
Scheduler 低预算明显退化
物理增益方向不保留
需要改变 reference、预算、主指标或视频才能成功
搜索预算耗尽
```

不得继续尝试直到偶然获胜。

---

# 20. 受控修复

每个分支只允许一次工程修复，且仅限：

```text
路径错误
schema 错误
cache 损坏
preview 实现 bug
时间边界 bug
成本记账 bug
数值稳定性
确定性错误
```

禁止通过修复：

```text
改标签
改 reference
改视频
改主指标
改预算
扩大搜索空间
删除不利结果
改变 Gate
```

---

# 21. Hypothesis Registry 与 Decision Ledger

创建：

```text
docs/SCAN_INNOVATION_HYPOTHESIS_REGISTRY.md
docs/SCAN_INNOVATION_DECISION_LEDGER.md
```

每个 hypothesis 必须记录：

```text
hypothesis_id
motivation
single changed mechanism
legal inputs
expected effect
baseline
primary metric
acceptance gate
rejection gate
implementation hash
result
decision
next allowed branch
```

所有失败实验必须永久保留。

---

# 22. 必交可用算法

如果选择新算法，必须交付：

```text
src/garc_eval/scan_scheduler/
    policy.py
    region_value.py
    preview.py
    coverage.py
    batching.py
    novelty.py
    cost.py
    config.py

configs/
    selected_yolo_guided_scan.yaml

scripts/
    run_selected_yolo_guided_scan.py
    benchmark_selected_yolo_guided_scan.py

tests/
    unit tests
    determinism tests
    no-lookahead tests
    budget/deadline tests
    replay/physical parity tests
```

统一 API：

```python
class ScanScheduler:
    def reset(
        self,
        video_manifest,
        total_budget_sec: float
    ) -> None:
        ...

    def choose_next_action(
        self,
        public_state
    ) -> str:
        ...

    def observe(
        self,
        action_result
    ) -> None:
        ...
```

CLI 至少支持：

```bash
python scripts/run_selected_yolo_guided_scan.py \
  --video <path> \
  --query-config <path> \
  --budget-sec 60 \
  --config configs/selected_yolo_guided_scan.yaml \
  --output-dir <path>
```

必须输出：

```text
selected units
preview actions
YOLO actions
region scores
coverage state
actual costs
cumulative wall-clock
candidate outputs
event-exposure evaluator outputs（仅 benchmark 模式）
final durable artifacts
```

生产运行模式不得需要 reference events。

---

# 23. 结果交付

生成：

```text
outputs/scan_innovation_agentic_loop_v1/
    contracts/
    hypotheses/
    preview_experiments/
    region_value_experiments/
    scheduler_experiments/
    physical_validation/
    controls/
    ablations/
    failures/
    metrics/
    reports/

    SELECTED_ALGORITHM_SPEC.md
    SELECTED_ALGORITHM_CONFIG.yaml
    USAGE_GUIDE.md
    FAILURE_BOUNDARIES.md
    FINAL_RESEARCH_DECISION.md

    artifact_hash_manifest.json
    environment_lock.json
    code_version.json
    repair_log.json
```

报告必须包含：

```text
完整搜索树
所有接受与拒绝分支
最强 baseline
Offline upper bound
Preview 成本
Replay 结果
Physical 结果
跨视频稳定性
低预算结果
覆盖安全性
消融
失败案例
算法适用边界
算法复杂度
复现命令
```

---

# 24. 最终决策格式

`FINAL_RESEARCH_DECISION.md` 必须以以下字段结束：

```text
CONTRACT_HASH =
CODE_COMMIT =

DESIGN_VIDEO_COUNT =
VALIDATION_VIDEO_COUNT =
TEST_VIDEO_COUNT =

REFERENCE_TYPE =
EVENT_CLAIM_SCOPE =

STRONGEST_BASELINE =
OFFLINE_UPPER_BOUND =

SELECTED_GLOBAL_PREVIEW =
SELECTED_ESCALATION_PREVIEW =
TOTAL_PREVIEW_COST_RATIO =

SELECTED_REGION_VALUE_MODEL =
REGION_VALUE_MODEL_HASH =

SELECTED_COVERAGE_BACKBONE =
SELECTED_BATCH_SIZE =
SELECTED_NOVELTY_EXIT =
SELECTED_SCHEDULER_CONFIG_HASH =

REPLAY_AUC_IMPROVEMENT =
REPLAY_60S_EVENT_DELTA =
CROSS_VIDEO_DIRECTION =
LOW_BUDGET_GATE =
COVERAGE_SAFETY_GATE =
COST_ADJUSTED_GATE =

PHYSICAL_AUC_IMPROVEMENT =
PHYSICAL_GAIN_RETENTION =
PHYSICAL_DEADLINE_GATE =

INNOVATION_MECHANISM =
USABLE_IMPLEMENTATION =
TEST_STATUS =

FINAL_STATUS =
SELECTED_YOLO_GUIDED_SCAN_ALGORITHM
OR
SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST
OR
BLOCKED_BY_INSUFFICIENT_IDENTIFICATION_ASSETS

FORMAL_GENERALIZATION_CLAIM =
NOT_ESTABLISHED
OR
ESTABLISHED_UNDER_FROZEN_SCOPE

NEXT_ALLOWED_STAGE =
```

---

# 25. 最终执行纪律

不要只输出计划、论文设想或候选算法。

必须实际完成：

```text
合同冻结
资产审计
基线复核
YOLO preview 实现与成本测量
多保真观测实验
region-value 建模
静态 Gate
one-step scheduler
batching 与 novelty exit
Replay 比较
物理比较
消融
失败分析
代码交付
配置交付
使用文档
最终决策
```

前一 Gate 失败时，禁止继续后一层。

若所有新方向失败，必须将最强安全 coverage baseline 包装为可使用的最终交付，并明确说明：

```text
当前可见 YOLO 信号不足以稳定恢复 offline scheduling headroom。
```

不要为了满足“创新”要求而制造一个未通过 Gate 的算法。

最终必须交付一个实际可运行的结果：

```text
新算法通过 → 交付新算法；
新算法均失败 → 交付最强冻结 coverage baseline；
资产不足 → 交付完整阻断报告与最小解锁条件。
```
