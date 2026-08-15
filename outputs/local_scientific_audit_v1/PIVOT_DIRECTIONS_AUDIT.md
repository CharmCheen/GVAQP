# GVAQP 转向方向审计：7 个候选 Idea 的详细论证

> 生成依据：`local_scientific_audit_v1` 审计结论 + `NOVELTY_CLAIM_MATRIX.csv`
> 9 维度威胁矩阵 + 本轮补充检索。方法论：CCF Idea Optimizer
> （intake 字段 + 问题-方法蓝图 + 创新类型 + 风险登记）。
> 目标会场假设：VLDB 主会 / SIGMOD / VLDBJ；信息检索侧以 SIGIR 为参照。
> 重要约定：每个 idea 的"科学价值"与"本机执行可行性"分开陈述——本机无 GPU，
> 需要 GPU 的 idea 不等同于不可做，而是标注执行前置条件。

---

## 0. Venue Lens（会场视角总纲）

VLDB 审稿人要三样东西：(1) 问题在数据管理社区有意义（不只是 CV/IR 问题）；
(2) 方法在最近工作减法后仍有非平凡差异；(3) 系统/测量证据达到"多数据集 +
真实负载 + 直接基线对照"标准。SIGIR 要求任务-用户-检索相关性与强实验。
按审计矩阵：机制层（proxy+oracle、自适应采样、资源调度、覆盖获取、事件
重建）novelty delta 基本为 EMPTY，因此**新 idea 必须落在 问题层/契约层/
评估层/测量层**，否则必然被减法击杀。以下 7 个 idea 全部按此过滤。

## 1. Normalized Idea Table（总览）

| # | Idea | 创新类型 | 矩阵关系 | 本机可行性 | 会场 | 开发标签 |
|---|---|---|---|---|---|---|
| I1 | 廉价感知自然漏检的测量与证伪研究 | 经验发现+协议 | D8 的前提未测 | 需 GPU+人工 | VLDB(测量)/SIGMOD | needs-feasibility-check |
| I2 | 因果暴露+单时钟+完成式记账的确认事件查询契约 | 新设定+系统设计 | D7+D8 残余槽 | 需 GPU(证据)/CPU(契约) | VLDB | needs-evidence-design |
| I3 | 自适应视频查询策略的可信离线评估协议 | 评估方法+协议 | 审计失败转贡献 | CPU 可做主体 | VLDB/SIGMOD | needs-literature-search |
| I4 | 内生候选生成基准（causal exposure benchmark） | 数据/基准 | D8 的载体 | 契约 CPU；运行需 GPU | VLDB 或 NeurIPS D&B | needs-domain-constraint |
| I5 | 产量最大化→事件级效用的可证明刻画 | 理论结果 | C-A/C-C 的收口 | 纯 CPU 可证 | VLDB(理论)/PODS 边缘 | needs-mechanism |
| I6 | 完成式记账的 anytime 质量语义与安全预留调度 | 理论+小系统 | 与流式威胁正面区隔 | CPU 模拟+证明 | VLDB | needs-search |
| I7 | 确认事件关系的获取溯源（acquisition lineage） | 系统设计 | D7 的差异化子集 | 复用本地缓存日志 | VLDB | near-pivot |

开发路线建议（非打分排名）：**最佳开发路线 = I1（测量，钥匙）→ I2（契约，
主论文）**；**备份路线 = I3（评估协议，最省资源）或 I5（理论，唯一纯 CPU
可独立成文）**。I4/I6/I7 仅在主路线证据到位后作为配套或后续考虑。

---

## 2. 逐 Idea 详细论证

### I1 廉价感知自然漏检的测量与证伪研究

- **Task**：在真实原始视频 × 多查询 × 多廉价检测器上，系统测量自然曝光漏检
  （sensor 未产出候选/证据）的流行率、幅度、可调度挽回性、与预测难度。
- **Gap**：整个自适应感知-验证文献（LAVA/ARC/Seiden/ExSample 谱系）都隐含
  假设"廉价感知会漏检且漏检可通过调度挽回"，但**没有一篇工作系统测量过该
  前提**；GVAQP 自己的审计证明该前提在预计算基板上构造性不成立。
