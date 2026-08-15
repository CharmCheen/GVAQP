# Local Source of Truth (auditor's reconstruction, CPU-only)

This file is the auditor's independent consolidation of what the local
machine can actually support. It does not modify any project state file.

## Repository identity

- Path: `/Users/charmcheen/FDU/入学前/GVAQP`
- Git: single branch `main` (remote `origin/main`, `origin/dspro` present as
  refs); HEAD `973900696` ("Consolidate GVAQP research state and experiment
  artifacts", 2026-08-13); no worktrees, no stashes, no tags.
- Untracked local audit dirs exist: `outputs/ccf_independent_research_audit_v1/`,
  `outputs/endogenous_scan_root_cause_audit_v1/`.
- Migration provenance: repo consolidated from `/qiuyeqing/llama_prl/G-ARC`
  (frozen commit `5047241b…`) per `provenance/` manifests; a side study was
  staged at `/root/charm/GVAQP_side_rcsem` (per `RC_SEM_PACKAGE_MANIFEST.json`).

## What is machine-verified locally (class A; 56/56 deterministic checks)

1. **Proxy quality is weak and video-dependent.** AUPRC 0.3146 / 0.2584 /
   0.3112 (DALI/HANGZHOU/WUHAN); 1475 units; 251 semantic positives;
   candidate exposure recall 1.0 by construction.
2. **Ranking is the demonstrated bottleneck.** Ranking-stress low-budget
   median EventF1 gap 0.095134; synthetic exposure-stress gap 0.000000
   (exact frozen definition re-derived).
3. **Materialization changes model-relative recovery.** 54/54 controlled
   K3-vs-K0 pairs: 40 better / 14 equal / 0 worse; median ΔF1 +0.1457, mean
   +0.1840; consistent across 3 videos; selector-dependent (0.0182–0.2704).
4. **Nearly all of it is the 10-second gap rule.** Mechanism ablation:
   gap-only median +0.1377 (40/14/0); duration cap, negative barrier, and
   complex-K3 extras median 0.0. Complex-K3 novelty is NOT_ESTABLISHED.
5. **Quality is near-monotone in oracle-call budget** (0.48% nested-trace
   violations) — an invocation-budget property, not wall-clock.
6. **Selector × materializer interaction is systematic** (range 0.2573).
7. **Geometry explains model-relative terminal EventF1** (LOVO macro R²
   0.0057 → 0.7953 with public geometry; 0.9803 reference-aware) — but
   fails to transfer to the VLM-direct shadow (MAE gain 0.000665; 2/6
   clusters positive; proxy effects conflict) and P2 finds no semantic-state
   residual (median cluster ΔF1 0.0, 95% CI [−0.0136, 0.0223]).
8. **Learned action selection loses to a fixed action.** 108 cached states
   (2 source videos, abstract costs): learned regret 0.009693 vs fixed
   always-VERIFY 0.000885; gate FAIL. Physical probes: 0/18 immediate
   positives, 1/7 timing-only continuation conversions. Same-source
   Guangzhou repeat recovers one event at ~224 s in both runs.
9. **Protocol hashes are self-consistent** (4 protocol families re-hashed
   byte-exact), and the cited physical-probe sha256s match local files.
10. **Human P1 is frozen but empty.** 0 label rows; protocol sha verified;
    analysis NOT authorized.

## What exists only as report/narrative (classes B–D)

- The claimed endogenous preflight (class F locally / C if it ran remotely).
- Anything in `outputs/endogenous_scan_root_cause_audit_v1/` beyond its
  blocked fact-check (it is itself A-class evidence of absence).
- Older design-pack claims superseded by the state files.

## Auditor's bottom-line reconstruction

GVAQP's local evidence supports a **bounded, model-relative systems finding**:
weak proxy ranking creates real low-budget quality loss; a trivial gap-only
materializer repairs much of the model-relative event structure; adaptive
controllers fail to beat fixed policies on current substrates. The two
falsifiable open questions (human-event geometry utility H1; faithful
endogenous SCAN regret H2) have NO local empirical resolution: H1 is
pending human labels (0 collected), H2 has never been faithfully instantiated
anywhere verifiable.
