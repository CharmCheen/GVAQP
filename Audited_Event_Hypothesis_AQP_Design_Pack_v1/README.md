# Audited Event-Hypothesis AQP：长驾驶视频安全事件查询课题设计包

**版本**：v1.0  
**冻结日期**：2026-07-10  
**用途**：作为研究者、工程 agent、评测 agent、标注 agent 和论文写作 agent 的统一 source of truth。

## 1. 一句话课题定义

在长第一视角驾驶视频中，cheap primitives / proxy 对稀有安全事件并不可靠，而 expensive oracle（VLM 或人工）只能调用有限次数。系统需要在预算约束下发现、验证、去重并定位安全事件，并对仍可能漏掉的事件给出可审计的剩余质量估计。

最终目标方法暂定名：

> **Audited Event-Hypothesis AQP（AEH-AQP）**：维护 actor-centric event hypotheses，以事件级 typed probes 自适应分配 oracle budget，并通过独立 audit ledger 估计 residual missing-event mass。

当前已经有实证支持、可以作为稳定基线的系统层是：

> **MAP-BBEM** = Materialization-Aware Anchor Probing + Bounded / Barrier-aware Event Materialization。

## 2. 当前结论：必须区分“已成立”和“目标算法”

| 状态 | 内容 | 当前判断 |
|---|---|---|
| `PILOT_CONFIRMED` | clip evidence 到 event output 存在 materialization gap | 成立 |
| `PILOT_CONFIRMED` | K3 BB-EM：gap limit + duration prior + queried-negative hard barrier | 已冻结为 pilot 最小 materializer |
| `PILOT_SUPPORTED` | MAP-anchor-only 在共享 K3 下改善低预算 unique-event discovery | 初步成立 |
| `OPEN` | K3/C6 完全相同是否因可选机制从未触发 | 必须做 trigger/path audit |
| `OPEN` | MAP-anchor-barrier 在 B=100 的 overcoverage 反弹原因 | 必须做 lineage forensics |
| `TARGET` | actor-centric hypothesis graph + typed query planner | 尚未形成完整方法 |
| `TARGET` | independent audit ledger + residual-mass certificate | 尚未验证 |
| `NOT_CLAIMABLE` | 完整 SEHS 已有效、统计 guarantee 已成立 | 当前不能声称 |

Pilot 结果、K3 压缩与 Stage 1A MAP 结果来自现有 replay 产物与项目记录；在跨视频、人工 adjudicated ground truth 和代码路径审计完成前，不得泛化为最终论文结论。

## 3. 文档导航

| 文件 | 主要读者 | 内容 |
|---|---|---|
| `MASTER_RESEARCH_DESIGN.md` | 全体 | 单文件总体课题设计：问题、方法、算法、评测、路线与 agent 契约 |
| `01_PROJECT_CHARTER.md` | 全体 | 研究问题、范围、已验证结论、非目标和贡献层次 |
| `02_FORMAL_QUERY_MODEL.md` | 算法 / 理论 agent | 正式问题定义、事件语义、canonical anchor、关系模式和成本模型 |
| `03_METHOD_ARCHITECTURE.md` | 实现 agent | BB-EM、MAP、Minimal SEHS-node、目标 AEH-AQP 的算法规范与伪代码 |
| `04_EXPERIMENT_PROTOCOL.md` | 评测 / 数据 agent | 数据、baseline、公平性、ceiling、指标、统计检验和泄漏禁令 |
| `05_ROADMAP_AND_GATES.md` | 项目管理 | 阶段路线、GO/NO-GO、kill criteria 和依赖关系 |
| `06_AGENT_OPERATING_MANUAL.md` | 所有 agent/LLM | 工作规范、状态标签、输入输出契约、交接模板 |
| `07_AGENT_TASK_QUEUE.md` | 执行 agent | 可直接领取的任务规格与完成标准 |
| `08_REPO_AND_REPRODUCIBILITY.md` | 工程 / 复现 agent | 仓库同步、目录结构、artifact manifest、版本和发布流程 |
| `09_PAPER_POSITIONING.md` | 研究 / 写作 agent | 与 ARC、SUPG、ABae、Seiden、EQUI-VOCAL、LOTUS 的差异和论文 claim |
| `10_RISK_REGISTER.md` | PI / 红队 agent | 严重风险、mitigation 和明确 kill criteria |
| `11_FROZEN_CONFIG_FOR_CROSS_VIDEO.md` | 实验 agent | 当前已知参数、provenance、冻结规则和待从代码提取项 |
| `12_DECISION_LOG.md` | 全体 | 关键决策、被废弃论点、证据状态和变更规则 |
| `13_REFERENCES.md` | 文献 agent | 主要一手文献和本课题对应关系 |

## 4. Source-of-truth 优先级

发生冲突时按以下优先级处理：

1. **冻结配置与正式实验协议**：`11_FROZEN_CONFIG_FOR_CROSS_VIDEO.md`、`04_EXPERIMENT_PROTOCOL.md`。
2. **本设计包的决策记录**：`12_DECISION_LOG.md`。
3. **代码与生成 artifact 的 manifest / hash**。
4. **阶段性 FINAL_REPORT.md 与 sanity report**。
5. 讨论记录、旧 G-ARC 文档、未同步笔记。

任何 agent 发现 1–4 之间不一致，必须停止新增实验，先输出 `BLOCKED_BY_SOURCE_CONFLICT` 报告。

## 5. 当前最近的正确下一步

在 cross-video validation 之前，先完成以下 preflight：

1. K3/C6 materializer trigger/path audit。
2. Stage 1B B=100 overcoverage lineage forensics。
3. SUPG all-selected 与 confirmed-only 路径审计。
4. 从实际代码提取并冻结所有 pilot-selected 参数。
5. 同步服务器最新 adapter、BB-EM、MAP 和 replay artifacts 到主仓库或可复现分支。
6. 建立人工 adjudicated event schema 与 canonical-anchor 标注协议。
7. 运行三类 ceiling：candidate、oracle-informed planner、materializer。

只有 preflight 与 ceiling gates 通过，才实现 Minimal SEHS-node；只有 Minimal SEHS-node 在 held-out videos 上有增量，才投入完整 graph、VOI 和 certificate。

## 6. 禁止事项

- 不得用 reference events 或未查询 `oracle_label` 选择 query。
- 不得 per-budget 选择最优 baseline 配置并包装成 Ours。
- 不得把 boundedness 指标用来掩盖 `overlap_any` 主指标上的真实劣势；两类结果必须并列报告。
- 不得把 VLM-defined reference 称为人工 ground truth。
- 不得把 design invariant 称为统计 guarantee。
- 不得在 cross-video validation 看到结果后继续调整冻结参数。
- 不得仅凭“使用 event graph”宣称数据库算法创新。

## 7. 项目成功的最低闭环

一篇可信的系统论文至少需要同时成立：

1. **Event operator**：BB-EM 在多个 selector、多个视频上稳定改善 event-set materialization，而非仅修一个实现 bug。
2. **Query-time state**：Minimal SEHS-node 在共享 materializer、同预算、held-out videos 上显著改善事件发现。
3. **Candidate coverage**：hypothesis space 对人工 GT 的 ceiling 足够高。
4. **Independent validation**：多视频、人工 adjudication、外部数据源、参数冻结。
5. **Honest completeness story**：若没有有效 residual certificate，则明确写成 empirical anytime system；若 certificate 通过 coverage test，再升级 AQP guarantee claim。
