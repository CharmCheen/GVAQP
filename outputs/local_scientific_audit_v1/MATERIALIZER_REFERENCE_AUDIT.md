# 物化器 / 引用构造代码审计报告

**审计范围**：GVAQP 仓库「物化器 / 引用构造」相关实现的实际语义（静态代码阅读 + stdlib-only 确定性重算）。
**审计方式**：仅静态阅读与 `csv/json/hashlib` 确定性分析；本机无 GPU，未运行任何 Qwen/VLM/YOLO 推理、未下载模型、未训练。
**审计日期**：2026-08-13（UTC）。
**被审计文件指纹（SHA-256）**：

| 文件 | SHA-256 |
|---|---|
| `src/garc_eval/accelerated_event_query/k3_unit_event_adapter.py` | `7f00162bb30104ea21e9073883c74f26958618af510a05aa2be11a390568425c` |
| `src/garc_eval/accelerated_event_query/matching.py` | `0ad0b0205e7a88e75b7c555f7063246883aed64816612a8c669cb72dbd3bf9b0` |
| `src/garc_eval/accelerated_event_query/model_relative_event_relation.py` | `36667dc7d399b79c5e9914f4f58f66c24753f34ff8895df4ac1d95cb6a01db8e` |
| `src/garc_eval/accelerated_event_query/types.py` | `13858a9bbc359f320aaa84c9084149e2c985ae5e43df683da5e2bc4d007a4dc2` |
| `scripts/analyze_p0_v3_materializer_mechanisms.py` | `0be43de422cb3dcae8c5bc3627816398a480fa3c10df2633650b080ca2d2230c` |
| `scripts/run_p0_v3_materializer_validation.py` | `090537f0972a61b967b9424770b2b2ae243d92e4897d732c20bfcc1564d9146d` |
| `outputs/p0_materializer_validation_v3/EXPERIMENT_PROTOCOL.json` | `a396b61edb1773dc7222b8abbb81aed9d9d9ecd7f19d5fd284a8db87b202773a` |
| `outputs/v10_multiseal_reference_v1/MULTI_SEAL_PROTOCOL.json` | `5b5d85d5c4ded64587da77236d29c9cac3bbcb1b24585c830256e069db83ae19` |
| `outputs/v10_multiseal_reference_v1/REFERENCE_MANIFEST.json` | `53bceb8be451e8ac853810bdde75ad25f6e0f89477621260d178d2dfbbef6ed2` |

与 `PROJECT_STATE_OF_TRUTH.md` / `NEXT_STAGE_STATE_MACHINE.md` 交叉核对：本审计的结论与项目状态文件中的边界声明（"cached、query-budget、K3-reference/model-relative"）一致，未发现矛盾；本报告是对主证据（CSV + 代码）的独立复核。

---

## a. K3 的精确定义

K3 是 `K3UnitEventAdapter`（`k3_unit_event_adapter.py`）+ 冻结配置 `K3_UNIT_EVENT_CONFIG_V3.json`（`K3UnitEventConfig`，`protocol_id = AEQ_MODEL_RELATIVE_K3_V3_1`）。合并规则（`_materialize` + `_can_merge`，每视频独立处理）：

