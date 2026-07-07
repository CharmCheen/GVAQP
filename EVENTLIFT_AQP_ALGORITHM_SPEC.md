# EventLift-AQP — Algorithm Specification

> Design-only document. No code is implemented, no experiment is run, no
> video/GPU/VLM/YOLO inference is performed. All recall/precision numbers
> referenced are **VLM-oracle-relative** (labels in `center10_vlm_oracle_
> events.csv` / `reference_events.csv`), not human ground truth, and no
> formal guarantee / certificate / statistical bound is claimed (per
> `AGENTS.md`, `CLAIMS_LEDGER.md` line 87).
>
> This spec is the successor design to `RC_AQP_PREFLIGHT.md` (recommendation
> B+C) and is grounded in `BASELINE_SOURCE_DATA_AUDIT.md`. It does NOT write
> `RC_AQP_V1_SPEC.md` and does NOT claim guaranteed safe stopping.

## 0. Framing

**EventLift-AQP is not a toy wrapper.** It is an event-level AQP *lifting*
method: it lifts three baseline ideas — record/frame selection (SUPG),
aggregate residual estimation (ABae), and predicate-projected relevant
clip query refinement (ARC) — into one unified semantic-event query
processor that runs on the 6 LATE-AQP segments under strict replay.

The lift is necessary because, per `BASELINE_SOURCE_DATA_AUDIT.md`:
- SUPG outputs record-id sets, not events (no temporal grouping in
  `refe_repos/supg/supg/selector/*.py`).
- ABae outputs a scalar aggregate (`algorithm.py:42`), not intervals.
- ARC outputs clip intervals but only for per-frame numeric predicates
  (`tools.py:49-62`); the LATE-AQP semantic-event query (clip-level VLM
  predicate) cannot be expressed in ARC's grammar without a semantics-
  changing projection.

None of the three, separately, produces the EventLift-AQP output contract
(§7). EventLift-AQP jointly decides discover / certify / suppress / audit
actions under **one utility** and **one budget ledger**, instead of running
selection, grouping, and residual estimation as separate post-hoc modules.

============================================================
1. Problem definition
============================================================

**Given:**
- A video segment `V` (one of the 6 LATE-AQP segments in `outputs/late_aqp_
  event_diverse_discovery_v1/segment_info.csv`: 3 realcartest + 3
  dataset3, 63–157 atomic 10s bins each, 6–20 reference events each).
- A semantic event query `q` (e.g. "enter_ego_path events involving a
  vehicle, pedestrian, or cyclist" — the `event_type` / `event_type_majority`
  column of the VLM reference). The query is *clip-level semantic*: it is
  evaluated by the VLM oracle over a temporal window, not by a per-frame
  numeric threshold.
- Cheap proxy scores over atomic bins/components (the `prior_score_max` /
  `prior_score_mean` columns of `outputs/exsample_aware_replay/atomic_
  grid_10s.csv` and the `fused_score` / `cheap_fused_score` columns of
  `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`).
  Proxy is free to read; the oracle is not.
- An expensive VLM oracle `O` exposing `query_unit(bin_idx) -> {positive,
  negative}` and `query_interval(t_start, t_end) -> {positive, negative}`
  per `outputs/late_aqp_limited_oracle_frontier_v1/oracle_adapter_spec.md`.
  Each call = 1 oracle unit. `event_id` is never returned.
- A budget `B` (oracle units; same grid as `late_aqp_limited_oracle_
  frontier_v1`, e.g. B ∈ {5,8,10,16,20,31,40,47,60,63,78,80,100,120}).

**Output (the event-level answer — NOT a raw positive-bin count):**
1. Non-redundant event intervals (core + halo, see §3).
2. Event precision / event recall under the full VLM reference, computed by
   the shared evaluator at IoU ≥ 0.3 (the LATE-AQP threshold).
3. A residual uncertainty estimate (`residual_hat`, `residual_ucb`).
4. A budget ledger decomposed by action type (discover / certify / suppress
   / audit).
5. An optional stop / abstain decision (`stop_status`, `stop_reason`).

**Hard constraints (carry over from `AGENTS.md` + `oracle_adapter_spec.md`):**
- The online algorithm may not read `grid['is_positive']` or `ref` directly.
- `event_id` is never returned by the oracle; the algorithm must not use it.
- `probe_set_v1` is read-only and not used for tuning / selection / repair.
- Decision samples and evaluation samples must be different batches
  (outside-envelope audit samples driving a repair/audit decision cannot
  also prove that decision effective).
- The atomic unit is the **10s bin** (the LATE-AQP oracle granularity). A
  raw positive-bin count is *not* the target; an event-level answer is.

**Safe stopping is OPTIONAL and only allowed when the residual bound is
tight.** Per `RC_AQP_PREFLIGHT.md` Gate 2, per-segment safe stopping at
`tau_r ≥ 0.9` is statistically weak on these segments (`p_ucb(15) = 0.181`,
`p_ucb(10) = 0.259`; min `n_audit` for `p_ucb ≤ 0.05` is 59, larger than
any plausible per-segment audit share at B ≤ 120). Therefore:
- A residual report is **always** emitted.
- A stop certificate is emitted **only if** the residual UCB is tight
  enough to support the target (see §6.3).
- Otherwise the output is `stop_status = abstain_or_budget_exhausted`.

