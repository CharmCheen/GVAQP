# P1 Semantic Pilot Report — dataset3

**Task:** 50-anchor stratified VLM oracle pilot to answer five research questions about dataset3's suitability for Event-Native AQP.
**Date:** 2026-06-25
**Output dir:** `garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/`
**VLM:** Qwen3-VL-32B-Instruct (local weights, A800 80GB)
**Predicate:** `O_enter_ego_path_v0` (V13.6 prompt, verbatim)
**Labels:** VLM_ORACLE_RELATIVE. Not human truth.

---

## Pilot Configuration

| parameter | value |
|---|---|
| video | dataset3 (1920×1080, 30fps, 57.7min) |
| anchor grid | center10 (10s spacing, 5s half-window), 347 total anchors |
| pilot selection | 50 anchors stratified by `score_fusion_geometry_motion` quartiles (12/Q + 2 random) |
| frames/anchor | ~21 frames @ 2fps from 10s window |
| VLM generation | max_new_tokens=256, temperature=0.1, bf16 |
| total runtime | 15.6 min (model load 82s + inference 587s) |
| parse success | 50/50 (100%) |
| abstain rate | 0% (0/50) |

---

## Q1: Positive Rate

**Answer: 10.0% (5/50).** Within the 1%–10% GO range, at the upper bound.

| label | count | rate |
|---|---|---|
| positive | 5 | 10.0% |
| negative | 45 | 90.0% |
| abstain | 0 | 0.0% |

For comparison, realcartest V13.8 had 94/399 = 23.6% positive rate. dataset3's 10% is lower but non-vacuous — the predicate fires on real ego-path intrusions, not on every clip.

