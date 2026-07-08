# T033a — Full-policy oracle router ceiling

For each (segment, budget, seed), the oracle router selects the policy with the best `event_recall`. This gives an upper bound for what a learned router could achieve IF it could perfectly identify the best policy per cell.

Policies: B7, D3, ECP-c1, ECP-c2, ECP-v2, EventLift-DC, HTS-EC, TopProxy

## Router ceiling vs best single method

| segment | budget | router_recall | best_single | router_policy | best_policy |
|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | 0.200 | 0.200 | EventLift-DC | EventLift-DC |
| realcartest_0_1570 | 0.20 | 0.250 | 0.250 | EventLift-DC | EventLift-DC |
| realcartest_0_1570 | 0.30 | 0.300 | 0.300 | ECP-c1 | ECP-c1 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.100 | ECP-c1 | ECP-c1 |
| realcartest_2000_3200 | 0.20 | 0.150 | 0.150 | ECP-c2 | ECP-c2 |
| realcartest_2000_3200 | 0.30 | 0.200 | 0.200 | ECP-c2 | ECP-c2 |
| realcartest_3200_3830 | 0.10 | 0.429 | 0.429 | B7 | B7 |
| realcartest_3200_3830 | 0.20 | 0.429 | 0.429 | B7 | B7 |
| realcartest_3200_3830 | 0.30 | 0.571 | 0.571 | B7 | B7 |
| dataset3_0_1200 | 0.10 | 0.167 | 0.167 | D3 | D3 |
| dataset3_0_1200 | 0.20 | 0.167 | 0.167 | ECP-c2 | ECP-c2 |
| dataset3_0_1200 | 0.30 | 0.167 | 0.167 | ECP-c2 | ECP-c2 |
| dataset3_1200_2400 | 0.10 | 0.083 | 0.083 | D3 | D3 |
| dataset3_1200_2400 | 0.20 | 0.167 | 0.167 | D3 | D3 |
| dataset3_1200_2400 | 0.30 | 0.167 | 0.167 | D3 | D3 |
| dataset3_2400_3462 | 0.10 | 0.111 | 0.111 | B7 | B7 |
| dataset3_2400_3462 | 0.20 | 0.222 | 0.222 | EventLift-DC | EventLift-DC |
| dataset3_2400_3462 | 0.30 | 0.222 | 0.222 | EventLift-DC | EventLift-DC |

**Macro router recall: 0.228**
**Macro best single recall: 0.228**
**Router lift: +0.000**


### realcartest

- **B7**: recall=0.253, prec=0.639
- **D3**: recall=0.168, prec=0.624
- **ECP-c1**: recall=0.158, prec=0.662
- **ECP-c2**: recall=0.169, prec=0.654
- **ECP-v2**: recall=0.125, prec=0.645
- **EventLift-DC**: recall=0.197, prec=0.529
- **HTS-EC**: recall=0.133, prec=0.617
- **TopProxy**: recall=0.163, prec=0.578
- **Oracle Router**: recall=0.292

### dataset3

- **B7**: recall=0.074, prec=0.300
- **D3**: recall=0.127, prec=0.539
- **ECP-c1**: recall=0.019, prec=0.167
- **ECP-c2**: recall=0.080, prec=0.278
- **ECP-v2**: recall=0.019, prec=0.148
- **EventLift-DC**: recall=0.071, prec=0.213
- **HTS-EC**: recall=0.012, prec=0.037
- **TopProxy**: recall=0.012, prec=0.037
- **Oracle Router**: recall=0.164

## Policy win matrix (1 = best recall for that cell)

| segment | budget | B7 | D3 | ECP-c1 | ECP-c2 | ECP-v2 | EventLift- | HTS-EC | TopProxy |
| - | - | - | - | - | - | - | - | - | - | - |
| realcartest_0_1570 | 0.10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| realcartest_0_1570 | 0.20 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| realcartest_0_1570 | 0.30 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| realcartest_2000_3200 | 0.10 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| realcartest_2000_3200 | 0.20 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| realcartest_2000_3200 | 0.30 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| realcartest_3200_3830 | 0.10 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| realcartest_3200_3830 | 0.20 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| realcartest_3200_3830 | 0.30 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dataset3_0_1200 | 0.10 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dataset3_0_1200 | 0.20 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| dataset3_0_1200 | 0.30 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| dataset3_1200_2400 | 0.10 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dataset3_1200_2400 | 0.20 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dataset3_1200_2400 | 0.30 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dataset3_2400_3462 | 0.10 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dataset3_2400_3462 | 0.20 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| dataset3_2400_3462 | 0.30 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |

## Policy composition: which policies dominate?

- **B7**: 4 wins (22.2%)
- **D3**: 4 wins (22.2%)
- **ECP-c2**: 4 wins (22.2%)
- **EventLift-DC**: 4 wins (22.2%)
- **ECP-c1**: 2 wins (11.1%)
- **ECP-v2**: 0 wins (0.0%)
- **HTS-EC**: 0 wins (0.0%)
- **TopProxy**: 0 wins (0.0%)

## Verdict

- **POSITIVE**: oracle router (per-cell max) achieves 0.228 vs best single method B7 (0.164), lift = +0.064.
  Significant complementarity — a router could provide meaningful lift.

- Oracle router is an OFFLINE CEILING — it picks the best policy per cell with knowledge of final recall. A learned router (T033b) would need to predict the best policy from early-state features without seeing future labels.