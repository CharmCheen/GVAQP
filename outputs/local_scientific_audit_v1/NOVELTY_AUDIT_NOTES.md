# GVAQP 新颖性/相关工作审计笔记（NOVELTY AUDIT NOTES）

审计者：GVAQP 本地科学审计子代理（novelty/related-work）
审计日期：2026-08-13（仓库状态日期同源）
方法：独立 web 检索（web_search，可访问网络）+ 仓库内既有引文交叉验证。
产出：`NOVELTY_CLAIM_MATRIX.csv`（本目录）+ 本笔记。网络**可用**，无 SEARCH_BLOCKED。

## 0. 被审计对象（GVAQP 当前最强证据分支）

- (1) 代理（cheap SCAN/proxy）排序误差在低预算下造成 EventF1 缺口 0.0951（曝光误差为 0，即瓶颈是 ranking 而非 exposure miss）；
- (2) 固定 C1 gap 物化器（10 秒合并规则）相对 K0 的中位 ΔF1 +0.1457，机制消融显示几乎全部增益来自 gap 约束（中位 +0.1377）；
- (3) 自适应控制器（MAB/RL/bandit）被本地证据判 NO-GO（0/18 一步正例、1/7 延续转化、学习后悔率劣于固定策略）。
- 主算法方向：DATB-SV（确定性 temporal-bisection 覆盖 + 固定 1:1 SCAN→VERIFY 交错 + 硬截止期准入 + 原子提交的持久 EventRelation）。

## 1. 检索查询记录（本会话实际执行的查询）

**核心命名工作：**
1. `SUPG "Approximate Selection with Guarantees using Proxies" VLDB 2020 Kang` → 确认 PVLDB 13(11) p1990（vldb.org PDF、ar5iv 2004.00827）。
2. `AQUAPRO "approximate queries over machine learning models" proxy oracle precision recall` → 确认 VLDB 2023 / PVLDB 16(4) p918（vldb.org PDF）+ arXiv 2206.02845。
3. `ThalamusDB multimodal video data management prioritization error time labeling` → 确认 "ThalamusDB: Approximate Query Processing on Multi-Modal Data", PACMMOD 2024, DOI 10.1145/3654989（dl.acm.org、saehanjo.github.io PDF）。
4. `Seiden "Revisiting Query Processing in Video Database Systems" VLDB 2023` → 确认 PVLDB 16(9) p2289（vldb.org PDF）。
5. `ExSample "Efficient Searches on Video Repositories through Adaptive Sampling" ICDE 2022` → 确认 IEEE ICDE 2022（document 9835550）。
6. `ARC "Approximate Relevant Clip Query" video repositories SIGIR 2025` → 确认 SIGIR 2025，DOI 10.1145/3726302.3729896（dl.acm.org；复旦 DAS 实验室录用公告）。注意：仓库 `NOVELTY_RISK.md` 写作 "ARC (VLDB 2025)"，本审计以 dl.acm 的 SIGIR 2025 为准。
7. `LAVA multi-armed bandit video segment sampling language-driven traffic video localization ACM MM 2025` → 确认 ACM MM 2025，DOI 10.1145/3746027.3754955，arXiv 2507.19821。
8. `Zeus SIGMOD 2022 learned video analytics segment length rate resolution` → 确认 "Zeus: Efficiently Localizing Actions in Videos using Reinforcement Learning", SIGMOD 2022, DOI 10.1145/3514221.3526181（dl.acm PDF + arXiv 2104.06142）。
9. `FiGO SIGMOD 2022 query processing video fidelity per-chunk` → 仅 AMiner 页面确认标题 "FiGO: Fine-Grained Query Optimization in Video Analytics"；DOI 10.1145/3514221.3517857 取自仓库既有审计（MAB §6），本会话未在 ACM 主页面复验。
10. `Aero SIGMOD 2025 ...` / `"Aero" database video query processing "10.1145/3725408"` → 确认 "Aero: Adaptive Query Processing of ML Queries", PACMMOD 2025, DOI 10.1145/3725408（dl.acm.org + Semantic Scholar）。
11. `MIRIS "fast object track queries in video" SIGMOD 2020` → 确认 SIGMOD 2020, DOI 10.1145/3318464.3389692。
12. `DIVA video analytics USENIX ATC 2021 ...`（三次变体）→ **未找到名为 DIVA 的视频系统论文**；ATC 2021 演讲链接（atc21/presentation/xu）解析为 "Video Analytics with Zero-Streaming Cameras"（Xu 等，arXiv 1904.12342）。判定：仓库中 "DIVA" 引文疑似误标/待查，见 §4。
13. `TASTI "Semantic Indexes..." SIGMOD 2022` → 确认 SIGMOD 2022, DOI 10.1145/3514221.3517897（dl.acm.org）。
14. `EFS ...` / `"EFS" efficient frame sampling video analytics system paper`（多次变体）→ **无法解析为具体系统**；命中不相关或歧义条目。
15. `MEC ...` / `"MEC" event detection cascade video analytics expensive model` → **无法解析为具体系统**；命中 ETSI MEC（移动边缘计算）、专利等歧义条目。

