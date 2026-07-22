# 04 — Experiment and Evaluation Protocol

## 1. 当前 pilot

```text
video: realcartest_2000_3200
length: 20 minutes
units: 120 × 10s
VLM-defined reference events: 20
pseudo-positive units: 32
oracle: replayed pseudo-oracle label
budgets: 5, 10, 20, 50, 80, 100
```

该 pilot 只能用于方法开发、failure diagnosis 和参数冻结，不能用于最终泛化结论。

## 2. 数据分层

### D0 — Development pilot

当前单视频。允许开发和一次性冻结参数，不进入最终 statistical claim。

### D1 — Internal cross-video validation

最低配置：

- 5–10 个独立 10–20 分钟 driving windows；
- 多路况、事件密度、白天/夜间、天气；
- video-level split；
- 至少两个视频完全不参与调参；
- 统一 event schema 与 human adjudication。

### D2 — External validity

至少一个外部数据来源。Nexar Dashcam Collision Prediction Dataset 可用于 collision/near-collision 外部验证，但事件 schema、视频长度和标签语义与当前 cut-in/pedestrian pilot 不同，必须单独报告，不得直接合并平均。

### D3 — Actor-centric subset

为 actor identity、type 和 relation probe 建立小规模精标子集。未建立前，不评估完整 graph claim。

## 3. Ground truth protocol

### 3.1 标注字段

```text
event_id
video_id
event_type
actor_id_or_set
start_time
canonical_anchor_time
core_start_time
core_end_time
end_time
risk_level
ambiguity_flags
annotator_id
adjudication_status
```

### 3.2 流程

1. 两名独立标注者；
2. 对 event existence、type、actor、canonical anchor、边界分别标注；
3. 争议事件由第三方 adjudicate；
4. 报告 event-level agreement、anchor time error、boundary IoU；
5. VLM reference 只作为 proposal，不自动成为 GT；
6. ambiguous anchor 进入 sensitivity analysis，不进入主 certificate。

## 4. Baselines

### 4.1 Native outputs

- ARC-refinement（每个预注册 threshold 单独视为 selector）；
- SUPG-RT-all-selected；
- SUPG-RT-confirmed-only；
- ABae-stratified-confirmed；
- Ours legacy / frozen LATE wrapper；
- MAP-anchor-only；
- 后续 Minimal SEHS。

### 4.2 Strengthened common-materializer baselines

对每个 acquisition policy 统一接 K3 BB-EM：

```text
ARC + BB-EM
SUPG + BB-EM
ABae + BB-EM
Ours legacy + BB-EM
MAP + BB-EM
Minimal SEHS + BB-EM
```

Planner 增量必须以 strengthened baselines 为主要比较。Native outputs 用于展示实际系统行为和 permissive segment tradeoff。

### 4.3 可选额外 baseline

- top-proxy ranking + BB-EM；
- uniform temporal sampling + BB-EM；
- component-first non-adaptive + BB-EM；
- Seiden-inspired exploration/exploitation sampler（若能在相同 oracle cost 与 replay 协议下公平实现）；
- oracle-informed planner ceiling，不作为实际 baseline。

## 5. 三类 ceiling（必须先做）

### 5.1 Candidate ceiling

拆成两个版本：

1. `Core candidate coverage ceiling`：每个人工 GT event 是否至少有一个 candidate core / component 与 canonical anchor 或 event interval 对应；
2. `Materializable candidate ceiling`：查询所有 candidate core 后，用固定 BB-EM 能达到的 event recall/F1。

若 core candidate ceiling <0.80，停止 planner 优化。

### 5.2 Budgeted oracle-informed planner ceiling

在固定 candidate/action space 和预算 B 下，允许使用 GT 选择动作，计算可达到的最大 unique-event recall。可用 exhaustive search（小 B）、dynamic programming 或 integer program。

报告：

```text
planner_regret(B) = ceiling_recall(B) - method_recall(B)
```

若 target budget 下 ceiling 本身 <0.70–0.75，当前 action space 不足，不应继续调 planner。

