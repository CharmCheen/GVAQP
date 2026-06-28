# CURRENT PROJECT STATE — Read-Only Audit

**Date:** 2026-06-25
**Author:** Read-only audit pass (no new experiments, no GPU, no model calls).
**Scope:** Inventory and synthesis of all existing outputs, reports, CSVs, logs, scripts in `/qiuyeqing/llama_prl/G-ARC`.
**Method:** Only `ls/find/grep/python-read` used. All conclusions cite an evidence path. Where evidence is missing, the report says "未在现有文件中确认".

This audit heavily reuses and cross-checks two pre-existing audit packages that are the cleanest prior synthesis:
`/qiuyeqing/llama_prl/G-ARC/repo_audit_for_codex_v1/` and
`/qiuyeqing/llama_prl/G-ARC/codex_research_analysis_v1/`.
All numbers below were re-verified directly from the underlying CSVs where feasible.

---

## 一、项目一句话定位

当前项目是一个 **数据库 / AQP 风格的研究**：在长驾驶视频上，给定一个候选生成器（cheap proxy / 嵌入检索 / 中等 VLM）、一个昂贵 oracle（Qwen3-VL-32B，最终对齐到人工）、预算 B、目标召回 γ 与失败概率 δ，返回变长语义事件 clip，并对 **clip-level oracle-relative 召回给出保守统计 certificate**。它不是通用视频检索，也不是端到端驾驶事件检测：核心贡献目标是 **proxy-agnostic 的统计保证层**，而不是设计更好的驾驶事件检测器。

项目当前已落地：单一长视频 `realcartest.mp4`（~66.5 min）上完整的 VLM-oracle-relative 参考标签（399 anchor / 94 正 / 51 拼接事件），OracleBest 上界曲线，以及一个明确的负结论（ handmade 廉价 proxy 在有预算 AQP 下失败）。尚未落地：可发表的正向方法、统计 certificate 在有效 oracle 上的非空证明、跨视频泛化、人工校准。

证据：`repo_audit_for_codex_v1/EVIDENCE_PACK.md`；`codex_research_analysis_v1/CODEX_FINAL_DECISION.md`；`CASQ_CODEX_BRIEF_V12_1.md`。

---

## 二、仓库与产物地图

### 顶层治理文档（当前主线协议）
- `AGENTS.md` — 项目工作守则 / 数据集策略 / 实验约束。仍然重要，工作守则性。
- `CASQ_CODEX_BRIEF_V12_1.md` (1566 行) — V12.1 主协议，当前 governing。仍然重要，权威协议。
- `GARC_EVAL_BUILD_PLAN.md` (1089 行) — 早期 garc_eval 构建计划。历史规划，参考性。
- `G-ARC_Research_Report.md` (592 行) — 早期 G-ARC 研究总报告。历史背景，参考性。
- `docs/clip_aqp/CASQ_CODEX_BRIEF_V11.md` — 上一版协议。已被 V11→V12.1 取代，仅供溯源。

### 现有审计 / 综合产物（最值得先读）
- `repo_audit_for_codex_v1/` — 2026-06-23 的完整 artifact 清单 / lineage / decision log / evidence pack / 风险表 / KEY_RESULTS_TABLE.csv。**当前最干净的交接包**。
- `codex_research_analysis_v1/` — 继上一审计之后的状态评估、AQP 贡献分析、下一步实验排序、最终判定。**当前最有判断力的综合**。

### 主线证据：CASQ / G-ClipAQP 输出（V12 → V13）
位置：`test_vlm/outputs/`。这是当前研究主线证据。
- `clip_aqp_phase0_v1` / `*_phase0_*_summary.md` — Phase 0 伪事件分析，NO_GO → UNDERPOWERED。历史，已被 Phase1/V13 取代。
- `clip_aqp_phase1_*`（data / video_access / video_access_auth / nexar_small / nexar_200 / nexar_200_disentangle / nexar_video_repair / nexar_candidate_v1 / nexar_candidate_v2 / local_candidate_smoke）— Nexar 外部数据流水线，结论：Nexar-200 derived-boundary 不可用作 `O_enter_ego_path_v0` 的 oracle-relative 基准。历史，已被 V13 realcartest 取代。
- `v12_1_completion_v1/` — Micro-CASQ 38 正样本基准 + candidate feasibility + certificate。Decision `NO_CERTIFICATE_YET`（CERTIFICATE UNDERPOWERED）。**当前唯一一次真正跑过 certificate 仿真的地方**，仍重要（说明 certificate 层未站稳）。
- `v13_minimal_validation_v1` — Nexar-200 全视频 candidate smoke；廉价 candidate 全失败。历史。
- `v13_5_realcartest_oracle_relative_v1` — realcartest pilot（100 calls，旧 prompt 66% abstain）。被 V13.6 prompt 修复取代。
- `v13_6_clip_construction_sensitivity_v1` — clip 构造敏感性（416 calls）。Decision `USE_10S_ANCHOR_CENTERED_FOR_COARSE_ORACLE`。**当前仍在用的 clip 协议来源**，重要。
- `v13_7_center10_multi_method_replay_v1` — 17 方法 replay（labeled subset biased）。Decision `CENTER10_FULL_REFERENCE_RECOMMENDED`（推荐正确，性能数字被 V13.9/10 取代）。重要（提供 proxy_features 与 anchor grid）。
- `v13_8_center10_full_oracle_reference_v1` — 全 399 anchor 32B oracle，94 正 / 51 事件 / 0% abstain / 100% complete。**当前最强参考标签**，主线。
- `v13_9_latency_aware_center10_aqp_v1` — 19 方法 × 5 预算静态评测。Decision `LATENCY_AWARE_AQP_FAIL`。**当前核心负结论**，主线。
- `v13_10` — OracleBest 上界 + 自适应搜索 + metric reconcile。Decisions `STATIC_METHODS_FAR_BELOW_UPPER_BOUND`、`ADAPTIVE_NO_BETTER`、`SAME_BASE_HURTS_CONSISTENTLY`。**当前核心负结论**，主线。
- `v13_result_audit_proxy_killtest_20260624_152107` — proxy kill-test 复核。重要复核证据。
- `micro_casq_32b_oracle_v0` / `micro_casq_adjudication_package_v0` — Micro-CASQ v0 基准与 50-clip pilot adjudication package（等人审）。Waiting for human，挂起。

