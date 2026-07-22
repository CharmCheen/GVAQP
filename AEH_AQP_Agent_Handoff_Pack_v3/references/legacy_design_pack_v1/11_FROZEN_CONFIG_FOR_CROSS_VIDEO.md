# 11 — Frozen Config for Cross-Video Validation

**状态**：`INCOMPLETE_PRE_CROSS_VIDEO`  
**规则**：所有 `TO_EXTRACT_FROM_CODE` 项未补齐前，不得启动正式 cross-video test。

## 1. BB-EM/K3

| Parameter / mechanism | Value | Provenance | Cross-video change allowed? |
|---|---:|---|---|
| materializer | `K3_gap_duration_negative_barrier` | Stage 0.7 pilot-selected | No |
| `G_max` | 1 unit | Stage 0.7 frozen | No |
| `D_core_max` | 40 s | Stage 0.7 frozen | No |
| `D_seg_max` | 60 s | Stage 0.7 frozen | No |
| queried positive anchors | enabled | semantic core | No |
| queried-negative hard barrier | enabled | Stage 0.6 supported | No |
| proxy-valley barrier | disabled in main method | no independent pilot gain | No |
| duplicate suppression | disabled in main method | no independent pilot gain | No |
| selected expansion | disabled in K3 | K3 chosen over K4 | No |
| unqueried label access | forbidden | protocol | No |

## 2. MAP-anchor-only

以下值必须从 `scripts/stage1a_map_anchor_only.py` 和 run manifest 中提取，而不能凭讨论记录猜测。

| Parameter | Frozen value | Provenance | Status |
|---|---|---|---|
| proxy normalization | `TO_EXTRACT_FROM_CODE` | pilot implementation | BLOCKING |
| high-proxy component threshold | `TO_EXTRACT_FROM_CODE` | pilot implementation | BLOCKING |
| local peak definition | `TO_EXTRACT_FROM_CODE` | pilot implementation | BLOCKING |
| audit window size | `TO_EXTRACT_FROM_CODE` | pilot implementation | BLOCKING |
| nearby-query radius | `TO_EXTRACT_FROM_CODE` | pilot implementation | BLOCKING |
| B≤20 anchor/audit ratio | expected 80/20; verify code | pilot-selected | BLOCKING |
| B≥50 anchor/audit ratio | expected 70/30; verify code | pilot-selected | BLOCKING |
| tie-breaking rule | `TO_EXTRACT_FROM_CODE` | implementation | BLOCKING |
| random seed | `TO_EXTRACT_FROM_CODE` | implementation | BLOCKING |

## 3. MAP-anchor-barrier

| Parameter | Current value | Status |
|---|---|---|
| enable gate | reported `B >= 50` | PILOT-SELECTED, NOT APPROVED |
| barrier target scoring | `TO_EXTRACT_FROM_CODE` | BLOCKING |
| positive barrier semantics | audit required | BLOCKING |
| budget share | `TO_EXTRACT_FROM_CODE` | BLOCKING |

由于 B=100 overcoverage reportedly increased from 1.948 to 2.322 and IoU@0.5 slightly declined, MAP-anchor-barrier 不得进入 cross-video 主方法，除非 lineage forensics 解释并修复。若未解决，cross-video 运行：

```text
MAP-anchor-only + BB-EM
```

而不是 anchor-barrier。

## 4. Baseline config

| Baseline | Rule |
|---|---|
| ARC thresholds | 每个 threshold 独立 selector；阈值必须在 dev 冻结 |
| SUPG variants | 路径审计前均保留；若退化一致则合并并说明 |
| ABae | 固定 strata/allocation adapter |
| Native outputs | 原样评估，不经 common materializer |
| Strengthened outputs | 明确 `+BB-EM`，共享同一 K3 |

## 5. Budgets

```text
B = 5, 10, 20, 50, 80, 100
```

若新视频 units 数量显著不同，应同时报告 absolute budget 与 budget fraction；不得只调整 budget 以提高结果。正式 test 前可预注册一个 normalized budget schedule，之后冻结。

## 6. Metric config

- primary: `event_detection@overlap_any` one-to-one matching；
- secondary: IoU@0.3/0.5、matched mean IoU、duration、overcoverage、overmerge、prediction count；
- efficiency: event-F1 AUC、unique events/query、returned seconds；
- reference only for evaluation。

## 7. Change control

任何修改需新建 `CHANGE_ID`。若修改理由来自 cross-video test 结果，该 test split 失效，必须新增未见视频。
