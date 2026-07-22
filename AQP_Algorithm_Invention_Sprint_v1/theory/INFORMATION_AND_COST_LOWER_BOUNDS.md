# Information and cost lower bounds

## Observed lower bounds

The completed DARE gates supply direct bounds for algorithms restricted to
unit presence or Boolean pruning: the best public ranking still requires 311
logical calls, exact ANY costs 243/347 before audit, and risk-limiting pruning
has no robust feasible cell. VERA cannot claim to beat these bounds while
using the same information channel; it must physically demonstrate that one
enumeration call returns several event objects.

## Output-capacity bound

If an `EVENT_ENUMERATE` implementation returns at most `k_max` correct,
distinct event rows per call, discovering `M` events requires at least
`ceil(M/k_max)` successful calls even with oracle window placement. If the
model output-token cap is `T` and each canonical event consumes at least `t_e`
tokens under the frozen schema, then `k_max <= floor(T/t_e)`.

## Temporal-coverage bound

With maximum owned core length `L`, covering a video of duration `T_V` without
an external proposal guarantee requires at least `ceil(T_V/L)` enumeration
calls. Padding cannot enlarge ownership cores. For the strict video,
`T_V≈3462.93 s`; a 50-second core therefore needs at least 70 calls.

## Frame-visibility bound

For an event visible for duration `d` and deterministic uniform frame spacing
`Delta`, there exists an adversarial phase offset that exposes zero event
frames whenever `d < Delta`. Thus fixed sparse sampling cannot guarantee
capture of the many 0.7-second strict pseudo-events. A physical success is an
empirical property of the frozen 2 fps input, not a phase-independent theorem.

## Indistinguishability lower bound

Without observing an interval containing an event or receiving an external
proposal that covers it, two videos identical on every processed frame but
differing by an event between sampled frames induce the same transcript. No
algorithm can distinguish them. This rules out a distribution-free completeness
claim for sparse enumeration.

## Cost break-even

Let dense unit cost be `c_10`, enumeration use `W` windows, and mean enumeration
cost be `alpha*c_10`. Ignoring favorable caching, logical/GPU break-even at
70% dense requires

`alpha < 0.70*347/W`.

For `W=70`, `alpha<3.47`. This is the decisive physical threshold for the
registered 50-second-core plan. Model load cancels only in a warm paired
comparison; decode, preprocessing and output generation do not.

## Implication

Theoretical headroom is real but conditional: operator recall/F1 and mean
physical cost must simultaneously lie in the break-even region. A perfect-cost
ceiling alone does not justify the pilot or the paper claim.

