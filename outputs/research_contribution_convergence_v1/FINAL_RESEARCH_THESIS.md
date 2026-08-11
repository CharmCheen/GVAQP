# Final Research Thesis (Current Evidence)

## What exact problem did we discover?

In a sparse semantic event query, selecting units and evaluating an expensive predicate do not directly produce the requested event relation. The engine must materialize sparse verified-positive anchors into temporal event intervals.

## Why do existing approaches miss it?

Proxy/AQP and video-query systems principally optimize which records, frames, or clips receive expensive evaluation. Their usual output contracts are selections, aggregates, tracks, or frame labels; they do not make query-time reconstruction of a partial semantic observation relation into event intervals the central quality object.

## Core insight supported now

For the released V3 model-relative driving reference, naive global coalescing of all queried positives is destructive once multiple separated anchors are exposed. A simple local temporal continuity constraint accounts for almost all of the observed improvement.

## What mechanism addresses it?

The supported mechanism is **continuity-constrained event materialization**: group verified-positive anchors only across a frozen local temporal gap, rather than spanning all positives. Current V3 K3 realizes this operator plus negative/unknown/parse/duration safeguards, but those additional safeguards are not the demonstrated source of P0 gain.

## Evidence and boundary

The P0 matrix has 54 valid same-trace pairs across 3 independent videos, 3 selectors, and 6 query budgets (median K3−K0 F1 `+0.1457`; 40 better, 14 equal, 0 worse). Its component ablation attributes median `+0.1377` to the gap constraint and median `0` to the queried-negative barrier. This is only a **model-relative reconstruction finding** because the reference event relation is formed using full-grid K3 grouping. It does not establish a novel K3 algorithm, human event-boundary superiority, materialization-as-universal-bottleneck, or a hard-deadline claim.
