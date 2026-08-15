# GVAQP 本地科学审计最终报告（v1，仅 CPU，2026-08-13）

本报告是独立审计员对本地仓库 `/Users/charmcheen/FDU/入学前/GVAQP` 的最终
重建。全程未运行任何 Qwen/VLM/YOLO 推理、未训练、未启动 MAB/RL/控制器实验、
未改动任何项目状态文件。全部关键数字均用纯标准库 Python 从冻结工件重算
（56/56 项通过，见 `VERIFICATION_RESULTS.json`）。

## 1. 本地仓库与证据完整性

- Git：单分支 `main`，HEAD `973900696`（2026-08-13 "Consolidate GVAQP
  research state and experiment artifacts"）；无 worktree/stash/tag。
- 仓库自 `/qiuyeqing/llama_prl/G-ARC`（冻结提交 `5047241b…`）迁移而来；
  旁路研究暂存于 `/root/charm/GVAQP_side_rcsem`（仅存于 manifest 中的路径）。
- 核心冻结结果表全部本地可读且哈希自洽：4 个协议家族的 PROTOCOL_HASH 逐位
  复核通过；物理探针工件 sha256 与 `MAB_RESEARCH_DIRECTION_DECISION.md`
  引用值一致。
- 唯一重大缺口：声称的 `outputs/endogenous_scan_preflight_v1/` 本地不存在
  （13 个具名工件 0 命中）；人工 P1 标签 0 行（按设计待采集，非丢失）。
- 来源健康度判定：**PARTIAL**（绝大多数可验证；一个关键声称实验缺失）。

## 2. 可本地验证的实验与声明（A 级）

1. 代理质量弱且依赖视频：AUPRC 0.3146 / 0.2584 / 0.3112；1475 单元、251
   正例、候选曝光召回 1.0（构造性）。
2. 排名是已证实的瓶颈：R3 排名压力低预算中位 EventF1 缺口 0.095134；
   合成曝光压力缺口 0.000000（按冻结定义重推一致）。
3. 物化器效应真实但边界窄：54/54 控制对 K3 vs K0 40/14/0，中位 ΔF1
   +0.1457；机制消融显示几乎全部来自 10 秒 gap 规则（+0.1377），
   duration-cap / negative-barrier / 复杂 K3 边际全部 0.0。
4. 预算单调性：嵌套轨迹违规率 0.48%（调用数预算，非墙钟）。
5. 几何：模型相对 LOVO 宏 R² 0.0057→0.7953（含 reference-aware 0.9803）；
   但 VLM 影子仅 +0.000665 MAE、2/6 簇为正，P2 语义态残差 ABSENT。
6. 控制器：学习 regret 0.009693 vs 固定 always-VERIFY 0.000885；物理探针
   0/18、1/7；108 状态两组数字（25/26/57 与 5/5/98）已调和为同一批 delta
   的两种阈值/取向。
7. 人工 P1：协议冻结、哈希验证、0 标签——不可分析。

## 3. 仅存于历史报告/远端（B/C/D 级）

- 内生 SCAN preflight 的全部声称数字（0/36、0.1071 s / 18.4440 s、57/36
  状态、5 个自然漏检）= **REPORTED_REMOTE_UNVERIFIED**，不得用于科学论证。
- 被状态文件明确取代的旧路线图/设计包叙述（按规则取代，非冲突）。

## 4. 三条原始声明的独立重审

- **声明 A**（代理缺陷创造查询优化问题）：**PARTIALLY SUPPORTED**，且范围
  必须收窄为"完全预计算候选宇宙上的排名退化"；自然获取失败未被测量。
- **声明 B**（真实昂贵/不完全/内生 SCAN 需要状态依赖分配）：
  **NOT_ESTABLISHED**。缓存基板忠实实现"延迟可见性+VERIFY 合法性+验证
  反馈"，但没有内生感知、自然漏检、实测成本、自然状态流行率与人类效用；
  不可验证的 0/36 既不支持也不反驳。
- **声明 C**（事件感知获取比正例产量最大化更稳健）：**NOT_ESTABLISHED**。
  模型相对几何关联强（R² 0.7953）但引用循环风险高；VLM 影子与 P2 均为弱/
  负证据；人工 P1 挂起（0 标签）。

## 5. 物化器与引用循环

- K3 引用由**同一 Qwen3-VL-32B 模型标签 + 同一 K3 adapter 代码 + 同一配置
  哈希**在全网格上构造——对无条件事件级主张，**REFERENCE_CIRCULARITY_RISK
  = HIGH**；项目自评 `QUALIFIED_BUT_VALID` 与此一致。
- COMPLEX_K3_NOVELTY = NOT_ESTABLISHED（K3−C3 边际中位 0.0，0 正/4 负）。
- MATERIALIZATION_IMPORTANCE = LOW_TO_MODERATE（模型相对、gap-only）。

## 6. 控制器估计量调和（RECONCILED）

