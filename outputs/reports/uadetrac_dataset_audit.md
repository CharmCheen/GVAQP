# UA-DETRAC Dataset Audit Report

Generated: 2026-05-22

---

## 1. Dataset Overview

- **Source**: https://huggingface.co/datasets/abhineet123/ua_detrac
- **License**: CC-BY-4.0
- **Original paper**: https://arxiv.org/abs/1511.04136
- **Total sequences**: 100
- **Total frames**: ~140,131
- **Resolution**: 960x540 (typical)
- **Frame rate**: 25 fps
- **Scene type**: Traffic surveillance cameras (overhead/side-mounted)

---

## 2. Selected Subset

**Sequences extracted**: 8

| Sequence | Frames | Duration | Positive Frames | Positive Rate |
|----------|--------|----------|-----------------|---------------|
| MVI_20032 | 437 | 17.4s | 13 | 3.0% |
| MVI_20033 | 784 | 31.3s | 299 | 38.1% |
| MVI_20051 | 906 | 36.2s | 0 | 0.0% |
| MVI_40172 | 2,635 | 105.4s | TBD | TBD |
| MVI_40191 | 2,495 | 99.8s | TBD | TBD |
| MVI_40241 | 2,320 | 92.8s | TBD | TBD |
| MVI_40192 | 2,195 | 87.8s | TBD | TBD |
| MVI_40992 | 2,160 | 86.4s | TBD | TBD |
| **Total** | **13,932** | **557.1s** | **1,519** | **10.9%** |

Positive rates are with count_car >= 25 (YOLOv8x oracle).

---

## 3. Temporal Continuity

All sequences have **perfect temporal continuity**:
- Frame indices are consecutive (gap = 1.0 for all sequences)
- No missing frames
- Timestamps are monotonically increasing
- 25 fps constant frame rate

This is ideal for clip-level evaluation.

---

## 4. Vehicle Density

- **Proxy model**: YOLOv8n
- **Oracle model**: YOLOv8x
- **Proxy score range**: [0.000, 0.974]
- **Proxy score unique**: 13,912 / 13,932 (99.9%)
- **Oracle count range**: 0 to ~50+ cars per frame

The proxy score has excellent granularity (nearly all unique values), which enables fine-grained SUPG threshold selection.

---

## 5. Positive Rate Analysis

With count_car >= 25:
- **Positive rate**: 10.9% (1,519 / 13,932)
- **GT clips**: 126 temporal events
- **Mean clip duration**: 0.32s
- **Short clips dominate**: 61.9% of clips are < 0.2s

The positive rate is in the ideal range for SUPG experiments (5-20%).

---

## 6. Proxy-Oracle Correlation

- YOLOv8n (proxy) and YOLOv8x (oracle) are both YOLO models of different sizes
- Proxy scores correlate well with oracle counts
- The proxy is "strong" — this may underestimate the frame-to-clip gap

---

## 7. Suitability Assessment

| Criterion | Requirement | Status |
|-----------|-------------|--------|
| N (sampled frames) | >= 10,000 | **YES** (13,932) |
| Positive frame rate | 1%-20% | **YES** (10.9%) |
| Continuous timestamps | Required | **YES** (perfect) |
| GT clips | >= 10 events | **YES** (126) |
| Traffic/road scenes | Preferred | **YES** |
| Public availability | Required | **YES** |
| Resolution | >= 480p | **YES** (960x540) |
| Non-vacuous SUPG-RT | Required | **YES** (with budget=1000) |

**Verdict**: UA-DETRAC is **SUITABLE** for clip-level retrieval experiments.

---

## 8. Limitations

1. **Short clips**: Mean 0.32s. Longer events (10+ seconds) would stress-test the gap more.
2. **Strong proxy**: YOLOv8n is a good proxy for YOLOv8x. Weaker proxies would show larger gaps.
3. **Single camera angle**: Surveillance overhead view. Different from dashcam (BDD100K).
4. **No annotations**: Using YOLO pseudo-oracle, not human ground truth.
5. **Subset only**: 8 of 100 sequences extracted. Full dataset would provide more diversity.

---

*Generated: 2026-05-22*
