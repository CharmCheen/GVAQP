# GVAQP 下一阶段导师汇报报告

Date: 2026-08-24

## 一、结论先行

我建议将当前研究从“立即做人工事件效用论文”调整为“先完成 oracle-agnostic 查询执行系统，再用人工标注做外部有效性验证”，但不回到已经被证据否定的 controller/MAB/RL 路线。

新的核心方向是：

> 面向未扫描长视频和开放语义查询，在硬截止时间内联合安排候选发现与语义确认，并保证只有按时完成且持久化的独立事件进入查询结果。

推荐题目：

> **从未扫描视频到持久事件：面向开放语义查询的硬截止证据获取**

> **From Unscanned Video to Durable Events: Deadline-Safe Evidence Acquisition for Open-Semantic Queries**

当前已经完成 CPU 版本的统一算法合同、命令入口、单元测试和合成回放；尚未获得足以支撑 SIGMOD/VLDB claim 的真实多 workload 端到端结果。

## 二、问题背景

视频数据库查询通常依靠昂贵视觉模型将非结构化视频转换为可查询记录。对于自然语言描述的开放语义事件，模型调用成本更高，而且事件可能稀疏地分布在长视频中。若查询存在严格时间预算，系统不能先完整扫描、建索引，再进行语义判断，而必须在线决定：

1. 下一步扫描哪段尚未观察的视频；
2. 何时停止探索并确认已有候选；
3. 如何避免在截止时间前启动无法完成的工作；
4. 如何将多个重复 clip 合并为可持久化的独立事件结果。

因此，问题不只是模型推理加速，而是一个数据库执行问题：候选发现、昂贵谓词求值、预算分配、结果物化和截止语义必须共同设计。

## 三、为什么重要

现有工作常以帧准确率、正例 clip 数量、近似聚合误差或固定候选上的召回来评价系统。但真实查询用户通常需要的是按时返回的、去重后的语义事件。如果系统反复命中同一事件，clip yield 很高也可能没有更高用户效用。

更关键的是，在未扫描视频中候选并非预先存在。一次 SCAN 会创造后续 VERIFY 的机会，过早 VERIFY 可能错失尚未发现的区域，过度 SCAN 又可能来不及确认和提交结果。这个因果依赖使传统固定候选排序不能直接解决问题。

## 四、与最接近工作的关系

