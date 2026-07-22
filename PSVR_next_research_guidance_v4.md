# PSVR 后续研究探索指导文档 v4.0

**副标题：规则式两视频搜索 NO_GO 后的研究转向版**  
**状态日期：2026-07-18**

> 本版本更新研究状态、证据边界与后续探索路线；不重写 frozen oracle-defined semantics、K3、reference materializer、deadline safety contract 或 held-out 纪律。

## 执行摘要

当前最准确的项目判断：PSVR 的物理执行、deadline safety、oracle-defined benchmark、durable snapshot 和低成本 YOLOv8 proxy 已经成立；但 Coverage-Debt、结构优先级、候选暴露优先级、固定 Scan×VERIFY 因子和阶段控制器均未形成跨两个视频的稳定质量收益。当前 NO_GO 只否定“冻结两视频 workload 下的规则式控制搜索”，不等于否定 PSVR 研究问题。

下一阶段的最高价值假设：

```text
H-VALUE1 = Cross-Video Candidate-Value Identifiability
```

只使用运行时真实可见的 candidate、track、frontier、成本和剩余时限特征，检验能否跨视频预测一次 physical VERIFY 会产生 oracle-positive 且尚未确认的新事件。

- PASS：进入 H-CVV1 calibrated candidate value physical pilot。
- FAIL_DOMAIN_SHIFT：禁止 learned scheduler，转入 H-QPROXY1 query-conditioned temporal refiner。
- refiner 通过：整合 MF-PSVR；失败：语义价值路线 NO_GO。
- 只有冻结方法候选后，第三视频才用于 3×2 generalization。

## 1. 当前状态

```text
PSVR_RULE_BASED_TWO_VIDEO_SEARCH = NO_GO
PSVR_PROJECT_STATUS = ACTIVE_PIVOT
SELECTED_PROXY_FAMILY = YOLOV8
CURRENT_SIMPLE_BASELINE = FIFO
CURRENT_VALIDATED_CORE_METHOD = NONE
```

规则式终局：H-RECOVER1 发现异质瓶颈；H-BOTTLE2 的 96-cell factorial 和 H-STAGE1 的 48-cell matrix 都未形成跨视频 signal。最终 Macro AnytimeAUC=0.0475467284，Macro F1=0.0733333333，unique events=3，Macro TTFC=116.7433s。

任务瓶颈：

| Task | 主要瓶颈 |
|---|---|
| V0_Q1 | FRONTIER_OR_VERIFY_ORDER_LIMITED |
| V0_Q2 | SCAN_EXPOSURE_LIMITED |
| V1_Q1 | FRONTIER_RETENTION_OR_ADMISSION_LIMITED |
| V1_Q2 | FRONTIER_OR_VERIFY_ORDER_LIMITED；VERIFY_BUDGET_LIMITED 为备选 |

## 2. 已排除路线

- Coverage-Debt / global gap：质量机制未支持。
- Structural-only：单任务 tie-sensitive，不是稳健机制。
- age + novelty + suppression 与 10s NMS：H-EXPOSE2 REJECT。
- fixed Scan×VERIFY factorial：无跨视频主效应。
- observable stage rules：H-STAGE1 REJECT。
- YOLOP：当前 downstream 成本—质量不胜出。

禁止重启这些路线的参数、窗口和 tie-break 搜索。

## 3. 文献定位与空白

代表性路线包括 NoScope、Focus、BlazeIt、TASTI、SUPG、ABae、MIRIS、ExSample、Seiden、Zeus、ARC、Online Aggregation 和 Active Search。

可防守的组合空白：

1. query-time incomplete proxy，候选由 SCAN 内生生成；
2. decode/proxy/refiner/oracle/K3/commit 共享 hard wall-clock；
3. 输出是 set-valued temporal EventRelation；
4. 任意停止点必须 evidence-honest、durably committed；
5. 在 cheap perception、轻量 query semantics 与 frozen oracle 之间分配 fidelity。

ARC 是最接近的工作；正式投稿前必须全文级审计，不能做“首次 progressive sampling / proxy+oracle”主张。

## 4. 更新后的方法视角

```text
SCAN(region, level, proxy_config)
REFINE_CANDIDATE(candidate, refiner_config)
VERIFY(candidate, oracle_config)
REFINE_BOUNDARY(event_core, side)
COMMIT(snapshot)
```

Evidence ladder：

