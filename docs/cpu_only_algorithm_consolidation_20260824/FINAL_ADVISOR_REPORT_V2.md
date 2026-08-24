# GVAQP 新方向阶段汇报

## 先发现，再验证：未扫描视频上的硬截止开放语义事件查询

**English working title:** *Discovery Before Verification: Deadline-Safe Open-Semantic Event Queries over Unscanned Video*

**Date:** 2026-08-24  
**Research status:** `IDEA_AND_CPU_CONTRACT_READY / CLAIM_EVIDENCE_INCOMPLETE`  
**Target audience:** SIGMOD/VLDB 方向导师讨论  
**Current execution constraint:** CPU only

---

## 摘要

本项目研究长视频上的开放语义查询。用户以自然语言描述需要查找的事件，系统需要在有限预算或硬截止时间内，从尚未完整扫描的视频中返回经过语义确认、去重并持久化的事件结果。现有视频查询系统已经能够利用代理模型、语义索引、自适应采样或模型级联减少视觉推理成本，但大多默认待查询帧、候选集合或索引已经存在。该假设忽略了一个关键执行依赖：在未扫描视频中，候选并不是预先给定的，扫描新区域会创造未来可验证的候选，而验证已有候选又会消耗继续发现事件的预算。

我们据此将问题重新表述为因果候选前沿上的查询执行问题。系统状态不仅包含当前候选分数，还包含尚未扫描的时间区域、已暴露候选以及已经持久化的事件关系。SCAN 操作扩展未来可执行动作集合，VERIFY 操作只能消费已经暴露的候选，只有在截止时间前完成确认并原子提交的独立事件才产生查询效用。基于这一结构，我们实现了确定性的 Deadline-Aware Temporal-Bisection SCAN/VERIFY 算法，简称 DATB-SV。该算法使用广度优先时间二分实现早期时间覆盖，以固定比例交替执行发现和验证，并通过保守时延上界与提交预留保证截止语义。

当前 CPU 实现已经通过调度顺序、预算准入、事件去重、截止后不可变性和 oracle 来源不变性测试，也完成了合成端到端回放。但这些结果仅证明执行合同成立，尚未证明 DATB-SV 在真实工作负载上优于基线。现有语料仅包含 3 个视频和 2 个查询，形成 6 个交叉 video-query 单元，不能支持广泛泛化结论。下一阶段首先恢复或正式退役历史 endogenous scan preflight 的 provenance，随后进行 evaluator parity audit 和以事件稀疏度、多峰度为核心的 CPU 机制实验。只有机制、现有语料效应和成本有效性同时通过预注册门槛，才进入新数据获取、物理成本测量与独立人工事件验证。

---

## 一、研究背景

摄像设备持续产生大量长视频，但从视频中提取结构化语义仍依赖计算昂贵的视觉模型。传统视频数据库通常面向对象存在、对象计数或聚合查询，通过降低采样率、训练轻量代理、构建语义索引或选择不同精度的模型减少处理成本。随着视觉语言模型和开放世界检测器的发展，用户可以提出更加开放的自然语言查询，例如“行人在车辆接近时突然改变方向”或“车辆在非保护条件下与弱势道路使用者发生冲突”。这类查询不再对应一个固定对象类别，而是涉及对象关系、动作和时间上下文。

直接对长视频中的所有帧或片段调用重型语义模型通常不可接受。一个实用系统必须先用较低成本操作寻找可能相关的区域，再对少量候选调用更强的语义 oracle。然而，当查询存在硬截止时间时，系统不能把候选发现和候选验证分成两个互不相关的离线阶段。过度扫描会留下大量来不及确认的候选，过早验证又可能反复处理局部区域并错过时间轴上尚未暴露的事件。

因此，本项目关注的不是单纯提高模型准确率，而是回答一个数据库执行问题：当发现操作会创造未来候选、语义确认成本较高、结果必须在截止前持久化时，查询系统应如何分配发现与验证预算？

