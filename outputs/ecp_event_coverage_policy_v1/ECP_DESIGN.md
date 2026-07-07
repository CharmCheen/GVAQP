# ECP — Event-Coverage Policy (Event-Level Budgeted Decision Policy)

> Design doc authored 2026-07-07. This reframes the active direction from
> "improve the proxy / discovery heuristic" to "learn an event-level budgeted
> decision policy under weak proxy, expensive oracle, and unknown event
> boundaries". It supersedes the original T010 ("EC-AQP") framing as the
> **active mainline** (see TASK_QUEUE.yaml T010 + new T025/T026/T027).
>
> Track for any future metric: this is a **design / method** proposal, not a
> validated result. All empirical anchors below are read from existing
> `outputs/hts_ec_v0_phase2a_rp_*` and `outputs/eventlift_full_benchmark_v1/`
> artifacts; they are VLM-oracle-relative, not human ground truth, and the
> comparison track (strict_replay vs posthoc_eval) must be labeled.

## 0. One-sentence thesis

The real bottleneck is **not** "the proxy is not accurate enough" — it is that,
under a weak proxy, an expensive VLM oracle, and unknown event boundaries, the
algorithm has not yet learned to make **event-level decisions** (where to look,
what to verify, where to expand, when to stop, when not to return). The method
contribution is an **event-level contextual bandit / budgeted decision policy**
whose arms are event-operators, not bins, and whose reward is event-recall /
precision / IoU marginal utility, not a positive label.

## 1. The five-layer bottleneck (why current methods stall)

### 1.1 Bin-level hit vs event-level evaluation (missing event-formation policy)
Components optimize `find a positive bin`, but evaluation is `returned interval
IoU>=0.3 with a reference event`. Consequence: a positive anchor that forms only
a single-bin interval yields event-recall = 0. We lack the layer
`positive anchor -> event hypothesis -> interval confirmation`. This is not a
proxy-precision problem; it is an **event-formation policy** gap.

### 1.2 Action space is too low-level
Current actions are essentially `query this bin` / `query representative bin in
node` / `query fine-frontier bin`. The operator set should be upgraded to
event-level operators: `discover new event`, `expand anchor left/right`,
`certify interval`, `merge/suppress duplicate`, `audit low-proxy stratum`,
`abstain/stop`. With only `query bin`, the algorithm earns bin-level wins that
do not move event-level precision/recall.

### 1.3 Budget allocation is not unified to event utility
EventLift-DC unifies DISCOVER+CERTIFY; HTS-EC has tree/fine frontier; HTS-EC-RP
has StagRepMix. These still each carry their own heuristic (tree frontier =
coverage; fine frontier = local positive; StagRepMix = robust positive hit;
CERTIFY = precision; bridge = interval completion). The open method space is to
fuse all of them into **one event-utility bandit / policy** that, per oracle
call, maximizes expected event-level answer-quality gain.

### 1.4 Proxy-zero case is an information bottleneck
`dataset3_0_1200` is the canonical failure: all 7 true-positive bins have
proxy=0.0, sitting among 76 proxy=0.0 bins (7 positive + 69 negative). Without
extra signal, 2 probes in 76 zero-proxy bins find a positive with ~17.6% chance.
`outputs/hts_ec_v0_phase2a_rp_strategy_shadow_v1/rp_strategy_shadow_summary.csv`
confirms this: every shadow bridge strategy scores **0 hits on dataset3_0_1200**
(while `gap_bracket_v2/largest_gap_local_flank_or_proxy_neighbor` scores 11/30
shadow hits on the segments where a proxy signal exists). This is the regime
where proxy-free exploration / non-proxy reasoning is mandatory, not optional.

### 1.5 Precision is not a first-class citizen
EventLift-DC's CERTIFY shows precision *can* be raised (4/6 segments precision
up, 2/6 recall up, 0 segments recall harmed — `EVENTLIFT_RESULTS_SYNTHESIS.md`).
But the main loop still optimizes `where to query next`, not `returned interval
quality`. certify / suppress / merge / abstain are not yet unified into the
primary decision.

## 2. The proposed method: Event-Coverage Policy (ECP)

Reframe the whole problem as a **budgeted event-level contextual bandit /
decision policy** (name candidates: EC-Bandit, EventLift-Policy, BEAR =
Budgeted Event Active Reasoning).

