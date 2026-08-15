# Final CCF independent GVAQP audit

Independent audit of the GVAQP repository, from first principles, against the
underlying artifacts. Vocabulary: SUPPORTED / PARTIALLY_SUPPORTED /
NOT_ESTABLISHED / DISFAVORED / FALSIFIED / CLOSED.

## ACTUAL PROBLEM BEING TESTED

Budgeted reconstruction of a K3-defined, Qwen3-VL-32B model-relative temporal
event relation from a fully precomputed candidate universe (one candidate per
10-second unit), under an imperfect proxy ranker and oracle-call budgets. It
does not test online cheap sensing, endogenous candidate generation, natural
exposure false negatives, measured physical costs, or independent human event
utility.

## ORIGINAL THEORY IDENTIFIABILITY

PARTIAL. Faithfully realized: delayed proxy visibility, VERIFY legality gated
on SCAN, asymmetric abstract costs, verified feedback, one-step continuation.
Absent: endogenous sensing, natural exposure failure, measured costs, natural
state prevalence, human-valid utility. The load-bearing assumption (natural
exposure false negatives) is masked by construction (exposure recall 1.0).

## STRONGEST VERIFIED POSITIVE RESULT

The C1 gap-constrained materializer reconstructs the frozen K3-defined event
relation better than naive merge on 54/54 controlled pairs (median Delta F1
+0.1457), consistent across 3 videos and 3 selectors — but this is a
model-relative, circularity-qualified, bounded system finding, not independent
event truth.

## STRONGEST VERIFIED NEGATIVE RESULT

The complex-K3 materializer novelty is falsified: mechanism ablation attributes
essentially all gain to the 10-second gap rule (median +0.1377), with duration
cap, negative barrier, and K3 extras contributing ~0.

## MOST IMPORTANT EXPERIMENT-DESIGN FLAW

The candidate universe is precomputed (1475/1475) and SCAN is information
release rather than sensing, so the experiment can only observe ranking error
and cannot observe the natural acquisition error that the original theory is
about. Combined with a K3-defined reference, this produces a construct-validity
gap at both the input (acquisition) and output (evaluation) ends.

## MOST IMPORTANT CLAIM THAT SURVIVES

Proxy ranking quality is weak and video-dependent (AUPRC 0.258-0.315), and
ranking degradation causes a material low-budget EventF1 gap (0.0951) while
synthetic exposure degradation causes zero — i.e., on this substrate the
bottleneck is ranking, not acquisition.

## MOST IMPORTANT CLAIM THAT DOES NOT SURVIVE

That event-aware / geometry-driven acquisition is more robust than maximizing
positive yield (C-C/H1). The model-relative geometry R2 0.795 does not transfer
to the VLM-direct shadow (MAE gain 0.000665) and the P2 diagnostic finds
semantic-state residual ABSENT; the human test is still missing.

## CURRENT HUMAN-P1 STATUS

WAITING_HUMAN_REFERENCE. Frozen six clusters, 0 human labels, analyzer ready.
No PASS/PARTIAL/FAIL decision exists.

## GEOMETRY STATUS

PARTIAL in the model-relative K3 world; DISFAVORED as an independent mechanism
after the VLM shadow and P2 diagnostic. Action-value signal ABSENT.

## CONTROLLER STATUS

NO-GO / CLOSED on the current substrate (learned regret 0.009693 vs fixed
0.000885; 0/18 immediate positives; 1/7 continuation conversions). This is
substrate-bounded, not a universal impossibility.

## ORIGINAL ENDOGENOUS-SCAN THEORY STATUS

NOT ESTABLISHED. Masked, not falsified: the defining acquisition mechanism was
never faithfully instantiated.

## TOP 3 NOVELTY THREATS

1. LAVA (ACM MM 2025) — MAB segment sampling for traffic-video localization.
2. AQUAPRO / SUPG / ThalamusDB — proxy + expensive-oracle budget and ranking.
3. Seiden / ExSample / ARC — adaptive progressive sampling and refinement.

## IS THERE STILL A PAPER-WORTHY RESEARCH QUESTION?

MAYBE.

## IF YES, STATE IT IN ONE SENTENCE

Under a single physical clock, does a query processor that co-schedules
causally-exposed cheap sensing and expensive semantic verification, then
materializes a durable EventRelation, recover more independently-defined
temporal events than fixed deterministic coverage when cheap sensing genuinely
misses regions?

## SINGLE DECISIVE NEXT EXPERIMENT

A minimal faithful endogenous-SCAN probe on 2-3 held-out videos: measure real
cheap-detector natural exposure false negatives and hindsight SCAN-vs-VERIFY
action-regret prevalence/magnitude/predictability (with measured costs and
prospective logging) against a fixed SCAN1-to-VERIFY1 default.

## WHY THIS EXPERIMENT HAS MORE INFORMATION VALUE THAN THE ALTERNATIVES

It tests the one untested load-bearing assumption of the entire original
program. The human P1 reference is already heavily discounted by the shadow and
P2, so even a PASS would likely leave a generic-coverage explanation. A clean
negative here terminates the expensive P4/P5 branch cheaply; a clean positive is
the only result that reopens the theory.

## WHAT RESULT WOULD MAKE YOU RECOMMEND TERMINATING THIS RESEARCH DIRECTION

Natural exposure recall near 1.0 (cheap sensing does not actually miss regions),
or hindsight action regret that is rare, small, unpredictable across held-out
videos, or vanishes after measured physical costs. Either would falsify the
original endogenous-SCAN theory and justify terminating the adaptive-allocation
program while retaining the bounded systems findings.

## WHAT RESULT WOULD MAKE YOU RECOMMEND INVESTING HEAVILY

Non-trivial natural exposure false negatives plus non-rare, material,
cross-video-predictable action regret that remains positive after physical
costs. That would convert Claims B/C/K from NOT ESTABLISHED toward SUPPORTED and
justify a real P5 controller program on a faithful substrate.

## Audit discipline note

No models were trained, no algorithms tuned, no controller/MAB/RL launched, no
frozen P1 artifacts modified, no human-annotation outputs read, and no GPU work
run. All conclusions trace to frozen tables, manifests, source code, and
protocol hashes listed in SOURCE_MAP.md.
