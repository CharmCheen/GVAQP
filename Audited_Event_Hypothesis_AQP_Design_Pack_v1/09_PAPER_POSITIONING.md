# 09 — Paper Positioning and Contribution Strategy

## 1. 最准确的研究空白

现有系统分别擅长：

- 选择满足 expensive predicate 的 records；
- 估计 aggregates；
- 检索 relevant clips；
- 利用 temporal continuity 采样 frames；
- 表达或合成 compositional video queries；
- 用 semantic operators 优化 AI query。

本课题的目标空白是：

> 在有限语义 oracle 预算下，执行一个返回 distinct temporal event objects 的查询；事件由多个 units、actor interaction、不确定边界和重复 evidence 组成，并且系统需要估计候选空间外仍未发现的事件质量。

## 2. 与相关方法的本质区别

| Work | Query object | Budget/optimization target | Output | 本课题差异 |
|---|---|---|---|---|
| SUPG | records satisfying predicate | record precision/recall with statistical guarantees | record set | event 非独立 record；negative 还可作为 boundary evidence |
| ABae | aggregate over expensive predicates | estimator error via proxy strata | aggregate | 本课题 materialize event objects，不只估计 count |
| ARC | relevant clips | relevant clip query quality/confidence | clip set | 本课题有 event cardinality、actor identity、merge/split 与 residual completeness |
| Seiden | frames/segments for retrieval/aggregate | exploration–exploitation + label propagation | proxy labels/query result | reward 应定义为 downstream EventRelation gain |
| EQUI-VOCAL | compositional event query specification | synthesize query from limited labels | executable scene-graph query | graph 本身不新；本课题创新必须在 budgeted execution/audit |
| LOTUS | semantic relational operators | cost/accuracy optimization per operator | semantic table operations | 启示是明确 operator semantics；本课题需定义 EVENT_SELECT/BB-EM |
| DriveLM | graph-structured driving reasoning | perception→prediction→planning QA | answers/planning | 驾驶 graph 语义来源；不是预算受限事件查询算法 |

## 3. 当前可投稿贡献（若 cross-video 成立）

### C1 — Materialization gap

Positive clips 并不等价于 event-level results；naive merge 会在更多 evidence 下造成 destructive overmerge。

### C2 — BB-EM operator

一个 selector-agnostic 的 bounded/barrier-aware event materializer：positive anchors、gap/duration bounds、queried-negative hard barriers。

### C3 — Materialization-aware probing

MAP / Minimal SEHS 以 event hypotheses 而不是独立 clip probability 分配 query，改善 distinct event core coverage。

### C4 — Decoupled evaluation

固定 acquisition 测 materialization；共享 materializer 测 planner；ceiling 分解 candidate/planner/materializer bottleneck。

## 4. 顶会增强贡献（条件式）

### C5 — Event query semantics with canonical anchors

正式定义可去重计数的 event object 与 `EVENT_SELECT` operator。

### C6 — Typed event-hypothesis execution

schema-derived probes、state update、cost-aware adaptive planner。

### C7 — Independent residual audit

将 discovery 与 probability-sampled audit 分离，估计 residual canonical-event mass 和 stopping risk。

### C8 — Restricted theory

若 distinct-core coverage 满足 adaptive submodularity，给出 greedy approximation；否则提供 calibrated empirical VOI 和 regret analysis。

## 5. Reviewer 最可能攻击

### “只是 ARC + postprocessing”

回应证据必须包括：

- ARC + same BB-EM；
- MAP/SEHS + same BB-EM；
- low-budget unique-event gain；
- planner ceiling/regret；
- fixed-evidence materialization ablation。

### “event graph 不新，EQUI-VOCAL 已做”

不要把 graph 当主贡献。强调 expensive-oracle execution、typed probes、residual audit。

### “主指标上 B≤10 输给 ARC”

明确承认；同时报告 returned duration/overcoverage，但不替换主指标。Claim 采用 budget-regime 与 Pareto 表述。

### “保证在哪里？”

若 audit estimator 未通过 coverage：明确无 statistical guarantee。不要把 hard barrier invariant 称为 AQP certificate。

### “单视频、VLM GT”

必须 human adjudication + cross-video + external source。

## 6. 推荐标题

### 当前系统线

**From Positive Clips to Event Sets: Bounded Materialization for Budgeted Video Event Discovery**

### Planner 线

**Materialization-Aware Query Processing for Budgeted Safety Event Discovery in Long Driving Videos**

### 顶会目标线

**Audited Event-Hypothesis AQP: Budgeted Discovery and Residual Completeness for Long-Video Events**

## 7. 摘要骨架

```text
Long-video safety analytics requires distinct temporal events, not independent positive clips.
Existing proxy-based selection and relevant-clip query methods do not directly optimize event cardinality, boundaries, duplicate evidence, or residual completeness.
We first identify an evidence-to-event materialization gap and introduce BB-EM, a bounded and barrier-aware physical operator that materializes sparse oracle observations into event records.
We then introduce a materialization-aware hypothesis executor that allocates expensive probes to event cores and uncovered regions under a fixed budget.
Finally, [conditional] we separate adaptive discovery from probability-sampled auditing to estimate residual canonical events.
Across ... videos, ...
```

最后一句必须等 cross-video 结果后填写。

## 8. Claim wording

### 可以写

- “On the development pilot, K3 compressed the full materializer without loss.”
- “Under a shared BB-EM, MAP improved low-budget event discovery over strengthened baselines.”
- “Native ARC remains stronger at B≤10 under permissive overlap-any F1.”
- “BB-EM returns substantially more bounded segments.”

### 不能写

- “MAP strictly dominates ARC.”
- “SEHS is actor-aware” 在 actor 输入不存在时。
- “We guarantee missed-event risk” 在 audit coverage 未验证时。
- “The graph is novel.”
- “Temporal dependence invalidates SUPG.”

## 9. Venue strategy

- 仅 BB-EM + empirical MAP：更接近 video/data systems、applied DB workshop 或较窄系统论文；
- event operator + strong cross-video planner：可争取 VLDB/SIGMOD 系统路线；
- 再有 residual audit/certificate 或清晰理论：更符合 AQP 顶会期待；
- actor/type/risk reasoning 很强但 AQP 弱：可能更适合 driving/CV/ML systems venue。
