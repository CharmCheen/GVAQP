# Diversity Prefilter Replay v1 — Final Report

**Date:** 2026-06-25
**Code:** `garc_eval/outputs/diversity_prefilter_replay_v1/scripts/run_diversity_prefilter_replay.py`
**Input files (read-only, no new model calls):**
- `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv`
- `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_vlm_oracle_events.csv`
- `test_vlm/outputs/v13_7_center10_multi_method_replay_v1/tables/center10_proxy_features.csv`
- `test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/tables/method_budget_results.csv` (for sanity cross-check)

**Manifest:** 399 anchors × VLM-32B oracle (94 positive / 305 negative / 51 stitched events) over `realcartest.mp4` (~66.5 min). Single video. All labels VLM_ORACLE_RELATIVE, not human truth.

**Wall time:** < 5 seconds on CPU (pure replay over CSVs).
**Random seed base:** 42; **N random repeats per budget:** 200 (per `AGENTS.md`).

---

## 1. What this experiment tests

The V13.9/V13.10 "LATENCY_AWARE_AQP_FAIL" consequences collapsed the search axis to single-value B = "proxy top-B → oracle examines exactly those B". Three alternative budget allocations on **the same 399-anchor oracle** as V13.9:

- **H1 — Prefilter diversity** (DB-style budget decomposition). Split `proxy_top(P=2B, 3B, 4B, 8B)` from `oracle_examine(B)`. Greedy pick from the pool scoring `(score) + α · min_time_distance_to_selected` with α ∈ {0.5, 1, 2}. Hypothesis: a wider pool + temporal-spread-aware selection captures more distinct events per oracle call.
- **H2 — Multi-signal max-pool**. For each anchor take `max` of z-normalized scores over a small feature set (`object_count_mean` best for vehicle, `motion_energy_max` best for pedestrian, `bottom_roi_vehicle_count_mean` for lateral, `yolo_vehicle_max`). Hypothesis: object-type-heterogeneous predicate needs an any-signal-aggregated proxy.
- **H3 — Confirmed-positive adaptive refine**. Round 1 = top-(B/2) proxy; round 2 = contextually replay oracle ±30/±60 s around each TRUE positive returned, until total calls = B. Hypothesis: adaptive that expands around confirmed positives (not high-proxy-score anchors) leverages temporal locality discovered at runtime.

Baselines reproduced from V13.9 plus an added `top_object_count_mean` method (V13.9 omitted the single best-AUC cheap feature).

---

## 2. Sanity

| Check | Mine | V13.9 report | Verdict |
|---|---|---|---|
| Positive anchors | 94 / 399 (0.236) | 94 / 399 (0.236) | OK |
| Stitched events | 51 | 51 | OK |
| `top_yolo_vehicle_max` B=20 events_hit_overlap | 6 | 6 | exact match |
| `OracleBest@B` | min(B,51)/51 | min(B,51)/51 | matches V13.10 |

The exact V13.9 drop-in baseline equals the prior V13.9 number — the simulation correctly reproduces the V13.9 system at its own conditions before adding any new method.

---

## 3. Results — head-to-head

### 3.1 Random baseline (200 repeats; far tighter than V13.9's 5-seed)

| B | mean | std | 95% CI [p2.5, p97.5] | p99.8 |
|---:|---:|---:|---|---:|
| 5  | 0.025 | 0.018 | [0.000, 0.059] | 0.078 |
| 10 | 0.046 | 0.026 | [0.000, 0.098] | 0.122 |
| 20 | 0.089 | 0.035 | [0.020, 0.157] | 0.176 |
| 40 | 0.165 | 0.045 | [0.078, 0.255] | 0.306 |
| 80 | 0.305 | 0.053 | [0.196, 0.412] | 0.451 |

Important correction vs V13.9 — the V13.9 5-seed random estimate was optimistic (mean ≈0.10–0.14 at B=20 with 5 seeds). With 200 reps the random distribution is much tighter; the V13.9 "delta vs random" was computed against a noisy baseline. The +0.10 decision threshold in V13.9 was approximately a z-score against `mean+2σ ≈ 0.16` (i.e. roughly `p97.5`), so it survives the better-estimated baseline — meaning the qualitative V13.9 fail judgement still holds for the **single-axis proxy-top-B methods**.

### 3.2 Best method per budget

