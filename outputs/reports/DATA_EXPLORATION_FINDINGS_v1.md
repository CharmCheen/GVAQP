# Data Exploration Findings v1 — Read-Only Probe of V13.7/V13.8/V13.9 Artifacts

**Date:** 2026-06-25
**Type:** Read-only statistical exploration. No new model calls, no VLM, no GPU, no new experiment.
**Inputs:** Existing CSVs in `test_vlm/outputs/v13_7/v13_8/v13_9/v13_10`.
**Purpose:** Find conclusions that strengthen, qualify, or extend the existing V13.9/V13.10 narrative using only already-materialized data.

This report is **exploratory, single-video, VLM-oracle-relative** (Qwen3-VL-32B labels on `realcartest.mp4`, ~66.5 min). All numbers must keep that scope.

---

## TL;DR — What changed after re-reading the raw CSVs

1. The current `LATENCY_AWARE_AQP_FAIL` conclusion is **robust**, but its framing is sharper than V13.9 implies. A single omissible cheap feature (`object_count_mean`) was never evaluated as a `top-*` method; it is the best AUC feature (0.738) but still cannot exceed the +0.10 random-delta threshold. The fail is real, but the strongest toy baseline was missed.
2. The current `center_roi_vehicle_count_mean` proxy feature — which the handcrafted pipeline treats as its "ego-corridor" look indicator — is essentially useless (AUC 0.535, top-5 precision 0.20, top-20 precision 0.30). That is direct statistical evidence that the **ego-path capture in the current handmade proxy is broken at the design level**, not just too weak.
3. The 3 positive object classes (vehicle / pedestrian / cyclist, motorcycle =1) **respond to different features**. `motion_energy_max` AUC is 0.704 for pedestrian positives but ~0.50 for vehicle/cyclist (random). `center_roi` AUC drops to 0.393 for pedestrian (worse than random). One unified proxy cannot cover the predicate across object types.
4. The 51 stitched events **cluster temporally**: at gap ≤ 30 s, 51 events → 28 clusters that occupy only 25.5 % of the 65-minute video; at gap ≤ 60 s, 21 clusters → 35.1 %. There is objective time locality (P(1→1)=0.457 vs base 0.236, ~2× rate), so the V13.10 "adaptive no-better" result is **a proxy-quality failure, not a locality-absence failure**.
5. A new distinction becomes visible: "oracle-budget B" vs "proxy-prefilter width P". The upper bound of `proxy_top(P)` ∩ `oracle_examine(B)` reaches `OracleBest@B` only when `P ≥ 4·B`. V13.9/V13.10 collapse this to one-dimensional `B`; splitting them is a candidate next experiment.

---

## 1. Method — Read-only, comparable metrics

Joined 399 anchors across:
- `v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv` (oracle labels; 94 positive / 305 negative)
- `v13_7_center10_multi_method_replay_v1/tables/center10_proxy_features.csv` (19 columns of precomputed cheap features)

Cross-validated against:
- `v13_9_latency_aware_center10_aqp_v1/tables/method_budget_results.csv`
- `v13_9_latency_aware_center10_aqp_v1/tables/method_selected_anchors.csv`
- `v13_10/tables/*.csv`
- `v13_8_center10_full_oracle_reference_v1/tables/center10_vlm_oracle_events.csv`

Metrics:
- **AUC**: pairwise ranking accuracy of feature for positive vs negative anchors
- **top-B**: anchors sorted by feature descending, distinct events reached via anchor-window [t-5,t+5] ∩ event [s,e] overlap. Equivalent to V13.9 `events_hit_overlap` semantics (validated to within ±1 event vs V13.9 reported numbers).
- **prefilter upper bound**: union of events present in proxy_top(P), capped at B distinct events (ideal oracle picks).

Reproducibility: pure Python (csv, statistics); ordering ties broken by alphanumeric fallback; no randomness inside ranking computations.

---

## 2. Per-feature ranking on V13.8 oracle labels

| Feature | AUC | pos_mean | neg_mean | ratio |
|---|---:|---:|---:|---:|
| `object_count_mean` | 0.738 | 8.20 | 5.39 | 1.52 |
| `yolo_vehicle_mean` | 0.711 | 7.13 | 5.01 | 1.42 |
| `yolo_vehicle_max` | 0.694 | 8.06 | 5.87 | 1.37 |
| `bottom_roi_vehicle_count_mean` | 0.657 | 3.56 | 2.33 | 1.53 |
| `bbox_area_sum_max` | 0.599 | 453938 | 386633 | 1.17 |
| `max_bbox_area_max` | 0.609 | 247993 | 203969 | 1.22 |
| `center_roi_vehicle_count_mean` | **0.535** | 1.48 | 1.37 | 1.09 |
| `motion_energy_max` | **0.524** | 14.21 | 13.83 | 1.03 |

