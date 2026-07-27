# SCAN–CONFIRM Common-Utility Alignment Contract V1

Status: `FROZEN_BEFORE_STATIC_ALIGNMENT_AUDIT`  
Research problem: `SCAN_CONFIRM_COMMON_UTILITY_ALIGNMENT`  
Parent decision: `MYOPIC_VPS_V1=REJECTED_DUE_TO_UTILITY_SCALE_MISMATCH`

## Objective and frozen project state

Determine whether SCAN and CONFIRM can be valued in the same unit—expected new
distinct confirmed events—well enough for a causal one-step controller to
improve over the frozen `R4_RATIO_25_75` policy. The production/default policy
remains R4: 25% of realized action time to SCAN and 75% to CONFIRM. SCAN remains
`ANYTIME_LARGEST_GAP`; the Y8 candidate generator, score-only capacity-10
Frontier, highest-score CONFIRM target, physical Qwen Oracle outcomes, parser,
K3/materializer, deduplication, and durable commit remain unchanged.

Free Myopic-VPS V1 is rejected. Bandits and SMDPs remain deferred and RL is
prohibited. No estimator, controller, or repair may change the candidate
universe, event mapping, Frontier, CONFIRM target, reference, query, deadlines,
or materialization semantics.

This is a two-video/four-query development mechanism study. Primary static and
replay estimates use leave-one-video/query-group-out fitting: the held group is
identified only by the evaluator to construct a training split; group/video ID
is never a controller feature. Test remains sealed. No generalization claim is
available.

## Common terminal utility

Both action values use `EXPECTED_NEW_DISTINCT_CONFIRMED_EVENTS`.

For the highest-score legal Frontier witness `c`,

`V_confirm(c,s) = P(c atomically commits a new distinct reference event | H_t)`

and

`UVPS_confirm = V_confirm / cbar_confirm_complete`.

For SCAN, candidate arrival and conversion are explicitly composed. For each
frozen score bucket `j`, the online/development estimator provides expected new
arrival count `lambda_j` and new-event conversion probability `p_j`. Candidate
values `p_j` are inserted into the current Frontier-value multiset, respecting
capacity, score order, and remaining service slots. Let

`W(F,b) = sum of estimated new-event probabilities of the highest-priority
witnesses that can be fully CONFIRM+commit serviced within b`.

Then

`V_scan(s) = max(0, E[W(F union DeltaF, b-cbar_scan)] - W(F,b))`

and `UVPS_scan = V_scan/cbar_scan`. Fractional expected arrivals contribute a
fractional final candidate. This is a frozen deterministic approximation, not
an exact lookahead. It prevents candidate count from being treated as terminal
utility and assigns zero marginal value when new witnesses cannot enter a
serviceable slot.

## Estimators and legal information

Score buckets are LOW `[0,1/3)`, MEDIUM `[1/3,2/3)`, and HIGH `[2/3,1]`.
Coverage buckets use the same thirds. Frontier congestion is LOW for sizes 0–4
and HIGH for sizes 5–10. Candidate age is audited descriptively but is not used
in V1 because the frozen Frontier has no outcome-dependent aging and sparse
positive support would make a three-way table unstable.

Candidate arrivals use Gamma–Poisson shrinkage by coverage × score bucket with
global fallback below 5 SCAN observations. Candidate conversion uses
Beta–Bernoulli shrinkage by score × congestion with score-only then global
fallback below 5 CONFIRMable witnesses. Priors are group-external empirical
rates with strength 2, falling back to Beta(1,1)/Gamma(1,1) when the external
pool is empty. The current held group's future outcomes never initialize or
update these priors.

The new public state adds only `frontier_score_bucket_counts={LOW,MEDIUM,HIGH}`
and the current fitted arrival/conversion table; it exposes no candidate ID,
unit location, or future field. Online observations may update arrival counts
after completed SCAN and conversion outcomes after completed CONFIRM. Reference events, exhaustive
labels, future actions, future costs, and offline Oracle results are evaluator
only. Controller public state is the parent schema plus fitted bucket tables;
video ID and group ID are prohibited features.

Serviceability is deterministic under the conservative cost bound: the number
of full CONFIRM slots is `floor(remaining_budget / cbar_confirm)`. After a
prospective SCAN it is `floor((remaining_budget-cbar_scan)/cbar_confirm)`.
Capacity, queried witnesses, and score ordering are applied before W.

## Deadline admission and safety gate

The parent Q90 bound is rejected for this stage. Replay admission uses

`cbar(a) = Q0.99(development complete-action costs) + delta_safety(a)`,