### 2.1 State `S_t`
Each step maintains:
```
tree frontier, fine frontier,
discovered positive anchors,
candidate intervals,
proxy distribution,
queried labels,
zero-proxy strata (explicitly flagged),
posterior over node density,
uncertainty over interval boundary,
duplicate / overlap risk,
budget remaining
```
This is richer than HTS-EC's node posterior: it also tracks "can this positive
form an event", "is this interval trustworthy", "is this region already
covered".

### 2.2 Arms (event-level operators, NOT bins)
```
A1 tree_discover(node)
A2 robust_probe(node, strategy)          # StagRepMix-like diverse probe on stagnant node
A3 bridge_left(anchor)                   # AnchorBridge: convert bin-level hit -> event interval
A4 bridge_right(anchor)
A5 certify_interval(interval)
A6 expand_boundary(interval, side)
A7 suppress_or_merge(interval_pair)
A8 zero_proxy_stratum_probe(region)      # proxy-free exploration, budget-capped
A9 abstain_or_stop
```
This is closer to the task than SUPG (record selection), ABae (aggregate
estimator), or ARC (predicate-defined clip query) — none operate on an
event-level action space under budget.

### 2.3 Reward (event-level marginal utility, not positive label)
Current implicit reward `query positive bin = +1` is insufficient. Replace with:
```
U(a) = E[ Δevent_recall + α·Δprecision + β·ΔIoU
          − γ·duplicate_overlap_penalty − η·false_positive_risk ] / expected_cost(a)
```
Under this utility, DISCOVER / BRIDGE / CERTIFY / SUPPRESS / ZERO_PROXY_AUDIT
all compete in one objective.

### 2.4 Bandit strategy
Borrow budgeted contextual bandit / Thompson-sampling / UCB ideas (e.g.
Thompson Sampling for Budgeted MAB, arXiv:1505.00146). Each arm is an
event-operator; sample the utility/cost posterior per arm and pick the highest
sampled `U(a)/cost`. Update after each oracle feedback. Natural arm priors:
tree_discover = high recall / low precision; certify_interval = high precision /
lower recall; bridge_anchor = medium cost, high chance to convert bin-hit ->
event-hit; zero_proxy_probe = high uncertainty / low prior but essential for
proxy-zero recall. A meta-bandit / active-search layer (cf. Lehigh meta-AS) can
let the policy avoid over-committing to one sampling assumption.

## 3. Six method-level directions (all more "algorithm" than "better proxy")

1. **Event-Coverage Bandit (recommended mainline)**: fuse DISCOVER / BRIDGE /
   CERTIFY / ZERO_PROXY / STOP into one budgeted loop driven by `U(a)`.
   Goes beyond EventLift-DC (which unifies only DISCOVER+CERTIFY) and can call
   HTS-EC as its discover executor.
2. **Option-level / offline contextual policy**: train `state -> action_type`
   from strict-replay logs (no deep RL first). Three steps: (a) offline
   counterfactual utility labeling of each action; (b) supervised policy /
   ranker; (c) strict-replay eval without `event_id`. Borrows the meta-bandit
   idea of choosing among base strategies.
3. **Multi-fidelity cascade**: `level0 proxy -> level1 cached embedding/CLIP
   similarity -> level2 track/motion/temporal-consistency rule -> level3 small
   VLM/distilled verifier -> level4 full VLM`. The method question is the
   **budgeted fidelity-selection policy** (cf. FrugalGPT; multi-fidelity MAB).
   "Skip VLM" is only realistic *conditionally*, never fully.
4. **Event hypothesis model (active inference)**: treat the event as a latent
   state `H = {center, left_boundary_dist, right_boundary_dist, event_type,
   support_bins, uncertainty, duplicate_risk}`; each oracle query updates
   `P(event exists)`, `P(boundary)`, `P(IoU>=0.3)` and naturally yields
   query-center / query-left / query-right / query-gap actions.
5. **Proxy-zero stratum sampling**: explicitly detect the proxy-zero regime and
   trigger `zero_proxy_space_filling` / `low_discrepancy` / `temporal_cluster`
   probes with a hard `zero_proxy_budget_cap`, so dense segments are not hurt.
   Trigger predicate: node stagnant AND proxy-entropy low AND zero-proxy share
   high AND top-proxy probes all negative.
6. **Precision-aware abstention**: allow `return / certify-more / bridge-more /
   suppress / abstain` as a decision arm; optimize expected utility of the
   *returned answer set*, not number of positive bins.

## 4. Can we "skip the VLM and reason ourselves"?

