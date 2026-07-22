# PSVR bottleneck research synthesis

`PSVR_TWO_VIDEO_SEARCH = NO_GO`

The strongest supported conclusion is that the frozen two-video workload has a heterogeneous
execution bottleneck, but the allowed simple rule family does not convert that diagnosis into a
stable cross-video method. H-BOTTLE2's fixed max-gap scan and cell-diverse VERIFY factors changed
neither V1 outcome nor any substantive macro threshold. H-STAGE1 then used the previously idle
deadline aggressively and exposed V1 positives, yet recovered zero V1 events in all 12 physical
ST1 cells.

The decisive failure chain is no longer “the scan never saw a positive.” On V1_Q1, positive units
produced candidates but those candidates never entered the capacity-10 frontier. On V1_Q2, half
of the positive candidates entered and survived in the frontier but none received VERIFY. Thus the
residual bottleneck is heterogeneous frontier retention plus VERIFY allocation under physical
budget, not proxy candidate generation or an intrinsic deadline floor.

ST1 did recover a second event on V0_Q2 in 6/6 cells, but it lost AUC on V0_Q1 and produced no V1
gain. Relative to F0, macro AUC improved only 5.75%, macro F1 by 0.0192, TTFC worsened by 5.3%, and
the four-task total gained only one event. All four preregistered quality thresholds failed.

The negative decision is conservative. Physical safety/durability passed, but the exact-repeat
signature gate failed in two V1 transition cells because physical latency allowed 8 versus 9 tail
VERIFY calls. Two pre-smoke validity repairs were also required. These deviations prohibit any
positive acceptance; they do not explain away V1's 0/12 semantic result.

No ablation or causal revision is triggered: the branch is not a near miss because the mandatory
cross-video direction is absent. No third video is requested because no core candidate was frozen.

`HELD_OUT_OPENED = false`