### 早期 candidate pool 实验（Phase 0 之前）
- `kinematic_proxy/` — 运动学异常 proxy 探索，多个 review_html / manual review。BLOCKED（learned anomaly proxy 偏离 DB/AQP 主线）。历史。
- `roadclip_budget_v2/` — roadclip 预算 v2 + vlm_oracle_expanded + scene_windows。喂给 micro_casq 基准。历史 feeder。

### garc_eval 线（SUPG / ABae 复现 + 帧级框架）
位置：`garc_eval/outputs/`。这是 **独立研究线**，与 CASQ clip-level 流水线尚未整合。
- `paper_reproduction_matrix.md` / `garc_research_retrospective.md` / `full_paper_reproduction_status.md` / `abae_reproduction_status.md` / `research_infrastructure_audit.md` — 复现状态综述。
- `supg_paper_synthetic_reproduction/` / `abae_paper_synthetic_reproduction/` — 合成复现（算法级，非完整论文复现）。
- `kitti_*` / `bdd100k_*` / `uadetrac_temporal*` / `driv100_smoke` / `nuscenes_event_aqp_feasibility_audit_v1.md` — 真实帧级基准。结论：KITTI 退化、BDD100K 图像级有效、UA-DETRAC 多退化、nuscenes PARTIAL_GO 未跟进。历史 frame-level 线，与 clip 线未打通。
- `clip_aqp_phase0_v1_summary.md` / `clip_aqp_phase1_*_summary.md` / `event_budget_gate_v2_summary.md` / `candidate_coverage_gate_v1_summary.md` / `v12_1_completion_v1_summary.md` / `v13_*_summary.md` — 阶段总结（与 test_vlm/outputs 同名报告为镜像）。
- `garc_experiment_protocol.md` / `garc_extension_baseline_summary.md` / `collapse_boundary_analysis.md` / `temporal_retrieval_stress_benchmark.md` — 早期框架与压力测试。

### try_or_no 线（早期 ARC 来源 + 迁移审计）
位置：`try_or_no/`。这是 **历史原型线**，已被 CASQ/V13 主线取代。
- `arc_source/` — ARC 论文源码（含 supg 子目录、Everest/MaskRCNN/YOLOv5s cluster 数据、preprocessing）。参考实现，read-only。
- `experiments/clip_boundary/` — clip 边界 / joint allocation / proxy_baselines / K5/K10/K20 扫描。早期 ARC 实证，已被 superseded。
- `data_moving_arc/realcar_5k/` — realcar_5k 数据（cluster / ground_truth）。早期真实数据尝试，recall=0 失败见 `realcar_5k_arc_stress_test_report.md`、`realcar_5k_failure_attribution_report.md`。
- `outputs/` — factorial / hard_synthetic / moving_camera_feasibility / nuscenes_mini_feasibility / smoke / audit / topic_migration_audit。早期合成与可行性。
- `outputs/topic_migration_audit/recommendation.md` — **关键决策点**：明确把主线收敛到 "Clip-Level Guaranteed AQP (G-ARC)"，并提出必须先证形式化 guarantee + 真实数据验证。仍然是当前选题依据。
- `academic-research-skills/` — 第三方 Claude/学术写作技能包。与项目内容无关，工具性。
- `try_or_no#/vlm_oracle_exp/` — 早期 VLM oracle 探索（qwen2_5_vl_7b）。历史原型。

### 数据与模型（大文件本地态）
- `data/` — bdd100k / driv100 / kitti_raw / nuscenes (mini) / tables / ua_detrac / videos / frames。历史帧级素材。
- `datasets/` — `DrivingDojo-mini`、`casq_external/`（dada2000、dota、micro_casq_v0、nexar）。当前候选外部数据来源，但 DrivingDojo/Nexar 尚未在主线 V13 跑通。
- `models/` — yolo (yolov8n/x)、vlm (qwen3_vl 8B/32B)、.hf_cache。本地权重，read-only 资产。
- `refe_repos/` — `supg/`、`abae/` 论文参考实现。只读参考。

### 协议 / 元
- `.agents/skills/aqp-event-budget-loop/` — 内部 AQP budget 流程技能。工具性。
- `env_garc.sh` — conda 环境激活。工具性。
- `repo_audit_for_codex_v1/`、`codex_research_analysis_v1/` — 已述，**当前最有效的交接**。

---

## 三、研究问题演化（时间线）

