# G-ARC Research Report
## Guaranteed Approximate Relevant Clip Query Processing over Large-Scale Video Repositories
### Deep Research Report · 2025/2026

---

## 1. Executive Summary

本报告针对提出的主线研究方向 **G-ARC**（Guaranteed Approximate Relevant Clip Query）进行了系统性文献调研与可行性评估。

**核心结论：**

1. **研究空白真实存在**。目前没有任何论文同时实现了 clip-level precision/recall 高概率保证、IoU-based hit 语义、oracle budget 约束这三者的结合。这是一个货真价实的 gap。

2. **G-ARC 不是对现有工作的简单拼接**。SUPG 的保证机制不能直接迁移到 clip level，原因是 clip 不是 i.i.d. records、IoU hit 定义与 frame-level match 不等价、clip 边界本身具有统计不确定性。ARC 的 confidence 不等价于 SUPG 式的高概率保证。

3. **项目可行性高**。核心理论工具（置信区间、importance sampling、conservative threshold 选取）已有扎实基础，主要挑战在于将其正确扩展到 clip 语义，这是有解决路径的技术问题。

4. **推荐优先投稿 VLDB/SIGMOD**。G-ARC 的 query semantics 扩展和统计保证设计更符合数据库/数据管理系统的顶级会议定位；若侧重检索语义也可考虑 SIGIR/MM。

---

## 2. Related Work Map

### 2.1 核心相关论文（直接相关）

#### [P1] SUPG — Approximate Selection with Guarantees using Proxies
- **引用**: Daniel Kang, Edward Gan, Peter Bailis, Tatsunori Hashimoto, Matei Zaharia. *PVLDB* 13(11), 2020.
- **DOI**: https://doi.org/10.14778/3407790.3407804
- **问题**: 大规模非结构化数据上的 approximate selection，带 precision/recall target 和高概率保证
- **查询对象**: record（帧级，i.i.d.）
- **是否有统计保证**: ✅ Pr[Recall(R) ≥ γ] ≥ 1-δ；Pr[Precision(R) ≥ γ] ≥ 1-δ
- **方法**: 代理分层 + importance sampling（√A(x) 权重）+ 置信区间 threshold 选取
- **未解决的问题**: 不支持 temporal clip query；record 粒度是 i.i.d. 假设；无 IoU-based hit；无 clip 边界不确定性处理

#### [P2] ABae — Accelerating Approximate Aggregation Queries with Expensive Predicates
- **引用**: Daniel Kang, John Guibas, Peter Bailis, Tatsunori Hashimoto, Yi Sun, Matei Zaharia. *PVLDB* 14(11), 2021.
- **DOI**: https://doi.org/10.14778/3476249.3476285
- **问题**: AVG/SUM/COUNT 聚合查询，WHERE 谓词需要昂贵 oracle
- **查询对象**: record（帧级）
- **是否有统计保证**: ✅ 置信区间 + bootstrap
- **方法**: proxy 分层 + pilot sampling + 最优 budget allocation（∝ √(p_k · σ_k)）
- **未解决的问题**: 不支持 clip-level query；clip discovery 与 clip boundary uncertainty 带来的 dependent samples 问题没有处理

#### [P3] ARC — Approximate Relevant Clip Query in Large-Scale Video Repositories
- **引用**: Yue Chen, Yinan Jing, Ziqiang Yu, Xiaohui Yu, Zhenying He, Kai Zhang, X. Sean Wang. *SIGIR 2025*.
- **DOI**: https://doi.org/10.1145/3726302.3729896
- **问题**: 大规模视频库中带时序约束和统计推理条件的视频片段检索
- **查询对象**: clip（连续帧序列，variable length）
- **是否有统计保证**: ❌ 仅有 confidence 估计（ARC 的 Conf(C̃) 是点估计，非高概率保证）
- **方法**: proxy pruning + time-domain clustering + adaptive progressive sampling (MAB-UCB) + label propagation
- **未解决的问题**: **没有 Pr[Clip-Recall ≥ γ] ≥ 1-δ 式的高概率保证**；没有 oracle budget 约束下的 guarantee violation rate 控制

---

### 2.2 重要相关工作

#### [P4] TASTI — Semantic Indexes for Machine Learning-based Queries over Unstructured Data
- **引用**: Daniel Kang, John Guibas, Peter Bailis, Tatsunori Hashimoto, Matei Zaharia. *SIGMOD 2022*.
- **DOI**: https://doi.org/10.1145/3514221.3517897
- **问题**: 针对多种查询类型构建 query-agnostic proxy score index，利用语义相似性减少 target labeler 调用
- **查询对象**: record（帧/文本）
- **是否有统计保证**: 部分（理论分析 embedding 误差与查询精度的关系）
- **与 G-ARC 的关系**: TASTI 生成的 proxy scores 可直接作为 G-ARC proxy 输入；TASTI 可替代 G-ARC 中的 CMDN proxy

