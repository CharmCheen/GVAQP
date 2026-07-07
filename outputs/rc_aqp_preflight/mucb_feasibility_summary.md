# RC-AQP Preflight — M_UCB / RecallLCB feasibility summary

Binomial zero-hit upper bound `p_ucb(n, alpha) = 1 - alpha**(1/n)` with alpha=0.05. All counts are *oracle-relative* and computed from existing CSV artifacts only; no oracle / model / new discovery was run.

## Inputs

- segment info: `outputs/late_aqp_d3_accounting_fix_v1/segment_info.csv`
- discovered events (le30 budget): `outputs/late_aqp_event_diverse_discovery_v1/unique_event_coverage.csv`

| segment_id | num_units | num_positive_units | num_events |
|---|---:|---:|---:|
| realcartest_0_1570 | 157 | 44 | 20 |
| realcartest_2000_3200 | 120 | 32 | 20 |
| realcartest_3200_3830 | 63 | 13 | 7 |
| dataset3_0_1200 | 120 | 7 | 6 |
| dataset3_1200_2400 | 120 | 21 | 12 |
| dataset3_2400_3462 | 107 | 12 | 9 |

## 1. p_ucb reference vs n_audit (alpha=0.05)

| n_audit | p_ucb |
|---:|---:|
| 1 | 0.95 |
| 2 | 0.776393 |
| 3 | 0.631597 |
| 5 | 0.45072 |
| 8 | 0.312344 |
| 10 | 0.258866 |
| 12 | 0.220922 |
| 15 | 0.181036 |
| 20 | 0.139108 |
| 30 | 0.095034 |
| 50 | 0.058155 |
| 80 | 0.036754 |
| 120 | 0.024655 |
| 200 | 0.014867 |
| 500 | 0.005974 |

## 2. Min n_audit to obtain p_ucb <= target (alpha=0.05)

| p_ucb_target | min_n_audit |
|---:|---:|
| 0.2 | 14 |
| 0.1 | 29 |
| 0.05 | 59 |
| 0.02 | 149 |

## 3. M_allowed for RecallLCB >= tau_r (per discovered-event count)

M_allowed = D * (1/tau_r - 1). RecallLCB=D/(D+M_ucb) >= tau_r requires M_ucb <= M_allowed.

| segment_id | discovery_method | discovered_events_le30 | tau_r | M_allowed |
|---|---|---:|---:|---:|
| realcartest_0_1570 | B7-core | 6.0 | 0.8 | 1.5 |
| realcartest_0_1570 | B7-core | 6.0 | 0.9 | 0.6667 |
| realcartest_0_1570 | B7-core | 6.0 | 0.95 | 0.3158 |
| realcartest_0_1570 | D3-norepair-core-chunk120 | 5.4 | 0.8 | 1.35 |
| realcartest_0_1570 | D3-norepair-core-chunk120 | 5.4 | 0.9 | 0.6 |
| realcartest_0_1570 | D3-norepair-core-chunk120 | 5.4 | 0.95 | 0.2842 |
| realcartest_2000_3200 | B7-core | 6.4 | 0.8 | 1.6 |
| realcartest_2000_3200 | B7-core | 6.4 | 0.9 | 0.7111 |
| realcartest_2000_3200 | B7-core | 6.4 | 0.95 | 0.3368 |
| realcartest_2000_3200 | D3-norepair-core-chunk120 | 5.2 | 0.8 | 1.3 |
| realcartest_2000_3200 | D3-norepair-core-chunk120 | 5.2 | 0.9 | 0.5778 |
| realcartest_2000_3200 | D3-norepair-core-chunk120 | 5.2 | 0.95 | 0.2737 |
| realcartest_3200_3830 | B7-core | 0.8 | 0.8 | 0.2 |
| realcartest_3200_3830 | B7-core | 0.8 | 0.9 | 0.0889 |
| realcartest_3200_3830 | B7-core | 0.8 | 0.95 | 0.0421 |
| realcartest_3200_3830 | D3-norepair-core-chunk120 | 1.0 | 0.8 | 0.25 |
| realcartest_3200_3830 | D3-norepair-core-chunk120 | 1.0 | 0.9 | 0.1111 |
| realcartest_3200_3830 | D3-norepair-core-chunk120 | 1.0 | 0.95 | 0.0526 |
| dataset3_0_1200 | B7-core | 2.2 | 0.8 | 0.55 |
| dataset3_0_1200 | B7-core | 2.2 | 0.9 | 0.2444 |
| dataset3_0_1200 | B7-core | 2.2 | 0.95 | 0.1158 |
| dataset3_0_1200 | D3-norepair-core-chunk120 | 2.0 | 0.8 | 0.5 |
| dataset3_0_1200 | D3-norepair-core-chunk120 | 2.0 | 0.9 | 0.2222 |
| dataset3_0_1200 | D3-norepair-core-chunk120 | 2.0 | 0.95 | 0.1053 |
| dataset3_1200_2400 | B7-core | 4.6 | 0.8 | 1.15 |
| dataset3_1200_2400 | B7-core | 4.6 | 0.9 | 0.5111 |
| dataset3_1200_2400 | B7-core | 4.6 | 0.95 | 0.2421 |
| dataset3_1200_2400 | D3-norepair-core-chunk120 | 2.6 | 0.8 | 0.65 |
| dataset3_1200_2400 | D3-norepair-core-chunk120 | 2.6 | 0.9 | 0.2889 |
| dataset3_1200_2400 | D3-norepair-core-chunk120 | 2.6 | 0.95 | 0.1368 |
| dataset3_2400_3462 | B7-core | 3.0 | 0.8 | 0.75 |
| dataset3_2400_3462 | B7-core | 3.0 | 0.9 | 0.3333 |
| dataset3_2400_3462 | B7-core | 3.0 | 0.95 | 0.1579 |
| dataset3_2400_3462 | D3-norepair-core-chunk120 | 2.0 | 0.8 | 0.5 |
| dataset3_2400_3462 | D3-norepair-core-chunk120 | 2.0 | 0.9 | 0.2222 |
| dataset3_2400_3462 | D3-norepair-core-chunk120 | 2.0 | 0.95 | 0.1053 |