依据 `repo_audit_for_codex_v1/EXPERIMENT_LINEAGE.md`、`try_or_no/outputs/topic_migration_audit/recommendation.md`、`garc_eval/outputs/garc_research_retrospective.md`、`G-ARC_Research_Report.md`、`CASQ_CODEX_BRIEF_V12_1.md`。

1. **传统 AQP / 生成式 AQP 阅读**：从 AQP 文献出发，确立 "approximate query processing over expensive predicates" 的问题框架。产物：`G-ARC_Research_Report.md`、`try_or_no/academic-research-skills`（学术审稿工具引用）。结果：选定 "guarantee + budget + expensive oracle" 范式，而非纯生成式。
2. **Hydro / Agent / ML 查询处理方向**：早期探讨过 Agent/ML 查询执行。证据：`try_or_no/outputs/topic_migration_audit/related_work_boundary.md` 中提到 query-impact-aware predictive execution 作为 backup topic。结果：判定为应用性更强、DB venue fit 弱，列为 backup。
3. **ARC / SUPG / ABae / Taster（proxy + oracle budget + guarantee）文献线**：`refe_repos/supg`、`refe_repos/abae`、`try_or_no/arc_source`。本地做了 SUPG / ABae 合成算法级复现（`garc_eval/outputs/supg_paper_synthetic_reproduction`、`abae_paper_synthetic_reproduction`）。结果：确认 frame-level 召回保证可行；clip-level 保证是真正的 gap。
4. **车载 / 移动相机长视频语义 clip 查询**：`try_or_no/outputs/moving_camera_feasibility`、`nuscenes_mini_feasibility`、`experiments/clip_boundary`。结果：发现 frame→clip 退化在合成上 5–20×，确认 G-ARC clip-level guarantee 是真正缺口。
5. **VLM oracle 可用性验证**：`try_or_no#/vlm_oracle_exp`（qwen2_5_vl_7b）、`test_vlm/round2_32b_report.md`、`test_vlm/outputs/prompt_sensitivity_report.md`、`test_vlm/outputs/vlm_killtest_report.md`。结果：32B 比 8B 稳；prompt 敏感（旧 prompt 66% abstain，V13.6 修复到 0%）。VLM-oracle 相对但非人工真值。
6. **cheap proxy / kinematic proxy / YOLO proxy 验证**：`kinematic_proxy`、`roadclip_budget_v2`、`v13_7/v13_9/v13_10` 的 proxy_features。结果：handmade YOLO count + motion 信号弱，V13.9/V13.10 显示 B=20 proxy delta 仅 +0.059（< +0.10 阈值）；kinematic proxy BLOCKED（学习式异常偏离主线）。
7. **CASQ / G-ClipAQP / certificate 方向**：`v12_1_completion_v1`（candidate feasibility READY 但 certificate UNDERPOWERED，38 正样本 < ~500 需求）。结果：certificate 层在采样基准上无法非空推出。Phase 0 power 仿真要求扩到 ≥500 事件。
8. **V12 / V12.1 / V13 realcartest 长视频阶段**：V12/V12.1 完成 Nexar 流水线（derived-boundary 不可用）→ V13 收敛到单一真实长视频 `realcartest.mp4`，构造 V13.6 center10 anchor 协议 → V13.8 全 oracle → V13.9/V13.10 静态 / 自适应 / 上界评测。结果：站住了"参考 + 负结论 + 上界"，正方法与 certificate 仍未站住。

---

## 四、已完成实验总表