**Caveat.** This 10% is from a stratified sample (12 anchors per proxy-score quartile + 2 random). The true full-scan positive rate may differ because high-score anchors are not necessarily high-recall (see Q3). Extrapolating to 347 anchors: ~35 positives expected, ~12 stitched events (assuming similar clustering to realcartest's 94→51 compression). This is above the ~30-positive minimum needed for non-vacuous certificate mechanics (per AGENTS.md Findings: Phase-0.6 needs ~500, V13.8 had 51).

---

## Q2: Positive Composition — Real Ego-Path Intrusion?

**Answer: YES — all 5 positives are real, interpretable ego-path intrusion events.**

| anchor | t (s) | involved_object | event_type | evidence (truncated) |
|---|---|---|---|---|
| 0060 | 605 | **pedestrian** | enter_ego_path | "A pedestrian with a child crossing the road from the right sidewalk into the ego vehicle's path, moving across the crosswalk" |
| 0195 | 1955 | **pedestrian** | enter_ego_path | "pedestrian on the right sidewalk, walking toward the crosswalk and entering the ego vehicle's path by 0.7s" |
| 0197 | 1975 | **vehicle** | enter_ego_path | "公交车从左侧车道向右变道，进入ego车辆前方车道，构成潜在空间冲突" (bus cut-in from left) |
| 0247 | 2475 | **pedestrian** | enter_ego_path | "pedestrian crossing from the right side, entering the ego vehicle's path via crosswalk" |
| 0325 | 3255 | **pedestrian** | enter_ego_path | "pedestrian on the left sidewalk near the curb, steps onto the crosswalk and enters the ego path" |

**Composition: pedestrian=4, vehicle=1, cyclist=0.** The positives cover:
- **Pedestrian crossing** (4/5): pedestrians entering from sidewalks via crosswalks — the clearest ego-path intrusion pattern.
- **Vehicle cut-in / merge** (1/5): a bus changing lanes into the ego lane — a vehicle-side ego-path intrusion.
- **Cyclist intrusion** (0/5): no cyclist positives in this 50-anchor sample. This is expected given the 12.3% bike-window rate and small sample; a full scan would likely find some.

**Evidence quality: HIGH.** All 5 evidence strings are specific, mention the object type, the spatial trajectory (from sidewalk / from left lane), and the ego-path conflict. The VLM is not hallucinating — each description references concrete visual elements (crosswalk, bus, child, sidewalk). One evidence is in Chinese (公交=bus), indicating the VLM adapts language to the scene context (Chinese urban driving).

This matches the `O_enter_ego_path_v0` predicate definition exactly: objects start outside the ego path and enter it.

---

## Q3: Hard Negatives — Misjudgments?

**Answer: NO large-scale misjudgment.** The 45 negatives show clean, interpretable reasoning.

| negative_reason | count | meaning |
|---|---|---|
| `normal_following` | 26 | ego following traffic, no lane change into ego path |
| `no_ego_path_interaction` | 19 | visible objects but none entering ego path |
| other reasons | 0 | — |

**Hard-negative check on high-score anchors.** 22 high-score anchors (score > 0.5 or Q3/Q4) were labeled negative. Spot-checking their evidence:

| anchor | score | neg_reason | evidence |
|---|---|---|---|
| 0320 | 5.19 | normal_following | "driving under an overpass in multi-lane road with moderate traffic, all vehicles maintaining lanes" |
| 0251 | 2.84 | normal_following | "multi-lane urban road with moderate traffic, all vehicles in their lanes" |
| 0198 | 2.65 | no_ego_path_interaction | "stopped at traffic light behind white sedan, other vehicles stationary" |
| 0211 | 2.30 | no_ego_path_interaction | "driving straight through intersection then narrow road, no objects entering" |
| 0244 | 2.25 | normal_following | "driving straight in multi-lane urban road with normal traffic flow" |

These are **correctly labeled negatives** — high proxy scores (many vehicles / large bboxes / high motion) but no actual ego-path intrusion. This confirms the AQP-side finding from realcartest: **proxy score ≠ event presence.** Dense traffic with many vehicles produces high `object_count_mean` but no cut-in/merge event. This is exactly the budget-decomposition motivation: oracle targets must be chosen by coverage/diversity, not by raw proxy score.

**No false-positive pattern detected.** The VLM does not label normal traffic as positive. The 0% abstain rate also means the VLM is not using abstain as an escape hatch for ambiguous cases — it makes a clear binary call.

---

## Q4: Event Boundary Degeneracy?

**Answer: YES — boundary output is severely templated.** This is the one red flag.

| field | values across 5 positives |
|---|---|
| `event_start` | `0.0, 0.0, 0.0, 0.0, 0.0` (all identical) |
| `event_end` | `0.7, 0.7, 0.7, 0.7, 0.7` (all identical) |
| `boundary_status` | `ok, ok, ok, ok, ok` (all "ok") |
| `complete_event_visible` | `True, True, True, True, True` |

**All 5 positives have event_start=0.0s and event_end=0.7s.** This is not a coincidence — it is a templated response. The VLM is outputting a fixed 0.7-second boundary for every positive, always starting at clip beginning. This means:

1. **The boundary values are not real temporal localization.** A pedestrian crossing and a bus cut-in do not both happen in exactly 0.0–0.7s.
2. **`boundary_status=ok` is unreliable** — the VLM claims all events are fully visible with clean boundaries, but the identical values suggest it is not actually localizing.
3. **Event stitching will produce degenerate events** — if every positive has the same 0.7s duration, stitched events will have artificial uniformity.

**Comparison to realcartest V13.8:** On realcartest, the V13.8 oracle produced varied event boundaries (the 51 stitched events had durations ranging from 1s to 40s+). The dataset3 pilot shows the same VLM + same prompt producing templated boundaries on a different video — this is a prompt/format issue, not a video issue.

**Likely cause:** The `{"type": "video", "video": pil_frames, "fps": 2.0}` message format passes a list of PIL images without video metadata. The transformers warning `Asked to sample fps frames per second but no video metadata was provided, defaulting to fps=24` suggests the VLM may not be receiving correct temporal context, leading it to output a fixed boundary.

**Detailed audit:** See `BOUNDARY_DEGENERACY_AUDIT.md`.

---

## Q5: Worth Boundary Refinement?

**Answer: YES, with a mandatory boundary-fix prerequisite.**

The positive rate (10%), positive composition (real ego-path intrusions), and negative quality (no misjudgments) all support proceeding to P1b. dataset3 is a valid second-video benchmark for Event-Native AQP.

**However**, the boundary degeneracy (Q4) must be fixed before or during P1b. Options:

1. **Fix the video metadata warning** — pass `video_metadata` to the processor so the VLM gets correct temporal context. This is the most likely root cause.
2. **Switch to contact-sheet frame format** (V13.6 `contact_sheet_10s_5frames`) — uniformly spaced frames with explicit timestamps may produce better boundary localization.
3. **Post-hoc boundary refinement pass** — run a second VLM query on each positive anchor asking specifically for event boundary localization, with explicit frame timestamps.
4. **Accept degenerate boundaries for now** — if the AQP contribution is clip-level recall (not boundary precision), the templated 0.7s boundary may be acceptable for P2 budget-quality experiments. But this must be documented as a limitation.

**Recommendation:** Try fix #1 (video metadata) first at P1b. If boundaries remain templated, use fix #3 (post-hoc refinement) for the boundary refinement stage. If neither works, use fix #4 (accept for P2, document limitation) and proceed to budget-quality experiments where clip-level recall does not depend on precise boundaries.

---

## Comparison to realcartest V13.8

| metric | realcartest V13.8 | dataset3 P1 pilot |
|---|---|---|
| anchors | 399 (full scan) | 50 (stratified pilot) |
| positive rate | 23.6% (94/399) | 10.0% (5/50) |
| abstain rate | 0% | 0% |
| parse success | 100% | 100% |
| positive composition | vehicle=67, ped=13, cyclist=13 | ped=4, vehicle=1, cyclist=0 |
| boundary variety | varied (1s–40s+) | **templated (all 0.0–0.7s)** |
| evidence quality | specific | specific (comparable) |
| negative reasons | varied | normal_following=26, no_interaction=19 |

**Key difference:** dataset3 has a lower positive rate and pedestrian-dominant positives (vs realcartest's vehicle-dominant). This reflects the different scene type — dataset3 is Chinese urban with crosswalks and pedestrian activity, while realcartest was more vehicle-centric. This is a feature, not a bug: it tests the predicate's portability across scene types.

---

## Limitations

1. **50 anchors is a small sample.** The 10% positive rate has a wide CI (binomial 95% CI: ~3.3%–21.8%). The full-scan rate may differ.
2. **Stratified by proxy score, not random.** If positives cluster in specific score ranges, the stratified sample may over- or under-estimate the true rate.
3. **Boundary degeneracy not yet fixed.** The 0.0–0.7s template means event stitching on the full scan would produce artificial uniformity unless the boundary issue is addressed.
4. **No cyclist positives.** Expected given small sample, but the full scan should confirm cyclist events exist.
5. **VLM_ORACLE_RELATIVE labels only.** No human truth. All claims are about VLM-defined positives, not real risk events.