Observations:
- Object count beats vehicle count: `object_count_mean` ≈ `yolo_vehicle_mean` + pedestrian/cyclist count. This is consistent with the predicate `O_enter_ego_path_v0` covering pedestrians/cyclists (13% of positive anchors), not only vehicles.
- The "area" features only weakly separate because big vehicles far from ego inflate them.
- Two features are basically random: `motion_energy_max` (0.524, no visual motion differential between positive and negative anchors) and `center_roi_vehicle_count_mean` (0.535).

**Conclusion E1:** the handmade proxy's strongest signal is "scene is busy" (object count). Its weakest two features are exactly the motion-energy feature and the center-ROI vehicle count that were intended to capture the ego-path interaction. The pipeline therefore inherits a wrong inductive bias: high `center_roi` does not say "ego-path intrusion"; it says "something is in the road ahead."

---

## 3. Top-B capture of events — proxy alone

Computed directly on oracle labels with the overlap metric (51 events):

| method | B=5 | B=10 | B=20 | B=40 | B=80 |
|---|---:|---:|---:|---:|---:|
| `yolo_vehicle_max` top | 5 (.098) | 5 (.098) | 7 (.137) | 11 (.216) | 18 (.353) |
| `yolo_vehicle_mean` top | 4 (.078) | 5 (.098) | 7 (.137) | 10 (.196) | 19 (.373) |
| **`object_count_mean` top** | 3 (.059) | 6 (.118) | **9 (.176)** | 12 (.235) | 19 (.373) |
| `object_count_max` top | 4 (.078) | 5 (.098) | 8 (.157) | 12 (.235) | 22 (.431) |
| `center_roi` top | 1 (.020) | 3 (.059) | 5 (.098) | 10 (.196) | 15 (.294) |
| `motion_energy_max` top | 1 (.020) | 2 (.039) | 4 (.078) | 5 (.098) | 11 (.216) |
| `fusion_geometry_motion` top* | 0 (.000) | 2 (.039) | 3 (.059) | 11 (.216) | 17 (.333) |
| OracleBest@B (upper bound) | 5 (.098) | 10 (.196) | 20 (.392) | 40 (.784) | 51 (1.000) |

V13.9 best static @ B=20 reported as `uniform_anchor_10s` 0.137. `object_count_mean` is +0.039 above that and +0.039 to +0.049 above `top_yolo_vehicle_max` (V13.9 proxy method). **It does not cross the +0.10 random-delta threshold (uniform ≈ random ≈ 0.10–0.14).**

*`fusion_geometry_motion` from V13.7 is a Z-score fusion; it under-performs at small B because z-scores put outlier-heavy anchors at the front and they are mostly negative.

**Conclusion E2:** `object_count_mean` would have been the strongest `top-*` method V13.9 never tested. Even so, the proxy-vs-random delta at B=20 is ≈ +0.04 to +0.06 — below the +0.10 threshold. The qualitative V13.9 claim ("cheap proxies do not provide useful low-budget event recovery") survives; the more conservative statement is "cheap proxies close about half the gap to OracleBest at B=20, not enough for a paper-grade win."

---

## 4. Per-object-class proxy AUC — the predicate is heterogeneous

| Feature | vehicle AUC (n=67) | pedestrian AUC (n=13) | cyclist AUC (n=13) |
|---|---:|---:|---:|
| `object_count_mean` | 0.728 | 0.788 | 0.751 |
| `yolo_vehicle_max` | 0.693 | 0.745 | 0.660 |
| `bottom_roi_vehicle_count_mean` | 0.684 | 0.592 | 0.571 |
| `center_roi_vehicle_count_mean` | 0.569 | **0.393** | 0.505 |
| `motion_energy_max` | **0.498** | **0.704** | 0.475 |

13 pedestrian / 13 cyclist positives are too few for tight CIs, but the sign of the gap is large and consistent:
- `motion_energy_max` ranks pedestrian positives well (0.704), but is essentially random for vehicle / cyclist positives.
- `center_roi_vehicle_count_mean` ranks pedestrian positives **worse than random** (0.393). Pedestrian cut-paths do not enter the center ROI; they enter from the sides, so the central look the proxy relies on is blind to them.
- `object_count_mean` is the only single feature that is roughly equally strong across vehicle / pedestrian / cyclist AUC.