| B | best method | recall | random mean | Δ vs random mean | best baseline | Δ vs base |
|---:|---|---:|---:|---:|---:|---:|
| 5  | `top_yolo_vehicle_max`                | 0.098 | 0.025 | +0.073 | 0.059 | +0.039 |
| 10 | **`prefilter_div_objmean_P3B_a0.5`**  | **0.137** | 0.046 | +0.091 | 0.098 | +0.039 |
| 20 | `prefilter_div_objmean_P2B_a0.5`      | 0.176 | 0.089 | +0.088 | 0.157 | +0.020 |
| 40 | **`prefilter_div_objmean_P2B_a0.5`**  | **0.314** | 0.165 | +0.149 | 0.216 | +0.098 |
| 80 | **`prefilter_div_objmean_P8B_a0.5`**   | **0.490** | 0.305 | +0.185 | 0.353 | +0.137 |

**Best method is consistently the diversity-prefilter on `object_count_mean` with small α=0.5 and narrow P=2B/3B/8B.**

### 3.3 Per-hypothesis outcome

| Hypothesis | B=20 best recall | Δ vs random mean | Δ vs top_obj_mean base | Δ vs random p99.8 | decision | 
|---|---:|---:|---:|---:|---|
| H1 — Prefilter diversity | 0.176 | +0.088 | +0.020 | +0.000 | **WEAK** (exactly touches p99.8) |
| H2 — Multi-signal max-pool | 0.137 | +0.048 | −0.020 | −0.040 | **NO** |
| H3 — Confirmed-positive refine | 0.098 | +0.009 | −0.059 | −0.079 | **NO** |

At the more meaningful B=40 (closer to where the OracleBest curve starts to rise):

| Hypothesis | B=40 best recall | Δ vs random mean | Δ vs top_obj_mean base | Δ vs random p99.8 | decision |
|---|---:|---:|---:|---:|---|
| H1 — Prefilter diversity | 0.314 | +0.149 | +0.098 | +0.008 | **STRONG** |
| H2 — Multi-signal max-pool | 0.216 | +0.051 | +0.000 | −0.090 | **NO** |
| H3 — Confirmed-positive refine | 0.157 | −0.008 | −0.059 | −0.149 | **NO** |

### 3.4 Efficiency ratio (recall / OracleBest@B) — direct V13.10 metric comparison

| Budget | V13.10 best static efficiency | this experiment best | improvement (pp) |
|---:|---:|---:|---:|
| B=20 | 0.350 (uniform_anchor_10s) | **0.450** (prefilter_div_objmean_P2B_a0.5) | +10.0 |
| B=40 | 0.275 (top_fusion_geometry_motion) | **0.400** (prefilter_div_objmean_P2B_a0.5) | +12.5 |
| B=80 | — | **0.490** (prefilter_div_objmean_P8B_a0.5) | — |

The gap to the OracleBest upper bound is partially closed by a **pure budget-decomposition switch** (the same proxy features, the same oracle, no new VLM calls). This contradicts the way V13.10 phrased `STATIC_METHODS_FAR_BELOW_UPPER_BOUND` as a property of proxy weakness alone; a meaningful fraction is attributable to **single-axis budgeting**, not only proxy quality.

---

## 4. Multiple-comparison correction (Bonferroni)

25 H-configurations tested. α = 0.05 / 25 = 0.002 ⇒ p99.8 threshold.

| B | best H recall | random p99.8 | exceeds Bonferroni? | vs base |  per-B decision |
|---:|---:|---:|---|---:|:--|
| 5  | 0.078 | 0.078 | tied | +0.020 (yes, base lower) | WEAK |
| 10 | 0.137 | 0.122 | yes (+0.016) | +0.039 | **STRONG** |
| 20 | 0.176 | 0.176 | tied | +0.020 | WEAK |
| 40 | 0.314 | 0.306 | yes (+0.008) | +0.098 | **STRONG** |
| 80 | 0.490 | 0.451 | yes (+0.039) | +0.137 | **STRONG** |

**Overall decision: WEAK_GO.**
- Strict criterion (both B=20 and B=40 STRONG after Bonferroni): NOT MET — B=20 only ties p99.8.
- Loose criterion (B=40+ STRONG, B=20 beats base by ≥+0.02): MET — practical improvement at operating-point budgets.

The strongest, multiple-comparison-defensible **single claim** is:

> At oracle budget B=40 on `realcartest.mp4` under Qwen3-VL-32B oracle, a 2-stage diversity prefilter on the same cheap `object_count_mean` proxy used in V13.9 reaches event-recall 0.314 (95% above RANDOM 0.165 mean / 0.306 p99.8) — vs the V13.9-reported best static 0.216 at the same budget (+0.098 absolute, +45 % relative). The OracleBest@40 efficiency rises from 0.275 to 0.400.

