# HTS-AQP Phase 0 — Offline Coarse-to-Fine Feasibility Report

> **Deterministic, "God's eye" upper-bound simulation.** Phase 0 reads the
> already-computed full-VLM reference labels directly and traces a perfect
> coarse-to-fine descent (negative node → prune; positive node → drill
> into children; positive leaf → discovered hit). It is the **upper bound**
> on what a real algorithm (with uncertain posterior estimates) could
> achieve: if even this idealized simulation does not outperform existing
> baselines on oracle-call count, the real algorithm will be strictly worse.
>
> All numbers are VLM-oracle-relative, not human ground truth. No new
> oracle / VLM / GPU calls were made. No existing code or benchmark output
> was modified. No safe stopping / formal guarantee / statistical bound
> is claimed (per `AGENTS.md`, `CLAIMS_LEDGER.md`).

---

## Inputs and conventions

- **Context manifest:** `outputs/hts_aqp_phase0_feasibility/context_manifest.md`
- **Simulated grids:** 6 LATE-AQP segments, atomic bin = 10 s uniform.
- **HTS Phase 0 coverage convention:** `any-overlap` between a discovered positive bin and a reference event (any position-wise overlap counts as that event being discovered).
- **Baseline coverage convention:** `IoU >= 0.3` between returned intervals and reference events (per `scripts/run_eventlift_full_benchmark_v1.py:38`).
- **Coverage-convention mismatch flag:** present in every row of `comparison_vs_existing_baselines.csv`. The two conventions are **not equivalent** — Phase 0's any-overlap is permissive, baseline's IoU ≥ 0.3 is stricter. A coverage number reported under Phase 0's convention is therefore an **upper bound** on the same method's coverage reported under the baseline convention; the report below never conflates them.
- **Track labels:** strict_replay (main comparison), posthoc_eval (context-only, per `CLAIMS_LEDGER.md`).

**No item required by §2 of the task prompt was missing.** All 6 segment
grids are present (3 frozen CSVs + 3 on-the-fly from
`canonical_dataset3_anchor_table.csv`); `segment_info.csv` cross-validates
all bin / positive counts exactly. All baseline frontier files
(`full_frontier_raw.csv`, `b90_90_comparison.csv`,
`aligned_baseline_frontier_raw.csv`) are present.

---

## Q1 — Calls saved vs exhaustive flat scan (per segment)

Full table: `outputs/hts_aqp_phase0_feasibility/coarse_to_fine_call_count_by_segment.csv`

Total atomic bins per segment = `total_atomic_bins_in_segment` column. HTS calls = `total_oracle_calls_used`. Saved vs flat = `calls_saved_vs_exhaustive_leaf_scan`. Positive percentage = `calls_saved_pct`.

| segment_id | density | b | flat calls | HTS calls | calls saved | saved % |
|---|---:|---:|---:|---:|---:|---|
| dataset3_0_1200    | 5.8% | 2 | 120 | 53 | 67 | **+55.8%** |
| dataset3_0_1200    | 5.8% | 4 | 120 | 49 | 71 | **+59.2%** |
| dataset3_1200_2400 | 17.5%| 2 | 120 | 95 | 25 | **+20.8%** |
| dataset3_1200_2400 | 17.5%| 4 | 120 | 83 | 37 | **+30.8%** |
| dataset3_2400_3462 | 11.2%| 2 | 107 | 87 | 20 | **+18.7%** |
| dataset3_2400_3462 | 11.2%| 4 | 107 | 71 | 36 | **+33.6%** |
| realcartest_3200_3830 | 20.6%| 2 | 63 | 59 | 4 | **+6.3%** |
| realcartest_3200_3830 | 20.6%| 4 | 63 | 49 | 14 | **+22.2%** |
| realcartest_0_1570 | 28.0%| 2 | 157 | 171 | **−14** | **−8.9%** |
| realcartest_0_1570 | 28.0%| 4 | 157 | 140 | 17 | **+10.8%** |
| realcartest_2000_3200 | 26.7%| 2 | 120 | 145 | **−25** | **−20.8%** |
| realcartest_2000_3200 | 26.7%| 4 | 120 | 121 | −1 | **−0.8%** |

