# Proxy Bias & Doubly-Robust (DR) Feasibility Diagnosis

> **Read-only diagnosis.** No new oracle / VLM / YOLO / GPU run. No
> EventLift parameter tuned. No benchmark output modified. No large artifact
> created. All recall/precision class claims are intentionally avoided here;
> this document does **not** claim any new SOTA, safe stopping, formal
> guarantee, or statistical bound. All event-level matches use the same
> VLM-oracle-relative labels (`center10_vlm_oracle_events.csv` /
> `canonical_dataset3_anchor_table.csv`) already used by the EventLift full
> benchmark v1. Track: strict_replay for all online analyses. Reference-event
> matching is offline-only and is flagged as such in every CSV.

> The DR / AIPW estimator family used in this note is **not a novel statistical
> invention**; it is the standard doubly-robust / augmented inverse-propensity-weighting
> estimator (`M_DR = Σ p_model(c) + Σ_{c∈audit} (y_c − p_model(c)) / π_c`).
> Any contribution of an EventLift-DR direction would be the *application* of a
> design-based audit correction to an event-level AQP discovery posterior, not
> the estimator itself.

---

## Executive conclusion

| Gate | Decision | One-line evidence |
|---|---|---|
| **A** proxy bias diagnosis | **PASS** | Missed positive bins are concentrated outside the top-30% proxy stratum (mean over segment×method = 0.682); in bottom-50% proxy stratum (mean = 0.528). Realcartest proxy AUC ∈ [0.68, 0.78]; dataset3 proxy AUC ∈ [0.31, 0.56] (weak). |
| **B** DR variance feasibility | **CONDITIONAL** | With the **deployable** per-stratum-LOO p_model, ≥20% RMSE reduction vs model-only holds on **1/6 segments** (dataset3_0_1200); DR beats ABae-residual on 2/6. With the **raw-minmax strawman**, 3/6 segments show big DR wins on realcartest, but only because the model-only baseline is *itself* badly miscalibrated (proxy mean ≈ 0.91 for positives ≈ 0.71 for negatives on realcartest_0_1570). The aggregate "≥4/6 PASS" only emerges when crediting that strawman. |
| **C** forced audit floor prior | **PASS** (borderline) | Audit-as-dual-use (positive recovery + bias correction) is conceptually different from the three prior failed/neutral forced-exploration routes (v2 `cold_start_fallback`, `hybrid_coldstart`, D3 repair-vs-norepair-neutral). The **only** meaningful difference between EventLift-DR and those priors is this dual-use framing; it is empirically grounded (Gate A) but only *conditionally* statistically tractable (Gate B). |

**Recommendation:** **A — Proceed to a TARGETED EventLift-DR ablation prototype, as a design-only next step, awaiting explicit human authorization.** Per the task's hard constraints: do **not** implement EventLift-DR yet. Per `AGENTS.md` + `FAILURES.md`: any future prototype must NOT replace the default `score_topk + temporal NMS + duration cap` selector; it must be a strictly separate ablation path; audits used for correction must be isolated from samples used to drive selection / repair.

