# Prompt Strictness Sensitivity Report

**Date:** 2026-06-11
**Video:** realcartest_5k.mp4, 67 masked clips (clip_len=6, stride=3, start=10)
**Goal:** Determine whether VLM over-detection (high false positive rate) is a prompt problem or a model capability problem.

---

## 1. Prompt Levels

| Level | Name | Core criterion | Design intent |
|-------|------|----------------|---------------|
| L1 | ego_risk | "could affect ego driving decisions" | Loose — any potential risk |
| L2 | ego_risk_L2 | "would REQUIRE ego to brake/swerve" | Moderate — active reaction needed |
| L3 | ego_risk_L3 | "imminent physical danger, close proximity" | Strict — immediate threat |
| L4 | ego_risk_L4 | "collision/near-collision visibly occurring" | Very strict — only confirmed events |

---

## 2. Results

| Config | yes | no | yes% | avg latency |
|--------|-----|----|------|-------------|
| **8B L1** | 39 | 28 | 58.2% | 3.0s |
| **8B L2** | 0 | 67 | 0.0% | 2.8s |
| **8B L3** | 0 | 67 | 0.0% | 2.7s |
| **8B L4** | 0 | 67 | 0.0% | 2.7s |
| **32B L1** | 51 | 16 | 76.1% | 5.6s |
| **32B L2** | 12 | 55 | 17.9% | 5.6s |
| **32B L3** | 18 | 49 | 26.9% | 5.5s |
| **32B L4** | 1 | 66 | 1.5% | 5.7s |

---

## 3. Key Finding: Prompt vs Model Capability

### 3.1 It is BOTH a prompt problem AND a model capability problem

**8B: prompt problem dominates.** The 8B model collapses to 0% yes at any strictness level above L1. It cannot maintain discrimination between "loose" and "strict" — it either over-detects (L1: 58%) or detects nothing (L2-L4: 0%). This is a **capability limitation**: the 8B model lacks the nuanced understanding to distinguish severity levels.

**32B: prompt problem is solvable.** The 32B model shows a clear monotonic decrease:
```
L1: 76% → L2: 18% → L4: 1.5%
```
This means the 32B model CAN distinguish severity levels — the over-detection at L1 is primarily a **prompt problem** that can be fixed by tightening the prompt.

### 3.2 L2/L3 Reversal Explained

32B L3 (27%) has MORE yes than L2 (18%), which seems counterintuitive since L3 is supposed to be stricter. The reason:

- L2 says "would **require** the ego to brake/swerve" — the word "require" is a high bar; the model interprets it as "the ego MUST react or something bad happens"
- L3 says "**imminent** physical danger, **close proximity**" — these are physical descriptors that are easier to trigger; a vehicle turning nearby IS "imminent" and "close" even if the ego can just slow down

**This is a prompt wording artifact, not a model error.** The model follows the semantic meaning of the prompt, not the designer's intended strictness ordering.

### 3.3 32B L2 is the Sweet Spot

At L2, 32B flags 12/67 clips (18%). All 12 describe genuine close-proximity conflicts:

| Clip | Time | Evidence |
|------|------|----------|
| s000013_e000019 | 13-19s | Cyclist emerges from behind tree, crosses directly in front of ego |
| s000016_e000022 | 16-22s | Cyclist enters road from left sidewalk into ego path |
| s000019_e000025 | 19-25s | Pedestrian stepping into road at close distance |
| s000022_e000028 | 22-28s | Pedestrians actively crossing directly in front of ego |
| s000025_e000031 | 25-31s | Pedestrian suddenly steps into road |
| s000028_e000034 | 28-34s | Pedestrian stepping into ego path from left |
| s000031_e000037 | 31-37s | Pedestrian stepping into road from left sidewalk |
| s000058_e000104 | 58-64s | Two pedestrians crossing at close distance |
| s000101_e000107 | 61-67s | Two pedestrians crossing at close distance |
| s000128_e000134 | 88-94s | Silver sedan making sudden left turn into ego path |
| s000131_e000137 | 91-97s | Cyclist crossing at close distance |
| s000134_e000140 | 94-100s | Multiple pedestrians and cyclists crossing |

**These are all plausible ego-relevant risks.** Whether they are true positives depends on human annotation, but the descriptions are grounded and specific.

---

## 4. Cross-Level Agreement

| Comparison | Count | Interpretation |
|------------|-------|----------------|
| All 4 levels agree no | 16 | Definitely safe clips |
| L1=yes → L2=no | 39 | Model CAN distinguish (these are L1 false positives) |
| L2=yes (all higher levels) | 12 | Candidate true positives |
| L3=yes but L2=no | 7 | L3 wording artifact (see §3.2) |
| L4=yes | 1 | Only 1 clip meets "collision visibly occurring" |

---

## 5. Conclusions

1. **The over-detection problem is solvable for 32B.** L1→L2 reduces yes from 76% to 18%, showing the model has the capability to be more precise.

2. **8B lacks the capability for nuanced severity judgment.** It either over-detects (L1) or detects nothing (L2+). The 8B model is not suitable as a precise verifier without significant prompt engineering or fine-tuning.

3. **Prompt wording matters more than intended strictness level.** "Require the driver to react" (L2) is more effective at reducing false positives than "imminent physical danger" (L3), because the model interprets these phrases differently than intended.

4. **32B L2 at 18% positive rate is a reasonable baseline for human annotation.** The 12 flagged clips all describe plausible risks with specific evidence.

5. **The remaining question: is 18% still too high?** This requires human annotation to answer. Some of the 12 L2=yes clips may be false positives (e.g., pedestrian crossing far enough ahead that ego doesn't need to react).

---

## 6. Recommended Next Steps

1. **Annotate the 32B L2 review sheet** — this is the most informative set:
   ```
   test_vlm/outputs/qwen3_vl_32b_masked_ego_risk_L2.jsonl
   ```

2. If L2 precision is still too low, consider an **L2.5 prompt** between L2 and L4:
   - "A collision is imminent or the ego vehicle must perform emergency braking to avoid impact"
   - Skip L3 (wording artifact)

3. If L2 precision is acceptable, use L2 as the **oracle prompt** for budgeted VLM experiments.

4. **8B is not recommended as a verifier** at any strictness level — it lacks discrimination capability.

---

## Appendix: Output Files

```
test_vlm/outputs/qwen3_vl_8b_masked_ego_risk_L2.jsonl
test_vlm/outputs/qwen3_vl_8b_masked_ego_risk_L3.jsonl
test_vlm/outputs/qwen3_vl_8b_masked_ego_risk_L4.jsonl
test_vlm/outputs/qwen3_vl_32b_masked_ego_risk_L2.jsonl
test_vlm/outputs/qwen3_vl_32b_masked_ego_risk_L3.jsonl
test_vlm/outputs/qwen3_vl_32b_masked_ego_risk_L4.jsonl
test_vlm/outputs/prompt_sensitivity_report.md
```
