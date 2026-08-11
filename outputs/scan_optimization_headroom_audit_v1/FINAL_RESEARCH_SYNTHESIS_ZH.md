# SCAN 优化空间审计：最终研究综合

## 明确答案

**当前 SCAN 阶段存在很大的潜在调度空间，但现有公开可见信号还不足以形成一个稳定、跨视频一致的自适应调度器。**

已验证的不是“Largest-Gap 已经是新方法”，而是三件更重要的事：

1. 时间位置分配确实改变 distinct-event 暴露；
2. 真实 controlled-warm wall-clock 没有系统性吞掉逻辑收益；
3. 最大剩余空间来自“预测哪里有新事件”，不是继续添加几何 guard 或无条件邻域 refinement。

因此当前应保留简单 coverage baseline，停止实现完整 Guarded Marginal Scan；下一项真正有创新价值的工作应是**带几何可恢复约束的因果区域新事件价值估计**。

## 1. Headroom 实验结果

Replay 使用同一视频内统一绝对 deadline，对应 Sequential full-scan Q90
estimated cost 的 5/10/20/30/40/60/80/100%；Random 使用 50 个 seed。

| 视频 | Sequential grid AUC | 最强简单 causal | 最强 AUC | 增量 | Offline greedy | 已见剩余 headroom |
|---|---:|---|---:|---:|---:|---:|
| PSP_V0_SHORT | 0.5007 | Anytime Largest-Gap | 0.5296 | +0.0289 | 0.9039 | +0.3743 |
| PSP_V1_LONG | 0.5202 | Macro-region Largest-Gap | 0.5282 | +0.0080 | 0.8637 | +0.3355 |

这里的 Offline greedy 使用隐藏 pseudo-reference mapping，只是可实现的非因果比较器，不是数学最优上界。即便如此，它已经构成一个强证据：存在一个合法扫描顺序，远好于当前 causal baseline，因此“当前 SCAN 算子已经没有调度空间”被否证。

在相同 60 秒 estimated horizon 下：

| 视频 | 最强 causal | Replay AUC | Offline greedy AUC | 60 秒结束事件数（causal / oracle） |
|---|---|---:|---:|---:|
| PSP_V0_SHORT | Sequential | 0.1321 | 0.3539 | 15 / 49 |
| PSP_V1_LONG | Uniform-prefix | 0.0452 | 0.1946 | 18 / 68 |

这说明真正的剩余空间不是几个百分点：若能从公开观测中逼近事件价值，低预算事件数理论上仍可能提高约 3–4 倍。当前证据只证明“空间存在”，没有证明在线可达到该空间。

## 2. Physical 结果与含义

复用并冻结了已有 32 次 controlled-warm runs，给每个已完成 prefix 重放 visible-subset candidate 和 evaluator-only event mapping。

| 视频 | Policy | Physical Exposure AUC（4 blocks mean ± sd） | 相对 Sequential |
|---|---|---:|---:|
| PSP_V0_SHORT | Sequential | 0.1327 ± 0.0130 | 0 |
| PSP_V0_SHORT | Uniform | 0.0978 ± 0.0011 | −0.0349 |
| PSP_V0_SHORT | Largest-Gap | 0.0973 ± 0.0026 | −0.0355 |
| PSP_V1_LONG | Sequential | 0.0304 ± 0.0053 | 0 |
| PSP_V1_LONG | Uniform | 0.0497 ± 0.0007 | +0.0192 |
| PSP_V1_LONG | Largest-Gap | 0.0332 ± 0.0008 | +0.0027 |

长视频中 Uniform 相对 Sequential 的增量在四个 block 全为正，matched
60 秒 Replay 增量为 +0.0172，Physical 为 +0.0192，收益保留率约 1.12。
短视频中 Replay 与 Physical 都选择 Sequential；所有分散 coverage 方法在四个 block 都更差。

所以 H3 的正确结论是：**物理访问开销没有推翻 Replay 的 matched-budget 方向；真正的不稳定性来自视频上的事件空间分布差异。**

短视频前 10% unit 已包含 21.4% 的首次可暴露事件，而且 10–20% 区间没有新增首次暴露事件，这给 Sequential 造成了特殊的低预算优势。该现象是 evaluator-side 解释，不能成为在线策略的预知输入。

## 3. 几何与路径成本

Largest-Gap 在两个视频的所有 pre-full checkpoints 都显著降低最大未扫描 gap，因此 H1 机制成立；但几何改善不自动等于事件改善。

controlled-warm Q90 action costs：

| Path class | Q90 秒 |
|---|---:|
| backward seek | 1.2850 |
| forward long seek | 1.2854 |
| forward short seek | 1.3175 |
| contiguous | 1.2973 |
| initial | 4.5907 |

当前硬件/协议下 long/backward seek 并不比 contiguous 显著更贵。因此“Replay 好而 Physical 被 seek 吞掉”的假设在本数据上不成立，path-aware batching 暂时不是首要创新点。Macro batching 仍可能改变覆盖顺序，但其物理收益尚未直接运行。

## 4. 时间相关性与 refinement

观测相关性 `K_obs(d)` 在 10 秒时为 0.362（短）和 0.466（长），短视频约 40 秒降至 0.1 以下，长视频约 90 秒降至 0.1 以下；两视频平均经验 horizon 为 80 秒。

