# 32B targeted pilot：失败证据与硬门槛附录

本附录只整理 `AEQ_ORACLE_PREFLIGHT_V2` 已完成运行的直接证据，不修改 sealed
实验、原始输出、分析器结果、grounding 结果或最终判决。执行 seal SHA-256 为
`58f84d2ce389aa3cf8122137911b0ec8429d6db80d84766afd88ee870b6b7576`。

## 最短结论

四条决策相关原始输出如下：

| 类型 | 调用 | 32B 输出 | 冻结的 pre-outcome review | 结果 |
|---|---|---|---|---|
| strict parse 失败 | `DALI_u0548_fps4_sensitivity` | `relevant`, 但边界为 17–20 秒 | `DALI_u0548` 为 `relevant` | `invalid_relevant_boundary`，有效标签保留为 `parse_failure` |
| semantic contradiction | `DALI_u0555_fps2_r0` | `not_relevant` | 两位 reviewer 一致为 `relevant` | polarity contradiction |
| semantic contradiction | `HANGZHOU_u0234_fps2_r0` | `relevant` | 两位 reviewer 一致为 `not_relevant` | polarity contradiction；事后 positive-claim grounding 亦为 `UNSUPPORTED` |
| semantic contradiction | `WUHAN_u0217_fps2_r0` | `not_relevant` | 两位 reviewer 一致为 `relevant` | polarity contradiction |

这三个 contradiction 分布在三个视频，超过冻结的 systematic semantic failure
门槛（至少两个 contradiction，且跨至少两个视频）。不过实际 finalizer 的状态优先由
更早发生的 numeric gate 失败决定：32 条中只有 31 条 strict-parse 成功，
`31/32 = 0.96875 < 1.0`。

这里的 `semantic contradiction` 严格采用冻结 analyzer 的定义：32B 的 decided polarity
与两位 agent 在看到新 oracle 输出前达成的 polarity consensus 相反。该 consensus 是
adversarial screen，不是人工 ground truth 或可用于估计 accuracy 的代表性 reference；
contradiction 是必须审查/达到数量门槛时拒绝 protocol 的直接证据，不应被误读为已测得
population error rate。

## 32B 实际收到的输入

每次调用的 user message 由一个预采样 video frame sequence 和下述冻结文本组成。
runner 将 `fps` 元数据设为该调用的 2 或 4，并要求
`process_vision_info(...)= {"do_sample_frames": false}`，所以 processor 不再自行抽帧。

- 2 fps base 或 cross-replica 调用：10 秒闭区间上 21 帧，目标相对时间为
  `0, 0.5, ..., 10.0` 秒。
- 4 fps sensitivity 调用：10 秒闭区间上 41 帧，目标相对时间为
  `0, 0.25, ..., 10.0` 秒。
- 32 次物理调用中有 26 次为 21 帧、6 次为 41 帧，合计向 processor 提交
  `26×21 + 6×41 = 792` 帧。去除同进程 repeat 和 cross-replica 重复后，18 个不同
  的 candidate/rate frame set 合计 498 个 frame occurrences。
- 每个 raw JSON 都保存了每帧的 target time、requested/decoded frame index、
  decoded timestamp 和 RGB content SHA-256；分析器验证这些值与冻结 frame manifest
  完全相等。

这里的“21/41 帧”指实际提交给 `Qwen3VLProcessor` 的离散 RGB 帧序列。运行记录保存了
processor 输出 tensor 的整体 SHA-256，但没有保存内部 temporal padding、视觉 patch 或
视觉 token 的 shape；因此本附录不声称一个未测量的内部 token 数。

抽帧规则是 endpoint-inclusive target grid 上的最近源帧：

```text
relative_target = ordinal / sampling_fps
source_offset = floor(relative_target * video_fps + 0.5)
requested_index = start_frame + source_offset
```

DALI 的源视频名义为 30 fps，但其解码时间戳以毫秒三位记录。因此 4 fps 的
`DALI_u0548` 实际解码时间为：

