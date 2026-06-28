# Stage 19: Stage 18 Relabel Audit

## Audit question

Stage 18 was labeled `BUDGET_SCHEDULE_FOUND`. Re-check:
1. Did Stage 18 test a budget-adaptive schedule, or only fixed alpha?
2. Does the best config meet the pre-set threshold of B=80 recall drop <= -0.05?

## What Stage 18 actually tested

Stage 18 tested 4 configs:
- `alpha_0.10` (fixed)
- `alpha_0.15` (fixed)
- `alpha_0.20` (fixed)
- `schedule_adaptive` (alpha=0.25 at B<=40, 0.15 at B=60-80, 0.10 at B>=100)

**Yes, a budget-adaptive schedule was tested.** The schedule_adaptive config
is a genuine schedule, not a fixed alpha. However, at B=80 (the worst-case
budget), the schedule uses alpha=0.15, which is identical to the fixed
alpha_0.15 config. So at the critical B=80 point, schedule and fixed-0.15
give the same result.

## Threshold check

Pre-set target: B=80 recall drop <= -0.05 (i.e., L4 recall within 0.05 of L3).

Actual B=80 results by config:

| config | alpha | L4_event_recall_mean | L3_event_recall | recall_drop_vs_L3 | verdict |
| --- | --- | --- | --- | --- | --- |
| alpha_0.10 | 0.1000 | 0.4214 | 0.5185 | -0.0971 | VALID |
| alpha_0.15 | 0.1500 | 0.3907 | 0.5185 | -0.1278 | VALID |
| alpha_0.20 | 0.2000 | 0.3571 | 0.5185 | -0.1614 | VALID |
| schedule_adaptive | 0.1500 | 0.3907 | 0.5185 | -0.1278 | VALID |

**No config meets the -0.05 target at B=80.** The best is alpha=0.10 at -0.097,
still nearly 2x the target.

## Worst drop across all budgets

| Config | Worst drop | At B= | Mean drop | All valid | Meets -0.05? |
|---|---|---|---|---|---|
| alpha_0.10 | -0.1174 | 60 | -0.0441 | True | False |
| alpha_0.15 | -0.1278 | 80 | -0.0355 | True | False |
| alpha_0.20 | -0.1614 | 80 | -0.0383 | True | False |
| schedule_adaptive | -0.1278 | 80 | -0.0450 | True | False |

## Diagnosis

The `BUDGET_SCHEDULE_FOUND` label was incorrect. The pre-set threshold (-0.05
at B=80) was NOT met by any config. The best achievable is -0.097 (alpha=0.10),
which is still nearly 2x the target.

The improvement from Sprint 2's -0.161 (alpha=0.20) to -0.097 (alpha=0.10) is
real but insufficient. The fundamental issue is that at B=80, the calibration
+ audit overhead (even at alpha=0.10, that's 8+7=15 anchors = 19% of budget)
removes enough exploit capacity to cause a measurable recall loss.

The schedule_adaptive config does NOT help at B=80 because it assigns alpha=0.15
there (same as fixed). A different schedule that assigns alpha=0.10 at B=80
might do better, but that's what alpha_0.10 already tests — and it still gives
-0.097.

## DECISION

`BUDGET_SCHEDULE_PARTIALLY_IMPROVED_TARGET_NOT_MET`

The Stage 18 label should be corrected from `BUDGET_SCHEDULE_FOUND` to
`BUDGET_SCHEDULE_PARTIALLY_IMPROVED_TARGET_NOT_MET`. The improvement is partial (from -0.161 to -0.097 at B=80) but
does not meet the pre-set -0.05 threshold. The label must reflect the actual
threshold outcome, not the mere presence of improvement.

## Implication for Sprint 4

The B=80 problem is not solved by budget schedule alone. Task 2 (B=80 anomaly
diagnosis) is needed to determine whether this is a structural cluster gap or
a rounding artifact. If structural, no alpha schedule will fix it — the issue
is that the calibration/audit anchors displace exploit anchors at a budget
where every anchor matters for covering specific clusters.

## Guardrail

- The threshold (-0.05) was pre-set in the Sprint 3 task instructions. It must
  be applied as-is, not relaxed after seeing results.
- "Improvement" is not the same as "meeting the target." A label of
  BUDGET_SCHEDULE_FOUND requires meeting the target, not just doing better than
  before.
- This audit does NOT invalidate the Stage 17 certificate validation
  (EXACT_HYPERGEOMETRIC_BOUND_VALIDATED) — the bound is still valid. It only
  corrects the Stage 18 budget-schedule label.
