# P1 Dataset3 Semantic Pilot — Final Decision

**Date:** 2026-06-25
**Output dir:** `garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/`

---

## DECISION: **GO** (with boundary-fix prerequisite for P1b)

---

## Five Questions Answered

| # | question | answer | status |
|---|---|---|---|
| Q1 | Positive rate? | **10.0%** (5/50) — within 1%–10% GO range | ✓ |
| Q2 | Positives are real ego-path intrusions? | **YES** — ped crossing×4, vehicle cut-in×1; all interpretable, specific evidence | ✓ |
| Q3 | Hard negatives misjudged? | **NO** — 45 negatives clean (normal_following=26, no_interaction=19); high-score dense-traffic correctly negative | ✓ |
| Q4 | Boundary degeneracy? | **YES — templated** (all 5 positives: start=0.0s, end=0.7s, boundary_status=ok) | ⚠ |
| Q5 | Worth boundary refinement? | **YES**, but fix boundary issue first (video_metadata / post-hoc refinement / accept for P2) | ✓ |

---

## Decision Rationale

**GO criteria met:**
- ✅ Positive rate in 1%–10% with stable clear positives (10%, 5 events)
- ✅ Hard negatives not misjudged (0 false positives, clean negative reasoning)
- ✅ Oracle outputs interpretable evidence (specific descriptions referencing crosswalks, buses, sidewalks)
- ✅ Event state judgment usable (positive/negative binary is reliable; boundary is not)

**One caveat (not blocking for GO):**
- ⚠ Boundary output is templated (all 0.0–0.7s). This does NOT affect clip-level recall (the AQP contribution) but DOES affect event stitching. Must be fixed before or during P1b, or accepted as a documented limitation for P2.

**Why not WEAK GO:** The positive rate is at the GO upper bound (10%), not "very few." The positives are diverse (pedestrian + vehicle), not a single type. The negatives are clean, not uncertain. This is a strong positive result, not a marginal one.

---

## What This Enables

| next step | status | dependency |
|---|---|---|
| **P1b boundary oracle** (full 347-anchor scan) | **AUTHORIZED TO PROCEED** (with boundary fix) | Fix video_metadata or accept limitation |
| **P2 budget-quality curve** | authorized after P1b | needs P1b labels |
| **Budget decomposition replication** | authorized after P1b | needs P1b labels + dataset3 proxy features (already built) |
| **Certificate test** | authorized after P1b | needs P1b labels + sufficient positive count |

**Estimated P1b cost:** 347 anchors × ~12s/anchor = ~70 min GPU. Same A800, same configuration.

---

## Boundary Fix Action Plan

**At P1b start, test Fix 1 (video_metadata) on first 10 anchors:**
1. Add `video_metadata={"duration": 10.0, "fps": 2.0}` to the video message.
2. Check if transformers warning disappears.
3. Check if event_start/event_end values become varied.
4. If yes → full scan with Fix 1. If no → try Fix 2 (contact-sheet) or Fix 3 (post-hoc refinement).
5. If all fail → accept Fix 4 (document limitation, proceed to P2 on anchor-level labels).

---

## Key Findings for AQP-Side Research

1. **Proxy score ≠ event presence (confirmed on second video).** 22 high-score anchors were correctly labeled negative — dense traffic with many vehicles but no ego-path intrusion. This replicates the realcartest finding and reinforces the budget-decomposition motivation: oracle targets must be chosen by coverage, not raw proxy score.

2. **Scene-type portability.** The predicate `O_enter_ego_path_v0` works on Chinese urban crosswalk-heavy scenes (dataset3) with a different positive composition (pedestrian-dominant) than realcartest (vehicle-dominant). The prompt is portable; the positive mix shifts with scene type.

3. **VLM evidence quality is cross-scene stable.** The VLM produces specific, interpretable evidence on both videos. This supports using evidence as a qualitative validation signal in future experiments.

4. **Boundary localization is the weak point.** The VLM's binary event judgment (positive/negative) is reliable, but its temporal boundary localization is not. This is an AQP-side finding: clip-level recall guarantees are feasible, but event-boundary-level guarantees require additional machinery (post-hoc refinement or multi-pass query).

---

## Output File Index

| path | content |
|---|---|
| `metadata/center10_anchor_grid.csv` | 347 center10 anchors |
| `metadata/center10_proxy_features.csv` | 347-anchor proxy features (V13.7 schema + ego-band/lateral) |
| `metadata/dataset3_anchor_plan.csv` | 50 stratified pilot anchors |
| `oracle_outputs/dataset3_oracle_parsed.csv` | 50-row parsed VLM labels (V13.8 schema) |
| `oracle_outputs/dataset3_oracle_raw.jsonl` | raw VLM responses (one JSON per line) |
| `oracle_outputs/raw_per_anchor/` | per-anchor raw JSON files |
| `oracle_outputs/pilot_analysis.json` | quantitative analysis |
| `reports/SEMANTIC_PILOT_REPORT.md` | detailed Q1–Q5 analysis |
| `reports/BOUNDARY_DEGENERACY_AUDIT.md` | boundary template finding + fix plan |
| `reports/P1_DATASET3_SEMANTIC_PILOT_FINAL.md` | this decision document |
| `scripts/build_anchor_plan.py` | anchor grid + proxy features + stratified selection |
| `scripts/run_pilot_oracle.py` | VLM oracle runner (adapted V13.8) |
| `logs/anchor_build.log` | anchor build log |
| `logs/pilot_run.log` | full pilot run log |

---

## Reproducible Commands

```bash
cd /qiuyeqing/llama_prl/G-ARC && source env_garc.sh

# build anchor grid + proxy features + select 50 pilot anchors
python garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/scripts/build_anchor_plan.py

# run 50-anchor VLM pilot (~16 min on A800)
python garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/scripts/run_pilot_oracle.py

# smoke test (3 anchors, ~2 min)
# create dataset3_anchor_plan_smoke.csv with 3 anchors first, then run with smoke plan
```
