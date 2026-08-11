# Cost-adjusted Ranking Report

Every comparison pays preview cost inside the total wall-clock budget and executes complete regions only.

- `PSP_V0_SHORT` / `WALLCLOCK_60S`: proxy=4, coverage=5, Δ=-1.
- `PSP_V0_SHORT` / `FULL_SCAN_COST_10PCT`: proxy=5, coverage=5, Δ=0.
- `PSP_V0_SHORT` / `FULL_SCAN_COST_20PCT`: proxy=13, coverage=16, Δ=-3.
- `PSP_V0_SHORT` / `FULL_SCAN_COST_30PCT`: proxy=22, coverage=26, Δ=-4.
- `PSP_V1_LONG` / `WALLCLOCK_60S`: proxy=6, coverage=8, Δ=-2.
- `PSP_V1_LONG` / `FULL_SCAN_COST_10PCT`: proxy=18, coverage=23, Δ=-5.
- `PSP_V1_LONG` / `FULL_SCAN_COST_20PCT`: proxy=44, coverage=41, Δ=3.
- `PSP_V1_LONG` / `FULL_SCAN_COST_30PCT`: proxy=65, coverage=62, Δ=3.

The proxy is negative at 60 s on both videos. At larger q-derived budgets its direction remains budget- and video-dependent; this does not rescue the failed exploratory Gate.
