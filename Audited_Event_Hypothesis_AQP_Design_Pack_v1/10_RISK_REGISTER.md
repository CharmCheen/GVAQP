# 10 — Red-Team Risk Register

| ID | 风险 | 严重性 | Mitigation | Kill / downgrade criterion |
|---|---|---:|---|---|
| R1 | novelty 仅是 event graph | 极高 | 主贡献放在 query semantics、typed execution、audit | graph 不影响 action/materialization 时移出主方法 |
| R2 | BB-EM 只是 duration cap | 高 | K0–K3、leave-one-out、trigger/path、跨视频 | K2 与 K3/full 在所有视频等价时降级为 bounded merge heuristic |
| R3 | K3/C6 ablation harness 无效 | 极高 | trigger counts、hash、lineage、independent reimplementation | 发现 variant 分支复用则所有相关结果 invalid |
| R4 | single-pilot overfit | 极高 | 参数冻结、held-out videos、external source | cross-video effect 不稳定则只保留 pilot finding |
| R5 | pseudo-oracle / VLM reference circularity | 极高 | human adjudication、label mismatch audit | disagreement 使排名反转则停止方法 claim |
| R6 | candidate space 漏事件 | 极高 | candidate ceiling、candidate-outside audit | ceiling <0.80 时停止 planner，修 candidate generation |
| R7 | VOI prior 自我确认 | 高 | independent calibration、prior-wrong stress、uniform audit | wrong-prior 下比 uniform 更差且不可恢复则不用 VOI |
| R8 | residual estimator 方差过大 | 高 | canonical anchor、strata、simulation、coverage tests | CI 无用或 coverage 失败则去掉 certificate claim |
| R9 | canonical anchor 不唯一 | 高 | event-specific annotation rules、ambiguity flag | 大量事件无法一致 anchor，certificate 路线暂停 |
| R10 | B≤10 raw F1 输 ARC | 中高 | 如实报告，Pareto 与 review cost并列 | 不得宣称全面 dominance；若所有 budgets 均输则 planner no-go |
| R11 | boundedness metric gaming | 高 | raw F1、IoU、review seconds 同时报告 | 只靠切短提升 precision 且 recall 崩溃时 BB-EM fail |
| R12 | Stage 1B barrier 增加 overcoverage | 高 | per-segment forensics、asymmetric semantics | 无法修复则移除 proactive barrier probing |
| R13 | baseline adapter 不忠实 | 极高 | source audit、set hash、native/strengthened 分离 | pipeline bug 则受影响结论全部重跑 |
| R14 | SUPG variants 意外同路径 | 中高 | selected/query/anchor/segment set audit | 若代码复用 bug，修复前不发布 baseline ranking |
| R15 | cost accounting 不公平 | 高 | oracle tokens/time/human effort 与 returned seconds | 换统一成本后优势消失则不称 query acceleration |
| R16 | 10s resolution 太粗 | 中高 | boundary claim 限制；未来 2s/5s subset | strict IoU 长期不可用则不主打 localization |
| R17 | actor tracking 噪声破坏 graph | 高 | actor-centric subset、track uncertainty、relation probe | graph 增量不超过 temporal hypotheses 时移除 actor graph |
| R18 | event types 异质 | 高 | per-type models/metrics、macro averaging | 只在单一类型有效则缩小 scope |
| R19 | adaptive-submodularity 假设不成立 | 中 | counterexample search；restricted objective | 失败则转 empirical VOI，不声称 approximation bound |
| R20 | repo 无法复现真实结果 | 极高 | T00 sync、manifest、release tag | 无法从 clean checkout 重跑则论文实验 blocked |

## 重点 kill decision tree

```text
Candidate ceiling low?
  yes → fix candidates; stop planner.
  no  → Oracle planner ceiling low?
          yes → expand action space; stop optimizer tuning.
          no  → Minimal SEHS beats shared-materializer baselines?
                  no → keep BB-EM-only/system paper.
                  yes → Cross-video stable?
                          no → narrow claim.
                          yes → Audit certificate calibrated?
                                  no → empirical AQP system.
                                  yes → stronger audited AQP paper.
```