#### [P5] ExSample — Efficient Searches on Video Repositories through Adaptive Sampling
- **引用**: Oscar Moll, Favyen Bastani, Sam Madden, Mike Stonebraker, Vijay Gadepally, Tim Kraska. *ICDE 2022*.
- **DOI**: https://doi.org/10.1109/ICDE53745.2022.00266
- **问题**: 视频库中无索引对象搜索，通过 MAB 自适应采样加速
- **查询对象**: frame/object（无 temporal clip 概念）
- **是否有统计保证**: ❌ 无形式保证，目标是找到 K 个匹配帧
- **与 G-ARC 的关系**: 提供了 MAB-based 视频帧优先采样的思路，ARC 已部分吸收；G-ARC 需要在此基础上增加 guarantee

#### [P6] Seiden — Revisiting Query Processing in Video Database Systems
- **引用**: Jaeho Bang, Gaurav Tarlok Kakkar, Pramod Chunduri, Subrata Mitra, Joy Arulraj. *PVLDB* 16(9), 2023.
- **DOI**: https://dl.acm.org/doi/10.14778/3598581.3598599
- **问题**: 重新审视 oracle-proxy 架构，在 oracle 速度追上 proxy 的新背景下设计新型 VDBMS
- **查询对象**: frame/object（目标选取）
- **是否有统计保证**: ❌
- **与 G-ARC 的关系**: 背景参考；说明 oracle/proxy 速度差距在缩小，G-ARC 的 oracle budget 约束仍有现实意义

#### [P7] InQuest — Accelerating Aggregation Queries on Unstructured Streams
- **引用**: 作者来自 MIT，arXiv:2308.09157, 2023.
- **问题**: 流式非结构化数据上的聚合查询，带统计保证
- **查询对象**: record（流式）
- **是否有统计保证**: ✅ 期望误差收敛保证
- **与 G-ARC 的关系**: 将 ABae 扩展到流式设定，是方法论上的近邻，但不涉及 clip 查询

#### [P8] BARGAIN — Cut Costs, Not Accuracy: LLM-Powered Data Processing with Guarantees
- **引用**: UC Berkeley EPIC Lab，arXiv:2509.02896，SIGMOD 2026.
- **问题**: LLM cascade 数据处理，带 precision/recall/accuracy 强保证（non-asymptotic，使用 conformal prediction 工具）
- **查询对象**: record（文本）
- **是否有统计保证**: ✅ 比 SUPG 更强的有限样本保证
- **与 G-ARC 的关系**: **最重要的方法参考之一**。BARGAIN 将 SUPG 的渐近 CLT 保证升级为有限样本保证（e-value、conformal p-value）。G-ARC 可借鉴这套工具来设计 clip-level 有限样本保证。

#### [P9] PilotDB — Database-Agnostic Online AQP with A Priori Error Guarantees
- **引用**: Yuxuan Zhu, Tengjun Jin, Charith Mendis, Daniel Kang 等. *SIGMOD 2025*.
- **DOI**: https://doi.org/10.1145/3725335
- **问题**: 无需离线采样、无需修改 DBMS 的 online AQP，带 a priori 误差保证
- **查询对象**: 结构化数据（SQL 聚合）
- **与 G-ARC 的关系**: 提供了数据库无关 AQP 保证的最新参考；G-ARC 面向非结构化视频数据的 selection 语义，不在其覆盖范围内

#### [P10] On Efficient Approximate Queries over Machine Learning Models
- **引用**: arXiv:2206.02845, 2022.
- **问题**: 同时满足 precision 和 recall target 并最小化 oracle 调用，超越单一目标 SUPG
- **查询对象**: record（i.i.d.）
- **是否有统计保证**: ✅
- **与 G-ARC 的关系**: 解决了 SUPG 不能同时保证 precision 和 recall 的问题；G-ARC 同样面对这个问题，但在 clip 语义下更复杂

#### [P11] Predictive and Near-Optimal Sampling for View Materialization in Video Databases
- **引用**: Yanchao Xu, Dongxiang Zhang 等. *PACMMOD* 2(1), 2024.
- **DOI**: https://dl.acm.org/doi/10.1145/3639274
- **问题**: 视频数据库中 view materialization 的预测性近优采样
- **查询对象**: frame/object
- **与 G-ARC 的关系**: 提供视频数据库采样优化的方法论参考

