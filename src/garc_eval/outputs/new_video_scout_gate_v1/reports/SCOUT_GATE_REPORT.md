# P0 New-Video Scout Gate — Report

**Task:** Low-cost data-availability & event-density screening for `dataset2` / `dataset3`
as candidate long-video benchmarks for Event-Native Budgeted AQP.
**Stage:** P0 scout (necessary-condition screen). **No VLM / LLM oracle. No semantic
event labels. No claim that proxy high-score windows are real events.**
**Date:** 2026-06-25
**Output dir:** `garc_eval/outputs/new_video_scout_gate_v1/`

---

## 1. Decision

| video | data_avail | non_degeneracy | predicate_relevance | scene_distinctness | **GATE** |
|---|---|---|---|---|---|
| **dataset3** | PASS | PASS | PASS (rich heterogeneous mix) | PASS (1080p, rich two-wheeler) | **GO** — recommend center10 pilot |
| **dataset2** | PASS | PASS | WEAK (bike_any only 0.8%) | PASS (720p, pedestrian-heavy urban) | **WEAK GO** — pilot with caution |

**Rationale.** Both videos clear data-availability and non-degeneracy. `dataset3`
additionally shows a class mix (vehicle 95.8% + person 37.5% + bike/motorcycle
12.3%) that closely matches the heterogeneous composition of the active predicate
`O_enter_ego_path_v0` on realcartest (vehicle=67 / pedestrian=13 / cyclist=13),
plus the highest lateral activity (bbox_cx_std 0.179 vs 0.096), making it the
strongest second-video candidate. `dataset2` is non-degenerate and provides
scene-type diversity (pedestrian-dominated, different resolution) but its
two-wheeler signal is near-vacuous (0.8% of windows), so the cyclist subtype of
the predicate would be underrepresented — usable as a diversity / portability
test, not as the primary replication video.

**Both decisions are NECESSARY-condition screens only.** They do not estimate
positive rate or proxy AUC (those require oracle labels, forbidden at this stage).
The next step is a small center10 pilot per AGENTS.md "avoid full 32B scan until
non-degenerate".

---

## 2. Data Availability (both PASS)

| field | dataset2 | dataset3 | realcartest (V13 ref) |
|---|---|---|---|
| resolution | 1280×720 | 1920×1080 | 1920×1080 |
| fps | 30.000 | 30.000 | 24.000 |
| duration | 4617.0s (76.9min) | 3462.9s (57.7min) | 3987.1s (66.5min) |
| nb_frames (ffprobe) | 138509 | 103886 | 95690 |
| bit_rate | 1.90 Mbps | 2.61 Mbps | — |
| codec | h264 High@51 | h264 High@50 | h264 |
| **duration ≥ 30min** | YES (76.9) | YES (57.7) | YES (66.5) |
| **frames ≥ 10000** | YES (138509) | YES (103886) | YES (95690) |
| **read success rate** | **100.0%** (0 fail / 138509) | **100.0%** (0 fail / 103886) | — |
| 5s windows produced | 924 | 693 | 798 |
| contact sheet frames | 77 (1 per 60s) | 58 (1 per 60s) | — |

No corrupt gaps. Single sequential cv2 pass: d2 63.9s (2166 fps read), d3 97.7s
(1063 fps read — higher resolution). Batched YOLOv8n on A800: d2 924 frames in
18.5s (50 fps), d3 693 frames in 13.9s (50 fps). Total scout cost per video
< 2 min on one A800. **Contact sheets need human visual inspection** (this
model cannot read images): `figures/contact_sheet_dataset2.jpg`,
`figures/contact_sheet_dataset3.jpg`.

---

## 3. Non-Degeneracy (both PASS)

5s-window cheap proxy features, compared against the V13.5 realcartest 5s
reference (`experiments/v13/v13_5_pilot/tables/proxy_features_5s.csv`, 798 rows).

| signal | realcartest | dataset2 | dataset3 | criterion |
|---|---|---|---|---|
| motion_energy_mean μ | 12.34 | 29.42 | 30.17 | non-zero |
| motion_energy std | 9.04 | 7.72 | 7.60 | > 0 |
| motion_energy CV | 0.73 | 0.26 | 0.25 | — (see note) |
| motion non-zero win | 100% | 100% | 100% | most windows |
| vehicle_count μ | 5.51 | 1.36 | 5.07 | — |
| vehicle_count CV | 0.54 | **0.73** | **0.63** | > 0.3 ✓ |
| vehicle non-zero win | 97.1% | 89.1% | 95.8% | meaningful fraction ✓ |
| object_count μ | 6.05 | 3.37 | 6.56 | — |
| object_count CV | 0.56 | 0.42 | 0.58 | non-trivial spread ✓ |

**Note on motion CV.** Both new videos have lower motion CV (0.25–0.26) than
realcartest (0.73): higher baseline motion / busier scenes, so motion_energy is
less discriminative as a ranking signal here. This is **not** a degeneracy
(std > 0, non-constant) but it does mean `motion_energy` alone will be a weaker
proxy feature on these videos. The primary proxy feature per AGENTS.md is
`object_count_mean` (best single-feature AUC 0.738 on realcartest), and its CV
on the new videos (0.42 / 0.58) is comparable to realcartest (0.56) — so the
primary ranking signal retains discriminative power.