| 实验名 | 输出目录 | 输入数据 | 目标 | 方法 | 核心结果数字 | Final Decision | 对当前主线意义 | 仍有效 |
|---|---|---|---|---|---|---|---|---|
| Phase 0 | `test_vlm/outputs/clip_aqp_phase0_v1` (`garc_eval/outputs/clip_aqp_phase0_v1_summary.md`) | 本地 clip + 伪事件 | SUPG stitch 仿真 / bound 审计 | 伪事件拼接 + UCB/LCB | 伪事件，UCB/LCB 公式缺陷 | `NO_GO` → 修复→`UNDERPOWERED_NO_CLEAN_GO_NO_GO`; power→`EXPAND_BENCHMARK_TO_N_EVENTS` (~500) | 第一次暴露 certificate 需要事件规模 | 有效（作为论证"需要扩样本"的依据） |
| Phase 1 data / video access | `clip_aqp_phase1_data_v1`, `clip_aqp_phase1_video_access_v1`, `_auth_v1` | DoTA/DADA-2000/Nexar 元数据 | 准备外部数据流水线 | 下载试通 | HF 鉴权阻塞 | `NEED_HF_AUTH_OR_LICENSE` | 历史基础设施 | 已被 V13 路径取代 |
| Nexar small / 200 / disentangle / video_repair / candidate_v1/v2 / local_smoke | `clip_aqp_phase1_nexar_*`, `clip_aqp_phase1_local_candidate_smoke_v1` | 50/200 Nexar 视频 | 构建 derived-boundary CASQ 基准 | VLM micro-audit + 外部标签映射 | derived true recall 0.06; VLM positive agreement 仅 16%; readable 392/400 | `METHOD_STILL_TOO_VACUOUS`、`CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK`、`CANDIDATE_STILL_TOO_WEAK`、`BOUNDARIES_ARE_DERIVED_ONLY` | 证明 Nexar-200 不可用为 `O_enter_ego_path_v0` oracle | 有效（作为放弃 Nexar 的依据） |
| Micro-CASQ v0 / 32B oracle | `micro_casq_32b_oracle_v0` | candidate pools (kinematic_proxy, roadclip_budget_v2) | 32B oracle 基准 | 采样 + 32B 标注 | 23 合格正, 51 负 | `NEED_MORE_POSITIVES` | 早期采样基准 | 历史（被 v12_1 v1 取代） |
| Micro-CASQ v12.1 completion | `v12_1_completion_v1` | v0 + 99 expansion 32B calls | 推进 certificate | 采样基准 + candidate feasibility + certificate 仿真 | 38 正 / 131 负; reserved pool 47 选 35 / 7 命中 / true recall 0.857 / LCB 0.487 | candidate `READY_FOR_CERTIFICATE`; certificate `UNDERPOWERED` (pool oracle positives < 30); 整体 `NO_CERTIFICATE_YET` | 唯一一次真正跑 certificate 仿真；证明 certificate 在采样基准上 non-trivial 不可达 | 有效（certificate 层未站稳的核心证据） |
| Micro-CASQ adjudication package | `micro_casq_adjudication_package_v0` | 500 selected / 50 pilot clips | 准备人审 | 打包 review kit | 50 pilot | `READY_FOR_PILOT_ADJUDICATION` | 等人审，挂起 | 有效 |
| Candidate coverage gate v1 | `candidate_coverage_gate_v1` (`candidate_coverage_gate_v1_summary.md`) | 早期 candidate | coverage 闸门 | gate sim | — | `WEAK_GO` | 历史闸门 | superseded |
| Event budget gate v2 | `event_budget_gate_v2` (`event_budget_gate_v2_summary.md`) | 早期预算 | 预算闸门 | gate sim | — | `WEAK_GO` | 历史闸门 | superseded |
| Kinematic proxy | `kinematic_proxy` | 早期真实/合成 clip | 运动学异常 proxy | learned anomaly + review | — | `BLOCKED`（偏离 DB/AQP 主线） | 探索性 | 历史 |
| Roadclip budget v2 | `roadclip_budget_v2` | roadclip scene_windows | 候选池 + vlm_oracle_expanded | budget sim | — | feeder only | 喂给 micro_casq | 历史 |
| V13 minimal validation | `v13_minimal_validation_v1` | Nexar-200 | 全视频 candidate smoke | flat vs representation candidate | 无 candidate 达 0.50 at ≤0.35 frac | `FULL_VIDEO_CANDIDATE_FLAT_TRY_REPRESENTATION_CANDIDATE` | candidate 全失败 | 有效（候选生成器弱的依据） |
| V13.5 realcartest pilot | `v13_5_realcartest_oracle_relative_v1` | realcartest.mp4 | pilot 是否够正 | 100 32B calls (旧 prompt) | 18% positive, 66% abstain | `PROCEED_FULL_ORACLE` (但 abstain 须修) | pilot 信号 | 被 V13.6 取代（abstain） |
| V13.6 clip construction | `v13_6_clip_construction_sensitivity_v1` | V13.5 + 修 prompt | clip 构造策略 | 416 calls, 52×8 | center_10s: 56% pos vs 44% fixed_5s; 0% abstain; 399 vs 798 估计全视频 calls | `USE_10S_ANCHOR_CENTERED_FOR_COARSE_ORACLE` | 当前 clip 协议来源 | 有效（单视频） |
| V13.7 multi-method replay | `v13_7_center10_multi_method_replay_v1` | V13.6 labeled subset | 17 方法 × 8 预算 replay | labeled subset (52 clip, 25% high-YOLO 偏) | labeled-subset B=20 best recall 0.448; proxy vs random ≥+0.10 (biased) | `CENTER10_FULL_REFERENCE_RECOMMENDED`（推荐对，数字偏） | 提供 anchor grid + proxy features | 推荐 valid；性能数字 superseded |
| V13.8 full center10 oracle | `v13_8_center10_full_oracle_reference_v1` | 399 anchors | 全 oracle 参考 | Qwen3-VL-32B 全扫 | 399/399 成功; 94 正 (23.6%); 51 拼接事件; 0% abstain; 100% complete; 0% truncation; ~74 min | `FULL_CENTER10_ORACLE_REFERENCE_READY` | 当前最强参考标签 | 有效（主线 source of truth） |
| V13.9 latency-aware AQP | `v13_9_latency_aware_center10_aqp_v1` | V13.8 + V13.7 proxies | 预算静态查询 | 19 方法 × 5 预算 | B=20 best: uniform 0.137 (event_recall_overlap); B=40: top_fusion_geometry_motion 0.216; proxy delta vs random @ B=20 = +0.059 (< +0.10) | `LATENCY_AWARE_AQP_FAIL` | 核心负结论 | 有效（V13.10 复核） |
| V13.10 upper bound + adaptive | `v13_10` | V13.8 + V13.7 + V13.9 | OracleBest + 自适应 + metric reconcile | OracleBest 直接发现 + adaptive sim + 字段比对 | OracleBest@B = min(B,51)/51 (B=5→0.098, B=20→0.392, B=40→0.784, B=80→1.0); static best eff B=20 0.350; B=40 0.275; adaptive 任何预算不超过 best static; same-base 11/15 hurt; 93→18 mismatch 修复为 0 语义差异 | `STATIC_METHODS_FAR_BELOW_UPPER_BOUND`、`ADAPTIVE_NO_BETTER`、`SAME_BASE_HURTS_CONSISTENTLY`、`V13_10_COMPARISON_BUG_NOT_SEMANTIC_DIFFERENCE` | 核心负结论 + 上界 | 有效 |
| Proxy kill-test 复核 | `v13_result_audit_proxy_killtest_20260624_152107` | V13.8/V13.9/V13.10 | 复核 proxy 失败是否稳健 | 重复随机种子 / 字段审计 | — | 复核 proxy 失败 | 复核 | 有效 |
| try_or_no realcar_5k ARC | `try_or_no/data_moving_arc/realcar_5k`, `realcar_5k_*_report.md` | realcar_5k (K=12, tau=30) | 真实数据 ARC stress | ARC pipeline | proxy-oracle Pearson 0.79 / Spearman 0.80; proxy recall 0.285 / precision 0.682; ARC recall=0 | 失败归因（proxy 与 oracle 错位） | 早期真实数据失败案例 | 历史（被 V13 取代） |
| try_or_no clip_boundary | `try_or_no/experiments/clip_boundary/*` | UA-DETRAC / 合成 | clip 边界 / joint allocation / K 扫 | factorial + stress | propagation 比 allocation 影响大 ~5×; naive adaptive 全失败 | 探索 | 历史规模性结论 | 历史 |
| garc_eval SUPG/ABae 复现 | `garc_eval/outputs/supg_*`, `abae_*` | 合成 / BDD100K / KITTI / UA-DETRAC | 算法级复现 | run_supg_synthetic / run_abae_synthetic | 合成复现 OK; KITTI 退化; BDD100K 图像级有效; UA-DETRAC 常选全 | frame-level 线状态 | 与 clip 线未打通 | 历史 |