---

### 2.3 边界相关工作（部分相关）

| 论文 | 会议/年份 | 关系说明 |
|------|-----------|----------|
| BlazeIt (Kang et al.) | VLDB 2019 | 聚合+limit 查询加速，无 clip 概念 |
| NoScope (Kang et al.) | VLDB 2017 | frame-level DNN query 加速，无保证 |
| Focus (Hsieh et al.) | OSDI 2018 | 视频查询系统，无统计保证 |
| OTIF (Bastani et al.) | SIGMOD 2022 | 大规模视频 tracking，无 guarantee |
| VIVA (Romero et al.) | VLDB 2023 | 声明式模型关系优化视频查询 |
| Boundary Uncertainty in TAL (Xie et al.) | ICASSP 2020 | 时序动作定位中的边界不确定性建模（CV 视角） |

---

## 3. Comparison Table

| 维度 | SUPG | ABae | ARC | G-ARC（目标） |
|------|------|------|-----|--------------|
| 查询类型 | Selection | Aggregation | Selection (clip) | Selection (clip) |
| 查询对象 | record/frame | record/frame | **clip（variable-length）** | **clip（variable-length）** |
| 使用 proxy | ✅ | ✅ | ✅ | ✅ |
| 使用 oracle | ✅ | ✅ | ✅ | ✅ |
| Oracle budget 约束 | ✅ | ✅ | ✅（软约束） | ✅（硬约束） |
| 统计保证形式 | Pr[Recall ≥ γ] ≥ 1-δ | CI on aggregate | confidence 点估计（非保证） | **Pr[Clip-Recall ≥ γ] ≥ 1-δ** |
| Precision target | ✅ | — | 部分（conf 类 precision） | ✅ |
| Recall target | ✅ | — | 最大化 recall（无保证） | ✅ |
| IoU-based hit | ❌ | ❌ | ✅ | ✅ |
| Temporal continuity | ❌ | ❌ | ✅ | ✅ |
| Variable-length clip | ❌ | ❌ | ✅ | ✅ |
| Clip boundary uncertainty | ❌ | ❌ | 部分处理 | **核心设计点** |
| Temporal dependence | ❌（i.i.d.假设） | ❌ | 利用但不用于保证 | **核心挑战** |
| Guarantee violation rate | 可控 | 可控 | **不可控** | **可控** |

---

## 4. Research Gap Analysis

### 4.1 SUPG 的保证为什么不能直接用于 ARC？

**问题的本质**：SUPG 的 guarantee 建立在以下假设上：

1. **查询结果是单个 records 的集合**，precision/recall 定义在 records 上：precision = |R ∩ O⁺| / |R|。
2. **Records 是 i.i.d. 的**，从而置信区间（CLT 或 Hoeffding）对 threshold 选取有效。
3. **Oracle(x) ∈ {0,1}** 明确告知每个 record 是否匹配，oracle 反馈与 proxy score 是对齐的。

**在 ARC clip 查询中，这三条全部失效：**

**（1）Clip 不是 i.i.d. records**  
相邻帧高度相关（时域连续性），同一 clip 内的帧满足谓词的概率彼此依赖。SUPG 的 CLT 论证依赖样本的独立性；对 clip 使用这一论证会得到错误的置信区间（通常偏窄，即 under-coverage）。

**（2）Frame-level recall ≠ Clip-level recall**  
设 ground truth 有 M 个 relevant clips，每个 clip 的长度为 L_j 帧。
- Frame-level recall = 匹配帧数 / 总匹配帧数
- Clip-level recall（IoU-based）= clip hits（IoU ≥ θ）的数量 / M

两者数值上完全不同：你可能找到了 90% 的匹配帧，但如果每个 clip 都有少量边缘帧被漏掉，导致 IoU < θ，clip-level recall 可能接近 0。SUPG 即使成功实现了 frame-level recall ≥ γ，也无法保证 clip-level recall ≥ γ。

**（3）Frame-level precision ≠ Clip-level precision**  
Clip-level precision = 被判为 relevant 的 candidate clips 中，IoU hit 的比例。即使 frame-level precision 很高，一个候选 clip 里只要有少量错误帧导致边界偏移，IoU 就可能跌破阈值，整个 clip 从 hit 变为 miss。

**（4）Clip boundary uncertainty 带来 oracle 反馈的模糊性**  
当我们 oracle 标注一帧时，得到的是该帧是否满足谓词的 binary 结果。但 clip 的 start/end boundary 本质上是连续谓词在时间维度上的过渡区域。边界处的帧可能以 50% 的概率满足/不满足谓词，导致 clip boundary 具有固有不确定性。SUPG 没有处理这种"boundary region"的采样策略。