---

## 4. Predicate Relevance — `O_enter_ego_path_v0` (both non-vacuous, d3 strong)

The active predicate is object-type-heterogeneous: on realcartest V13.8 the 94
positives split **vehicle=67 / pedestrian=13 / cyclist=13**. A useful second
video must contain vehicles AND vulnerable road users (pedestrian + bicycle/
motorcycle) so the heterogeneous predicate is testable.

| class (frac windows with ≥1 YOLOv8n det) | realcartest* | dataset2 | dataset3 |
|---|---|---|---|
| vehicle | — (97.1% vehicle_count) | 89.1% | 95.8% |
| person | (not in V13.5 schema) | **83.9%** | 37.5% |
| bicycle | (not in V13.5 schema) | 0.0% | 5.5% |
| motorcycle | (not in V13.5 schema) | 0.8% | 6.8% |
| **bike_any (bicycle+motorcycle)** | — | **0.8% (WEAK)** | **12.3% (85 win)** |
| near_ego_vehicle (ego-band ROI) | (not in V13.5) | 85.2% | 87.7% |
| bbox_cx_std μ (normalized lateral spread) | (not in V13.5) | 0.096 | **0.179** |
| bbox_cx_std non-zero win | — | 93.7% | 93.2% |
| lateral_presence_count μ | — | 0.87 | **3.31** |

*realcartest V13.5 CSV has no per-class breakdown (only `vehicle_count_mean`); its
class mix is known from the V13.8 oracle label split, not from the scout CSV.

**dataset3** is the closest analog to realcartest's heterogeneous predicate:
vehicles dense (95.8%), pedestrians present (37.5%), and a rich two-wheeler
signal (12.3% of windows, 85 windows) — substantially richer than dataset2.
It also has the highest lateral activity (bbox_cx_std 0.179, lateral_presence
3.31), directly relevant to "object starts laterally and enters ego path".

**dataset2** is pedestrian-dominated (83.9% person windows) with near-vacuous
two-wheeler signal (0.8%). It would test the pedestrian subtype of the predicate
strongly but the vehicle/cyclist subtypes weakly.

---

## 5. Scene Distinctness from realcartest (both PASS)

| | realcartest | dataset2 | dataset3 |
|---|---|---|---|
| resolution | 1920×1080 | **1280×720** | 1920×1080 |
| fps | 24 | **30** | **30** |
| dominant class | vehicle | **person** | vehicle + person + bike |
| vehicle density μ | 5.51 | **1.36** (low) | 5.07 (comparable) |
| scene type (inferred from class mix) | vehicle-heavy driving | pedestrian-heavy urban | dense traffic w/ two-wheelers |

Both differ from realcartest along multiple axes (resolution / fps / class mix /
vehicle density), satisfying the AGENTS.md preference for a "different scene type
(highway / night / weather) from realcartest to test V13.6 prompt stability".
d2 provides the largest scene shift (pedestrian-heavy urban, lower-res); d3
provides a class-mix shift while keeping 1080p.

---

## 6. Notable Finding — V13.5 center-thirds ROI is broken on dataset3