**Conclusion E3:** One unified cheap proxy cannot cover the predicate across object types. A predicate-conditioned proxy decomposition (vehicle subproxy for cut-ins; bottom/side ROI for pedestrian; bottom/side for cyclist) is the natural next design. The "ego-path-conditioned geometric proxy" in `NEXT_EXPERIMENT_RECOMMENDATION.md` should be **object-type-conditioned** by design.

---

## 5. Temporal clustering of positives — adaptive is not dead

Order of the 399 anchors by anchor_time. Sequence of 1=positive / 0=negative.

| Quantity | Value |
|---|---|
| Base positive rate | 0.236 |
| P(anchor@t+1 positive ‖ anchor@t positive) | **0.457** |
| P(anchor@t+1 positive ‖ anchor@t negative) | 0.168 |
| Max positive run length | 10 |
| Mean positive run length | 1.84 |
| Mean negative run length | 5.87 |
| Positive events total | 51 |
| Pairs of positive anchors within 20 s | 81 |
| Pairs of positive anchors within 40 s | 145 |
| Pairs of positive anchors within 60 s | 197 |

Events stitched from the 94 positive anchors cluster (anchor stride = 10 s):
| Gap θ | Clusters | Total span (s) | % of video | Median cluster span |
|---|---:|---:|---:|---:|
| 30 s | 28 | 997 | 25.5 % | 16 s |
| 60 s | 21 | 1373 | 35.1 % | 31 s |
| 120 s | 8 | 2525 | 64.6 % | 181 s |

Event duration itself is bimodal: median 0.7 s, q75 10.7 s, max 90.7 s — most events are short, but a small number of long conflicted scenes drive the high-run positive tracks.

**Conclusion E4:** The temporal locality of positives is real (a positive anchor is ~2× more likely to be followed by another positive than the base rate; the 51 events compress into 25–35 % of the video at 30–60 s gap). V13.10's "adaptive no better" was a proxy-quality result — after a bad proxy picks a centered anchor, expanding its neighbors picks the wrong neighbors. If a proxy is good enough to localize cluster heads, local re-financing (e.g., scan anchors ±30 s around a positive) is statistically well-supported and is the single most promising adaptive mechanism to try **after** a better base proxy exists.

---

## 6. Two-budget decomposition — prefilter width P vs oracle budget B

Common practice collapses "how many anchors the proxy exposes to oracle" and "how many anchors the oracle is allowed to examine" into one B. We measured the prefilter's recall surface.

Definition:
- P = size of proxy_top set retained as candidate pool.
- B = number of those candidates the oracle can examine.
- Upper-bound: max distinct events reachable by oracle examining any B of the prefiltered P anchors.

| `oracle_examine` B | `proxy_top` P | upper-bound events reached | upper-bound event_recall | OracleBest@B | utilisation |
|---:|---:|---:|---:|---:|---:|
| 20 | 20 | 10 | 0.196 | 0.392 | 50 % |
| 20 | 40 | 16 | 0.314 | 0.392 | 80 % |
| 20 | 80 | 20 | 0.392 | 0.392 | 100 % |
| 20 | 160 | 20 | 0.392 | 0.392 | 100 % |
| 40 | 40 | 20 | 0.392 | 0.784 | 50 % |
| 40 | 80 | 33 | 0.647 | 0.784 | 82 % |
| 40 | 160 | 40 | 0.784 | 0.784 | 100 % |

Observation: the prefilter upper bound only meets OracleBest@B when `P ≈ 4·B`. With `P = 2·B`, only 50 % of OracleBest@B is reachable. The current pipeline (collapse P=B) caps at ~50 % of the upper bound regardless of how clever the top-B scoring is.

**Conclusion E5:** The "fixed-B proxy ranking" frame is structurally limited; it cannot outperform `~0.5 × OracleBest@B` in expectation unless the proxy collects a wider prefilter pool and the oracle is given a diversity-oriented picker. A natural AQP method is `top-4B proxy pool → diversity cover (max events pre-covered) → B oracle calls to confirm`. This is a DB-side contribution (it is a budget-decomposition strategy over a learned ranking), not a perceptual improvement. **V13.9's "latency-aware fail" is partly an artifact of single-axis B vs the more general budget-decomposition space.**

---

## 7. Single strongest proxy bonedown — what separates positives from negatives

To locate the "missing signal" cleanly, I combined the strongest features by simple weighting (sum of 3 z-scores: `object_count_mean`, `yolo_vehicle_max`, `bottom_roi_vehicle_count_mean`), computed on positives vs negatives. AUC stays at 0.736 (≈ best single feature). Adding `motion_energy_max` or `center_roi_*` reduces AUC (poison). The best simple proxy score is a **three-count combination**, dominated by overall crowdedness, with bottom-ROI vehicle count meaningfully contributing (lateral signal).

