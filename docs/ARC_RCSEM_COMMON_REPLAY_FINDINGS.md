# ARC versus RC-SEM common-input replay findings

Status: exploratory cached comparison, complete and independently recomputed.
It is not a physical hard-deadline result.

## Research question

On the exact frozen unit, proxy, cached 32B label, and reference-event inputs
already used by `ARC-CACHED-REPLAY-v1`, does RC-SEM return more query-relative
events at the same logical VERIFY budget while preserving ARC's CSV schemas,
strict K3 materializer, and evaluator?

The primary domain is `dataset3_development`.  It is the only domain in this
benchmark with complete query provenance:

```text
prompt SHA-256: 12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33
parser SHA-256: 9a7413407d52df0484c0a338f0a12ae6b57553bdfa16753d7542f60977b558cb
model SHA-256:  c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210
```

The two `realcartest` slices lack prompt/parser hashes in the frozen
derivative.  They are sensitivity evidence, not query-identity-complete
evidence.

## Exact comparison contract

Both methods receive the same:

- `units.csv`, `proxy_only.csv`, `oracle_labels.csv`, and
  `reference_events.csv` frozen bytes;
- budget caps `5, 10, 20, 50, 80, 100` and five pairing seeds;
- definition of one first unique unit-label access as one logical VERIFY call;
- strict `k3_bridge_safe` configuration (`g_max=1`, `d_core_max=40`,
  `d_seg_max=60`);
- overlap-any, one-to-one Hungarian event evaluator;
- `selection_trace.csv`, `predictions.csv`, `event_matches.csv`, and
  `per_run_metrics.csv` schemas.

ARC's frozen `exact_fill=false` is preserved, so ARC may stop below a budget
cap.  RC-SEM uses exactly the budget.  All methods satisfy `calls <= budget`.
This difference is reported rather than silently normalised away.

For a held-out source video, RC-SEM fits its single-feature posterior and risk
gate only on the other source video.  Target ordering is fixed before the
held-out label is revealed.  The five RC-SEM seed rows are deterministic
pairing rows and are not independent samples.

## Observed results

### Query-bound `dataset3_development`

| Budget | ARC precision | RC-SEM precision | ARC recall | RC-SEM recall | ARC F1 | RC-SEM F1 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | 0.200 | 0.000 | 0.008 | 0.000 | 0.015 | 0.000 |
| 20 | 0.600 | 1.000 | 0.031 | 0.115 | 0.058 | 0.207 |
| 50 | 1.000 | 1.000 | 0.123 | 0.192 | 0.218 | 0.323 |
| 80 | 1.000 | 1.000 | 0.223 | 0.385 | 0.364 | 0.556 |
| 100 | 1.000 | 1.000 | 0.277 | 0.423 | 0.434 | 0.595 |

The query-bound F1-AUC is `0.224` for ARC and `0.354` for RC-SEM.  At budget
100, RC-SEM returns 11 verified events and ARC returns 7.2 on average; the
corresponding F1 difference is `+0.161` for RC-SEM.  ARC is slightly better at
budget 10, so the advantage is not uniform over the whole curve.

### Two-source-video sensitivity macro

The two realcartest slices are averaged within their source video before the
two-source macro is formed.

| Method | Precision AUC | Recall AUC | F1 AUC | tIoU@0.3 AUC | tIoU@0.5 AUC |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARC | 0.645 | 0.192 | 0.262 | 0.053 | 0.036 |
| RC-SEM | 0.857 | 0.381 | 0.483 | 0.136 | 0.115 |

These are descriptive results from two independent source videos.  They do
not support a population-level significance claim.

## Decisive mechanism audit

The apparent ARC-to-RC-SEM uplift is **not evidence for the full RC-SEM
mechanism**.

Observed facts:

1. Neither cross-source training fold produced at least ten predicted events
   whose 95% Wilson precision lower bound reached the frozen `0.80` floor.
2. RC-SEM therefore returned exactly zero unverified `PROBABLE_EVENT` rows.
3. The fitted proxy coefficient was positive in both source-video folds.
4. In all three domains, RC-SEM's posterior VERIFY ranking was exactly
   identical to descending raw `proxy_score` with unit ID as the tie break.
5. The existing PSTR control, evaluated on the same frozen inputs and K3,
   achieved higher F1-AUC than RC-SEM: `0.380` versus `0.354` on the primary
   query domain and `0.518` versus `0.483` on the two-source macro.

Thus the supported mechanism is much narrower:

> ARC's historical adaptive sampler is weaker on this cache than a simple
> proxy-ranked VERIFY schedule, but temporal stratification in PSTR remains
> stronger across the budget curve.

The result does not demonstrate RC-SEM's risk-controlled speculative
publication, dynamic SCAN/VERIFY allocation, learned Q surface, or physical
deadline safety.

## Decision

```text
VERIFIED_SCHEDULING_UPLIFT_ONLY_NO_SPECULATIVE_EVIDENCE
```

This is a positive result against ARC as requested, but a negative result for
an independent RC-SEM innovation claim.  The dominant unresolved bottleneck
remains the event posterior/state: the available proxy is not precise enough
to publish unverified events at the required risk floor.

## Main competing explanation

ARC's poor result may be specific to its repository adaptation: original ARC
CDF features are unavailable, it operates on `[1-proxy, proxy]`, and the exact
instrumented historical entry point is missing.  A faithful native/physical
ARC implementation could reverse the comparison.  Conversely, RC-SEM's
ranking benefit may disappear under real action costs because this replay
charges logical calls rather than wall time.

## Next discriminating action

After the main repository releases deployable physical inputs, run ARC,
PSTR/ST1, raw-proxy VERIFY, and full RC-SEM through the same shared physical
runtime and deadline profile.  RC-SEM must additionally have an event-level
posterior calibrated on other videos.  The full method is supported only if:

- safe probable coverage is non-zero and its held-out precision lower bound
  remains at least `0.80`;
- RC-SEM beats both PSTR/ST1 and raw-proxy ranking, not only ARC;
- the gain survives equal wall-clock budgets, K3, and output precision;
- no incomplete admitted action or post-deadline commit occurs.

Reject or revise the current state model if probable coverage remains zero or
if the physical result is no better than the simple controls.

## Reproduction and artifacts

```bash
cd /root/charm/GVAQP_side_rcsem
PYTHONPATH=src pytest -q
PYTHONPATH=src python experiments/arc_rcsem_common_replay.py \
  --arc-root /root/charm/GVAQP-arc-phys-baseline \
  --output outputs/arc_rcsem_common_replay
```

The completed output is bound by:

```text
RUN_MANIFEST.json SHA-256:
e53170f6388235c8c71552cc581c52063bb14e764c0f9b9e10eeb2c37c02a8ce

artifact inventory aggregate hash:
28e80f35a813024378690908911d20718f0a20d6fc67f0d4887db64bbf1dd23d
```

Validation recomputed all 180 run metrics, found zero duplicate queries,
verified all calls stayed within budget, and proved the three output table
schemas are column-identical to ARC.  No GPU inference or new 32B call was
made.
