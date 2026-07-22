# H-EXPOSE2 R3 adversarial review

## Verdict

`H-EXPOSE2 = REJECT` and `TWO_VIDEO_CORE_SIGNAL = ABSENT`.

The decisive evidence is the complete 72-cell reference-scored revision matrix. R3 improves
0/4 tasks over each task's best baseline, passes none of the four preregistered substantive
thresholds, and contributes no V1 gain. The physical/correctness gate passes, so this is a
scientific rejection rather than an execution block. No ablation is authorized.

## Artifact and opportunity audit

- Observed: 72/72 frozen cells are present and valid; all use `attempt_001`. There are zero
  duplicate or failed cells, deadline misses, cache replays, future accesses, visibility
  violations, missing checkpoints, or invalid action ledgers.
- Observed: all methods have identical scan order/timestamps, proxy evidence, VERIFY
  opportunity counts, and candidate capacity (10) within matched task/deadline/replicate
  cells. All 72 planned schedules complete.
- Observed: the FIFO and score-only revision baselines exactly reproduce their original
  matrix jobs, scan sequences, query targets, proxy-evidence hashes, endpoint F1, and unique
  events in 24/24 cells per method. Physical timing varies: the maximum cross-block TTFC
  difference is 8.376 s and maximum AnytimeAUC difference is 0.00913.
- Conclusion: opportunity or artifact inequality does not explain the endpoint-quality
  result. Runtime/service drift exists at the seconds scale and can perturb timing-derived
  AUC/TTFC, but cannot explain FIFO's categorical V0_Q1 event versus the two null arms.
- Observed: no slow sample was excluded. All started cells terminate in a retained valid
  `complete.json`; there are no failed attempts or replacement attempts.
- Observed: runtime configuration states `reference_visible_to_runtime=false`; per-run
  reference-visibility counters are zero. Reference matching occurs only in the separate
  evaluator after the physical matrix. No evidence of reference leakage was found.

## Why FIFO recovers V0_Q1

The shared first three scans are units `[173, 86, 260]`, followed by exactly one VERIFY
opportunity. FIFO verifies unit 173 in all six deadline/replicate runs because it is the
first-created candidate. The physical oracle labels unit 173 positive. Its durable K3 event
has anchor/evidence unit 173, which exactly matches reference `V0_Q1_event_0007`; this is a
true positive, not a raw-confirmation/reference mismatch.

Score-only and R3 both verify unit 86 in all six runs. Unit 86 has the larger proxy score
(0.796944 versus 0.644305 for unit 173) but is physically negative, so neither produces a
reference match. All three candidates fit within capacity 10, and unit 173 remains in the
frontier for the losing methods. Therefore the causal distinction is VERIFY order induced
by ranking: FIFO's creation order happens to select the reference-positive candidate.
Candidate creation, frontier retention, and reference matching are not the differentiators.
The fixed 10-second NMS cannot separate these widely spaced candidates and does not repair
the score-dominant first choice.

## R3 versus score-only

R3 is not exactly ranking-equivalent to score-only over the full matrix: their complete query
signatures match in 12/24 paired cells. They are behaviorally identical on V0, including the
V0_Q1 miss and V0_Q2 hit. They diverge in later V1 negative VERIFY choices, but both remain
null. Their macro endpoint quality is identical (F1 0.0208333; mean unique events 0.25), and
their macro AnytimeAUC differs only by 0.0000395. Thus the NMS revision changes some V1 order
without creating cross-video quality benefit.

## Concentration and the V1 null

- Observed: every nonzero result is on V0. FIFO's advantage over score-only/R3 is entirely
  the single V0_Q1 reference event; all methods also recover one V0_Q2 event. Both V1 tasks
  are null for every method.
- Observed: V1 executes the same 12 scans and four VERIFY calls for both deadlines. None of
  the 12 scanned unit IDs is a reference-positive unit for either V1 query, so no scheduler
  can confirm a V1 reference event from the exposed evidence.
- Competing explanation: the V1 null is consistent with limited scan opportunity under the
  conservative deadline plan, not uniquely with poor frontier ranking. Actual snapshots
  finish around 81--83 s against 199--203 s deadlines, leaving substantial realized slack;
  the frozen tail-bound planner nevertheless caps the schedule at 12 scans. This weakens any
  claim that the null identifies the frontier mechanism, but it does not rescue R3 because
  all methods share the limitation and R3 still has 0/4 directional wins.

## Decision robustness

The main alternative explanation is that FIFO's apparent superiority is a single-event
creation-order coincidence and that conservative scan planning suppresses V1 evidence. That
alternative argues against accepting FIFO as a generalized method; it does not support R3.
Rejecting H-EXPOSE2 requires only the preregistered failure of R3, which is directly observed:
0/4 positive-direction tasks, no quality threshold, no V1 contribution, and no mechanism
alignment versus the best baseline.

The conclusion would be revised only by discovery of a direct implementation or artifact
identity error that invalidates the reference matching or matched opportunities. The audits
found none. New parameter changes or another revision are not a valid rejection trigger.
Further discrimination among different core routes requires a third independent source
video and a new preregistration; it must not continue adaptively on these same two videos.