1. **仅 relevant 单元构成事件支持**：`outcome == "relevant"` 的单元是事件锚点；`not_relevant` / `unknown` / `parse_failure` 从不产生事件，只分别记入 `negative_unit_ids` / `unknown_unit_ids` / `parse_failure_unit_ids`。
2. **排序与去重**：按 `(video_id, start_time, end_time, unit_id)` 排序；同 unit_id 冲突（核心字段不一致）报错，去 diagnostics 后单例化。
3. **相邻合并（gap == 0）**：`merge_adjacent_positive_units=True`，紧邻 positive 直接合并。
4. **未知桥接（0 < gap ≤ 10s）**：`unknown_gap_rule = bridge_one_fully_covering_unknown_unit_within_maximum_gap` —— 若左右 positive 之间恰好存在 ≤1 个（`maximum_unknown_gap_units=1`）**unknown** 单元、且该单元完全覆盖空隙（`bridge_start <= left.end_time and bridge_end >= right.start_time`），则允许合并；空隙 >10s 或 between 数量 >1 则拒绝。
5. **negative 硬屏障**：`negative_gap_rule = hard_barrier` —— 之间出现 `not_relevant` 单元即拒绝合并。
6. **parse_failure 为"不确定硬屏障"**：`parse_failure_gap_rule = indeterminate_hard_barrier_not_negative` —— 不合并（与 negative 同样阻断），但语义上不归为 negative（记入独立类别）。
7. **时长上限**：合并后组跨度 `end - start > min(maximum_core_duration_seconds=40, maximum_event_duration_seconds=60)=40s` 即拒绝本次合并（`adjacent_distinct_event_rule = merge_observationally_indistinguishable_adjacent_positives_until_duration_cap`）。
8. **事件构造**：每组一个 `VERIFIED_EVENT`，`start = min(group start)`，`end = max(group end)`（`boundary_rule = min_positive_unit_start_to_max_positive_unit_end`）；`event_score=1.0`；`event_id = sha256(query_id, video_id, 组内最早 positive unit_id, k3_config_sha256)` 截 16 位（`event_identity_rule`）；`k3_group` 同规则。
9. **exact 配置**：参数以 JSON 冻结，`k3_config_sha256 = canonical_hash(parameters)`。本审计用 stdlib 复刻 `canonical_hash`（`json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)` → sha256）重算，得 `7906ab2da20cab7edbe0f379224b60160c7a857cd81ab7f4fec42f54ab9629b9`，与 `K3_UNIT_EVENT_CONFIG_V3.json` 的 `k3_config_sha256`、V10 `REFERENCE_MANIFEST.json` 的 `k3_config_hash`、P0 `EXPERIMENT_PROTOCOL.json` 的 `materializers.K3.config_sha256` **三者完全一致**。

K3 的 unknown/parse 语义一句话总结：**unknown 可桥接一个完全覆盖空隙的单元（≤10s 空隙），parse_failure 是"不归为 negative 的硬屏障"，negative 是硬屏障，相邻 positive 直接合并，组跨度上限 40s；只从 relevant 单元构造事件。**

> 注意：K3 与 C1 的一个关键差异 —— K3 对 0<gap≤10s 的非相邻 positive 合并**要求 unknown 桥**，而 C1 只要求 gap≤10s（不看之间是什么）。这是"K3 相对 C3 的未知/parse/exact 语义"边际的一部分。

## b. C0 / C1（gap-only）精确定义

来自 `scripts/analyze_p0_v3_materializer_mechanisms.py::generic_events`（54 条冻结 P0 轨迹上的 outcome 保持重放，`VARIANTS = (C0_naive_all_positive_span, C1_gap_limited, C2_gap_duration, C3_gap_duration_negative_barrier, K3_current_v3)`）：

- **C0（`C0_naive_all_positive_span`）**：把该轨迹**所有被查询的 relevant 单元合并为恰好一个事件**，跨度 = min(start)→max(end)；无 relevant 则不产生事件。与 P0 运行器中的 K0（`run_p0_v3_materializer_validation.py::k0_materialize`）**语义完全相同**（`K0_DEFINITION` 明确写"emit exactly one VERIFIED_EVENT spanning min(start) to max(end) of every queried relevant unit"，且不检查 negatives/unknowns/parse failures/gaps/duration caps）。
- **C1（`C1_gap_limited`）**：按 `(start,end,unit_id)` 排序 relevant 锚点后做**贪心链式合并**：仅当相邻锚点 `gap = max(0, right.start - left.end) ≤ 10.0s` 时并入当前组，否则开新组。**无时长上限、无 negative 屏障、无 unknown/parse 语义**（即 C1 可由多条 ≤10s 相邻空隙链成一个任意长的跨度，直到遇到 >10s 空隙）。每组 → 一个 `VERIFIED_EVENT`，跨度 = 组内 min→max。
- **C2 = C1 + 40s 核心跨度上限**（`proposed_end - proposed_start <= 40.0`）。
- **C3 = C2 + 被查询 negative 屏障**：相邻锚点之间若存在 `not_relevant` 单元严格位于窗口内（`x.start >= left.end and x.end <= right.start and x.end > left.end and x.start < right.start`）则禁止合并。
- **K3_current_v3**：直接调用 `runner.k3_materialize`（= `K3UnitEventAdapter` + 冻结配置），含 unknown/parse/exact 语义。