AGENTS.md records that `center_roi_vehicle_count_mean` (AUC 0.535, "effectively
random — the ego-corridor design in the handmade proxy is broken at the feature
level"). The scout replicates this failure mode cleanly on dataset3:

| ROI definition | dataset2 nz | dataset3 nz |
|---|---|---|
| V13.5 center-thirds (x∈[⅓,⅔], y∈[⅓,⅔]) | 85.2% | **1.9%** (13/693) |
| ego-band (x∈[0.35,0.65], y∈[0.45,1.0]) | 85.2% | **87.7%** (608/693) |

On dataset3, vehicles are almost never in the geometric center-third box but ARE
in the lower-center ego band — a different camera geometry / object distribution
that makes the V13.5 center-ROI near-useless. The ego-band ROI (from the
kinematic proxy config) works on both. **Action for the center10 pilot on d3:
use the ego-band ROI, not the V13.5 center-thirds ROI, for any near-ego proxy
feature.** This is a direct AQP-side consequence (proxy feature design), not a
detector improvement. (Bug fix applied in the scout script: the V13.5 code used
`cy = (y2+y2)/2` = bbox bottom for the ROI test; this scout uses the true
vertical center `(y1+y2)/2`, so the 1.9% figure is not an artifact of that bug.)

---

## 7. Sanity Checks (all PASS)

| check | result |
|---|---|
| frame read success > 99.5% | d2 100.0%, d3 100.0% — PASS |
| motion non-degenerate (std>0, non-zero in most win) | both 100% non-zero, std 7.6–7.7 — PASS |
| vehicle CV > 0.3 | d2 0.73, d3 0.63 — PASS |
| object_count spread non-trivial | d2 CV 0.42, d3 CV 0.58 — PASS |
| no forbidden fields (vlm/oracle/label/event_*) | both `INVARIANT PASS` (grep-clean) — PASS |
| schema = V13.5 superset | first 18 cols identical + 6 extra — PASS |
| person OR bike present | d2 person 83.9%, d3 person 37.5% + bike 12.3% — PASS |
| lateral activity non-trivial | d2 cx_std 0.096 (93.7%), d3 cx_std 0.179 (93.2%) — PASS |
| YOLO status | all rows `ok` or `no_detections` (no errors) — PASS |

Full stats: `tables/sanity_check_summary.json`.

---

## 8. Limitations & What This Scout Does NOT Establish

1. **No positive-rate / proxy-AUC estimate.** That requires oracle labels
   (forbidden here). The scout only confirms the cheap-signal *preconditions*
   for a non-degenerate pilot.
2. **No claim that high-motion / high-count windows are real events.** Per task
   constraints, proxy high-score windows are NOT interpreted as semantic events.
3. **Motion CV is lower than realcartest** on both videos — motion_energy will
   be a weaker standalone proxy feature; the pilot should rely on
   `object_count_mean` (and, on d3, the ego-band ROI variant) as primary scores.
4. **Contact sheets not visually verified by me** (image input unsupported).
   A human should glance at `figures/contact_sheet_dataset2.jpg` and
   `figures/contact_sheet_dataset3.jpg` to confirm continuous dashcam driving
   footage (no static camera, no cuts, no off-road segments).
5. **dataset2 two-wheeler signal is near-vacuous (0.8%).** The cyclist subtype
   of `O_enter_ego_path_v0` would be underrepresented; expect a
   pedestrian-skewed positive composition if d2 is piloted.
6. **Single midpoint frame per 5s window for YOLO** (matches V13.5 protocol).
   Within-window temporal variation of object counts is not captured; this is
   sufficient for a scout but the center10 pilot should aggregate multiple
   frames per anchor (V13.7 style).

---

## 9. Recommendation — Next Step (center10 pilot, NOT authorized here)

Per AGENTS.md target #3 ("Second long-video validation — a small center10 pilot
first, avoid full 32B scan until non-degenerate"):

- **dataset3 → center10 pilot** (GO). Build the center10 anchor grid (10s
  spacing, 5s half-window), aggregate the existing 5s scout features up to
  anchor level (reuse `v13_7_pipeline.py:97-145` aggregation), compute z-scores
  and fusion scores matching `center10_proxy_features.csv` schema, then run a
  small VLM pilot (~40-50 anchors stratified by proxy score) to check
  positive rate is in 1–25% and non-degenerate. Use ego-band ROI, not V13.5
  center-thirds. ~57.7min → ~346 anchors at 10s spacing.
- **dataset2 → center10 pilot with caution** (WEAK GO). Same protocol; expect
  pedestrian-skewed positives and few cyclist events. Useful as a
  scene-portability / prompt-stability test, not as the primary replication.
  ~76.9min → ~461 anchors at 10s spacing.
- **Do NOT run a full 32B scan** on either video until the pilot confirms a
  non-degenerate positive rate.

No VLM calls are made in this report. The next step requires explicit
authorization for VLM compute.

---

## 10. Reproducible Commands

```bash
cd /qiuyeqing/llama_prl/G-ARC && source env_garc.sh

# smoke (first 120s, ~90s total)
python garc_eval/outputs/new_video_scout_gate_v1/scripts/scout_pipeline.py --mode smoke --videos both

# full (both videos, ~4 min total on one A800)
python garc_eval/outputs/new_video_scout_gate_v1/scripts/scout_pipeline.py --mode full --videos both

# single video
python garc_eval/outputs/new_video_scout_gate_v1/scripts/scout_pipeline.py --mode full --videos d3
```

## 11. Outputs Index

| path | content |
|---|---|
| `config/scout_config.yaml` | experiment config, gate criteria, ROI defs, forbidden list |
| `data_manifest/input_manifest.md` | input videos, signal sources, schema, leakage notes |
| `scripts/scout_pipeline.py` | self-contained scout pipeline (ffprobe+motion+YOLO+ROI+lateral+contact+figures) |
| `tables/window_features_dataset2.csv` | 924 rows, V13.5-superset 5s-window proxy features |
| `tables/window_features_dataset3.csv` | 693 rows, V13.5-superset 5s-window proxy features |
| `tables/summary_dataset2.json` / `summary_dataset3.json` | per-video summary stats |
| `tables/summary_combined_full.csv` / `.json` | combined summary |
| `tables/sanity_check_summary.json` | 3-video comparison stats (realcartest + d2 + d3) |
| `figures/scout_timeline_dataset2.png` / `dataset3.png` | motion / class / ego-occupancy timelines |
| `figures/scout_comparison_3video.png` | 4-panel distribution + class-mix + ROI comparison |
| `figures/contact_sheet_dataset2.jpg` / `dataset3.jpg` | 1 frame / 60s montage (needs human visual check) |
| `logs/scout_smoke.log` / `scout_full.log` | full run logs with timestamps |