============================================================
2. Baseline lifting view
============================================================

EventLift-AQP lifts each baseline into an event-level action without
collapsing it into a toy imitation:

### 2.1 SUPG-event (record selection lifted to event selection)
- **Native SUPG** (`refe_repos/supg/supg/selector/recall_selector.py`):
  importance-sampled recall-target selection over records, returns an id
  set, no grouping.
- **Lift:** treat each 10s bin as a SUPG record (`id=bin_idx`,
  `label=is_positive`, `proxy_score=prior_score_max`). Run the SUPG
  `RecallSelector` importance sampler as the **DISCOVER** action's
  sampling distribution (§4). Then perform temporal grouping (gap ≤ 1
  bin) into candidate events — the missing `supg_rt_plus`/`supg_pt_plus`
  step from `docs/GARC_EVAL_BUILD_PLAN.md` lines 411-412.
- **What is NOT lifted:** SUPG's `SamplingBounds` selection-size calibration
  is not re-labeled as an event-level RecallLCB (it calibrates selection
  size, not event coverage).

### 2.2 ABae-residual (aggregate estimation lifted to residual mass)
- **Native ABae** (`refe_repos/abae/abae/algorithm.py:42`): two-stage
  stratified importance sampling estimating `E[statistic | predicate]`,
  outputs a scalar + bootstrap CI.
- **Lift:** set `statistic ≡ 1` and `predicate = "bin is positive"`. The
  ABae aggregate collapses to an estimate of total positive-mass fraction
  `P(predicate)`. Use this as the **AUDIT** action's residual estimator
  (§6) over *uncovered* components (residual = estimated total mass −
  observed positive mass).
- **What is NOT lifted:** ABae's temporal ignorance. The lift keeps ABae
  as a scalar estimator over strata; it does not produce intervals and
  cannot be evaluated on event coverage directly (it feeds the residual
  field of the output contract, not the intervals field).

### 2.3 ARC-projection (clip query lifted to certify/suppress refinement)
- **Native ARC** (`refe_repos/ARC-main/arc/arc.py:20-133`,
  `tools.py:49-62`): progressive frame sampling + label propagation +
  `findCandClips` over a per-frame predicate `P(score,op,constant)`,
  outputs `(start,end)` clips with clip-IoU confidence.
- **Lift:** ARC's machinery is re-purposed as the **CERTIFY** and
  **SUPPRESS** actions (§4). CERTIFY refines a candidate event's
  boundaries by oracle-sampling inside the component (ARC's progressive
  sampling over the bin-grid broadcast). SUPPRESS uses ARC's label-
  propagation idea to mark a neighborhood as negative after a certify
  miss, avoiding redundant discovery calls.
- **What is NOT lifted:** ARC's per-frame numeric predicate grammar. The
  LATE-AQP semantic-event query is a clip-level VLM predicate; it is not
  expressible as `P(score,op,constant)` on a per-frame statistic. The lift
  operates on the **bin grid** (10s units), not on per-frame counts. ARC
  is therefore a *restricted predicate subset* baseline in §8, not a full
  semantic-event comparator.

### 2.4 B7-core / D3-norepair-core (strong frontier baselines, not lifted)
- Per `PROJECT_STATE.md` and `HANDOFF.md`: B7-core (posthoc_eval) and
  D3-norepair-core (strict_replay) are the strongest existing event-level
  baselines. They are comparison targets in §8, not lifted components.
- Their discovery prior (chunk-bandit Thompson sampling on `prior_score`)
  seeds EventLift-AQP's DISCOVER utility in §5.

### 2.5 Why EventLift-AQP differs
The three lifts above are, separately, still post-hoc modules: SUPG-event
selects then groups, ABae-residual estimates mass separately, ARC-projection
refines separately. EventLift-AQP's difference is that it places all four
actions (DISCOVER, CERTIFY, SUPPRESS, AUDIT) inside **one utility function
(§5)** and **one budget ledger (§7)**, so that the decision "spend the next
oracle call on a new component, on refining a known candidate, on
suppressing a neighborhood, or on auditing an uncovered stratum" is made
by the same arbitration rule. This directly addresses the post-fix residual
gap documented in `RC_AQP_PREFLIGHT.md` Gate 1: after the D3 accounting
fix, repair is neutral not because local expansion is useless, but because
"repair consumes budget that could otherwise go to global bandit
exploration" (`late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md`). A unified
utility prices both in the same currency.

============================================================
3. State representation
============================================================

All state is derived only from oracle responses + free proxy scores. **No
ground-truth `event_id` may be used by the online algorithm.**

### 3.1 atomic bin `b`
The base oracle-queryable unit: a 10s temporal bin from `segment_info.csv`
(`atomic_bin_size=10.0`). Each bin has a free proxy score
(`prior_score_max`, `prior_score_mean`, or `fused_score`) and a hidden
oracle label `is_positive ∈ {0,1}` revealed only via `query_unit(b)`.

### 3.2 component `C`
A maximal run of *temporally adjacent* bins (gap ≤ 1 bin = 10s) whose proxy
score exceeds a threshold θ_proxy. A component is a *candidate event
scaffold*; it is cheap to compute (proxy only) and is the unit on which
DISCOVER operates. Components do not use `event_id`. Formally:
`C = {b_start..b_end}` s.t. `proxy(b) ≥ θ_proxy` for all `b ∈ C` and
`proxy(b_start-1), proxy(b_end+1) < θ_proxy` (or boundary).