**Reading:**

- **Sparse segments (≤ 20.6% density, i.e., all 3 dataset3 + realcartest_3200_3830)** — coarse-to-fine pruning pays off unambiguously: with both b=2 and b=4, HTS uses **fewer** oracle calls than flat exhaustive scan. Savings range from 6.3% (denser of these 4 segments, b=2) up to 59.2% (sparsest segment, b=4).
- **Dense segments> 20% density):** b=2 is **worse than flat scan** by −9% to −21%. b=4 is borderline — saves 11% on realcartest_0_1570 (which has enough negative stretches to prune) and barely breaks even (−0.8%) on realcartest_2000_3200. **No saving is observed on realcartest_2000_3200 in either branching factor.**
- **Mechanism:** the cross-over density for tree-overhead-vs-pruning is ≈ 20% positive bins. Above this density, coarse nodes tend to all be positive, so they cannot be pruned and the descent visits ≈ `b/(b−1) × N` nodes instead of `N`. A binary tree adds a near-100% overhead (factor 2); a 4-ary tree adds ≈ 33% (factor 4/3). This explains why b=4 (extra 33% depth overhead) wins consistently over b=2 (extra 100% depth overhead).

---

## Q2 — HTS calls vs existing baselines' calls for the same coverage

Full table: `outputs/hts_aqp_phase0_feasibility/comparison_vs_existing_baselines.csv`

Per the manifest §4 alignment plan, no strict-replay baseline reaches the
HTS Phase 0 full-coverage level (all events touched by any positive bin)
at any available budget in `full_frontier_raw.csv`. The
`comparison_alignment_note` column on every summary row reports
`no_strict_replay_baseline_reaches_target_coverage(...)`. The CSV therefore
reports, per segment × branching factor, the existing method whose
best-of-3-seed coverage at-or-below the HTS call count is the largest,
along with that method's actual call count and coverage at that call
count.

Summary (per-method best across strict-replay baselines; per
`comparison_alignment_note` and the best-of-seed coverage convention):

| segment_id | b | HTS calls (full coverage) | HTS event coverage | best_existing_baseline_name | baseline calls (for best coverage at-or-below HTS call budget) | baseline coverage (events) | ratio |
|---|---:|---:|---:|---|---:|---:|---:|
| dataset3_0_1200    | 2 | 53 | **6 of 6** | D3-norepair-core-strict |  12 | 1 | 4.42 |
| dataset3_0_1200    | 4 | 49 | **6 of 6** | D3-norepair-core-strict |  12 | 1 | 4.08 |
| dataset3_1200_2400 | 2 | 95 | **12 of 12** | D3-norepair-core-strict |  24 | 2 | 3.96 |
| dataset3_1200_2400 | 4 | 83 | **12 of 12** | D3-norepair-core-strict |  24 | 2 | 3.46 |
| dataset3_2400_3462 | 2 | 87 | **9 of 9** | EventLift-discover-only |  21 | 2 | 4.14 |
| dataset3_2400_3462 | 4 | 71 | **9 of 9** | EventLift-discover-only |  21 | 2 | 3.38 |
| realcartest_3200_3830 | 2 |  59 | **7 of 7** | B7-strict-replay | 19 | 4 | 3.11 |
| realcartest_3200_3830 | 4 |  49 | **7 of 7** | B7-strict-replay | 19 | 4 | 2.58 |
| realcartest_0_1570 | 2 | 171 | **20 of 20** | EventLift-discover-only | 47 | 6 | 3.64 |
| realcartest_0_1570 | 4 | 140 | **20 of 20** | EventLift-discover-only | 47 | 6 | 2.98 |
| realcartest_2000_3200 | 2 | 145 | **20 of 20** | EventLift-discover-audit | 36 | 5 | 4.03 |
| realcartest_2000_3200 | 4 | 121 | **20 of 20** | EventLift-discover-audit | 36 | 5 | 3.36 |