**2024–2026 扩展检索：**
16. `natural language video analytics LLM video database query optimization VLDB 2025 2026` → 命中 SemBench（PVLDB 19(8), DOI 10.14778/3811243.3811249, arXiv 2511.01716）、VisualWorld（UW）、KEN（执行引擎）、LazyVLM、MIRA（自适应路由）。
17. `LLM-assisted video analysis systems budget-aware verification semantic query 2025` → 命中 Video-RAG（NeurIPS 2025）、TV-RAG（2512.23483）、VideoSEAL（ICML 2026）、QuoTA（2503.08689）。
18. `adaptive temporal sampling video query deadline budget scheduling 2025 2026` → 命中 "When and Where to Look: Adaptive Visual Evidence Scheduling for Efficient Long Video Understanding"（arXiv 2608.03918，2026-08）。
19. `video event query progressive refinement proxy oracle sampling 2025 2026 arXiv` → 命中 FrameOracle（arXiv 2510.03584, ICML 2026）。
20. `"When and Where to Look" ...`（细节检索）→ 确认 arXiv 2608.03918；仅标题/条目级验证，未读全文。另命中 "Active Video Perception: Iterative Evidence Seeking for Agentic Long Video Understanding"（arXiv 2512.05774, CVPR 2026）。
21. `FrameOracle "what to see and how much to see" ...` → 确认 ICML 2026 poster + arXiv 2510.03584。
22. `SemBench semantic query processing engines benchmark VLDB 2025` / `SemBench arXiv 2511.01716 abstract ...` → 确认 PVLDB 19(8)（dl.acm）+ DEEM Lab 页面（2026-03-15）。
23. `LazyVLM neuro-symbolic video analytics IEEE` → 确认 arXiv 2505.21459（Özsu 组，OpenReview）。
24. `DoveDB declarative low-latency video database natural language` → 确认 VLDB 2023（PVLDB 16(12) p3906）。
25. `Vamos ...` → 命中的是 "Vamos: Versatile Action Models for Video Understanding"（ECCV 2024，CV 模型），**不是**仓库语境中的视频查询系统；不纳入矩阵。
26. `"One Ranking, Any Budget" Matryoshka evidence-to-context frame selection` → 确认 arXiv 2608.05707（2026-08）。
27. `"Event-Anchored Frame Selection" effective long-video understanding` → 确认 arXiv 2603.00983（2026-03）。
28. `joint sensing verification scheduling resource-aware query optimization video` → 命中 QueryStream（ICLR 2026，query-aware pruning）。
29. `EcoFrame adaptive frame selection video understanding GitHub` → GitHub AK-DREAM/EcoFrame，与 2608.03918 同主题；仅条目级。
30. `"coverage" vs "diversity" acquisition event detection video query optimization` → 命中 AdaRD-key（arXiv 2510.02778）、LFS（arXiv 2601.14594）、Ground-Cover-Refine（arXiv 2608.01660）、Content-Aware Key Frame Sampling 主题。
31. `anytime video analytics query deadline progressive results materialization` → 命中 EVA（materialized views，gatech）、"Hierarchical Event Memory"（ICCV 2025）。
32. `traffic video event detection query system STRIVE-D iFinder 2025 2026` → 命中 iFinder（dash-cam LLM grounding）、"Driving Video Retrieval for Complex Queries with Structured Grounding"（arXiv 2606.09109）。
33. `video database "event" materialization durable relation temporal semantic query processing 2025` → 命中 EVA、BilVideo 等早期 VDBMS；无直接 "durable EventRelation" 命中。
34. `"Active Video Perception" iterative evidence seeking ...` → 确认 CVPR 2026（openaccess.thecvf.com）+ arXiv 2512.05774。
35. `LLM cascade inference video query verification budget cost-aware 2025 2026` → 命中 Agentic-VideoRAG（IEEE 2026, cost-aware）、VideoRouter（query-adaptive dual routing）、VisualClaw（VLM API 成本削减 98%）。
36. `"temporal coverage" sampling video query efficiency diversity exploration 2025` → 命中 AdaRD-key、KFS-Bench（WACV 2026, arXiv 2512.14017）、Hierarchical Text-Guided Frame Sampler（arXiv 2510.27280）。
37. `"SCAN" "VERIFY" operators video query processing candidate generation verification pipeline` → 命中 "Think, Then Verify: A Hypothesis–Verification Multi-Agent Framework for Long Video Understanding"（CVPR 2026, arXiv 2603.04977）、CACR（ICML 2026）、NVIDIA VSS alert-verification 工作流（工业）。
38. `"temporal bisection" OR "bisection" sampling video query scheduling coverage` → 命中 LENS（ECCV 2026, adaptive spatio-temporal zooming）；无 "temporal bisection" 调度命中。
39. `"event recall" OR "event F1" deadline video query confirmed events materialized output` → 无相关学术命中。
40. `Anytime query processing video analytics early results approximate final guarantee 2024 2025` → 命中 QueryStream、MoVi（IEEE 2026）、LOVO（ICDE 2025, arXiv 2507.14301）、Video Monitoring Queries（arXiv 2002.10537）。
41. `LOVO efficient complex object query large-scale video datasets` → 确认 ICDE 2025。
42. `"Hierarchical Event Memory" online video temporal grounding ...` → 确认 ICCV 2025（openaccess.thecvf.com）+ GitHub OnVTG。
43. `"Think, Then Verify" ...` → 确认 CVPR 2026（openaccess.thecvf.com）。
44. `KFS-Bench ...` → 确认 WACV 2026（openaccess.thecvf.com + arXiv 2512.14017）。
45. `"Query-Driven Video Event Processing" Internet of Multimedia Things` → 确认 PVLDB 14(11) p2847（vldb.org PDF）。
46. `TRECVID surveillance event detection ...` → 确认 NIST TRECVID MED/SED 任务存在（2013–2017 页面）。
47. `"event relation" model video analytics materialized query result semantic events database` → 命中 VideoGraph（图模型视频查询，早期）、"Semantic Event Graphs for Long-Form Video QA"（arXiv 2601.06097）、URBANCLIPATLAS、阿里云 AnalyticDB 视频事件抽取（工业文档）。
48. `guaranteed approximate selection video clips high-probability recall precision ...` → 命中 SUPG（vldb.org）、ARC（dl.acm）；未发现 clip-level 高概率保证系统（这与仓库 G-ARC 调研的 gap 判断一致）。
49. `survey video analytics systems LLM 2025 semantic query processing databases` → 命中 "Video Understanding with Large Language Models: A Survey"（arXiv 2312.17432）等综述。
50. `"DIVA" video analytics system paper cheap expensive model passes` → 再次无 DIVA 系统命中（见 #12）。
51. `"Semantic Event Graphs" long-form video question answering abstract` → 确认 arXiv 2601.06097 + ENTER（NeurIPS 2024, event-based interpretable reasoning）。
52. `LazyVLM lazy video language model abstract skip irrelevant segments` → 确认 arXiv 2505.21459（lazy/neuro-symbolic）。