### 3.3 core interval
A sub-interval `[t_start, t_end]` inside a component that has been
*certified* by ≥1 positive oracle call and is released as a returned event.
Core = positive selected bins + positive guard bins (same definition as
LATE-AQP Core/Halo, `MAX_GUARDS_PER_SIDE=3`).

### 3.4 halo interval
The bins immediately adjacent to a core interval (within the component)
that are reported as *diagnostic only*, not as returned events. Halo is
not counted toward event precision/recall; it is reported for failure-mode
analysis (matching the existing Core/Halo semantics in `late_aqp_core_halo_
attribution_v1`).

### 3.5 covered memory `M`
The set of bins whose oracle label has been revealed (by any action) plus
their propagation label (CERTIFY/SUPPRESS may propagate labels to
neighbors). `M` records `(bin_idx, label, label_source_action,
label_source_call_id)`. This is the per-call unified ledger that
`RC_AQP_PREFLIGHT.md` line 141 flags as missing (`source_action` lineage
gap in v3 replay). EventLift-AQP logs it from the start.

### 3.6 candidate event `e_hat`
A core interval that has not yet been released; it is a tentative event
awaiting either CERTIFY (to become a returned interval) or SUPPRESS (to be
discarded). A candidate event is defined by `(component, anchor_bin,
proxy_score, current_core_span)`.

### 3.7 uncovered region `U`
The set of bins not in `M` (not yet queried) AND not in any SUPPRESS
neighborhood. This is where residual positive mass may still live. AUDIT
operates on `U`.

### 3.8 audit stratum `S`
A partition of `U` by proxy-score rank (same stratification as ABae,
`abae/data.py:22`: `np.array_split(np.argsort(proxy_scores), k)`). Each
stratum has a known sampling probability (AUDIT draws with known
probability per stratum), which is required for the residual estimator
(§6) to be unbiased.

### 3.9 residual mass state `R`
The current estimate of uncovered positive mass: `R = (estimate of
positive-bin fraction in U) × |U|`, plus a one-sided UCB. `R` is updated
after every AUDIT action and after every DISCOVER that reveals new labels
in `U`. `R` is the field that drives the stop/abstain decision (§6.3).

============================================================
4. Actions
============================================================

Four action types. Each consumes oracle calls, updates state, and has an
expected benefit and a failure mode. The utility in §5 arbitrates between
them.

### 4.1 DISCOVER(component)
- **Input:** a component `C` (from §3.2) with high aggregate proxy mass.
- **Oracle calls consumed:** 1 per sampled bin inside `C`
  (`query_unit(b)`). Sample count = `min(|C|, B_discover_share)`; the
  sampling distribution inside `C` is the SUPG importance sampler
  (`sqrt(proxy)` weights, `recall_selector.py:53`).
- **State update:** sampled bins enter `M` with `label_source_action=
  DISCOVER`. Positive bins become candidate events (`e_hat`).
- **Expected benefit:** reveal new positive bins → new candidate events →
  potential event-coverage gain. Proportional to the component's proxy
  mass × its fraction of bins not yet in `M`.
- **Failure mode:** discovery miss. The dominant LATE-AQP failure mode
  (`failure_taxonomy.csv`: 6 discovery_miss vs 6 release_over_conservative
  vs 3 LATE-specific). Happens when the proxy points to a component with
  no true positives, wasting budget. Mitigated by SUPPRESS feeding back
  into the discovery prior.

### 4.2 CERTIFY(anchor / core)
- **Input:** a candidate event `e_hat` with an anchor positive bin.
- **Oracle calls consumed:** 1 per bin sampled inside `e_hat`'s component
  neighborhood (ARC-style progressive sampling, `arc.py:94-95`). Bounded
  by `MAX_GUARDS_PER_SIDE=3` per side (the existing Core/Halo cap).
- **State update:** sampled bins enter `M` with `label_source_action=
  CERTIFY`. Positive neighbors expand the core span; negative neighbors
  bound it. `e_hat` is either promoted to a returned interval (core) or
  demoted (if the anchor is isolated).
- **Expected benefit:** convert a candidate event into a release-ready
  interval with correct boundaries → event-precision gain (reduce false
  positives from over-broad components).
- **Failure mode:** release-over-conservative. The second LATE-AQP
  failure mode (`failure_taxonomy.csv`). Happens when CERTIFY over-samples
  around a single positive, spending budget that could have discovered
  new events. This is the exact "repair consumes budget that could
  otherwise go to global bandit exploration" gap from
  `late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md`. The unified utility
  (§5) is what makes CERTIFY pay for this opportunity cost.

### 4.3 SUPPRESS(neighborhood)
- **Input:** a neighborhood of bins (a component or a stratum) that
  DISCOVER/CERTIFY has shown to be negative.
- **Oracle calls consumed:** 0 (SUPPRESS does not query; it *propagates*
  labels from `M` into `U` using ARC's label-propagation idea,
  `arc.py:113-114`). Optionally 1 confirmatory query at the neighborhood
  boundary.
- **State update:** bins in the neighborhood are marked
  `label=propagated_negative, label_source_action=SUPPRESS` in `M` and
  removed from `U`.