### 5.3 Materializer ceiling

固定真实 queried observations，允许 reference-aware optimal partition / dynamic programming，仅作为诊断 upper bound。它回答输出构造还剩多少空间，不能用于方法执行。

## 6. 指标

### 6.1 主指标

- `event_detection@overlap_any` precision / recall / F1；
- event-F1 AUC over budget；
- canonical-anchor recall（人工 GT 阶段）；
- cost-to-target quality。

`overlap_any` 的极低预算结果必须如实报告，即使 aggressive baseline 通过长 segment 获胜。

### 6.2 Boundedness 与边界

- IoU@0.3 / IoU@0.5；
- matched mean IoU；
- average / p90 / max duration；
- overcoverage ratio；
- returned-video seconds；
- event recall per returned minute。

这些指标提供语境，不能替代主指标。

### 6.3 Event cardinality

- prediction count error；
- overmerge multiplicity；
- references per predicted segment；
- segments per reference；
- duplicate prediction rate；
- oversplit rate。

### 6.4 Query efficiency

- unique events per query；
- queries per discovered event；
- positive anchor rate；
- oracle calls to F1/recall target；
- wall-clock；
- oracle token/human time if typed oracles differ。

### 6.5 Planner / probability diagnostics

- outcome Brier score / ECE；
- action-type yield；
- action mix by budget/video；
- planner regret to oracle ceiling；
- prior-wrong stress test。

### 6.6 Audit / certificate

- residual count MAE / bias / RMSE；
- confidence interval width；
- empirical coverage；
- stop decision false-stop rate；
- audit cost。

## 7. 公平性规则

1. 同一 UnitTable、reference、budgets、oracle semantics。
2. hidden label 只在 query 后读取。
3. reference 只用于 evaluation / diagnostic ceiling。
4. materializer 参数跨 selector 与 budget 固定。
5. baseline threshold 必须在 dev 上预注册；不能 test per-budget pick-best。
6. 所有方法报告 native 与 shared-materializer 结果。
7. typed oracle 需要统一成本单位或展示完整 Pareto frontier。
8. 若 baseline adapter 不支持原论文 guarantee，必须标记 `ADAPTED_NO_ORIGINAL_GUARANTEE`。
9. SUPG all-selected / confirmed-only 路径必须做 set/hash audit。
10. 结果表以 selector config 为键，不能只用 method name 合并多 threshold。

## 8. 参数与 split

- D0 用于开发与冻结；
- D1 dev 子集可进行一次性选择；
- D1 held-out 和 D2 绝不调参；
- 每次 config 变更需记录 decision ID；
- 若 cross-video 后改参数，旧 held-out 自动降级为 dev，必须新增 test videos。

## 9. 统计分析

- 统计单位是 video，不是 unit；
- 报告 video-level paired bootstrap 95% CI；
- 小样本同时报告每视频结果和 effect size；
- 比较 AUC、目标预算 recall/F1、review cost；
- 避免把 120 units 当 120 个独立样本；
- 多 event types 时报告 macro 与 per-type；
- 预注册主要比较，控制大量 threshold/variant 的多重试验解释。

## 10. Stress tests

1. Proxy-invisible events：将正例 proxy 设为低分或 0；
2. Clustered duplicate evidence：一个事件产生多个 positives；
3. Adjacent distinct events：测试 overmerge；
4. Long event vs short event；
5. Oracle noise；
6. Actor track fragmentation；
7. Type confusion；
8. Budget regimes：extreme low / medium / near-exhaustive；
9. Prior shift across videos；
10. Audit sampling under clustered residual events。

## 11. 必须输出的 artifact

每个 run：

```text
config snapshot
oracle_log.csv
candidate/hypothesis table
segments.csv
metrics.json/csv
sanity_checks.md
run_manifest.json
stdout/stderr log
```

每个 stage：

```text
FINAL_REPORT.md
metrics_by_run.csv
budget_curves.csv
per_video_summary.csv
claim_decision.md
artifact_hashes.csv
```