---

## 二、现有方法及其不足

### 2.1 代理过滤、近似聚合与 limit 查询

[BlazeIt](https://www.vldb.org/pvldb/vol13/p533-kang.pdf) 使用专用神经网络、控制变量和面向 limit query 的搜索算法减少视频查询成本。这类方法证明数据库优化器可以利用不准确但廉价的模型，同时保留特定查询的统计保证。但其主要执行对象仍是固定视频帧，查询优化关注哪些帧需要昂贵模型，而不是扫描操作如何先创造候选以及候选如何被物化为独立事件。

### 2.2 语义索引与查询无关预处理

[TASTI](https://cs.stanford.edu/people/matei/papers/2022/sigmod_tasti.pdf) 构建可复用的语义索引以支持多类机器学习查询，[Seiden](https://www.vldb.org/pvldb/vol16/p2289-kakkar.pdf) 则直接利用 oracle 抽样建立查询无关索引，并在查询阶段结合探索与利用。这些系统适合可以提前支付索引构建成本的场景。GVAQP 研究的是不同起点：查询到达时视频仍未完整扫描，系统必须在当前查询截止时间内同时完成发现、确认和结果提交。

### 2.3 未索引视频的自适应采样

[ExSample](https://oscar-moll.com/assets/pdf/Moll_ExSample_ICDE.pdf) 将未索引视频的对象搜索建模为自适应采样问题，根据已经处理帧的反馈重新分配采样位置。它是 GVAQP 最重要的发现类基线。两者的主要差别不应停留在“ExSample 没有做开放语义”的文字表述，而应通过机制实验验证：GVAQP 中低成本 SCAN 只负责暴露候选，高成本 VERIFY 负责语义确认，两类操作竞争同一截止预算，因此事件分布的稀疏度和多峰度应系统性改变最优发现与确认安排。

### 2.4 动作查询与模型配置优化

[ZEUS](https://arxiv.org/abs/2104.06142) 通过强化学习调整输入动作分类器的视频片段采样率、长度和分辨率，以满足准确率目标。它说明动作查询需要处理连续视频片段，而不是孤立帧，但其优化对象是已经构造的输入片段，没有显式建模 SCAN 扩展 VERIFY 候选集合以及 deadline 前 durable commit 的约束。[FiGO](https://hparch.gatech.edu/papers/jiashen_sigmod2022.pdf) 为不同视频 chunk 选择不同精度和成本的模型，解决的是细粒度模型配置，而不是候选发现与确认之间的因果依赖。

### 2.5 开放语义交通视频查询

[LAVA](https://arxiv.org/abs/2507.19821) 结合自然语言查询、多臂老虎机 segment localization、开放世界检测和长期轨迹抽取，是当前最接近的开放语义相邻工作。LAVA 已经覆盖“语言驱动、分段采样和开放世界检测”的一般组合。因此，GVAQP 不能仅以这些关键词作为新颖性来源。需要验证的新边界是硬截止下的因果候选前沿、发现与确认的共同成本合同，以及 durable event materialization 对查询计划和评价结果的影响。

---

## 三、核心科学问题

本项目的核心问题是：

> 对于一段尚未完整扫描的长视频，当低成本发现操作可以产生新的候选、高成本语义 oracle 只能验证已暴露候选，并且只有截止时间前持久化的独立事件才计入结果时，如何设计具有可解释边界和可复现截止语义的查询执行策略？

这一问题包含三个相互关联但需要分别验证的子问题：

1. 发现与验证之间是否存在足以改变查询计划的结构性耦合？
2. 时间二分是否只在事件稀疏、多峰等特定时间分布下有优势？
3. 这种优势在模拟成本、真实配对成本和不同 oracle 下是否仍然成立？

---

## 四、核心洞见

现有方法通常把查询过程理解为从固定候选集合中选择下一项，或者从固定视频帧集合中选择下一帧。未扫描视频不满足这一假设，因为 SCAN 会改变后续可执行动作集合。由此，系统面对的不是普通候选排序，而是一个因果候选前沿：当前未执行的发现动作决定未来有哪些验证动作存在。

这项观察带来两个设计结论。首先，在没有足够数据证明学习型调度有效之前，系统应优先保证时间轴上的最坏情况探索覆盖，而不是从少量历史工作负载学习复杂策略。其次，截止时间必须进入查询语义。一个已经获得正向模型输出但尚未提交的候选不应被计为查询结果，否则系统可以通过启动大量无法按时完成的操作获得虚假收益。

---

## 五、问题形式化

在时刻 \(t\)，系统状态包括尚未扫描的 temporal cells、已经暴露的候选前沿、已经提交的事件关系以及剩余时间：

\[
X_t=(U_t,F_t,R_t,t).
\]

SCAN 从 \(U_t\) 中选择一个时间单元并产生零个或多个候选，从而更新候选前沿 \(F_t\)。VERIFY 只能选择 \(F_t\) 中已经暴露的候选。对于 oracle 确认的候选，系统还必须完成去重和原子提交，才能更新事件关系 \(R_t\)。

给定截止时间 \(D\)，主要目标是最大化截止前已经持久化的独立事件数量：

\[
\max |R_D|.
\]

为了评价整个执行过程而非单个终点，还可以计算归一化 anytime utility：

\[
\frac{1}{D}\int_0^D\frac{|R_t|}{|R^*|}\,dt,
\]

其中 \(R^*\) 是同一 oracle 和同一事件定义下的离线参考集合。参考集合不能向在线策略免费提供候选，只用于事后评价。

---

## 六、DATB-SV 查询算法

DATB-SV 是当前保留的确定性算法。它不训练 controller，不使用 MAB 或 RL，也不根据最终人工结果调参。

### 6.1 时间二分发现

算法按照广度优先顺序扫描时间区间的中点，再递归处理左右子区间。与顺序扫描相比，该策略优先缩小整个时间轴上的最大未观察间隔，适合在不知道事件位置时寻找分散事件。

一个需要正式证明的性质是：对于长度为 \(L\) 的二分时间轴，完成深度 \(d\) 的扫描后，最大未扫描间隔满足

\[
G_d\leq\frac{L}{2^d}.
\]

后续需要在离散 temporal-cell 和冻结 exposure model 下给出严格版本，并推导事件持续时间与最坏触达时间之间的关系。当前该性质是理论证明目标，不是已经建立的论文结论。

### 6.2 候选前沿验证

VERIFY 只能处理已经由 SCAN 暴露的候选。所有基线必须遵守相同限制，不能在未支付发现成本的情况下访问完整候选集合。候选优先级来自冻结 manifest，算法不能利用 oracle 来源、未来标签或 reference-aware geometry。

### 6.3 固定发现与确认交替

当前版本以 1:1 比例交替执行 SCAN 和 VERIFY。首选操作不存在合法动作或无法安全完成时，可以回退到另一种操作。选择固定策略是证据约束下的设计，而不是假设固定策略永远最优。历史实验尚未证明状态信号具有稳定可学习性，因此复杂 controller 暂不具备引入依据。

### 6.4 截止准入与持久提交

每次操作执行前，系统使用冻结的动作时延上界和 commit reserve 判断该操作能否在 deadline 前完整结束。若观测时延超过声明上界，系统停止并记录 cost-bound violation。只有 oracle 确认、事件去重和原子提交均在截止前完成时，结果才进入 \(R_D\)。截止后完成的工作可以进入诊断日志，但不能改变用户可见结果。

### 6.5 Oracle 解耦

调度器仅使用统一接口：

```python
confirm(candidate, query) -> confirmation_result
```

缓存 VLM 标签、heavy model 或人工判断都可以实现该接口。oracle 名称和来源只作为 provenance，不作为调度特征。给定完全相同的确认记录，更换 oracle 来源元数据不应改变 action trace。

算法与 oracle 接口解耦，并不意味着科学结论与 oracle 无关。VLM 可以支持开发和 oracle-relative 评价，但只有独立人工事件标注能够验证输出是否符合人的语义事件定义。

---

## 七、当前代码与实验状态

### 7.1 已完成内容

当前已经形成统一的 CPU replay 实现、命令入口和测试：

| Artifact | Function |
|---|---|
| `src/garc/datb_sv.py` | DATB-SV 状态转换、调度、截止准入与 durable commit |
| `scripts/run_datb_sv_cpu_replay.py` | CPU-only 单命令 replay |
| `tests/test_datb_sv.py` | 时间二分、交替策略、去重、截止语义和 oracle 不变性测试 |

授权执行的 CPU suite 共运行 6 项测试并全部通过。合成端到端 replay 完成了 6 次 SCAN、4 次 VERIFY，在截止前提交 3 个去重事件，并在没有完整可执行动作时以 `NO_COMPLETE_ACTION_FITS` 停止。该结果证明实现合同可执行，不证明真实工作负载上的性能收益。

### 7.2 历史实验能够支持的结论

现有 detector exposure 在 vulnerable-road-user workload 上覆盖 257/264 个系统单元和 170/173 个 proxy-defined events，仍存在 3 个零暴露事件和 4 个部分暴露事件。这说明 cheap sensing 并非完整 oracle，但不直接证明新的调度策略有效。

固定候选上的 oracle allocation 实验显示较大的 VERIFY 分配 headroom，但这些候选已经预先存在，因此不能作为 endogenous SCAN 收益的证据。108 个缓存抽象状态中同时存在 SCAN-better 和 VERIFY-better 状态，但该状态集是构造出来的，无法说明这些状态在自然 workload 中的出现比例。

历史 learned policy 的 regret 约为 0.0097，而 always-VERIFY 为 0.000885。该结果说明当前实现下 learned policy 表现较弱，但在 policy 与 baseline 的 budget、oracle、episode 和 regret evaluator 完成 parity audit 前，不能将其解释为 RL/MAB 理论失败。

两个 production queries 的最优固定策略名称不同，但相对于最佳全局固定策略的 specialization gain 只有 0.000585 EventRecall-AUC。策略名称不同本身不足以支持 universal planner。Adaptive batching 的 CPU headroom 为 0 到 0.003，也没有形成论文级机会。

两个同源 Guangzhou traces 曾显示 temporal bisection 在约 224 秒时恢复一个 deadline-safe event。由于证据来自单一来源和单一事件，该结果只能作为机制动机。

### 7.3 尚未建立的结论

目前不能声称：

1. DATB-SV 在真实工作负载上稳定优于强基线；
2. learned controller、MAB 或 RL 已经被理论证伪；
3. 六个现有 video-query cells 支持跨视频和跨查询泛化；
4. 当前 scan 与 cached Qwen 时延能够组成真实 VERIFY/SCAN cost ratio；
5. VLM shadow events 等价于 independent human events；
6. 时间 geometry 已经解释了 human-event utility。

---

## 八、外部评审与方向调整

Qwen、Seed 和 Claude 都认为“独立 human-event utility measurement”比原 learned-controller 方案更成熟。三者对 measurement 方案的评分分别为 4.30、3.37 和 3.36，对 controller 方案的评分分别为 3.08、2.49 和 2.62。这种一致排序说明原 controller 方案缺少证据，但不能替代具体实验。

外部评审提出的小规模人工 pilot 具有有限但真实的决策价值。两个预注册 workload 若已经表现为 delta 接近零或方向相反，可以作为单向止损信号；若两者方向一致，则不能用于确认效应，只能说明值得继续完整标注。当前选择不立即运行 pilot，并不是因为 pilot 在方法上无效，而是因为算法合同、真实 replay provenance 和现有语料效应仍未完成。先完成这些步骤可以避免人工结果反过来影响算法选择。

综合三方意见后，当前路线不是返回完整 RL，也不是立即把工作完全改成人工测量论文，而是：

> 先完成 oracle-agnostic、deadline-safe 的确定性查询系统，在冻结算法和输出后，再将 independent human events 作为外部有效性层。

---

## 九、决定性研究假设

### 9.1 时间分布机制

最优先验证的假设是：DATB-SV 相对于顺序和均匀发现的优势会随事件时间稀疏度和多峰度增加，并在事件密集、连续时趋近于零。

这一假设比单纯比较平均性能更重要。若成立，它能够说明收益来自因果发现与确认耦合的结构，而不是另一个经验采样顺序。若不成立，时间二分缺少明确适用边界，算法论文路线应降级。

### 9.2 截止效用

在完全相同的候选访问、oracle、提交和成本语义下，DATB-SV 应在前述适用区间内提高 deadline 前的 distinct committed events 和 normalized anytime utility。

### 9.3 Oracle 来源不变性

给定相同 confirmation records，仅改变 oracle 来源元数据不应改变调度轨迹。oracle 判断发生变化时，效用可以变化，但算法执行合同不能随 oracle 身份变化。

### 9.4 人类事件外部有效性

相同 positive-clip yield 的系统输出可能覆盖不同数量或不同完整程度的独立人类语义事件。该假设只在算法、workload 和输出全部冻结后检验，不用于算法调参。

---

## 十、实验路线

### 10.1 Provenance 恢复或退役

第一步检查历史 endogenous scan preflight 是否具有完整、相互兼容的候选暴露来源、oracle 输出、动作时延和 workload 标识。恢复出的数据必须来自原始执行链，不能根据下游结果重建。无法恢复时，应将相应历史性能主张标记为 `RETIRED_FOR_CLAIM_USE`。

### 10.2 Evaluator parity audit

在解释历史 controller regret 前，将 learned-policy evaluator 强制输入 always-VERIFY action trace。相同动作、候选、oracle、成本和 deadline 必须产生逐项相同的 utility 与 regret。随后检查 SCAN/VERIFY 预算计数、episode 边界、unfinished action、候选访问和 reference oracle 是否一致。

如果 parity 失败，历史 negative result 无效，但不能因此直接重训。如果 parity 通过，则继续测量合法 endogenous frontier 上 oracle best action 相对于最佳固定动作的 headroom。只有 headroom 明显且状态可预测时，未来才可能重新讨论简单自适应策略。

### 10.3 CPU 合成机制实验

合成 trace 按预注册因素控制事件密度、时间模态数、事件持续时间、proxy exposure noise、VERIFY/SCAN cost ratio 和 deadline tightness。主要比较 sequential、uniform-stride、largest-gap、random 和 temporal-bisection 策略，并保证其 VERIFY、commit 和成本逻辑完全相同。

主要指标为 normalized anytime distinct-committed-event AUC。决定性分析不是选择平均最优方法，而是检验 policy 与 temporal regime 的交互关系。只有 DATB-SV 优势从 sparse/multimodal 到 dense/contiguous 呈预期方向变化，并且在至少两个 cost ratios 下稳定，才能通过机制 gate。

### 10.4 现有语料 replay

现有语料包含 3 个视频、2 个查询和 6 个 video-query cells。这一阶段只评价现有语料内部效应，不进行广泛泛化推断。结果必须同时报告每个 workload、leave-one-video-out 和 leave-one-query-out 诊断，不能将 raw pair 数量作为独立样本量。

工程上的最小重要效应暂定为：normalized anytime committed-event AUC 的 workload 中位相对增益至少为 5%，并且在多数 workload 的两个相邻实际 deadline 上至少多提交一个独立事件。该阈值是继续投入的工程决策标准，不是统计显著性阈值，需要在查看 Stage 1 结果前由导师确认或修改。

### 10.5 新数据与真实成本

现有 3 个 video clusters 和 2 个 query clusters 无法通过 generalization gate。开发规模至少需要 6 个长视频和 4 类语义查询。面向 claim-grade 评价，建议至少准备 8 个长视频、8 个语义不同的查询、4 个 query families 和 2 个独立视频来源。查询和视频必须在观察 DATB-SV 对比结果前冻结。

真实成本阶段需要在同一硬件、同一软件版本和同一执行边界上配对测量 SCAN 与 VERIFY，包括视频解码、预处理、模型推理、候选物化和事件提交。该阶段当前需要非 CPU 资源，因此标记为 `BLOCKED_BY_NON_CPU_REQUIREMENT`。

### 10.6 Human-event 外部验证

算法、workload selection、system outputs、exact-yield pairs 和统计协议冻结后，再执行 independent maximal semantic event 标注。主要 endpoint 使用已经冻结的 Mean Event Coverage，并将 clip yield 与 human-event utility 的关系作为外部效度问题。人工结果不能用于重新选择 temporal metric、阈值或策略。

---

## 十一、成本有效性

所有实验结果必须携带明确 cost tier，防止模拟预算被写成真实 wall-clock 结论。

| Cost tier | Definition | Evidence grade | Allowed claim |
|---|---|---|---|
| `SIMULATED_BOUND` | 使用冻结的确定性或分布式 action costs 做 CPU replay | PARTIAL | 机制和成本敏感性 |
| `CACHED_MEASURED_UNPAIRED` | 来自不同硬件、路径或时间的历史测量 | FAIL for comparison | 仅作为背景范围 |
| `PAIRED_COMMON_PATH` | SCAN/VERIFY 在同一执行路径和硬件上配对测量 | PASS candidate | 真实 deadline systems claim |

现有语料 replay 只能使用 `SIMULATED_BOUND`。每张表和每幅图都必须在标题或 caption 中标注 `simulated-bound / PARTIAL cost validity`。当前 2.018542 秒的 scan pilot 与 18.694820 秒的 cached Qwen timing 属于不可配对来源，不能组合为 measured cost ratio。

---

## 十二、数据规模与泛化边界

`3 videos × 2 queries` 虽然形成 6 个 cells，但共享视频和查询会产生交叉依赖。将这 6 个 cells 当成完全独立样本会高估证据量。当前数据最多支持三类结论：实现合同成立、现有语料上的描述性差异、以及某些机制是否值得进一步检验。

真正的 generalization claim 需要同时增加 video clusters 和 query clusters。只增加同一视频上的相似 query，或者只增加同一 query 的相邻视频片段，都不能解决外部有效性问题。数据扩充应覆盖对象状态、多对象交互、时间扩展动作和安全/near-miss 等语义类别，并至少来自两个独立来源。

新数据选择必须在运行 DATB-SV 与 baseline 对比前完成。不能因为现有结果弱而增加有利 query，也不能因为某个视频导致负结果而移除该视频。

---

## 十三、时间盒与止损规则

| Stage | Maximum effort | Stop condition | Route after stop |
|---|---:|---|---|
| Provenance recovery | 8 investigator-hours | 无法恢复兼容原始 manifest | 退役历史 claim |
| CPU mechanism test | 24 investigator-hours | 稀疏度/多峰度交互不成立 | 转 execution-contract 或 measurement 论文 |
| Existing-corpus replay | 40 investigator-hours | 效应低于门槛、方向不稳或由单一视频/query 驱动 | 不申请 GPU 扩展 |
| New inference and cost measurement | 仅在前述 gates 通过后授权 | Tier C3 成本下效应消失 | 停止算法主张 |
| Human external validation | 算法和输出冻结后执行 | human utility 与 clip yield 基本一致 | 报告 clip yield 已是强代理 |

时间盒的作用不是强迫产生正结果，而是避免在 PARTIAL 状态下无限扩展策略、数据或指标。

---

## 十四、结果解释矩阵

| Mechanism result | Existing-corpus effect | Cost validity | Interpretation |
|---|---|---|---|
| PASS | PASS | Paired common-path | 进入 claim-grade generalization evaluation |
| PASS | PASS | Simulated-bound | 机制有前景，但只能声称模拟成本下有效 |
| PASS | FAIL | Any | 理论/合成假设与真实语料不匹配，转边界或负结果研究 |
| FAIL | PASS | Any | 可能是工程收益，但缺少可解释机制，顶会 story 较弱 |
| FAIL | FAIL | Any | 停止 DATB-SV 算法路线 |
| Any | Any | Mixed unpaired | 不允许 deadline comparative claim |

Generalization 是独立的第三维度。即使现有 6 个 cells 中效果很大，也不能自动升级为跨查询或跨视频结论。

---

## 十五、预期论文贡献

在所有关键证据尚未完成前，贡献应按层级表达。

当前已经具备的贡献是一个可执行的问题定义和系统合同：将未扫描视频查询建模为因果候选前沿上的 deadline-safe execution，并明确只有 durable committed events 才构成查询结果。

若 CPU 机制实验和理论证明完成，可以进一步贡献时间二分的最大间隔性质，以及事件时间分布决定算法收益的 regime map。

若真实语料、配对物理成本和扩展 workload 均通过 gate，则可以形成完整 systems contribution：一个 oracle-agnostic 的开放语义视频查询执行器，在公平成本和候选访问条件下改善 deadline event utility。

若 independent human evaluation 进一步证明 clip yield 与 human-event utility 存在差异，则可以补充一个评价层贡献，说明视频查询系统需要从 clip-level yield 转向 independently defined event utility。

---

## 十六、SIGMOD/VLDB 潜力判断

当前方向具有数据库顶会所需要的问题形态，但还不具备投稿证据。它的潜力不来自使用 VLM、MAB 或 temporal bisection，而来自以下组合是否能够被证明为一个普遍系统问题：

1. candidate discovery 会改变未来 query plan；
2. discovery 与 verification 共享硬截止预算；
3. unfinished work 和未提交结果不能产生 deadline utility；
4. 事件时间分布决定不同执行策略的适用边界；
5. frame/clip yield 可能无法代表 durable semantic events。

若只能在模拟成本和单一来源数据上展示少量收益，工作不满足 SIGMOD/VLDB research paper 的证据要求。若能够完成理论边界、强基线、真实配对成本、跨 query/video generalization 和 human-event external validation，则具有顶会竞争力。

---

## 十七、主要风险与证伪条件

### 风险一：历史 evaluator 口径不一致

如果 policy 和 baseline evaluator 不同，历史 controller regret 不可解释。解决方式是 action-trace identity test，而不是继续训练。

### 风险二：不存在足够 action headroom

如果合法 endogenous frontier 上 oracle best action 与最佳固定策略几乎相同，任何 controller 都没有实质优化空间。此时应关闭调度学习路线。

### 风险三：时间二分没有稳定适用区间

如果合成机制实验无法恢复稀疏、多峰条件下的预期优势，则 DATB-SV 缺少结构性解释，不应通过增加变体挽救。

### 风险四：现有语料效应由单一来源驱动

如果 leave-one-video-out 或 leave-one-query-out 后效应消失，应停止算法 generalization claim，并在新数据投入前重新判断问题价值。

### 风险五：真实成本消除模拟收益

如果 Tier C3 配对成本下 conservative admission 几乎不允许有效工作，或者 DATB-SV 收益消失，则模拟 deadline 结果不能升级为系统 claim。

### 风险六：human-event 评价否定 clip utility gap

如果 independent human events 与 positive-clip yield 高度一致，应结论为 clip yield 在当前 workloads 上已经是良好代理，而不是事后修改事件定义。

---

## 十八、希望导师确认的三个决策

### 决策一：是否认可新的核心问题

是否同意将论文中心从 learned controller 调整为“未扫描视频上的 causal-frontier deadline execution”，并将 controller 保持关闭，除非 evaluator parity、oracle headroom 和状态可学习性三个 gate 同时通过？

### 决策二：是否接受分层证据路线

是否同意当前 6 个 video-query cells 仅用于 descriptive internal support，并在任何 generalization claim 前冻结至少两个数据来源、多个 video clusters 和多个 query families 的扩充计划？

### 决策三：是否接受止损标准

是否同意将“中位 normalized anytime utility 相对增益至少 5%，且多数 workload 在两个相邻 deadline 上至少多一个事件”作为继续申请非 CPU 资源的工程门槛？如不接受，需要在查看 Stage 1 结果前替换为新的最小重要效应。

---

## 十九、下一步

唯一立即执行的工作是：

> **在 8 investigator-hours 的 CPU-only 时间盒内，执行 `RECOVER_OR_RETIRE_ENDOGENOUS_SCAN_PREFLIGHT_PROVENANCE`。**

恢复成功后进入 evaluator parity audit；无法恢复则正式退役依赖该 package 的历史性能主张。当前不运行 GPU、不调用新 VLM、不训练 controller、不扩展 query，也不启动人工 outcome evaluation。

---

## 附录 A：三分钟口头汇报版本

我的课题研究长视频上的开放语义查询。和传统视频查询不同，我关注的是查询到达时视频还没有被完整扫描，而且语义判断需要昂贵的 VLM 或其他 oracle。系统必须在硬截止时间内同时决定扫描哪里、验证哪个候选，以及哪些结果来得及真正提交。

我现在认为这个问题的关键不是训练一个 controller，而是候选发现与候选验证之间存在因果依赖。SCAN 会创造后续 VERIFY 候选，所以它不是在固定候选集合上做普通排序。与此同时，只有在 deadline 前完成确认、去重和持久化的事件才应该计入结果。

基于这个问题，我实现了 DATB-SV。它使用广度优先时间二分扫描未观察区域，以固定比例交替执行 SCAN 和 VERIFY，并通过保守时间上界保证不会启动无法在 deadline 前完成和提交的工作。CPU 实现和六项测试已经通过，但目前只证明执行合同正确，还没有证明真实性能收益。

接下来最关键的实验不是继续训练 RL，而是验证时间二分为什么可能有效。我会首先用 CPU 合成 trace 控制事件的稀疏度和多峰度，测试 DATB-SV 是否只在稀疏、多峰事件中获得优势。如果这个机制不成立，就停止算法路线。如果成立，再在现有 3 个视频和 2 个 query 上做描述性 replay。

现有六个 video-query cells 不能支持 generalization，因为实际上只有 3 个 video clusters 和 2 个 query clusters。真实顶会 claim 还需要扩展视频与 query、在同一执行路径上测量 SCAN/VERIFY 成本，并在算法冻结后用 independent human events 做外部验证。

我希望老师确认三个问题：是否认可 causal-frontier deadline execution 作为核心问题，是否同意现有数据只支持内部描述性证据，以及是否接受预注册的效应门槛和止损规则。

## 附录 B：当前证据等级速查

| Statement | Status |
|---|---|
| DATB-SV CPU implementation is executable | Supported |
| Deadline admission and durable commit tests pass | Supported |
| Oracle identity is excluded from scheduling | Supported at interface level |
| Temporal bisection has a formal maximum-gap theorem | Proof target |
| DATB-SV improves real deadline utility | Needs evidence |
| Existing six cells support generalization | Not supported |
| Historical learned controller is theoretically invalid | Not supported |
| Simulated cost establishes deployment speedup | Not supported |
| VLM labels are suitable for algorithm development | Supported with oracle-relative scope |
| VLM labels replace independent human validity | Not supported |