- **Expected benefit:** avoid redundant DISCOVER calls in a region already
  shown negative → free up budget for AUDIT or DISCOVER elsewhere.
  Directly attacks the duplicate-sampling failure mode (D3 pre-fix had
  11.21 mean duplicates; post-fix 0.51, `FAILURES.md` line 92).
- **Failure mode:** over-suppression. A neighborhood is marked negative
  but actually contains a positive event that was missed by the
  seed queries. This is a *new* failure mode EventLift-AQP introduces;
  mitigated by AUDIT sampling inside suppressed neighborhoods at a low
  rate (§6).

### 4.4 AUDIT(stratum)
- **Input:** an audit stratum `S` over `U` (§3.8).
- **Oracle calls consumed:** `n_audit` per stratum, drawn with known
  probability `p_S` (ABae two-stage, `algorithm.py:7-42`: pilot `n1` per
  stratum → optimal `n2` allocation ∝ `√p·σ`).
- **State update:** sampled bins enter `M` with `label_source_action=
  AUDIT`. The residual estimator `R` (§3.9, §6) is updated. AUDIT
  samples that turn out positive are *also* fed back as candidate events
  (a positive in an audit stratum is a discovery miss — this is the
  dual-purpose channel).
- **Expected benefit:** (a) tighten the residual estimate `R` → enable a
  principled stop/abstain decision; (b) catch discovery misses in low-
  proxy strata that DISCOVER would never visit. This is the ABae-residual
  lift.
- **Failure mode:** audit-heavy regime. At low budget, AUDIT steals
  budget from DISCOVER, collapsing event recall. Per `RC_AQP_PREFLIGHT.md`
  Gate 2, at 30% budget / 20% audit share, `n_audit ≤ 9` per segment and
  `p_ucb ≥ 0.259` — the residual estimate is loose. Mitigated by the
  utility (§5) pricing AUDIT's opportunity cost.

============================================================
5. Unified utility
============================================================

A single action utility arbitrates between the four actions. This is a
**budget-arbitration heuristic**, not a proven optimal policy (no claim of
optimality — see §9).

### 5.1 General form

For an action `a` given current state `(M, U, R, candidates)` and remaining
budget `B_rem`:

```
U(a) =   expected_event_coverage_gain(a)
       + λ · expected_residual_uncertainty_reduction(a)
       − μ · duplicate_redundancy_cost(a)
       − η · oracle_cost(a)
       − κ · opportunity_cost(a | B_rem)
```

- `expected_event_coverage_gain(a)`: expected number of *new reference
  events* (distinct, IoU ≥ 0.3) that `a` will uncover. For DISCOVER,
  proportional to proxy mass of the component × (1 − fraction already in
  `M`). For CERTIFY, 0 new events but precision gain on existing
  candidates. For AUDIT, the expected positive rate of the stratum × its
  size. For SUPPRESS, 0.
- `expected_residual_uncertainty_reduction(a)`: expected shrink in the
  UCB width of `R` (§6). For AUDIT, large (this is its primary purpose).
  For DISCOVER, small (it reveals labels in `U` but not in a stratified
  way). For SUPPRESS, 0. For CERTIFY, 0.
- `duplicate_redundancy_cost(a)`: expected fraction of `a`'s oracle calls
  that hit bins already in `M`. Directly penalizes the pre-fix D3
  duplicate-sampling failure mode. For DISCOVER in a fresh component,
  low; for CERTIFY in an already-sampled component, high.
- `oracle_cost(a)`: number of oracle calls `a` consumes. Linear in calls.
- `opportunity_cost(a | B_rem)`: the expected coverage gain forgone by
  spending `oracle_cost(a)` calls on `a` instead of the best alternative.
  This is the term that makes CERTIFY pay for budget it takes from
  DISCOVER — the post-fix residual gap (§2.5).

`λ, μ, η, κ` are hyperparameters. Defaults (to be tuned on the dev segment
`realcartest_2000_3200` only, never on `probe_set_v1`):
`λ=0.5, μ=1.0, η=1.0, κ=0.5`. These are starting points, not fitted
values; any tuning must be reported with the dev-segment-only caveat.

### 5.2 Per-action instantiation

**U_discover(component C):**
```
U_discover(C) =  proxy_mass(C) · (1 − |C ∩ M| / |C|)
              + λ · (|C ∩ U| / |U|) · residual_var_reduction_if_sampled
              − μ · (|C ∩ M| / |C|)        # redundancy penalty
              − η · n_discover_calls
              − κ · best_alternative_gain(n_discover_calls)
```

**U_certify(candidate e_hat):**
```
U_certify(e_hat) =  boundary_precision_gain(e_hat)   # narrow core span
                 − μ · (|neighborhood(e_hat) ∩ M| / |neighborhood|)
                 − η · n_certify_calls
                 − κ · best_alternative_gain(n_certify_calls)
```
Note: `expected_event_coverage_gain = 0` for CERTIFY — it does not find
new events, it refines existing ones. Its value is precision, priced
against discovery's coverage gain.

**U_audit(stratum S):**
```
U_audit(S) =  λ · ucb_shrink(S, n_audit)            # residual purpose
            + proxy_low_mass(S) · discovery_miss_recovery_prob(S)
            − μ · (|S ∩ M| / |S|)
            − η · n_audit_calls
            − κ · best_alternative_gain(n_audit_calls)
```
The second term is the dual-purpose channel: AUDIT in a low-proxy stratum
can recover discovery misses. This is what prevents AUDIT from being pure
overhead.