### 4.1 Why H2 and H3 failed

- **H2 Multi-signal max-pool**: the per-class AUC advantage (motion energy for pedestrians, bottom-ROI for lateral objects) does not transfer to top-B selection because the per-class positives overlap heavily with the strongest-feature positives (vehicle cut-in dominates). Combining signals via `max` mostly adds noise from the worst features. Multi-signal averaging can help only if the per-class positives are disjoint in time.
- **H3 Confirmed-positive refine**: the V13.10 conclusion "adaptive no better" is **vindicated** even with this principled adaptive rule. Reason: positives are temporally clustered (P(1→1)=0.457), so expanding ±30/±60 s around any confirmed positive re-hits the already-hit event neighborhood rather than discovering new events. Adaptive refine works only when budget × positives can spread across distinct events, but the actual data has too few distinct hot zones. This is independent of proxy quality.

### 4.2 What H1 captured that V13.9/V13.10 missed

The V13.9/V13.10 framing was: choose B anchors that maximize proxy score. The prefilter diversity method: **the oracle's job is to maximize distinct events discovered, not to examine the top-B highest scores**. With P=2B and a small temporal-spread penalty, the diversity solver picks anchors that are slightly lower scoring but spread across different time-clusters, hitting more events.

The α=0.5 sweet spot is small — the proxy score still dominates the welfare function, but with a tiny penalty for sitting inside an already-selected temporal neighborhood. Aggressive diversity (α=2.0) shows no further gain over α=0.5. Wider P (8B) only helps at B=80, where there are enough positives in the pool to require pulling farther down the proxy ranking.

---

## 5. Limitations and caveats

1. **Single video.** All numbers are for `realcartest.mp4` (66.5 min, Chinese urban dashcam). The +0.098 absolute delta at B=40 is single-video; does not generalize.
2. **VLM-oracle-relative.** Qwen3-VL-32B labels are not human truth; no human calibration exists.
3. **Multiple comparisons.** 25 H-configurations offer an upward bias — best-case cited; the Bonferroni-corrected STRONG threshold is met only at B=10, 40, 80 (not B=20).
4. **`object_count_mean` was added as a NEW top-* baseline and would have been V13.9's best method**. Honest reading: V13.9's `uniform_anchor_10s` was the best method partly because V13.9 didn't test `top_object_count_mean`. The "V13.10 improvement" here is **not purely from H1**; ~half of the gain comes from choosing a stronger base feature. To disentangle, the line `Δ vs base_objmean` in §3.2 is the cleanest H1-specific number (B=40: +0.098, B=80: +0.137).
5. **No new semantic proxy.** H1's gain comes from budget-decomposition logic; it does not solve the underlying proxy weakness H1 was designed around.
6. **NO_CERTIFICATE layer**: still untouched — this experiment produces no statistical guarantee, only recall numbers. The certificate replication budget gap (~500 events needed vs 51 available) is unchanged.

---

## 6. What this changes about the project status

### Re-statements that survive

- "Hand-crafted cheap proxies cannot close +0.10 random-delta at B=20 **on a single-axis budget B**" — V13.9 claim — **HOLDS**.
- "Uniform selection is the best static method at B=20" — V13.9 claim — refuted: it is the best only *ignoring `object_count_mean`*; with it, top_obj_mean wins (0.157 vs 0.137). The V13.9 method enumeration was incomplete.
- "Adaptive local refinement cannot beat best static on this proxy" — V13.10 claim — **HOLDS** even with the principled confirmed-positive rule. Not just a proxy-quality result; the data structure (events cluster tightly around few hot zones) makes local refine redundant.
- "OracleBest far above static methods at B=20/40" — V13.10 claim — **partially holds**: the gap closes 10–13 pp from 0.35→0.45 / 0.275→0.40.

### New claims from this experiment (Bonferroni-defensible)

