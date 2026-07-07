# RC-AQP Preflight Check

> This document records the preflight check before any RC-AQP (Residual-Certified
> Event-Coverage AQP) implementation is committed. It is *read-only* with respect
> to all existing state files, final reports, and canonical outputs. No new
> experiment, oracle, VLM, YOLO or GPU run was performed. No artifact >100MB was
> created or modified. The deliverable is this file plus the four small CSVs in
> `outputs/rc_aqp_preflight/` and `scripts/rc_aqp_mucb_feasibility.py`.
>
> All numbers below are **oracle-relative** (VLM labels in
> `center10_vlm_oracle_events.csv` / `reference_events.csv`), not human ground
> truth and not formal statistical guarantees. Per AGENTS.md: no "formal
> guarantee", "certificate", or "statistical bound" is claimed.

============================================================
1. Repository and state audit
============================================================

- Current git commit: `6a3de200c286b90af6cdd16e6806e3ec2e0fa69e`
- Branch: `main`, status line `* main 6a3de20 [origin/main: ahead 7]` → branch
  is **ahead of origin by 7 commits**. These commits are the historical
  "state sync round 19" batch and are **not pushed** in this session (per the
  hard constraint "Do not push").
- Working tree: **clean** (`git status --porcelain` returned nothing before
  this session started; all preflight outputs are new untracked files).
- Tracked files > 100 MB (run via `git ls-files | du -b`), confirmed present:

  | Path | Size |
  |---|---|
  | `src/garc_eval/outputs/cils_empty_return_root_cause_audit_v1/cils_rejection_trace.csv` | 638 MB |
  | `src/garc_eval/outputs/cils_calibration_repair_smoke_v1/smoke_candidate_p_answer.csv` | 503 MB |
  | `src/garc_eval/outputs/cils_calibration_repair_replay_v1/candidate_p_answer_by_policy.csv` | 195 MB |
  | `src/garc_eval/outputs/synthetic_cheap_signal_downstream_validation_v1/synthetic_signal_candidates.csv` | 120 MB |

  These are the same four large artifacts listed in
  `outputs/state_sync_late_aqp_v1/large_artifact_manifest.md`. They are not
  modified, not gitignored, not externalized (decision T021 still pending).
  **Risk: high-byte blobs in history inflate clone size; no action taken here.**

- Project-state files read for this preflight:
  - `AGENTS.md`, `PROJECT_STATE.md`, `HANDOFF.md`, `TASK_QUEUE.yaml`,
    `CLAIMS_LEDGER.md`, `FAILURES.md`,
    `outputs/state_sync_late_aqp_v1/large_artifact_manifest.md`,
    `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md`,
    `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` and
    `unique_event_coverage.csv`,
    `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md` and
    `segment_info.csv` / `d3_fixed_frontier_raw.csv`,
    `outputs/late_aqp_repair_negative_diagnosis_v1/FINAL_DIAGNOSIS.md` and
    `repair_budget_diversion_report.md` / `net_effect_decomposition.md`,
    `reports/evidence_audit_strategy7_budget_certificate_cost_v1/EVIDENCE_AUDIT.md`,
    `docs/G-ARC_Research_Report.md`, `docs/GARC_EVAL_BUILD_PLAN.md`,
    `src/garc_eval/adapters/supg_adapter.py` and the `run_supg_*` experiments.

- Stale claims check. I scanned the root-state files for the four flagged
  wordings. Results:

  | Stale wording                                  | Found in canonical state? | Note |
  |---|---|---|
  | "LATE beats B7-core" / "LATE-AQP beats B7-core" | No (explicitly disallowed in `CLAIMS_LEDGER.md` line 75; FAILURES.md line 28; AGENTS.md `never` list) | Clean |
  | "Core/Halo is LATE-specific"                    | No (explicitly disallowed in `CLAIMS_LEDGER.md` line 76; FAILURES.md line 39; AGENTS.md `never` list) | Clean |
  | "repair is net-negative only because of accounting bug" | No. The disallowedConviction wording is "repair is net-negative (settled)" and is explicitly disallowed. The clean post-fix statement "neutral after the fix" is canonical. (`CLAIMS_LEDGER.md` line 77; `FAILURES.md` line 46) | Clean |
  | "cheap selector smoke is the next mainline"     | No. The state files explicitly demote the Phase 3 smoke to a completed_negative diagnostic (`PROJECT_STATE.md` line 14; `HANDOFF.md` line 56; `FAILURES.md` line 7) | Clean |

  No stale claim was found in the canonical state files. The research-report
  drafts in `docs/` and `reports/` do contain historical wording about SUPG and
  certificates, but those are *historical research drafts*, not canonical
  state, and per AGENTS.md they are not to be edited.

