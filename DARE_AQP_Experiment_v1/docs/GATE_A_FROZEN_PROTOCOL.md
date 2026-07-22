# Gate A: frozen semantic signal final falsification protocol

## Decision question

Can a fixed external zero-shot signal materially reduce the public-to-ideal
event-discovery gap enough to change the original Gate B total-cost decision?

Gate A is a final falsification test for **unit-ranking DARE**, not an open-ended
model search.

## Frozen methods

1. existing public proxy;
2. `openai/clip-vit-base-patch32` at commit
   `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, one center frame per unit;
3. `microsoft/xclip-base-patch32` at commit
   `a2e27a78a2b5d802e894b8a1ef14f3a8ce490963`, eight uniform frames per unit;
4. equal-weight mean of descending percentile ranks from methods 2 and 3.

Frozen query text:

```text
a vehicle, pedestrian, or cyclist entering the ego vehicle's path from outside the driving corridor
```

All methods rank all 347 units.  No strict-label training, threshold tuning,
model replacement, or post-hoc fusion selection is permitted.  Model IDs,
weights, prompts, frame sampling, software revisions, and input hashes must be
frozen before evaluator labels are joined.

## Required outputs

- canonical-anchor and presence top-k coverage at k=5/10/20/24/50;
- distinct-event discovery curve and events/query;
- blocked/prequential AUROC and AP;
- original exact Gate B total-cost curve for each frozen ranking;
- cold index construction time, warm ranking latency, CPU/GPU seconds, frames
  decoded, and peak memory;
- failures, including low-score events and duplicate hits within one event.

## Stop rule

After the four frozen methods are evaluated once:

- if none makes public Gate B GO under the existing cost/certificate contract,
  record `UNIT_ORACLE_DARE_ACCELERATION_NO_GO` and close unit-ranking DARE;
- if one passes, freeze it and proceed to strengthened end-to-end baselines;
- do not swap encoders or tune fusion on this video after a NO-GO.

The oracle-anchor result (24 events in the first 24 calls) is an idealized
feasibility boundary, not a required semantic-model score and not a tuning
target.

## Current execution status

Protocol frozen; external image/video embeddings are not present in the
current artifacts, and the current host reports no available GPU.  No semantic
result is claimed.  Running model inference or downloading model weights is a
separate compute/network action requiring an explicit execution decision.

The score evaluator and label-blind inference runner are implemented.  A
current-proxy preflight reproduces NO-GO (4/26 events at top 24; linked Gate B
cost 318/347).  This is not the final four-method result.