---

## 五、当前已经被验证的事实（证据来源）

### 1. VLM oracle 方面
- Qwen3-VL-32B 已在 realcartest 上跑通 399 次，0% abstain（V13.6 修 prompt 后）；旧 prompt 在同一视频上 66% abstain。证据：`v13_8.../tables/center10_full_oracle_labels.csv`（399 行，label=positive 94 / negative 305，abstain_reason 全空）；`v13_5.../tables/vlm_pilot_labels.csv` + V13.6 报告。
- prompt 极度敏感：`test_vlm/outputs/prompt_sensitivity_report.md`、"Normal driving → negative" 修复即把 66% abstain 降到 0%。证据：V13.6 FINAL_REPORT。
- 8B 比 32B 不稳：早期 `test_vlm/outputs/round2_32b_report.md`、`try_or_no#/vlm_oracle_exp` 用 qwen2_5_vl_7b 探索；V13 全用 32B。
- VLM 同 clip 重复一致性未在现有文件中确认（OPEN_QUESTIONS_AND_RISKS 标 MEDIUM，未跑）。未在现有文件中确认。

### 2. cheap proxy 方面
- YOLO 车辆 count / bbox 几何 / center-region count / motion energy 在 V13.9/V13.10 full-oracle 上弱：B=20 proxy delta vs random 仅 +0.059；best static eff B=20 仅 0.350（远低于 OracleBest 0.392 的理想，且远低于"再多预算能拿到的效率"）。证据：`v13_10/tables/static_methods_efficiency_v13_10.csv`（实测 best/预算如 §四）、`v13_9.../tables/method_budget_results.csv`。
- proxy 与 oracle 在 realcar_5k 上相关性高（Pearson 0.79）但 ARC recall=0，说明 proxy 与目标 predicate 错位（捕获交通密度而非 ego-path 入侵）。证据：`realcar_5k_failure_attribution_report.md`。
- kinematic learned-anomaly proxy 偏离主线，BLOCKED。证据：`kinematic_proxy/` 多报告。

### 3. clip construction 方面
- 固定 5s vs center_10s：center_10s 在 V13.6 上 56% vs 44% 正率、399 vs 798 估计全视频 calls、0% abstain、100% complete / 0% truncation。证据：`v13_6.../tables/clip_construction_policy_summary.csv`、`full_video_call_cost_estimates.csv`。
- boundary refinement / IoU 0.3 在 10s anchor vs ~5s event 下恒为 0（不适合 anchor 级评测），应使用 event_recall_overlap。证据：V13.9 IoU 列全 0、V13.10 mismatch 根因报告。
- 自适应局部扩展（priority boost / bidirectional expand）在 11/15 same-base 组合下 hurt 或 neutral。证据：`v13_10/tables/same_base_comparison_v13_10.csv`、`window_sensitivity_v13_10.csv`。

### 4. budget replay 方面
- proxy-guided 在 unbiased full-oracle 下未优于 uniform/random：B=20 最佳静态是 uniform_anchor_10s (0.137)；proxy-guided 相对 random delta 仅 +0.059，低于预设 +0.10 阈值。证据：`v13_9.../tables/method_budget_results.csv`、V13.9/V13.10 FINAL_REPORT。
- V13.7 labeled-subset 给出的 proxy 优势被 full-oracle 证伪（25% high-YOLO 偏采样把 proxy 通胀 ~3×）。证据：V13.10 report 中 reuse audit 与 V13.9 对比；DECISION_LOG 第 2 行标注 superseded。
- adaptive 无改善。证据如上。

