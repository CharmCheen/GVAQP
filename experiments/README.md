# 实验归档规范

## 组织原则

一个“研究主题”对应 `experiments/<topic>/`；一个可独立复现、可独立做出判断的实验运行对应 `experiments/<topic>/<experiment_id>/`。重复运行、smoke、ablation 和参数扫描应作为该实验的子目录或在 README 中关联，而不是散落到仓库根目录。

当前仓库采用“先索引、后迁移”：已有路径保持不变，避免破坏脚本和报告中的相对路径。新增实验必须放在这里；旧目录只有在确认引用已更新、并且没有大文件复制时才迁移。

## 推荐目录

```text
<experiment_id>/
├── README.md                 # 实验摘要和状态（必需）
├── config/                   # 冻结配置、schema、预注册参数
├── data_manifest/            # 输入数据清单、版本、split、来源
├── scripts/                  # 可复现入口；不要把脚本藏在输出目录
├── logs/                     # 运行日志、环境和硬件记录
├── tables/                   # 机器可读结果（CSV/JSON）
├── figures/                  # 图表
├── reports/                  # 审计、结果解释和最终报告
└── raw/                      # 必须保留的原始输入（优先使用链接/清单）
```

`candidates/`、`features/`、`return_sets/`、`converted/`、`review_package/` 等是允许的语义化扩展；它们应在 README 中说明来源和是否可再生成。`__pycache__/`、临时下载目录和大体积原始媒体不应作为研究证据提交。

## README 必填字段

每个独立实验目录必须有 README，至少包括：

- 目的/假设，以及本实验要区分的竞争解释；
- 数据、配置、代码入口和运行命令；
- 结果摘要：观察到的证据、推导出的结论、尚未验证的假设；
- 证据链接：最终报告、关键表格、图和日志；
- 状态：`planned`、`running`、`complete`、`blocked` 或 `superseded`；
- 下一步、拒绝/修订条件和日期。

模板见 [`templates/README_EXPERIMENT.md`](templates/README_EXPERIMENT.md)。索引见 [`EXPERIMENT_INDEX.md`](EXPERIMENT_INDEX.md)。

## 命名规则

目录使用小写 `snake_case`，版本和运行编号使用 `_v1`、`_v2` 或明确的日期；同一假设的后续试验不要另起无关主题。README 中使用相对链接，避免硬编码机器路径。