```text
5480.000, 5480.267, 5480.500, 5480.767, ...,
5489.000, 5489.267, 5489.500, 5489.767, 5490.000 sec
```

这仍对应精确的 0–10 秒、0.25 秒 target grid；约 0.267/0.233 秒的交替来自
30 fps 源帧到 4 fps target 的最近帧映射和时间戳显示精度。

## 冻结的 32B prompt

冻结文件：`outputs/accelerated_event_query_v1/configs/query_prompt_v2.txt`
文件 SHA-256：`39f6d983b4f1499e6be2e73b5badb7949d5f7bc53e59e7eb9047770052cee158`

```text
You are the frozen Qwen3-VL-32B operational oracle for an event-query benchmark.

Inspect this 10-second ego-driving clip and decide whether an attentive ego driver needs a noticeable slowdown, braking action, or avoidance maneuver because of visible conditions within the clip.

Relevant causes may include a road user entering or threatening the ego path, a suddenly slowing or stopped lead vehicle, a traffic control that visibly requires a marked response within this clip, or a visible obstacle or road condition requiring a marked speed or path change. Normal steady driving, ordinary following with no marked response, distant hazards, merely seeing pedestrians or vehicles, and a response completed before the clip are not relevant. Do not infer hidden motion or a future event outside the clip. If only an endpoint frame suggests an event and its timing cannot be established, return unknown.

For a relevant event, event_start_sec is the earliest time in [0, 10] when the visible situation makes the marked response necessary, and event_end_sec is the latest time in [0, 10] when that need remains visible. These are necessity boundaries, not estimates of the ego vehicle's actual pedal or steering actuation. Return unknown if the necessity interval cannot be localized from the supplied frames.

Return exactly one JSON object, with no markdown fence, prefix, suffix, or extra key:
{
  "label": "relevant" | "not_relevant" | "unknown",
  "event_start_sec": number | null,
  "event_end_sec": number | null,
  "required_response": ["slowdown" | "brake" | "avoid"],
  "cause": string | null,
  "confidence": "high" | "medium" | "low",
  "evidence": string,
  "unknown_reason": string | null
}

The fields must satisfy these rules:
- relevant: finite boundaries with 0 <= start <= end <= 10, at least one unique required_response, a nonempty visible cause, nonempty evidence, and unknown_reason null;
- not_relevant: both boundaries null, required_response empty, cause null, nonempty evidence, and unknown_reason null;
- unknown: both boundaries null, required_response empty, cause either null or a nonempty suspected visible cause, nonempty evidence, and a nonempty unknown_reason.

Use unknown rather than guessing when sampling, occlusion, clip boundaries, or temporal context are insufficient. Unknown and malformed output are never negatives.
```

## 实际冻结并执行的 JSON contract

本实验没有另存一份 JSON Schema Draft 文件；权威 contract 是上述 prompt 加 sealed
parser source：
`src/garc_eval/accelerated_event_query/oracle_protocol.py` 和
`src/garc_eval/accelerated_event_query/oracle_response_protocol.py`。

parser 对整个 response string 执行以下约束：

- 必须是单个 JSON object；递归拒绝 duplicate keys。
- key 集合必须**恰好**是
  `label,event_start_sec,event_end_sec,required_response,cause,confidence,evidence,unknown_reason`。
- `label ∈ {relevant, not_relevant, unknown}`；
  `confidence ∈ {high, medium, low}`；response 只能来自
  `{slowdown, brake, avoid}` 且不得重复。
- `relevant`：有限数值且非 boolean 的边界满足
  `0 <= start <= end <= 10`；response 非空；cause/evidence 非空；
  `unknown_reason=null`。
- `not_relevant`：边界均为 null；response 为空；cause 为 null；evidence 非空；
  `unknown_reason=null`。
- `unknown`：边界均为 null；response 为空；cause 为 null 或非空字符串；
  evidence 和 unknown_reason 均非空。