### 5. benchmark 方面
- **realcartest**：唯一支撑 V13 主线的长视频；399 anchor / 94 正 / 51 事件，单视频。证据：V13.8。
- **Nexar**：derived-boundary 不可用作 `O_enter_ego_path_v0` oracle（VLM positive agreement 16%）；Phase 1 全部 candidate 太弱。证据：`nexar_candidate_v2/reports/EXTERNAL_LABEL_MAPPING.md`(LOOSE_APPROXIMATION)、`VLM_MICRO_AUDIT_REPORT.md`(UNRELIABLE)、`nexar_200_v1` true derived recall 0.06。
- **DrivingDojo**：`datasets/DrivingDojo-mini` 存在；未在主线 V13 跑过；`strive_d_drivingdojo_asset_audit_v1` 仅有资产审计。是否真正可用未在现有文件中确认。
- **nuScenes / KITTI / UA-DETRAC / BDD100K**：仅 garc_eval 帧级线使用；KITTI 退化、BDD100K 图像级有效、UA-DETRAC 常选全、nuScenes PARTIAL_GO 未跟进。证据：`garc_eval/outputs/{uadetrac_dataset_audit,kitti_*,bdd100k_*,nuscenes_event_aqp_feasibility_audit_v1}.md`。

### 6. statistical certificate 方面
- v12.1 是唯一一次真正 certificate 仿真：candidate feasibility READY，但 RESERVED certification pool 中 oracle positive 数 < 30，certificate UNDERPOWERED。证据：`v12_1_completion_v1/certificate/reports/MICRO_CASQ_CERTIFICATE_REPORT.md`（reserved_pool_n=47, selected_n=35, positive_event_count=7, LCB 0.487, decision UNDERPOWERED）。
- candidate 已 "READY_FOR_CERTIFICATE"（部分 valid）：但仅在**采样基准**上，不是全视频检索。证据同上。
- Phase 0.6 power 仿真表明需 ≥500 事件才能非空。证据：`clip_aqp_phase0_v1/power_v1/reports/POWER_REPORT.md` (NEED_500_EVENTS)。
- certificate 在 V13.8 valid oracle 上**从未跑过**（blocked by "no working budgeted query plan"）。证据：OPEN_QUESTIONS_AND_RISKS §Statistical guarantee layer untested。

### 7. system cost 方面
- V13.8 全 399 calls 32B 约 74 min GPU（A800 80GB），脚本可恢复（resume）。证据：V13.8 FINAL_REPORT、OPEN_QUESTIONS_AND_RISKS §Engineering。
- 估计全视频 calls：center_10s 399 vs fixed_5s 798，clip 构造直接省 50% 调用。证据：`v13_6.../tables/full_video_call_cost_estimates.csv`。
- 数据读取 / 编码瓶颈（realcartest 由 Bilibili XCoder 压制）的具体 profiling 未在现有文件中确认。未在现有文件中确认。

---

## 六、当前尚未解决的关键问题（带证据路径）

1. **oracle 定义问题**：当前 oracle = Qwen3-VL-32B，非人工真值；同一 clip 重复一致性未测；无人工校准集；事件边界误差未测。证据：`OPEN_QUESTIONS_AND_RISKS.md` §Oracle-Label、`repo_audit_for_codex_v1/EVIDENCE_PACK.md` §6.
2. **query semantics 问题**：`O_enter_ego_path_v0` 是当前唯一活跃 predicate，是否扩展到其他语义事件（cut-in / pedestrian / cyclist）未定；clip 召回命中语义（overlap vs direct discovery）已 reconcile 但 IoU 类指标仍不可用。证据：V13.10_MISMATCH_ROOT_CAUSE.md、CASQ_CODEX_BRIEF_V12_1.md。
3. **proxy 是否足够强**：handmade YOLO/motion 已证弱；representation-based (CLIP/SigLIP) 与 8B VLM cascade 均未测；ego-path-conditioned geometric proxy 未测。证据：`codex_research_analysis_v1/NEXT_EXPERIMENT_RECOMMENDATION.md`、V13.9/V13.10。
4. **clip 构造与边界问题**：center_10s 协议在 realcartest 完成 100% / 0% truncation，但 popup 在更长事件或恶劣天气未知；boundary 2s 精修未测。证据：V13.6/V13.8、`OPEN_QUESTIONS_AND_RISKS`。
5. **能否给 recall / confidence / certificate**：certificate 未在 V13.8 上跑过；采样基准下 UNDERPOWERED；需 ~500 事件而 V13.8 仅 51。证据：`v12_1_completion_v1/certificate/...`、Phase 0 power report。
6. **数据集规模与泛化**：所有 V13.x 仅来自 realcartest.mp4 一段 66.5 min 视频；23.6% 正率、0% abstain 不可外推；无第二视频。证据：`CURRENT_STATUS_ASSESSMENT.md` §7、`OPEN_QUESTIONS_AND_RISKS` §Single-Dataset。
7. **实验功效不足**：V13.9/V13.10 是单 oracle 一次跑（无 100-trial 重采样）；随机基线 仅 5 seed；certificate 仿真单配置。`AGENTS.md` 规定随机基线 ≥100 repeats 未在 V13 线严格执行。证据：`v13_9.../tables/random_seed_summary.csv` (5 seeds)、DECISION_LOG。
8. **论文 claim 还缺什么**：(a) 一个正向方法（当前只有负结论）；(b) certificate 在有效 oracle 上非空证明；(c) 第二视频泛化；(d) 人工校准；(e) proxy-agnostic 跨多类 proxy 的演示（当前只有 cheap 单类）。证据：`CODEX_FINAL_DECISION.md` (PROMISING_BUT_NEEDS_POSITIVE_METHOD)。