============================================================
2. Gate 1: repair failure diagnosis
============================================================

**Hypothesis under test:**

  H1: repair is neutral/negative not because local expansion is intrinsically
  useless, but because side-channel repair and the main bandit/discovery loop
  compete for the same oracle budget without a unified utility or ledger.

**Evidence inspected (concrete file paths):**

  - `outputs/late_aqp_repair_negative_diagnosis_v1/FINAL_DIAGNOSIS.md`
  - `outputs/late_aqp_repair_negative_diagnosis_v1/repair_budget_diversion_report.md`
  - `outputs/late_aqp_repair_negative_diagnosis_v1/net_effect_decomposition.md`
  - `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md`
  - `outputs/late_aqp_d3_accounting_fix_v1/repair_budget_diversion_after_fix.csv`
  - `outputs/late_aqp_d3_accounting_fix_v1/d3_fixed_frontier_raw.csv`
  - `outputs/late_aqp_event_diverse_discovery_v1/unique_event_coverage.csv`
  - `outputs/late_aqp_event_diverse_discovery_v1/repair_marginal_value_report.md`
  - `outputs/late_aqp_algorithm_v3_oracle_relative/FINAL_REPORT.md`
  - `outputs/late_aqp_frozen_cross_segment_v1/repair_trace_logging_spec.md`

**Short summary of evidence:**

  1. **Pre-fix budget diversion (real, recorded):**
     `repair_budget_diversion_report.md` reports 38 logged repair calls, of
     which **25 (65.8 %)** picked a chunk with strictly lower bandit θ than
     the best unqueried chunk. Per-segment diversion rate reaches 82.4 % on
     `realcartest_0_1570` and 100 % on `realcartest_3200_3830`. This is direct
     evidence that repair and the chunk-bandit were competing for the same
     oracle budget, and that repair did so without referencing the bandit's
     expected-information utility — i.e. two separate ledgers.

  2. **Accounting bug (the dominant confound, now fixed):**
     `FINAL_DIAGNOSIS.md` reports 981 discovery calls in D3-core re-queried
     bins already queried by audit/repair because
     `discovery_d3_chunk_bandit` ignored the `queried` argument. This is a
     *separate* failure from H1, but it is the precondition the fix deleted.

  3. **Post-fix residual gap is *pure* budget contention:**
     `late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md` states: "After the
     accounting fix, repair calls no longer preempt higher-theta chunks
     (146 repair calls, 0 diversion, 0.0 %). The remaining performance gap
     vs D3-norepair is therefore **not caused by budget diversion, but by the
     fact that repair consumes budget that could otherwise go to global bandit
     exploration**." This sentence is *the* empirical anchor for H1: even
     after the bug is gone, the loss is exactly the ledger contention that a
     unified utility would have made explicit.

  4. **Per-trial net effect:**
     `net_effect_decomposition.md` over 45 trials: "D3-core has on average
     **−0.8 fewer unique bins queried** than D3-norepair, while using 0.8
     repair calls and 21.8 duplicate discovery calls. The lost unique bins are
     the primary driver of lower event recall." The lost-unique-bin count is
     the *missing* term that a unified oracle budget ledger would have to
     price in.

  5. **Marginal value comparison:**
     `late_aqp_d3_accounting_fix_v1` shows D3-core-fixed wins on 1/6 segments
     vs D3-norepair and 0/6 vs B7-core. The repair-vs-no-repair difference is
     non-positive on the chunk-bandit backbone — consistent with H1 (the loss
     is from offsetting discovery budget, not from a broken repair primitive).

  6. **Missing evidence (honestly listed):**
     `late_aqp_algorithm_v3_oracle_relative/FINAL_REPORT.md` Q4/Q5 and
     `FAILURES.md` line 87 note that the v3 replay's `source_action` lineage
     is `unknown_not_logged` for many intervals. **There is no clean
     per-segment, per-call unified ledger yet** that labels every oracle call
     with the action type that emitted it. The closest artefacts are
     `late_aqp_frozen_cross_segment_v1/repair_trace_calls.csv` and
     `repair_trace_selected_intervals.csv` (clean schema) — but the v3
     `source_action` lineage gap is an open hole.