- 任一不满足项保留原始 response，但 effective label 设为 `parse_failure`；不会将其
  重标为 negative 或 unknown。

## 四条原始输出

### 1. Strict parse failure：DALI_u0548_fps4_sensitivity

- raw：`operational_oracle/preflight_v2/raw/DALI/DALI_u0548_fps4_sensitivity.json`
- raw file SHA-256：`279a448c79185d057197a591f3a129989f3976af1c7fac1fe476347cac36d912`
- source window：DALI absolute `[5480.0, 5490.0]` 秒；clip-relative `[0,10]` 秒。
- sampling：4 fps，41 帧；target 为 `0,0.25,...,10` 秒；actual decoded timestamps
  如上节所列。
- frame content：末段 9.0、9.5、10.0 秒帧显示两名行人从右侧进入道路/ego path；
  对应 base 2 fps positive claim 的独立 grounding 为 `SUPPORTED`。这不挽救本条
  4 fps 输出的越界时间。
- contact sheet：`operational_oracle/preflight_v2/contact_sheets/DALI_u0548.png` 只是 2 fps、
  21 帧 base subset 的可视概览，不是本条 4 fps 调用的完整输入。4 fps 的权威 41 帧证据
  是本条 raw JSON 的 `frames` 数组及
  `operational_oracle/preflight_v2/ORACLE_INPUT_FRAME_MANIFEST_V2.json` 中对应的冻结 frame set。

模型原始 response：

```json
{
  "label": "relevant",
  "event_start_sec": 17.0,
  "event_end_sec": 20.0,
  "required_response": ["slowdown", "avoid"],
  "cause": "two pedestrians crossing the road directly in front of the ego vehicle in the middle of the street, requiring a response to avoid collision",
  "confidence": "high",
  "evidence": "At 17.0 seconds, two pedestrians are seen stepping into the road from the right sidewalk, moving across the lane directly in the path of the ego vehicle. They continue to cross the road until 20.0 seconds, remaining in the vehicle's path. The ego vehicle must slow down or maneuver to avoid them, as they are not on a crosswalk and are in the active travel lane.",
  "unknown_reason": null
}
```

观察：JSON 可被语法解析，且 positive cause 大体可见，但 17–20 秒不在当前 10 秒
clip-relative contract 中。strict parser 因此返回 `invalid_relevant_boundary`，并保留
`effective_label=parse_failure`。这是 protocol/timestamp anchoring 失败，不是“无事件”。

### 2. Semantic contradiction：DALI_u0555_fps2_r0

- raw：`operational_oracle/preflight_v2/raw/DALI/DALI_u0555_fps2_r0.json`
- raw file SHA-256：`800f481a61cbeeaa91fc67ed394d57e0bc95f9709af6b76ab4c8069f2740e789`
- source window：DALI absolute `[5550.0, 5560.0]` 秒。
- sampling：2 fps，21 帧；actual decoded timestamps 为
  `5550.0,5550.5,...,5560.0` 秒。
- frame/review description：两位 reviewer 在看到新 32B 输出之前，均把道路中的黄衣
  行人和正前方 scooter 视为需要明显响应；primary 特别记录“行人与 scooter 的贡献不能
  仅凭帧分离”。
- contact sheet：`operational_oracle/preflight_v2/contact_sheets/DALI_u0555.png`。

模型原始 response：

```json
{
  "label": "not_relevant",
  "event_start_sec": null,
  "event_end_sec": null,
  "required_response": [],
  "cause": null,
  "confidence": "high",
  "evidence": "The ego vehicle is driving steadily at night on a multi-lane road with visible traffic flow. There are no sudden changes in traffic, no vehicles abruptly entering the path, no traffic signals requiring immediate response, and no visible obstacles or hazards that would necessitate a slowdown, brake, or avoidance maneuver. Pedestrians are present but at a safe distance and not crossing the path of the ego vehicle. The lead vehicles maintain consistent spacing and speed, and the ego vehicle appears to be following normally without any visible need for a marked response.",
  "unknown_reason": null
}
```

