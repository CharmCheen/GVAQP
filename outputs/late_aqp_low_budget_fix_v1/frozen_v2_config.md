# Frozen-LATE-AQP-v2 Configuration

This is the refrozen configuration selected after low-budget diagnosis and tuning.

## Differences from v1

Only the low-budget audit schedule changed; all other components (E0 top20 envelope, repair utility U0_current, discovery ranking, B6/B7 baselines) remain identical to v1.

- **Selected variant**: `cold_start_fallback`
- **Audit schedule**: for budgets ≤ 20, skip audit entirely and use the full budget for discovery (repair trigger is disabled). Budgets > 20 keep v1 schedule.

## Tuning segment

- `realcartest_5k_tuning` (label_source=newly_generated_this_task)

## Final validation segment

- `realcartest_3830_3920_final` (label_source=existing_vlm_oracle)