## 2. 逐维度判定（与 CSV 对齐）

### D1 proxy+oracle —— 威胁 HIGH，delta EMPTY（机制层面）
- 最接近：SUPG（VLDB 2020）、AQUAPRO（VLDB 2023）、ThalamusDB（PACMMOD 2024）、ABae（VLDB 2021）、TASTI（SIGMOD 2022）、BARGAIN（SIGMOD 2026，有限样本保证）。
- 重叠：代理打分全种群 + 自适应 oracle/标签预算分配 + precision/recall target + 误差目标。SUPG 的 RT/PT 即"代理 + 昂贵 oracle + 预算"的通用形式化；AQUAPRO 同时满足 P/R 双目标；ThalamusDB 在多模态数据上按 error/time/labeling 目标优先级化处理与标注。
- GVAQP 剩余差异：0.0951 缺口是"排序误差在低预算下的 EventF1 缺口"这一**诊断性测量**（模型相对、缓存子基底、曝光误差为 0），不是新机制；"事件级确认输出 vs 聚合估计"的差异与 ARC 的 clip 语义重叠。
- 判定理由：不得因"我们研究 event-level F1、他们研究 recall/precision"宣称新颖；预算下的 proxy 不完美问题已被系统性覆盖。

### D2 adaptive temporal sampling —— 威胁 HIGH，delta EMPTY
- 最接近：ExSample（ICDE 2022，MAB chunk 采样）、Seiden（VLDB 2023，查询期探索-利用采样）、ARC（SIGIR 2025，MAB-UCB 渐进采样）、LAVA（ACM MM 2025，MAB 段采样）；2026 LLM-视频侧：LENS（ECCV 2026）、AdaRD-key、AdaFocus、When-and-Where-to-Look（2608.03918）、FrameOracle（ICML 2026）、Ground-Cover-Refine、Adaptive Greedy Frame Selection（2603.20180）、KFS-Bench（WACV 2026）。
- 重叠：预算下"看哪些时间单元/帧"的选择；自适应与确定性方案都有大量近邻。
- GVAQP 剩余差异：自适应采样本身 GVAQP 内部已 NO-GO；确定性 bisection/largest-gap 覆盖是 farthest-point/low-discrepancy 采样的标准变体；"先时域铺开再验证"是单一来源（广州、单事件）的机制观察。
- 判定理由：本维度若作为主贡献必被 LAVA/ExSample/Seiden/ARC 及 2025–2026 帧选择文献直接覆盖。

