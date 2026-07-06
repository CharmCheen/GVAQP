# Budget Allocation Diagnosis — Ours (Frozen-LATE-AQP-v1)

This report diagnoses how Ours spends its oracle budget at low budgets (B=10, B=20) compared to B=40.

All numbers are proportions of the nominal budget (audit_calls / budget, etc.).
Source: `outputs/late_aqp_frozen_cross_segment_v1/cross_segment_metrics.csv`.

## Overall average allocation per budget

| Budget | Audit ratio | Discovery ratio | Repair ratio |
|--------|-------------|-----------------|--------------|
| 10 | 0.105 | 0.885 | 0.010 |
| 20 | 0.115 | 0.873 | 0.013 |
| 40 | 0.168 | 0.776 | 0.037 |

## Macro-averaged allocation per budget (average across segments)

| Budget | Audit ratio | Discovery ratio | Repair ratio |
|--------|-------------|-----------------|--------------|
| 10 | 0.105 | 0.885 | 0.010 |
| 20 | 0.115 | 0.873 | 0.013 |
| 40 | 0.168 | 0.776 | 0.037 |

## Per-segment allocation at B=10, B=20, B=40

### realcartest_0_1570

| Budget | Audit | Discovery | Repair | N trials |
|--------|-------|-----------|--------|----------|
| 10 | 0.100 ± 0.000 | 0.900 ± 0.000 | 0.000 ± 0.000 | 5 |
| 20 | 0.130 ± 0.067 | 0.840 ± 0.134 | 0.030 ± 0.067 | 5 |
| 40 | 0.160 ± 0.082 | 0.805 ± 0.130 | 0.035 ± 0.049 | 5 |

### realcartest_1630_2000

| Budget | Audit | Discovery | Repair | N trials |
|--------|-------|-----------|--------|----------|
| 10 | 0.100 ± 0.000 | 0.900 ± 0.000 | 0.000 ± 0.000 | 5 |
| 20 | 0.100 ± 0.000 | 0.900 ± 0.000 | 0.000 ± 0.000 | 5 |
| 40 | 0.130 ± 0.067 | 0.785 ± 0.089 | 0.010 ± 0.022 | 5 |

### realcartest_2000_3200

| Budget | Audit | Discovery | Repair | N trials |
|--------|-------|-----------|--------|----------|
| 10 | 0.120 ± 0.045 | 0.840 ± 0.134 | 0.040 ± 0.089 | 5 |
| 20 | 0.100 ± 0.000 | 0.900 ± 0.000 | 0.000 ± 0.000 | 5 |
| 40 | 0.190 ± 0.082 | 0.750 ± 0.137 | 0.060 ± 0.055 | 5 |

### realcartest_3200_3830

| Budget | Audit | Discovery | Repair | N trials |
|--------|-------|-----------|--------|----------|
| 10 | 0.100 ± 0.000 | 0.900 ± 0.000 | 0.000 ± 0.000 | 5 |
| 20 | 0.130 ± 0.067 | 0.850 ± 0.112 | 0.020 ± 0.045 | 5 |
| 40 | 0.190 ± 0.082 | 0.765 ± 0.124 | 0.045 ± 0.045 | 5 |

## Hypothetical reallocation: lower audit ratio to B=40 level

B=40 overall audit ratio = 0.168.

| Budget | Total budget (across segments/trials) | Actual audit calls | Target audit calls (B=40 ratio) | Freed calls for discovery+repair |
|--------|----------------------------------------|--------------------|----------------------------------|-----------------------------------|
| 10 | 200 | 21 | 33.500 | -12.500 |
| 20 | 400 | 46 | 67.000 | -21.000 |

## Diagnosis conclusions

- B=10 audit ratio = 0.105, B=20 audit ratio = 0.115, B=40 audit ratio = 0.168.
- Audit share at B=10/20 is not consistently higher than at B=40.
- If audit ratio at B=10/20 were reduced to the B=40 level (0.168), the freed calls would be approximately:
  - B=10: -12.500 calls across all segments/trials, or about -2.500 calls per segment on average.
  - B=20: -21.000 calls across all segments/trials, or about -4.200 calls per segment on average.

### Budget-allocation vs cold-start assessment

- At B=10, discovery+repair combined gets 0.895 of the budget; at B=20, 0.885; at B=40, 0.814.
- Audit share is not the main driver; the low-budget failure is more consistent with a cold-start problem (discovery ledger cannot seed enough positives early).
- **Judgment: this supports a cold-start mechanism problem.** A fallback that lets discovery run before/without audit-gated repair is more appropriate.

### Recommended candidate family

Prioritize `V4_cold_start_fallback`: at low budgets, allow discovery to skip audit-gated repair and run discovery-first.