同一 pseudo-reference event 在相邻 10 秒 unit 延续的概率约为 9.7%，20 秒及以后为 0。因此最多只值得检查一个邻居，而且目标应是邻近**新事件**，不是延长同一事件证据。

宽泛 candidate/composite trigger 在长视频是负条件增益。只有 lateral-motion component 同时满足两视频正增益，合并邻居新事件风险比为 3.24。这个关联通过了“允许测试简单 refinement”的 gate，但并不等于调度收益。

固定 refinement 的关键结果：

| 方法 | 短视频 ΔAUC vs strongest coverage | 长视频 ΔAUC |
|---|---:|---:|
| LG + one neighbor | +0.0954 | −0.0404 |
| LG + two neighbors | +0.0954 | −0.0446 |
| C75-R25 | −0.0211 | +0.0082 |
| C50-R50 | +0.0082 | −0.0076 |
| Cover-then-refine | +0.0214 | −0.0175 |

没有一个固定策略同时提高两个视频。因此：

```text
FIXED_REFINEMENT_STABILITY = FAIL
GUARDED_MARGINAL_SCAN_GATE = STOP
```

这揭示了一个关键机制：**trigger 的局部关联不足以支付放弃全局 coverage 的机会成本。** 新算法不能写成“看到 lateral motion 就扫邻居”，必须比较邻域的预测新事件价值与当前最优全局 probe 的相对边际价值。

## 5. 应设计什么 SCAN 调度算法

当前证据支持的创新方向是：

```text
CAUSAL_EVENT_VALUE_WITH_RECOVERABLE_COVERAGE
```

建议的调度器不是继续叠加 M1–M9 规则，而是一个三层、可逐项消融的结构。

### 层 A：Anytime hierarchical coverage backbone

以 Uniform/Largest-Gap 作为无信息 fallback，维护最大未观测 gap 和 macro-region 覆盖债务。预算很低时先跨时间轴放置 probe；当 gap 已足够小后再连续填充局部 unit。该层不使用事件或未扫描观测。

### 层 B：因果 region new-event value

只用已扫描 unit 更新 region posterior：

\[
\widehat p_r^{\mathrm{new}}
=P(\text{next scan exposes a new event}\mid
\text{completed public observations in region }r).
\]

输入可以包含 detection/track count、center occupancy、bbox growth、lateral motion 和候选 novelty，但必须通过跨视频 shrinkage 或 UCB 保留不确定性。当前结果明确禁止把 raw candidate trigger 直接当作价值。

### 层 C：相对机会成本与可恢复 guard

对合法 action 计算：

\[
S(u)=
\frac{\widehat p^{\mathrm{new}}(u)+\beta\,\sigma(u)}
{\widehat c(\text{current},u)}.
\]

只有当局部邻居的 `S(u)` 高于最强全局 coverage probe，并且执行后仍能在剩余预算内恢复冻结的最大-gap 约束时，才允许 refinement。否则回退到 coverage backbone。局部扫描一旦连续没有 novelty posterior 增量就退出。

该设计的真正创新点是：

1. 优化 distinct-new-event，而不是 candidate mass；
2. refinement 与最强全局替代动作做相对比较；
3. 用 recoverability 约束而非固定 coverage/refinement 比例；
4. 在 region posterior 不可靠时自动退化为简单 coverage。

## 6. 当前应停止什么、继续什么

停止：

- 把 Largest-Gap 包装成普适事件方法；
- 无条件 one/two-neighbor refinement；
- 使用宽泛 candidate/P0 trigger；
- 继续实现完整 Guarded Marginal Scan 或 RL controller；
- 将 Offline greedy 称为最优上界。

继续：

1. 增加独立完整视频，至少让 region-value predictor 有跨视频验证；
2. 物理运行 Macro-region Largest-Gap，验证其 60 秒长视频 Replay 优势；
3. 先做一个校准的 causal region-value predictor，并与 time-index、shuffle、coverage-only 做严格对照；
4. predictor 通过后，只实现“相对全局替代动作”的 one-step refinement；
5. 只有它在独立视频上同时超过最强 coverage，才重新打开 Guarded Marginal gate。

## 最终状态

```text
SCAN_SCHEDULING_HEADROOM = LARGE_BUT_HIDDEN_INFORMATION_DEPENDENT
GEOMETRIC_COVERAGE_VALUE = REAL_BUT_VIDEO_DEPENDENT
PHYSICAL_GAIN_RETENTION = SUPPORTED_ON_LONG_VIDEO
PATH_COST_AS_PRIMARY_BOTTLENECK = NOT_SUPPORTED
HANDCRAFTED_TRIGGER_REFINEMENT = NOT_STABLE
CURRENT_RECOMMENDED_BASELINE = SIMPLE_ANYTIME_COVERAGE
NEXT_INNOVATION = CAUSAL_REGION_NEW_EVENT_VALUE_WITH_RECOVERABLE_COVERAGE
GUARDED_MARGINAL_SCAN = DEFERRED
```

这两视频足以回答“SCAN 是否值得继续研究”：**值得，因为 hidden-information greedy 与 causal baseline 的差距很大。** 但它们也否决了一个更诱人的错误结论：**不能靠再叠加几个局部 trigger/guard 就稳定吃到这部分 headroom。**

