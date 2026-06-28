# Stage 2: Dataset3 Full Center10 Oracle Reference

**Date:** 2026-06-25
**VLM:** Qwen3-VL-32B-Instruct (A800 80GB)
**Predicate:** `O_enter_ego_path_v0` (V13.6 prompt, verbatim)
**Labels:** VLM_ORACLE_RELATIVE. No human truth. Boundary values unreliable (templated).

---

## Execution Summary

| metric | value |
|---|---|
| total anchors | 347 |
| P1 pilot reused | 50 |
| new VLM calls | 297 |
| parse success | 347/347 (100%) |
| abstain | 0 (0%) |
| total GPU time | ~60 min (297 calls × ~12s) + model load ~2×2min |
| input format | Video frames at fps=2 (Scheme A, Stage 1 selected) |

---

## Oracle Label Distribution

| label | count | rate |
|---|---|---|
| positive | 40 | 11.5% |
| negative | 307 | 88.5% |
| abstain | 0 | 0.0% |

**Positive rate = 11.5%** — within the 1–25% range for non-degenerate AQP. Higher than P1 pilot's 10% (stratified sample).

---

## Positive Composition

| involved_object | count | share |
|---|---|---|
| pedestrian | 25 | 62.5% |
| cyclist | 11 | 27.5% |
| vehicle | 4 | 10.0% |

**Key difference from realcartest V13.8:** realcartest had vehicle=67/ped=13/cyclist=13 (vehicle-dominant). dataset3 is pedestrian-dominant (62.5%), with significant cyclist presence (27.5%). This reflects the Chinese urban scene with crosswalks and mixed two-wheeler traffic.

**Cyclist events discovered:** The P1 pilot found 0 cyclist positives (small sample). The full scan reveals 11 cyclist events — cyclist ego-path intrusion is common on dataset3.

---

## Negative Reason Distribution

| reason | count | share of negatives |
|---|---|---|
| normal_following | 182 | 59.3% |
| no_ego_path_interaction | 125 | 40.7% |

No abstains, no "dense_traffic_only" or "far_crossing" — the VLM makes clean binary calls.

---

## Boundary Status

| metric | value |
|---|---|
| unique event_start values | 2 ({0.0, 0.5}) |
| unique event_end values | 1 ({0.7}) |
| boundary_status | all "ok" |

**Boundary is templated.** All 40 positives have event_end=0.7. Most have event_start=0.0, a few have 0.5. This confirms the Stage 1 finding: boundary localization is unreliable. Clip-level labels are reliable; boundaries are not.

---

## Confidence Distribution

| confidence | count |
|---|---|
| high | 347 (100%) |

All labels are high-confidence. The VLM does not hedge — it makes clear binary calls.

---

## Relation to P1 Pilot

| metric | P1 pilot (50 anchors) | Full scan (347 anchors) |
|---|---|---|
| positive rate | 10.0% (5/50) | 11.5% (40/347) |
| pedestrian share | 80% (4/5) | 62.5% (25/40) |
| cyclist share | 0% (0/5) | 27.5% (11/40) |
| vehicle share | 20% (1/5) | 10.0% (4/40) |

P1 pilot over-represented pedestrian and under-represented cyclist events due to small sample. The full scan reveals a more diverse event composition.

**Label stability check:** P1 anchor 0197 (bus cut-in, positive in P1) was labeled negative in Stage 1 Scheme A re-test. This is the one label instability case — vehicle merge events may be borderline for this VLM.

---

## Oracle Failure Cases

No parse errors, no GPU errors, no timeout failures. All 297 new VLM calls succeeded. The resumable design (save per-anchor JSON + JSONL) handled the 60-minute timeout gracefully — the scan was resumed and completed in two sessions.

---

## Output Files

| file | description |
|---|---|
| `oracle_outputs/dataset3_full_center10_parsed.csv` | 347-row parsed labels (V13.8 schema + boundary_reliable) |
| `oracle_outputs/dataset3_full_center10_raw.jsonl` | Raw VLM responses (one JSON per line) |
| `oracle_outputs/raw_per_anchor_full/` | Per-anchor raw JSON files (297 new + 50 P1 reused) |
| `analysis/full_center10_analysis.json` | Quantitative analysis summary |
