# Pass/Fail Criteria Report

## Criterion 1: Long-event recall improvement over B6 and B7

Macro-averaged long-event recall across the three unseen segments.  
*Source: `center10_vlm_oracle_events.csv` (VLM-oracle reference).*

| Budget | B6 | B7 | Ours | Wins both? |
|--------|-------|-------|-------|------------|
| 5 | 0.138 | 0.125 | 0.188 | Yes |
| 10 | 0.300 | 0.225 | 0.188 | No |
| 20 | 0.450 | 0.463 | 0.350 | No |
| 40 | 0.738 | 0.725 | 0.900 | Yes |
| 80 | 0.887 | 0.900 | 1.000 | Yes |
| 120 | 0.963 | 0.975 | 1.000 | Yes |

- Budgets where Ours wins both: 4/6
- Wins at B=120: Yes
- **Verdict**: PASS (need ≥3 budgets incl. B=120)

## Criterion 2: Duration-weighted precision vs B7

Average precision difference (B7 − Ours) across unseen segments, in percentage points.  
*Source: `center10_vlm_oracle_events.csv` (VLM-oracle reference).*

| Budget | Avg Δ precision (pp) |
|--------|----------------------|
| 5 | -16.0 |
| 10 | -15.8 |
| 20 | -1.6 |
| 40 | -3.1 |
| 80 | -1.4 |
| 120 | -0.2 |

- Maximum average drop (B7 − Ours): -0.2 pp. Negative values mean Ours is *more* precise than B7 on average; the largest B7 advantage is never above 0 pp. Threshold ≤5.0 pp.
- **Verdict**: PASS

## Criterion 3: Causal repair trace

- Repair-expansion calls: 184
- Triggered by outside-envelope positives: 184
- Repairs with positive duration overlap: 48
- **Verdict**: PASS

## Criterion 4: Low-density segment behavior

Segment `realcartest_1630_2000` (5.4% positive-bin density).

| Budget | Event recall | Selected precision |
|--------|--------------|-------------------|
| 5 | 0.000 | 0.000 |
| 10 | 0.000 | 0.000 |
| 20 | 0.500 | 0.001 |
| 40 | 1.000 | 0.002 |
| 80 | 1.000 | 0.002 |
| 120 | 1.000 | 0.002 |

- Finds at least one event: Yes
- Precision stays non-negative: Yes
- **Verdict**: PASS

## Overall

- Criterion 1 (recall): PASS
- Criterion 2 (precision): PASS
- Criterion 3 (repair trace): PASS
- Criterion 4 (low density): PASS

**Overall verdict: PASS**

The frozen LATE-AQP-v1 configuration satisfies all pre-specified cross-segment criteria.