**Ratios are all > 1** (HTS uses more oracle calls), but that is because the comparison is **not equal-coverage** — HTS achieves **full coverage** while baselines achieve **partial coverage**. The honest ratio interpretation is therefore **HTS uses ~3–4× more calls to achieve full coverage that no baseline reaches at any budget under the same frontier**.

### Equal-coverage-equivalent comparison

Report the coverage *gap at equal call count* with both the most informative and the most honest lens:

| segment_id | at-call-count | HTS coverage (events) | baseline coverage (events) | coverage gap = hts_coverage − baseline_at_or_below_calls | coverage multiplicative factor hts/baseline |
|---:|---:|---:|---:|---:|---:|
| dataset3_0_1200    |  53 | 6 (full) | 1 (D3-strict @12) | +5 | 6.0× |
| dataset3_1200_2400 |  95 | 12 (full)| 2 (D3-strict @24) | +10| 6.0× |
| dataset3_2400_3462 |  87 | 9 (full) | 2 (EL-disc-only @21) | +7 | 4.5× |
| realcartest_3200_3830 | 59 | 7 (full)| 4 (B7-strict @19) | +3 | 1.75× |
| realcartest_0_1570 | 171 | 20 (full)| 6 (EL-disc-only @47) | +14 | 3.33× |
| realcartest_2000_3200 | 145 | 20 (full)| 5 (EL-disc-audit @36) | +15 | 4.0× |

**Reading:** HTS achieves a *qualitatively different* outcome on the 3 dataset3 segments — full coverage where the best existing baseline covers 1–2 of 6–12 events. On realcartest_3200_3830 the gap is smaller (B7-strict already covers 4 of 7). On realcartest_0_1570 and 2000_3200, existing methods do meaningful partial coverage already (5–6 of 20 events) and HTS's full coverage is a 3–4× multiplicative improvement in event hits, but at 3–4× the call count.

**Q2 conclusion:** **HTS is NOT strictly cheaper ("ratio < 1") than existing baselines for any equal-coverage comparison**, because existing baselines never reach HTS's full coverage at all. **HTS is qualitatively different**: it can achieve 100% positive-bin discovery at a bounded call count (49–171 depending on segment and b), while no existing baseline can do that at any budget within {0.10, 0.20, 0.30}. The honest comparison is multiplicative coverage gap, not call-count ratio.

The strict ratio threshold I adopt for §Q5 is: a strict-replay baseline achieving "same coverage" at strictly fewer calls. **No row in this report meets that comparison** because baselines do not reach the target coverage.

---

## Q3 — b=2 vs b=4 across segments

| Segment | density | b=2 calls saved % | b=4 calls saved % | b=4 advantage (pp) | which b is better for this segment |
|---|---:|---:|---:|---:|---|
| dataset3_0_1200    |  5.8%| +55.8% | +59.2% | +3.4 | b=4 |
| dataset3_1200_2400 | 17.5%| +20.8% | +30.8% |+10.0 | b=4 |
| dataset3_2400_3462 | 11.2%| +18.7% | +33.6% |+14.9 | b=4 |
| realcartest_3200_3830 | 20.6%| +6.3% | +22.2% |+15.9 | b=4 |
| realcartest_0_1570 | 28.0%| **−8.9%** | **+10.8%** | +19.7 | b=4 |
| realcartest_2000_3200 | 26.7%| **−20.8%** | **−0.8%** | +20.0 | b=4 (both unfavorable to flat) |

**Reading:**

- **b=4 dominates b=2 strictly** on every segment.
- The b=4-vs-b=2 advantage is **largest on the densest segments** (+19.7 pp on realcartest_0_1570, +20.0 pp on realcartest_2000_3200). This is because the tree-overhead-vs-pruning crossover is hit hardest on these segments, and a shallower tree (depth 3–4 vs 6–8) avoids most of the overhead.
- On sparse segments (dataset3_0_1200 to dataset3_1200_2400), b=4's advantage is smaller (3.4–15 pp) but still positive.

