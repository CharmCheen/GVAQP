# MATERIALIZER_SENSITIVITY (ERAEA E4)

Scoring x final materializer, mean EventF1-AUC:

| scoring | C1 | C3 (K3-like) | K0 |
|---|---:|---:|---:|
| agnostic (proxy) | 0.1618 | 0.1599 | 0.0396 |
| gap_aware (relation) | 0.1634 | 0.1605 | 0.0396 |
| k3_aware | 0.1634 | 0.1605 | 0.0396 |

## Decisive quantities
- gain of gap_aware over agnostic under C1: 0.0016
- gain under C3: 0.0005
- gain under K0: 0.0
- Retention_gap = 1.0 (trivially 1.0 because the gain is
  ~0 everywhere; there is no materializer regime where the relation-aware
  score adds measurable value)
- Ranking reversals across materializers: 0.2222
- gap-threshold sensitivity (relation - top_proxy mean AUC): {"5.0": 0.0001, "10.0": 0.0016, "15.0": 0.0016, "20.0": 0.0014}

## Verdict
- K0 evaluation collapses all policies (0.03-0.06 AUC): the materializer IS
  the dominant factor, not the acquisition policy.
- k3_aware scoring == gap_aware scoring exactly: the K3-like barrier term is
  inert on this substrate.
- The relation-aware gain does not depend on the gap threshold (0.0001-0.0016
  across gap in 5..20s) -> no mechanism hiding in threshold tuning.
- The current gain pattern is consistent with REFERENCE_CIRCULARITY_RISK:
  the whole evaluation is a K3-defined model-relative reference over the same
  Qwen grid; policy-level differences are second-order.