**（5）Clip merge/split 的非单调性**  
在 SUPG 中，增加一个 record 到结果集不会改变其他 records 的状态。但在 clip 查询中，新标注一帧可能导致两个相邻 candidate clips **合并为一个 hit**，或者一个 clip **分裂为两个 non-hit**。这种非单调性使 threshold 选取算法的单调性假设不成立。

---

### 4.2 ARC 的 confidence 是否等价于 SUPG 式的高概率保证？

**不等价。差异本质是点估计 vs. 高概率下界。**

ARC 定义的 confidence（定义 3.9）为：
```
Conf(C̃) = E_{C̃_i ∈ C̃} [ P(∃C_j s.t. IoU ≥ θ) ]
```
这是一个**期望 precision 的估计值**，类似于 E[Precision]。

SUPG 的保证是：
```
Pr[ Precision(R) ≥ γ ] ≥ 1-δ
```
这是一个**事件发生概率的下界保证**。

**关键区别**：
- ARC 的 confidence 是对当前结果质量的一个**点估计**，它可能因为抽样随机性而以较高概率低于 γ。例如，Conf(C̃) = 0.92 不意味着"以 95% 的概率，clip-level precision ≥ 0.9"。
- SUPG 的保证明确控制了**保证违反率**（guarantee violation rate），即 Pr[Recall < γ] ≤ δ。
- ARC 论文实验中，当 confidence requirement 设为 0.9 时，并不保证 recall 真的以高概率 ≥ 0.9。事实上 ARC 在 taipei-hires 数据集上的性能下降正是因为 proxy 可靠性估计有偏，说明其 confidence 估计不可靠。

---

### 4.3 ABae 的置信区间能否直接迁移到 clip-level aggregation？

**不能，原因如下：**

**（1）Clip discovery 问题**  
ABae 假设数据集 D 已知，记录是可枚举的。但在 clip 查询中，relevant clips 的数量和边界本身是**待发现的量**，oracle 帧标注结果会实时改变 clip set 的定义。ABae 的 pilot sampling 无法处理"样本数量本身是未知随机变量"的情形。

**（2）Clip boundary uncertainty 带来 overlap 和 temporal dependence**  
ABae 使用分层 i.i.d. 采样计算 aggregate（如每 clip 的平均车辆数）。但 clip 不是 i.i.d. 的，且 clip 之间可能 overlap 或 merge，导致传统 Horvitz-Thompson 估计量的无偏性失效。

**（3）Stochastic clip size**  
ABae 的最优 allocation 公式 T*_k ∝ √(p_k · σ_k) 假设每 stratum 有固定的"有效样本数"。但 clip 的长度是随机的，且取决于连续标注结果（连续满足谓词的帧序列），这使每个 stratum 的有效信息量本身是随机变量。

---

### 4.4 这个方向是否有足够 novelty？

**有。从以下五个维度均存在新贡献：**

1. **New query semantics**: 首次将 high-probability guarantee 引入 clip-level query，提出 CLIP RECALL TARGET γ WITH PROBABILITY 1-δ 的完整查询语义。

2. **New guarantee objective**: 将保证目标从"frame-level recall"扩展到"clip-level recall with IoU ≥ θ"，需要重新定义 estimand 并设计新的 estimator。

3. **New sampling/budget allocation strategy**: 针对 clip 边界不确定性和 IoU-sensitivity 的 oracle 调用分配策略（conservative boundary adjustment + oracle allocation based on boundary uncertainty）。

4. **New clip-level uncertainty estimation**: 在 ARC 的 confidence estimation 基础上，引入保守估计技术（下界估计而非点估计），并处理 temporal dependence。

5. **New experimental metric**: guarantee violation rate（Pr[clip-level recall < γ] over 100 runs），这是 SUPG 的 failure rate 在 clip 语义下的扩展。

---

### 4.5 已有工作检索结论

通过系统搜索，**未找到**以下任何组合的直接相关工作：
- clip-level precision/recall guarantee with high probability
- video clip query with formal statistical guarantees (Pr[...] ≥ 1-δ) under oracle budget
- temporal segment retrieval with IoU-based guarantee
- combining SUPG-style guarantees with ARC-style video clip query

**最相近的工作是 BARGAIN (SIGMOD 2026)**，它将 SUPG 的 asymptotic 保证升级为有限样本保证，但针对的是 i.i.d. text records，不涉及任何 clip/temporal 概念。

---

