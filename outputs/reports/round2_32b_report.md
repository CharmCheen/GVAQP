# Round 2 Report — Qwen3-VL 8B vs 32B on ego-risk detection

**Date:** 2026-06-11
**Video:** realcartest_5k.mp4 (208s, 1920×1080)
**Clip settings:** clip_len=6, start=10, stride=3 → **67 clips**
**Prompt:** ego_risk (strict: only label yes if risk could force ego to react)
**fps:** 1.0

---

## 1. Execution Summary

| Metric | 8B raw | 8B masked | 32B raw | 32B masked |
|--------|--------|-----------|---------|------------|
| Total clips | 67 | 67 | 67 | 67 |
| JSON OK | 67/67 (100%) | 67/67 (100%) | 67/67 (100%) | 67/67 (100%) |
| Runtime errors | 0 | 0 | 0 | 0 |
| Parse errors | 0 | 0 | 0 | 0 |

### Latency (excluding cold-start first clip)

| Metric | 8B raw | 8B masked | 32B raw | 32B masked |
|--------|--------|-----------|---------|------------|
| Mean | 3.01s | 3.02s | 5.52s | 5.55s |
| Median | 2.99s | 3.01s | 5.45s | 5.56s |
| Min | 2.62s | 2.60s | 3.95s | 4.91s |
| Max | 3.86s | 3.90s | 6.40s | 6.20s |
| Cold-start | 8.78s | 11.57s | 17.36s | 12.86s |

**32B is ~1.85× slower than 8B** (5.5s vs 3.0s per clip).

---

## 2. Relevant Distribution

| vlm_relevant | 8B raw | 8B masked | 32B raw | 32B masked |
|--------------|--------|-----------|---------|------------|
| yes | 27 (40%) | 39 (58%) | 41 (61%) | 51 (76%) |
| no | 40 (60%) | 28 (42%) | 26 (39%) | 16 (24%) |

### Risk level distribution (32B raw)

| risk_level | count |
|------------|-------|
| none | 26 |
| low | 1 |
| medium | 39 |
| high | 1 |

### Risk type distribution (32B raw)

| risk_type | count |
|-----------|-------|
| normal_driving | 26 |
| pedestrian_or_bike_conflict | 19 |
| near_collision | 10 |
| cut_in | 6 |
| sudden_braking | 4 |
| abnormal_lane_change | 2 |

### Temporal distribution of yes (32B raw)

| Time range | yes count | Content |
|------------|-----------|---------|
| 10–40s | 10 | Urban intersection, pedestrians, cyclists |
| 40–70s | 9 | Parking lot, pedestrians nearby |
| 70–100s | 10 | Urban traffic, mixed road users |
| 100–130s | 5 | Transition area |
| 130–160s | 0 | Clear highway driving |
| 160–190s | 6 | Highway with surrounding traffic |
| 190–210s | 1 | End of video |

**The temporal distribution is sensible:** high positive rate in pedestrian/urban zones (10–100s), zero in clear highway (130–160s), moderate in mixed traffic (160–190s).

---

## 3. Raw vs Masked Comparison

| Model | Agree | Disagree | raw=yes masked=no | raw=no masked=yes |
|-------|-------|----------|-------------------|-------------------|
| 8B | 55 (82.1%) | 12 (17.9%) | 0 | 12 |
| 32B | 53 (79.1%) | 14 (20.9%) | 2 | 12 |

**Key finding:** Masking **increases** the positive rate. Almost all disagreements are `raw=no → masked=yes`. This means:
- The black bars do NOT reduce detection capability
- Masking may remove contextual cues (subtitles, timestamps) that previously helped the model say "no" with confidence
- Or: the black bars create a visual artifact that the model interprets as "unusual" → triggers risk detection

**There is no evidence of subtitle leakage causing false positives in raw.** If subtitles were leaking, we'd expect `raw=yes > masked=yes` (subtitles adding false positives). The opposite is true.

---

## 4. Typical Cases

### 32B raw — YES cases

| Clip | Time | Risk | Level | Ego | Evidence |
|------|------|------|-------|-----|----------|
| s000010_e000016 | 10–16s | pedestrian_or_bike_conflict | medium | stopped | "pedestrian crossing road directly in front of ego vehicle" |
| s000013_e000019 | 13–19s | pedestrian_or_bike_conflict | medium | stopped | "cyclist rapidly crosses front of ego vehicle from right to left" |
| s000140_e000146 | 100–106s | near_collision | medium | moving | "pedestrian with umbrella and cyclist with delivery box crossing intersection" |
| s000240_e000246 | 160–166s | cut_in | medium | moving | "vehicle ahead abruptly changes lane into ego's lane" |

### 32B raw — NO cases

