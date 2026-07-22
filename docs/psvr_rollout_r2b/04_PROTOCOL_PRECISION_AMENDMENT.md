# H1B result-blind protocol precision amendment

This amendment changes no 1A claim and creates no H1B result. It makes the
H1B draft executable only after a future implementation/freeze review.

## Fixed primary target and topology

The sole confirmatory compute target is `(64 posterior worlds, 64 continuation
trajectories)`. The `(4,4)`, `(16,16)`, and `(256,256)` settings are
diagnostic-only and can never select an ACCEPT branch. The primary policy is
planning-time-aware LCB fallback. Error/planning robustness is evaluated on the
fixed lattice: magnitude `0, .05, .10, .20` × planning ticks `0,2,5,10,20`,
at the primary compute target, separately for each error mechanism/form.
The required continuous neighborhood is the three consecutive positive-cost
cells `P=2,5,10` at one fixed magnitude and mechanism/form. Joint corners are
reported separately and never counted as this neighborhood.

## Deterministic model-error semantics

The true toy environment remains unperturbed. Error affects only the planner's
generative model. For H1B seed `s`, decision `j`, mechanism `k`, form `f`, and
trajectory `n`, derive `z in {-1,+1}` from SHA-256 of the canonical UTF-8 key
`H1B_ERROR|s|j|k|f|n`; map its first bit to the sign. Independent variance uses
that sign independently per trajectory. Systematic optimism uses `+1` for every
key; systematic pessimism uses `-1`; state-dependent uses `+1` iff the visible
candidate has the maximum frozen `score_bin` among current frontier candidates,
otherwise `-1`. Empty frontiers use `-1`.

For probability `p`, the planner uses `clip(p + sign*magnitude, .01, .99)`.
For duration `d`, it uses `max(1, ceil(d*(1 + sign*magnitude)))`. Candidate
yield is a per-candidate retention probability; grouping transition is a
probability that two candidates with equal frozen `hypothesis_id` are grouped;
novelty is the probability an otherwise positive confirm maps to a new token;
materialization success is the positive-token emission probability. Joint
corner uses one common sign derived with `k=JOINT` and applies the same rule to
all six mechanisms. All random draws use the same canonical key with an added
draw index; no draw reads an outcome or future region.

## Planning and fallback sequence

At each decision with remaining time `R`, immediate pi0 acts without planning.
Each approximate policy first checks `R>P`; if false it executes pi0 directly.
If true, it consumes exactly `P` SMDP ticks, then draws all fixed 64×64 paired
samples using the post-planning visible state and selects an action from actions
legal at that state. Thus estimator computation and admission have no hidden or
double-counted time cost. Ungated rollout selects the largest paired mean;
point fallback overrides only when that mean is positive; LCB and
planning-admission+LCB override only when the frozen 95% normal paired LCB is
strictly greater than `b_model + P`. The latter name means *override admission*,
not a zero-cost pre-planning screen. Planning invocation is counted whenever
`R>P`; admission frequency is the fraction of invocations that override pi0.

## Gate definitions and unique branch order

`b_model` is zero except for the joint corners, where it is `0.20*1600` utility
ticks. The paired LCB is `mean(D)-1.96*sample_sd(D)/sqrt(n)`; zero variance uses
the mean. Incorrect override means an approximate override whose evaluator-only
exact-M1 paired action value is less than pi0's. Paired regret is
`max(0, G(exact_M1)-G(selected))`; paired loss is `G(policy)-G(pi0)`, and its
5th percentile is the nearest-rank empirical 0.05 quantile. Major process
families are exactly `UNIFORM_SPARSE`, `UNIFORM_DENSE`, and
`BURSTY_CLUSTERED`; their collapse bound uses each family's mean immediate-pi0
utility, which must be positive or the experiment is integrity-blocked.

Decision order is unique: (1) integrity failure => BLOCKED; (2) primary-target
ACCEPT conditions => ACCEPT; (3) any positive finite-cost primary cell but
neighborhood/no-collapse failure => PARTIAL; (4) no positive-LCB finite-cost
exact-model primary cell => REJECT_PLANNING_COST_ERASES_GAIN; (5) an exact-model
finite-cost positive cell but no nonzero-error positive cell =>
REJECT_MODEL_ERROR_ERASES_GAIN; (6) otherwise => REJECT_APPROXIMATION_UNSTABLE.
