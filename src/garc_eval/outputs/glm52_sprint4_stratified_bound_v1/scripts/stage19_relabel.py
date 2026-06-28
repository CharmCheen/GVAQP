#!/usr/bin/env python3
"""Stage 19 / Task 1: Stage 18 relabel audit.

Check whether Stage 18 tested a fixed alpha=0.15 or a budget-adaptive schedule.
Re-evaluate the DECISION label against the pre-set threshold of -0.05.
"""
import pandas as pd
import common as C

C.ensure_dirs()

# Load Stage 18 results
s18 = pd.read_csv(C.ROOT / "garc_eval/outputs/glm52_sprint3_certificate_queryprior_v1/tables/stage18_budget_schedule.csv")

# Check what configs were tested
configs_tested = s18["config"].unique().tolist()
print(f"Configs tested in Stage 18: {configs_tested}")

# Check if schedule_adaptive was tested
has_schedule = "schedule_adaptive" in configs_tested
has_fixed_015 = "alpha_0.15" in configs_tested

# Check the "best config" chosen
# Stage 18 report says best_config = alpha_0.15
# Let's verify the schedule_adaptive results
sched = s18[s18["config"] == "schedule_adaptive"]
fixed015 = s18[s18["config"] == "alpha_0.15"]

print("\n=== schedule_adaptive results ===")
print(sched[["budget", "alpha", "L4_event_recall_mean", "L3_event_recall", "recall_drop_vs_L3", "verdict"]].to_string(index=False))
print("\n=== alpha_0.15 results ===")
print(fixed015[["budget", "alpha", "L4_event_recall_mean", "L3_event_recall", "recall_drop_vs_L3", "verdict"]].to_string(index=False))

# Check the threshold: target is B=80 recall drop <= -0.05
b80_sched = sched[sched["budget"] == 80]["recall_drop_vs_L3"].iloc[0] if not sched[sched["budget"] == 80].empty else None
b80_fixed = fixed015[fixed015["budget"] == 80]["recall_drop_vs_L3"].iloc[0] if not fixed015[fixed015["budget"] == 80].empty else None

print(f"\nB=80 recall drop: schedule={b80_sched}, fixed_0.15={b80_fixed}")

# The Stage 18 report claims BUDGET_SCHEDULE_FOUND with best=alpha_0.15
# But the target was -0.05, and alpha_0.15 at B=80 gives -0.128
# The schedule_adaptive at B=80 gives -0.128 (same, because schedule uses alpha=0.15 at B=80)

# Check ALL configs at B=80
b80_all = s18[s18["budget"] == 80]
print("\n=== ALL configs at B=80 ===")
print(b80_all[["config", "alpha", "L4_event_recall_mean", "L3_event_recall", "recall_drop_vs_L3", "verdict"]].to_string(index=False))

# Check worst drop across ALL budgets for each config
print("\n=== Worst drop per config ===")
for config in configs_tested:
    sub = s18[s18["config"] == config]
    worst = sub["recall_drop_vs_L3"].min()
    worst_B = sub.loc[sub["recall_drop_vs_L3"].idxmin(), "budget"]
    mean_drop = sub["recall_drop_vs_L3"].mean()
    all_valid = sub["verdict"].eq("VALID").all()
    meets_target = worst >= -0.05
    print(f"  {config}: worst={worst:+.4f} at B={worst_B}, mean={mean_drop:+.4f}, valid={all_valid}, meets_target={meets_target}")

# Relabel decision
any_meets_target = False
for config in configs_tested:
    sub = s18[s18["config"] == config]
    if sub["verdict"].eq("VALID").all() and sub["recall_drop_vs_L3"].min() >= -0.05:
        any_meets_target = True
        break

if any_meets_target:
    decision = "BUDGET_SCHEDULE_FOUND"
else:
    decision = "BUDGET_SCHEDULE_PARTIALLY_IMPROVED_TARGET_NOT_MET"

report = f"""# Stage 19: Stage 18 Relabel Audit

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

{C.md_table(b80_all[["config", "alpha", "L4_event_recall_mean", "L3_event_recall", "recall_drop_vs_L3", "verdict"]])}

**No config meets the -0.05 target at B=80.** The best is alpha=0.10 at -0.097,
still nearly 2x the target.

## Worst drop across all budgets

| Config | Worst drop | At B= | Mean drop | All valid | Meets -0.05? |
|---|---|---|---|---|---|
"""
for config in configs_tested:
    sub = s18[s18["config"] == config]
    worst = sub["recall_drop_vs_L3"].min()
    worst_B = sub.loc[sub["recall_drop_vs_L3"].idxmin(), "budget"]
    mean_drop = sub["recall_drop_vs_L3"].mean()
    all_valid = sub["verdict"].eq("VALID").all()
    meets = worst >= -0.05
    report += f"| {config} | {worst:+.4f} | {worst_B} | {mean_drop:+.4f} | {all_valid} | {meets} |\n"

report += f"""
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

`{decision}`

The Stage 18 label should be corrected from `BUDGET_SCHEDULE_FOUND` to
`{decision}`. The improvement is partial (from -0.161 to -0.097 at B=80) but
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
"""
(C.REPORTS / "STAGE19_STAGE18_RELABEL_AUDIT.md").write_text(report, encoding="utf-8")
print(f"\nStage 19 done. decision={decision}")