### 5.3 Selection rule
At each step, compute `U(a)` for the top-k candidate actions of each type
(candidate components for DISCOVER, candidate events for CERTIFY, strata
for AUDIT, neighborhoods for SUPPRESS). Pick `argmax_a U(a)` subject to
`oracle_cost(a) ≤ B_rem`. Repeat until `B_rem = 0` or `stop_status` is
emitted (§6.3).

============================================================
6. Residual estimator
============================================================

The residual estimator is the lift of ABae to event-level uncertainty
reporting. It is **conservative** (one-sided UCB) and **always emitted**.
A stop certificate is emitted only when the bound is tight (§6.3).

### 6.1 Strata over uncovered components
Partition `U` (§3.7) into `k` strata by proxy-score rank (ABae style,
`abae/data.py:22`). Strata are re-computed whenever `U` shrinks (after
DISCOVER / SUPPRESS / AUDIT). Each stratum `S` has:
- `N_S` = number of bins in `S`
- `n_S` = number of AUDIT samples drawn from `S` (with known probability
  `p_S = n_S / N_S`)
- `x_S` = number of positive AUDIT samples in `S`

### 6.2 Estimate and UCB
Per-stratum positive-mass estimate (Horvitz-Thompson, known-sampling-
probability):
```
p_hat_S = x_S / n_S                  (if n_S > 0)
p_ucb_S = 1 − (α/2)^(1/n_S)          (zero-hit upper bound, α=0.05)
```
`p_ucb_S` is the binomial zero-hit upper bound from `RC_AQP_PREFLIGHT.md`
§3: `p_ucb(n, α) = 1 − α^(1/n)`. This is the honest bound; it is loose at
small `n` (`p_ucb(10)=0.259`, `p_ucb(15)=0.181`).

Aggregate residual estimate over `U`:
```
residual_hat = Σ_S  N_S · p_hat_S                          (point estimate)
residual_ucb = Σ_S  N_S · p_ucb_S                           (one-sided UCB)
```
If `n_S = 0` for some stratum, `p_ucb_S = 1` (uninformative) — the
aggregate UCB is then dominated by that stratum's `N_S`, which is the
correct conservative behavior.

### 6.3 Stop / abstain decision
- **Target recall** `tau_r` (e.g. 0.9). Let `D` = number of distinct
  reference events currently covered (known to the evaluator, not the
  algorithm — the algorithm uses a proxy: number of positive bins in `M`
  scaled by an average-events-per-positive-bin factor estimated from the
  dev segment only).
- **Stop certificate condition:** emit `stop_status = stopped_certificate`
  iff `residual_ucb / (D + residual_ucb) ≤ 1 − tau_r` AND every stratum
  has `n_S ≥ n_min` (where `n_min` is the sample size at which `p_ucb` is
  non-vacuous; per `RC_AQP_PREFLIGHT.md`, `n_min ≥ 29` for `p_ucb ≤ 0.10`,
  `≥ 59` for `p_ucb ≤ 0.05`).
- **Abstain condition (default):** otherwise emit
  `stop_status = abstain_or_budget_exhausted`, with `stop_reason` ∈
  `{audit_n_too_small, residual_ucb_too_loose, budget_exhausted}`.
- **Hard rule:** per `RC_AQP_PREFLIGHT.md` Gate 2, at the LATE-AQP segment
  scale (63–157 bins, B ≤ 120), per-segment `n_audit` is typically ≤ 9 at
  30% budget / 20% audit share → `p_ucb ≥ 0.259`. Therefore the stop
  certificate condition will **almost never** be met per-segment. Pooled
  across all 6 segments, `n_audit` can reach ~30–80, making `p_ucb` useful
  (0.05–0.10) — a *pooled* residual report is feasible, a *per-segment*
  stop certificate is not. The output contract (§7) carries both.

### 6.4 Calibration error (evaluation-only)
When the full VLM reference is available (evaluator side only), compute:
```
residual_calibration_error = |residual_hat − true_uncovered_positive_bins|
residual_ucb_coverage = P(true_uncovered ≤ residual_ucb)   (over seeds)
```
This is reported per `RC_AQP_PREFLIGHT.md`'s recommendation-C re-scope:
residual uncertainty reporting, not a guarantee.

============================================================
7. Output contract
============================================================

One row per `(segment_id, baseline_id, query_id, budget, seed)`. This
schema extends the common schema proposed in `BASELINE_SOURCE_DATA_AUDIT.md`
§6 and is a strict superset of the LATE-AQP frontier schema
(`d3_fixed_frontier_raw.csv` columns):

