# Remote Artifact Recovery Manifest — endogenous-SCAN preflight

Status: the claimed preflight is REPORTED_REMOTE_UNVERIFIED (absent locally).
Root-cause analysis of the claimed 0/36 remains NOT AUTHORIZED until the
artifacts below are recovered and hash-verified.

## Likely source environments (from local records)

- `/root/charm/GVAQP` (path cited in the original task prompt)
- `/root/charm/GVAQP_side_rcsem` (staging root recorded in
  `RC_SEM_PACKAGE_MANIFEST.json`)
- Any sibling worktree / archive of the above.

## Required artifacts (exact names as claimed)

| Artifact | Why it is required |
|---|---|
| `outputs/endogenous_scan_preflight_v1/ENDOGENOUS_SCAN_PREFLIGHT_REPORT.md` | headline decision and claim text |
| `outputs/endogenous_scan_preflight_v1/DECISION.json` | machine-readable decision fields |
| `outputs/endogenous_scan_preflight_v1/WORKLOAD_FREEZE.json` | which videos/units were used and their hashes |
| `outputs/endogenous_scan_preflight_v1/CHEAP_SCAN_CONTRACT.json` | operator, model checkpoint, decode settings |
| `outputs/endogenous_scan_preflight_v1/BEHAVIOR_POLICY_CONTRACT.json` | how the 57 prospective states were generated |
| `outputs/endogenous_scan_preflight_v1/NATURAL_EXPOSURE_RESULTS.csv` | per-unit exposure outcomes incl. the claimed 5 natural misses |
| `outputs/endogenous_scan_preflight_v1/NATURAL_EXPOSURE_MISSES.csv` | miss rows with taxonomy (`no_relevant_object_class` etc.) |
| `outputs/endogenous_scan_preflight_v1/PROSPECTIVE_STATE_LOG.csv` | 57 prospective dual-legal states with propensities |
| `outputs/endogenous_scan_preflight_v1/COUNTERFACTUAL_STATE_MANIFEST.csv` | the 36 frozen counterfactual states |
| `outputs/endogenous_scan_preflight_v1/ACTION_BRANCH_RESULTS.csv` | per-branch outcomes |
| `outputs/endogenous_scan_preflight_v1/ACTION_REGRET_BY_STATE.csv` | delta values at threshold 0.02 |
| `outputs/endogenous_scan_preflight_v1/ACTION_REGRET_BY_VIDEO.csv` | per-video aggregation |
| `outputs/endogenous_scan_preflight_v1/PHYSICAL_COST_PROFILE.csv` | measured SCAN 0.1071 s / VERIFY 18.4440 s claims |

## Recovery acceptance criteria (before any scientific use)

1. Directory plus all 13 files present, byte-identical naming.
2. Per-file sha256 recorded; video hashes cross-checked against locally known
   source hashes (DALI `64cb0cfa…`, HANGZHOU `69649cd2…`, WUHAN `bad22900…`).
3. Code entrypoint recovered and statically inspected for model calls; no
   re-execution on a CPU-only machine.
4. Substrate-fidelity claims reconciled with the local P4 ledger
   (`NOT_STARTED / NOT_AUTHORIZED`): if the preflight really ran, the ledger
   and state machine must be corrected by the project owner first — this
   audit does not modify them.
5. Only then may a root-cause audit of the 0/36 proceed — and it must still
   respect that one preflight at delta 0.02 cannot falsify the theory, only
   bound the tested SCAN1-vs-VERIFY1 formulation.

## Non-GPU recovery options

- The artifacts are CSVs/JSONs/MDs — copying them from the old machine
  requires no GPU.
- If the old environment is gone, nothing local can regenerate the physical
  measurements; the claim then stays REPORTED_REMOTE_UNVERIFIED forever.

## What does NOT need recovery

- The 1475-unit cached substrate, P0/P1/P2 artifacts, controller tables, and
  physical Guangzhou probes are all present locally with verified hashes.
