# ECP Steps 1-3 — results synthesis (T025 / T026 / T027)

> Strict-replay, VLM-oracle-relative experiments under the ECP mainline
> (`outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md`). All metrics use
> IoU>=0.3 event evaluation; reference events read only at final eval, never
> online; no event_id leak; 1 oracle call per action.

## T025 — AnchorBridge shadow (formation gap isolation)

Per-reference-event analysis over all 6 segments (74 reference events). Result
is sharper than the original "bridge the gap" hypothesis:

- **Positives within an event are already contiguous** (`max_internal_gap = 0`
  for all 74 events). Gap-bridging across empty bins is therefore a near-empty
  formation gap — AnchorBridge's *gap-filling* role is mostly unnecessary.
- **The real formation bottleneck is temporal granularity.** Many reference
  events are <1s (ref_dur 0.2–0.7s) sitting inside 10s bins; even a perfect
  single positive bin yields IoU = 0.07, far below 0.3. These are
  `short_event_granularity_limited` (12/20, 14/20, 3/7 on realcartest; 5/6,
  10/12, 6/9 on dataset3). Bridging cannot fix them — only **sub-bin boundary
  resolution** (VLM/CERTIFY on the bin) can.
- **Longer events (ref_dur >= 10.7s) already form well** once discovered
  (`already_formable`: 8/20, 6/20, 4/7 realcartest; 1/6, 2/12, 3/9 dataset3) —
  consec_iou 0.5–0.9. Formation is fine there.
- **`proxy_zero_blocked` dominates dataset3** (5/6, 8/12, 2/9): these events'
  positives are all prior_score_max==0.0, so discovery — not formation — is the
  blocker, exactly matching the RP shadow (0 bridge-positive hits on
  dataset3_0_1200).

**T025 takeaway**: ECP's BRIDGE arm should emphasise *boundary extension*
(CERTIFY/expand_boundary, sub-bin resolution) more than *gap-filling*, and the
proxy-zero regime needs a dedicated ZERO_PROXY discovery arm, not a bridge.

## T026 — action-level offline utility labeling

`t026_action_utility.csv` logs, for all 1236 strict-replay steps, the online
heuristic utility U(a) of every ECP arm plus the chosen arm and its oracle
outcome. This is the offline-labeled training signal for a future learned
policy. Key empirical facts extracted:

- **BRIDGE is the most efficient arm**: positive rate 0.474 vs DISCOVER 0.277.
- **BRIDGE was under-used by the hand-designed weights**: when a bridge target
  existed (876 steps), it was chosen only 234 times; DISCOVER's +0.05 floor
  inflated its utility above BRIDGE (1.01 vs 0.744). Arm-weight tuning matters.
- **ZERO_PROXY fired only 6 times and found 0 positives** — the space-filling
  trigger was too weak/capped; needs strengthening for the proxy-zero regime.

## T027 — hand-designed event-utility bandit (strict replay)

ECP bandit (DISCOVER/BRIDGE/CERTIFY/ZERO_PROXY/STOP, heuristic U(a)/cost,
online-only state) run as a real strict-replay method, vs HTS-EC-safe and
B7-strict-replay.

- **On realcartest (proxy-informative)**: ECP is competitive-to-better than
  HTS-EC-safe — e.g. realcartest_0_1570 @0.30: ECP recall 0.300 vs HTS 0.183;
  realcartest_2000_3200 @0.10: ECP 0.050 vs HTS 0.100 (mixed). Precision is
  comparable or better (ECP 0.5–0.64 vs HTS 0.62–0.72 at 0.30).
- **On dataset3 (proxy-zero)**: ECP ≈ HTS-EC-safe ≈ 0 at low budget, and below
  B7-strict at 0.30 — the weak-proxy discovery bottleneck is not solved by the
  current hand-designed weights (consistent with T025 proxy_zero_blocked).
- Strict-replay compliant: 0 budget violations, 0 event_id leaks, 1 call/arm.

**T027 takeaway**: event-level arm selection is a *viable* strict-replay policy
layer and on proxy-informative segments already matches/beats the fixed HTS-EC
executor. The open levers are (1) reweight BRIDGE up, (2) strengthen
ZERO_PROXY for the proxy-zero regime, (3) add a learned policy (T027 step 4)
trained on the T026 table. ECP does **not** yet beat B7-core on dataset3; the
claim "ECP improves low-budget event coverage" remains **not supported** until
those levers land.

## Honest scope

- All numbers VLM-oracle-relative; "true recall" wording disallowed.
- ECP is a policy layer above the discovery executor; default selector and
  Core/Halo unchanged.
- Proxy-zero segments remain an upper-bounded regime even under ECP without new
  signal; ECP's claim there is "explicit fallback", not "solved".