What would falsify H1: a future strict-replay run with a *unified* ledger and
a *unified utility* (one that prices both repair and bandit exploration in the
same information-gain currency) where repair *still* loses by an amount that
can be fully attributed to local expansion being intrinsically weak. That run
has not happened yet.

**Gate 1 status:** PASS.

**Implication for RC-AQP:** The empirical motivation for a *unified oracle
budget ledger* + *unified utility* is supported. The current LATE-AQP budget
accounting (audit / discovery / repair / guard, 4-way) is logged but *not
priced in a single currency* and the post-fix residual gap is exactly the
symptom H1 predicts. RC-AQP's "unified budget ledger" component is therefore
empirically grounded, not speculative.

============================================================
3. Gate 2: M_UCB / RecallLCB feasibility arithmetic
============================================================

Run script: `scripts/rc_aqp_mucb_feasibility.py` (no oracle, no model, no new
discovery; reconstructs audit counts from existing `segment_info.csv` only).

Outputs:

  - `outputs/rc_aqp_preflight/mucb_feasibility.csv` (per-segment, all budget
    ratios × audit shares × discovery method)
  - `outputs/rc_aqp_preflight/mucb_unit_agnostic_reference.csv`
  - `outputs/rc_aqp_preflight/mucb_required_n.csv`
  - `outputs/rc_aqp_preflight/m_allowed_table.csv`
  - `outputs/rc_aqp_preflight/mucb_feasibility_summary.md`

**Per-segment event scale (from `segment_info.csv`):**

  | segment_id | num_units | num_positive_units | num_events |
  |---|---:|---:|---:|
  | realcartest_0_1570 | 157 | 44 | 20 |
  | realcartest_2000_3200 | 120 | 32 | 20 |
  | realcartest_3200_3830 | 63 | 13 | 7 |
  | dataset3_0_1200 | 120 | 7 | 6 |
  | dataset3_1200_2400 | 120 | 21 | 12 |
  | dataset3_2400_3462 | 107 | 12 | 9 |

Per-segment event counts are ~6-20; the smallest segment has only 6 events.

**The binomial zero-hit upper bound, `p_ucb(n, alpha) = 1 - alpha**(1/n)`,
alpha = 0.05:**

  | n_audit | p_ucb |
  |---:|---:|
  | 5 | 0.451 |
  | 10 | 0.259 |
  | 15 | 0.181 |
  | 20 | 0.139 |
  | 30 | 0.095 |
  | 50 | 0.058 |
  | 80 | 0.037 |
  | 120 | 0.025 |

**Min n_audit to obtain p_ucb <= target (alpha = 0.05):**

  | p_ucb_target | min_n_audit |
  |---:|---:|
  | 0.20 | 14 |
  | 0.10 | 29 |
  | 0.05 | 59 |
  | 0.02 | 149 |

Even at a **30 % budget ratio with a 20 % audit share**, on the largest
segment (`realcartest_0_1570`, 157 units) the audit n is only **9 samples**
→ p_ucb = 0.283. Across the six segments the largest audit n at this
budget / share combination is ≤ 9. For p_ucb ≤ 0.10 you need n_audit ≥
29, which implies ≥ ~30 % audit on a ≥ 80-call budget — i.e. an
audit-heavy regime that shrinks discovery budget to near trivial.