冻结 review consensus 为 `relevant`，模型为 `not_relevant`，故为 decided-polarity
contradiction。r1 与 r0 的 raw-response hash 完全相等，且跨 HANGZHOU/WUHAN replica
的 anchor 输出也完全相等，所以不能用随机性解释该差异。

### 3. Semantic contradiction：HANGZHOU_u0234_fps2_r0

- raw：`operational_oracle/preflight_v2/raw/HANGZHOU/HANGZHOU_u0234_fps2_r0.json`
- raw file SHA-256：`a54dcdd191c9a66c8a11ef06f887f31342a677edefd69107d3a18c7a10a7845c`
- source window：HANGZHOU absolute `[2340.0, 2350.0]` 秒。
- sampling：2 fps，21 帧；actual decoded timestamps 为
  `2340.0,2340.5,...,2350.0` 秒。
- frame/review description：冻结的两位 reviewer 均描述为绿灯控制下跟随白色前车的
  普通多车道行驶，无冲突。事后独立 grounding 逐帧确认 7.5–10.0 秒直行绿箭持续亮，
  红灯控制左转，crosswalk 无人，overlay 仍为绿色倒计时。
- contact sheet：`operational_oracle/preflight_v2/contact_sheets/HANGZHOU_u0234.png`。

模型原始 response：

```json
{
  "label": "relevant",
  "event_start_sec": 8.0,
  "event_end_sec": 10.0,
  "required_response": ["brake"],
  "cause": "The traffic light for the straight-ahead lane turns red, requiring the ego vehicle to stop before the crosswalk.",
  "confidence": "high",
  "evidence": "At 8.0 seconds, the traffic light for the straight-ahead lane changes from green to red. The ego vehicle is approaching the intersection and must brake to stop before the crosswalk, as indicated by the red light and the presence of the pedestrian crossing. The countdown timer on the navigation overlay also shows the green light duration ending around this time, confirming the timing of the signal change.",
  "unknown_reason": null
}
```

冻结 review consensus 为 `not_relevant`，模型为 `relevant`；而独立 claim-grounding
又把该 positive claim 判为 `UNSUPPORTED`。这不仅是阈值边界分歧，模型给出的直行红灯
转换、行人存在和 overlay 解释均被精确帧反证。

### 4. Semantic contradiction：WUHAN_u0217_fps2_r0

- raw：`operational_oracle/preflight_v2/raw/WUHAN/WUHAN_u0217_fps2_r0.json`
- raw file SHA-256：`6540613a42a15c9c9a7b816ed1be7ed03d0978f242502d31928a38883d5ad971`
- source window：WUHAN absolute `[2170.0, 2180.0]` 秒。
- sampling：2 fps，21 帧；actual decoded timestamps 为
  `2170.0,2170.5,...,2180.0` 秒。
- frame/review description：两位 reviewer 在新 32B 输出前均认为约 7–10 秒间，红衣
  对向骑行者在狭窄道路上接近，前车/停放车辆限制 clearance，需要 slowdown/avoid；
  两者也都警告精确 lane geometry 未被测量。
- contact sheet：`operational_oracle/preflight_v2/contact_sheets/WUHAN_u0217.png`。

模型原始 response：

```json
{
  "label": "not_relevant",
  "event_start_sec": null,
  "event_end_sec": null,
  "required_response": [],
  "cause": null,
  "confidence": "high",
  "evidence": "The ego vehicle is driving steadily through an intersection with a green traffic light, following other vehicles. There are no sudden changes in traffic flow, no visible obstacles in the path, and no road users entering or threatening the ego path. The cyclist in red is riding on the left side of the road and is not in the ego vehicle's lane or path. The lead vehicles maintain consistent speed and distance, and no traffic control requires a marked response within the clip. The environment is clear and no visible conditions necessitate a slowdown, brake, or avoidance maneuver.",
  "unknown_reason": null
}
```