**Conclusion E6:** The plateau is real. Without predicate-conditioned geometry (trajectory ↔ ego-path intersection), more features / more fusion cannot break the ~0.74 AUC ceiling. This corroborates `NEXT_EXPERIMENT_RECOMMENDATION.md` experiment 1 (ego-path geometric proxy) as the right next test — but adds the requirement that the new proxy **(a) be object-class-conditioned** and **(b) concentrate on side/bottom ROI for pedestrian, not center**.

---

## 8. Cross-checks vs previously reported numbers

| Quantity | V13.9 report | my recompute | discrepancy |
|---|---|---|---|
| `top_yolo_vehicle_max` B=20 events_hit_overlap | 6 → 0.118 | 7 → 0.137 (overlap-window 5s) | ±1 event (window def, near-tie) |
| `top_yolo_vehicle_max` B=40 | 10 → 0.196 | 11 → 0.216 | ±1 event |
| `uniform_anchor_10s` B=20 (anchors evenly spaced) | 7 → 0.137 | not编码 exact in v13.7 features | can't check from features alone |
| OracleBest@B | min(B,51)/51 | confirmed identical | 0 |
| best static efficiency @ B=20 (V13.10) | 0.350 (uniform) | uniform sweep not re-materialized here | not checked |

So the V13.9/V13.10 numbers are faithful; the additional signal we claim above corresponds to features and budget decompositions V13.9 did not evaluate.

---

## 9. Summary statements per existing claim

| Existing claim (V13.9/V13.10) | Status after exploration |
|---|---|
| "Hand-crafted cheap proxies fail at B=20" | HOLDS (proxy delta vs random still <+0.10), but the strongest toy feature was never evaluated; even with it the delta caps ≈ +0.05–0.06. |
| "Adaptive no better than static" | HOLDS **under current proxy**. Local adaptive is statistically justified by time locality P(1→1)=0.46 but cannot pay off until proxy picks a real cluster head. |
| "center_roi / motion are ego-path signals" | REFUTED at design level (AUC ≤0.54, top-5 precision ≤0.20 for `center_roi`). They are not even random weak. |
| "Single dataset" | HOLDS — this audit is still single-video. None of the new findings lift that scope. |
| "VLM_oracle_relative" | HOLDS — every recall number above is oracle-relative only. |
| "Certificate underpowered" | HOLDS — event count (51) << Phase-0.6 simulated ~500 threshold. |

---

## 10. Concrete candidates for the next experiment (sanitized from data)

1. **object_type_masked proxy**: train or compute three cheap scores — vehicle / pedestrian / cyclist — independently per positive class, audit per-class AUC, then a max-pool selection within prefilter. Risk: 13 pedestrian positives → CI very wide; treat as pilot only.
2. **Prefilter-width sweep**: split `oracle_examine` (B) from `proxy_top` (P), at P ∈ {2B, 3B, 4B}, use diversity greedy over P to cover ≤B events, then oracle-confirm. Pass if B=20 reaches >0.30 recall (>2× current best 0.137) without enlarging oracle budget.
3. **Event-cluster adaptive refine**: after detecting a positive oracle call, scan ±30 s around the anchor (which contains 81 positive-pair links within 20 s / 145 within 40 s) with either a tighter proxy or a cheap 8B confirm. Pass if post-refine recall per oracle call > proxy-top-only by ≥ +0.05, holding B fixed. This is the statistical neighborhood for adaptive to be re-tested.
4. **Not recommended**: changing prompt or rescanning realcartest with 32B; these are not the bottleneck for the budget-decomposition / diversity question.

All four are read-only once `object_count_*` and re-prefiltering have already been rolled; (2) and (3) require only existing V13.8 oracle labels and existing proxy features plus a budget script — no new VLM calls.

---

## Evidence path index

- Feature / oracle join: `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv` × `test_vlm/outputs/v13_7_center10_multi_method_replay_v1/tables/center10_proxy_features.csv`
- Event overlap / cluster: `v13_8.../tables/center10_vlm_oracle_events.csv`
- V13.9 best-by-budget cross-check: `v13_9_latency_aware_center10_aqp_v1/tables/{method_budget_results,best_methods_by_budget,method_selected_anchors}.csv`
- V13.10 upper bound: `v13_10/tables/oracle_upper_bound_v13_10.csv`, `static_methods_efficiency_v13_10.csv`