where `delta_safety(a)=max(0.25 sec, observed_max-Q0.99+0.25 sec)`. Thus the
frozen replay bound equals observed development maximum plus 0.25 seconds. It
is a workload-scoped empirical bound, not a future WCET guarantee. All action
validation, SCAN stages, Oracle, parsing, materialization, deduplication, fsync,
atomic commit, Frontier update, and scheduler overhead are included exactly as
in the parent measured-action traces.

No action is interruptible. If no full action fits, STOP. Utility committed
after a deadline is zero. The replay and any future physical gate require zero
deadline overruns, zero post-deadline commits, and zero incomplete actions.
Before any formal physical claim, a disjoint calibration split and
split-conformal complete-action upper bound must be frozen.

## Static alignment audit

The audit dataset consists of causal states generated by independently reset R4
development replays. At every decision state, evaluator-only counterfactuals
compute:

- actual CONFIRM gain: whether the selected witness yields a new distinct event;
- actual SCAN aligned gain: the oracle-valued increase in serviceable Frontier
  event utility after the next frozen SCAN, net of its consumed service time;
- predicted common-utility values using only the other three groups and public
  history.

Primary static metrics are pairwise SCAN-vs-CONFIRM ranking accuracy on states
where both are legal and actual gains differ, balanced accuracy, Brier score for
CONFIRM, calibration by score bucket, predicted/actual action disagreement, and
coverage of every estimator cell. Actual-gain ties are excluded; predicted
UVPS ties receive 0.5 ranking credit and are reported separately.

Static Gate passes only if all are true:

1. at least 20 informative both-legal states exist across at least 3 groups;
2. ranking accuracy is strictly above 0.50 and its group bootstrap point delta
   over 0.50 is positive;
3. at least 2/3 of evaluable groups are nonnegative versus chance;
4. CONFIRM conversion Brier is below the external-pool constant-rate Brier;
5. no leakage or unsupported primary bucket occurs;
6. both SCAN and CONFIRM are predicted optimal in at least one state.

Failure stops controller evaluation and returns R4 unchanged.

## Controllers and replay

If the Static Gate passes, compare only:

- `R4_FIXED_25_75`;
- `FREE_COMMON_UTILITY_MYOPIC`;
- `RATIO_ANCHORED_COMMON_UTILITY`;
- evaluator-only `OFFLINE_ONE_STEP_ACTION_ORACLE`.

The anchored controller freezes `rho*=0.25`, `epsilon=0.05`, and common-utility
margin 0.0. Its total rule is:

1. STOP if no complete action fits;
2. SCAN if Frontier is empty and SCAN fits;
3. SCAN if realized SCAN share is below 0.20 and SCAN fits;
4. CONFIRM if realized SCAN share is above 0.30 and CONFIRM fits;
5. inside the band, choose the greater common-utility VPS;
6. exact ties follow the R4 ratio action;
7. if the desired action is illegal, use the other legal action, else STOP.

Replay uses 30/60/120/240 seconds, all four groups, and independent reset at
each budget. R4 and anchored stochasticity is absent; no configuration search
is allowed.

Replay Gate requires: positive macro utility-deadline AUC versus R4; no group
with negative AUC delta; nonzero SCAN and CONFIRM in every action-capable run;
positive leave-best-group-out; nonnegative 30-second macro delta; zero deadline
overrun/post-deadline/incomplete action; and benefit not driven by one budget.
Failure freezes `ADAPTIVE_SCAN_CONFIRM_CONTROL=NOT_ESTABLISHED` and selects R4.

## Physical execution gate

Only a passing Static Gate and Replay Gate authorize a new physical contract.
New combined end-to-end physical runs are mandatory before any wall-clock system
claim and are substantial compute requiring explicit user authorization. Trace
composition can never upgrade itself to formal physical evidence.

## Outputs and stopping

Outputs live under `outputs/scan_confirm_common_utility_v1/` with contracts,
audits, static_alignment, replay, statistics, physical_validation, reports,
repair log, and artifact hashes. Required reports are identification audit,
conversion/calibration report, static ranking report, controller replay report,
deadline safety report, failure analysis, independent completion audit, and
final decision.

Stop immediately for insufficient conversion positives, non-identifiable
serviceability, leakage, failed Static Gate, starvation, failed Replay Gate,
deadline overrun, or need to modify the frozen Frontier/CONFIRM chain. Only one
controlled engineering repair cycle is permitted and cannot alter scientific
semantics or delete adverse results.

This file becomes immutable when its SHA-256 enters the new freeze manifest.