Concretely the targeted scope (from Gate B's disaggregated evidence):

- **In scope:** dataset3_0_1200 (proxy AUC = 0.31, 5.8% density) and dataset3_1200_2400 (proxy AUC = 0.46); both already-severe failure segments per `EVENTLIFT_RESULTS_SYNTHESIS.md` §7 / `FAILURES.md`.
- **Out of scope:** realcartest_0_1570, realcartest_2000_3200, realcartest_3200_3830, dataset3_2400_3462 — proxy AUC ≥ 0.56 and DISCOVER/CERTIFY already rank positives well; DR correction variance dominates the bias there (see `dr_variance_feasibility.csv` rows: `correction_term_sd` >> `|model_only_signed_error|`).
- **Audit budget in scope:** audit shares ∈ {0.10, 0.20} only; the Monte-Carlo trace shows audit share ≥ 0.30 does **not** further help (saturates near pooled-binomial variance) and would consume discovery budget needed for the proxy still ranks positives.

---

## 1. Historical prior: forced exploration has failed before

Per `FAILURES.md` and the cross-referenced `outputs/late_aqp_*` reports, three
prior routes share the structural shape of "an audit / exploration / repair
floor that competes with discovery for the same oracle budget":

| Route | Status | Why failed/neutral | Source |
|---|---|---|---|
| Phase 3 fixed cheap-signal selector | NEGATIVE | Det. ranking on cheap features underperforms uniform-random at B=40; signal is *not* convertible to budgeted return-set coverage via a different ranking function. | `outputs/agent_loop_v1/phase3_selector_smoke_v1/` |
| Frozen-LATE-AQP-v2 `cold_start_fallback` on original failure segments | FAIL | Substantive improvement 0/3 segments at both B=10 and B=20. Refined audit schedule did not solve low-budget. | `outputs/late_aqp_v2_original_segment_verification/` |
| `hybrid_coldstart` (r=0.5 blending) | FAIL | Blending exploration and exploitation in cold-start did not fix low-budget on original failure segments. | `outputs/late_aqp_hybrid_coldstart_v1/` |
| D1 / D2 / D3 discovery vs B7-core on B_90/90 | No stable win | No LATE variant beats B7-core-posthoc on B_90/90. | `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` Q4 |
| D3-core vs D3-norepair-core (post-fix) | Neutral | After the accounting-bug fix, repair is not consistently additive; marginal value non-positive or zero. | `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md` |
| Algorithm v3 two-phase / leakage-density schedules (strict replay) | Modest only | No audit-schedule / repair-utility combo wins both recall and precision. Repair `source_action` lineage mostly `unknown_not_logged`. | `outputs/late_aqp_algorithm_v3_oracle_relative/FINAL_REPORT.md` Q4/Q5 |

### Mechanisms conceptually similar to a forced audit floor

1. **`hybrid_coldstart`** (r ∈ {0.3, 0.5, 0.7}) — reserves a fraction of cold-start budget for exploration. Fails because the reserved budget is not informative without a *bias correction* utility; it's just less discovery. Most similar to a naive audit floor that has no estimator on top.
2. **D3-core repair** — repair calls consume discovery budget that would otherwise have gone to bandit exploration; post-fix is neutral. Most similar to a forced audit floor that **also** tries to do positive recovery.
3. **V3 two-phase schedule** — two-phase allocation of audit/discovery budget. Modest, not dominant, and `source_action` lineage missing.

### The only meaningful difference EventLift-DR offers

The one structural difference that *was not tested* in those prior routes is
**audit-as-dual-use**: the same audit sample yields two distinct utilities —
(1) positive recovery (offline grouping into returned intervals) and (2)
**bias correction** of the discovery posterior via the DR augmentation term
`Σ (y − p_model) / π`. In D3-core the audit budget was *only* spent on
recovery, so any loss from the audit floor was a pure discovery-budget tax
with no counter-balancing estimator correction. EventLift-DR is the first
candidate mechanism in this project where the audit calls also produce a
*model-correction* signal — which is the only path to recoup the discovery-budget
tax under the small-sample regime that Gate 2 of `RC_AQP_PREFLIGHT.md` already
flagged as statistically weak (`p_ucb(15)=0.181`).

**Do not** brand EventLift-DR as a "new exploration algorithm" or "novel
statistical invention". The estimator is standard DR/AIPW; the novel element
is putting a design-based audit correction onto the event-level AQP discovery
posterior. Whether that dual-use actually recoups the budget tax on the
targeted segments is **not yet established empirically** — this report only
shows it is statistically *plausible* under the constraints (Gate B CONDITIONAL).

---

## 2. Proxy bias diagnosis (Gate A)

Full table: `outputs/eventlift_dr_feasibility/proxy_calibration_by_segment.csv`.

Per-segment proxy (`prior_score_max`, the column EventLift actually uses) quality:

| segment | n_bins | pos_bins | density | proxy AUC | proxy AP | top-30% proxy contains | bottom-50% proxy contains |
|---|---:|---:|---:|---:|---:|---:|---:|
| realcartest_0_1570    | 157 | 44 | 28.0% | **0.777** | 0.530 | 61.4% of positives | 18.2% of positives |
| realcartest_2000_3200 | 120 | 32 | 26.7% | **0.701** | 0.442 | 50.0% of positives | 31.3% of positives |
| realcartest_3200_3830 |  63 | 13 | 20.6% | **0.685** | 0.322 | 53.8% of positives | 30.8% of positives |
| dataset3_0_1200       | 120 |  7 |  5.8% | **0.305** | 0.058 |  0.0% of positives | 100% of positives |
| dataset3_1200_2400    | 120 | 21 | 17.5% | **0.460** | 0.165 | 23.8% of positives | 61.9% of positives |
| dataset3_2400_3462    | 107 | 12 | 11.2% | **0.561** | 0.153 | 33.3% of positives | 41.7% of positives |

Key observations:

- AUC/AP are computable on every segment (each has both classes; no NaN case). Computed via `sklearn.metrics.{roc_auc_score, average_precision_score}` on the bin-level `is_positive` vs `prior_score_max`.
- The realcartest proxy ranks positives well (AUC ∈ [0.68, 0.78]) and ~50–61% of positives sit in the top 30% of proxy bins — so proxy-guided discovery is plausibly effective there. This matches EventLift's empirical win on `realcartest_0_1570` and `dataset3_2400_3462` per `EVENTLIFT_RESULTS_SYNTHESIS.md`.
- The dataset3 proxy (`prior_score_max = max(0, max(score_yolo_count))` per 10 s bin, identical to `eventlift_stage2_multiseg_smoke.py:load_dataset3_segment`) ranks positives **near-randomly or worse than random** on dataset3_0_1200 (AUC=0.31) and dataset3_1200_2400 (AUC=0.46). On dataset3_0_1200 **all 7 positives sit in the bottom 50% of proxy bins** — proxy guidance is actively anti-informative.
- This is an `EVENTLIFT_RESULTS_SYNTHESIS.md` §8 ("Weak proxy on dataset3") confirmation at the bin level: the score_yolo_count proxy used by EventLift on dataset3 is the upstream failure mode, not the discovery scheduler.

**Why this matters for DR (Gate A → Gate B/B-DR):** the more anti-informative the proxy, the larger `|model_only_signed_error|` is for a calibrated-p_proxy model, and the *more room* there is for the DR correction term `Σ (y − p_model) / π` to recoup bias — but only if the audit allocation reaches those low-proxy *positives*, which is exactly where uniform/stratified audit can land.

### Gate A decision

- avg(over segment × method, 0.30 budget) `frac_missed_outside_top_30pct_proxy` = **0.682** (>0.5).
- avg `frac_missed_in_bottom_50pct_proxy` = **0.528**.
- Weak-proxy (AUC < 0.6) segments: dataset3_0_1200, dataset3_1200_2400, dataset3_2400_3462 (the three segments all 9 methods struggle on per `EVENTLIFT_FULL_BENCHMARK_V1_REPORT.md` §8).

**Gate A: PASS.** Missed positives are concentrated outside top-proxy strata and in low/mid proxy strata, particularly on dataset3. The cause is *not* "discovery scheduler bias" abstracted away from the proxy — it is *proxy lock-in* (EventLift samples via `sqrt(proxy)` importance weighting, so when proxy AUC < 0.5 there is no information channel into discovery).

---

## 3. Found vs missed proxy rank diagnosis

Full tables: `outputs/eventlift_dr_feasibility/positive_rank_by_segment.csv` (bin-level, all seeds aggregated) and `outputs/eventlift_dr_feasibility/missed_event_proxy_rank.csv` (event-level, offline-only, seed 0 traceable view).

### Bin-level (`positive_rank_by_segment.csv`)

Per method (budget 0.30), the bins that any returned interval *overlaps* and that are positive are marked "found"; the remaining positive bins are "missed". The proxy-rank percentile columns report where each missed positive bin sits in the segment's overall proxy ranking (smaller = higher proxy; i.e., a "found" positive should have a small rank if the method is exploiting the proxy well; a "missed" positive's rank tells us if the miss is a proxy-bias gap or a selection failure).