```
segment_id
baseline_id            # "EventLift-AQP" or ablation tag
query_id               # e.g. "enter_ego_path"
budget_abs             # B
budget_ratio           # B / num_units
oracle_calls           # total = sum of the 4 below
oracle_calls_by_action # "discover=..;certify=..;suppress=..;audit=.." (string or 4 cols)
proxy_cost             # number of bins whose proxy was read (cheap, full scan)
returned_intervals     # list of (t_start, t_end) core intervals
core_intervals         # subset of returned_intervals
halo_intervals         # diagnostic only, not scored
event_precision        # vs full VLM reference, IoU>=0.3
event_recall           # vs full VLM reference, IoU>=0.3
unique_event_coverage  # count distinct reference events hit
duplicate_rate         # fraction of oracle calls hitting bins already in M
residual_hat           # point estimate of uncovered positive mass
residual_ucb           # one-sided UCB (alpha=0.05)
residual_calibration_error  # |hat - true|, only if reference available (eval-side)
stop_status            # {stopped_certificate, abstain_or_budget_exhausted}
stop_reason            # {audit_n_too_small, residual_ucb_too_loose, budget_exhausted, certificate_met}
recall_lcb_available   # false (EventLift-AQP does not emit a per-segment event-recall LCB; only a residual mass UCB)
stop_certificate_available  # true iff stop_status=stopped_certificate
strict_replay          # true (no event_id in selection)
applicability_note     # free text
```

**Budget ledger invariants (enforced, not just logged):**
- `oracle_calls = discover_calls + certify_calls + suppress_confirm_calls + audit_calls`.
- `oracle_calls ≤ B` (hard assertion; pre-fix D3 violated this via the
  `queried`-state bug — `FAILURES.md` line 92. EventLift-AQP asserts it).
- Every oracle call has a `source_action` and `source_call_id` in `M`
  (closes the v3 lineage gap, `RC_AQP_PREFLIGHT.md` line 141).
- AUDIT samples that drive a stop decision are *not* reused to evaluate
  the stop decision's correctness (per `AGENTS.md`: decision vs evaluation
  batch separation). The evaluator draws a fresh batch for calibration.

============================================================
8. Comparison plan
============================================================

### 8.1 Baselines
- **B7-core** (posthoc_eval) — strongest empirical baseline
  (`PROJECT_STATE.md`). Comparison target for event P/R.
- **D3-norepair-core** (strict_replay) — strongest strict-replay
  alternative. Comparison target under strict replay.
- **SUPG-event** — the SUPG lift (§2.1): bin-adapter + temporal grouping.
  Record-selection baseline role.
- **ABae-residual** — the ABae lift (§2.2): total-positive-mass estimator.
  Aggregate-estimation baseline role. Compared on `residual_hat` /
  `residual_ucb` / `residual_calibration_error`, NOT on event P/R (it
  emits no intervals).
- **ARC-projection** — the ARC lift (§2.3): restricted predicate-defined
  clip query on the bin grid. **Conditionally applicable** (per
  `BASELINE_SOURCE_DATA_AUDIT.md` §5): the semantic-event query is
  projected to a per-bin predicate; this is a restricted subset comparison,
  NOT full semantic-event parity. Labeled as such in every table.

### 8.2 Ablations (EventLift-AQP itself)
- **discover-only** — DISCOVER + SUPPRESS, no CERTIFY, no AUDIT. Closest
  to D3-norepair-core.
- **discover+certify** — adds CERTIFY. Closest to D3-core-fixed.
- **discover+audit** — adds AUDIT (residual reporting) but no CERTIFY.
  Tests whether AUDIT alone improves coverage (via the dual-purpose
  channel) without boundary refinement.
- **full EventLift-AQP** — all four actions under the unified utility.

### 8.3 Primary metrics
- **Unique event recall vs budget** (the EC-AQP objective from
  `PROJECT_STATE.md` / `TASK_QUEUE.yaml` T010). Primary.
- **Duplicate sampling rate** (`d3_fixed_frontier_raw.csv` column).
  Directly measures whether the unified utility fixes the pre-fix D3
  failure mode.
- **Residual calibration error** (§6.4). Measures whether the residual
  report is honest. Reported pooled across 6 segments AND per-segment
  (with the per-segment `p_ucb ≤ 0.18` caveat).
- **Oracle budget decomposition** (discover / certify / suppress / audit).
  Measures whether the unified utility actually arbitrates (vs. a
  degenerate all-discover policy).
- **False stop rate** — only if `stop_status = stopped_certificate` is
  ever emitted. Expected to be ~0 per-segment (§6.3); if it fires, report
  the false-stop rate. If it never fires, report abstain rate.
- **Abstain rate** — fraction of (segment, budget, seed) trials with
  `stop_status = abstain_or_budget_exhausted`. Expected to be ~1.0
  per-segment at current scales.

### 8.4 Tracks (per `CLAIMS_LEDGER.md`)
- EventLift-AQP is `strict_replay` (no `event_id` in selection).
- SUPG-event and ABae-residual are `strict_replay` (same).
- ARC-projection is `strict_replay` on the restricted predicate subset.
- B7-core is `posthoc_eval`; D3-norepair-core is `strict_replay`.
- Every comparison table labels the track.

============================================================
9. Claim boundary
============================================================

### 9.1 Allowed claims
- "We propose an event-level AQP lifting method (EventLift-AQP) that unifies
  selection (SUPG-event), certification (ARC-projection), residual
  estimation (ABae-residual), and budget accounting (4-way ledger) under a
  single utility."
- "Existing SUPG / ABae / ARC ideas can be adapted to the LATE-AQP
  semantic-event setting, but separately they do not provide a unified
  semantic-event AQP answer: SUPG lacks temporal grouping, ABae lacks
  interval output, ARC lacks the per-frame numeric predicate for a clip-
  level VLM semantic query." (grounded in `BASELINE_SOURCE_DATA_AUDIT.md`
  §2-3).