### D3 resource-aware scheduling —— 威胁 HIGH，delta EMPTY/WEAK
- 最接近：Zeus（SIGMOD 2022，RL 选段长/率/分辨率）、FiGO（SIGMOD 2022，逐 chunk fidelity 规划）、Aero（PACMMOD 2025，自适应 ML 谓词/资源）、One-Ranking-Any-Budget（2608.05707，任意预算证据选择）、FrameOracle、MoVi、QueryStream（ICLR 2026）、VideoRouter、Agentic-VideoRAG（成本感知）。
- 重叠：受限算力下的"在哪里花钱"；预算自适应选择被广泛覆盖。
- GVAQP 剩余差异：硬 wall-clock 截止期 + 不可分割动作 + 完成式记账 + 原子持久提交——是系统/设计框架而非新调度机制；学习型/自适应调度正是项目内部已否决的方向。

### D4 NL video analytics —— 威胁 MEDIUM（拥挤但非 GVAQP 主张点），delta EMPTY
- 最接近：ARC（SIGIR 2025，带时序约束的 clip 谓词）、LAVA（语言驱动交通视频）、DoveDB（VLDB 2023，声明式 NL 视频库）、VQPy（VLDB 2023）、LazyVLM（2025）、SemBench（VLDB 2025/26，语义查询引擎基准）、iFinder / Driving Video Retrieval（2025–2026）。
- GVAQP 差异：GVAQP 的 "open-semantic" 查询语义继承自 LLM/VLM oracle，不贡献 NL 接口本身。该维度只定义查询类型。
- 判定理由：不得把"对 NL 查询做视频分析"当作新颖点。

### D5 coverage/diversity acquisition —— 威胁 HIGH，delta EMPTY/WEAK
- 最接近：AdaRD-key（2510.02778）、AdaFocus（2605.12954）、LFS（2601.14594）、Ground-Cover-Refine（2608.01660）、MMR（经典）、ExSample。
- 重叠：relevance+diversity 目标在长视频帧选择上正被密集研究（2025–2026）。
- 内部佐证：仓库 `p2_query_policy_novelty_killer_v1` 显示通用 relevance+coverage/MMR 与 StaticProxyRank 中位 ΔF1=0.0（平手）；C-I（equal-yield 几何假设）已 DISFAVORED。先验文献+内部诊断共同击杀"coverage-aware acquisition"头衔。

### D6 event reconstruction —— 威胁 HIGH，delta EMPTY/COVERED
- 最接近：TRECVID MED/SED 谱系、Query-Driven Video Event Processing（PVLDB 2021）、LOVO（ICDE 2025）、Hierarchical Event Memory（ICCV 2025）、Semantic Event Graphs（2026）、ENTER（NeurIPS 2024）、时域 grounding/动作定位中的 gap 分组（标准原语）。
- 重叠：从视频重建事件/时间片段；gap 约束合并是标准定位原语。
- GVAQP 剩余差异：K3 物化器的 10 秒 gap 合并规则即该标准原语；内部机制消融显示 gap 约束≈全部增益（中位 +0.1377），说明无复杂新机制；+0.1457 是模型相对缓存评估结果。
- 判定理由：不得因"我们物化为 EventRelation"而宣称 gap 合并新颖。

### D7 durable EventRelation —— 威胁 MEDIUM（唯一仍有空间的维度）
- 最接近：EVA（物化视图）、ProgressiveDB（渐进物化）、Hierarchical Event Memory（ICCV 2025）、Semantic Event Graphs（2026）、阿里云 AnalyticDB 视频事件抽取（工业）、ARC 确认结果输出。
- 重叠：持久/物化的语义视频输出。
- GVAQP 剩余差异：**未检索到同时拥有 (a) 确认事件关系在 (b) 单一物理时钟下 (c) 每动作原子提交且 (d) 完成式截止期记账的组合**。这是仓库自身定位（NOVELTY_RISK.md：single-clock durable-EventRelation contract）一致的最小残差槽。
- 判定理由与警示：这是系统/设计契约而非机制；需以广州单源/单事件证据支撑才可辩护；且"无先验工作拥有该契约"是**检索覆盖意义上的负命题**，非穷举证明。

