# Metrics, gates, and statistics

## Primary utility

`normalized_anytime_reference_event_recall_auc` over `[0, 40*m_DV]`, using
the exhaustive DirectVerify event set for that video-query workload. Report
the complete wall-clock curve and terminal EventRecall at all three deadlines.

Workloads with zero reference events remain in prevalence and degeneracy
reports but have undefined utility AUC and are excluded from effect averages.
Their frequency is always reported; they are never silently dropped.

## Opportunity quantities

1. `SCAN_FIXED_GAIN`: mean AUC of the best single global scan-enabled fixed
   policy minus the best single global DirectVerify-only policy.
2. `GLOBAL_SPECIALIZATION_HEADROOM`: mean per-workload fixed-policy envelope
   minus the best single global fixed policy. This is an oracle diagnostic,
   never a deployable result.
3. `LOVO_SELECTED_GAIN`: select one scan-enabled fixed policy on two videos and
   compare it with the selected DirectVerify policy on the held-out video.
4. `MATERIAL_STATE_PREVALENCE`: fraction of legal states on frozen baseline
   traces where a one-step action change followed by the same fixed continuation
   changes terminal recovered reference events by at least one or AUC by 0.02.
5. Exposure diagnostics: zero-candidate-region fraction, full-SCAN reference
   exposure recall, candidates per non-empty region, and verifier disagreement.

Video is the independent replication unit; queries are nested workloads. Report
all 18 cells, per-video means, per-query means, median, range, and exact signs.
With three videos, bootstrap confidence intervals are descriptive only.

## B1a PASS

All conditions must hold:

1. `SCAN_FIXED_GAIN >= 0.02` absolute AUC.
2. Scan-enabled gain is positive on at least 2/3 videos and at least 3/6
   queries with defined utility.
3. `LOVO_SELECTED_GAIN > 0` on at least 2/3 held-out videos and pooled held-out
   gain is at least 0.01.
4. `MATERIAL_STATE_PREVALENCE >= 0.10` on at least 2/3 videos.
5. At least 2/3 videos have both at least 10% empty SCAN regions and at least
   10% non-empty SCAN regions; full-SCAN reference exposure recall lies in
   `[0.20, 0.98]` on those videos.
6. No result depends on one failed-action convention, one query, or one video;
   exact evaluator parity and zero reference leakage pass.

PASS means `B1A_NATURAL_OPPORTUNITY_SCREEN_POSITIVE` and authorizes only B1b
protocol design.

## Failure branches

- `CLOSE_ADAPTIVE_CLAIM_B`: scan gain is non-positive, state prevalence is
  below 0.05 on every video, and exposure is degenerate on every video.
- `REVISE_SENSOR`: exposure recall is below 0.20 or verifier disagreement
  exceeds 0.30 on at least 2/3 videos.
- `SIMPLE_FIXED_SUFFICIENT`: fixed scan may help but specialization headroom is
  below 0.01 and LOVO selection adds no benefit.
- `INCONCLUSIVE_HETEROGENEOUS`: all other failures. Do not add queries or tune
  policies; diagnose before deciding whether one preregistered replication is
  justified.
