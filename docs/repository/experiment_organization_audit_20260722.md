# 实验组织审计与维护状态（2026-07-22）

## 目标

让研究者能从一个入口找到每个实验的摘要、复现实验所需的配置/脚本、结果证据和下一步决策，同时避免为了“看起来整齐”移动大体积产物而破坏已有路径。

## 直接观察

- 仓库已有 `experiments/`，目前按 14 个主题分组；扫描到 54 个二级运行根目录。
- 实验产物最常见的目录是 `config`、`data_manifest`、`scripts`、`logs`、`tables`、`figures`、`reports`，但数据审计、候选、return set、review package 等扩展目录也存在。
- `experiments/` 下已有大量报告和 `summary.md`，但缺少统一的实验级 README 入口。
- 根目录另有 DARE、BSEC、AQP sprint、AEH design/handoff 等包；它们混合了协议、研究状态、交接材料和实验输出，不能简单按单次运行归档。
- 根目录和实验目录包含视频、帧、模型输出、缓存等高风险大文件；当前没有进行整体移动。

## 当前结论

1. 实验应集中存放在 `experiments/<topic>/<experiment_id>/`，主题分组是合适的，现有分组不需要重建。
2. 每个独立运行目录必须有 README；README 是摘要和导航层，报告/表格/日志是证据层。
3. `config`、`data_manifest`、`scripts`、`logs`、`tables`、`figures`、`reports` 作为默认规范，按实验需要扩展，不强行创建空目录。
4. 当前最小且可逆的整理动作是补入口、补模板、补索引；大文件迁移推迟到路径引用审计之后。

## 未决问题与替代解释

- 54 个二级目录并不一定都是独立实验；`frame_level` 的参数扫描和 `clip_aqp_phase0_v1` 的 diagnostics/power/repair 更可能是父实验的子试验。README 目前保留原结构，并要求上级卡片说明关系。
- 某些目录可能是数据准备或资产审计而非科学实验；索引不把目录名自动解释为“已完成结果”。状态默认为 `unclassified`，需要根据直接报告更新。
- 根目录历史包是否迁入 `experiments/` 尚未决定。触发迁移的条件是：确认没有外部依赖、完成相对路径检查、迁移成本不涉及复制大文件。

## 持久化入口

- 仓库入口：[`../../README.md`](../../README.md)
- 规范：[`../../experiments/README.md`](../../experiments/README.md)
- 总索引：[`../../experiments/EXPERIMENT_INDEX.md`](../../experiments/EXPERIMENT_INDEX.md)
- 单实验模板：[`../../experiments/templates/README_EXPERIMENT.md`](../../experiments/templates/README_EXPERIMENT.md)

## 下一步最高信息量动作

优先从当前仍在使用的实验开始，把 `unclassified` 更新为真实状态，并从最终报告提炼 3—8 行摘要；之后再对根目录历史包做引用和路径审计。若发现脚本依赖根目录路径或外部程序硬编码路径，应维持现路径并只在索引中归档。