[BlazeIt](https://www.vldb.org/pvldb/vol13/p533-kang.pdf) 面向聚合与 limit 查询，利用专用网络和控制变量降低帧处理成本；[TASTI](https://cs.stanford.edu/people/matei/papers/2022/sigmod_tasti.pdf) 预构建可复用语义索引；[Seiden](https://www.vldb.org/pvldb/vol16/p2289-kakkar.pdf) 直接用 oracle 抽样建立 query-agnostic 索引。这些系统主要从已有帧或索引上选择执行策略，而本项目关注“尚未扫描区域如何产生候选”。

[ExSample](https://oscar-moll.com/assets/pdf/Moll_ExSample_ICDE.pdf) 是未索引视频自适应采样的直接基线，但主要针对对象搜索和实例去重，没有开放语义 oracle、确认阶段与硬截止持久化合同。[FiGO](https://hparch.gatech.edu/papers/jiashen_sigmod2022.pdf) 为不同视频 chunk 选择不同精度/成本模型，解决的是模型配置而不是发现与确认的因果调度。

[ZEUS](https://arxiv.org/abs/2104.06142) 是最接近的动作查询系统。它通过强化学习调整输入动作分类器的视频片段采样率、长度和分辨率，以满足准确率目标。它的重要启示是动作查询需要考虑连续片段而非单帧；但它假设优化对象已经是送入分类器的片段，没有显式建模 SCAN 才能产生 VERIFY 候选、截止前 durable commit 才计效用的约束。

[LAVA](https://arxiv.org/abs/2507.19821) 是最强的开放语义相邻工作：它结合 MAB segment localization、开放世界检测和轨迹抽取。它证明自然语言驱动的大规模交通视频查询已有强竞争者。因此本项目不能只声称“开放语义+自适应采样”，而必须证明硬截止、因果候选暴露和 durable event materialization 构成新的系统问题，并带来可测量收益。

## 五、当前仓库真实状态

仓库中已有许多实验，但它们并非一个完整系统：

1. proxy audit 说明廉价证据并不完美；
2. fixed-candidate oracle 实验说明确认预算存在理论重分配空间；
3. 108 个构造状态中 SCAN-better 与 VERIFY-better 都存在，但自然比例未知；
4. 学习得到的状态策略反而弱于 always-VERIFY，因此不支持 controller；
5. 两个 query 的最优固定策略名称不同，但相对全局固定策略的增益只有 0.000585 AUC，不足以支持 universal planner；
6. batching 的 CPU headroom 只有 0 到 0.003，不构成论文机会；
7. temporal bisection 在两个同源 trace 中恢复过一个 deadline-safe event，但证据仅为探索性。

此前实现也存在不一致：历史 replay controller 使用 largest-gap scan 和 25% scan target，而保留下来的研究方向是 breadth-first temporal bisection 和固定 1:1 SCAN/VERIFY。现在已经新增统一的 `DATB_SV_CPU_REPLAY_V1` 实现。

## 六、我设计的算法

算法名为 **Deadline-Aware Temporal-Bisection SCAN/VERIFY，DATB-SV**。

其执行过程为：

1. 将视频划分为不可变 temporal cells；
2. 用 breadth-first temporal bisection 决定 SCAN 顺序，使早期扫描覆盖整个时间轴；
3. SCAN 后产生候选，未暴露候选禁止 VERIFY；
4. 以固定 1:1 顺序交替执行 SCAN 与 VERIFY，首选动作不可执行时才安全回退；
5. 每次动作前用保守时延上界和 commit reserve 判断能否在 deadline 前完成；
6. 只有 oracle 确认且在 deadline 前原子提交到 EventRelation 的事件才计入效用；
7. 相同 event ID 去重，deadline 后完成的结果只进入诊断日志。

这一版本故意不使用学习控制器。原因不是算法简单，而是现有数据没有证明学习复杂度有必要。

## 七、VLM 标签与人工标注分别有什么作用

VLM 标签可以承担开发 oracle：用于实现算法、CPU replay、基线比较、消融和 oracle-relative 性能评价。算法本身只依赖统一的 `confirm(candidate, query)` 接口，因此可以替换为 heavy model 或人工判断。

但“算法与 oracle 实现解耦”不等于“科学结论与标注来源无关”。如果 VLM 系统性漏掉某类事件，那么算法在 VLM 标签上的最优结果只能说明它更擅长满足这个 VLM oracle，不能说明更符合人的查询意图。

因此人工标注可以后置，但不能被永久删除。最合理顺序是：

1. 先用冻结 VLM 标签完成算法和 workload-level 实验；
2. 在看到人工结果前冻结算法、输出、pair 和统计协议；
3. 最后用独立人工 maximal semantic events 验证外部有效性；
4. 人工结果不能再用于调整算法。

## 八、已经完成的 CPU-only 工作

已完成：

1. 统一 DATB-SV replay runner；
2. 单命令 CPU replay 入口；
3. deadline admission、durable commit、去重和 oracle-source invariance 测试；
4. 六项 CPU 单元测试全部通过；
5. synthetic 端到端回放通过，执行 6 次 SCAN、4 次 VERIFY，按时提交 3 个去重事件，并以 `NO_COMPLETE_ACTION_FITS` 安全停止。

这些结果证明实现合同正确，但不证明算法性能优于基线。

## 九、下一步实验设计

第一阶段是 CPU-only 的真实缓存 trace replay。必须先恢复或正式退役缺失的 endogenous scan preflight provenance，确保每个候选的暴露来源、SCAN/VERIFY 成本和 oracle 输出来自同一可比较路径。然后比较 DATB-SV、uniform scan、sequential scan、largest-gap scan 和多个固定 SCAN/VERIFY ratio。

主要指标是 `DistinctCommittedEvents@Deadline`，辅助指标包括 anytime utility AUC、首个事件延迟、deadline 浪费、暴露召回和 cost-bound violation。统计单位应为 `video x query`，不是 raw pair。

第二阶段需要同一硬件和同一路径上的物理成本测量。当前 2.018542 秒的 scan pilot 与 18.694820 秒的 cached Qwen verify timing 不可配对，不能直接作为论文 cost ratio。这一阶段需要 GPU，当前标记为 `BLOCKED_BY_NON_CPU_REQUIREMENT`。

第三阶段扩展预注册 query/video workloads。至少需要多个独立 workload 才能判断收益是否由单一视频或 query 驱动。不能因为初步结果弱而事后增删 query。

第四阶段才进行人工 maximal-event 外部验证，回答 equal positive yield 是否等于 equal human-event utility。

## 十、三方评审后的决策

Qwen、Seed、Claude 都认为人工事件测量方案当前强于原 controller 方案。三方对方案 A 的评分分别为 4.30、3.37、3.36，对方案 B 的评分分别为 3.08、2.49、2.62。

这些结果不意味着必须立即做小规模人工标注。Seed 建议的 30-40 pairs 和 Claude 建议的两个 workload 都不足以形成独立样本支持，而且容易产生“看到结果再决定”的风险。更稳妥的整合决策是：

> 延后人工评价，先完成确定性、oracle-agnostic 的查询算法；但不重启 learned controller，并保留人工标注作为最终外部效度 gate。

## 十一、顶会潜力判断

当前版本还不具备 SIGMOD/VLDB 投稿成熟度。它具有潜在顶会问题形态，但必须形成以下证据闭环：

1. 证明 discovery 与 verification 的因果耦合会实质改变 deadline query plan；
2. 在统一物理成本下，DATB-SV 对强基线有稳定、非平凡收益；
3. 收益跨多个独立 video-query workload 成立；
4. durable event 评价与 frame/clip yield 得出不同系统结论；
5. 与 ExSample、ZEUS、Seiden、FiGO、LAVA 的边界和公平比较成立。

如果 algorithmic effect 很小或仅存在于单一 workload，应停止“新算法”包装，转为更诚实的 measurement/negative-result 论文。若 human event utility 最终与 clip yield 高度一致，也应报告正例 clip 已是良好代理，而不是事后修改事件定义。

## 十二、未来展望

只有固定策略在多 workload 上显示稳定 headroom 后，才有理由重新考虑 query-aware planner。届时需要先证明三个条件：策略异质性、状态可学习性和自然 workload 中的非平凡出现率。当前三者均未同时成立。

更长期可以研究跨 oracle 的鲁棒调度、带不确定时延分布的 admission control、事件级增量物化，以及多个查询共享扫描结果。但这些都不应先于当前端到端证据闭环。

## 十三、唯一下一步

**执行 CPU-only 的 `RECOVER_OR_RETIRE_ENDOGENOUS_SCAN_PREFLIGHT_PROVENANCE`：恢复则绑定到 DATB-SV 真实 replay；无法恢复则正式撤销相应历史性能主张。**