## 5. Recommended Project Directions（优先级排序）

### 项目一（最高优先级）: G-ARC

**英文标题**: *G-ARC: Guaranteed Approximate Relevant Clip Query Processing over Large-Scale Video Repositories*

**核心创新**: 将 SUPG 式的高概率 precision/recall 保证引入 ARC 的 clip-level 查询框架，解决 clip boundary uncertainty、temporal dependence、IoU-based hit 带来的统计挑战。

**推荐会议**: VLDB 2026 或 SIGMOD 2027

---

### 项目二（次优先级）: Clip-Level Aggregation with Guarantees

**英文标题**: *CLAG: Clip-Level Aggregation Queries with Statistical Guarantees over Video*

**核心创新**: 将 ABae 扩展到 clip-level aggregation（e.g., "what is the average duration of traffic jam clips? with CI"），处理 clip discovery 的 stochasticity 和 temporal dependence 带来的新统计挑战。

**推荐会议**: VLDB 2026

---

### 项目三（低优先级）: Streaming G-ARC

**英文标题**: *S-GARC: Online Guaranteed Clip Query over Live Video Streams*

**核心创新**: 将 G-ARC 扩展到 streaming 视频场景，结合 InQuest (arXiv 2023) 的流式 AQP 思路，支持实时保证。

**推荐会议**: SIGMOD 2027 或 ICDE 2027

---

## 6. Proposed Method Sketch: G-ARC

### 6.1 查询语义

```sql
SELECT relevant_clips
FROM video_repository
WHERE duration >= τ
  AND predicate(frame) = TRUE
CLIP RECALL TARGET γ_r           -- e.g., 0.90
[CLIP PRECISION TARGET γ_p]      -- e.g., 0.90, optional
WITH PROBABILITY 1-δ             -- e.g., 0.95
ORACLE LIMIT B                   -- e.g., 5000 frames
USING proxy_model
IOU THRESHOLD θ                  -- e.g., 0.9
```

**语义定义**:
- Clip-level Recall: CR(C̃) = |{C ∈ C* : ∃C̃_i s.t. IoU(C, C̃_i) ≥ θ}| / |C*|
- Clip-level Precision: CP(C̃) = |{C̃_i ∈ C̃ : ∃C ∈ C* s.t. IoU(C, C̃_i) ≥ θ}| / |C̃|
- **G-ARC RT 语义**: Pr[CR(C̃) ≥ γ_r] ≥ 1-δ，且 |C̃| 尽量大
- **G-ARC PT 语义**: Pr[CP(C̃) ≥ γ_p] ≥ 1-δ，且 |C̃| 尽量大

---

### 6.2 方法框架

G-ARC 在 ARC 的两阶段框架上增加 **Guarantee Module**，整体分三阶段：

```
Phase 1: Proxy Pruning (继承自 ARC)
  - 代理模型推断所有帧的概率分布
  - Time-domain clustering 增强 pruning
  - 输出: 初始 candidate clips C̃⁰ 和 cluster 结构 K

Phase 2: Guarantee-Aware Oracle Refinement (核心新贡献)
  - 2a. Conservative Boundary Adjustment
        将每个 candidate clip C̃_i 的边界向外保守扩展 Δ_i
        Δ_i 基于 IoU-sensitivity 和 boundary uncertainty 计算
  - 2b. Stratified Oracle Allocation
        将帧分为三类 strata:
          S1: boundary-critical frames（高优先级）
          S2: interior candidate frames（中优先级）
          S3: non-candidate frames with high proxy uncertainty（recall recovery）
        按 guarantee risk 分配 oracle budget B
  - 2c. Incremental Guarantee Estimation
        对当前 C̃ 计算 CR-lower-bound（而非点估计）
        使用 temporal cluster 内的 label propagation 减少所需 oracle 数量

Phase 3: Guarantee Certification
  - 使用 conservative 置信区间验证 Pr[CR(C̃) ≥ γ] ≥ 1-δ
  - 如不满足，触发 recall recovery sampling 直到 budget 耗尽
  - 输出: C̃, achieved_confidence, oracle_calls_used, violation_risk_estimate
```

---

### 6.3 关键算法设计

#### 算法 A: Conservative Boundary Adjustment

**直觉**: 如果一个 candidate clip C̃_[s,e] 与 ground truth clip 相比边界偏移了 Δ 帧，则 IoU 会下降。为了使 IoU(C̃_i, C_j) ≥ θ 以高概率成立，我们需要扩展边界。