### D8 causally exposed sensing —— 威胁 LOW-MEDIUM，delta NOT-FOUND（负命题）
- 检索未发现将"SCAN 完成才暴露候选、VERIFY 消耗候选、暴露合法性与延迟可见性、单一时钟"形式化的工作。最近概念邻居：MIRIS（增量精化）、Zero-Streaming Cameras（渐进 pass）、Think-Then-Verify、Active Video Perception、SUPG（对照：先全量打分再标注）。
- 判定理由：作为建模/实现约束有空间，但不是可发头条的机制；负命题仅由检索覆盖支持，如实标注为无法完全验证。

### D9 joint SCAN-VERIFY scheduling —— 威胁 MEDIUM-HIGH，delta WEAK/MEDIUM
- 最接近：Think-Then-Verify（CVPR 2026，假设生成→验证多智能体）、Active Video Perception（CVPR 2026，迭代证据寻求）、ARC（渐进精化）、Aero（自适应谓词调度）、ExSample/Seiden/LAVA（交错探索）、SUPG（对照：两阶段不交错）、DIVA/Zero-Streaming（渐进 pass）。
- 重叠：廉价/昂贵两阶段的交错被 ARC/ExSample/Seiden/LAVA 及 CVPR 2026 两篇直接覆盖。
- GVAQP 剩余差异：固定确定性 1:1 bisection 交错 + 硬截止期准入 + 完成式记账（DATB-SV）——范围受限的系统/设计主张，当前证据为单一来源单事件+同源复现。自适应共调度内部已 NO-GO，且与 LAVA/Aero/ARC 冲突。

## 3. 结论：唯一仍可能成立的 novelty 主张

**D7（durable EventRelation，结合 D8 的 causal exposure 作为其底座）是唯一仍有空间的维度**，且其成立形态必须收窄为：

> "一个单一物理时钟下、候选创建/因果暴露/昂贵确认/K3 去重/持久提交共享同一截止期的因果合法、硬截止期 physical-anytime 事件查询契约，以及确定性 temporal-coverage 执行器在既定工作负载上比 chronological 与 scan-then-verify 更早恢复截止期安全事件的设计证据。"

这与仓库自身冻结定位（MAB §9/§10、NOVELTY_RISK.md）一致。全部可头条机制——bandit/自适应采样（D2、D3、D9）、proxy+oracle 预算（D1）、gap 合并物化（D6）、coverage/diversity（D5）、NL 接口（D4）——均被近邻工作覆盖。且 D7 本身目前证据薄弱（单源/单事件、无独立人类参考），因此判定为"仍可能成立但未建立"。

## 4. 无法验证/存疑事项（诚实声明）

1. **EFS、MEC**：多次检索无法解析为具体论文/系统（可能是缩写歧义或仓库任务书中的代号）。矩阵中未列入；若后续能提供全名可补审。
2. **DIVA**：仓库既有审计引用 ATC 2021 演讲链接，但该链接实际解析为 "Video Analytics with Zero-Streaming Cameras"（Xu 等）。未找到名为 DIVA 的视频分析系统论文。判定：DIVA 引文疑似误标，其"cheap-to-expensive passes + validation + continuous results"的要旨由 Zero-Streaming Cameras 承担；本审计不发明替代引文。
3. **2026 新条目多为标题/条目级验证**：When-and-Where-to-Look（2608.03918）、One-Ranking-Any-Budget（2608.05707）、Event-Anchored Frame Selection（2603.00983）、AdaFocus、LFS、Ground-Cover-Refine、Semantic Event Graphs（2601.06097）、Think-Then-Verify、Active Video Perception 等以 arXiv/会议页面条目为准，未读全文；其与 GVAQP 的差异判定为标题/摘要级推断。
4. **"无先验工作拥有 single-clock durable EventRelation 契约"是负命题**：基于检索覆盖，非穷举；不排除未索引的工业系统或非英语文献。
5. **FiGO 的 DOI 与 venue** 来自仓库既有审计，本会话仅复验标题（AMiner）。
6. 未验证 2026-08 之后（审计日之后）的新 arXiv 条目；文献雷达建议后续用 ccf-literature-monitor 持续跟踪 D7 附近（EVA/event memory/event graph 谱系）的新工作。
