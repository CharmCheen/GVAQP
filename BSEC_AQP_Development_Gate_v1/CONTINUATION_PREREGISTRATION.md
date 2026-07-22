# Continuation v2 preregistration

Freeze time: 2026-07-12 15:51:17 UTC, before CLIP scoring on `realcartest_0_1570`.

## Why the first candidate was rejected

Frozen QTPC improved `dataset3` but failed its cross-video decision rule on `realcartest_2000_3200`: F1-AUC 0.593589 versus 0.619170 for CLIP and 0.602761 for shared-K3 ARC. It is not retained as the proposed general method.

The reversal was budget-specific. QTPC found two events at held-out B=5, but its peak-only ordering missed events at B=80/100. Temporal NMS was more stable, while QTPC supplied useful candidates that NMS missed. This motivates a portfolio rather than another single peak-width claim.

## Frozen PNIR rule

PNIR constructs two complete, label-blind rankings from the same CLIP scores:

1. QTPC with an eight-unit contrast radius;
2. greedy temporal NMS with a ten-unit radius, then raw-CLIP fill.

It repeatedly emits one unused QTPC candidate followed by three unused NMS candidates, skipping duplicates. All budgets are prefixes of this single merged ranking. The 1:3 ratio and both radii were selected on the two already scored datasets and are fitting parameters, not theory-derived constants.

## Confirmation

The untouched score domain is the disjoint `[0,1570)` interval of `realcartest`: 157 ten-second units and 20 VLM-defined pseudo-events. Exact scene-window media is present, so the same frozen CLIP model and center-frame sampling can be used. Labels and references are not opened by the scorer.

The primary comparison rematerializes PNIR, CLIP, NMS, QTPC, and ARC queried units with the identical safe K3 operator. PNIR passes only if its AUC exceeds both CLIP and shared-K3 ARC, its AUC exceeds NMS alone, it beats shared-K3 ARC at four or more budgets, and every primary curve uses exactly B unique observations.

Even a pass is limited evidence: the final interval is disjoint but comes from the same realcartest source as the first held-out interval.