---

## 七、当前项目状态判断

**阶段**：问题与评测栈已建立（`AQP_STATUS: PROBLEM_AND_EVALUATION_ESTABLISHED`），方法与 certificate 贡献尚未站住（`RESEARCH_STATUS: PROMISING_BUT_NEEDS_POSITIVE_METHOD`）。依据：`codex_research_analysis_v1/CODEX_FINAL_DECISION.md`。

**已经站住（可作为论文 fact 引用）**：
- V13.8 full center10 oracle 参考（399/94/51，0% abstain）。
- V13.10 OracleBest 上界曲线与上界远超 static 的事实（eff B=20 0.350 vs ideal 0.392；B=40 0.275 vs ideal 0.784）。
- V13.6 center_10s > fixed_5s（在该视频上）。
- V13.9/V13.10 handmade cheap proxy 在 budgeted AQP 下失败的负结论。
- Nexar-200 不可用作该 predicate 的 oracle-relative 基准。
- v12.1 certificate 在采样基准上 UNDERPOWERED。

**还只是现象（不可外推）**：
- 23.6% 正率、0% abstain、100% complete event（单视频）。
- adaptive 在 11/15 组合下 hurt（仅当前 proxy 下）。
- realcar_5k ARC recall=0 的失败归因（特定数据 + K）。

**不应继续投入的方向**：
- 继续在 Nexar-200 derived-boundary 上做 oracle-relative claim（已证 UNRELIABLE）。
- 继续在 KITTI / UA-DETRAC 上做 SUPG-RT 主要 benchmark（已证退化）。
- 继续在 V13.7 labeled-subset 数字上做性能 claim（已证 biased）。
- 继续做 naive local adaptive boost/expand（V13.10 已证 hurt）。
- 继续在无正向方法下跑 certificate 仿真（recall 太低使 certificate vacuous）。

**最值得继续推进的方向**（依据 `NEXT_EXPERIMENT_RECOMMENDATION` 排序）：
1. ego-path-conditioned geometric proxy（最便宜的"是否能拿到正向 L0 信号"测试）。
2. RoI-SigLIP / CLIP representation scorer（leakage-safe）。
3. 8B VLM cascade pilot（需新 VLM call，需授权）。
4. 第二长视频验证（最强外生有效性质保障）。
5. certificate 在 V13.8 上的 minimal B1 no-repair 仿真（即使 recall 低也能验证保证层逻辑）。

**是否足够写论文**：尚不足。依据 `CODEX_FINAL_DECISION.md` 与 `garc_research_retrospective.md`（自评 30–40%）。缺的是 **正向方法 + certificate 非空 + 第二视频**，而不是单纯工程量；核心缺的是"proxy-agnostic 在多类 proxy 上都能给保证"的演示，即问题抽象层面的核心贡献尚未有证据。

**判断依据**：上述 EVIDENCE_PACK / EXPERIMENT_LINEAGE / DECISION_LOG / V13.9 / V13.10 / v12.1_certificate 文件交叉印证。

---

## 八、最小下一步建议（不依赖新实验的部分明天可做）

### 1. 明天就能做（只读 / 文档）
- 把 V13.9/V13.10 的"static efficiency / OracleBest / adaptive hurt"三组数字固化成 paper-grade 表格，并明确所有数字标 `VLM_ORACLE_RELATIVE, single-video`。
- 写一份"certificate 推不出来"的归因文档：把 Phase 0 power 仿真（≥500 事件）与 v12.1 certificate UNDERPOWERED（reserved pool oracle positives < 30）与 V13.8（仅 51 事件）三者串联，定量说明 certificate 非空需要多少事件、当前差多少。
- 把 proxy 弱结论与 ego-path 错位结论（`realcar_5k_failure_attribution_report.md` Pearson 0.79 但 ARC recall=0 + V13.9 delta +0.059）合并成一段 motivation：proxy 抓交通密度而非 ego-path 入侵。
- 校验现有 raw_vlm_responses 的重复一致性（仅读 JSON，不调模型）可作 oracle stability 量化。

### 2. 一周内应补齐
- 一个 leakage-safe 的 ego-path-conditioned geometric proxy score（仅复用已有 YOLO geometry + anchor timestamps，无新 GPU），并在 V13.8 oracle 上 replay；Pass = B=20 event recall > 0.137 且超 random +0.10。
- certificate 在 V13.8 上的 minimal B1 no-repair 仿真（无新模型），即便 non-vacuous 表明 guarantee 层逻辑可跑。
- 一份"正方法缺失"的 paper outline：负结论 + OracleBest 上界 + 上界远未被静态触达 → 引出下一类 proxy。
- random baseline ≥100 repeats（按 AGENTS.md 要求）的最小补跑（纯 replay，无新 oracle）。

### 3. 一个月内要形成的论文级核心证据
- **至少一个正向 selection 方法**（ego-geometry / CLIP / 8B cascade 至少一个 Pass）使得 B=20 event recall 显著超 uniform 且达 OracleBest 的可观比例。
- **second-video 验证**：在另一段长驾驶视频上重跑 center10 oracle pilot（先小 pilot，避免 32B 全扫），验证 0% abstain 与正率量级。
- **certificate 在一个有效 oracle 上非空**：要么扩到事件数够的真实/合成基准（≥500 事件），要么证明在 V13.8 上即便 recall 低也能给出 conservative oracle-relative 表述。
- **人工小审（20–50 clip）** 校准 32B oracle，否则 `VLM_ORACLE_RELATIVE → human-truth` 不可声称。