- **Root challenge**：不是"漏检率是多少"，而是把"漏检"定义成可测量量：需要
  独立语义引用（人类事件边界）+ 因果暴露协议（SCAN 完成前候选不存在）+ 事
  后后悔分解（漏检是否被另一合法调度挽回 = SCHEDULING_RECOVERABLE vs
  SENSOR_SUPPORT）。
- **Core insight**：前提本身是经验命题，且可能是假的；无论真假，第一次把它
  变成可测量、可复现的量，就是贡献——正结果建立问题存在性，负结果证伪一
  个被多篇论文共享的隐含假设。
- **Proposed mechanism（测量协议）**：冻结 P4 式最小基板（本地已有
  `MINIMUM_FAITHFUL_P4_SUBSTRATE.md` 规格）→ 多源视频（≥5）× 多查询（≥3）
  × 多检测器（YOLOv8n / 光流 / 触发式跟踪）× 前瞻状态日志含行为倾向 →
  报告 漏检率、漏检的可挽回比例、事后 SCAN-vs-VERIFY 后悔的流行率/幅度/
  跨视频可预测性、扣除实测成本后的净值。
- **Contribution type**：新经验发现 + 测量协议（可独立被引用的标准）。
- **Expected evidence**：漏检率分布；miss taxonomy（no_object_class /
  low_confidence / temporal_truncation…）；后悔流行率（自然状态加权，非
  截断抽样）；wrong-deviation downside；跨源复现性。
