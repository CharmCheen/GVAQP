# Fixed Lateral-Refinement Baselines

Only the preregistered `lateral_motion_signal` trigger passed the temporal gate. All policies are causal and use completed-unit observations only.

- `LG_ONE_NEIGHBOR` / `PSP_V0_SHORT`: AUC=0.6250, delta vs `ANYTIME_LARGEST_GAP`=+0.0954.
- `LG_TWO_NEIGHBOR` / `PSP_V0_SHORT`: AUC=0.6250, delta vs `ANYTIME_LARGEST_GAP`=+0.0954.
- `C75_R25` / `PSP_V0_SHORT`: AUC=0.5086, delta vs `ANYTIME_LARGEST_GAP`=-0.0211.
- `C50_R50` / `PSP_V0_SHORT`: AUC=0.5379, delta vs `ANYTIME_LARGEST_GAP`=+0.0082.
- `TWO_STAGE_COVER_THEN_REFINE` / `PSP_V0_SHORT`: AUC=0.5511, delta vs `ANYTIME_LARGEST_GAP`=+0.0214.
- `LG_ONE_NEIGHBOR` / `PSP_V1_LONG`: AUC=0.4878, delta vs `MACRO_REGION_LARGEST_GAP`=-0.0404.
- `LG_TWO_NEIGHBOR` / `PSP_V1_LONG`: AUC=0.4837, delta vs `MACRO_REGION_LARGEST_GAP`=-0.0446.
- `C75_R25` / `PSP_V1_LONG`: AUC=0.5364, delta vs `MACRO_REGION_LARGEST_GAP`=+0.0082.
- `C50_R50` / `PSP_V1_LONG`: AUC=0.5206, delta vs `MACRO_REGION_LARGEST_GAP`=-0.0076.
- `TWO_STAGE_COVER_THEN_REFINE` / `PSP_V1_LONG`: AUC=0.5108, delta vs `MACRO_REGION_LARGEST_GAP`=-0.0175.

```text
GUARDED_MARGINAL_SCAN_GATE = STOP
STABLE_REFINEMENT_WINNERS = NONE
```

The comparator is the strongest simple causal coverage policy separately on each video, not merely Sequential or Largest-Gap.
