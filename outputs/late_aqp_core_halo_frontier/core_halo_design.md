# Core/Halo Precision-Constrained Release Design

## Base method

Frozen-LATE-AQP-v1 (audit + discovery + repair) is used unchanged up to the candidate interval generation step.

## Core/Halo release

After v1 produces candidate intervals, we perform boundary guards only on intervals that contain at least one positive selected bin (candidate events).

- Up to **3 guard bins per side** (left and right).
- Guarding stops early when a negative bin is encountered, because that confirms the event boundary.
- **Core** = positive selected bins + any positive guard bins discovered during boundary confirmation.
- **Halo** = negative selected bins, intervals with no positive selected bins, and any part of a candidate interval that is not confirmed positive.

## Budget integration

Guard calls are accounted inside the same total budget B. We iterate discovery budget and guard need:

1. Run audit/repair (fixed cost).
2. Estimate guard need for the candidate intervals produced by a given discovery budget.
3. Reduce discovery budget until `discovery_budget + guard_need <= total_remaining_budget`.
4. Run discovery with that budget, perform guards, and report actual `guard_calls`.

## Metrics

We report **event-level** precision/recall for B_90/90 measurement:

- event_precision = (# core intervals overlapping any reference event) / (# core intervals)
- event_recall = (# unique reference events overlapped by any core interval) / (# reference events)

Duration-level precision/recall are also recorded in the raw CSV for reference, but B_90/90 is measured on event-level metrics.

## Comparison asymmetry (declared)

B6/B7 are evaluated on their raw selected intervals without any additional boundary guard or core/halo release. This means LATE-AQP-core pays an explicit guard overhead that B6/B7 do not. This is a method-level difference, not an experimental fairness adjustment.