**形式化**: 设 proxy reliability RelP（继承自 ARC），clip 长度 L。当边界不确定性为 σ_b 时，保守扩展量：
```
Δ_i = max(0, ceil( (1-θ)/(1+θ) · L · (1 - RelP) ))
```
扩展后：C̃'_[s-Δ,e+Δ]，并将扩展区域的帧加入高优先级 oracle 队列。

#### 算法 B: Clip-Level Recall Lower Bound Estimation

**目标**: 构造 CR_LB 使得 Pr[CR(C̃) ≥ CR_LB] ≥ 1-δ。

**步骤**:
1. 对当前已标注帧 S ⊂ V（样本集），计算经验 clip-level recall: CR_hat(S)
2. 处理 temporal dependence：使用 cluster-level blocking，将相关帧归为一组，组间独立
3. 使用 block bootstrap 或 cluster-aware CLT 计算 CR 的 1-δ 置信下界:
```
CR_LB = CR_hat - z_{1-δ} · σ_hat / √(n_clusters)
```
4. 需要额外处理的技术点：
   - IoU ≥ θ 是非线性约束，需要 Delta method 或 bootstrap
   - Clip merge/split 事件使 CR 不是帧标注结果的线性函数

#### 算法 C: Guarantee-Aware Oracle Budget Allocation

**目标**: 给定剩余 budget B_rem，最大化 CR_LB 的提升。

**三层优先级分配**:
1. **Boundary-critical frames** (60% of B_rem): oracle 调用 clip 边界 ±Δ 内的帧。这些帧的标注结果直接影响 IoU hit 判断，是 guarantee 提升效率最高的。

2. **Recall recovery frames** (30% of B_rem): 对 non-candidate 区域中 proxy 不确定性（entropy H(K_r)）最高的 cluster 进行 importance sampling。这是 ARC 中已有的机制，在 G-ARC 中与 guarantee 校准结合。

3. **Precision calibration frames** (10% of B_rem): 对现有 C̃_i 随机采样验证 precision，防止大量 false positive clips 拉低 confidence。

---

### 6.4 理论保证设计

**命题（Recall Target）**:  
给定采样方案 (cluster-aware blocking，B oracle 调用)，G-ARC 满足:
```
Pr[ CR(C̃) ≥ γ_r ] ≥ 1-δ
```
**推导路线**:
1. 在 block bootstrap/CLT 框架下，CR_LB 是 CR 的 (1-δ) 置信下界
2. G-ARC 只在 CR_LB ≥ γ_r 时才终止并声称保证，否则继续采样
3. 这等价于：当算法终止时，以 1-δ 的概率 CR ≥ CR_LB ≥ γ_r

**关键难点（需解决）**:
- Temporal dependence 的有效样本数估计
- Clip merge/split 的非单调性需要保守估计（例如，不对 boundary 区域的 label propagation 使用在 guarantee 计算中，只在 recall recovery 中使用）
- δ 的分裂（union bound）：Boundary adjustment + oracle sampling + CI 三个步骤各消耗部分 δ

**简化路线**（MVP 版本）: 
- 假设 cluster 间独立（ARC 已做此假设）
- 在 G-ARC 中验证此假设的 guarantee violation rate 实验表现

---

## 7. Experimental Plan

### 7.1 实验设置

**数据集**（全部来自 ARC）:
- jackson-town-square（约 32K 帧 @ 30 fps）
- amsterdam（约 39K 帧）  
- taipei-hires（约 39K 帧，proxy 可靠性最低）
- venice-rialto（约 28K 帧）
- venice-grand-canal（约 21K 帧 @ 60 fps）

可补充：可考虑 ActivityNet 视频中截取 traffic/crowd 片段合成数据集，以增加 ground truth clips 多样性。

**Oracle 模型**: Mask R-CNN（继承自 ARC）  
**Proxy 模型**: CMDN + YOLOv5s（继承自 ARC）；可扩展至 TASTI embeddings

**查询设置**:
- 时序约束 τ ∈ {180, 300, 420} 帧
- 统计条件 c ∈ {P2.5, P10, P20}
- recall target γ_r ∈ {0.8, 0.9, 0.95}
- failure probability δ ∈ {0.05, 0.1}
- oracle budget B ∈ {1000, 2000, 5000} frames
- IoU threshold θ ∈ {0.5, 0.7, 0.9}

### 7.2 Baselines

| Baseline | 描述 |
|----------|------|
| **Oracle-Only** | 所有帧 oracle，100% 精确 |
| **Proxy-Only (CMDN)** | 只用 proxy，无 oracle 验证 |
| **ARC** | 原始 ARC，无 guarantee |
| **SUPG-RT+** | ARC 论文中的 SUPGrt+：用 SUPG 处理帧，然后转为 clips |
| **SUPG-PT+** | ARC 论文中的 SUPGpt+ |
| **G-ARC-Uniform** | G-ARC 的消融版：uniform oracle allocation（不做 boundary-aware 分配） |
| **G-ARC** | 完整方法 |

