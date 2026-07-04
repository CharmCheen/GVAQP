# AGENTS.md — SQ-CRAQ 项目约定

> 这份文件是给 Codex（以及其他遵循 AGENTS.md 规范的 agent）的持久性上下文，
> 每次任务开始前会被自动读取。只写"不写就大概率会猜错"的内容，
> 通用的工程建议不放这里。任务级别的具体要做什么，见每次单独下发的 prompt。

## 项目是什么

长视频语义事件查询（AQP）研究项目，代号 SQ-CRAQ。核心目标：用低成本信号
在长视频里生成候选事件区间，用有限的 oracle（VLM/人工）预算审计和修复候选，
最终返回高 recall、高 precision 的事件片段。当前阶段目标是**跑出好的经验
recall/precision，不追求正式统计证书（formal guarantee）**。

## 非负例（Never）

```text
- 不要把 CILS 设为默认 selector。默认 selector 固定是
  score_topk + temporal NMS + duration cap。CILS 只能以 ablation/独立对照
  的形式存在。除非某次任务明确要求"重新评估 CILS 是否该转正"，
  否则不要改动这个默认值，也不要因为它"看起来更精细"就顺手换上去。

- 不要主动补全或"修复" certificate 相关的统计量
  （r_upper 作为有效上界、γ_lower、置信区间、sample-splitting 证明等）。
  如果代码里已经有这些字段的占位符或历史实现，除非任务明确要求，
  否则不要动它们，也不要认为它们"没写完"而去补充统计推导。

- 任何标记为 probe_set_v1（或未来标记为"独立探针集/frozen eval set"）
  的数据，只能用于只读评估，不能用于调参、选阈值、驱动任何 repair 或
  selector 的决策。如果某次任务的实现方式导致这批数据被用来调参了，
  停下来，在交付说明里明确指出这个问题，不要悄悄绕过。

- outside-envelope audit 产生的样本，如果被用来驱动 repair 决策，
  就不能同时被当作证明"repair 有效"的评估依据。决策用的样本和
  评估用的样本必须是不同批次，这条不是可选优化项，是硬约束。
```

## 报告 recall/precision 数字时的约定

```text
任何 recall/precision/AUC 类数字，必须标注数据来源，例如：
  "6_event_reference" / "expanded_reference" / "probe_set_v1"
不要写成裸的 "recall = 0.8"，必须带来源标签。
如果不同数据源上结论不一致，如实并列展示，不要挑好看的那个报告。
```

## 目录与命名约定

```text
实验产出统一放在形如：
  outputs/<experiment_name>_v<N>/
  内含 FINAL_REPORT.md（人类可读总结）+ 原始数据/中间产物

新实验如果是已有实验的迭代版本，版本号递增（_v1 → _v2），
不要覆盖旧版本目录，旧版本保留作为对照。

<!-- TODO（人工填写，Codex 不要猜）：
  - 实际的 lint / test / build 命令是什么
  - cheap feature 计算 / candidate lattice 生成的代码具体在哪个模块
  - VLM 调用是走 API 还是本地部署，配置在哪
  这几项我目前不确定具体路径和命令，写错了比不写更糟，
  请在首次使用前手动补上，避免 Codex 凭空猜测命令名或路径。
-->
```

## 不确定时怎么办

```text
遇到本文件或任务 prompt 都没覆盖的情况：
  - 需要一个具体阈值/采样参数：选合理默认值，在交付报告里写清楚假设和理由。
  - 找不到某个提到的已有模块/路径：先搜索确认是否改名/移动，
    确认不存在再新建，并在交付说明里注明。
  - 发现某个既有结论（比如"CILS value-add = neutral"）可能因为新证据
    需要重新评估：如实报告新证据，不要自己下结论说"应该翻案"，
    这类路线级判断留给人做决定。
```