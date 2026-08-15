# REWARD_MINIMALITY_REPORT (ERAEA E3)

Same deterministic greedy executor, only the reward changes (R0 = proxy score
as the visible yield surrogate; R1..R4 = visible relation terms).

## Median AUC increments (R_k - R_{k-1}, across clusters)
- R1 - R0 = 0.0
- R2 - R1 = 0.0
- R3 - R2 = 0.0
- R4 - R3 = 0.0

Per-cluster R AUCs: {"R0": {"DALI": 0.1406, "HANGZHOU": 0.1669, "WUHAN": 0.1778}, "R1": {"DALI": 0.1455, "HANGZHOU": 0.1669, "WUHAN": 0.1778}, "R2": {"DALI": 0.1455, "HANGZHOU": 0.1669, "WUHAN": 0.1778}, "R3": {"DALI": 0.1455, "HANGZHOU": 0.1669, "WUHAN": 0.1778}, "R4": {"DALI": 0.1455, "HANGZHOU": 0.1669, "WUHAN": 0.1778}}

## Findings
1. R1 == R2 == R3 == R4 **exactly** at every budget on every cluster: the
   redundancy, merge-risk and boundary terms NEVER change the greedy's choice
   on this substrate (top-50 proxy candidates; terms inactive).
2. R1 vs R0 (new-component vs pure proxy score) differs only at high budgets
   on DALI (<= 0.005 AUC); HANGZHOU/WUHAN identical.
3. Minimal effective mechanism: **R1 (new-component) at most**; R2/R3/R4 terms
   add nothing measurable here.
- Per the routing rules: R2 already captures >=90% of R4's gain (it is
  identical to R4); the merge-risk/boundary terms have 0 independent gain and
  must not be packaged as a mechanism.