### 7.3 Metrics

| Metric | 定义 |
|--------|------|
| **Clip-level Recall** | 定义见 Section 6.1 |
| **Clip-level Precision** | 定义见 Section 6.1 |
| **mIoU** | 与 ARC 一致 |
| **Guarantee Violation Rate (GVR)** | 在 100 次独立运行中，clip-level recall < γ_r 的比例。**这是最重要的新指标**，目标是 GVR ≤ δ（例如 δ=0.05 时 GVR ≤ 5%）。 |
| **Oracle Calls** | 达到 guarantee 所需 oracle 调用数 |
| **End-to-End Time** | 总查询时间 |
| **Quality at Fixed Budget** | 在固定 budget 下的 clip-level recall |

### 7.4 关键实验

**实验 1（核心）: Guarantee Validity Test**
- 100 次独立运行每种方法
- 对比 G-ARC、ARC、SUPG+ 的 GVR（目标 GVR ≤ 5%，ARC 应 > 5%）
- 类比 SUPG 论文的 Figure 5/6 结构

**实验 2: Oracle Budget Efficiency**  
- 在相同 GVR ≤ 5% 约束下，比较各方法所需 oracle 数
- G-ARC 的 boundary-aware allocation 应比 uniform sampling 节省 oracle 调用

**实验 3: Quality-Cost Tradeoff**  
- 固定 budget，比较 G-ARC vs ARC 的 (recall, GVR) 曲线
- 展示 G-ARC 在牺牲少量 recall 的代价下大幅降低 GVR

**实验 4: Ablation Study**  
- 去掉 Conservative Boundary Adjustment：GVR 上升
- 去掉 Boundary-priority Oracle Allocation：oracle 效率下降
- 去掉 Cluster-aware CI：GVR 可能上升（如果 temporal dependence 被忽视）

**实验 5: Sensitivity**  
- 不同 θ 下（0.5 → 0.9）的 guarantee 成立性
- 不同 proxy reliability 下的表现（对比 ARC 在 taipei-hires 的失败案例）

---

## 8. Risks and Fallbacks

### 8.1 主要技术风险

| 风险 | 严重性 | 应对方案 |
|------|--------|----------|
| **Temporal dependence 导致 CLT 置信区间 under-coverage** | 高 | 使用更保守的 block bootstrap；增大 effective sample size correction；或改用 e-value（非渐近）工具 |
| **Clip merge/split 使 CR 非单调，难以设计保守估计量** | 中 | 简化假设：仅对"稳定 clip"（内部无 boundary uncertainty）提供保证；boundary 区域单独处理 |
| **Oracle budget B 在小规模数据集上消耗过快** | 中 | 强化 label propagation 以减少 oracle 调用；引入 TASTI 类的 semantic index 降低所需 oracle 数 |
| **实验中 GVR 难以控制在 5% 以下** | 低-中 | 放宽 δ（如 δ=0.1）；or 用更保守的 CI（Clopper-Pearson 而非 CLT normal approximation） |
| **理论保证中 temporal dependence 的处理过于复杂，难以发表** | 中 | MVP 版本：假设 cluster 间独立（ARC 的既有假设），将 temporal dependence 留作 limitation，实验验证 GVR 符合预期 |

### 8.2 Fallback Plan

**如果 clip-level 保证理论太难**:
- 降级为"fragment-level guarantee"：仅对 clip 内满足条件的最长连续帧序列提供保证（类似 SUPG 的帧级，但考虑时序约束 τ）
- 仍是比 ARC 更强的 contribution，但理论难度大幅下降

**如果实验效果不佳（GVR 控制不住）**:
- 转向 conservative ARC：牺牲一部分 recall 质量来换取 GVR 控制（保守 threshold 选取）
- 仍比 ARC 提供更强的 guarantee，论文核心论点仍成立

**如果 IoU-based guarantee 太难**:
- 先解决 τ-level recall guarantee（clip 长度满足要求的帧序列 recall），不引入 IoU，降低难度

---

## 9. Suggested Reading List

### 必读（直接基础）

