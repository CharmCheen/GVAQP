# Controller dynamic-headroom report

Decision: **REVISE**, with a positive cached mechanism signal.

The new paired replay sampled 108 naturally reachable states where both
`SCAN_FIXED` and `VERIFY_TOP1` were legal. Each state was replayed from its
causal prefix, forced once into either action, and continued with the identical
fixed 1:1 policy. Q equally weights terminal distinct-event recall and
AnytimeEventRecallAUC, with a hard penalty for nonempty outputs below precision
0.80.

Observed classes were 25 `SCAN_BETTER` (23.1%), 26 `VERIFY_BETTER` (24.1%),
and 57 ties (52.8%). Non-ties were 47.2%; both directions appeared in both
independent source videos; deterministic replay noise and abstract-budget
overruns were zero. Thus the preregistered directional cached headroom screen
passes.

This is not the physical Gate 1 result. It uses an older query/reference,
abstract 0.1/1.0 costs, only two independent source videos across three
domains, one continuation policy, and one deterministic rollout. It does not
establish wall-clock deadline safety, dynamic-oracle advantage over best fixed
ratio, leave-best-video-out gain, state predictability, or closed-loop utility.

Accordingly a small public-state prediction study is scientifically permitted
on this cached branch table as diagnostics. That leave-one-source-out study is
now complete and negative: always `VERIFY` achieved decision regret 0.000885
and weighted sign accuracy 0.814. The best learned model, linear regression,
had regret 0.009693 (10.95 times worse) and weighted sign accuracy 0.558.
Logistic, histogram tree, small MLP, and contextual-bandit models were also
worse than the fixed action. ID-only and shuffled-state controls were near
chance; the hindsight oracle remained perfect. LightGBM was unavailable in the
environment and sklearn histogram boosting is reported as the tree control.

Thus cached Gate 2 fails: headroom exists in hindsight but is not predictable
from the current public summaries across held-out sources. Controller
escalation or RL is not justified, and the cached closed loop already found
fixed 1:1 interleaving stronger than the selected dynamic policy. The V3
decision must wait for released labels and physical cost profiles, then repeat
the paired branch test before any new state-model work.