- "The main contribution is unified event-level AQP budget arbitration and
  residual uncertainty reporting, not a new selection algorithm, not a new
  clip grammar, and not a statistical guarantee."
- "Per-segment safe stopping is not statistically supported at the LATE-AQP
  scale (`p_ucb(15)=0.181`); EventLift-AQP therefore emits a residual report
  by default and a stop certificate only when the bound is tight, which is
  expected to be rare per-segment." (grounded in `RC_AQP_PREFLIGHT.md`
  Gate 2).
- "The unified budget ledger closes the `source_action` lineage gap noted
  in `RC_AQP_PREFLIGHT.md` line 141, by logging every oracle call with its
  action type from the start."

### 9.2 Forbidden claims
- "Safe stopping is guaranteed on all segments." — forbidden (per
  `RC_AQP_PREFLIGHT.md` Gate 2 + `CLAIMS_LEDGER.md` line 87).
- "Component abstraction alone is novel." — forbidden (per
  `RC_AQP_PREFLIGHT.md` §6 unsupported framing).
- "SUPG / ABae / ARC are absent or irrelevant." — forbidden (per
  `BASELINE_SOURCE_DATA_AUDIT.md` §8 wording discipline: SUPG exists and
  is runnable, ABae is the correct aggregate-estimation role, ARC is the
  correct clip-query role).
- "ARC cannot handle clips." — forbidden (ARC is a relevant-clip-query
  system by design, `BASELINE_SOURCE_DATA_AUDIT.md` §3.3).
- "EventLift-AQP is proven optimal." — forbidden (the utility in §5 is a
  budget-arbitration heuristic, not a proven-optimal policy).
- "LATE-AQP / EventLift-AQP beats B7-core on B_90/90." — forbidden
  (`CLAIMS_LEDGER.md` line 75) unless and until a strict-replay run shows
  it, and even then only with the track label.
- "The residual bound is a formal guarantee / certificate / statistical
  bound." — forbidden (`CLAIMS_LEDGER.md` line 87).

============================================================
10. Minimal implementation plan
============================================================

Four stages. Each stage produces a small CSV + MD under
`outputs/eventlift_aqp_*_v1/`, no large artifacts, no video, no VLM, no GPU.
All oracle calls are replay over the *already-labelled*
`center10_vlm_oracle_events.csv` / `reference_events.csv` (the same labels
LATE-AQP uses). Tuning is on the dev segment `realcartest_2000_3200` only;
`probe_set_v1` is never touched for tuning.

### Stage 1 — SUPG-event + ABae-residual adapters + discover/audit core
- Implement `SUPG-event` (bin-adapter over `atomic_grid_10s.csv` + temporal
  grouping) using the existing `src/garc_eval/adapters/supg_adapter.py`.
- Implement `ABae-residual` (statistic≡1, two-stage stratified) over `U`,
  using the existing `src/garc_eval/adapters/abae_adapter.py`.
- Implement EventLift-AQP's DISCOVER (SUPG importance sampler over
  components) + AUDIT (ABae over `U`) under the unified utility, WITHOUT
  CERTIFY or SUPPRESS.
- Output: `outputs/eventlift_aqp_discover_audit_v1/per_segment_results.csv`
  + `summary.md`.
- Compare against D3-norepair-core (strict_replay) on the dev segment.
- **Gate:** does discover+audit's residual report calibrate? Does the
  dual-purpose AUDIT channel recover any discovery misses? If no on both,
  STOP and report negative (do not proceed to Stage 2 with a broken core).

### Stage 2 — add CERTIFY + SUPPRESS into the same utility loop
- Add CERTIFY (ARC-style progressive sampling over bin-grid, bounded by
  `MAX_GUARDS_PER_SIDE=3`) and SUPPRESS (label propagation, 0 oracle calls
  except optional 1 confirmatory) as actions in the unified utility.
- The utility now arbitrates all four actions. The `opportunity_cost` term
  is what makes CERTIFY pay for budget taken from DISCOVER — directly
  addressing the post-fix residual gap (`RC_AQP_PREFLIGHT.md` Gate 1).
- Output: `outputs/eventlift_aqp_full_v1/per_segment_results.csv` +
  `summary.md`.
- Compare against B7-core (posthoc_eval) and D3-norepair-core
  (strict_replay) on all 6 segments.
- **Gate:** does full EventLift-AQP's budget decomposition show non-
  degenerate arbitration (i.e. not all-discover)? Does duplicate_rate drop
  vs Stage 1? If the utility collapses to all-discover, STOP and report
  that the unified utility did not arbitrate in practice.

### Stage 3 — ARC-projection restricted comparison
- Implement the ARC-projection lift (§2.3) as a *baseline*, not as part of
  EventLift-AQP. Runs on the restricted per-bin-predicate subset only.
- Output: `outputs/arc_projection_restricted_v1/per_segment_results.csv`.
- Labeled `applicability_note = "restricted predicate subset; not full
  semantic-event parity"` in every row.
- This is the conditional-comparison slot from `BASELINE_SOURCE_DATA_AUDIT.md`
  recommendation C. It is NOT a claim that ARC runs on the full
  semantic-event task.

