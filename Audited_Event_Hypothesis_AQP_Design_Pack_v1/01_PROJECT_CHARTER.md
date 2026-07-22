# 01 — Project Charter：研究问题、贡献层次与边界

## 1. 研究目标

设计一个用于长第一视角驾驶视频的预算受限语义事件查询系统。用户给定安全事件 schema，例如 cut-in、pedestrian crossing、near-miss；系统只能调用有限次数的 expensive oracle，并返回去重、边界有界、actor/type 可追踪的事件关系，而不是一组独立 positive clips。

目标查询结果：

```text
EventRelation(
  event_id,
  event_type,
  actor_id_or_set,
  start_time,
  core_start_time,
  core_end_time,
  end_time,
  risk_level,
  confidence,
  evidence_summary,
  verification_state,
  canonical_anchor_time
)
```

## 2. 核心研究问题

### RQ1 — Event materialization

在相同 sparse queried evidence 下，怎样避免 naive merge 导致的 overmerge、超长片段和错误 event cardinality？

### RQ2 — Hypothesis-space coverage

真实事件是否进入 cheap-proxy 构造的候选/hypothesis space？proxy 完全不可见的事件如何被候选外探索发现？

### RQ3 — Budgeted query planning

在当前 event-hypothesis state 下，应查询哪个 target、哪个 attribute，才能最大化单位 oracle cost 的新增事件覆盖或不确定性下降？

### RQ4 — Event completeness

如何在 discovery policy 高度自适应、有偏的情况下，独立估计尚未发现的事件数量或 event-recall lower bound？

### RQ5 — Driving semantics

actor identity、interaction phase、event type 和边界是否能作为查询状态，而不是最后一次 VLM 输出中的非结构化文本？

### RQ6 — Query acceleration

与 ARC、SUPG、ABae 等方法相比，系统能否以更少 oracle calls、更少 returned-video review time 达到相同 event-set quality？

## 3. 当前项目分层

### 3.1 当前可防守层：BB-EM

`BB-EM/K3` 是 selector-agnostic 的物理算子：

```text
ObservationTable + ProxyTable + CandidateTable
                    ↓
                   BB-EM
                    ↓
               EventRelation
```

K3 机制：

- queried positive unit 是 event anchor；
- 只有 gap 与 duration constraints 通过时才允许连接 anchors；
- queried negative unit 是 hard barrier；
- 不使用未查询 label；
- 不依赖特定 selector。

### 3.2 当前初步支持层：MAP-anchor-only

MAP 以 proxy-only temporal components 作为低成本 event hypotheses，优先跨 component 查询 anchor，并对未覆盖区域做 audit。Pilot 上它在共享 K3 的 strengthened-baseline 比较中改善 B=5/10/20 的 F1 和 unique-events-per-query，但不能声称在 B≤10 全面击败 native ARC。

### 3.3 顶会目标层：Audited Event-Hypothesis AQP

目标方法不只是 graph representation，而是以下完整闭环：

1. Event hypotheses 是 query execution state。
2. Typed probes 是 physical operators。
3. Planner 优化 event-level expected progress / cost。
4. Independent audit ledger 估计 residual missing-event mass。
5. Event-set materializer 将 observations 变成有约束的 EventRelation。

## 4. 已验证、部分支持与尚未成立

| Claim | 状态 | 证据要求 |
|---|---|---|
| positive clip evidence 不等于 event-level output quality | `PILOT_CONFIRMED` | Stage 0 fixed-evidence repair |
| K3 可替代复杂 C6 | `PILOT_CONFIRMED_PENDING_PATH_AUDIT` | 指标相同；需补 trigger count |
| negative observation 可作为 materialization barrier | `PILOT_SUPPORTED` | leave-one-out 有独立增量 |
| MAP component-first probing 改善低预算发现 | `PILOT_SUPPORTED` | shared-K3 strengthened baselines |
| MAP 全面优于 ARC/SUPG/ABae | `REJECTED_CURRENTLY` | B≤10 native ARC 反例 |
| actor-centric graph 提升 query planning | `HYPOTHESIS` | 尚无 actor-level replay |
| VOI planner 有增量 | `HYPOTHESIS` | 需 outcome calibration 与 regret experiment |
| residual event certificate 有效 | `HYPOTHESIS` | 需独立 audit + coverage validation |
| 统计 AQP guarantee | `NOT_AVAILABLE` | 当前 certificate 为 NO-GO/underpowered |

## 5. 旧论点废弃清单

以下内容不得继续作为论文 gap 或方法事实：

1. “时序相关会直接击穿 SUPG”。项目实验已不足以支持该绝对论断。
2. “ARC confidence 是普通 mean precision”。应以 ARC 原论文/源码的 relevant-clip confidence 语义为准。
3. “完整 C6 的 proxy valley、NMS、expansion 均有独立贡献”。Stage 0.6 不支持。
4. “Ours planner 已明显优于所有 baseline”。Stage 0.5 与 native ARC 低预算结果不支持。
5. “SEHS 已实现并有效”。当前只是部分组件与设计。
6. “有 missed-event risk certificate”。当前不存在通过验证的 certificate。

## 6. Scope

### 当前 scope 内

- 长驾驶视频中的稀有安全事件发现。
- binary unit oracle 的离线 replay。
- sparse observations 到 event segments 的 materialization。
- proxy component / temporal hypothesis 层的自适应查询。
- actor-centric schema 与 typed oracle 的后续扩展。
- 独立 audit sampling 与 residual event estimation。

### 当前 scope 外

- 端到端自动驾驶控制或 planning。
- 从头训练大型视频模型。
- 用单个 pilot 证明跨场景泛化。
- 以 clip-level top-K 为最终输出。
- 无校准 outcome model 的复杂 RL/GNN planner。
- 未经人工 adjudication 的强安全结论。

## 7. 成功标准

### Operator-level success

BB-EM 在至少 5 个独立视频和多个 acquisition policies 上，相对 common naive/gap-only materializer 稳定降低 overmerge 与 review duration，同时 event-F1 AUC 不下降。

### Planner-level success

在同 primitives、同 oracle、同 BB-EM、同预算下，Minimal SEHS-node 相对 `ARC-adapted + BB-EM` 至少提高 0.10 absolute event recall（预注册阈值，可在 test 前一次性修改），且 precision ≥0.80 或达到预注册 precision floor；至少两个 held-out 视频方向一致。

### Candidate-level success

人工 GT 下 candidate ceiling ≥0.80。若低于该值，停止优化 planner，先修 hypothesis construction。

### Certificate-level success

独立 audit estimator 在 simulation 与 held-out videos 上达到预注册 coverage（例如 nominal 90% upper bound 的 empirical coverage 接近 90%），并且 bias/variance 可接受。未达标时论文不得使用 guarantee/certificate 表述。

## 8. 论文贡献的两种可行终态

### 终态 A：稳健系统论文

- event materialization gap；
- BB-EM physical operator；
- MAP / Minimal SEHS 的实证 query acceleration；
- decoupled replay 与 cross-video validation。

### 终态 B：更强 AQP 论文

在终态 A 基础上增加：

- canonical-anchor event semantics；
- independent audit ledger；
- residual event mass estimator / recall bound；
- 在受限条件下的 adaptive-submodular 或 approximation analysis。

只有真实 evidence 支持时才选择终态 B。
