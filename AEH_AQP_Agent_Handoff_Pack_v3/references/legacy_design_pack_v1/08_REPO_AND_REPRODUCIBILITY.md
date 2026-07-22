# 08 — Repository and Reproducibility Plan

## 1. 当前仓库状态说明

截至 2026-07-10，公开 `CharmCheen/G-ARC` 页面可见 13 commits，以及 `Hermes_Project_Handoff`、`garc_eval`、`related_work`、`AGENTS.md`、`G-ARC_Research_Report.md`、`GARC_EVAL_BUILD_PLAN.md`、`garc_research_retrospective.md` 等内容。

项目内部审计报告称：

- 主仓库叙事仍主要停留在 V12/V13 和早期 G-ARC；
- `ARC_related_repos` 包含更新的 ARC 源码审计、SEHS/VOI 与 stress-test 设计；
- 服务器端 event-level adapters、BB-EM、MAP 和最新 replay 尚未完整同步。

后两项属于项目方报告，必须通过 T00 的 SHA/manifest 独立固化。

## 2. 推荐目录

```text
repo/
├── AGENTS.md
├── README.md
├── configs/
│   ├── pilot_frozen.yaml
│   ├── cross_video_frozen.yaml
│   └── schemas/
├── docs/
│   ├── project_design/
│   │   └── <本设计包>
│   ├── annotation/
│   ├── deprecated/
│   └── paper/
├── src/
│   ├── adapters/
│   ├── materialization/
│   │   └── bbem_k3.py
│   ├── acquisition/
│   │   ├── map_anchor.py
│   │   └── minimal_sehs.py
│   ├── audit/
│   ├── evaluation/
│   └── common/
├── scripts/
│   ├── stages/
│   ├── audits/
│   └── reproduce/
├── data_manifests/
├── outputs/
│   └── <stage>/<run_id>/
├── tests/
│   ├── unit/
│   ├── invariants/
│   └── leakage/
└── logs/
```

## 3. Run manifest

每次运行保存：

```json
{
  "run_id": "...",
  "git_commit": "...",
  "dirty_worktree": false,
  "config_sha256": "...",
  "input_manifest_sha256": "...",
  "method": "...",
  "selector": "...",
  "materializer": "BBEM_K3",
  "budget": 20,
  "random_seed": 0,
  "oracle_semantics": "binary_unit_replay_v1",
  "reference_version": "...",
  "evaluator_version": "...",
  "started_at": "...",
  "completed_at": "..."
}
```

## 4. Artifact manifest

```text
relative_path
size_bytes
sha256
producer_run_id
schema_version
created_at
immutable
```

Stage FINAL_REPORT 必须引用 manifest，而不是只写文件路径。

## 5. 版本化对象

必须单独版本化：

- Unit CSV；
- proxy version；
- pseudo-oracle labels；
- human GT；
- event schema；
- materializer；
- acquisition policy；
- metric protocol；
- baseline adapter；
- frozen config。

## 6. 测试

### Unit tests

- gap calculation；
- barrier crossing；
- duration cap；
- one-to-one matching；
- budget prefix；
- HT estimator on known toy population。

### Invariant tests

- hidden label never read before query；
- K3 never crosses negative barrier；
- no segment exceeds cap；
- barrier-positive does not auto-merge；
- audit inclusion probability positive and recorded。

### Regression tests

- Stage 0 B=100 repair；
- K3 compression metrics；
- Stage 1A known pilot summary；
- native ARC diagnostic。

## 7. Branch 与 release

推荐：

```text
main                 稳定、可复现
research/dev         新实验
release/pilot-v1     已冻结 pilot
release/crossvideo-v1
```

每个论文结果绑定 annotated tag：

```text
pilot-bbem-map-v1
crossvideo-minsehs-v1
paper-submission-v1
```

## 8. 旧文档处理

不删除历史，但对以下类型加 header：

```markdown
> DEPRECATED: This document contains superseded claims.
> Current source of truth: docs/project_design/README.md
```

特别标记：旧 SUPG gap、旧 ARC confidence 解释、旧完整 C6/SEHS claim。

## 9. 复现命令要求

每个 stage 提供一个入口：

```bash
python scripts/reproduce/<stage>.py \
  --config configs/<frozen>.yaml \
  --manifest data_manifests/<version>.csv \
  --out outputs/<stage>/<run_id>
```

禁止把关键参数散落在脚本常量中。

## 10. 发布清单

- clean checkout 可运行；
- 输入数据或合法下载说明；
- exact environment lock；
- CPU replay path；
- 可选 GPU path；
- artifact hashes；
- metric evaluator tests；
- baseline license / attribution；
- human annotation protocol；
- known limitations；
- claim-to-artifact mapping。