1. **SUPG** (Kang et al., VLDB 2020) — 方法论基础
2. **ABae** (Kang et al., VLDB 2021) — 聚合扩展参考
3. **ARC** (Chen et al., SIGIR 2025) — 直接扩展对象
4. **TASTI** (Kang et al., SIGMOD 2022) — proxy index 构建参考
5. **BARGAIN** (arXiv:2509.02896, SIGMOD 2026) — **最重要的统计工具升级参考**：非渐近 CI、e-value、adaptive sampling
6. **ExSample** (Moll et al., ICDE 2022) — 视频 MAB 采样参考

### 强烈推荐（统计方法）

7. **On Efficient Approximate Queries over ML Models** (arXiv:2206.02845) — 同时 precision+recall guarantee 的参考
8. **Kish (1965), Survey Sampling** — stratified sampling + pilot sampling 经典教材（ABae 的理论基础）
9. **Owen & Zhou (2000), Safe and Effective Importance Sampling** — defensive importance sampling（SUPG 直接引用）
10. **InQuest** (arXiv:2308.09157) — streaming 扩展参考

### 背景参考（视频系统）

11. **BlazeIt** (Kang et al., VLDB 2019)
12. **NoScope** (Kang et al., VLDB 2017)
13. **Seiden** (Bang et al., VLDB 2023)
14. **Predictive Sampling for View Materialization** (Xu et al., PACMMOD 2024)

---

## 10. Final Recommendation

### 核心评估结论

**G-ARC 是一个清晰、可行、有足够 novelty 的研究方向**，回答了一个现有工作（ARC）留下的核心 open question：*能否在 clip-level 查询上提供像 SUPG 那样的高概率保证？*

**最强的 novelty 在哪里**:
- **新问题定义**：clip-level precision/recall guarantee with IoU-based hit，这是一个新的、有现实意义的查询语义
- **新统计挑战**：temporal dependence + clip boundary uncertainty + IoU non-linearity 的组合，使已有 guarantee 技术无法直接套用
- **新实验维度**：guarantee violation rate 作为核心评估指标，这是 clip-level AQP 研究的空白

**最大技术难点**:
- 处理 temporal dependence（frames within a clip are not i.i.d.）对置信区间有效性的影响
- 设计 conservative 但不过于 vacuous 的 clip-level recall 下界估计量

**理论保证怎么设计才不至于过难（MVP 方案）**:
1. 接受 cluster 间独立的假设（ARC 已有此假设）
2. 在 cluster 内应用保守的 CLT 置信区间（类 SUPG）
3. 通过 conservative boundary adjustment 将 IoU ≥ θ 的检验转化为帧级检验
4. 使用 union bound 合并各步骤的 δ 消耗
5. **通过实验验证** GVR ≤ δ（实验保证作为 fallback 理论保证）

**第一个 minimum viable paper 应该怎么做**:

| 模块 | MVP 版本 | 完整版本 |
|------|----------|----------|
| 查询语义 | RT 查询（recall target）| RT + PT 双目标 |
| 统计工具 | CLT + cluster-level independence 假设 | Block bootstrap / e-value |
| IoU 处理 | Conservative boundary extension（将 IoU ≥ θ 条件转化为帧级约束）| 完整 IoU-based CI |
| Oracle allocation | 简单的 boundary-priority 两阶段采样 | 完整 risk-aware allocation |
| 实验 | 5 个数据集，核心 GVR 实验 | 全参数 sensitivity + ablation |

**如果想降低难度**:
- 限制查询类型为 single-predicate RT query
- 假设 τ（最小 clip 长度）足够大，使 boundary uncertainty 影响相对较小
- 忽略 clip merge/split，只对"当前 C̃ 不变时"提供保证

**如果想提高论文档次**:
- 扩展到 PT query（precision target）
- 引入 BARGAIN 的有限样本非渐近工具（e-value, conformal p-value）
- 支持 aggregation on clips（如"满足条件的 clips 的平均时长"）
- 推广到多谓词复合查询

**投稿建议**:

| 目标 | 推荐会议 | 理由 |
|------|----------|------|
| 首选 | VLDB 2026 (Research Track) | query processing + statistical guarantee 完美契合；ARC 在 SIGIR 25，上级会议是 VLDB |
| 备选 | SIGMOD 2027 | 同等档次；Kang 组的 SUPG/ABae 在此 |
| 扩展版 | TKDE / VLDBJ | 期刊版，可提供更完整的理论 |
| 若以检索语义为主 | SIGIR 2026 | 继承 ARC 的 SIGIR 投稿策略 |

---

*报告编写时间: 2025年5月*  
*调研范围: VLDB, SIGMOD, ICDE, SIGIR, MM, arXiv (2019-2025)*  
*调研确认不存在的工作: clip-level high-probability guarantee with IoU + oracle budget constraint*