冻结 review consensus 为 `relevant`，模型为 `not_relevant`，故为 contradiction。
这里的主要竞争解释确实是“骑行者是否威胁 ego path”的 lane-geometry 判断，而不是
输出格式或采样失败；这也暴露了当前 qualitative query 缺少可测 clearance/kinematic
阈值的问题。

## 额外的 unsupported positive（非上述三个 contradiction）

`WUHAN_u0171_fps2_r0.json` 的模型和冻结 review 都给出 `relevant`，所以它不属于
semantic contradiction；但模型声称信号灯“在 6.0 秒转红”。独立 reviewer 检查精确
4.5、5.0、5.5 秒帧后发现同一信号已为红色，因此把整个冻结 positive claim 判为
`UNSUPPORTED`。这说明 label agreement 也不足以建立 claim adequacy。

## “明显减速、制动或避让”的实际操作化

冻结 query 没有使用速度、加速度、TTC、横向 clearance 或制动踏板的数值阈值。
它采用的是**视觉上必要的 marked response**这一反事实/规范性定义：一个 attentive ego
driver 是否因为当前 10 秒内可见的条件而需要明显改变速度或路径。

操作规则为：

- positive 原因包括进入/威胁 ego path 的 road user、突然减速或停止的 lead vehicle、
  在 clip 内明显要求响应的 traffic control，以及要求 marked speed/path change 的可见
  障碍或道路条件。
- steady driving、无 marked response 的 ordinary following、远处危险、仅仅看到行人或
  车辆、以及在 clip 开始前已完成的响应均排除。
- event boundaries 表示“该明显响应从何时开始变得必要、到何时仍然必要”，不是 ego
  实际踩踏板或转向的时间估计。
- 不得推断隐藏运动或 clip 外未来；sampling、occlusion、边界或 temporal context 不足时
  必须输出 `unknown`，不得猜测。

因此，当前 operation 是可执行但仍是 qualitative 的。三个 semantic contradiction 和
两个 unsupported positive claims（四个 unique positives 中）表明，`noticeable/marked`、
ego-path threat、signal-lane association 和时间锚定还不够可靠。若修订 protocol，最需要
优先测试的是可测量的 ego-path/clearance、traffic-control lane association 和
clip-relative timestamp anchoring，而不是事后改变本次标签或阈值。

## TARGETED_PILOT_DECISION_V2 与硬拒绝条件

最终判决文件
`operational_oracle/preflight_v2/TARGETED_PILOT_DECISION_V2.json` 自身是 write-once 的
decision envelope；它记录 finalizer status、mapping hash、seal hash 和 scope，不重复展开
全部门槛。门槛的权威来源是冻结 preregistration、sealed analyzer/finalizer 和
pre-outcome user mapping。

判决文件内容为：

```json
{
  "decision": "REVISE_ORACLE_PROTOCOL",
  "decision_payload_sha256": "6c9d1c8b5ace55c1bdd1877678b1f1b904b1379cb183b101bdb7423ea47f11ca",
  "execution_seal_sha256": "58f84d2ce389aa3cf8122137911b0ec8429d6db80d84766afd88ee870b6b7576",
  "experiment_id": "AEQ_ORACLE_PREFLIGHT_V2",
  "finalizer_decision_sha256": "cee366f580d7d510d0cd1935310f81e60e301e534c0be4e8b2aa7c98c4afb528",
  "mapping_sha256": "10ed8d9c3ef22e9db4378af5cecee3c03b432706b40958dd11601dca982ae4e8",
  "scope": "Targeted 32-call protocol pilot only; no representative/full-oracle or downstream claim.",
  "source_finalizer_status": "FAIL_NUMERIC_OR_SUPPORT_GATE"
}
```

### 不能形成有效 pass、但不是 protocol hard reject 的条件