```text
UNSEEN
→ PROXY_OBSERVED
→ PERSISTENT_TRACK_CANDIDATE
→ SEMANTIC_REFINED_CANDIDATE
→ ORACLE_CONFIRMED_CORE / REJECTED
→ MATERIALIZED EVENT
→ DURABLY COMMITTED
```

## 5. H-VALUE1

### 数据

复用历史 physical traces，每条样本是 `(candidate, online state, VERIFY opportunity)`。同一 candidate 的 repeats 必须聚合；reference 只用于事后生成 oracle-positive / new-event labels。

### 在线特征

- track：类别、持续性、运动、box growth、approx TTC、front-region occupancy、raw proxy score；
- frontier：age、size、score margin/entropy、same-cell count、到 pending/confirmed/rejected 区域距离、negative streak；
- execution：coverage、gap、scan/VERIFY count、remaining time、admissible actions、cost bounds。

禁止 reference identity、future proxy、eventual TP 和 evaluator bottleneck label。

### 模型和划分

- FIFO、raw proxy、deterministic random；
- logistic regression；
- LightGBM；
- 主 Gate：leave-one-video-out；辅助 leave-one-query/task-out；random row split 只作 smoke。

### PASS

- 两个 video folds 均优于 raw proxy；
- macro VERIFY-order regret 至少下降 20%；
- 固定 call budget 下跨任务至少多 1 unique event；
- 不只由 V0_Q1 驱动；
- calibration 不明显更差。

## 6. PASS 分支：H-CVV1

固定 scan 与 VERIFY opportunities，只比较 FIFO、raw score、calibrated candidate value：

```text
3 methods × 4 tasks × 2 deadlines × 3 repeats = 72 runs
```

要求两视频各有 task 改善，并达到 Macro AUC +10%、TTFC −20%、F1 +0.05 或合计多恢复 2 events 之一；regret 和 negative calls before TP 同时下降。

## 7. FAIL 分支：H-QPROXY1

使用独立 DrivingDojo 候选池；free-text 仅用于抽样，标签必须由相同 frozen oracle query 自动生成；按 source vehicle/session grouped split。训练 LightGBM，必要时小型 causal TCN/GRU；V0/V1 仅作零样本和 physical evaluation，不得训练。

目标是中间语义 fidelity：`P(oracle-positive candidate)`，不是直接产生 strict event。

## 8. MF-PSVR

```text
YOLOv8 SCAN
→ query-conditioned REFINE_CANDIDATE
→ frozen oracle VERIFY
→ K3 MATERIALIZE
→ durable COMMIT
```

组件分别通过 Gate 后才允许整合。冻结候选后，第三视频用于 3×2 generalization；通过后才进入 >=12 视频 held-out。

## 9. 立即执行

```bash
python scripts/preregister_psvr_hvalue1.py
python scripts/build_psvr_candidate_value_dataset.py
python scripts/evaluate_psvr_candidate_value_identifiability.py
```

若脚本不存在，只实现完成 H-VALUE1 所需的最小版本。

## 10. 建议状态

```json
{
  "project_status": "ACTIVE_PIVOT",
  "rule_based_two_video_search": "NO_GO",
  "selected_proxy_family": "YOLOV8",
  "current_simple_baseline": "FIFO",
  "current_validated_core_method": null,
  "active_research_program": "CANDIDATE_VALUE_IDENTIFIABILITY",
  "active_hypothesis": "H-VALUE1",
  "heldout_opened": false,
  "next_exact_command": "python scripts/preregister_psvr_hvalue1.py"
}
```

## 参考文献

1. NoScope, PVLDB 2017, DOI 10.14778/3137628.3137664.
2. Focus, OSDI 2018.
3. BlazeIt, PVLDB 2019, DOI 10.14778/3372716.3372725.
4. TASTI, arXiv:2009.04540.
5. Approximate Selection with Guarantees using Proxies, PVLDB 2020.
6. ABae, PVLDB 2021, DOI 10.14778/3476249.3476285.
7. MIRIS, SIGMOD 2020, DOI 10.1145/3318464.3389692.
8. ExSample, arXiv:2005.09141 / ICDE 2022.
9. Seiden, PVLDB 2023, DOI 10.14778/3598581.3598599.
10. Zeus, SIGMOD 2022, DOI 10.1145/3514221.3526181.
11. ARC, SIGIR 2025, DOI 10.1145/3726302.3729896.
12. Online Aggregation, SIGMOD 1997, DOI 10.1145/253260.253291.
13. Bayesian Optimal Active Search and Surveying, ICML 2012.
