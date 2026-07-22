# 实验总索引

本页是仓库整理时的稳定入口。每个可独立判断的运行目录都有一张 README 卡片；README 中的报告和表格才是结论的证据来源。状态没有在产物中明确记录时，不推断为完成。

## 主题分组

| 主题 | 内容 | 入口 |
|---|---|---|
| `frame_level` | 帧级 oracle allocation、SUPG/ABAE、时序和数据集压力测试 | [`frame_level/`](frame_level/) |
| `clip_aqp` | clip AQP 数据审计、候选生成、Nexar/视频可用性 | [`clip_aqp/`](clip_aqp/) |
| `micro_casq` | Micro-CASQ oracle 与人工复核 | [`micro_casq/`](micro_casq/) |
| `v12_1`, `v13` | 版本化完成验证、候选构造和 oracle replay | [`v12_1/`](v12_1/), [`v13/`](v13/) |
| `candidate_coverage`, `event_budget_v2`, `diversity_prefilter` | 候选覆盖、事件预算和多样性筛选 | [`candidate_coverage/`](candidate_coverage/), [`event_budget_v2/`](event_budget_v2/), [`diversity_prefilter/`](diversity_prefilter/) |
| `deadline_aqp`, `kinematic_proxy`, `roadclip_budget_v2`, `strive_d` | 预算、运动学代理、RoadCLIP 和 DrivingDojo 资产审计 | 对应主题目录 |
| `focused_validation`, `vlm_raw_responses` | 聚焦验证及原始 VLM 响应 | 对应主题目录 |

## 独立运行入口

以下目录是当前扫描到的主要运行根；更深层的 `k_stress/`、`budget_search/`、`supg_results/` 等是运行内部的子试验或结果分支，须通过上级 README 解释。

| 主题 | 运行目录 |
|---|---|
| candidate_coverage | [`candidate_coverage_gate_v1`](candidate_coverage/candidate_coverage_gate_v1/) |
| clip_aqp | [`clip_aqp_phase0_v1`](clip_aqp/clip_aqp_phase0_v1/)、[`clip_aqp_phase1_candidate_v1`](clip_aqp/clip_aqp_phase1_candidate_v1/)、[`clip_aqp_phase1_data_v1`](clip_aqp/clip_aqp_phase1_data_v1/)、`clip_aqp_phase1_nexar_*`、`clip_aqp_phase1_video_access_*`、`clip_aqp_data_asset_audit_v1` |
| frame_level | `abae_*`、`supg_*`、`bdd100k_*`、`kitti_*`、`uadetrac_temporal`、`adaptive_oracle_allocation`、`temporal_oracle_allocation`、`temporal_stress_benchmark`、`collapse_boundary`、`dataset_acquisition_audit`、`real_frames` |
| 其他 | `deadline_aqp/deadline_aqp`、`diversity_prefilter_replay_v1`、`event_budget_gate_v2`、`focused_validation_outputs`、`kinematic_proxy`、`micro_casq_*`、`roadclip_budget_v2`、`strive_d_*`、`v12_1_completion_v1`、`v13_*` |

## 仓库根目录的历史包

这些目录包含研究设计、交接材料或完整 gate 包，不等同于单次实验运行；保留原路径以维护已有引用。

| 包 | 角色 |
|---|---|
| [`DARE_AQP_Experiment_v1/`](../DARE_AQP_Experiment_v1/) | 独立 gate 实验包，建议后续迁入 `experiments/dare_aqp/` |
| [`BSEC_AQP_Development_Gate_v1/`](../BSEC_AQP_Development_Gate_v1/) | development/confirmation gate 包，建议后续迁入 `experiments/bsec_aqp/` |
| [`AQP_Algorithm_Invention_Sprint_v1/`](../AQP_Algorithm_Invention_Sprint_v1/) | 算法发明 sprint 与研究状态包 |
| [`Audited_Event_Hypothesis_AQP_Design_Pack_v1/`](../Audited_Event_Hypothesis_AQP_Design_Pack_v1/) | 设计包；含大量 agent run，不应直接当作结果目录 |
| [`AEH_AQP_Agent_Handoff_Pack_v3/`](../AEH_AQP_Agent_Handoff_Pack_v3/) | 交接/治理包，不是实验结果 |