Headline (selected rows; see CSV for all 30):

| segment | method | n_missed_pos | missed_mean_rank_pct | missed_median_rank_pct | frac_missed_outside_top_30pct | frac_missed_in_bottom_50pct |
|---|---|---:|---:|---:|---:|---:|
| dataset3_0_1200       | EventLift-discover-certify | 7 | 0.708 | 0.725 | 1.00 | 1.00 |
| dataset3_0_1200       | B7-strict-replay          | 7 | 0.708 | 0.725 | 1.00 | 1.00 |
| dataset3_1200_2400    | EventLift-discover-certify |17 | 0.595 | 0.600 | 0.94 | 0.76 |
| dataset3_2400_3462    | EventLift-discover-certify | 8 | 0.543 | 0.575 | 0.75 | 0.63 |
| realcartest_3200_3830 | EventLift-discover-certify | 9 | 0.430 | 0.349 | 0.56 | 0.44 |
| realcartest_0_1570    | EventLift-discover-certify |25 | 0.394 | 0.369 | 0.60 | 0.32 |
| realcartest_2000_3200 | EventLift-discover-certify |22 | 0.459 | 0.425 | 0.68 | 0.45 |
| realcartest_2000_3200 | B7-strict-replay          |32 | 0.357 | 0.313 | 0.50 | 0.31 |
| realcartest_3200_3830 | B7-strict-replay          |12 | 0.349 | 0.262 | 0.42 | 0.33 |
| realcartest_0_1570    | B7-strict-replay          |42 | 0.305 | 0.236 | 0.40 | 0.19 |

Reading:

- On dataset3 (all three segments), **all missed positive bins sit outside the top-30% proxy and ≥ 60% sit in the bottom 50% proxy**. The miss is concentrated in regions EventLift's `sqrt(proxy)` sampler deprioritizes. → proxy-lock-in failure mode, not a discovery-scheduler bug.
- On realcartest, B7-strict and D3-strict's `missed_median_rank_pct` is < 0.30 — B7's *missed* positives are mostly in the *high*-proxy region. That means on realcartest the failure is *not* proxy-bias-driven; it is interval-grouping / boundary / expansion depth. B7's high-precision wins on `realcartest_3200_3830` (P=0.722) and EventLift's loss there (`EVENTLIFT_RESULTS_SYNTHESIS.md` §7) cannot therefore be addressed by DR audit correction — that loss is interval-grouping (CERTIFY depth=2 vs B7's k=3).
- **EventLift-discover-certify is meaningfully worse than B7-strict at ranking missed positives** on realcartest_0_1570 (median missed-rank-pct 0.369 vs B7's 0.236). This is *exactly* what the marginal DISCOVER-with-CERTIFY accounting in `RC_AQP_PREFLIGHT.md` Gate 1 warned about: CERTIFY consumes budget that B7 instead spends on extra temporal expansion. It is not a proxy-bias gap on realcartest.

### Event-level (`missed_event_proxy_rank.csv`, offline-only)

Per `positive_rank_by_segment.csv`'s last two columns, `n_ref_events_found` / `n_ref_events_missed` are aggregated across seeds (offline-only event mapping via IoU ≥ 0.3 against `center10_vlm_oracle_events.csv` for realcartest and `canonical_dataset3_anchor_table.csv` events for dataset3). **Avoid claiming these are recall/precision** — they are diagnostic counts of which reference events an interval set touches.

On dataset3_0_1200 (seed 0): every method misses ~6 events out of 6 reference events at budget 0.30 — and misses have mean proxy rank percentile ≈ 0.708–0.725 (i.e., bottom 30%). **Confirming Gate A**: the failure is the proxy not ranking the 7 positives.

### Special focus: dataset3_0_1200 / dataset3_1200_2400 / dataset3_2400_3462

- dataset3_0_1200: **0 gain** for any method except B7/D3-strict's symbolic 1/6. Missed bins are 100% in bottom-50% proxy. The segment is at the proxy-AUC 0.31 wall — neither discovery scheduler nor CERTIFY expansion can recover positives the proxy deprioritizes. This is exactly where DR audit correction is *statistically* able to help (Gate B §4 below).
- dataset3_1200_2400: EventLift-discover-certify finds positives of mean proxy 0.640 (because the few positives it does find are high-proxy segment anchors), but **the missed positives have mean proxy 0.014** and 94% of missed positives are outside top-30% proxy. The proxy is itself poor (AUC 0.46) — DR can in principle help here, but Gate B's Monte-Carlo shows correction SD ≈ 17.5 vs model bias |1.8|; DR **hurts** this segment unless the audit allocation is much larger.
- dataset3_2400_3462: missed positives have mean proxy 0.569 (mid-tier), 62.5% in bottom-50% proxy. Proxy AUC = 0.56 — borderline. DR correction SD 13.4–14.8 beats model bias 9.5–11.9 only narrowly under the strawman-minmax calibration; under deployable LOO it loses. **Out of scope for DR** even though Gate A passes; the proxy is too good for DR to win.

### Failure mode attribution

Synthesizing `positive_rank_by_segment.csv`:

| Segment | Dominant failure mode | DR fixability |
|---|---|---|
| realcartest_0_1570    | poor *selection* (CERTIFY budget diversion vs B7's expansion) | low (proxy already good) |
| realcartest_2000_3200 | mid-proxy missed positives + interval grouping | low |
| realcartest_3200_3830 | interval grouping (B7's k=3 expansion better than CERTIFY depth=2) | low |
| dataset3_0_1200       | **proxy-bias / proxy lock-in** | **.drivable** (Gate B win) |
| dataset3_1200_2400    | proxy-bias BUT correction variance dominates | conditional |
| dataset3_2400_3462    | weak proxy mid-tier + interval grouping | low |

---

## 4. DR estimator feasibility arithmetic (Gate B)

Full table: `outputs/eventlift_dr_feasibility/dr_variance_feasibility.csv` (432 rows = 6 segs × 3 budgets × 4 audit shares × 2 stratum counts × 3 p_models).

### Setup

- record / component = single 10 s bin; `y_c ∈ {0,1}` = `is_positive`.
- true total positive mass = `Σ y_c` per segment (per `segment_info.csv`: 7, 21, 12, 13, 32, 44).
- For each (segment × budget_ratio ∈ {0.10, 0.20, 0.30} × audit_share ∈ {0.05, 0.10, 0.20, 0.30} × n_strata ∈ {3, 5} × p_model):
  - p_model ∈ {per-segment raw-minmax calibration (A), per-stratum leave-one-segment-out empirical calibration (B, deployable), oracle per-stratum empirical (C, marked `optimistic_lower_bound`)}.
  - Audit allocation: stratified SRSWOR by proxy quantile, proportional allocation per stratum; `π_c = stratum_audit_n / stratum_size`.
  - p_model C is the optimistic lower bound (uses full labels → no online leakage); rows with `optimistic_lower_bound=True` do NOT count toward Gate B.
  - Monte Carlo reps `N_MC = 200` (the analysis is cheap — pure arithmetic over ~150 bins × 200 draws).
- Per config produce: `model_only_estimate`, `model_only_signed_error`, `model_only_rmse`, `dr_estimate_mean`, `dr_signed_error_mean`, `dr_abs_error_mean`, `dr_variance`, `dr_sd`, `dr_rmse`, `correction_term_mean`, `correction_term_sd`, `effective_sample_size_n_audit`, `max_weight_1_over_min_pi`, `correction_sd_lt_model_bias_abs`, `dr_rmse_lt_model_only_rmse`, `dr_rmse_lt_abae_residual_rmse` (using per-segment ABae residual RMSE from `full_residual_calibration.csv`).

### Aggregate Pass count under each p_model (audit_share ∈ {0.10, 0.20}, ≥20% reduction vs model-only OR dr_rmse < abae)

Disaggregated by `p_model` (non-optimistic only, audit_share ∈ {0.10, 0.20}):

| p_model | segs with ≥20% DR improvement over model-only | segs with DR RMSE < ABae |
|---|---:|---:|
| raw_minmax (A, strawman — badly miscalibrated on realcartest) | 3 / 6 | 2 / 6 |
| per_stratum_loo (B, deployable cross-segment calibration) | **1 / 6** (dataset3_0_1200) | 2 / 6 (dataset3_0_1200, realcartest_3200_3830 borderline) |
| aggregate(any non-optimistic p_model) | 4 / 6 | 2 / 6 |

### Why raw_minmax is a strawman

The realcartest `prior_score_max` distribution is compressed near 1.0: positive_proxy_mean = 0.85–0.91, negative_proxy_mean = 0.71–0.74. So `(p − min) / (max − min)` produces per-bin p_model values clustered near 1.0 on *every* bin, giving `model_only_estimate ≈ n_bins − O(1)` ≫ true_positive_mass (e.g., realcartest_0_1570: model_only = 109 vs true = 44). The DR correction term `Σ (y − p) / π` then *mechanically* subtracts ~65 because all proxies exceed true-bin-y — the "win" reflects fixing a hugely biased model, not a property of DR vs a well-calibrated model.

This is recognised in the literature (DR is dominated by the better of model-only or HT-only; on a severely biased model and a small-audit-n setting, DR's corrected RMSE = HT's variance − Bias² could fall below model-only, but only by accident of bias magnitude). I report this honest caveat explicitly so a future prototype does not over-credit.

### Why per_stratum_loo is the honest deployable calibration

The per-stratum leave-one-segment-out calibration estimates the positive rate of each proxy quantile stratum from the **other 5** segments, then applies it to the segment under test. This is the only one of the three p_models that could be deployed online without using the same segment's labels. Under p_model B:

- dataset3_0_1200: model_only_rmse = 18.77 (LOO calibration overshoots because this segment has only 7/120 positives while the other 5 segments average 30% positives) → DR pulls to 11.04 → **41% improvement**, DR < ABae. ✓
- dataset3_2400_3462: model_only_rmse = 1.11 (LOO undershoots because the segment's positives are at high proxy while others spread them out) → DR pushes to 14.77 → DR **hurts** by ~13× the model-only error. ✗
- realcartest_3200_3830: model_only_rmse = 1.11 → DR slightly beats ABae in one 5-strata config; ≤20% over model-only in either direction. Borderline.
- All other segments: DR hurts under per_stratum_loo.

### Effective sample size sanity check

At audit_share = 0.20, budget 0.30, sample sizes are:

| segment | budget_abs @30% | audit_n @20% share | true_positive_mass | stratified audit captures (avg) |
|---|---:|---:|---:|---:|
| realcartest_0_1570    | 47 | 9 | 44 | ≈ 14 expected per MC |
| realcartest_2000_3200 | 36 | 7 | 32 | ≈ 9 |
| realcartest_3200_3830 | 19 | 4 | 13 | ≈ 3.5 |
| dataset3_0_1200       | 36 | 7 |  7 | ≈ 0–1 (proxy AUC = 0.31 ⇒ audit hits ~ audit_share × positive_density × n / n_audit) |
| dataset3_1200_2400    | 36 | 7 | 21 | ≈ 4 |
| dataset3_2400_3462    | 32 | 6 | 12 | ≈ 2 |

These audit sizes are much smaller than the `RC_AQP_PREFLIGHT.md` n_min=14 needed for p_ucb ≤ 0.20 under SRSWOR zero-hit; stratification improves (cuts cluster-weight variance) but cannot reach a credible per-segment stopping certificate. **A DR-corrected *calibration* report is feasible (the estimator is finite; variance is bounded); a DR-based *stopping certificate* is not.**

### Gate B decision

- Deployable per-stratum-LOO delivers ≥20% improvement on **1/6** segments and beats ABae on **2/6**. The "≥4/6" PASS threshold is **only** met if we include the raw-minmax strawman.
- => **Gate B: CONDITIONAL** — DR helps only targeted weak-proxy / mis-calibration-prone segments, and only with non-trivial caveats. Honest dr<abae win count is 2/6, not 4/6.

### Comparison vs ABae-residual-strict

From `outputs/eventlift_full_benchmark_v1/full_residual_calibration.csv`, per-segment ABae-residual-strict RMSE (`abs_error` rows) at budget ≤ 0.30:

| segment | ABae-residual-strict RMSE |
|---|---:|
| realcartest_0_1570    | 14.46 |
| realcartest_2000_3200 | 12.57 |
| realcartest_3200_3830 | 10.41 |
| dataset3_0_1200       | 18.70 |
| dataset3_1200_2400    | 13.13 |
| dataset3_2400_3462    | 10.00 |

DR beats ABae on dataset3_0_1200 (DR=11.0 < ABae=18.7) confidently and on realcartest_3200_3830 narrowly (DR=10.17 < ABae=10.41 under one config). On 4/6 segments ABae's stratified estimator already outperforms DR's stratified DR estimator; this is consistent with `EVENTLIFT_RESULTS_SYNTHESIS.md` §5 / `EVENTLIFT_FULL_BENCHMARK_V1_REPORT.md` §6: ABae-residual-strict has the better-calibrated residual estimate (abs_error=11.4 vs EventLift's 16.5).

---

## 5. Gate decision & recommendation

`outputs/eventlift_dr_feasibility/dr_gate_summary.csv` snapshot:

```csv
gate,decision,criterion,evidence
A_proxy_bias_diagnosis,PASS,missed positives concentrated outside top proxy,"avg frac_missed_outside_top_30pct=0.682; avg frac_missed_in_bottom_50pct=0.528; weak_proxy(AUC<0.6) segments=['dataset3_0_1200', 'dataset3_1200_2400', 'dataset3_2400_3462']"
B_dr_variance_feasibility,CONDITIONAL,DR RMSE < model-only (>=20pct) on >=4/6 segs,"deployable(per_stratum_loo): >=20pct on 1/6 segs; dr<abae on 2/6; raw_minmax_strawman: >=20pct on 3/6; aggregate(any p_model): >=20pct on 4/6; dr<abae on 2/6; ..."
C_forced_audit_floor_prior,PASS,A & B support audit as dual-use,"Audit-as-dual-use (positive recovery + bias correction) is supported by A+B; but forced-exploration priors in FAILURES.md are failed/neutral (v2 cold_start, hybrid_coldstart, D3 repair vs norepair-neutral). EventLift-DR's only meaningful difference: audit correction term is dual-use."
```

### Gate A: PASS

Missed positives concentrate outside the top-30% proxy and inside the bottom-50% proxy (mean ~0.68 / ~0.53 across segment × method). The proxy bias is especially severe on dataset3 (`score_yolo_count` clipped proxy is anti-informative on dataset3_0_1200: AUC=0.31).

### Gate B: CONDITIONAL

Per the prompt's strict definition ("PASS if realistic audit shares, especially 0.10 or 0.20, reduce RMSE by at least 20% vs model-only or ABae on at least 4/6 segments") the honest answer is **CONDITIONAL**: the deployable per-stratum-LOO calibration passes that threshold on 1/6 segments and beats ABae on 2/6. The aggregate "≥4/6" only emerges when crediting the raw-minmax strawman — which tests "DR fixes a hopelessly miscalibrated model" rather than "DR fixes a deployable model".

Prompt-defined CONDITIONAL branch: *"DR helps only targeted low-proxy/weak-proxy segments."* Yes — exactly the case here.

### Gate C: PASS (borderline / dual-use)

Per the prompt's criterion PASS for C requires A and B support audit-as-dual-use correction. Both A and B (in {PASS, CONDITIONAL}) support that framing. The dual-use framing is the **one** structural difference from the three prior failed/neutral forced-exploration routes (hybrid_coldstart, v2 cold_start, D3 repair-vs-norepair). It is *conceptually* different; it is *not yet empirically validated* to actually recoup the budget tax at the audit sizes available in this benchmark.

### Recommendation

**A — Proceed to a TARGETED EventLift-DR ablation prototype, design-only next step.**

Subject to the task's hard constraints — **do NOT implement EventLift-DR yet**; do NOT modify the default `score_topk + temporal NMS + duration cap` selector; do NOT run new oracle/VLM/video/GPU; do NOT create large artifacts; do NOT claim a working EventLift-DR until an explicit test runs.

Targeted ablation scope (per Gate B's disaggregated evidence):

- **Segments in scope:** dataset3_0_1200 (the only unconditional Gate B win) and dataset3_1200_2400 (the proxy-bias failure segment where the gap is still a partial DR opportunity, even though full DR also hurts here at current audit n).
- **Segments out of scope:** realcartest_0_1570, realcartest_2000_3200, realcartest_3200_3830 (proxy AUC ≥ 0.68, DR's correction SD > model bias), dataset3_2400_3462 (proxy AUC = 0.56, borderline; B7's `k=3` expansion beats CERTIFY there).
- **Audit allocation constraint:** the audit draws used to compute the DR correction term MUST come from a *stratified* sample by the same proxy quantile strata used to compute `π_c`, and MUST be isolated from the bins that the DISCOVER/CERTIFY oracle calls already touched (per `AGENTS.md`: "outside-envelope audit samples double-counted as evaluation → label-isolation risk"; "decision-used audit ≠ evaluation audit"). Concretely: small `audit_share ∈ {0.10, 0.20}` ONLY, sampled disjointly from the discovery calls of the same trial.
- **Comparison baseline:** per_stratum_loo DR vs ABae-residual-strict (not raw-minmax DR vs ABae — the latter would unfairly credit the strawman).
- **Required non-claim:** do NOT claim an audit-floor variant fixes the dataset3_0_1200 0-recall failure on its own; the Gate B test was on the residual estimator (a calibration report), not on interval return-set precision/recall. EventLift-DR must demonstrate *interval return-set* improvement on dataset3_0_1200 to claim performance; this report only shows the *calibration* estimate improvement.

### Non-recommendations (also enumerated by prompt)

- **B (do not implement DR; improve discovery/certify instead):** would be the right call if Gate A FAILED. It did not — proxy AUC = 0.31 on dataset3_0_1200 means *no* discovery scheduler reform will recover positives there without at least some audit-floor injection.
- **C (do not implement DR; insufficient audit sample size):** rejected at Gate B = CONDITIONAL. Audit n = 7 at share 0.20 is small, but the Gap B CONDITIONAL branch (targeted weak-proxy segments) keeps it open rather than kills it.
- **D (re-scope to proxy improvement / data expansion):** the long-term right call. Even if DR passes a targeted ablation, the root cause on dataset3 is that `score_yolo_count` is not a useful proxy (AUC 0.31–0.46). DR is a *workaround*; a better proxy or more labels on dataset3 is the structural fix. Tracking recommendation D as a parallel roadmap item alongside any targeted DR ablation.

---

## 6. Required wording discipline

- DR/AIPW is a **known estimator family**, not a novel statistical invention. Per `CLAIMS_LEDGER.md` and `RC_AQP_PREFLIGHT.md` §6: no claim of "novel statistical estimator" or "new AQP paradigm."
- The only **novelty candidate** would be the application of a design-based audit correction to an *event-level AQP discovery posterior*. This is **not yet empirically demonstrated** to recoup the discovery-budget tax on the targeted segments — only statistically *plausible*.
- Forced-audit-floor prior: the three structurally similar routes (v2 `cold_start_fallback`, `hybrid_coldstart`, D3-core repair) **failed or landed as neutral** in this project (`FAILURES.md` lines 14–47). Any future EventLift-DR prototype must be **explicitly framed** against those priors and *not* rebranded as a new mechanism.
- Do NOT claim EventLift-DR works before implementation. Do NOT claim SOTA on the dataset3 segments. Do NOT claim safe stopping (per `RC_AQP_PREFLIGHT.md` Gate 2: per-segment `p_ucb(15)=0.181`, statistically weak; DR augmentation does **not** change that — that's a per-segment per-bin statistical-power wall, not a calibration-tool problem).
- Do NOT claim DR "fixes" dataset3_0_1200 0-recall. Gate B's DR win is on the *residual calibration estimator*, not on the *interval return-set*; recall precision is not what was tested. The EventLift-DR interval return-set evidence is reserved for a future targeted ablation, with strict audit-sample-isolation rules from `AGENTS.md`.
- All event-level numeric findings use **VLM-oracle-relative** labels from `center10_vlm_oracle_events.csv` / `canonical_dataset3_anchor_table.csv` — not human ground truth. Do NOT claim "true recall" / "ground truth recall".

---

## Appendix — execution record

**Files created (all new, small):**

- `PROXY_BIAS_DR_FEASIBILITY.md` (this file)
- `scripts/proxy_bias_dr_feasibility.py` (~430 LOC, pure arithmetic + Monte Carlo over existing labels; no new oracle / VLM / GPU)
- `outputs/eventlift_dr_feasibility/proxy_calibration_by_segment.csv` (6 rows)
- `outputs/eventlift_dr_feasibility/positive_rank_by_segment.csv` (30 rows)
- `outputs/eventlift_dr_feasibility/missed_event_proxy_rank.csv` (30 rows)
- `outputs/eventlift_dr_feasibility/dr_variance_feasibility.csv` (432 rows; ~70 KB)
- `outputs/eventlift_dr_feasibility/dr_gate_summary.csv` (3 rows)
- `outputs/eventlift_dr_feasibility/machine_summary.json` (3-line decision blob)

**Files modified:** none.

**Commands run:**

```bash
python3 scripts/proxy_bias_dr_feasibility.py
# (CPU-only; <5 s wall; replay-mode only, reusing bin labels + reference events)
```

**Was any experiment run?** NO. The script reads existing grids (`outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_*.csv`), the dataset3 anchor table (`src/garc_eval/outputs/codex_recompute_proxy_basa_v1/tables/canonical_dataset3_anchor_table.csv`), reference events (`center10_vlm_oracle_events.csv`), and the EventLift full benchmark output CSVs (`full_frontier_raw.csv`, `full_residual_calibration.csv`). All bin labels and oracle call traces it consumes were already produced by `scripts/run_eventlift_full_benchmark_v1.py` and the existing aligned baselines scripts. **The audit draws in the DR Monte Carlo are *synthetic* — they reuse the known bin labels in `is_positive` as if the audit had "queried" the bin; no new oracle call was made.**

**Budget/label-isolation compliance:** the Monte Carlo *pretends* the audit sees bin labels; this is the *offline feasibility arithmetic* the prompt explicitly authorizes (Section 4: "This is offline feasibility arithmetic, not an online algorithm. No new oracle calls are made."). It is *not* an online algorithm and *not* a claim that any future online EventLift-DR implementation could obtain those audit labels in this same segment without first making an oracle call. The audit-sample-isolation rule from `AGENTS.md` ("outside-envelope audit samples double-counted as evaluation → label-isolation risk") applies to any future *online* prototype; this feasibility check deliberately breaks that rule *because* it is offline-only and explicitly marked.

**Gate decisions summary:**

| Gate | Decision |
|---|---|
| A (proxy bias diagnosis) | **PASS** |
| B (DR variance feasibility) | **CONDITIONAL** |
| C (forced audit floor prior) | **PASS** (borderline, dual-use framing differentiates from prior failed/neutral forced-exploration routes) |

**Recommended next task:** *Design-only* — draft an EventLift-DR targeted ablation prototype spec covering dataset3_0_1200 (and optionally dataset3_1200_2400) **only as a strictly separate ablation path**. The spec must specify:
1. audit-share ∈ {0.10, 0.20} only;
2. audit sample bins drawn from a stratum-proportional design, *disjoint* from DISCOVER/CERTIFY oracle calls of the same trial (strict isolation per `AGENTS.md`);
3. p_model = per_stratum_loo (NOT raw_minmax), with leave-one-segment-out calibration, so the deployed baseline is the deployable one and any observed DR win is over an honest calibration;
4. the *interval return-set* comparison is the primary endpoint (not just residual calibration RMSE) — a DR win must lift returned-interval coverage on dataset3_0_1200 from 0 recall to a positive number to be实施的; if DR only fixes the residual certainty estimate while the return-set stays at 0, EventLift-DR is **not** a performance improvement, only a calibration-report improvement (same limitation AUDIT already has per `EVENTLIFT_RESULTS_SYNTHESIS.md` §5);
5. do NOT modify the default `score_topk + temporal NMS + duration cap` selector or the score-based discovery importance sampler;
6. compare vs ABae-residual-strict (not raw-minmax strawman) and report when DR wins, ties, and loses under the deployable p_model; if DR loses on dataset3_2400_3462 and ties on the realcartest segments, that is the honest expected outcome and must be reported as such.

**No implementation of EventLift-DR is authorized by this report.** It is a feasibility-and-gate document only. Implementation requires a separate explicit human approval per the task's hard constraints.