**"gap-only 效应" = C1 − C0**：即把"所有相关锚点 → 一个跨度"换成"≤10s 空隙才合并、否则分裂为多个事件"带来的增量。**C0 效应 = K0 基线**（P0 的控制组）。

## c. 匹配 / 评估器语义与 EventF1

`matching.py`（`MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0)` 为主匹配器，协议 `primary_matcher = v3_one_to_one_max_cardinality_then_tiou`）：

- **eligibility = strict positive temporal overlap**：`temporal_iou > minimum_tiou(=0.0)` 或 `boundary_ok`（起止点各自 |差| ≤ tolerance=0.0，即精确边界相等）。`temporal_iou = intersection/union`，`intersection = max(0, min(a_end,b_end) − max(a_start,b_start))`，故 `tIoU > 0 ⟺ 严格正重叠`（恰好相接、零长度交叠不算）。`boundary_ok` 需要两端都精确相等，此时必有正重叠，因此有效资格条件就是**严格正时间重叠**。
- **1:1 最大基数匹配，然后 tIoU**：`score = eligible*1_000_000 + iou`，`linear_sum_assignment(-score)` 最小化负分 = 最大化总分。因 `1e6 ≫ 任何 iou 和差`，最优解先最大化**合格配对数（基数）**，再在基数相同的情况下最大化 tIoU 总和。非合格配对在事后被剔除（不计入 TP）。这是确定性的（给定输入矩阵，scipy 的指派算法无随机性）。
- **EventF1（TP/FP/FN 定义）**：`TP = matched_events = 合格且被指派的配对数`；`FP = len(predicted) − TP`（含"未匹配但重叠的预测"→ 协议 `duplicate_rule = unmatched_overlapping_prediction_is_false_positive`）；`FN = len(reference) − TP`；`precision = TP/len(predicted)`，`recall = TP/len(reference)`，`F1 = 2PR/(P+R)`（`summarize_matches` 与 `metric_row` 一致）。`mean_event_boundary_tIoU` 只作边界质量的报告量，不影响 F1。
- **tIoU 敏感度**：`SENSITIVITY_MATCH = one_to_one_tiou_at_least_0_30`（`minimum_tiou=0.30`），资格变为 `tIoU > 0.30` 或精确边界相等，其余逻辑相同；在 P0 中作为 `sensitivity_F1_tiou_0_30` 列报告，不参与主判定。
- **主判定阈值**（协议 `statistics`）：`material_effect_threshold_f1 = 0.02`，`accept_direction_threshold = 0.75`；`decision_summary` 要求 direction ≥0.75、median ≥0.02、3 个 selector 均正、3 视频均正、K3 overmerge < K0 才 ACCEPT。

## d. 引用（reference）的构造与循环风险事实

引用由两层构成，两者**都不是人类独立真值**：

1. **单元标签层（模型相对）**：`outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet` 的 1475 个单元的 `authoritative_label` 全部来自 **Qwen3-VL-32B-Instruct-FP8**（`scripts/run_v10_multiseal_oracle.py` 用 `transformers.Qwen3VLForConditionalGeneration.from_pretrained(..., local_files_only=True)` 加载；`MULTI_SEAL_PROTOCOL.json::semantic_contract.model_hash = 3febe26f...`；预注册文件 ground_truth_definition 明确写 "authoritative label emitted for each exact frozen unit by the bound Qwen3-VL-32B checkpoint…"）。提示词明确指示模型**只输出单元标签，事件构造由 K3 完成**（"K3, not this model response, constructs events and event boundaries"）。多 seal（SEAL_A = 1454 个 V9 可接受检查点 + SEAL_B = 21 个缺失集单元，`CROSS_SEAL_COMPATIBILITY = PASS`）验证的是**同一模型输出的可复现性**（shadow 9 单元 raw/parsed 一致），不是人类正确性。
2. **事件层（K3 定义）**：`scripts/finalize_v10_multiseal_reference.py::finalize`（L145–152）用**与 P0 方法侧完全相同的 `K3UnitEventAdapter` + 相同冻结配置（k3_config_hash = 7906ab…，与协议 `materializers.K3.config_sha256` 逐位相等）**，在全网格 1475 标签上 `materialize()` 两次并校验确定性，写出 `K3_MODEL_RELATIVE_EVENT_RELATION.parquet`。