### 4. 失败条件（收敛或转向）
- 若 ego-geometry / CLIP / 8B cascade 三者都 fail（B=20 仍 ≤ uniform + 0.10），则"廉价/中等 proxy 可达 budgeted AQP"路线需收缩 → 转向"任意 oracle 输入下保守 certificate 的纯统计贡献"作为主 claim（即使没有好 proxy，certificate 层仍是 DB 贡献）。
- 若 second-video 出现 0% 事件或 prompt 大面积 abstain，则 realcartest 23.6% 是特例 → 必须改 predicate 或换数据，否则单视频 claim 不能成文。
- 若 certificate 在扩到 ≥500 事件基准后仍 vacuous，则 clip-level 保证的统计可行性本身受质疑 → 需重新定义 hit 语义或放宽 γ/δ，或退回 frame-level + aggregation claim。

---

## 九、最终摘要（10 条 bullet）

1. 项目是 **DB/AQP**：长视频上给定 cheap 候选生成器 + 昂贵 VLM oracle + 预算 B + (γ, δ)，返回变长事件 clip 并给 **clip-level oracle-relative 召回的保守 certificate**；不是驾驶事件检测。依据 `CASQ_CODEX_BRIEF_V12_1.md`、`CODEX_FINAL_DECISION.md`。
2. 唯一 active predicate 是 `O_enter_ego_path_v0`；所有正例均为 Qwen3-VL-32B 标签，非人工真值。依据 V13.5/6/8。
3. 唯一主线长视频是 `realcartest.mp4`（~66.5 min）；V13.8 全 oracle：399 anchor / 94 正 / 51 拼接事件 / 0% abstain / 100% complete。依据 `v13_8.../tables/`。
4. clip 构造结论：center_10s > fixed_5s（V13.6，56% vs 44%，全视频调用减半）。这是当前 clip 协议来源。
5. OracleBest 上界 = min(B,51)/51；B=20 → 0.392，B=40 → 0.784。静态最佳效率 B=20 仅 0.350、B=40 仅 0.275，远低于上界。依据 `v13_10/tables/`。
6. **handmade cheap proxy 已证弱**：B=20 proxy delta vs random 仅 +0.059 (< +0.10)；proxy 抓交通密度而非 ego-path 入侵（realcar_5k Pearson 0.79 但 ARC recall=0）。`LATENCY_AWARE_AQP_FAIL`。
7. **adaptive 局部 boost/expand 无效**：11/15 same-base 组合 hurt；naive local adaptive 不应继续投入。
8. **certificate 未站住**：v12.1 certificate UNDERPOWERED（reserved pool oracle positives < 30）；Phase 0 power 要求 ≥500 事件，V13.8 仅 51；certificate 从未在 V13.8 valid oracle 上跑过。`NO_CERTIFICATE_YET`。
9. 已放弃 / superseded：Nexar-200 derived-boundary（UNRELIABLE, 16% positive agreement）、KITTI / UA-DETRAC SUPG-RT（退化）、V13.7 labeled-subset 数字（biased）、kinematic_proxy（BLOCKED）。
10. 当前判定：`PROBLEM_AND_EVALUATION_ESTABLISHED` 但 `NEEDS_POSITIVE_METHOD`；最缺的是"正向 selection 方法 + certificate 在有效 oracle 上非空 + 第二视频"，缺的是问题抽象与方法证据，不只是工程量。下一步首选 ego-path-conditioned geometric proxy（低成本、leakage-safe、可直接在 V13.8 replay）。

---

### 证据路径索引（可直接复核的关键文件）
- 协议：`CASQ_CODEX_BRIEF_V12_1.md`
- 综合交接：`repo_audit_for_codex_v1/EVIDENCE_PACK.md`、`EXPERIMENT_LINEAGE.md`、`DECISION_LOG.md`、`OPEN_QUESTIONS_AND_RISKS.md`、`codex_research_analysis_v1/CODEX_FINAL_DECISION.md`、`CURRENT_STATUS_ASSESSMENT.md`、`NEXT_EXPERIMENT_RECOMMENDATION.md`
- 主线参考标签：`test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv`、`center10_vlm_oracle_events.csv`
- clip 构造：`test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/tables/clip_construction_policy_summary.csv`、`full_video_call_cost_estimates.csv`
- 负结论：`test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/tables/method_budget_results.csv`、`test_vlm/outputs/v13_10/tables/static_methods_efficiency_v13_10.csv`、`same_base_comparison_v13_10.csv`、`oracle_upper_bound_v13_10.csv`
- certificate：`test_vlm/outputs/v12_1_completion_v1/certificate/reports/MICRO_CASQ_CERTIFICATE_REPORT.md`、`clip_aqp_phase0_v1/power_v1/reports/POWER_REPORT.md`
- proxy 错位：`try_or_no/outputs/realcar_5k_failure_attribution_report.md`
- 选线决策：`try_or_no/outputs/topic_migration_audit/recommendation.md`
- 数据 / 复现：`garc_eval/outputs/paper_reproduction_matrix.md`、`garc_research_retrospective.md`、`uadetrac_dataset_audit.md`、`nuscenes_event_aqp_feasibility_audit_v1.md`
- Nexar 放弃依据：`test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/reports/EXTERNAL_LABEL_MAPPING.md`、`VLM_MICRO_AUDIT_REPORT.md`