### Stage 4 — calibration and ablation report
- Run all 4 ablations (§8.2) on all 6 segments × the budget grid × 5 seeds.
- Compute residual calibration error (§6.4) pooled and per-segment.
- Report false-stop rate (expected ~0 per-segment) and abstain rate
  (expected ~1.0 per-segment).
- Output: `outputs/eventlift_aqp_ablation_v1/{per_segment_results.csv,
  calibration_report.md, ablation_summary.md}`.
- Update `CLAIMS_LEDGER.md` "Pending Validation" with the EventLift-AQP
  results once Stage 4 lands.

### Stage gates and do-not-repeat
- Stage 1's gate must pass before Stage 2 (avoid building CERTIFY on a
  broken discover+audit core).
- If Stage 2's utility collapses to all-discover, that is a *negative
  result* about unified arbitration — report it, do not paper over it
  (per `FAILURES.md` style).
- Do NOT reuse outside-envelope AUDIT samples both to drive a stop decision
  AND to evaluate that decision (`AGENTS.md` hard constraint; §7 enforces
  batch separation).
- Do NOT tune on `probe_set_v1` or on non-dev segments.

============================================================
Appendix — execution record
============================================================

**Files created:** `EVENTLIFT_AQP_ALGORITHM_SPEC.md` (this file) only.
**Files modified:** none. No state file (`PROJECT_STATE.md`, `HANDOFF.md`,
`CLAIMS_LEDGER.md`, `FAILURES.md`, `AGENTS.md`, `TASK_QUEUE.yaml`,
`EXPERIMENT_REGISTRY.csv`) was touched. No `outputs/late_aqp_*` was modified.
No `RC_AQP_V1_SPEC.md` was created (per the hard constraint).

**No experiments run.** No video/GPU/VLM/YOLO inference. No baseline run.
No smoke run. No new outputs under `outputs/`.

**Source/data inspected (read-only):**
- `BASELINE_SOURCE_DATA_AUDIT.md` (the baseline audit)
- `RC_AQP_PREFLIGHT.md` (Gates 1-3, recommendation B+C)
- `PROJECT_STATE.md`, `HANDOFF.md`, `CLAIMS_LEDGER.md`, `FAILURES.md`,
  `AGENTS.md`
- `outputs/late_aqp_limited_oracle_frontier_v1/oracle_adapter_spec.md`
  (`query_unit` / `query_interval` contract)
- `outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv` (6
  segments, 63-157 bins, 6-20 events)
- `outputs/late_aqp_d3_accounting_fix_v1/d3_fixed_frontier_raw.csv`
  (B7-core / D3-norepair-core / D3-core-fixed columns, incl.
  `duplicate_sampling_rate`, `oracle_calls_total`, `strict_replay_or_posthoc`)
- `refe_repos/supg/supg/selector/recall_selector.py` (importance sampler,
  `sqrt(proxy)` weights, `SamplingBounds`)
- `refe_repos/abae/abae/algorithm.py` (`_execute_ours`, two-stage stratified,
  `Σ m_k p_k / Σ p_k`)
- `refe_repos/ARC-main/arc/arc.py` + `tools.py` (`findCandClips`,
  progressive sampling, label propagation)

**Open questions:**
1. **Utility hyperparameters `(λ, μ, η, κ)`.** Defaults are proposed in §5.1
   but must be tuned on the dev segment only. Whether the utility is
   sensitive to these (or collapses to all-discover regardless) is an
   empirical question for Stage 2's gate.
2. **AUDIT dual-purpose channel.** Whether AUDIT samples that turn out
   positive actually feed back into DISCOVER effectively (vs. being too
   late / too few to matter at B ≤ 120). This is Stage 1's gate question.
3. **Pooled residual report.** Whether the pooled-across-6-segments
   residual UCB is narrow enough to be a useful calibration report (vs.
   vacuous). `RC_AQP_PREFLIGHT.md` Gate 2 suggests `n_audit` ~30-80 pooled
   → `p_ucb` 0.05-0.10, useful but not tight. Needs Stage 4 to confirm.
4. **ARC-projection restricted subset.** Exactly which per-bin predicate to
   project the semantic event onto (e.g. `prior_score_max > θ` with
   `tau = 3 bins`). This is a Stage 3 design choice, not a Stage 1 blocker.
5. **Opportunity-cost term.** How to estimate
   `best_alternative_gain(n_calls)` cheaply without solving the full
   lookahead. Candidate: a roll-out of the utility over the top-k
   alternative actions at a 1-step horizon. Needs Stage 2 to validate.

**Recommended next implementation step:**
Begin Stage 1 — implement `SUPG-event` (bin-adapter + temporal grouping)
and `ABae-residual` (statistic≡1, two-stage stratified over `U`) on top of
the existing `src/garc_eval/adapters/{supg_adapter,abae_adapter}.py`, then
implement EventLift-AQP's DISCOVER+AUDIT core (no CERTIFY/SUPPRESS yet) on
the dev segment `realcartest_2000_3200` only, replaying the already-
labelled `center10_vlm_oracle_events.csv`. Output one small CSV +
`summary.md` under `outputs/eventlift_aqp_discover_audit_v1/`. Do NOT
proceed to Stage 2 until Stage 1's gate (residual calibration + dual-
purpose AUDIT) passes.