25/26/57（tie 1e-12，Q(SCAN)−Q(VERIFY) 对称口径）与 5/5/98（practical
delta 0.005，偏离默认 1:1 动作口径）是同一 108 状态的同一单步固定延续 Q
差；两轴（阈值、取向）不同，非矛盾。逐态复推 0/108 不一致。实践决策性
表述是 5/5/98（仅约 9% 状态 |delta|>0.005），且两个精度越界态贡献 96.6%
正向偏差值。

注：`CONTROLLER_ESTIMAND_MAP.csv` 使用控制器审计子任务内部定义的
保真度导向 A–E 方案（B=缓存抽象重放 / C=静态重推 / D=探索性物理探针 /
E=非授权诊断，定义见 `CONTROLLER_AUDIT.md` §f），与本审计主线使用的
本地性导向 A–F 层级（见 `SOURCE_MAP.csv`）坐标轴不同，勿混读。

## 7. 几何四问（互不蕴含）

G1 模型相对终态 EventF1：SUPPORTED（仅模型相对）；G2 VLM 直接恢复：
DISFAVORED；G3 独立人类事件恢复：PENDING（0 标签）；G4 SCAN/VERIFY 动作
价值：ABSENT。

## 8. 人工 P1 安全结论

HUMAN_P1_PROTOCOL_STATUS = FROZEN / READY / BLINDED；
HUMAN_LABEL_COUNT_METADATA_ONLY = 0 ROWS；
**HUMAN_P1_ANALYSIS_AUTHORIZED = NO**。

## 9. 内生 SCAN preflight 裁定

**REPORTED_REMOTE_UNVERIFIED**；0/36 可用于科学：**NO**；根因审计授权：
**NO**。恢复清单见 `REMOTE_ARTIFACT_RECOVERY_MANIFEST.md`。

## 10. 统计独立性

所有关键结果均已按"实验行 / 匹配对 / 视频-查询簇 / 独立源视频"分层（见
`INDEPENDENCE_AUDIT.csv`）。要点：198 对 ≠ 198 独立样本（簇内相关）；54 对
≠ 54 独立样本（3 视频 × 3 选择器 × 6 预算）；108 状态非总体加权（流行率
不可辨识）；广州结果单源单事件。

## 11. 新颖性

独立文献检索（52 条查询，网络可用）确认：proxy+oracle、自适应时间采样、
资源感知调度、覆盖/多样性获取、事件重建诸维度 novelty delta 大多为
EMPTY/COVERED；**唯一残余槽位是 durable EventRelation 契约 + 因果暴露感知
（D7/D8，MEDIUM 威胁）**，且其形态必须收窄为"单物理时钟的 physical-anytime
事件查询契约 + 确定性 temporal-coverage 设计证据"，当前证据仅单源单事件。
EFS/MEC 无法解析；DIVA 引文疑似误标。

## 12. 根项目问题（独立回答）

**E（组合）**：当前最恰当的理解是——主层为"预算约束下的昂贵语义验证/证据
选择 + 事件关系物化"（B+C 的结合，受限于模型相对引用）；次层为原理论的
"部分可观测感知+验证查询处理"（D，从未被忠实实例化）；自适应控制器分支
（A）已关闭。任何把 GVAQP 描述为"已实证的自适应控制器项目"的表述都
不符合本地证据。

## 13. 研究方向分诊

总分（见 `RESEARCH_DIRECTION_SCORECARD.csv`）：
**方向 4（忠实内生 sensing-verification 建模）69 分最高**——它测试整个
原程序中唯一未检验的承重假设，正反结果都有决定性信息量；当前执行可行性
受 GPU+人工引用约束。方向 1（几何/P1）与方向 3（VERIFY 分配）并列 48；
方向 2/5/6 低。注意：分诊反映科学价值，不等于当前可执行性（本机无 GPU）。

## 14. 结论

- 最强本地正结果：C1 gap 物化器（54/54，+0.1457）——模型相对、循环限定。
- 最强本地负结果：复杂 K3 新颖性证伪 + 学习控制器劣于固定动作。
- 最强"有报告但不可验证"结果：内生 preflight 0/36。
- 最大本地-远端冲突：preflight 声称的 substrate fidelity PASS 与本地
  P4=NOT_STARTED 台账直接矛盾。
- 论文级问题仍存在：**MAYBE**——"在单一物理时钟下，因果暴露的廉价感知与
  昂贵语义验证的联合调度 + 持久事件关系物化，能否在廉价感知真实漏检时
  超过固定确定性覆盖"，但必须先通过 P4 最小忠实探针检验。

详见 `LOCAL_SOURCE_OF_TRUTH.md`、`PROVENANCE_CONFLICTS.md`、
`MISSING_EVIDENCE_REGISTER.csv`、`PROPOSED_CLAIM_LEDGER.csv`、
`PROPOSED_STATE_OF_TRUTH_UPDATE.md` 与 `DECISION.json`。