**M_allowed for RecallLCB >= tau_r** (`M_allowed = D * (1/tau_r - 1)`)
is tiny on these segments even for the strongest baseline (`B7-core`,
discovered counts ≤ 6.4):

  | tau_r | D_B7 max (across segs) | M_allowed |
  |---:|---:|---:|
  | 0.80 | 6.4 | 1.60 |
  | 0.90 | 6.4 | 0.71 |
  | 0.95 | 6.4 | 0.34 |

For RecallLCB ≥ 0.90, the audit must certify that *fewer than one event* of
residual mass remains uncovered. With p_ucb ≥ 0.18 at the realistic audit
sizes, this is not statistically credible.

**Unit-level RecallLCB (loose upper upper bound, see `mucb_feasibility.csv`):**
At the largest segment / 30 % budget / 20 % audit share, RecallLCB_unit ≈
0.125 (against D_B7 = 6.0). On the smallest segments it is < 0.03. These
numbers are dominated by the `num_units − n_audit` upper bound on
uncovered units and say nothing useful at the per-segment level.

**Honest reading of the small-sample concern (per AGENTS.md):**

  > Per-segment oracle event counts are ~6-20 and audit_n at low budget is
  > often ≤ 15; per-segment safe stopping at tau_r ≥ 0.9 is statistically
  > weak (p_ucb(15) = 0.181, p_ucb(10) = 0.259).

Pooling the six segments raises the total audit n by ≈ 6× but changes the
unit definitions: the residual becomes "uncovered events across the pooled
segment batch", not per-segment. That claim is still meaningful but **it
is not the same claim as per-segment safe stopping**.

**Precedent from the legacy audit:** `reports/evidence_audit_strategy7_
budget_certificate_cost_v1/EVIDENCE_AUDIT.md`:

  - Exact hypergeometric bound: coverage 1.0 ≥ 0.95 nominal **validated**
    under Monte Carlo. Temporal clustering does not invalidate SRSWOR.
  - But the bound is **too conservative for practical use**: R_lower
    0.02-0.08 vs true recall 0.19-0.50 on the same videos.
  - On realcartest (94 frame-level positives at the time), the certificate
    was UNDERPOWERED; Phase 0.6 power simulation estimated ~500 events for
    a non-vacuous γ=0.30 certificate, vs ≤ 51 available. This is the same
    small-sample wall we are seeing above.

**Gate 2 status: CONDITIONAL.**

- **Per-segment safe stopping (tau_r ≥ 0.9): FAIL** on the current six
  segments. The audit sample sizes that the LATE-AQP budgets support are
  statistically too small to certify a 90 % event recall with a zero-hit
  upper bound. This is not fixable by aggregation within one segment.
