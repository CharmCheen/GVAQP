# Core/Halo Attribution Summary

B_90/90 is the first budget in {5,10,20,40,60,80,100,120} where mean event_precision >= 0.9 and mean event_recall >= 0.9.

| Segment | Method | B_90_90 | P@point | R@point |
|---------|--------|---------|---------|---------|
| realcartest_0_1570 | B6 | not_reached | 0.307 | 0.660 |
| realcartest_0_1570 | B6-core | not_reached | 1.000 | 0.670 |
| realcartest_0_1570 | B7 | not_reached | 0.265 | 0.680 |
| realcartest_0_1570 | B7-core | not_reached | 1.000 | 0.720 |
| realcartest_0_1570 | LATE-AQP-candidate | not_reached | 0.467 | 0.840 |
| realcartest_0_1570 | LATE-AQP-core | not_reached | 1.000 | 0.850 |
| realcartest_2000_3200 | B6 | 120 | 1.000 | 1.000 |
| realcartest_2000_3200 | B6-core | 120 | 1.000 | 1.000 |
| realcartest_2000_3200 | B7 | 120 | 1.000 | 1.000 |
| realcartest_2000_3200 | B7-core | 120 | 1.000 | 1.000 |
| realcartest_2000_3200 | LATE-AQP-candidate | 120 | 1.000 | 1.000 |
| realcartest_2000_3200 | LATE-AQP-core | 120 | 1.000 | 1.000 |
| realcartest_3200_3830 | B6 | 80 | 1.000 | 1.000 |
| realcartest_3200_3830 | B6-core | 60 | 1.000 | 1.000 |
| realcartest_3200_3830 | B7 | 80 | 1.000 | 1.000 |
| realcartest_3200_3830 | B7-core | 60 | 1.000 | 1.000 |
| realcartest_3200_3830 | LATE-AQP-candidate | 80 | 1.000 | 1.000 |
| realcartest_3200_3830 | LATE-AQP-core | 80 | 1.000 | 1.000 |

## Diagnostic answers

### 1. Do B6-core / B7-core also reach 90/90?

- **B6-core**: reaches 90/90 in 2/3 segments.
  - realcartest_2000_3200: B=120 (P=1.000, R=1.000)
  - realcartest_3200_3830: B=60 (P=1.000, R=1.000)
- **B7-core**: reaches 90/90 in 2/3 segments.
  - realcartest_2000_3200: B=120 (P=1.000, R=1.000)
  - realcartest_3200_3830: B=60 (P=1.000, R=1.000)

### 2. Are their B_90/90 close to LATE-AQP-core?

- realcartest_2000_3200: LATE=120, B6-core=120 (delta=0).
- realcartest_2000_3200: LATE=120, B7-core=120 (delta=0).
- realcartest_3200_3830: LATE=80, B6-core=60 (delta=-20).
- realcartest_3200_3830: LATE=80, B7-core=60 (delta=-20).

### 3. Does LATE-AQP-core still hold an advantage?

All three core methods reach 90/90 on exactly the same segments, so the **Core/Halo gain is generic**, not LATE-AQP-specific.

### 4. If advantage disappeared, Core/Halo is generic post-processing

**Conclusion: Core/Halo is a generic post-processing gain.** Once B6 and B7 receive the same boundary-guard release, they reach 90/90 on the same segments as LATE-AQP-core; on `realcartest_3200_3830` they even reach it at a lower budget (B=60 vs B=80). The gain is therefore not LATE-AQP-specific.