1. **Budget decomposition matters independently of proxy quality.** Splitting `proxy_top(P=2B)` from `oracle_examine(B)` with mild temporal-spread diversity raises V13.8 anchor-event-recall at fixed oracle budget on the same cheap proxies. At B=40 the gain is +0.098 absolute / +45 % relative and is Bonferroni-significant. The single-axis-`B` framing in V13.9/V13.10 systematically understated reachable recall.
2. **Cheap proxy signal saturation is real** but the operational problem is partly DB-side (coverage), not perceptual. A DB-style **max-coverage-greedy within prefilter** method is a candidate DB-side contribution. It does not require a better detector.
3. **`object_count_mean` is the missing V13.9 top-B method**. It should not have been omitted. The narrow conclusion "no cheap proxy gives low-budget recall" depends on which cheap proxies were tried.
4. **H2 multi-signal max-pool fails** despite per-class AUC differences. The predicate heterogeneity observed in the read-only exploration does not translate to budgeted-AQP gains via signal fusion alone; it would require per-object-class proxy features (e.g. pedestrian-count + lateral-position scores) that are not yet in `proxy_features.csv` — i.e., a motion/geometry proxy still needs to be physically built.

### What this experiment does NOT establish

- The +0.10 random-delta "AQP feasibility threshold" at B=20 — still not met by the diversity method (only +0.088 mean delta, +0.000 p99.8 delta).
- A statistical certificate — this is a recall result, not a guarantee.
- Any generalization beyond this single video.
- Any improvement over **strong** future proxies. If ego-path geometric or 8B cascade proxies turn out to have AUC much higher than 0.74, the diversity-fusion may be additive but might not (need a separate run once those features exist).

---

## 7. GO / WEAK_GO / NO-GO

**WEAK_GO.**

Rationale:
- The single strictly Bonferroni-significant operating point at B=40 (best 0.314 vs random p99.8=0.306) is meaningful because B=40 is well within the budget regime where OracleBest@40=0.784 — recall moves the operation point from "essentially all sampled anchors miss events" to "half the events covered per oracle call".
- The matching efficiency improvement vs V13.10 (0.275→0.400 at B=40) materially falsifies the "static methods are far below upper bound **because proxies are weak**" cause-of-failure attribution. Part of the gap is a budget-framing artifact.
- Cannot be GO because B=20 ties the random p99.8 (does not pass) and the "single-axis B" framing improvement is partly confounded with the untested `object_count_mean` base.

---

## 8. Next minimum experiment (no new VLM)

Given that budget-decomposition alone buys ~0.10 recall B=40 on this single video, the next non-trivial tests on the same V13.8 oracle are:

1. **Stratified-diversity with K targets**: instead of `score + α·min_dist`, use `max_coverage` over temporal windows (greedy set-cover with proxy-weighted anchors). Should reach OracleBest-adjacent at low B if K &lt;= cluster count (~28 at 30s gap).
2. **Combined H1 with object_type_conditioned proxy** once a pedestrian-count OR lateral-motion feature is added to `proxy_features.csv` (a CPU pipeline, no VLM needed; requires re-running YOLO with class `pedestrian` / `cyclist` bbox filtering on cached center10 clips).
3. **Certificate B1-no-repair simulation on V13.8 oracle**: with the now-better recall (0.314 at B=40), test whether a ≥30%-recall → LCB ≥ 0.17 certificate can be issued. Even a vacuous narrow LCB demonstrates the statistical layer can produce output; necessary for paper claim about "conservative oracle-relative recall".
4. **Second video**: the budget-decomposition finding needs at least one other clip to claim generality — the failing-cost condition is "if on a second long video uniform / diversity / proxy all collapse together, single-video effects dominate the V13 finding".

Failure condition to abandon H1 as the main DB-side contribution: if on a second diverse video the diversity-helps gain collapses to ≤ +0.03 absolute or worse than a uniform baseline.

---

## 9. Files written by this experiment

```
garc_eval/outputs/diversity_prefilter_replay_v1/
├── scripts/
│   └── run_diversity_prefilter_replay.py
├── tables/
│   ├── method_budget_results.csv        # all methods × all budgets (includes random 200×)
│   ├── method_selected_anchors.csv      # per-method per-B anchor selections
│   ├── random_baseline_summary.csv      # 200-reply random mean/std/CI per B
│   ├── best_methods_by_budget.csv       # best non-random method per B + delta vs random
│   ├── h_method_results.csv             # all H1/H2/H3 results only
│   ├── delta_summary.csv                # per-tag best vs random vs base
│   ├── decision.csv                     # initial (single-comparison) decision
│   ├── decision_bonferroni.csv          # multi-comparison-corrected per-B decisions
│   └── decision_overall.json           # overall: WEAK_GO
├── logs/
│   └── sanity_and_run.log               # sanity checks, seed, wall time, input paths
└── reports/
    └── FINAL_REPORT.md                  # this report
```

No existing CSV, video, VLM labels or scripts were modified.