1. **Authentication/accounting**：任一 binding/self-hash/raw hash/input identity/frame hash/
   runtime GPU declaration 不符；或不是恰好 32 个 authorized call 各一次 started、completed、
   accepted；或出现 failed/uncertain generation/retry。部分情形会直接 abort，因而不能
   产生有效 finalizer pass。冻结 mapping 将 incomplete/unauthenticated run 映射为
   `INSUFFICIENT_EVIDENCE`，不能把它解释为已证明 protocol 失败。

### 完整、authenticated run 的硬 protocol 拒绝条件

1. **Parse**：strict parse success fraction 必须为 `1.0`。本次为 `0.96875`，已单独构成
   `FAIL_NUMERIC_OR_SUPPORT_GATE`。
2. **Reproducibility**：12/12 same-process pairs 必须有相同 model input 和 raw response；
   三个 cross-replica anchor observation 也必须完全相同。
3. **Class support**：model repeat-consensus 至少有 2 个 relevant clips 且跨至少 2 个视频，
   至少 2 个 not_relevant clips 且跨至少 2 个视频；unknown 总数不超过 4、每视频不超过 2。
4. **2/4 fps sensitivity**：任一 relevant/not_relevant flip 直接失败；两边都为 relevant 时，
   最大 boundary difference 必须不超过 1 秒，response set 必须相同。
5. **Systematic semantic failure**：至少两个 decided-polarity contradiction 且跨至少两个
   视频，状态为 `FAIL_SYSTEMATIC_SEMANTIC_GATE`。本次观测到三个、跨三个视频；只是被
   analyzer 的 numeric-failure precedence 掩盖，没有成为最终 status 字符串。
6. **Claim grounding**：如果前述 analyzer gates 允许进入 grounding，任一 positive claim
   为 `UNSUPPORTED` 就得到 `FAIL_CLAIM_GROUNDING_GATE`。本次四个 unique positive claims
   中有两个 unsupported；同样因 numeric gate 已先失败，finalizer 保留较早的失败状态。

### 只触发 review/证据不足、不是单个硬拒绝的条件

- sensitivity 在 `unknown` 与 decided label 之间转换；
- 少于 systematic threshold 的 decided-polarity contradiction；
- model 为 `unknown` 而冻结 review 为 decided；
- claim review 缺失或为 `INDETERMINATE`。

这些路径映射到 `REVIEW_REQUIRED -> INSUFFICIENT_EVIDENCE`。只有 authentication、numeric/
support 和 semantic gates 全部通过，且所有 positive claims 均被独立判为 `SUPPORTED`，
才可能得到
`TARGETED_ORACLE_PILOT_PASS_REPRESENTATIVE_AUDIT_REQUIRED`。即使该 pass 出现，也只说明
protocol survived targeted pilot，不说明三视频代表性 adequacy，更不授权 1,475-unit run
或任何下游 YOLO/headroom/controller claim。

## 权威证据路径

- prompt：`outputs/accelerated_event_query_v1/configs/query_prompt_v2.txt`
- parser：`src/garc_eval/accelerated_event_query/oracle_protocol.py`
- duplicate-key wrapper：`src/garc_eval/accelerated_event_query/oracle_response_protocol.py`
- frozen gates：`outputs/accelerated_event_query_v1/operational_oracle/PREFLIGHT_V2_PREREGISTRATION.json`
- exact frame manifest：`outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/ORACLE_INPUT_FRAME_MANIFEST_V2.json`
- frozen review consensus：`outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/PRE_OUTCOME_REVIEW_CONSENSUS_V2.json`
- analyzer metrics：`outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/PREFLIGHT_METRICS_V2.json`
- independent grounding：`outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/GROUNDING_REVIEW_V2.json`
- finalizer：`scripts/finalize_accelerated_event_query_oracle_preflight_v2.py`
- final decision envelope：`outputs/accelerated_event_query_v1/operational_oracle/preflight_v2/TARGETED_PILOT_DECISION_V2.json`
