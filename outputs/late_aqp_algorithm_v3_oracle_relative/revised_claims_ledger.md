# Revised Claims Ledger

## A. Claims we can currently make

1. **Long-interval discovery under oracle-relative replay**
   - LATE-AQP improves mid-budget oracle-relative discovery of long-interval VEPC events compared with ExSample-style expansion in existing VLM-oracle replay.
   - Example: prior Ours-full recall@40 on long-interval events = 0.728 vs B7 = 0.564 (source: `late_aqp_h7_long_event_v1`).

2. **No selected-duration inflation at budget=40**
   - Ours-full and B7 both select 400 s of video at budget=40, so the recall gain is not explained by simply selecting more duration.
   - Ours-full precision@40 = 0.410 vs B7 = 0.364.

3. **Evidence consistent with candidate-envelope leakage**
   - Long events (e.g., event_0037, 50.7 s) span multiple 10 s bins; some positive bins fall outside a tight top-prior envelope, suggesting leakage.

4. **Dense \( O_{\text{ref}} \) labels exist**
   - `full_reference_units.csv` provides 2 s dense VLM-oracle labels for the full 20-minute video, enabling oracle-relative calibration without new oracle calls.

## B. Claims we cannot currently make

1. **Calibrated missing-mass estimation**
   - Dense labels exist but calibration evaluation has not been executed in this round.

2. **Human-grounded VEPC correctness**
   - \( O_{\text{ref}} \) is a VLM-oracle, not human ground truth.

3. **Formal precision/recall guarantee**
   - Results are empirical replay averages, not statistical certificates.

4. **Full interval reconstruction**
   - Complete-event coverage and boundary IoU remain weak.

5. **Causal attribution of gains to audit-triggered repair**
   - The current selection log lacks `source_action` lineage; repair trace is partially `unknown_not_logged`.

6. **Superiority over SUPG / ABae**
   - Those baselines were explicitly excluded from this round.

## C. Conditions for next claims

| Desired claim | Required next step |
|---------------|--------------------|
| "V3 audit schedule fixes budget=20" | Run the v3 schedule and show stable improvement at B=20 without sacrificing B=40. |
| "Repair utility improves long-event repair" | Show one utility consistently beats U0 on long_interval recall while preserving precision. |
| "Calibration is verified" | Execute calibration evaluation using existing dense `full_reference_units.csv`. |
| "Audit-triggered repair causally helps" | Add full repair trace logging and demonstrate that repair-hits come from outside-E0 seeds. |
| "Better than SUPG/ABae" | Implement and run those external baselines in a future round. |

## Quick empirical reference from this round

- Audit schedule v3: best long-event recall@20 = 0.517 (V3_two_phase) vs V2_static25 = 0.417.
- Audit schedule v3: best long-event recall@40 = 0.733 vs V2_static25 = 0.700.
- Best precision@40 among v3 schedules = V3_budget_aware.
- Repair utility v3: best long-event recall@40 = 0.750 (U1_leakage_density).
