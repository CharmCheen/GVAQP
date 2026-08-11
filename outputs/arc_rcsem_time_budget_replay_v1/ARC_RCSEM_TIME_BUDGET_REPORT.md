# ARC vs full RC-SEM under equal calibrated time budgets

## Result

| time_budget_minutes | logical_call_capacity | event_precision_arc | event_precision_rcsem | event_recall_arc | event_recall_rcsem | event_f1_arc | event_f1_rcsem | delta_f1_rcsem_minus_arc | returned_event_count_arc | returned_event_count_rcsem |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 4 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 5 | 11 | 0.200 | 1.000 | 0.008 | 0.038 | 0.015 | 0.074 | 0.059 | 0.200 | 1.000 |
| 10 | 23 | 0.600 | 1.000 | 0.031 | 0.154 | 0.058 | 0.267 | 0.208 | 0.800 | 4.000 |
| 20 | 47 | 0.800 | 1.000 | 0.100 | 0.154 | 0.177 | 0.267 | 0.089 | 2.600 | 4.000 |
| 30 | 70 | 1.000 | 1.000 | 0.192 | 0.308 | 0.322 | 0.471 | 0.149 | 5.000 | 8.000 |
| 40 | 94 | 1.000 | 1.000 | 0.269 | 0.423 | 0.424 | 0.595 | 0.171 | 7.000 | 11.000 |

Precision and recall are event-level seed means under the frozen evaluator.
An empty result has precision 0 by that evaluator's convention; returned-event
count is shown so this is not confused with a false-positive rate.

## Fair comparison contract

- Primary domain only: `dataset3_development`, whose old-query prompt is bound to
  `12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33`.  The two provenance-incomplete `realcartest` derivatives
  are excluded.
- Both methods use identical frozen units, proxy cache, oracle-label cache,
  strict K3 (`g_max=1`, `d_core_max=40`, `d_seg_max=60`), and evaluator bytes.
- Both pay the same 32B cold load (14.203 s) and the same mean
  complete-path VERIFY charge (25.179 s).  That mean comes from
  four calls over three content-blind clips using the identical prompt.
- Time excludes the already-materialized shared proxy/oracle cache construction
  for both methods.  Controller/K3/cache-read CPU time is not physically
  measured and is not charged to either method.
- ARC and RC-SEM traces are prefix-stable at every original checkpoint.  Each
  time cutoff therefore exposes the same number of oracle labels to both.
- RC-SEM's cross-source 0.80 precision risk gate failed, so the "full" method
  publishes zero unverified probable events.  Its result here is entirely the
  verified scheduling path; it should not be described as speculative gain.

## Evidence boundary

This is a **physical-latency-calibrated cached replay**, not a hard-deadline
physical run.  The four-call latency probe is too small to establish tail
latency or a safety bound.  It supports a fair expected-time x-axis only.