**结论：是。引用 = 同一 Qwen3-VL-32B 模型在 full-grid 上、由同一 K3 规则族（同一 adapter 代码 + 同一 exact 配置哈希）定义的事件关系。** 方法侧 K3 只是在该引用的"稀疏查询子集"上重跑同一规则族。因此"K3 重建 K3 定义的事件关系"的 F1 比较中，**评测真值与被测算法共享事件定义层** —— 这正是项目自评 `QUALIFIED_BUT_VALID`（`REFERENCE_CIRCULARITY_AUDIT.md`）的含义，且该审计明确说：对"K3 是否普遍优于其他物化器"的无条件主张这是**致命**的，仅对"稀疏 K3 能否重建冻结 K3 定义关系"的机制研究不致命。

**人类独立真值**：`outputs/gvaqp_long_horizon_p1_p3_v1/human_reference_package/HUMAN_EVENT_LABELS.jsonl` **0 行**（sha256 = `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，即空文件哈希）；未读取其内容，仅记录行数/哈希。该包内 `ANNOTATOR_VIEW_CASES.json` 等为标注工具文件，未读取标注内容。**不存在任何人类独立的 ground truth。**（按指示，除该文件的行数/哈希外未读取任何其他人类标注内容。）

## e. 判定与理由

1. **MATERIALIZATION_IMPORTANCE（物化器重要性证据等级）= LOW_TO_MODERATE**（狭窄的模型相对重建结论为 MODERATE；作为一般物化器重要性证据为 LOW）。
   理由：效应在 54 个受控对中真实且可复现（median ΔF1 = +0.1457，40/14/0，3 视频、3 selector，protocol 判定 REVISE 而非 ACCEPT——方向/量级/视频一致性达标但 selector 稳健性不足，TemporalCoverage 仅 9/18 正、median +0.0182）；但 (1) 引用为模型相对且 K3 定义（d 节），(2) 机制消融显示中位数增益的 ~94.5%（0.1377/0.1457）来自**平凡 10s gap 约束**，(3) 复杂 K3 语义边际为 0 甚至略负，(4) 是 query-budget 缓存重放而非物理 deadline。因此作为一般研究主张的证据等级低；仅作为"在冻结 K3 引用下 K3 优于 K0 的重建系统发现"成立（与 `PROJECT_STATE_OF_TRUTH` 的边界一致）。
2. **COMPLEX_K3_NOVELTY（复杂 K3 新颖性）＝ 不成立（NOT ESTABLISHED）**。
   理由：K3 相对 C3 的"unknown 桥接/parse 语义/exact 配置"边际：**median = 0.0，mean = −0.00034，54 格中 0 正 / 50 平 / 4 负**（K3 在这些格反而更差）；duration-cap 边际 median 0.0（mean +0.0072，10 正）；negative-barrier 边际 median 0.0（mean +0.0034，5 正）。即 K3 相对 C0/C1 的全部主要增益可由简单 gap 约束解释，K3 特有的复杂机制在当前稀疏轨迹上**没有任何正的边际贡献**。复杂 K3 的新颖性主张缺乏证据。
3. **REFERENCE_CIRCULARITY_RISK = HIGH**（对事件级无条件主张）。
   理由：(a) 引用事件关系与方法侧 K3 共享同一 adapter 代码、同一冻结配置哈希（7906ab…）与同一标签来源（Qwen3-VL-32B）；(b) 单元标签本身无人类校验，shadow/多 seal 只证明模型输出可复现；(c) 人类独立真值文件 0 行；(d) 项目自评仅 `QUALIFIED_BUT_VALID`，明确"对无条件 superior 主张致命"。因此事件级"K3 更好"的判定存在真实且未被外部真值消除的循环风险；该风险被项目充分披露并限缩了主张，但风险等级本身应判 HIGH（NONE/LOW/MODERATE/HIGH 中取最高档）。单位标签级（VLM 相对）结论的循环性相对较低，但事件级结论完全被 K3 定义层主导。

## f. stdlib 重算结果（复核用户数字）

用纯 `csv/json`（自实现 median/mean，无 numpy/pandas）重算 `materializer_effects.csv` 与 `mechanism_effects.csv`：

| 效应 | cells | median ΔF1（重算） | mean ΔF1 | + / = / − 格 | 用户声称值 | 独立验证（F1_to−F1_from 中位数） |
|---|---:|---:|---:|---|---:|---:|
| K3 vs K0（受控对） | 54 | **0.145652** | 0.183991 | 40 / 14 / 0 | 0.1457 ✓ | —（直接取 Delta_F1） |
| gap-only（C1−C0） | 54 | **0.137703** | 0.173803 | 40 / 14 / 0 | 0.1377 ✓ | 0.137703，Δ 与 F1_to−F1_from 零失配 |
| duration-cap（C2−C1） | 54 | **0.0** | +0.007178 | 10 / 44 / 0 | 0.0 ✓ | 0.0，零失配 |
| negative-barrier（C3−C2） | 54 | **0.0** | +0.003355 | 5 / 49 / 0 | 0.0 ✓ | 0.0，零失配 |
| complex-K3（K3−C3） | 54 | **0.0** | −0.000345 | 0 / 50 / 4 | 0.0 ✓ | 0.0，零失配 |

补充核对：
- `pooled_summary.json`：`median_delta_f1 = 0.145652`，`mean = 0.183991`，`k3_better/equal/worse = 40/14/0`，`valid_controlled_pairs = 54`，`decision = REVISE` —— 与重算完全一致。
- 逐格可加性验证：gap 0.173803 + dur 0.007178 + negbar 0.003355 + K3extras −0.000345 = 0.183991 ≈ K3−K0 mean 0.183991 ✓。
- per-selector：StaticProxyRank median +0.2704（17/18 正）、UniformTemporal +0.1813（14/18 正）、TemporalCoverage +0.0182（9/18 正）——解释 REVISE 判定。
- K3 配置哈希重算 = `7906ab2d…`，与三处冻结声明一致（a 节第 9 点）。

**用户给出的五个中位数全部复核通过（0.1457 / 0.1377 / 0.0 / 0.0 / 0.0），且用 F1_from/F1_to 的独立重推零失配。**

## g. matching.py 模型调用检查

`matching.py` 全部 92 行仅导入 `numpy`、`scipy.optimize.linear_sum_assignment` 与 `.types`。**无任何模型加载（无 transformers/torch/weights）、无网络、无随机源、无文件 IO**；`temporal_iou`、资格矩阵、`linear_sum_assignment` 均为输入事件的确定性函数（`summarize_matches`/`model_relative_event_metrics` 同理）。`run_p0_v3_materializer_validation.py` 的 `metric_row` 只做计数与算术。`matching.py` 确认**纯确定性**；P0/机制消融脚本也只读 parquet/CSV，不调用 oracle 或模型（协议声明 `semantic_oracle_invocations = 0`）。模型调用只存在于引用构造管线 `scripts/run_v10_multiseal_oracle.py`（Qwen3-VL-32B 推理），与本审计的评估器语义无关，且本机未运行。

---

## 主要不确定性 / 审计局限

- 本审计未重跑 parquet 读取（pyarrow 非 stdlib），引用事件数/边界值取自冻结 CSV 与 finalizer 代码逻辑，未逐事件核对 parquet 内容。
- `scipy.optimize.linear_sum_assignment` 的确定性取决于 scipy 版本；就本矩阵规模与整数系数而言结果稳定，但未做跨版本验证。
- 机制消融的归因粒度：`C1−C0` 同时包含"gap 分裂"与"多事件化"两种变化，不能进一步拆解；"gap-only"标签是项目既有命名。

## 报告末尾结构化 JSON

```json
{
  "audit_id": "GVAQP_LOCAL_SCIENTIFIC_AUDIT_MATERIALIZER_REFERENCE_V1",
  "k3_definition": {
    "adapter": "K3UnitEventAdapter (k3_unit_event_adapter.py), frozen config AEQ_MODEL_RELATIVE_K3_V3_1",
    "events_from": "relevant units only; not_relevant/unknown/parse_failure never produce events",
    "merge_rules": {
      "adjacent_gap_0": "merge_adjacent_positive_units=true",
      "gap_0_to_10s": "merge only if exactly <=1 unknown unit fully bridges the gap (bridge_one_fully_covering_unknown_unit_within_maximum_gap)",
      "negative": "hard_barrier",
      "parse_failure": "indeterminate_hard_barrier_not_negative (blocks merge, counted separately)",
      "duration_cap": "group span <= min(40,60)=40s",
      "boundary": "min_positive_unit_start_to_max_positive_unit_end",
      "event_identity": "sha256(query,video,earliest_positive_unit,k3_config)"
    },
    "exact_config_sha256": "7906ab2da20cab7edbe0f379224b60160c7a857cd81ab7f4fec42f54ab9629b9",
    "config_hash_recomputed_stdlib": true
  },
  "c1_definition": "greedy chain merge of queried relevant anchors when adjacent gap <= 10.0s; NO duration cap, NO negative barrier, NO unknown/parse semantics; one VERIFIED_EVENT per group spanning min-to-max (generic_events variant C1_gap_limited)",
  "c0_definition": "all queried relevant anchors become exactly one VERIFIED_EVENT spanning min(start) to max(end); no event if none relevant; identical to P0 K0 (NaiveAllPositiveSpan)",
  "matcher_semantics": {
    "eligibility": "strict_positive_temporal_overlap (tIoU > 0.0 with boundary_tolerance 0.0)",
    "assignment": "1:1 maximum cardinality then maximum total tIoU (score = eligible*1e6 + iou, linear_sum_assignment)",
    "TP_FP_FN": "TP = matched pairs; FP = len(predicted) - TP (unmatched overlapping prediction is FP); FN = len(reference) - TP",
    "event_f1": "harmonic mean of precision TP/len(predicted) and recall TP/len(reference)",
    "tIoU_sensitivity": "sensitivity matcher minimum_tiou=0.30, same 1:1 cardinality logic"
  },
  "reference_construction": "1475 Qwen3-VL-32B-Instruct-FP8 unit labels (multi-seal V9+SEAL_B, cross-seal PASS = model reproducibility only) -> K3UnitEventAdapter.materialize(full grid) with the SAME adapter code and SAME frozen config sha256 7906ab... as the method-side K3 -> K3_MODEL_RELATIVE_EVENT_RELATION.parquet",
  "reference_source_model": "Qwen3-VL-32B-Instruct-FP8 via transformers.Qwen3VLForConditionalGeneration (V10 semantic_contract.model_hash=3febe26ff0cee468bf48dc733e4bca559c8f13f8fe09f931a1e0808ba7c58873)",
  "human_independent_ground_truth_exists": false,
  "human_labels_file": {"path": "outputs/gvaqp_long_horizon_p1_p3_v1/human_reference_package/HUMAN_EVENT_LABELS.jsonl", "lines": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "content_not_read": true},
  "materialization_importance": "LOW_TO_MODERATE",
  "materialization_importance_reason": "real and reproducible within the frozen K3-defined model-relative reference (54 cells, median +0.1457, 40/14/0, decision REVISE), but ~94.5% of the median gain comes from the trivial 10s gap constraint, reference is model-relative and K3-defined, no human ground truth, query-budget not wall-clock",
  "complex_k3_novelty": "NOT_ESTABLISHED",
  "complex_k3_novelty_reason": "K3-vs-C3 unknown/parse/exact marginal: median 0.0, mean -0.00034, 0 positive / 50 equal / 4 negative cells; duration-cap and negative-barrier marginals also median 0.0; all gain attributable to simple gap constraint",
  "reference_circularity_risk": "HIGH",
  "reference_circularity_reason": "reference event relation is built by the same K3 adapter code and same frozen config hash as the method-side K3, over labels from the same Qwen3-VL-32B model; no human independent ground truth exists; project discloses QUALIFIED_BUT_VALID which is fatal to unconditional event-level superiority claims",
  "recomputation_confirmed": true,
  "recomputation": {
    "k3_vs_k0_median_delta_f1": 0.14565222117493926,
    "gap_only_median_delta_f1": 0.1377027474346243,
    "duration_cap_median_delta_f1": 0.0,
    "negative_barrier_median_delta_f1": 0.0,
    "complex_k3_median_delta_f1": 0.0,
    "cells": 54,
    "k3_better_equal_worse": [40, 14, 0],
    "independent_f1to_minus_f1from_mismatch_count": 0,
    "user_claimed_values_confirmed": [0.1457, 0.1377, 0.0, 0.0, 0.0]
  },
  "matching_module_model_calls": "none; pure deterministic (numpy + scipy.optimize.linear_sum_assignment only, no model/weights/network/randomness)"
}
```
