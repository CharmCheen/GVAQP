# Open Questions and Risks — CASQ / G-ClipAQP

## Methodological Risks

| Risk | Evidence | Severity | Recommendation |
|---|---|---|---|
| **Single-dataset scope** — all V13 results are from one 66-min dashcam video (realcartest.mp4) | V12.1 Section 30 requires second dataset before general claims; no second dataset exists | **HIGH** | Run center10 oracle on at least one additional diverse driving video before any general claim |
| **No human-adjudicated labels exist** — all "positives" are VLM-oracle-relative | Zero human-adjudicated event boundary labels in any benchmark | **HIGH** | Build small (20-50 clip) human-adjudicated set for VLM calibration before claiming oracle-relative → human-truth mapping |
| **Proxy features too weak for budgeted AQP** — YOLO vehicle counts + motion energy achieve 0.350 efficiency at B=20 | V13.9/V13.10: proxy delta vs random at B=20 is only +0.059 | **HIGH** | Test representation-based proxy (CLIP/SigLIP) or 8B VLM cascade before concluding AQP infeasible |
| **Adaptive search degrades performance** — adding spatial/temporal locality hurts same-base static at 11/15 combos | V13.10 sensitivity addendum | **MEDIUM** | If better proxy features are found, re-test adaptive mechanisms; current failure may be proxy-specific |
| **VLM oracle stability unknown** — no same-clip disagreement rate measured for V13.8 oracle | No stability audit exists for the 399-anchor run | **MEDIUM** | Run 10-20 repeated VLM calls on same clips to measure label flip rate |
| **Certificate simulation never attempted on valid oracle** — V13.8 oracle exists but no certificate run | Certificate blocked by "no working budgeted query plan" | **LOW** | Only attempt certificate after finding a method with useful event_recall at modest budget |

## Metric-Definition Risks

| Risk | Evidence | Severity | Recommendation |
|---|---|---|---|
| **event_recall_overlap vs event_recall_direct_discovery** — V13.9 used temporal overlap; V13.10 used anchor→event mapping | V13.10 mismatch analysis: 93 "mismatches" were field-comparison bug, 0 semantic difference found | **LOW (resolved)** | Both definitions produce identical results on this dataset; document the equivalence |
| **event_recall_iou_0p3 always 0.0** — 10s anchor windows vs ~5s events rarely achieve IoU≥0.3 | V13.9 results table shows all zeros | **LOW (known)** | Use event_recall_overlap as primary; IoU metrics are not suitable for anchor-level evaluation |
| **positive_anchor_recall ≠ event_recall** — 94 positive anchors ≠ 51 events; some events span multiple anchors | V13.8 stitching: 94 positives → 51 events | **MEDIUM** | Always specify which recall metric is being reported; prefer event_recall for AQP claims |

## Single-Dataset Risks

| Risk | Evidence | Severity | Recommendation |
|---|---|---|---|
| **realcartest.mp4 may not be representative** — 66-min Chinese urban dashcam, packed by Bilibili XCoder | Video encoding, scene types, traffic patterns unknown relative to general dashcam distribution | **HIGH** | Characterize video content (urban/highway split, traffic density, weather) before generalization |
| **23.6% positive rate may not generalize** — 94 positives in 399 anchors on this specific video | No second video exists to compare | **MEDIUM** | The rate could be 5% or 50% on another video; affects budget sizing |
| **0% abstain rate may be video-specific** — good visibility throughout this video | No challenging-conditions clips tested (night, rain, fog) | **MEDIUM** | Test the V13.6 prompt on a video with poor visibility to stress-test abstain rate |

## Oracle-Label Risks

| Risk | Evidence | Severity | Recommendation |
|---|---|---|---|
| **32B VLM is not a true oracle** — Qwen3-VL-32B may have systematic biases (e.g., over-detecting pedestrians, under-detecting subtle cut-ins) | No calibration against human labels or a stronger model | **MEDIUM** | Cross-validate 10% of V13.8 positives with a different VLM or human review |
| **VLM-oracle-relative ≠ human-truth-relative** — all claims must be qualified | V12.1 Section 9.9: oracle roles; V13.5 Section 0: label all as VLM_ORACLE_RELATIVE | **HIGH** | Never drop the VLM_ORACLE_RELATIVE qualifier without human calibration |
| **Event boundary accuracy unknown** — VLM-reported event_start/event_end may be ±2s off from true boundaries | No boundary-error measurement exists | **MEDIUM** | Run 2s refinement VLM on 10 positive anchors to estimate boundary variance |

## AQP-Contribution Risks

| Risk | Evidence | Severity | Recommendation |
|---|---|---|---|
| **Work drifting toward video understanding engineering** — proxy design, VLM cascade, representation learning all are perception tasks, not DB/AQP | V12.1 Section 25 warns against this drift; V13.9/10 results show proxy quality is the bottleneck | **HIGH** | Frame contributions as: "Given any candidate generator (even a weak one), can the system provide statistical guarantees?" — not "build a better candidate generator" |
| **Statistical guarantee layer untested** — certificate simulation was underpowered in V12.1, never run on V13.8 | No working certificate exists | **HIGH** | A minimal certificate simulation (B1 no-repair) on V13.8 oracle would validate the core AQP contribution even if recall is low |
| **Proxy-agnostic claim weakened** — if only representation-based proxies work, the claim becomes "works with good embeddings" not "works with any proxy" | Current cheap proxies fail; representation candidate not tested | **MEDIUM** | Test multiple proxy types (cheap, representation, 8B cascade) to demonstrate proxy-agnostic property |

## Engineering Risks

| Risk | Evidence | Severity | Recommendation |
|---|---|---|---|
| **Git push blocked** — SSH key and HTTPS credentials unavailable | Last push attempt failed with Permission denied (publickey) | **LOW** | Configure git credentials or use a token |
| **Resumability of long VLM runs** — V13.6 (416 calls) and V13.8 (399 calls) scripts are resumable; future runs should follow the pattern | Scripts check for existing output before processing | **LOW** | Maintain the resumable pattern in all future VLM inference scripts |
| **GPU availability** — A800 (80GB) used for all runs; if unavailable, 8B model on smaller GPU is fallback | All experiments log GPU name and peak memory | **LOW** | Document GPU requirements in run manifests |