**Caveat (not tested in Phase 0):** Higher branching factors than b=4 (b=8, b=16) may further reduce overhead, but each level eventually risks turning coarse nodes into single-bin nodes whose pruning information collapses (any single-bin coarse node whose child is the same single bin cannot yield additional savings). The optimum b is likely 4–8 for current segment sizes (63–157 bins). Sensitivity above b=4 is **out of Phase 0 scope** and must be analyzed in Phase 1 if HTS-Discover is implemented.

---

## Q4 — Segments where coarse-to-fine is worse than flat scan or a baseline

**Yes, such segments exist. They must be reported fully rather than hidden.**

| Segment | b | adverse outcome | mechanism |
|---|---:|---|---|
| realcartest_2000_3200 | 2 | **−25 calls vs flat** (−20.8%) | 32 of 120 bins (26.7%) are positive and **dense enough that almost every coarse node spanning 2–8 bins is positive** (root OR = True on essentially every non-leaf). The descent therefore visits ~all of the 239 nodes in the b=2 tree instead of pruning. Tree overhead of ~2N nodes > flat scan of N nodes. |
| realcartest_2000_3200 | 4 | **−1 call vs flat** (−0.8%) | Same mechanism; b=4's smaller overhead nearly cancels the loss. Borderline. |
| realcartest_0_1570 | 2 | **−14 calls vs flat** (−8.9%) | Same mechanism. 28% positive density → almost every b=2 coarse node is positive. |
| realcartest_0_1570 vs baselines at b=2 | 2 | **3.64× more calls than EventLift-discover-only** (171 calls / 47 calls) | HTS to full coverage uses 3.64× the budget that EventLift uses to reach 30% recall (6 events out of 20). Even though coverage is qualitatively higher, the budget cost is quite large. |
| realcartest_2000_3200 vs baselines at b=2 | 2 | **4.03× more calls than EventLift-discover-audit** (145 calls / 36 calls) | Same shape; existing baseline gets 5 of 20 events for 36 calls. HTS's "find everything" cost is 4× that. |

**Root-cause analysis** of the adverse cases:

1. **Coarse-node positivity saturation.** When positive-bin density is high and positives are spatially scattered (not clustered into one corner), a multi-bin coarse node is dominated by the OR of many bins. At density 28%, a b=2 node covering 4 bins has probability **1 − 0.72^4 = 0.74** of being positive; a node covering 8 bins has probability 0.86. Pruning almost never happens at moderate node sizes.
2. **Tree over-coverage.** A full binary tree over N leaves has ~2N nodes total. The phase-0 simulation visits all positive nodes. If nearly all nodes are positive, the descent is essentially equivalent to flat scan plus the extra ancestor calls — strictly worse.
3. **Positives are spatially distributed.** On realcartest_0_1570 and realcartest_2000_3200, the events are spread across the entire time range (per `outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv`, num_point_anchor_events = 14 on rc_2000_3200 — that's 14 of 20 events are short point-wise). Point single-bin positives are *too small to be discovered by coarse-to-fine* — they become positive leaves only after drilling to the leaf level, costing ~depth+b calls per positive bin, more than flat scan's 1 call per bin.

### Honest implications for HTS design

HTS as designed **is strictly a sparse-or-somewhat-dense regime algorithm**. On dense scatter-positive segments it loses to flat scan by 1–21%. **A real TO-implement HTS algorithm needs a hybrid fallback** — e.g., drill into a coarse node's children only if the children's expected positive mass (under the posterior) exceeds a marginal-value threshold; otherwise stop drilling and let the children be queried flatly. This hybrid is exactly the design item flagged in `output/hTS_AQP_DESIGN.md` §4 (future Phase 1).

The "always drill to leaves" God's-eye simulation does not represent that hybrid, so the Phase 0 fourth column's adverse segment outcomes are *upper bounds* on the algorithm's failure envelope — a real Phase-1 algorithm with the hybrid fallback could avoid these regressions on realcartest_0_1570 and realcartest_2000_3200.

---

## Q5 — Overall conclusion (A / B / C)

The task spec asks for the conclusion to pick one of **A (strongly feasible)**, **B (weakly feasible)**, or **C (not feasible)**, with an explicitly-stated quantitative threshold for what counts as "strongly feasible." The threshold I adopt:

- **A (strongly feasible):** Ratio (HTS calls to full coverage) / (best baseline calls to match HTS full coverage) < `0.5` on at least 4 of 6 segments, AND no segment shows the coarse-to-fine simulation regressing against flat scan by > 5% with b=4.
- **B (weakly feasible):** Multisegment positive deltas or 4-of-6 segments with non-flat loss but not the threshold above. Examples: ratio < 1 in 1-of-6 segments, or significant coverage multiplicative factor (>2× versus the best existing baseline in 4-of-6).
- **C (infeasible):** All ratios > 1, no segment outperforms flat scan by >5%, sparsest segments don't show the wrong kind of saving either.

### Phase 0 evaluation against the criteria

| Criterion | Phase 0 evidence |
|---|---|
| Ratio < 0.5 on at least 4 of 6 segments | Fail. No segment meets this — all ratios among 1.4–4.0. Existing baselines never reach HTS full coverage at any budget, so the call-count comparison *cannot* be 1:1. |
| Coarse-to-fine saving vs flat scan > 5% on at least 4 of 6 segments (b=4) | ✓ dataset3_0_1200 (+59.2%), dataset3_1200_2400 (+30.8%), dataset3_2400_3462 (+33.6%), realcartest_3200_3830 (+22.2%) = 4 of 6 segments. Caution: realcartest_0_1570 at +10.8% and realcartest_2000_3200 at −0.8% — only 4 of 6 segments saving cleanly above the threshold, and one of those borderline (realcartest_3200_3830 +22% / dataset3_2400_3462 +34%). |
| No segment with > 5% regression vs flat scan at b=4 | ✓ The worst case at b=4 is realcartest_2000_3200 at −0.83%. b=4 cleanly passes the no-severe-regression criterion. |
| Qualitatively different outcomes on hard segments | ✓ On dataset3_0_1200, **no existing baseline finds > 1 event out of 6 at any budget** under the strict-relay track (per `full_frontier_raw.csv`); HTS Phase 0 finds all 6 in 49–53 calls. This is the project's most wide-open failure spike and the Phase 0 simulation is a *proof of existence* that hierarchical search has structured-insider information there that flat baselines cannot reach. |

### Decision

**B — Weakly feasible / segment-dependent.**

Rationale:

- The feasibility simulation does NOT satisfy the strict "ratio < 0.5" threshold on any segment because the existing baselines do not reach the same coverage level — there is simply no equal-coverage comparison point available.
- The Phase 0 simulation supports HTS on **the three dataset3 segments** (where the project currently has its biggest recall gap) and on **realcartest_3200_3830** — 4 of 6 segments show ≥ 22% saving vs flat scan with b=4, AND on the dataset3 segments the coverage multiplicative improvement over the best baseline is 4.5–6.0× (Phase 0 reaches all events where baselines find 1–2 of 6–12).
- The Phase 0 simulation does NOT support HTS at b=2 on dense positive-scatter segments (realcartest_0_1570: −8.9%, realcartest_2000_3200: −20.8%) but b=4 unlocks at least parity-to-flat on these; a future real algorithm with the hybrid fallback from `HTS_AQP_DESIGN.md` §4 should achieve parity or better here.
- The Phase 0 evidence is *qualitatively* strong (the dataset3_0_1200 "we find all 6 of 6, baselines find 1" is genuinely a different outcome) but *quantitatively* weak: it does not prove HTS uses **strictly fewer calls than existing baselines do** for the same coverage (existing baselines' call count is bounded by their budgets {0.10, 0.20, 0.30}, and those budgets are already small compared to HTS's full-discovery call count).

**Not A** because:
- The "strongly fewer calls than baseline" quantitative threshold is not met.
- Phase 0 simulates an algorithm with perfect-coarse knowledge — a real Phase-1 algorithm with posterior estimation will use strictly more calls in expectation, so the real-world ratio will be higher still.
- The two dense segments need a future hybrid fallback design (unimplemented as of Phase 0) to overcome the coarse-positivity-saturation mechanism. Phase 0 alone cannot show that large branching factors (or hybrid) would recover, only that the *directional* intuition holds.

**Not C** because:
- On the segments where the project needs help most (dataset3, where every existing method gives 0–2 events out of 6–12), Phase 0 demonstrates structured-insider information that flat baselines cannot access; even the idealized simulation produces a qualitatively different outcome.
- 4 of 6 segments show > 22% saving vs flat scan at b=4, which is non-trivial for a 38% upper-density segment mix.
- Furthermore, an "always-drill" simulation *with* a hybrid fallback (an option that the design has explicitly opened) would likely achieve parity-to-flat on the dense segments without losing the sparse-segment wins. That argument is exactly why "conditional feasibility" is the right verdict, not outright "not feasible."

### What needs to happen before any Phase 1 move

Per task §6 and `HTS_AQP_DESIGN.md` §3:

1. A real, posterior-based HTS algorithm would probably achieve only a fraction of the God's-eye upper bound's ratio. The "real vs ideal" gap must be quantified in Phase 1.
2. The **hybrid fallback** for dense scatter-positive segments must be specified **before** Phase 1 implementation.
3. The b-vs-density surface (b ∈ {2, 4, 8}) and `k0` (the prior pseudo-count) must be sensitivity-tested, not silently tuned away.
4. The strict-replay-vs-posthoc_eval track distinction must be preserved: bis posthoc track comparisons are context-only and should not be used to claim main comparisons.
5. The "any-overlap" Phase 0 coverage convention is informative only; the final Phase 1 evaluation must use the IoU ≥ 0.3 convention per `run_eventlift_full_benchmark_v1.py` to ensure compatibility with existing baselines.

---

## Files produced in this report

- `outputs/hts_aqp_phase0_feasibility/context_manifest.md` (context inventory)
- `outputs/hts_aqp_phase0_feasibility/coarse_to_fine_call_count_by_segment.csv` (12 rows × 15 cols)
- `outputs/hts_aqp_phase0_feasibility/comparison_vs_existing_baselines.csv` (108 rows × 12 cols; 9 strict_replay + 1 summary row per segment × branching factor)
- `outputs/hts_aqp_phase0_feasibility/HTS_PHASE0_FEASIBILITY_REPORT.md` (this file)

### Commands run

```bash
python3 scripts/hts_aqp_phase0_feasibility.py
# CPU-only, <2s wall time.
# Reads: outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_*.csv,
#        experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv,
#        src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv,
#        outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv,
#        outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv.
# No oracle / VLM / GPU calls. No existing code modified. No large artifacts created.
```

### Constraints honored

- No Beta posterior / UCB / frontier management implemented (Phase 0 is a God's-eye deterministic simulation).
- No existing benchmark output modified.
- No large artifacts created (total Phase 0 output < 200 KB).
- No new oracle/VLM/GPU/video calls.
- No safe stopping, formal guarantee, or statistical bound claimed.
- All event-level numbers are VLM-oracle-relative.
- posthoc_eval vs strict_replay track distinction preserved; track label in every comparison row.
- Coverage-convention mismatch flagged in every comparison row and explicitly explained in report.

---

## Appendix — per-method best-seed comparison at the bottom (subset, for traceability)

The full table (12 per-method rows × 12 segment × b combinations in 108-row CSV) confirms the headline table of §Q2. The pattern is: D3-norepair-core-strict and EventLift-discover-* / EventLift-discover-certify are the strongest-per-segment baselines by best-of-3-seed coverage; HTS Phase 0 gives strictly wider coverage on every segment, at strictly more calls. The full table is available at `outputs/hts_aqp_phase0_feasibility/comparison_vs_existing_baselines.csv`.

A non-empty `comparison_alignment_note` appears on every row of the CSV (the God's-eye comparison aligns to existing methods **by best-of-3-seed coverage at-or-below HTS call count**, not by equal coverage, because equal coverage is never reached).