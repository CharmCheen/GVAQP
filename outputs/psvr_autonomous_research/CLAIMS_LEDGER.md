# PSVR Claims Ledger

## Final two-video bottleneck claims — 2026-07-18

### Supported

- H-RECOVER1 establishes heterogeneous recoverability: VERIFY order on V0_Q1, scan exposure on V0_Q2/V1_Q1, and a V1_Q2 floor only at the original fixed action count.
- H-BOTTLE2 is a valid 96-cell null factorial: fixed max-gap scan, cell-diverse VERIFY, and their combination produce no cross-video signal.
- H-STAGE1 is physically safe/durable in 48/48 cells and converts idle deadline into substantially more actions.
- ST1 consistently recovers a second event on V0_Q2 but zero events on either V1 task in 12/12 cells.
- V1_Q1 residual loss is frontier retention/admission; V1_Q2 residual loss is VERIFY order/budget after partial frontier entry.
- No tested rule method satisfies the core-candidate standard; `PSVR_TWO_VIDEO_SEARCH=NO_GO`.

### Limitations and negative controls

- H-STAGE1 exact query signatures agree in 14/16 cells, so its preregistered correctness gate is not fully passed.
- Two validity repairs occurred in the cycle; evidence is negative and procedurally qualified.
- The legacy every-three-scan survival metric is not used for ST1; actual lifecycle tables are authoritative.
- Invalidated interrupted diagnostic attempts do not have complete total-GPU summaries and are excluded from formal cost.
- `HELD_OUT_OPENED=false`; no generalization video is requested because no candidate was frozen.

### Not supported

- A usable PSVR core method.
- A cross-video scan, VERIFY, interaction, or stage-controller quality mechanism.
- Proxy candidate generation as the dominant V1 failure; V1 positives do generate candidates.
- An intrinsic V1 deadline floor independent of action allocation.

## Two-video terminal evidence (2026-07-17)

- `TWO_VIDEO_DEV_BENCHMARK=PASS`; YOLOV8/Y8 remains the uniquely selected proxy and its
  physical regime revalidation passes.
- The H-EXPOSE2 R3 matrix is complete and valid at 72/72 cells with zero deadline miss,
  replay, future access, visibility violation, failed cell, duplicate, or missing snapshot.
- Existing reference matching rejects H-EXPOSE2: R3 improves 0/4 tasks, passes no substantive
  threshold, has no V1 contribution, and has no mechanism alignment versus FIFO.
- `TWO_VIDEO_CORE_SIGNAL=ABSENT`; H-EXPOSE2 ablation was not run because the hypothesis was
  rejected after its only permitted revision.
- FIFO is the descriptive best method, but its advantage is driven by a single V0_Q1 event;
  it is not established as a cross-video mechanism or usable method.
- R3 and score-only have identical endpoint quality and near-identical AnytimeAUC; R3 changes
  some V1 negative VERIFY choices without producing a cross-video benefit.
- Held-out remains unopened. Further adaptive work on the same two videos is not authorized;
  a third independent source is required before another core route can be assessed.

## Supported on the current development task

- The frozen oracle reference is complete and deterministically reconstructable for the 347-unit benchmark.
- The tested capability boundary blocks unqueried label/reference access.
- H-DS1 is empirically deadline-safe for the frozen one-video/query/A800 workload used here.
- H-FACT1 shows that scan ordering, not adaptive VERIFY's independent main effect, drives the current-task quality signal.
- H-SCAN1A shows the proxy-independent structural group is sufficient on this task under frozen A0 **and the frozen ascending TB0 exact-tie order**: D2 is effective in 6/6 formal runtime repeats while proxy-only D3 is ineffective in 0/6.
- D2 has higher mean AnytimeAUC and lower median TTFC than D1 in the fresh H-SCAN1A matrix, with no added deadline misses.

## Supported limitations and negative evidence

- Fixed Coverage D0 and proxy-only D3 recover no events in the H-SCAN1A formal matrix despite equal scan batches and five VERIFY calls.
- D3 has a much worse max gap (1725 s) and global gap integral than D1/D2.
- H-SCAN1A is not blind to all related component evidence because an earlier different Stage-4 experiment existed; this is disclosed and not pooled.
- D2's event path is conditional on the frozen hierarchy and deterministic tie-break.
- H-SCAN1B directly establishes tie sensitivity on the current task: TB0 succeeds 3/3, while TB1 and TB2 fail 0/6 under otherwise frozen execution.
- Equal final coverage and maximum gap across TB0/TB1/TB2 do not imply equal candidate frontiers or event recovery.
- The bounded Phase-A inventory contains 609 candidate rows and 607 existing paths, but only `long_video_dataset3` satisfies the current independent-long-source gate.
- The Nexar roots contain 604 ffprobe-visible paths representing 603 unique file hashes; all are 15.00–49.464883 seconds and zero meet the frozen 1200-second workload minimum.
- `realcartest_5k` is a documented prefix derivative, the canonical long `realcartest` bytes are absent, dataset2 bytes are absent and its recorded in-cabin view is semantically unsuitable, and DrivingDojo-mini has no video-container entries.
- Two additional independent long source videos are required. Input insufficiency is an autonomous pause, not a method failure and not project-level `NO_GO`.
- The authoritative Phase-A audit excludes canonical held-out media/reference access. A superseded draft performed metadata-only ffprobe/SHA access to `try_or_no/test.mov`; no held-out semantics, labels, method evaluation, or tuning were accessed.

## Not yet supported

- Whether duration/coverage or scan-level/hierarchical debt is the structural driver; the factorial was correctly not run after the tie gate failed.
- That observed proxy signal is harmful in general; only proxy-only sufficiency is unsupported on this task.
- Cross-video, cross-query, scene-category, hardware, or held-out generalization.
- That runtime repeats are independent semantic samples.
- A usable production method or paper-level core innovation.
- Whether midpoint plus ascending ordering generalizes; the required independent multi-video/multi-query physical inputs are missing.
- `H-COV1` acceptance; its current status is `REVISE_TIE_SENSITIVE` after H-SCAN1B.
- That the current local input pool supports a three-video development benchmark; it does not.
- Any multi-video, second-query, usability, or paper-ready claim.

Authoritative evidence: `stage_3_factorization/AUDITED_DECISION.json`, `stage_4_scan_component_ablation/AUDITED_DECISION.json`, `cycle_05_H_SCAN1B/TIE_GATE_DECISION.json`, `benchmark_unblock/`, and `cycle_07_BENCHMARK_UNBLOCK/CORRECTNESS_REPORT.json`, with raw physical attempts retained below each experiment directory.
