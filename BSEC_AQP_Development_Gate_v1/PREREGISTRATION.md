# BSEC-AQP Development Gate v1: frozen continuation

Freeze time: 2026-07-12 15:15:04 UTC, before computing any CLIP scores for the held-out `realcartest_2000_3200` replay.

## What the development evidence already ruled out

- Plain BSEC semantic-temporal cover did not exceed CLIP top-k on `dataset3`.
- MMR and semantic facility-location did not diagnose the main failure.
- CLIP's low-budget selected positives contained no duplicate reference events at B=5, 10, or 20. The low-budget bottleneck is therefore not duplicate saturation.
- Public CLIP score and image-embedding autocorrelation both crossed the conventional 1/e decorrelation threshold at one unit, so an 8- or 10-unit radius cannot honestly be presented as autocorrelation-estimated.

The surviving hypothesis is narrower: query-score *local peak contrast* can remove high-score temporal plateaus and promote isolated query-relevant peaks.

## Frozen candidate

For raw CLIP score `s_i` and radius `h=8` units,

`c_i = s_i - max(s_j : 0 < |j-i| <= h)`.

Rank units by descending `c_i`, breaking ties by ascending unit ID. Every budget is a prefix of this one ranking. The radius was selected on the development video from the dyadic grid `{1,2,4,8,16,32}` and is consequently a tuned development parameter. It remains fixed on held-out data.

## Fair primary comparison

Every selection method receives exactly B cached oracle observations and is rematerialized by the same `k3_bridge_safe` operator. Event precision, recall, F1, predicted count, and returned seconds are then computed by the same one-to-one overlap evaluator. The normalized trapezoidal F1-AUC over B=`{5,10,20,50,80,100}` is primary.

Historical native ARC remains a descriptive comparator. It returns broad, partly unverified intervals through a different materializer, so its event recall cannot be attributed to the B queried units alone. Calling that an equal-budget primary comparison would conflate query selection with output coverage.

## Held-out test and stopping rule

The held-out replay is the historical `realcartest_2000_3200` 20-minute interval. Its original video is missing, but retained overlapping five-second clips cover the exact 10-second unit-center timestamps. The CLIP score extractor must record the clip and relative timestamp used for every unit.

QTPC replicates only if it:

1. exceeds CLIP top-k and ARC rematerialized with shared K3 in F1-AUC;
2. exceeds CLIP at at least four of six budgets;
3. uses exactly B oracle observations per budget; and
4. is evaluated without changing radius, query, ranking, or materializer.

Failure rejects the general QTPC claim. It does not permit post-hoc radius selection on realcartest.