- **Fully skip VLM: not realistic** for open semantic events (ego-path entry,
  near-miss, abnormal maneuver); proxy-zero shows current info is
  positive/negative inseparable. Pure algorithm cannot invent semantic info.
- **Partially skip (selective VLM invocation / budgeted semantic cascade):
  realistic and the recommended direction.** Call full VLM only when cheap
  signal is insufficient or the boundary is uncertain; cap proxy-zero probes.
- **Amortized oracle (VLM teacher -> lightweight verifier):** use full VLM on a
  few bins to train a query-specific cheap verifier, trust it except under high
  uncertainty. Needs extra training and strict isolation from `event_id`
  online. Method contribution = fast per-segment verifier adaptation + trust
  rule, not proxy-precision tuning.

## 5. ECP algorithm skeleton

```
Input: video bins, proxy scores, budget B, optional cheap features
Init: tree frontier; event hypothesis set H={}; ledger={}; returned={}
For each budget step:
  1. Update belief: node-density posterior, hypothesis existence,
     boundary uncertainty, duplicate risk, proxy-zero risk.
  2. Generate candidate actions A1..A9.
  3. Score U(a) = E[Δrecall + αΔprec + βΔIoU − γdup − ηfp] / cost(a).
  4. Select action via contextual Thompson / UCB / learned policy.
  5. Execute at cheapest sufficient fidelity (proxy / verifier / full VLM).
  6. Update ledger and hypotheses.
Return: high-confidence event intervals + optional residual/uncertain regions.
```
Relationship to existing work: SUPG selects records; ABae estimates positive
mass; ARC uses predicate-defined clip queries; EventLift-DC unifies
DISCOVER+CERTIFY; HTS-EC is the executor. ECP is the **policy layer** that
unifies DISCOVER + ROBUST_PROBE + BRIDGE + CERTIFY + ZERO_PROXY above an
executor (HTS-EC or EventLift-DC).

## 6. Concrete next steps (4-step plan; Step 1 is active)

- **Step 1 — AnchorBridge shadow (ACTIVE, see T025):** on existing replay logs,
  verify whether a positive anchor + 1–3 local probes can reach IoU>=0.3. The
  `rp_opportunity_by_step.csv` / `rp_strategy_shadow_summary.csv` already contain
  the raw opportunity; the open task is to convert a single-bin hit into a
  confirmed event interval and measure the event-recall delta. This isolates
  how much of the current precision/recall gap is *formation*, not *discovery*.
- **Step 2 — Action-level offline utility labeling (T026):** label each state in
  existing replays with the counterfactual event-utility of DISCOVER / BRIDGE /
  CERTIFY / ZERO_PROXY / STOP. This table is the training data for the bandit.
- **Step 3 — Hand-designed event-utility bandit (T027):** rule-based
  `U_discover/U_bridge/U_certify/U_zero_proxy/U_stop` under Thompson/UCB,
  strict-replay eval. Goal: confirm event-level action selection beats the
  fixed pipeline.
- **Step 4 — Offline learned policy:** train a contextual bandit ranker
  (state features -> action priority) only after Step 3 shows signal. Deep RL
  deferred.

## 7. Positioning for the advisor (method-innovation pitch)

> The next step is not "make the proxy more accurate" (that is engineering).
> The method question is: under a possibly-failing proxy, an expensive oracle,
> and unknown event boundaries, how to adaptively allocate budget across
> discover / bridge / certify / zero-proxy-explore actions. Abstracted as an
> event-level contextual bandit / budgeted decision policy, each arm is an
> event-operator (not a bin) and the reward is the marginal gain in event
> recall, precision, and IoU. This explains why current methods raise bin-level
> hits without moving event-level precision/recall, and gives the optimization
> path forward.

## 8. Honesty / scope notes (must accompany any write-up)

- ECP is a **design proposal**; no strict-replay ECP run exists yet. Steps 1–3
  are the validation sequence.
- All cited numbers are VLM-oracle-relative; "true recall" / "ground truth
  recall" wording is disallowed.
- Proxy-zero (`dataset3_0_1200`) remains an upper-bounded regime even under ECP
  unless new signal is introduced; ECP's claim there is "explicit fallback", not
  "solved".
- Default selector (`score_topk` + temporal NMS + duration cap) and Core/Halo
  release are unchanged; ECP is a policy layer above them, not a replacement,
  and must not alter the default selector (AGENTS.md "Never").
- Outside-envelope audit samples that drive a decision cannot also evaluate it
  (AGENTS.md hard constraint); Step 2 labeling must keep decision/eval batches
  disjoint.
