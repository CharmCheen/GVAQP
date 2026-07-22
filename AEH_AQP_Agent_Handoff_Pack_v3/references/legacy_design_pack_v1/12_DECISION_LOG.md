# 12 — Decision Log

## Status vocabulary

`ACCEPTED` / `PROVISIONAL` / `DEPRECATED` / `BLOCKED` / `REJECTED`

---

## D001 — Query object is an event set

- **Date**：2026-07-10
- **Status**：ACCEPTED
- **Decision**：最终输出对象是 distinct EventRelation，不是 positive clips。
- **Reason**：多 positive units 可对应同一事件；超长 segment 可覆盖多个事件但 one-to-one matching 失败。

## D002 — BB-EM/K3 is the frozen pilot materializer

- **Status**：PROVISIONAL pending trigger/path audit
- **Mechanisms**：gap limit + duration prior + queried-negative hard barrier。
- **Pilot evidence**：K3 与 C6 的 AUC、B=20/B=100 F1 一致，max duration 更短。
- **Constraint**：不得将 proxy valley、NMS、expansion 写入主方法。

## D003 — Full C6 multi-rule claim removed

- **Status**：ACCEPTED
- **Reason**：leave-one-out 中 proxy valley、duplicate suppression、conservative expansion 的 mean AUC drop 为 0。

## D004 — MAP-anchor-only has pilot acquisition evidence

- **Status**：PROVISIONAL
- **Evidence**：共享 K3 时 B=5/10/20 超过 best strengthened baseline；AUC pilot 排名第一。
- **Limit**：native ARC 在 B≤10 raw overlap_any F1 更高。

## D005 — Native ARC low-budget loss must be stated separately

- **Status**：ACCEPTED
- **Decision**：不得用 boundedness 冲淡主指标劣势。论文同时写：raw F1 劣势；ARC 的 duration/overcoverage cost。

## D006 — MAP-anchor-barrier is not yet mainline

- **Status**：BLOCKED
- **Reason**：B=100 overcoverage 反弹，需 lineage forensics 和 asymmetric semantics。

## D007 — Full SEHS not currently claimable

- **Status**：ACCEPTED
- **Reason**：actor graph、typed VOI、candidate-outside audit、stopping 尚未完整实现/验证。

## D008 — Target method is Audited Event-Hypothesis AQP

- **Status**：TARGET_DESIGN
- **Components**：event semantics、hypothesis planner、independent audit ledger、residual estimate。

## D009 — No statistical guarantee yet

- **Status**：ACCEPTED
- **Reason**：当前 certificate underpowered / NO-GO；design invariant 不等于 statistical guarantee。

## D010 — Candidate/planner/materializer ceilings precede full graph

- **Status**：ACCEPTED
- **Reason**：先定位瓶颈，避免在候选 ceiling 低时浪费 planner 研发。

## D011 — Cross-video parameters are frozen after pilot

- **Status**：ACCEPTED
- **Constraint**：test 后改参则 test split 失效。

## D012 — Independent audit is required for completeness claim

- **Status**：TARGET_DESIGN
- **Decision**：discovery ledger 与 audit ledger 分离；canonical anchor 作为唯一计数对象。

## D013 — Deprecated research gap

- **Status**：DEPRECATED
- **Text**：“temporal correlation directly breaks SUPG”。
- **Replacement**：record/clip selection semantics 不覆盖 structured event materialization 与 residual completeness。

## D014 — Deprecated ARC confidence interpretation

- **Status**：DEPRECATED
- **Text**：“ARC confidence is ordinary mean precision”。
- **Replacement**：按原论文/源码描述 relevant-clip confidence；本课题差异是 event-set completeness、actor identity 和 audit。

## D015 — Public-repo status must be manifest-based

- **Status**：ACCEPTED
- **Decision**：不再用模糊“服务器最新”作为论文复现依据；每个 claim 绑定 commit/config/artifact hash。
