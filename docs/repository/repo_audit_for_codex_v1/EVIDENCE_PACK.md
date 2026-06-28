# Evidence Pack — CASQ / G-ClipAQP

**Generated:** 2026-06-23
**For:** Codex or another model to read before giving research advice.

## 1. Current Research Problem

Design a DB/AQP-style system that:
- Given any candidate generator (cheap proxy, VLM scorer, embedding retriever),
- An expensive oracle (32B VLM or human),
- A budget B, target recall γ, and failure probability δ,
- Returns variable-length clips and a **conservative clip-level recall certificate**.

The core contribution is **proxy-agnostic statistical guarantees** — not better driving-event proxy design.

## 2. Current Query Predicate

```
O_enter_ego_path_v0
```
An object starts outside/near the ego vehicle's future path, then enters or overlaps it, creating potential spatial conflict requiring ego attention.

## 3. Current Benchmark/Reference Status

| Asset | Status | Scope |
|---|---|---|
| **V13.8 Full Center10 Oracle** | ✅ Ready | 399 anchors, 94 positive, 51 stitched events, 0% abstain |
| V13.5 Pilot Labels | Available | 100 pilot clips, 18% positive (old prompt), 66% abstain |
| V13.6 Construction Sensitivity | Available | 416 VLM calls, center_10s beats fixed_5s |
| V13.7 Multi-Method Replay | Available (superseded) | Labeled-subset biased, proxy performance inflated |
| V13.9 Static Evaluation | Available | Full-oracle evaluation, proxy methods fail at low budgets |
| V13.10 Oracle Upper Bound | Available | OracleBest@B curve, efficiency ratios, adaptive fails |
| Nexar-200 Derived-Boundary | Available (unreliable) | LOOSE_APPROXIMATION / AUDIT_UNRELIABLE for O_enter_ego_path_v0 |
| Micro-CASQ v1 32B Benchmark | Available (underpowered) | 38 eligible positives, sampled from candidate pools |
| Human-Adjudicated Labels | **Not available** | None exist |

## 4. What Has Been Validated

1. **V13.6:** center_10s anchor construction beats fixed_5s — halved VLM calls (399 vs 798), 26% more positives, 0% abstain with repaired prompt.

2. **V13.8:** Full center10 oracle reference successfully constructed — 399/399 VLM calls, 94 positive anchors, 51 stitched events, 100% complete events, 0% truncation.

3. **V13.9/V13.10:** OracleBest@B curve established — B=5→0.098, B=10→0.196, B=20→0.392, B=40→0.784, B=80→1.000. Every anchor→exactly 1 event (simple upper bound).

4. **Prompt repair (V13.5→V13.6):** "Normal driving must be labeled negative, not abstain" fixed the 66%→0% abstain problem.

5. **Event completeness:** All O_enter_ego_path_v0 events in realcartest fit within 10s windows — 100% complete_event_visible, 0% truncation.

6. **Adaptive search assessed:** Both priority-boost and bidirectional-expand mechanisms were evaluated across 3 base scores, 5 budgets, 3 window widths. Adaptive never beats static.

## 5. What Has Failed

1. **Cheap proxy features are too weak for budgeted AQP:** YOLO vehicle counts + motion energy achieve 0.350 efficiency at B=20 (only 35% of OracleBest). Proxy advantage over random at B=20 is only +0.059 — below the +0.10 threshold.

2. **Adaptive search doesn't help:** Adding spatial/temporal locality to proxy scores (boost neighbors, expand bidirectionally) hurts same-base static performance at 11/15 budget×base combinations.

3. **V13.7 labeled-subset was biased:** 25% high-YOLO samples inflated proxy performance by ~3× compared to unbiased full-oracle evaluation.

4. **Nexar-200 external labels are unreliable:** 16% positive agreement with O_enter_ego_path_v0. Cannot support oracle-relative claims.

5. **Micro-CASQ certificate underpowered:** 38 eligible positives insufficient for non-vacuous certificate (~500+ events needed per Phase 0.6 power simulation).

## 6. What Remains Uncertain

1. Whether a representation-based proxy (CLIP/SigLIP embeddings) would provide enough signal for budgeted event recovery.

2. Whether an 8B VLM cascade (8B as first-pass scorer, 32B for refinement) could achieve meaningful budget reduction.

3. Whether the results generalize beyond realcartest.mp4 (single 66-minute dashcam video).

4. Whether ego-path-conditioned geometric features (lane estimation + object trajectory intersection) would outperform raw vehicle counts.

5. Whether the VLM oracle (Qwen3-VL-32B) is stable enough for eventual human-truth comparison — no human labels exist to calibrate against.

## 7. Which Numbers Are Safe to Cite

| Number | Value | Source |
|---|---|---|
| Full oracle anchors | 399 | V13.8 |
| Positive anchors | 94 (23.6%) | V13.8 |
| Stitched events | 51 | V13.8 |
| Abstain rate with V13.6 prompt | 0% | V13.8 |
| Complete event rate | 100% | V13.8 |
| OracleBest@B=20 | 20/51 = 0.392 | V13.10 |
| Best static efficiency at B=20 | 0.350 (uniform) | V13.10 |
| Best static efficiency at B=40 | 0.275 (top_fusion_geometry_motion) | V13.10 |
| center_10s vs fixed_5s recall improvement | 56% vs 44% positive rate | V13.6 |
| Full center10 scan runtime | ~74 min (399 calls, 32B) | V13.8 |

All numbers are VLM_ORACLE_RELATIVE, single-video (realcartest.mp4, 66.5 min).

## 8. Which Numbers Should Not Be Cited Yet

1. V13.7 labeled-subset recall numbers (biased sampling)
2. V13.9 event_recall_iou_0p3 or event_recall_iou_0p5 (always 0.0, not a useful metric)
3. Nexar-200 derived-boundary recall as "oracle-relative recall"
4. Any "human-truth recall" number (none exist)
5. Any generalization claim beyond realcartest.mp4

## 9. Recommended Next Analysis Targets

1. **Representation-based proxy:** Install CLIP or SigLIP, compute embeddings for all 399 center10 anchors, evaluate whether embedding similarity to known conflict scenes improves proxy ranking.

2. **8B VLM cascade simulation:** If 8B labels exist for any subset, simulate a two-stage cascade (8B first pass → 32B refinement) to estimate budget savings.

3. **Second video validation:** Run center10 oracle on one additional diverse driving video to test whether the 23.6% positive rate and 0% abstain rate generalize.

4. **Do NOT run certificate simulation** until a working budgeted query plan exists (event_recall at useful budgets is too low).

5. **Do NOT claim AQP feasibility** based on current proxy results — the evidence shows cheap handcrafted proxies are insufficient.