- **Why now**：2025–26 流式/自适应视频查询工作爆发（[QueryStream ICLR'26](https://mlanthology.org/iclr/2026/zhang2026iclr-querystream/)、[ProtoKV](https://arxiv-org.ezproxy.obspm.fr/html/2606.26762v1)、[StreamReady CVPR'26](https://www.openaccess.thecvf.com/content/CVPR2026/html/Azad_StreamReady_Learning_What_to_Answer_and_When_in_Long_Streaming_CVPR_2026_paper.html)），全部继承同一未验证前提。
- **Main risk**：负结果论文在顶会方差大；检测器误差测量本身有近邻（如
  [Momentarily Missed Detection WACV'20](https://mlanthology.org/wacv/2020/hosoya2020wacv-analysis/)），但"面向查询调度的可挽回性测量"未见占位——需进一步检索确认（needs-feasibility-check）。
- **本机可行性**：低（需 GPU 跑检测器 + 人类引用）；协议与代码骨架可本机冻结。
- **决定性证据**：漏检近零或后悔罕见→终止主路线（转为负结果论文）；非罕见
  且可预测→I2 的前提成立。
- **Best venue**：VLDB 测量类 / SIGMOD；负结果走 TOS 或 experimental track。

### I2 因果暴露 + 单时钟 + 完成式记账的确认事件查询契约（D7+D8）

- **Task**：形式化一个查询契约——候选只有在"一个已完成的 SCAN 暴露它"之后
  才因果地存在、VERIFY 才合法；输出是逐动作原子提交的持久确认事件关系；
  截止期按动作**完成时刻**记账；在此契约下给出合法调度类与确定性执行器。
- **Gap**：先验系统各占碎片——ARC 先穷举代理（无因果暴露）、Seiden 输出
  推测性插值（无确认语义）、LAVA 用 bandit 采样（无持久关系）、渐进式系统
  输出连续近似（无"确认"边界）。**没有系统完整拥有契约组合**（矩阵 D7
  threat=MEDIUM，唯一残余槽）。
- **Root challenge**：契约差异不是措辞差异——它改变合法动作集（endogenous
  action creation）、anytime 定义（完成式 vs 启动式）、可审计性（哪些事件在
  何时因哪些动作而成立）。
- **Core insight**："causally exposed sensing + single physical clock +
  completion-based deadline accounting + confirmed durable EventRelation"四件
  套的组合使"确认输出"从渐进近似的特例变成一个可严格记账的查询语义。
- **Proposed mechanism**：契约公理化（暴露偏序、合法转移、完成谓词、原子
  提交、失败即回滚到上次持久状态）→ 确定性时间二分覆盖执行器（本地已有
  DATB-SV 规格与单源实现）→ 因果合法性审计器（本地已有 H0 审计）→ 负设计
  证据（学习控制器在缓存基板失败 0.0097 vs 0.0009，物理探针 0/18、1/7）。
- **Contribution type**：新设定 + 系统设计证据（明确不宣称算法新颖性）。
- **Expected evidence**：≥3 独立源视频 × ≥2 查询；对 ARC/Seiden/LAVA 风格
  基线的直接对照；多检测器；完成式记账下 anytime 曲线；审计器证明无合法性
  违规。
- **Why now**：流式/延迟查询（ProtoKV、QueryStream）与渐进式确认正在相邻，
  但"确认+持久+因果暴露"的严格契约仍空置。
- **Main risk**：当前证据单源单事件，离 VLDB 评估标准差一个数量级；审稿人
  可能判为"engineering contract, no mechanism"。**必须由 I1 提供前提证据**。
- **本机可行性**：契约/审计器/重放全可 CPU；多源物理运行需 GPU。
- **决定性证据**：I1 正结果 + 多源复现中固定调度相对基线的 deadline-safe
  确认事件增益。
- **Rescue/pivot**：若多源运行不可得，降级为 VLDB workshop / TOS short；
  或与 I3 合并成"契约+评估协议"双贡献。
- **Best venue**：VLDB 主会（系统 track）。

### I3 自适应视频查询策略的可信离线评估协议

- **Task**：回答"用缓存日志离线评估自适应感知-验证策略，什么条件下结论才
  可信"，并给出协议+检查器+反例。
- **Gap**：本领域普遍用缓存重放评估自适应策略，但没人形式化重放偏差；
  GVAQP 审计恰好踩中全部坑：状态抽样非总体加权（`SAMPLING_VS_PREVALENCE
  =NOT_IDENTIFIABLE`）、无行为倾向、clairvoyant ceiling 不可达、policy
  isolation 泄露（pilot FAIL）、off-policy 转移动态缺失。
- **Root challenge**：不是"做一个基准"，而是给出**可判定的适用性条件**
  （何时重放结论外推到闭环有效，何时必须放弃）。
- **Core insight**：把审计失败清单升格为一般性评估科学：曝光因果检查 +
  propensity 覆盖要求 + ceiling 适用性判定 + 隔离审计，构成四道可自动化闸门。
- **Proposed mechanism**：协议（前置条件清单）→ 静态检查器（对策略代码做
  信息隔离审计，复用本地 isolation audit 经验）→ 对若干已发表系统的重放
  复检（ARC 风格公开代码）→ 反例集（展示违规时结论如何翻转）。
- **Contribution type**：评估方法/协议 + 经验发现。
- **Expected evidence**：检查器在真实系统上触发违规的案例；违反协议条件时
  排名反转的实证；合规重放与闭环的差距上界（若可证）。
- **Why now**：自适应视频查询论文爆发，评估可信度问题随之爆发。
- **Main risk**：被判"meta/负结果"拒稿；需要至少一个建设性系统演示立住。
- **本机可行性**：**高**（协议+检查器+重放复检全部 CPU；本地缓存日志现成）。
- **决定性证据**：能在一个已发表基线代码上复现"重放结论 ≠ 合规评估结论"。
- **Best venue**：VLDB/SIGMOD；SIGIR 若定位为"IR 策略离线评估"亦有空间。

### I4 内生候选生成基准（Causal-Exposure Benchmark）

- **Task**：发布首个"候选身份在查询时由感知因果生成"的公开基准（视频+查询
  +检测器+引用+暴露协议+代价模型+评估闸门），替代当前所有"候选预计算"基板。
- **Gap**：现有视频查询基准的候选宇宙几乎都预计算（含 GVAQP 的 1475/1475），
  因此无法测量获取误差——这是整个领域的方法学空洞。
- **Root challenge**：把"内生"做成硬约束而非文档承诺：候选在 SCAN 完成前对
  策略与评估器都不可见（需在基准代码层强制）。
- **Core insight**：一个领域的方法学空洞 = 一个可被基准论文占据的生态位；
  基准的 adoptability 来自它让 I1 类测量"开箱即用"。
- **Contribution type**：数据/基准 + 协议。
- **Expected evidence**：基准设计文档 + 冻结契约 + 3–5 个基线系统的公平重跑
  + 暴露合规检查器通过记录。
- **Why now**：与 I1 同源；流式基准（StreamReady 等）近邻但无"因果暴露"
  硬约束。
- **Main risk**：基准论文需要社区采纳故事；单独成文弱，通常作为 I1/I2 的
  配套发布。
- **本机可行性**：契约与检查器 CPU；数据生成与基线重跑需 GPU。
- **Best venue**：随 I1/I2 发布，或 NeurIPS D&B / VLDB benchmark track。

### I5 产量最大化 → 事件级效用的可证明刻画

- **Task**：在 gap-合并物化器（C1）下，刻画"记录级正例产量最大化"何时等价
  于事件级召回/EventF1 最优——给出充分条件、反例族、与几何量的联系。
- **Gap**：GVAQP 观察到产量最优 ≠ 事件最优（几何 R² 0.795 的模型相对关联），
  但没有理论说明差距何时出现、多大、如何闭合。
- **Root challenge**：事件效用是"锚点集合→合并区间"的集值函数，非次模；
  需要新刻画（锚点间距 vs 合并阈值的组合结构）。
- **Core insight**：gap 合并可看成对时间轴的区间覆盖组合问题；产量最优
  只在"正例间距分布满足某种规律"时事件最优——可证的反例来自间距双峰/空洞。
- **Proposed mechanism**：组合刻画（例如锚点集合的 gap 图）+ 最坏情况比 +
  在线选择下的差距界 + 与本地 378 格数据的诊断性吻合验证（不训练）。
- **Contribution type**：理论结果 + 诊断分析。
- **Expected evidence**：定理（充分/必要条件）+ 构造反例 + 在公开代理质量
  分布上验证条件的经验成立度。
- **Why now**：代理+oracle 预算文献的理论都止于记录级指标；事件级效用理论
  空置。
- **Main risk**：needs-search——覆盖/子模/代表性抽样理论可能已有等价刻画；
  且理论若与真实代理分布脱节，审稿人判"toy"。
- **本机可行性**：**纯 CPU 可证、可仿真、可诊断**（唯一完全不依赖 GPU 的
  独立成文路线）。
- **Best venue**：VLDB（theory/analytics）；若纯组合可试 PODS。

### I6 完成式记账的 anytime 质量语义与安全预留调度

- **Task**：形式化"动作完成时刻计入截止期"下的 anytime 质量曲线、安全预留
  调度（commit reserve）与保守准入策略的理论与仿真验证。
- **Gap**：渐进式查询（[ProgressiveDB](https://www.vldb.org/pvldb/vol12/p1814-berg.pdf)）的 anytime 语义基于启动时刻；物理系统里完成时刻决定可见性（本地广州证据：晚完成→被排除）。
- **Root challenge**：随机动作时长 + 完成谓词使质量曲线成为随机过程的停时
  泛函；保守预留的代价-安全权衡需要可证界。
- **Core insight**：完成式记账把"提前启动的乐观结果"变为"不可见"，这改变
  最优调度的形态（本地 A/C 政策归零、B 政策赢 1 事件即此现象的最小实例）。
- **Proposed mechanism**：停时模型 + 预留上界（基于本地 cost model 的 q90
  经验分布）+ 保守准入的后悔界 + 仿真在本地成本分布上的验证。
- **Contribution type**：理论 + 小系统证据。
- **Expected evidence**：定理（预留充分条件下的 deadline-safe 保证）+ 仿真
  对照 + 与 流式近邻（ProtoKV/QueryStream）的语义区隔表。
- **Why now**：流式"何时回答"工作（StreamReady）与其相邻，但"确认+持久+
  完成记账"的严格语义仍无人形式化。
- **Main risk**：needs-search——deadline 约束查询处理老文献可能已覆盖核心界；
  与 I2 契约重叠，可能被吞并。
- **本机可行性**：CPU 模拟+证明可做；物理验证需 GPU。
- **Best venue**：VLDB；或作为 I2 的理论节。

### I7 确认事件关系的获取溯源（acquisition lineage）

- **Task**：为持久事件关系的每个事件维护"获取溯源"——是哪些 SCAN 暴露、
  哪个 VERIFY 确认、哪条 gap 合并使该事件在 t 时刻变得可确认并持久。
- **Gap**：lineage 在数据库/分析 UDF 语境成熟（[Augmented lineage VLDBJ](https://acm-stag.literatumonline.com/doi/10.1007/s00778-022-00769-7)），但"预算获取行为对确认视频事件的因果溯源"无人做。
- **Root challenge**：事件是多个动作的联合产物（暴露→确认→合并→持久），
  溯源需在动作级重放中可判定、可压缩、随预算单调。
- **Core insight**：确认式输出的最大卖点是"可信"，而可信需要可解释性——
  获取溯源是把审计器（H0 审计）从方法学工具变成面向用户的输出特性。
- **Proposed mechanism**：动作级 provenance 图 + 压缩表示（minimal witness
  set）+ 增量维护（随持久提交原子更新，复用本地 commit/fsync 实现）。
- **Contribution type**：系统设计。
- **Expected evidence**：本地缓存日志上端到端溯源正确性 + 存储开销 + 对
  "为什么这个事件在 224s 出现"的最小实例演示。
- **Why now**：LLM 生成内容的可追溯性正热；视频事件确认的可追溯性是其
  数据库版。
- **Main risk**：near-pivot——lineage 非新概念，若无 I2 契约承载则易被评
  为"标准 provenance + 视频应用"。
- **本机可行性**：高（复用本地缓存日志与 commit 实现，CPU 即可）。
- **Best venue**：VLDB；适合作为 I2 的差异化亮点或独立 short。

---

## 3. 交叉审查（内部一致性与矛盾检查）

- I1 是 I2/I4 的前提证据；I2 与 I6 有语义重叠（anytime 记账），写作时二选一
  或 I6 并入 I2 理论节——**不能同时把"完成式记账"写成两个贡献**。
- I3 与 I4 共享"评估科学"主题但方向相反（I3 审方法、I4 建载体），可作为
  姊妹篇；I5 与 I1 正反互补（I1 测前提、I5 证结构），无冲突。
- I7 依赖 I2 契约才有 novelty，独立成文时威胁最高——保留为"亮点"而非主线。
- 所有 idea 均不宣称算法机制新颖性（矩阵已证机制层 EMPTY），贡献类型严格
  限定在 契约/测量/评估/理论/系统 层——这是本次优化的核心纪律。

## 4. 风险登记（汇总）

| Idea | 致命风险 | 类型 | 最低化解 |
|---|---|---|---|
| I1 | 负结果论文接受方差 | requires-new-result | 正负结果双轨写作；测量协议本身独立可引 |
| I2 | "无机制、单源单事件" | evidence-fixable | 多源复现+直接基线；与 I1 绑定投稿 |
| I3 | 判为 meta 拒稿 | writing-fixable | 至少一个建设性系统演示+反例翻转实验 |
| I4 | 采纳故事弱 | likely-pivot | 不单独成文，作 I1/I2 配套发布 |
| I5 | 已有等价刻画/toy | needs-search | 先做 2 天检索；用本地 378 格数据做诊断验证 |
| I6 | 与 I2 重叠被吞 | design-fixable | 并入 I2 理论节 |
| I7 | lineage 无新颖性 | near-pivot | 仅作 I2 亮点 |

## 5. 推荐下一步（不评分、只给开发路线）

**主开发路线：I1 → I2**。理由：I1 测量的是整个自适应谱系共享的未验证前提，
正负结果都产出可引贡献，且其产物（漏检率/后悔分布/倾向日志）恰好是 I2 契约
论文缺失的评估地基；两者共用同一忠实基板与同一人类引用，边际成本最低。

**备份路线：I3 或 I5**。若 GPU/人类标注长期不可得，I3（评估协议，CPU）与
I5（理论刻画，CPU）是唯一两条本机可独立推进到可投稿雏形的路线；其中 I5
最"轻"（无新数据），I3 最"稳"（复用审计已踩过的坑）。

**写作就绪度**：I2/I3/I5 具备 idea 级就绪；全部 idea 在动手前需补一轮
针对各自 novelty 的定向检索（I5、I3 标 needs-search），并对照
`NOVELTY_AUDIT_NOTES.md` 的 52 条已有查询避免重复劳动。
