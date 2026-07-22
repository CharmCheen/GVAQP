# 07 — Agent Task Queue：可直接执行的任务规格

## Task T00 — Repository Sync and Artifact Manifest

### Goal

把服务器最新 adapter、BB-EM、MAP、metric protocol 和 outputs 同步到可复现分支，建立项目真实状态。

### Hard constraints

- 不改算法；
- 不覆盖旧 outputs；
- 每个 artifact 记录 SHA256；
- 旧叙事文档加 deprecated banner，不直接删除历史。

### Outputs

```text
REPO_STATE_2026-07-10.md
artifact_manifest.csv
code_output_dependency_graph.md
sync_commit_sha.txt
```

### Pass

从固定 inputs 可重跑 Stage 0.6、0.7、1A 并复现关键表。

---

## Task T01 — Pre-Cross-Video Robustness Audit

### Goal

完成 trigger/path、Stage 1B overcoverage、SUPG variants 和 frozen config 审计。

### Required analyses

1. C6 optional mechanisms trigger/applied/output-change counts；
2. K3/K4/C6 segment hash；
3. MAP-anchor-only vs anchor-barrier per-segment lineage；
4. B=100 overcoverage contribution decomposition；
5. SUPG selected/query/anchor/segment set symmetric differences；
6. 从代码提取所有参数与 provenance。

### Decision

- `PREFLIGHT_PASS`；
- `PREFLIGHT_PASS_BBEM_MAP_ONLY`；
- `PREFLIGHT_BLOCKED`。

---

## Task T02 — Human GT and Canonical Anchor Protocol

### Goal

将 VLM-defined references 升级为 human-adjudicated event GT，并验证 canonical anchor 是否可用。

### Work

- 编写每类 event 的 annotation manual；
- 双人独立标注；
- 第三人 adjudication；
- 统计 existence agreement、type agreement、anchor time error、boundary IoU；
- 审计 32 pseudo-positive units 的一致性；
- 搜索遗漏事件。

### Outputs

```text
EVENT_SCHEMA.md
ANNOTATION_GUIDE.md
audited_events.csv
annotator_disagreements.csv
GT_AUDIT_REPORT.md
```

### Kill

若 anchor 无法稳定唯一化，certificate 方向暂停；可继续 empirical event discovery。

---

## Task T03 — Three Ceiling Experiments

### Goal

判断瓶颈在 candidate、planner 还是 materializer。

### Variants

1. Core candidate coverage ceiling；
2. Materializable candidate ceiling；
3. Oracle-informed planner ceiling by budget；
4. Reference-aware materializer upper bound。

### Required outputs

```text
candidate_ceiling_by_video.csv
planner_ceiling_by_budget.csv
materializer_ceiling.csv
ceiling_gap_decomposition.md
```

### Gate

- candidate ≥0.80；
- planner ceiling target budget ≥0.70–0.75；
- 否则不要实现 Full SEHS。

---

## Task T04 — Minimal SEHS-Node Replay

### Goal

验证 event hypothesis 作为 query-time state 是否在共享 BB-EM 下产生 acquisition 增量。

### State

- temporal hypothesis；
- core candidates；
- positive anchors；
- negative barriers；
- boundary uncertainty；
- status。

### Actions

- CONFIRM_CORE；
- AUDIT_REGION；
- EXPAND_BOUNDARY；
- STOP。

### Forbidden

- actor graph；
- learned GNN/RL；
- type/relation oracle；
- reference-aware scoring。

### Main comparison

```text
Minimal SEHS + BB-EM
vs ARC-adapted + BB-EM
vs ABae + BB-EM
vs MAP-anchor-only + BB-EM
```

### Pass

预注册 target budget recall +0.10 absolute，至少两个 held-out videos 同向。

---

## Task T05 — Independent Audit Ledger Prototype

### Goal

估计 discovery 后 residual canonical-anchor mass。

### Design

- 固定 block partition；
- stratified/Bernoulli inclusion probabilities；
- audit 与 discovery sample split；
- block 内完整 anchor count；
- HT point estimate + conservative interval。

### Validation

1. Synthetic populations with known clusters；
2. Fully annotated videos where residual count known；
3. Bias/variance/coverage；
4. cost vs interval width；
5. false-stop rate。

### Decision

`CERTIFICATE_GO` / `EMPIRICAL_AUDIT_ONLY` / `AUDIT_NO_GO`。

---

## Task T06 — Cross-Video Frozen Validation

### Prerequisites

T00–T03 pass；frozen config complete。

### Rules

- 参数零调整；
- video-level paired results；
- native + strengthened baselines；
- raw overlap_any 与 boundedness 并列；
- external dataset 单独分析。

### Outputs

```text
per_video_metrics.csv
aggregate_bootstrap_ci.csv
cost_quality_curves.csv
failure_cases.md
CROSS_VIDEO_FINAL_REPORT.md
```

---

## Task T07 — Adaptive Submodularity Feasibility

### Goal

判断 discovery-only objective 是否满足或近似满足 adaptive submodularity。

### Required analysis

- 定义 latent event/hypothesis mapping；
- duplicate saturation utility；
- independence assumptions；
- counterexample search；
- boundary/merge penalties为何破坏单调性；
- greedy approximation 适用范围。

### Output

```text
THEORY_ASSUMPTIONS.md
PROPOSITION_OR_COUNTEREXAMPLE.md
THEORY_DECISION.md
```

### Decision

- `THEORY_CORE_COVERAGE_GO`；
- `EMPIRICAL_VOI_ONLY`。

---

## Task T08 — Full Actor-Centric SEHS (conditional)

仅在 T04、T06 通过后执行。

### Additions

- actor track nodes；
- identity/type/relation probes；
- counterfactual VOI；
- calibrated outcome model；
- asymmetric barrier semantics。

### Required ablation

每个 node/edge/action 必须报告 trigger count、cost-normalized gain、leave-one-out 和跨视频结果。