## 4. Headline per-segment feasibility (unit-level RecallLCB)

Uncovered units are conservatively estimated as `num_units - n_audit` (no discovery coverage subtracted); M_ucb_unit = uncovered_units * p_ucb; RecallLCB_unit = D/(D+M_ucb_unit) using `B7-core` D (le 30 budget).

| segment_id | num_units | budget_ratio | budget_calls | audit_share | n_audit | p_ucb | M_ucb_unit | D_B7 | RecallLCB_unit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| realcartest_0_1570 | 157 | 0.10 | 16 | 0.20 | 3 | 0.6316 | 97.27 | 6.0 | 0.05810242425677139 |
| realcartest_0_1570 | 157 | 0.20 | 31 | 0.20 | 6 | 0.3930 | 59.35 | 6.0 | 0.0918151350167492 |
| realcartest_0_1570 | 157 | 0.30 | 47 | 0.20 | 9 | 0.2831 | 41.90 | 6.0 | 0.12525293875055254 |
| realcartest_2000_3200 | 120 | 0.10 | 12 | 0.20 | 2 | 0.7764 | 91.61 | 6.4 | 0.06529652927911898 |
| realcartest_2000_3200 | 120 | 0.20 | 24 | 0.20 | 5 | 0.4507 | 51.83 | 6.4 | 0.10990375584558044 |
| realcartest_2000_3200 | 120 | 0.30 | 36 | 0.20 | 7 | 0.3482 | 39.34 | 6.4 | 0.13991366836581492 |
| realcartest_3200_3830 | 63 | 0.10 | 6 | 0.20 | 1 | 0.9500 | 58.90 | 0.8 | 0.013400335008375211 |
| realcartest_3200_3830 | 63 | 0.20 | 13 | 0.20 | 3 | 0.6316 | 37.90 | 0.8 | 0.020674072442398165 |
| realcartest_3200_3830 | 63 | 0.30 | 19 | 0.20 | 4 | 0.5271 | 31.10 | 0.8 | 0.025077880506474838 |
| dataset3_0_1200 | 120 | 0.10 | 12 | 0.20 | 2 | 0.7764 | 91.61 | 2.2 | 0.023450558230454582 |
| dataset3_0_1200 | 120 | 0.20 | 24 | 0.20 | 5 | 0.4507 | 51.83 | 2.2 | 0.040716033075706176 |
| dataset3_0_1200 | 120 | 0.30 | 36 | 0.20 | 7 | 0.3482 | 39.34 | 2.2 | 0.0529578231720647 |
| dataset3_1200_2400 | 120 | 0.10 | 12 | 0.20 | 2 | 0.7764 | 91.61 | 4.6 | 0.04780989230354392 |
| dataset3_1200_2400 | 120 | 0.20 | 24 | 0.20 | 5 | 0.4507 | 51.83 | 4.6 | 0.08151292415885877 |
| dataset3_1200_2400 | 120 | 0.30 | 36 | 0.20 | 7 | 0.3482 | 39.34 | 4.6 | 0.10468227182463796 |
| dataset3_2400_3462 | 107 | 0.10 | 11 | 0.20 | 2 | 0.7764 | 81.52 | 3.0 | 0.03549401734865298 |
| dataset3_2400_3462 | 107 | 0.20 | 21 | 0.20 | 4 | 0.5271 | 54.29 | 3.0 | 0.05236122312922394 |
| dataset3_2400_3462 | 107 | 0.30 | 32 | 0.20 | 6 | 0.3930 | 39.70 | 3.0 | 0.07026285270406485 |

## 5. Caveats

- Uncovered-unit count is a *loose* upper estimate; no discovery coverage is subtracted, so M_ucb_unit is an *upper* upper bound. Tightening requires the per-call query ledger.
- Per-segment oracle event counts are ~6-20 and audit_n at low budget is often <=15; per-segment safe stopping at tau_r>=0.9 is statistically weak (p_ucb(15)=0.181, p_ucb(10)=0.259). Pooling across the 6 segments raises n_audit by ~6x but breaks the per-segment claim.
- The legacy `strategy7_certificate_power_v1` audit already validated the exact hypergeometric bound coverage (1.0 >= 0.95 nominal) and found R_lower too conservative (0.02-0.08 vs true recall 0.19-0.50) on these videos. That is a direct precedent for 'residual uncertainty reporting' but not for 'safe stopping certificate'.
- All discovered-event counts are `posthoc_eval` oracle-relative (B7-core uses event_id in selection); only D3-norepair-core is `strict_replay`. RC-AQP would need to re-discover its own candidate set, not inherit B7-core's D.