- **Pooled-segment residual reporting: feasible but weak.** The audit n
  can be pushed to ~30-80 by pooling the 6 segments, which makes `p_ucb`
  useful (0.05 < p_ucb ≤ 0.10). The residual claim becomes *global* ("across
  this batch of 6 segments, M_ucb≤X"), not per-segment.
- **Larger audit share scenario:** feasible only if you sacrifice
  discovery budget, i.e. move into an audit-heavy regime where the
  question is no longer "discover under B" but "verify the discovery we
  already have". That is a sensible regime for an RC-AQP *audit layer*.
- **Unit redefinition:** feasible if the residual mass is defined over a
  *coarser unit* (e.g. pooled segment) than per-segment histograms.

**Implication for RC-AQP:**

  - The "stop certificate" framing is **not supportable at the per-segment
    level** at current event counts. Re-scope the claim from "safe
    stopping" to "**residual uncertainty reporting / calibration under
    limited budget**" (recommendation C in the global decision section).
  - The M_UCB estimator itself is honest and computable; only the implied
    guarantee level is too tight.
  - A pooled "across-the-batch residual mass" certificate *is* feasible as
    a calibration report, not as a per-segment guarantee.

============================================================
4. Gate 3: SUPG baseline status
============================================================

Searched the repo for: SUPG implementation, SUPG-like threshold calibration,
approximate selection baseline, ABae baseline, frame-level
precision/recall guarantee baseline, residual missing-mass estimator,
event-level RecallLCB / stop certificate.

### 4.1 What exists

- **SUPG frame-level implementation: present.**
  - `src/garc_eval/adapters/supg_adapter.py` wraps `refe_repos/supg`
    (`RecallSelector` / `ImportancePrecisionTwoStageSelector`) and exposes
    `run_supg_rt` (recall-target) and `run_supg_pt` (precision-target).
  - Experiments: `src/garc_eval/experiments/run_supg_synthetic.py`,
    `run_supg_real_frames.py`, `run_frame_clip_gap.py`,
    `run_proxy_score_ablation.py`.
  - U-CI / U-NOCI baselines: `src/garc_eval/baselines/u_ci.py`,
    `u_noci.py`.
  - Build plan: `docs/GARC_EVAL_BUILD_PLAN.md` §3 ("SUPG Reuse Plan") and
    §5 (`supg_rt_plus` / `supg_pt_plus` to be added — never landed in
    `src/garc_eval/baselines/` — confirmed: that directory only contains
    `u_ci.py`, `u_noci.py`, `uniform_aggregation.py`).
  - `refe_repos/supg` is vendored in the repo.

- **ABae frame-level implementation: present.**
  - `src/garc_eval/adapters/abae_adapter.py`, plus
    `run_abae_synthetic.py`, `run_abae_real_frames.py`.

### 4.2 What does NOT exist

- **No event-level / clip-level grouping on top of SUPG.** The planned
  `supg_rt_plus` / `supg_pt_plus` ("SUPG frame selection, then merge to
  candidate clips") in `docs/GARC_EVAL_BUILD_PLAN.md` lines 411-412 were
  never created — `src/garc_eval/baselines/` shows no `supg_rt_plus.py` /
  `supg_pt_plus.py`. The only frame→clip machinery is
  `run_frame_clip_gap.py`, which produces the gap statistics, not a
  baseline.

- **No SUPG run against the LATE-AQP benchmark.** All existing SUPG
  outputs live under `experiments/frame_level/uadetrac_temporal/**` — a
  legacy frame-level benchmark, not the six `late_aqp` event segments.
  `glob` over `src/garc_eval/outputs/**/*supg*` returned **no** event-level
  SUPG output. The closest SUPG evaluation used the old `V13.8` realcartest
  oracle (94 frame-level positives) per
  `reports/evidence_audit_strategy7_budget_certificate_cost_v1/EVIDENCE_AUDIT.md`,
  not the per-event `center10_vlm_oracle_events.csv` used by LATE-AQP.

- **No residual missing-mass estimator / event-level RecallLCB / stop
  certificate.** `grep` across the repo for
  `missing_mass`, `M_UCB`, `RecallLCB`, residual missing-mass hits the
  design docs (`docs/G-ARC_Research_Report.md` §4.1-§4.3) which argue that
  SUPG's frame-level guarantee *cannot* be transferred to the clip/event
  level because (i) frames are temporally dependent (CLT independence
  broken), (ii) frame-level recall ≠ clip/event-level recall (IoU hit
  definition returns non-monotonic merge/split between candidates). No code
  computes an event-level residual mass.

### 4.3 Implication

SUPG as it stands is frame-level only and has never been measured against
the LATE-AQP event segments. The legacy certificate experiment
(`reports/evidence_audit_strategy7_budget_certificate_cost_v1`)
validated that the *hypergeometric* bound mechanism has correct coverage
(1.0 ≥ 0.95 nominal under Monte Carlo) but **found it too conservative
for practical use** (R_lower 0.02-0.08 vs true recall 0.19-0.50). The
phenomenon that the certificate would be underpowered at this sample size
is therefore *already demonstrated* on these videos.

The claimed RC-AQP contribution (audit ledger + residual missing-mass +
event-level RecallLCB + unified budget accounting) is **not** covered by
the existing SUPG implementation, and the existing legacy bound already
shows underflow on the realcartest scale. So a minimal SUPG baseline is
genuinely needed to ground any "RC-AQP adds an event-level residual
certificate that SUPG lacks" claim.

**Gate 3 status: PASS** (SUPG exists at frame level and lacks event-level
residual certificate, exactly matching the PASS definition). The minimal
baseline is not yet implemented against the LATE-AQP segments, so a
concrete minimal implementation plan is required before publishing RC-AQP
performance claims.

### 4.4 Minimal SUPG baseline implementation plan

This is a *design only* — no implementation is done in this preflight.

**Scope of a minimal baseline:** three components wrapped in one script,
no new oracle / GPU / VLM.

  1. `SUPG-precision` and `SUPG-recall` (frame-level)
  2. `SUPG-clip` — frame-level selection + temporal grouping into events
     (the missing `supg_rt_plus` / `supg_pt_plus` from the build plan)
  3. `SUPG-verify` — run the SUPG selection under the existing LATE-AQP
     `oracle_adapter_spec` so the audit budget is counted exactly as the
     LATE-AQP methods count it (one call per `query_unit` /
     `query_interval`)

**Required existing files (no new artifacts):**
  - `src/garc_eval/adapters/supg_adapter.py`
  - `src/garc_eval/baselines/u_ci.py`, `u_noci.py`
  - `outputs/late_aqp_limited_oracle_frontier_v1/oracle_adapter_spec.md`
    (defines `query_unit` / `query_interval` and the budget counter)
  - `center10_vlm_oracle_events.csv`, `dataset3_full_center10_parsed.csv`
    (the reference labels for the 6 LATE-AQP segments)
  - `outputs/late_aqp_d3_accounting_fix_v1/segment_info.csv` (defines the
    atomic units per segment)

**Inputs:**
  - per-segment `id`, `proxy_score`, `label` table — the existing
    `interval_features_with_signal_v2.csv` (`outputs/cheap_signal_v2/`)
    can supply a proxy, or uniform random proxy can be used as a
    conservative variant.
  - per-segment budget B (same grid as `late_aqp_limited_oracle_frontier_v1`)
  - gamma = {0.90, 0.95}, delta = 0.05.

**Outputs (one CSV + one MD, no large artifacts):**
  - `outputs/rc_aqp_supg_baseline_v1/per_segment_results.csv`
    (segment_id, method∈{SUPG-RT, SUPG-PT, SUPG-clip}, budget, gamma,
    delta, seed, oracle_calls, event_precision, event_recall,
    unique_event_coverage, B_90_90, alternative_T_oracle_calls,
    residual_estimate_present [=false for SUPG])
  - `outputs/rc_aqp_supg_baseline_v1/baseline_summary.md`

**How to adapt frame-level selection to event-level evaluation:**
  - Run SUPG-RT/PT on the atomic bins (each bin = one oracle-queryable
    unit per `segment_info.csv`). Use the closed oracle label per bin.
  - Map selected bins to events via temporal adjacency (the same
    merge rule LATE-AQP uses, documented in
    `late_aqp_frozen_cross_segment_v1/repair_trace_logging_spec.md`).
  - Compute event_precision / event_recall against
    `center10_vlm_oracle_events.csv` with the same IoU threshold the
    LATE-AQP reports use (0.3 per `phase3_selector_smoke_v1`).

**Metrics:**
  - `B_90/90` (per method per segment)
  - event_precision, event_recall
  - unique_event_coverage (count distinct reference events IoU ≥ 0.3 hit)
  - oracle_calls (asserted ≤ B)
  - **whether any residual estimate is present: false for SUPG.** This is
    the column that distinguishes the RC-AQP layer from the SUPG baseline.

**Run cost:** Each segment has 63-157 units, 5 budgets × 5 seeds ×
2 gamma × 2 methods = 50 trials per segment; ↔ ~300 oracle calls per
segment coming from the *already-labelled* `center10_vlm_oracle_events.csv`
(replay, not new VLM calls). This stays well under the "do not run large
experiments" hard constraint. Total wall time expected to be minutes on
CPU.

**Trivial-or-not test:** A *real-mist* implementation (~200-300 LOC) is
plausibly implementable without new oracle calls because all labels are
already in the CSV. So this plan is implementable under the current
no-VLM/no-GPU constraint.

============================================================
5. Overall decision
============================================================

| Gate | Status | Evidence | Consequence |
|---|---|---|---|
| Gate 1 repair diagnosis | PASS | `repair_budget_diversion_report.md` (25/38 diverted pre-fix); `late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md` (0 diversion post-fix, gap "not caused by budget diversion, but by … repair consumes budget that could otherwise go to global bandit exploration"); `net_effect_decomposition.md` (−0.8 unique bins avg) | Unified oracle-budget ledger + unified utility is empirically motivated. The new RC-AQP "unified budget ledger" component is grounded. |
| Gate 2 M_UCB feasibility | CONDITIONAL | `outputs/rc_aqp_preflight/*`: p_ucb(15)=0.181, min n_audit for p_ucb ≤ 0.05 is 59; per-segment RecallLCB_unit ≤ 0.13 at 30% budget / 20% audit; legacy `strategy7_certificate_power_v1` already showed R_lower 0.02-0.08 vs true 0.19-0.50 | Per-segment safe stopping FAILS. Pooled-segment residual reporting feasible. **Re-scope the certificate wording.** |
| Gate 3 SUPG status | PASS | `src/garc_eval/adapters/supg_adapter.py` exists for RT/PT (frame level); the planned `supg_rt_plus`/`supg_pt_plus` event-level adapters in `docs/GARC_EVAL_BUILD_PLAN.md` lines 411-412 were never created; no SUPG output on the LATE-AQP segments; no residual missing-mass / event-level RecallLCB / stop certificate code; `EVIDENCE_AUDIT.md` already showed the legacy bound too conservative for practical use | RC-AQP's residual certificate is not covered by existing SUPG. A minimal baseline plan is in §4.4 and should land before any RC-AQP-vs-SUPG performance claim. |

**Recommendation: B with C re-scoping (do not proceed to RC_AQP_V1_SPEC.md yet,
but proceed to a *design* doc that re-scopes the contribution).**

Reasoning:
  - Gate 1 PASS: the unified-ledger motivation is empirically grounded. ✓
  - Gate 2 CONDITIONAL: per-segment safe stopping is not statistically
    supportable at current event counts. This is an honest, conservatively
    re-scopeable problem: downgrade "stop certificate" → "residual
    uncertainty reporting / calibration under limited budget". Apply
    recommendation C.
  - Gate 3 PASS: a minimal SUPG baseline plan exists, but has not been
    implemented against the LATE-AQP segments. To avoid making claims
    before having a comparable baseline, the spec must call out the
    SUPG-clip baseline as a required prerequisite deliverable, not as an
    optional add-on.

Concretely, the next-step document (T020 successor) should NOT be named
`RC_AQP_V1_SPEC.md` claiming a "safe stopping certificate". It should be
a **design doc** that:

  1. Re-frames the contribution as completing + evaluating a
     "residual-certified AQP layer for budgeted temporal event discovery"
     with the discovery layer = strong existing baselines (B7-core /
     D3-norepair-core), and the new evaluated layer = audit ledger +
     residual missing-mass estimator + a **calibration** (not high-
     probability stopping) RecallLCB report + unified budget accounting.
  2. Pins Gate 1's unified-ledger motivation as the *first* evaluated
     component (lowest cost, strongest empirical anchor).
  3. Pins Gate 3's minimal SUPG-clip baseline as a *required* prerequisite
     before any RC-AQP-vs-baseline claim.
  4. Carries Gate 2's recommendation-C re-scope explicitly: the residual
     report is a calibration output, not a guarantee; numbers must be
     reported pooled + per-segment with the caveat that per-segment
     p_ucb(≤15) ≈ 0.18-0.26.

============================================================
6. Required final wording discipline
============================================================

**Supported contribution framing (use this, subject to the Gate 2 re-scope):**

  > We complete and evaluate a residual-certified AQP layer for budgeted
  > temporal event discovery. The discovery layer uses strong existing
  > baselines such as B7-core / D3-norepair-core. The new evaluated layer
  > is the audit ledger, residual missing-mass estimator, a RecallLCB
  > calibration report (not a high-probability stop certificate), and a
  > unified budget accounting that prices audit / discovery / repair / guard
  > calls in a single information-gain currency.

**Unsuppported framing (do NOT use, per AGENTS.md `never` list and
ClaimS_LEDGER disallowed wordings):**

  - "We invent a completely new AQP paradigm." — unsupported.
  - "EC-UCB is a novel exploration algorithm." — unsupported (component
    abstraction / exploration are existing).
  - "Component abstraction is a new contribution." — per AGENTS.md.
  - "Beta-Bernoulli new-event posterior is novel over ExSample."
    — unsupported.
  - "Core/Halo is LATE-specific." — explicit `never` list entry.
  - "Residual missing-mass estimator gives a safe stopping certificate at
    the per-segment 90/90 frontier." — contradicted by Gate 2.
  - "The residual bound is a formal guarantee / certificate / statistical
    bound." — explicit disallowed wording (CLAIMS_LEDGER line 87; AGENTS.md
    `never` list).

============================================================
Appendix — execution record
============================================================

**Files created (all new; small; CSV + MD only):**
  - `RC_AQP_PREFLIGHT.md` (this file)
  - `scripts/rc_aqp_mucb_feasibility.py` (~280 LOC, pure arithmetic)
  - `outputs/rc_aqp_preflight/mucb_feasibility.csv`
  - `outputs/rc_aqp_preflight/mucb_unit_agnostic_reference.csv`
  - `outputs/rc_aqp_preflight/mucb_required_n.csv`
  - `outputs/rc_aqp_preflight/m_allowed_table.csv`
  - `outputs/rc_aqp_preflight/mucb_feasibility_summary.md`

**Files modified:** none.

**Commands run:**
  - `git config --global --add safe.directory /qiuyeqing/llama_prl/G-ARC`
    (one-time, to make `git status` work under the env's dubious-ownership
    protection; this is the documented workaround in `FAILURES.md` line 81)
  - `git rev-parse HEAD`, `git status --porcelain`, `git branch -vv`,
    `git ls-files | du -b` (read-only audit, no write)
  - `python3 scripts/rc_aqp_mucb_feasibility.py` (Gate 2 arithmetic; no
    oracle, no model, <1 ms runtime)

**Commands NOT run (per hard constraints):**
  - No `git push`, no `git commit`, no `git add`.
  - No oracle, VLM, YOLO, GPU, or new discovery run.
  - No edit of any `FINAL_REPORT.md`, `final_recommendation.md`,
    `EXPERIMENT_REGISTRY.csv`, `PROJECT_STATE.md`, `HANDOFF.md`,
    `CLAIMS_LEDGER.md`, `FAILURES.md`, `TASK_QUEUE.yaml`, `AGENTS.md`.
  - No new experiment under `outputs/late_aqp_*`.
  - No movement of the four >100 MB tracked artifacts.

**Missing evidence (registered, not invented):**
  - A clean strict-replay per-call unified ledger that labels every
    oracle call with its `source_action` (gap noted by
    `late_aqp_algorithm_v3_oracle_relative/FINAL_REPORT.md`; the closest
    existing schema is `late_aqp_frozen_cross_segment_v1/repair_trace_
    calls.csv`, but v3 lineage is `unknown_not_logged` in many rows).
  - A `SUPG-clip` / `SUPG-verify` baseline run against the 6 LATE-AQP
    segments (the planned `supg_rt_plus`/`supg_pt_plus` never landed).
    Plan attached in §4.4.
  - Human-validated labels: all event counts used here are
    VLM-oracle-relative, not human ground truth (per AGENTS.md labeling
    rules).

**Recommended next task:** write a design-only doc (successor to T020)
that re-scopes the contribution per Recommendation B + C above — i.e. an
"audit ledger + residual calibration + unified budget accounting" layer
evaluated against B7-core / D3-norepair-core, with the minimal SUPG-clip
baseline of §4.4 as a required prerequisite, and with the contribution
wording kept to "residual uncertainty reporting / calibration under
limited budget" — not "safe stopping certificate". Do not create
`RC_AQP_V1_SPEC.md` with a stopping-certificate framing.