| Clip | Time | Risk | Level | Ego | Evidence |
|------|------|------|-------|-----|----------|
| s000052_e000058 | 52–58s | normal_driving | none | stopped | "ego vehicle stationary in parking area, no conflict" |
| s000155_e000201 | 115–121s | normal_driving | none | moving | "moving steadily in clear lane, no obstacles" |
| s000201_e000207 | 121–127s | normal_driving | none | moving | "driving straight, no sudden maneuvers" |
| s000301_e000307 | 181–187s | normal_driving | none | moving | "steady highway driving, no conflicts" |

**Evidence quality is high.** Descriptions are grounded in visual content, not hallucinated. The model correctly distinguishes urban pedestrian zones from clear highway.

---

## 5. Subtitle Leakage Analysis

**No clear evidence of subtitle leakage.** Specifically:
- The ego_risk prompt explicitly says "IGNORE all on-screen text"
- The positive rate is HIGHER in masked (no text visible) than raw (text visible)
- If subtitles were leaking risk descriptions, raw should have MORE positives, not fewer
- The temporal distribution of positives matches actual scene content (pedestrians in 10–100s, clear road in 130–160s)

**However:** The higher positive rate in masked is suspicious and needs human annotation to confirm whether masking causes more false positives or whether raw has false negatives.

---

## 6. 8B vs 32B Comparison

| Aspect | 8B | 32B |
|--------|-----|-----|
| Positive rate (raw) | 40% | 61% |
| Positive rate (masked) | 58% | 76% |
| Avg latency | 3.0s | 5.5s |
| Risk types used | normal_driving, pedestrian_or_bike_conflict, cut_in, abnormal_lane_change | + near_collision, sudden_braking |
| Risk levels used | none, low, medium | + high |
| ego_motion detection | 6 moving, 6 stopped (raw) | 57 moving, 10 stopped (raw) |

**32B is more sensitive** (higher positive rate), uses more granular risk types (near_collision, sudden_braking), and is better at detecting ego motion state (more stopped detections in parking areas).

---

## 7. Research Implications

### Cost analysis
- 8B: 67 clips × 3.0s = **201s** (~3.4 min)
- 32B: 67 clips × 5.5s = **369s** (~6.1 min)
- For a 1-hour video at stride=3s: ~1200 clips → 8B: ~60 min, 32B: ~110 min
- **Full scan is expensive**, confirming budgeted VLM motivation

### Observations without human labels
- The ego_risk prompt produces **more conservative** results than general_risk (round1 had only 10% positive on same video with 8B)
- The temporal distribution of positives matches plausible scene content
- Both models agree on the "safe zone" (130–160s: clear highway) → suggests they understand scene context
- 32B detects more nuance (risk levels, ego motion) but at 1.8× cost

### What we CANNOT conclude
- ❌ Precision/recall without human labels
- ❌ Whether 32B's higher positive rate is better recall or more false positives
- ❌ Whether masking helps or hurts accuracy

---

## 8. Next Steps

### Immediate (you)
1. **Annotate the 32B raw review sheet** — this is the most informative one:
   ```
   test_vlm/outputs/qwen3_vl_32b_round2_5k_raw_fps1_review.csv
   ```
   Set `human_label` to 0 or 1 for each clip.

2. **Re-run eval after annotation:**
   ```bash
   conda activate garc
   python test_vlm/scripts/eval_vlm_results.py \
     --pred test_vlm/outputs/qwen3_vl_32b_round2_5k_raw_fps1.jsonl
   ```

3. **Check disagreement cases** — the 14 clips where raw≠masked in 32B:
   ```
   test_vlm/outputs/compare_32b_raw_vs_masked.csv
   ```
   These are the most informative for understanding masking effects.

### Short-term
4. Annotate 8B raw review sheet for direct 8B vs 32B comparison on same labels
5. FPS sensitivity test: run same clips at fps=0.5 and fps=2.0
6. Test on `realcartest.mp4` (66 min) to verify scalability

### Medium-term
7. Design cheap proxy (frame-diff / optical flow) → VLM candidate pipeline
8. Compute recall vs VLM budget tradeoff

---

## Appendix: Output Files

```
test_vlm/outputs/
  qwen3_vl_8b_round2_5k_raw_fps1.jsonl          # 8B raw results
  qwen3_vl_8b_round2_5k_masked_fps1.jsonl        # 8B masked results
  qwen3_vl_32b_round2_5k_raw_fps1.jsonl          # 32B raw results
  qwen3_vl_32b_round2_5k_masked_fps1.jsonl        # 32B masked results
  qwen3_vl_8b_round2_5k_raw_fps1_review.csv      # 8B raw review sheet
  qwen3_vl_8b_round2_5k_masked_fps1_review.csv    # 8B masked review sheet
  qwen3_vl_32b_round2_5k_raw_fps1_review.csv      # 32B raw review sheet
  qwen3_vl_32b_round2_5k_masked_fps1_review.csv    # 32B masked review sheet
  compare_8b_raw_vs_masked.csv                     # 8B disagreement analysis
  compare_32b_raw_vs_masked.csv                    # 32B disagreement analysis
  round2_32b_report.md                             # this file
```
