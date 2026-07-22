# 05 — Roadmap、GO/NO-GO 与 Kill Criteria

## 1. 总原则

下一步不是直接扩完整 graph。路线必须按“正确性审计 → candidate ceiling → minimal query state → independent audit → full graph”推进。每个阶段失败都有明确降级路径。

## 2. Phase P0：证据与仓库冻结

### 任务

- 同步服务器最新 adapter、BB-EM、MAP、evaluation 和 outputs；
- 生成 commit SHA 与 artifact manifest；
- 废弃旧叙事文档或加醒目的 deprecated banner；
- 建立 source-of-truth links。

### Gate

`P0_PASS`：公开/内部可复现分支能从固定 CSV 重跑 Stage 0.6、0.7、1A；关键指标与报告一致。

`P0_BLOCKED`：无法定位真实代码、输入或 outputs；不得继续算法实验。

## 3. Phase P1：Pre-cross-video audit pack

### 任务

1. Materializer trigger/path audit；
2. Stage 1B overcoverage lineage forensics；
3. SUPG variant path audit；
4. frozen config 完整化；
5. claim wording freeze。

### Gate

- `P1_PASS`：K3/C6 equality 合法；Stage 1B 问题已解释或 Stage 1B 被移出主线；SUPG 路径无 bug。
- `P1_PASS_BBEM_MAP_ONLY`：BB-EM 与 MAP-anchor-only 可继续，barrier policy 暂停。
- `P1_BLOCKED`：variant harness 或 baseline adapter 有 bug。

## 4. Phase P2：人工 GT 与 canonical anchor

### 任务

- 定义 event schema；
- 双人标注 + adjudication；
- canonical anchor consistency；
- human audit VLM references 与 pseudo-oracle labels。

### Gate

- event existence agreement ≥预注册门槛；
- canonical anchor 可唯一化的事件比例足够；
- pseudo label 与 GT mismatch 可量化。

### Kill

若 reference/oracle disagreement 高到使 replay 排名不稳定，暂停算法 claim，先重建数据。

## 5. Phase P3：Ceiling experiments

### Candidate gate

```text
core_candidate_ceiling >= 0.80
```

失败：修 hypothesis construction / cheap primitives，不优化 planner。

### Planner-space gate

```text
oracle_informed_recall(target_B) >= 0.70–0.75
```

失败：扩 action/candidate space；当前 planner 不可能达到论文目标。

### Materializer gate

若 fixed-evidence optimal materializer 与 BB-EM 差距很小，冻结 BB-EM；若差距大，研究更强 event partition operator。

## 6. Phase P4：Minimal SEHS-node

### 方法

- temporal hypotheses；
- CONFIRM_CORE / AUDIT_REGION / EXPAND_BOUNDARY；
- rule-based or calibrated greedy；
- shared BB-EM。

### Pass

相对 `ARC-adapted + BB-EM`：

- target budget event recall +0.10 absolute（预注册）；
- precision 达到 floor；
- 至少两个 held-out videos 同方向；
- AUC 与 unique-events/query 改善；
- 无 hidden-label leakage。

### Weak pass

只超过 Ours legacy，不超过 strongest strengthened baseline：MAP/SEHS 作为系统 enhancement，BB-EM 保持主贡献。

### No-go

ceiling 高但 minimal SEHS 无增量：planner idea 暂停；不要扩 graph/GNN。

## 7. Phase P5：Independent audit ledger prototype

### 方法

- canonical-anchor blocks；
- known inclusion probabilities；
- residual anchor counting；
- HT / stratified estimator；
- sample splitting。

### Pass

- simulation 中 bias 可接受；
- nominal interval empirical coverage 达标；
- held-out videos residual estimate 与 full audit 一致；
- stop rule false-stop rate 低于预注册阈值。

### No-go

variance 过大、anchor 不唯一、audit oracle 无法完整计数：去掉 guarantee claim，保留 empirical audit diagnostic。

## 8. Phase P6：Cross-video validation

### 配置

- 参数完全冻结；
- native + strengthened baselines；
- 多视频、人工 GT；
- paired video-level statistics；
- 至少一个 external dataset。

### Pass

- BB-EM 的 materialization收益跨 selector/video 稳定；
- Minimal SEHS/MAP 的 acquisition gain 不是单 pilot 偶然；
- raw overlap_any 与 boundedness tradeoff 均透明报告。

### No-go

仅单视频有效或参数高度敏感：缩小 claim 为 pilot engineering finding / materializer module。

## 9. Phase P7：Full actor-centric graph 与 VOI

只有 P3、P4、P6 通过才启动。

### 增量组件

- actor-track nodes；
- relation probes；
- type probes；
- calibrated counterfactual VOI；
- asymmetric barrier semantics；
- optional adaptive-submodular analysis。

### Gate

每个新增组件必须有：

- trigger count；
- leave-one-out gain；
- cross-video effect；
- cost-normalized value；
- failure cases。

没有独立贡献就删掉。

## 10. 总体 Kill Criteria

以下任一长期成立，应放弃或降级主线：

1. 人工 GT candidate ceiling <0.80 且合理 cheap primitives 无法提升；
2. oracle-informed planner ceiling 也低；
3. shared-materializer 下 planner 无法超过 ARC/ABae；
4. audit estimator coverage 无法校准；
5. 跨视频 effect direction 不稳定；
6. actor graph 只增加工程复杂度，无 query allocation 增量；
7. 主要优势仅来自 permissive metric 或 test-tuned duration cap；
8. 同等 oracle/review cost 下没有加速收益。

## 11. 未来 4 个最优先 deliverables

1. `pre_cross_video_audit/FINAL_REPORT.md`；
2. `human_gt_schema_and_canonical_anchor.md`；
3. `ceiling_experiments/FINAL_REPORT.md`；
4. `minimal_sehs_node/FINAL_REPORT.md`。
