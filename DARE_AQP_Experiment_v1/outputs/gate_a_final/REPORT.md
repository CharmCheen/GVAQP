# Frozen Gate A final report

## Decision

**`UNIT_ORACLE_DARE_ACCELERATION_NO_GO`.** No frozen public signal meets the
registered Gate B threshold of total cost below 70% of the 347-call dense audit.
The best observed public cell is frozen CLIP at discovery budget 50: 11 events,
250 audit calls, 50 discovery calls and 11 certification calls, for 311 total
calls (89.625% dense).

CLIP does improve semantic ranking over the current proxy (anchor AUROC 0.6163
versus 0.5359; top-24 distinct events 8 versus 4; K3-safe event-F1 AUC 0.538949
versus 0.354212). This is real ranking evidence, but it does not change the
certificate cost regime. X-CLIP and frozen equal-rank fusion are worse on this
query. The main competing explanation is mismatch between the broad frozen text
query and the pseudo-event definition; the one-shot protocol forbids model,
prompt, or fusion selection after seeing these labels.

## Frozen signal results

| Signal | Top-24 events | Anchor AUROC | Anchor AP | Event-F1 AUC | Best Gate B total | Dense % | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| current proxy | 4 | 0.535945 | 0.093128 | 0.354212 | 315 | 90.778% | NO_GO |
| CLIP image-text | 8 | 0.616343 | 0.235062 | 0.538949 | 311 | 89.625% | NO_GO |
| X-CLIP video-text | 2 | 0.398035 | 0.112080 | 0.265671 | 316 | 91.066% | NO_GO |
| frozen rank fusion | 3 | 0.510724 | 0.110027 | 0.336627 | 316 | 91.066% | NO_GO |
| evaluator-only ideal | 24 | 1.000000 | 1.000000 | 0.919626 | 228 at B=24 | 65.706% | GO ceiling |

No public signal passes at any frozen Gate A discovery budget. The evaluator-only
ideal first passes at 24 discovery calls after finding 24/26 events. It is a
feasibility ceiling, not an attainable method result.

## Runtime and cost

| Model | Cold total | Warm-index query | GPU seconds | Decode | CPU preprocess | Forward | Peak GPU | Frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CLIP | 378.930s | 0.818s | 23.451s | 104.649s | 221.112s | 22.665s | 595.64 MiB | 347 |
| X-CLIP | 1642.990s | 2.643s | 25.409s | 323.747s | 1261.222s | 22.771s | 901.03 MiB | 2776 |

Both ran float32, batch size 1, SDPA, with synchronized GPU timing. NVIDIA total
energy counters were unavailable, so no energy value is claimed. Cold and warm
end-to-end cost must be reported as a vector: semantic runtime plus logical Gate B
calls. There is no defensible seconds conversion for the simulated exact oracle.
Even with a warm semantic index, the best public ranking still needs 311 logical
calls, so warm runtime acceleration is not established. Physical exact-oracle VLM
calls during Gate A are **0**.

## Seal and leakage

All four rankings contain each of units 0--346 exactly once. Raw score SHA256 is
`5bd2201de270327ae6e6a8810a04c99009c278a2b764bf3ea561ad591c5157c4`.
The inference process opened only the video, units, public proxy, frozen models,
processor and prompt. Evaluator labels were joined only after score and ranking
hash verification. See `INDEPENDENT_ADVERSARIAL_REVIEW.md` for the fail-closed
recomputation audit.

## Route

Freeze unit-ranking DARE as NO-GO. Do not test another embedding model, retune the
query, or alter fusion on this video. Under the frozen roadmap, only the separate
conditional C0 route remains: a small measured interval ANY/COUNT accuracy and
duration-cost pilot, and only with new explicit authorization.
