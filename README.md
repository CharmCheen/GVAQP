# G-ARC Research Repository

本仓库包含 G-ARC 的代码、数据、模型和多轮实验产物。实验产物的统一入口是 [`experiments/`](experiments/)，仓库整理规则和迁移边界见 [`experiments/README.md`](experiments/README.md)。

## 从哪里开始

- 实验总索引：[`experiments/EXPERIMENT_INDEX.md`](experiments/EXPERIMENT_INDEX.md)
- 单个实验摘要：进入对应实验目录的 `README.md`
- 实验目录模板：[`experiments/templates/README_EXPERIMENT.md`](experiments/templates/README_EXPERIMENT.md)
- 研究背景和决策文档：[`docs/`](docs/)
- 代码：[`src/`](src/)、[`scripts/`](scripts/)
- 共享数据与数据集：[`data/`](data/)、[`datasets/`](datasets/)

## 当前整理结论

`experiments/` 下的实验按研究主题归组，组内目录名使用 `主题_阶段或目的_版本`。已有产物暂不整体搬迁：视频、帧、模型输出和缓存体量较大，直接移动会增加路径失效和重复数据风险。根目录的 `*_AQP_*` 包保留为历史/交接包，并在实验索引中单独标注，不把它们伪装成新的运行结果。

实验 README 只记录可复核的摘要、证据入口、运行命令、状态和下一步；结论必须以 `reports/`、`tables/` 和日志中的直接产物为依据。

